import os
import chess
import chess.pgn
import chess.engine
from collections import Counter
from flask import Flask, jsonify, send_from_directory, render_template_string, Response, request
from flask_cors import CORS
from get_games import fetch_user_games
from analyze_games import analyze_game
import time  # Add time import for performance tracking
import json
import threading
import queue
from threading import Thread
import logging
import subprocess
import tempfile
import re
import glob

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

#--- Configuration ---
STOCKFISH_PATH = os.path.join(os.path.dirname(__file__), "stockfish", "stockfish.exe")
GAMES_TO_FETCH = 1
BLUNDER_THRESHOLD = 15
ENGINE_THINK_TIME = 0.1

# General descriptions for blunder categories (for hero stat)
BLUNDER_GENERAL_DESCRIPTIONS = {
    "Allowed Checkmate": "You played moves that allowed your opponent to deliver checkmate when it could have been avoided.",
    "Missed Checkmate": "You had opportunities to checkmate your opponent but played different moves instead.", 
    "Allowed Fork": "Your moves allowed your opponent to fork (attack multiple pieces simultaneously) with a single piece.",
    "Missed Fork": "You missed chances to fork your opponent's pieces, potentially winning material or gaining tactical advantage.",
    "Allowed Pin": "You positioned your pieces in ways that allowed your opponent to pin them (restrict their movement by attacking through them to more valuable pieces).",
    "Missed Pin": "You overlooked opportunities to pin your opponent's pieces, missing tactical advantages.",
    "Hanging a Piece": "You left pieces undefended, allowing your opponent to capture them for free or with favorable exchanges.",
    "Losing Exchange": "You initiated trades that resulted in losing more material value than you gained.",
    "Missed Material Gain": "You missed opportunities to capture opponent pieces or win material through tactical sequences.",
    "Mistake": "You made moves that significantly worsened your position according to engine evaluation."
}
#--- End Configuration ---

# Global progress tracking
progress_queues = {}
progress_lock = threading.Lock()
progress_trackers = {}

def send_progress_update(session_id, step, message, progress_percent=None, time_elapsed=None):
    """Send a progress update to the specified session"""
    with progress_lock:
        if session_id in progress_queues:
            update = {
                "step": step,
                "message": message,
                "progress": progress_percent,
                "time_elapsed": time_elapsed,
                "timestamp": time.time()
            }
            try:
                progress_queues[session_id].put_nowait(update)
            except queue.Full:
                pass  # Skip if queue is full

def cleanup_progress_session(session_id):
    """Clean up progress tracking for a session"""
    with progress_lock:
        if session_id in progress_queues:
            del progress_queues[session_id]

@app.route("/")
def home():
    """
    Serve the main HTML page.
    """
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        return "index.html not found", 404

@app.route("/styles.css")
def serve_css():
    """
    Serve the CSS file.
    """
    return send_from_directory('.', 'styles.css')

@app.route("/main.js")
def serve_js():
    """
    Serve the JavaScript file.
    """
    return send_from_directory('.', 'main.js')

def analyze_multiple_games(pgn_file_path, username, stockfish_path, blunder_threshold, engine_think_time, progress_tracker=None):
    """
    Wrapper function that processes multiple games from a PGN file and aggregates blunder data.
    
    Args:
        pgn_file_path (str): Path to the PGN file
        username (str): Username to analyze blunders for
        stockfish_path (str): Path to Stockfish engine
        blunder_threshold (float): Win probability drop threshold for blunder detection
        engine_think_time (float): Engine analysis time per move
        progress_tracker (ProgressTracker): Optional progress tracker for real-time updates
    
    Returns:
        dict: Structured summary with blunder statistics and detailed list
    """
    step_start = time.time()
    
    print(f"📥 Step 1: Initializing Stockfish engine from {stockfish_path}")

    # Initialize Stockfish engine
    try:
        engine_start = time.time()
        if progress_tracker:
            progress_tracker.update("engine_init", "🔧 Initializing Stockfish engine...", mark_complete=False)
        
        engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
        engine_time = time.time() - engine_start
        print(f"✅ Engine initialized successfully in {engine_time:.2f} seconds")
        
        if progress_tracker:
            progress_tracker.update("engine_init", f"✅ Engine initialized in {engine_time:.2f}s", mark_complete=True)
            
    except Exception as e:
        print(f"❌ Engine initialization failed: {str(e)}")
        if progress_tracker:
            progress_tracker.update("error", f"❌ Engine initialization failed: {str(e)}")
        return {"error": f"Could not initialize Stockfish engine: {str(e)}"}

    # Process games and collect blunders
    all_blunders = []
    games_analyzed = 0
    
    print(f"📖 Step 2: Reading PGN file '{pgn_file_path}'")
    
    if progress_tracker:
        progress_tracker.update("reading_pgn", f"📖 Reading PGN file...", mark_complete=False)
    
    try:
        file_start = time.time()
        with open(pgn_file_path, 'r', encoding='utf-8') as pgn_file:
            file_time = time.time() - file_start
            print(f"✅ PGN file opened in {file_time:.3f} seconds")
            
            if progress_tracker:
                progress_tracker.update("reading_pgn", f"✅ PGN file read in {file_time:.3f}s", mark_complete=True)
            
            while True:
                game_read_start = time.time()
                game = chess.pgn.read_game(pgn_file)
                if game is None:
                    break
                
                games_analyzed += 1
                game_read_time = time.time() - game_read_start
                print(f"🎯 Step 3.{games_analyzed}: Analyzing game #{games_analyzed}")
                print(f"   Game read in {game_read_time:.3f} seconds")
                
                # Get game info
                white_player = game.headers.get("White", "Unknown")
                black_player = game.headers.get("Black", "Unknown")
                print(f"   Players: {white_player} vs {black_player}")
                
                if progress_tracker:
                    # Show current game but don't mark analyzing_games complete until all done
                    progress_tracker.update("analyzing_games", 
                                          f"🎯 Analyzing game #{games_analyzed}: {white_player} vs {black_player}", 
                                          mark_complete=False)
                
                # Analyze this game for blunders
                analysis_start = time.time()
                blunders = analyze_game(
                    game=game,
                    engine=engine,
                    target_user=username,
                    blunder_threshold=blunder_threshold,
                    engine_think_time=engine_think_time,
                    debug_mode=False
                )
                analysis_time = time.time() - analysis_start
                
                print(f"   ✅ Game analysis completed in {analysis_time:.2f} seconds")
                print(f"   Found {len(blunders)} blunders in this game")
                
                all_blunders.extend(blunders)
            
            # Mark game analysis complete after all games processed
            if progress_tracker:
                progress_tracker.update("analyzing_games", 
                                      f"✅ Analyzed {games_analyzed} game(s), found {len(all_blunders)} blunders", 
                                      mark_complete=True)
                
    except FileNotFoundError:
        engine.quit()
        print(f"❌ PGN file not found: {pgn_file_path}")
        if progress_tracker:
            progress_tracker.update("error", f"❌ PGN file not found")
        return {"error": f"Could not find PGN file: {pgn_file_path}"}
    except Exception as e:
        engine.quit()
        print(f"❌ Error processing games: {str(e)}")
        if progress_tracker:
            progress_tracker.update("error", f"❌ Error processing games: {str(e)}")
        return {"error": f"Error processing games: {str(e)}"}
    finally:
        # Always close the engine
        engine_close_start = time.time()
        engine.quit()
        engine_close_time = time.time() - engine_close_start
        print(f"🔒 Engine closed in {engine_close_time:.3f} seconds")

    # Aggregate blunder statistics
    aggregation_start = time.time()
    print(f"📊 Step 4: Aggregating blunder statistics...")
    
    if progress_tracker:
        progress_tracker.update("aggregating", f"📊 Calculating statistics from {len(all_blunders)} blunders...", mark_complete=False)
    
    if not all_blunders:
        total_time = time.time() - step_start
        print(f"✨ Analysis complete! Total time: {total_time:.2f} seconds")
        
        if progress_tracker:
            progress_tracker.complete(f"✨ No blunders found! Total time: {total_time:.2f}s")
        
        return {
            "success": True,
            "username": username,
            "games_analyzed": games_analyzed,
            "summary": {
                "total_blunders": 0,
                "most_common_blunder": None,
                "message": "No blunders detected in the analyzed games!"
            },
            "blunders": []
        }

    # Count blunder categories
    blunder_categories = [blunder['category'] for blunder in all_blunders]
    category_counts = Counter(blunder_categories)
    
    # Find most common blunder
    most_common = category_counts.most_common(1)[0]
    most_common_category = most_common[0]
    most_common_count = most_common[1]
    most_common_percentage = round((most_common_count / len(all_blunders)) * 100, 1)
    
    # Get general description for the most common blunder category
    general_description = BLUNDER_GENERAL_DESCRIPTIONS.get(
        most_common_category, 
        f"You frequently made {most_common_category.lower()} errors during your games."
    )
    
    # Create structured summary
    summary = {
        "total_blunders": len(all_blunders),
        "most_common_blunder": {
            "category": most_common_category,
            "count": most_common_count,
            "percentage": most_common_percentage,
            "general_description": general_description  # General description for hero stat
        },
        "category_breakdown": dict(category_counts)
    }
    
    aggregation_time = time.time() - aggregation_start
    total_time = time.time() - step_start
    print(f"✅ Statistics aggregated in {aggregation_time:.3f} seconds")
    print(f"🎉 Analysis complete! Total time: {total_time:.2f} seconds")
    print(f"📈 Results: {len(all_blunders)} total blunders across {games_analyzed} games")
    
    if progress_tracker:
        progress_tracker.update("aggregating", f"✅ Statistics calculated in {aggregation_time:.3f}s", mark_complete=True)
        progress_tracker.complete(f"🎉 Found {len(all_blunders)} blunders! Most common: {most_common_category}")
    
    return {
        "success": True,
        "username": username,
        "games_analyzed": games_analyzed,
        "summary": summary,
        "blunders": all_blunders
    }

@app.route("/api/analyze", methods=['POST'])
def analyze_endpoint():
    """Handle analysis requests with new settings support"""
    global progress_trackers
    
    try:
        data = request.json
        session_id = data.get('session_id')
        username = data.get('username', '').strip()
        game_count = data.get('gameCount', 20)
        game_types = data.get('gameTypes', ['blitz', 'rapid'])
        rating_filter = data.get('ratingFilter', 'rated')
        analysis_depth = data.get('analysisDepth', 'balanced')
        
        # Validate input
        if not session_id or not username:
            return jsonify({'error': 'Session ID and username are required'}), 400
        
        # Map analysis depth to engine think time
        depth_mapping = {
            'fast': 0.1,
            'balanced': 0.2,
            'deep': 0.5
        }
        engine_think_time = depth_mapping.get(analysis_depth, 0.2)
        
        # Initialize progress tracker
        progress_trackers[session_id] = ProgressTracker(session_id, game_count)
        tracker = progress_trackers[session_id]
        
        # Start analysis in background thread
        def run_analysis():
            try:
                # Phase 1: Game fetching with settings
                tracker.start_phase("fetching_games", f"Fetching {game_count} {', '.join(game_types)} games ({rating_filter})")
                
                # Create filter object for get_games.py
                game_filters = {
                    'game_count': game_count,
                    'game_types': game_types,
                    'rating_filter': rating_filter
                }
                
                # Get filtered games and metadata
                pgn_content, games_metadata = fetch_games_with_filters(username, game_filters, tracker)
                
                if not pgn_content:
                    tracker.set_error("No games found matching the specified criteria")
                    return
                
                # Phase 2: Engine initialization
                tracker.start_phase("engine_init", "Initializing Stockfish engine")
                
                # Phase 3: Game analysis with new settings
                tracker.start_phase("analyzing_games", f"Analyzing games with {analysis_depth} depth")
                
                # Run analysis with settings
                results = analyze_games_with_settings(
                    pgn_content, 
                    username, 
                    engine_think_time,
                    tracker
                )
                
                if results:
                    # Phase 4: Pattern aggregation and scoring
                    tracker.start_phase("aggregating", "Calculating blunder patterns and scores")
                    
                    try:
                        # Update progress to show transformation is starting
                        tracker.update_progress(96, "🔄 Processing analysis results...")
                        
                        # Use actual games analyzed count from results, not requested count
                        actual_games_analyzed = results.get('games_analyzed', game_count)
                        
                        # Log detailed info for debugging
                        logger.info(f"Transforming results for session {session_id}: {len(results.get('blunders', []))} blunders from {actual_games_analyzed} games")
                        logger.info(f"Games metadata length: {len(games_metadata) if games_metadata else 0}")
                        
                        # Transform results into new format with detailed error catching
                        try:
                            final_results = transform_results_for_frontend(results, actual_games_analyzed, games_metadata)
                            logger.info(f"Successfully transformed results for session {session_id}")
                        except Exception as transform_error:
                            logger.error(f"Transform function failed for session {session_id}: {str(transform_error)}")
                            logger.error(f"Transform error traceback:", exc_info=True)
                            raise transform_error
                        
                        # Update progress to show completion
                        tracker.update_progress(99, "✨ Finalizing results...")
                        logger.info(f"About to call tracker.complete() for session {session_id}")
                        
                        # Force a small delay to ensure progress update is sent
                        time.sleep(0.1)
                        
                        # Complete with results - with comprehensive error handling
                        try:
                            logger.info(f"CALLING tracker.complete() NOW for session {session_id}")
                            logger.info(f"Results type: {type(final_results)}")
                            logger.info(f"Results keys: {list(final_results.keys()) if isinstance(final_results, dict) else 'not a dict'}")
                            
                            tracker.complete(final_results)
                            logger.info(f"COMPLETED tracker.complete() call for session {session_id}")
                            
                        except Exception as complete_error:
                            logger.error(f"EXCEPTION in tracker.complete() for session {session_id}: {str(complete_error)}")
                            logger.error(f"Complete error traceback:", exc_info=True)
                            # Try to send error instead
                            try:
                                tracker.set_error(f"Completion failed: {str(complete_error)}")
                            except Exception as error_error:
                                logger.error(f"Failed to send error message: {str(error_error)}")
                        
                        # Additional delay to ensure completion message is processed
                        time.sleep(0.2)
                        logger.info(f"Final completion processing done for session {session_id}")
                        
                        # Force final completion message if needed
                        try:
                            logger.info(f"Sending final completion backup for session {session_id}")
                            with progress_lock:
                                if session_id in progress_queues:
                                    backup_update = {
                                        "step": "complete",
                                        "status": "completed", 
                                        "message": "Analysis completed successfully!",
                                        "percentage": 100.0,
                                        "results": final_results,
                                        "timestamp": time.time()
                                    }
                                    try:
                                        progress_queues[session_id].put_nowait(backup_update)
                                        logger.info(f"Backup completion message queued for session {session_id}")
                                    except queue.Full:
                                        logger.error(f"Could not queue backup completion for session {session_id}")
                        except Exception as backup_error:
                            logger.error(f"Backup completion failed for session {session_id}: {str(backup_error)}")
                        
                    except Exception as transform_error:
                        logger.error(f"Error transforming results for session {session_id}: {str(transform_error)}")
                        logger.error(f"Error details: {repr(transform_error)}")
                        # Also log the results structure for debugging
                        logger.error(f"Results structure: {type(results)}, keys: {list(results.keys()) if isinstance(results, dict) else 'not a dict'}")
                        logger.error(f"Full traceback:", exc_info=True)
                        tracker.set_error(f"Failed to process analysis results: {str(transform_error)}")
                else:
                    tracker.set_error("Analysis failed to produce results")
                    
            except Exception as e:
                logger.error(f"Analysis error for session {session_id}: {str(e)}")
                tracker.set_error(f"Analysis failed: {str(e)}")
        
        # Start background thread
        thread = Thread(target=run_analysis)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'started',
            'session_id': session_id,
            'message': f'Analysis started for {username}'
        })
        
    except Exception as e:
        logger.error(f"Error starting analysis: {str(e)}")
        return jsonify({'error': str(e)}), 500

def fetch_games_with_filters(username, filters, tracker):
    """Fetch games using the updated get_games.py with filtering support"""
    try:
        # Update progress
        tracker.update_progress(5, f"Connecting to Chess.com API for {username}")
        
        # Build command with correct arguments that get_games.py actually supports
        cmd = [
            'python', 'get_games.py',
            '--username', username,
            '--num_games', str(filters['game_count'])  # Correct argument name
        ]
        
        # Add rating filter using the correct argument
        if filters['rating_filter'] == 'rated':
            cmd.extend(['--filter', 'rated'])
        elif filters['rating_filter'] == 'unrated':
            cmd.extend(['--filter', 'unrated'])
        else:  # 'all' or other values
            cmd.extend(['--filter', 'both'])
        
        # Add game type filters using the correct flags
        if filters['game_types']:
            if 'rapid' in filters['game_types']:
                cmd.append('--rapid')
            if 'blitz' in filters['game_types']:
                cmd.append('--blitz')
            if 'bullet' in filters['game_types']:
                cmd.append('--bullet')
            if 'daily' in filters['game_types']:
                cmd.append('--daily')
        # If no specific types selected, get_games.py will fetch all types by default
        
        tracker.update_progress(10, f"Downloading {filters['game_count']} games...")
        
        try:
            # Run get_games.py - it will create its own PGN file
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                # If it failed, try with minimal arguments
                tracker.update_progress(12, "Retrying with simpler game fetch...")
                cmd_simple = [
                    'python', 'get_games.py',
                    '--username', username,
                    '--num_games', str(min(filters['game_count'], 20)),  # Limit for safety
                    '--filter', 'rated'  # Default to rated games
                ]
                
                result = subprocess.run(cmd_simple, capture_output=True, text=True, timeout=120)
                
                if result.returncode != 0:
                    error_msg = result.stderr.strip() or result.stdout.strip() or "Failed to fetch games"
                    raise Exception(f"Game fetch failed: {error_msg}")
                    
        except subprocess.TimeoutExpired:
            raise Exception("Game fetching timed out")
        
        # get_games.py creates its own filename and prints it
        # Parse the output to find the created filename
        output_lines = result.stdout.strip().split('\n')
        created_filename = None
        
        for line in output_lines:
            if "PGN file saved as" in line:
                # Extract filename from "PGN file saved as 'filename'"
                parts = line.split("'")
                if len(parts) >= 2:
                    created_filename = parts[1]
                    break
        
        if not created_filename:
            # Try to find any .pgn file that was created recently for this username
            pattern = f"{username}_last_*_*.pgn"
            matching_files = glob.glob(pattern)
            if matching_files:
                # Get the most recently created file
                created_filename = max(matching_files, key=os.path.getctime)
        
        if not created_filename or not os.path.exists(created_filename):
            raise Exception("PGN file was not created by get_games.py")
        
        # Read the generated PGN file and metadata
        try:
            with open(created_filename, 'r', encoding='utf-8') as f:
                pgn_content = f.read()
            
            if not pgn_content.strip():
                raise Exception("No game data received - the PGN file is empty")
            
            # Read games metadata
            metadata_filename = created_filename.replace('.pgn', '_metadata.json')
            games_metadata = []
            
            if os.path.exists(metadata_filename):
                try:
                    with open(metadata_filename, 'r', encoding='utf-8') as f:
                        games_metadata = json.load(f)
                except Exception as e:
                    logger.warning(f"Could not read games metadata: {e}")
                    games_metadata = []
            
            tracker.update_progress(20, f"Successfully downloaded games")
            return pgn_content, games_metadata
            
        finally:
            # Clean up the created files
            for filename in [created_filename, created_filename.replace('.pgn', '_metadata.json')]:
                if os.path.exists(filename):
                    try:
                        os.unlink(filename)
                    except:
                        pass  # Don't fail if we can't clean up
                
    except Exception as e:
        logger.error(f"Failed to fetch games for {username}: {str(e)}")
        raise Exception(f"Failed to fetch games: {str(e)}")

def analyze_games_with_settings(pgn_content, username, engine_think_time, tracker):
    """Run game analysis with detailed progress tracking per game"""
    try:
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pgn', delete=False) as pgn_file:
            pgn_file.write(pgn_content)
            pgn_filename = pgn_file.name
        
        try:
            # Use the enhanced analyze_multiple_games function directly for better progress tracking
            results = analyze_multiple_games_enhanced(
                pgn_filename, 
                username, 
                STOCKFISH_PATH, 
                15,  # blunder_threshold
                engine_think_time, 
                tracker
            )
            
            if results.get("error"):
                raise Exception(results["error"])
            
            return {
                'blunders': results.get('blunders', []),
                'username': username,
                'total_blunders': len(results.get('blunders', [])),
                'games_analyzed': results.get('games_analyzed', 0)
            }
            
        finally:
            # Clean up
            if os.path.exists(pgn_filename):
                os.unlink(pgn_filename)
                
    except Exception as e:
        raise Exception(f"Analysis failed: {str(e)}")

def analyze_multiple_games_enhanced(pgn_file_path, username, stockfish_path, blunder_threshold, engine_think_time, progress_tracker=None):
    """
    Enhanced version of analyze_multiple_games with detailed per-game progress tracking
    """
    step_start = time.time()
    
    # Initialize Stockfish engine
    try:
        engine_start = time.time()
        if progress_tracker:
            progress_tracker.update_progress(25, "🔧 Initializing Stockfish engine...")
        
        engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
        engine_time = time.time() - engine_start
        
        if progress_tracker:
            progress_tracker.update_progress(30, f"✅ Engine initialized in {engine_time:.2f}s")
            
    except Exception as e:
        if progress_tracker:
            progress_tracker.set_error(f"❌ Engine initialization failed: {str(e)}")
        return {"error": f"Could not initialize Stockfish engine: {str(e)}"}

    # Process games and collect blunders
    all_blunders = []
    games_analyzed = 0
    total_games = 0
    
    # First pass: count total games
    try:
        with open(pgn_file_path, 'r', encoding='utf-8') as pgn_file:
            while True:
                game = chess.pgn.read_game(pgn_file)
                if game is None:
                    break
                total_games += 1
    except:
        total_games = 1  # Fallback
    
    if progress_tracker:
        progress_tracker.update_progress(35, f"📖 Found {total_games} game(s) to analyze")
    
    try:
        with open(pgn_file_path, 'r', encoding='utf-8') as pgn_file:
            while True:
                game_read_start = time.time()
                game = chess.pgn.read_game(pgn_file)
                if game is None:
                    break
                
                games_analyzed += 1
                
                # Get game info
                white_player = game.headers.get("White", "Unknown")
                black_player = game.headers.get("Black", "Unknown")
                
                # Calculate progress for this game (35% to 85% range)
                game_progress_start = 35 + ((games_analyzed - 1) / total_games) * 50
                game_progress_end = 35 + (games_analyzed / total_games) * 50
                
                if progress_tracker:
                    progress_tracker.update_progress(
                        game_progress_start, 
                        f"🎯 Analyzing game #{games_analyzed}: {white_player} vs {black_player}"
                    )
                
                # Analyze this game for blunders
                analysis_start = time.time()
                blunders = analyze_game(
                    game=game,
                    engine=engine,
                    target_user=username,
                    blunder_threshold=blunder_threshold,
                    engine_think_time=engine_think_time,
                    debug_mode=False
                )
                analysis_time = time.time() - analysis_start
                
                if progress_tracker:
                    progress_tracker.update_progress(
                        game_progress_end, 
                        f"✅ Game #{games_analyzed} complete: found {len(blunders)} blunder(s) ({analysis_time:.1f}s)"
                    )
                
                all_blunders.extend(blunders)
            
    except FileNotFoundError:
        engine.quit()
        if progress_tracker:
            progress_tracker.set_error("❌ PGN file not found")
        return {"error": f"Could not find PGN file: {pgn_file_path}"}
    except Exception as e:
        engine.quit()
        if progress_tracker:
            progress_tracker.set_error(f"❌ Error processing games: {str(e)}")
        return {"error": f"Error processing games: {str(e)}"}
    finally:
        # Always close the engine
        engine.quit()

    if progress_tracker:
        progress_tracker.update_progress(90, f"📊 Calculating statistics from {len(all_blunders)} blunders...")
    
    total_time = time.time() - step_start
    
    if progress_tracker:
        progress_tracker.update_progress(95, f"🎉 Analysis complete in {total_time:.1f}s!")
    
    return {
        "success": True,
        "username": username,
        "games_analyzed": games_analyzed,
        "blunders": all_blunders
    }

def sanitize_blunders_for_json(blunders):
    """Convert Move objects to strings in blunder data for JSON serialization"""
    sanitized = []
    for blunder in blunders:
        sanitized_blunder = blunder.copy()
        
        # Convert punishing_move from Move object to string
        if 'punishing_move' in sanitized_blunder and sanitized_blunder['punishing_move'] is not None:
            move_obj = sanitized_blunder['punishing_move']
            if hasattr(move_obj, 'uci'):  # Check if it's a Move object
                sanitized_blunder['punishing_move'] = move_obj.uci()  # Convert to UCI string
            
        sanitized.append(sanitized_blunder)
    
    return sanitized

def transform_results_for_frontend(results, games_analyzed, games_metadata=None):
    """Transform analysis results into the new frontend format"""
    try:
        blunders = results.get('blunders', [])
        
        # CRITICAL FIX: Sanitize blunders to convert Move objects to strings
        sanitized_blunders = sanitize_blunders_for_json(blunders)
        
        # Format games metadata for frontend
        games_list = []
        if games_metadata:
            for i, game in enumerate(games_metadata, 1):
                games_list.append({
                    'number': i,
                    'white': game.get('white', 'Unknown'),
                    'black': game.get('black', 'Unknown'),
                    'date': game.get('date', 'Unknown date'),
                    'time_class': game.get('time_class', 'unknown'),
                    'rated': game.get('rated', False),
                    'url': game.get('url', ''),
                    'target_player': game.get('target_player', '')
                })
        
        if not sanitized_blunders:
            return {
                'games_analyzed': games_analyzed,
                'total_blunders': 0,
                'hero_stat': {
                    'category': 'No Blunders Found',
                    'score': 0,
                    'description': 'Great job! No significant blunders were detected in your games.',
                    'examples': []
                },
                'blunder_breakdown': [],
                'games_list': games_list
            }
        
        # Group blunders by category (using sanitized blunders)
        grouped = {}
        for blunder in sanitized_blunders:
            category = blunder.get('category', 'Unknown')
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(blunder)
        
        # Calculate scores for each category with improved metrics
        blunder_breakdown = []
        for category, category_blunders in grouped.items():
            frequency = len(category_blunders)
            
            # Calculate average impact (placeholder calculation for now)
            # TODO: Extract actual win probability drops from blunder descriptions
            base_impact = {
                'Allowed Checkmate': 45.0,
                'Missed Checkmate': 40.0,
                'Hanging a Piece': 25.0,
                'Allowed Fork': 20.0,
                'Missed Fork': 18.0,
                'Losing Exchange': 15.0,
                'Missed Material Gain': 12.0,
                'Allowed Pin': 10.0,
                'Missed Pin': 8.0,
                'Mistake': 15.0
            }.get(category, 15.0)
            
            # Add some variance based on frequency (more occurrences might mean less severe on average)
            avg_impact = max(5.0, base_impact - (frequency * 0.5))
            
            # Calculate severity score: frequency * category weight * impact
            severity_score = frequency * get_category_weight(category) * (avg_impact / 10.0)
            
            breakdown_item = {
                'category': category,
                'severity_score': round(severity_score, 1),
                'frequency': frequency,
                'avg_impact': round(avg_impact, 1),
                'description': get_general_description(category),
                'all_occurrences': category_blunders,  # Now using sanitized blunders
                'examples': category_blunders[:3]  # First 3 examples for preview (sanitized)
            }
            blunder_breakdown.append(breakdown_item)
        
        # Sort by severity score (highest first)
        blunder_breakdown.sort(key=lambda x: x['severity_score'], reverse=True)
        
        # Hero stat is the highest scoring blunder
        hero_stat = blunder_breakdown[0] if blunder_breakdown else {
            'category': 'Unknown',
            'severity_score': 0,
            'description': 'No blunders detected',
            'examples': []
        }
        
        return {
            'games_analyzed': games_analyzed,
            'total_blunders': len(sanitized_blunders),
            'hero_stat': hero_stat,
            'blunder_breakdown': blunder_breakdown,
            'games_list': games_list
        }
        
    except Exception as e:
        logger.error(f"Error transforming results: {str(e)}")
        return {
            'games_analyzed': games_analyzed,
            'total_blunders': 0,
            'hero_stat': {
                'category': 'Analysis Error',
                'score': 0,
                'description': 'There was an error processing your analysis results.',
                'examples': []
            },
            'blunder_breakdown': [],
            'games_list': games_list if 'games_list' in locals() else []
        }

def get_category_weight(category):
    """Get scoring weight for different blunder categories"""
    weights = {
        'Allowed Checkmate': 3.0,
        'Missed Checkmate': 3.0,
        'Hanging a Piece': 2.5,
        'Allowed Fork': 2.0,
        'Missed Fork': 2.0,
        'Losing Exchange': 2.0,
        'Missed Material Gain': 1.8,
        'Allowed Pin': 1.5,
        'Missed Pin': 1.5,
        'Mistake': 1.0
    }
    return weights.get(category, 1.0)

def get_general_description(category):
    """Get general educational description for blunder categories"""
    descriptions = {
        'Hanging a Piece': 'You left pieces undefended, allowing your opponent to capture them for free. Always check if your pieces are safe after making a move.',
        'Missed Fork': 'You missed opportunities to attack two or more enemy pieces simultaneously with a single piece, forcing your opponent to lose material.',
        'Allowed Fork': 'Your move allowed your opponent to attack multiple pieces at once, forcing you to lose material. Look ahead to see if your moves give your opponent tactical opportunities.',
        'Missed Material Gain': 'You missed chances to win material through captures or tactical sequences. Look for opportunities to win pieces or pawns.',
        'Losing Exchange': 'You initiated exchanges that lost you material overall. Calculate the value of pieces being traded before making exchanges.',
        'Missed Pin': 'You missed opportunities to pin enemy pieces, restricting their movement and creating tactical advantages.',
        'Allowed Pin': 'Your move allowed your opponent to pin one of your pieces, limiting your options and creating weaknesses in your position.',
        'Allowed Checkmate': 'Your move gave your opponent a forced checkmate sequence. Always check if your moves leave your king vulnerable.',
        'Missed Checkmate': 'You missed opportunities to deliver checkmate. Look for forcing moves that can lead to mate.',
        'Mistake': 'This move significantly worsened your position or missed a better alternative. Review the position to understand what went wrong.'
    }
    return descriptions.get(category, 'This type of move generally leads to a worse position or missed opportunities.')

@app.route("/api/progress/<session_id>")
def progress_stream(session_id):
    """Server-Sent Events endpoint for progress updates"""
    def generate():
        logger.info(f"Starting progress stream for session {session_id}")
        
        # Create queue for this session if it doesn't exist
        with progress_lock:
            if session_id not in progress_queues:
                progress_queues[session_id] = queue.Queue(maxsize=50)
                logger.info(f"Created new progress queue for session {session_id}")
        
        try:
            while True:
                try:
                    # Wait for progress update with timeout
                    update = progress_queues[session_id].get(timeout=30)
                    logger.info(f"Sending progress update for {session_id}: {update.get('step', 'no-step')} - {update.get('message', 'no-message')}")
                    
                    # Send the update as SSE
                    yield f"data: {json.dumps(update)}\n\n"
                    
                    # Check if this is completion
                    if update.get("step") == "complete" or update.get("step") == "error":
                        logger.info(f"Stream ending for session {session_id} with step: {update.get('step')}")
                        break
                        
                except queue.Empty:
                    # Send heartbeat
                    logger.debug(f"Sending heartbeat for session {session_id}")
                    yield f"data: {json.dumps({'heartbeat': True})}\n\n"
                except Exception as e:
                    logger.error(f"Error in progress stream for session {session_id}: {str(e)}")
                    break
        finally:
            logger.info(f"Cleaning up progress session {session_id}")
            cleanup_progress_session(session_id)
    
    return Response(generate(), mimetype='text/event-stream')

@app.route("/api/status/<session_id>")
def status_endpoint(session_id):
    """Simple status endpoint to check analysis completion"""
    try:
        # Check if session exists in progress trackers
        if session_id in progress_trackers:
            tracker = progress_trackers[session_id]
            # For now, just return that it's running
            return jsonify({
                'status': 'running',
                'session_id': session_id,
                'message': 'Analysis in progress'
            })
        else:
            # Check if there are any results stored somewhere
            # For now, just return unknown
            return jsonify({
                'status': 'unknown',
                'session_id': session_id,
                'message': 'Session not found'
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'session_id': session_id,
            'error': str(e)
        }), 500

class ProgressTracker:
    """Helper class to track and report progress during analysis with time-weighted calculations"""
    def __init__(self, session_id, games_to_analyze=1):
        self.session_id = session_id
        self.start_time = time.time()
        self.completed = False
        self.error_occurred = False
        self.results = None
        
        # Create progress queue for this session immediately
        with progress_lock:
            progress_queues[session_id] = queue.Queue(maxsize=50)
        
        # Time-weighted progress phases with realistic estimates (in seconds)
        # These are based on actual observed performance
        self.phases = {
            "starting": {"weight": 0.5, "completed": False},
            "fetching_games": {"weight": 2.0, "completed": False},  # API calls
            "engine_init": {"weight": 0.5, "completed": False},     # Quick engine setup
            "reading_pgn": {"weight": 0.2, "completed": False},     # Fast file read
            "analyzing_games": {"weight": 8.0 * games_to_analyze, "completed": False},  # Most time here
            "aggregating": {"weight": 0.3, "completed": False},     # Quick stats calc
        }
        
        # Calculate total estimated time
        self.total_estimated_time = sum(phase["weight"] for phase in self.phases.values())
        self.current_progress = 0.0
        
    def update(self, phase_name, message, mark_complete=True):
        """Update progress for a specific phase"""
        if phase_name in self.phases and not self.phases[phase_name]["completed"]:
            if mark_complete:
                self.phases[phase_name]["completed"] = True
                
            # Calculate progress based on completed phases
            completed_weight = sum(
                phase["weight"] for phase in self.phases.values() 
                if phase["completed"]
            )
            
            # Add partial progress for current phase if not marking complete
            if not mark_complete and phase_name in self.phases:
                # Estimate we're 50% through current phase if not complete
                completed_weight += self.phases[phase_name]["weight"] * 0.5
            
            # Calculate percentage and cap at 100%
            self.current_progress = min(100.0, (completed_weight / self.total_estimated_time) * 100)
        
        time_elapsed = time.time() - self.start_time
        
        send_progress_update(
            self.session_id,
            phase_name,
            message,
            self.current_progress,
            time_elapsed
        )
        
    def complete(self, results=None):
        """Mark analysis as complete with results"""
        time_elapsed = time.time() - self.start_time
        
        # Set completion state
        self.completed = True
        self.results = results
        
        logger.info(f"ProgressTracker.complete() called for session {self.session_id}")
        
        # Send completion update with results
        with progress_lock:
            logger.info(f"Acquired progress_lock for session {self.session_id}")
            if self.session_id in progress_queues:
                queue_size = progress_queues[self.session_id].qsize()
                logger.info(f"Progress queue exists for session {self.session_id}, current size: {queue_size}")
                
                update = {
                    "step": "complete",  # Fixed: was "status": "completed"
                    "status": "completed",
                    "message": f"Analysis completed in {time_elapsed:.1f}s",
                    "percentage": 100.0,
                    "results": results,
                    "timestamp": time.time()
                }
                
                logger.info(f"Created completion update for session {self.session_id}: {update.keys()}")
                
                try:
                    # Clear any old messages and send completion
                    while not progress_queues[self.session_id].empty():
                        try:
                            progress_queues[self.session_id].get_nowait()
                        except queue.Empty:
                            break
                    
                    progress_queues[self.session_id].put_nowait(update)
                    new_queue_size = progress_queues[self.session_id].qsize()
                    logger.info(f"Successfully queued completion update for session {self.session_id}, new queue size: {new_queue_size}")
                    
                    # Force immediate flush by adding multiple copies if needed
                    for i in range(3):
                        try:
                            progress_queues[self.session_id].put_nowait(update)
                        except queue.Full:
                            break
                    
                except queue.Full:
                    logger.error(f"Progress queue full for session {self.session_id} when trying to send completion")
                except Exception as e:
                    logger.error(f"Unexpected error queuing completion for session {self.session_id}: {str(e)}")
            else:
                logger.error(f"No progress queue found for session {self.session_id} during completion")
                logger.error(f"Available sessions in progress_queues: {list(progress_queues.keys())}")

    def set_error(self, error_message):
        """Mark the analysis as failed with a specific error message"""
        with progress_lock:
            if self.session_id in progress_queues:
                update = {
                    "step": "error",
                    "status": "error", 
                    "error": error_message,
                    "timestamp": time.time()
                }
                try:
                    progress_queues[self.session_id].put_nowait(update)
                except queue.Full:
                    pass

    def update_progress(self, percent, message):
        """Update progress to a specific percentage"""
        with progress_lock:
            if self.session_id in progress_queues:
                update = {
                    "percentage": percent,
                    "message": message,
                    "timestamp": time.time()
                }
                try:
                    progress_queues[self.session_id].put_nowait(update)
                except queue.Full:
                    pass

    def start_phase(self, phase_name, message):
        """Mark a phase as started"""
        self.update(phase_name, message, mark_complete=False)

if __name__ == '__main__':
    # Make sure to install Flask-Cors: pip install Flask-Cors
    app.run(debug=True, port=5000)
