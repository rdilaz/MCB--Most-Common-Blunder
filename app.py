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

@app.route("/api/analyze/<string:username>")
def analyze_player(username):
    """
    Main API endpoint to fetch games, analyze them, and return blunders.
    """
    # Get session ID from query parameter or generate one
    session_id = request.args.get('session_id')
    if not session_id:
        session_id = f"{username}_{int(time.time())}"
    
    total_start = time.time()
    print(f"\n🚀 Starting analysis for player: {username} (Session: {session_id})")
    print(f"⚙️  Configuration: {GAMES_TO_FETCH} games, {ENGINE_THINK_TIME}s think time, {BLUNDER_THRESHOLD}% blunder threshold")

    # Create progress tracker
    progress_tracker = ProgressTracker(session_id, games_to_analyze=GAMES_TO_FETCH)
    progress_tracker.update("starting", f"🚀 Starting analysis for {username}...", mark_complete=True)

    # 1. Fetch the user's games
    print(f"\n🌐 Step 1: Fetching games from Chess.com API...")
    fetch_start = time.time()
    
    progress_tracker.update("fetching_games", f"🌐 Fetching games from Chess.com API...", mark_complete=False)
    
    pgn_filename = fetch_user_games(
        username=username, 
        num_games=GAMES_TO_FETCH, 
        selected_types=[], # Empty list = "all" types
        rated_filter="rated"
    )
    
    fetch_time = time.time() - fetch_start
    print(f"✅ Chess.com API fetch completed in {fetch_time:.2f} seconds")

    if pgn_filename is None:
        print(f"❌ Failed to fetch games from Chess.com API")
        progress_tracker.update("error", "❌ Failed to fetch games from Chess.com API")
        return jsonify({"error": "Could not fetch games from Chess.com API."}), 500

    print(f"📄 PGN file created: {pgn_filename}")
    
    # Mark fetching complete
    progress_tracker.update("fetching_games", f"✅ Fetched games in {fetch_time:.2f}s", mark_complete=True)

    # 2. Analyze all games using our wrapper function
    print(f"\n🔬 Step 2: Starting game analysis...")
    analysis_start = time.time()
    
    result = analyze_multiple_games(
        pgn_file_path=pgn_filename,
        username=username,
        stockfish_path=STOCKFISH_PATH,
        blunder_threshold=BLUNDER_THRESHOLD,
        engine_think_time=ENGINE_THINK_TIME,
        progress_tracker=progress_tracker
    )
    
    analysis_time = time.time() - analysis_start
    print(f"✅ Game analysis completed in {analysis_time:.2f} seconds")
    
    # 3. Handle errors from the analysis
    if "error" in result:
        print(f"❌ Analysis error: {result['error']}")
        return jsonify(result), 500

    total_time = time.time() - total_start
    print(f"\n🎯 FINAL RESULTS for {username}:")
    print(f"   📊 {result['summary']['total_blunders']} blunders across {result['games_analyzed']} games")
    print(f"   ⏱️  Total request time: {total_time:.2f} seconds")
    print(f"   📈 Breakdown: API fetch ({fetch_time:.2f}s) + Analysis ({analysis_time:.2f}s)")
    
    # 4. Return the successful result as JSON with session ID
    result["session_id"] = session_id
    return jsonify(result)

@app.route("/api/progress/<session_id>")
def progress_stream(session_id):
    """Server-Sent Events endpoint for progress updates"""
    def generate():
        # Create queue for this session
        with progress_lock:
            progress_queues[session_id] = queue.Queue(maxsize=50)
        
        try:
            while True:
                try:
                    # Wait for progress update with timeout
                    update = progress_queues[session_id].get(timeout=30)
                    
                    # Send the update as SSE
                    yield f"data: {json.dumps(update)}\n\n"
                    
                    # Check if this is completion
                    if update.get("step") == "complete":
                        break
                        
                except queue.Empty:
                    # Send heartbeat
                    yield f"data: {json.dumps({'heartbeat': True})}\n\n"
                except:
                    break
        finally:
            cleanup_progress_session(session_id)
    
    return Response(generate(), mimetype='text/event-stream')

class ProgressTracker:
    """Helper class to track and report progress during analysis with time-weighted calculations"""
    def __init__(self, session_id, games_to_analyze=1):
        self.session_id = session_id
        self.start_time = time.time()
        
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
        
    def complete(self, final_message="Analysis complete!"):
        """Mark analysis as complete with 100% progress"""
        time_elapsed = time.time() - self.start_time
        send_progress_update(
            self.session_id,
            "complete",
            final_message,
            100.0,  # Always 100% on completion
            time_elapsed
        )

if __name__ == '__main__':
    # Make sure to install Flask-Cors: pip install Flask-Cors
    app.run(debug=True, port=5000)
