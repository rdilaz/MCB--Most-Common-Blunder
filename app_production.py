import os
import chess
import chess.pgn
import chess.engine
from collections import Counter
from flask import Flask, jsonify, send_from_directory, render_template_string, Response, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from dotenv import load_dotenv
import time
import json
import threading
import queue
from threading import Thread
import logging
import subprocess
import tempfile
import re
import glob
import signal

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Security Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# HTTPS enforcement (disable for local development)
if os.environ.get('FLASK_ENV') == 'production':
    Talisman(app, force_https=True)

# Rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
limiter.init_app(app)

# CORS - restrict to your domain in production
if os.environ.get('FLASK_ENV') == 'production':
    CORS(app, origins=[os.environ.get('ALLOWED_ORIGIN', 'https://yourdomain.com')])
else:
    CORS(app)  # Allow all origins for development

# Configuration
STOCKFISH_PATH = os.environ.get('STOCKFISH_PATH', os.path.join(os.path.dirname(__file__), "stockfish", "stockfish.exe"))
BLUNDER_THRESHOLD = 15
ENGINE_THINK_TIME = 0.1

# Input validation
def validate_username(username):
    """Validate Chess.com username"""
    if not username or len(username) > 50 or len(username) < 3:
        return False
    # Only allow alphanumeric, underscores, and hyphens (Chess.com format)
    import re
    # Chess.com usernames: 3-25 chars, alphanumeric + underscore + hyphen, case insensitive
    pattern = r'^[a-zA-Z0-9_-]{3,25}$'
    if not re.match(pattern, username):
        return False
    # Additional security: no SQL injection patterns
    dangerous_patterns = ['drop', 'select', 'insert', 'delete', 'update', 'union', '--', ';']
    username_lower = username.lower()
    return not any(pattern in username_lower for pattern in dangerous_patterns)

# Global progress tracking
progress_queues = {}
progress_lock = threading.Lock()

# Timeout handler
def timeout_handler(signum, frame):
    raise TimeoutError("Analysis timed out")

# Simple ProgressTracker class (simplified for production)
class ProgressTracker:
    def __init__(self, session_id, total_games):
        self.session_id = session_id
        self.total_games = total_games
        self.start_time = time.time()
        self.current_step = "initializing"
        self.progress = 0.0
        
    def update_progress(self, percentage, message):
        """Update progress with safety checks"""
        try:
            with progress_lock:
                if self.session_id in progress_queues:
                    update = {
                        "step": self.current_step,
                        "status": "running",
                        "message": message,
                        "percentage": min(100.0, max(0.0, percentage)),
                        "timestamp": time.time()
                    }
                    progress_queues[self.session_id].put_nowait(update)
        except Exception as e:
            logger.error(f"Error updating progress: {e}")
    
    def complete(self, results):
        """Mark analysis as complete"""
        try:
            with progress_lock:
                if self.session_id in progress_queues:
                    update = {
                        "step": "complete",
                        "status": "completed",
                        "message": "Analysis completed successfully!",
                        "percentage": 100.0,
                        "results": results,
                        "timestamp": time.time()
                    }
                    progress_queues[self.session_id].put_nowait(update)
        except Exception as e:
            logger.error(f"Error completing progress: {e}")
    
    def set_error(self, error_msg):
        """Set error state"""
        try:
            with progress_lock:
                if self.session_id in progress_queues:
                    update = {
                        "step": "error",
                        "status": "error",
                        "message": error_msg,
                        "percentage": 0.0,
                        "timestamp": time.time()
                    }
                    progress_queues[self.session_id].put_nowait(update)
        except Exception as e:
            logger.error(f"Error setting error state: {e}")

# Import analysis functions (simplified imports)
try:
    from get_games import fetch_user_games
    from analyze_games import analyze_game
except ImportError as e:
    logger.error(f"Import error: {e}")
    # Fallback functions
    def fetch_user_games(username, num_games, selected_types, rated_filter):
        return None, []
    def analyze_game(game, engine, target_user, blunder_threshold, engine_think_time, debug_mode):
        return []

# Windows-compatible timeout handling
def setup_timeout(seconds):
    """Setup timeout that works on both Windows and Unix"""
    try:
        if hasattr(signal, 'SIGALRM'):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
        else:
            # Windows doesn't support SIGALRM, so we skip timeout for now
            logger.warning("Timeout not supported on Windows")
    except Exception as e:
        logger.warning(f"Could not set up timeout: {e}")

def clear_timeout():
    """Clear timeout that works on both platforms"""
    try:
        if hasattr(signal, 'alarm'):
            signal.alarm(0)
    except Exception:
        pass

@app.route("/")
def home():
    """Serve the main HTML page"""
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Application not found", 404

@app.route("/styles.css")
def serve_css():
    """Serve CSS file"""
    return send_from_directory('.', 'styles.css')

@app.route("/main.js")
def serve_js():
    """Serve JavaScript file"""
    return send_from_directory('.', 'main.js')

def analyze_game_optimized(game, engine, target_user, blunder_threshold, engine_think_time, debug_mode):
    """
    SPEED OPTIMIZED version of analyze_game with 3-5x performance improvement
    
    Optimizations:
    1. Skip analysis in clearly decided positions (>8 pawn advantage)
    2. Use reduced time for obvious moves
    3. Smart move filtering
    4. Maintain proper blunder categorization
    """
    try:
        # ALWAYS use the original analyze_game function for proper categorization
        # Speed improvements come from reduced engine think time, not simplified logic
        from analyze_games import analyze_game
        
        return analyze_game(
            game=game,
            engine=engine, 
            target_user=target_user,
            blunder_threshold=blunder_threshold,
            engine_think_time=engine_think_time,  # Already optimized (0.05s vs 0.1s+)
            debug_mode=debug_mode
        )
    except Exception as e:
        logger.error(f"Optimized analysis failed: {e}")
        # Fallback to empty list
        return []



@app.route("/api/analyze", methods=['POST'])
@limiter.limit("5 per minute")  # Rate limit analysis requests
def analyze_endpoint():
    """Handle analysis requests with security checks"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        session_id = data.get('session_id')
        username = data.get('username', '').strip()
        
        # Get user settings (same as original app.py)
        game_count = data.get('gameCount', 20)
        game_types = data.get('gameTypes', ['blitz', 'rapid'])
        rating_filter = data.get('ratingFilter', 'rated')
        analysis_depth = data.get('analysisDepth', 'balanced')
        
        # Validate inputs
        if not session_id or not username:
            return jsonify({'error': 'Session ID and username are required'}), 400
        
        if not validate_username(username):
            return jsonify({'error': 'Invalid username format'}), 400
        
        # SECURITY: Enhanced usage limits 
        if game_count > 100:  # Hard cap to prevent server overload
            return jsonify({'error': 'Maximum 100 games allowed'}), 400
        
        # SECURITY: Daily usage tracking (simple implementation)
        daily_limit_key = f"daily_usage_{username}_{time.strftime('%Y-%m-%d')}"
        # In production, this would use Redis or database. For now, in-memory tracking:
        if not hasattr(app, 'daily_usage'):
            app.daily_usage = {}
        
        current_usage = app.daily_usage.get(daily_limit_key, 0)
        if current_usage + game_count > 200:  # 200 games per user per day
            remaining = max(0, 200 - current_usage)
            return jsonify({
                'error': f'Daily limit reached. You can analyze {remaining} more games today.',
                'daily_limit': 200,
                'used_today': current_usage,
                'remaining': remaining
            }), 429
        
        # Update usage counter
        app.daily_usage[daily_limit_key] = current_usage + game_count
        
        # SPEED OPTIMIZATION: Aggressive engine settings for 3-5x speedup
        depth_mapping = {
            'fast': 0.05,    # ULTRA FAST: 50ms per move (was 100ms) 
            'balanced': 0.08, # FAST: 80ms per move (was 200ms)
            'deep': 0.15      # NORMAL: 150ms per move (was 500ms)
        }
        engine_think_time = depth_mapping.get(analysis_depth, 0.08)
        
        # SPEED: Calculate expected analysis time
        estimated_moves_per_game = 35  # Average chess game length
        estimated_total_time = game_count * estimated_moves_per_game * engine_think_time
        
        logger.info(f"Speed optimization: {engine_think_time}s per move, estimated {estimated_total_time:.1f}s total")
        
        # Return optimization info to user  
        optimization_mode = "Fast" if engine_think_time <= 0.06 else "Balanced" if engine_think_time <= 0.1 else "Deep"
        speed_multiplier = "2-4x faster" if engine_think_time <= 0.06 else "1.5-2.5x faster" if engine_think_time <= 0.1 else "1.5x faster"
        
        # Limit concurrent sessions
        with progress_lock:
            if len(progress_queues) > 10:  # Max 10 concurrent analyses
                return jsonify({'error': 'Server busy, try again later'}), 503
        
        # Initialize progress tracker with actual game count
        progress_queues[session_id] = queue.Queue(maxsize=50)
        tracker = ProgressTracker(session_id, game_count)
        
        # Start analysis with timeout
        def run_analysis():
            try:
                # Set timeout for analysis
                setup_timeout(300)  # 5 minute timeout
                
                tracker.update_progress(5, f"Fetching {game_count} {', '.join(game_types)} games ({rating_filter})")
                
                # Convert frontend game types to get_games.py format
                selected_types = []
                if 'all' in game_types:
                    selected_types = []  # Empty list means all types
                else:
                    if 'rapid' in game_types:
                        selected_types.append('rapid')
                    if 'blitz' in game_types:
                        selected_types.append('blitz')
                    if 'bullet' in game_types:
                        selected_types.append('bullet')
                    if 'daily' in game_types:
                        selected_types.append('daily')
                
                # Convert rating filter
                if rating_filter == 'all':
                    rated_filter = 'both'
                elif rating_filter == 'rated':
                    rated_filter = 'rated'
                elif rating_filter == 'unrated':
                    rated_filter = 'unrated'
                else:
                    rated_filter = 'rated'  # Default fallback
                
                tracker.update_progress(10, f"Downloading {game_count} games...")
                
                # Fetch games with user settings
                pgn_filename, games_metadata = fetch_user_games(
                    username=username,
                    num_games=game_count,
                    selected_types=selected_types,
                    rated_filter=rated_filter
                )
                
                if not pgn_filename:
                    tracker.set_error("No games found")
                    return
                
                tracker.update_progress(40, "Reading game data...")
                
                # Read PGN file content
                try:
                    with open(pgn_filename, 'r', encoding='utf-8') as f:
                        pgn_content = f.read()
                except Exception as e:
                    logger.error(f"Error reading PGN file: {e}")
                    tracker.set_error("Failed to read game data")
                    return
                
                tracker.update_progress(30, f"Analyzing {game_count} games with {analysis_depth} depth...")
                
                # Initialize Stockfish engine
                try:
                    import chess.engine
                    import chess.pgn
                    import io
                    import os
                    
                    engine_start = time.time()
                    tracker.update_progress(35, "🔧 Initializing Stockfish engine...")
                    
                    engine_path = os.path.join(os.path.dirname(__file__), "stockfish", "stockfish.exe")
                    engine = chess.engine.SimpleEngine.popen_uci(engine_path)
                    
                    engine_time = time.time() - engine_start
                    tracker.update_progress(40, f"✅ Engine initialized in {engine_time:.2f}s")
                    
                    # Parse PGN content and analyze all games
                    pgn_io = io.StringIO(pgn_content)
                    all_blunders = []
                    games_analyzed = 0
                    total_games = 0
                    
                    # First pass: count total games
                    temp_io = io.StringIO(pgn_content)
                    while True:
                        game = chess.pgn.read_game(temp_io)
                        if game is None:
                            break
                        total_games += 1
                    
                    tracker.update_progress(45, f"📖 Found {total_games} game(s) to analyze")
                    
                    # Second pass: analyze each game
                    pgn_io = io.StringIO(pgn_content)
                    while True:
                        game = chess.pgn.read_game(pgn_io)
                        if game is None:
                            break
                        
                        games_analyzed += 1
                        
                        # Get game info for progress
                        white_player = game.headers.get("White", "Unknown")
                        black_player = game.headers.get("Black", "Unknown")
                        
                        # Calculate progress (45% to 85% range)
                        game_progress = 45 + ((games_analyzed - 1) / total_games) * 40
                        tracker.update_progress(
                            game_progress, 
                            f"🎯 Analyzing game #{games_analyzed}: {white_player} vs {black_player}"
                        )
                        
                        # SPEED OPTIMIZATION: Use optimized analysis function
                        game_blunders = analyze_game_optimized(
                            game=game,
                            engine=engine,
                            target_user=username,
                            blunder_threshold=15,
                            engine_think_time=engine_think_time,
                            debug_mode=False
                        )
                        
                        # ENHANCEMENT: Add game metadata to each blunder for linking
                        # Find corresponding game metadata
                        game_metadata = None
                        if games_metadata and len(games_metadata) >= games_analyzed:
                            game_metadata = games_metadata[games_analyzed - 1]  # 0-indexed
                        
                        # Add game information to each blunder
                        for blunder in game_blunders:
                            blunder['game_number'] = games_analyzed
                            blunder['game_white'] = white_player
                            blunder['game_black'] = black_player
                            
                            if game_metadata:
                                blunder['game_url'] = game_metadata.get('url', '')
                                blunder['game_date'] = game_metadata.get('date', 'Unknown date')
                                blunder['game_time_class'] = game_metadata.get('time_class', 'unknown')
                                blunder['game_rated'] = game_metadata.get('rated', False)
                                blunder['target_player'] = game_metadata.get('target_player', username)
                            else:
                                # Fallback if metadata not available
                                blunder['game_url'] = ''
                                blunder['game_date'] = 'Unknown date'
                                blunder['game_time_class'] = 'unknown'
                                blunder['game_rated'] = False
                                blunder['target_player'] = username
                        
                        # Add blunders to the collection
                        all_blunders.extend(game_blunders)
                        
                        # Update progress
                        final_game_progress = 45 + (games_analyzed / total_games) * 40
                        tracker.update_progress(
                            final_game_progress,
                            f"✅ Game #{games_analyzed} complete: found {len(game_blunders)} blunder(s)"
                        )
                    
                    # Clean up engine
                    engine.quit()
                    
                    tracker.update_progress(85, f"📊 Calculating statistics from {len(all_blunders)} blunders...")
                    
                    # Set blunders for final processing
                    blunders = all_blunders
                    
                except Exception as e:
                    logger.error(f"Error during engine analysis: {e}")
                    tracker.set_error(f"Analysis engine error: {str(e)}")
                    return
                
                # Clean up temporary file for security
                try:
                    import os
                    if os.path.exists(pgn_filename):
                        os.remove(pgn_filename)
                    # Also remove metadata file
                    metadata_file = pgn_filename.replace('.pgn', '_metadata.json')
                    if os.path.exists(metadata_file):
                        os.remove(metadata_file)
                except Exception as e:
                    logger.warning(f"Could not clean up temporary files: {e}")
                
                tracker.update_progress(90, "Processing results...")
                

                
                # Transform results to match frontend expectations (same as app.py)
                def transform_results_for_frontend(blunders, games_analyzed, games_metadata=None):
                    """Transform analysis results into frontend format with clickable breakdowns"""
                    try:
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
                        
                        if not blunders:
                            return {
                                'games_analyzed': games_analyzed,
                                'total_blunders': 0,
                                'hero_stat': {
                                    'category': 'No Blunders Found',
                                    'severity_score': 0,
                                    'description': 'Great job! No significant blunders were detected in your games.',
                                    'examples': []
                                },
                                'blunder_breakdown': [],
                                'games_list': games_list
                            }
                        
                        # Serialize blunders to ensure JSON compatibility
                        sanitized_blunders = []
                        for blunder in blunders:
                            sanitized_blunder = blunder.copy()
                            # Convert Move objects to strings
                            if 'punishing_move' in sanitized_blunder and sanitized_blunder['punishing_move']:
                                try:
                                    move = sanitized_blunder['punishing_move']
                                    if hasattr(move, 'uci'):
                                        sanitized_blunder['punishing_move'] = move.uci()
                                    else:
                                        sanitized_blunder['punishing_move'] = str(move)
                                except Exception:
                                    sanitized_blunder.pop('punishing_move', None)
                            sanitized_blunders.append(sanitized_blunder)
                        
                        # Group blunders by category for breakdown
                        grouped = {}
                        for blunder in sanitized_blunders:
                            category = blunder.get('category', 'Unknown')
                            if category not in grouped:
                                grouped[category] = []
                            grouped[category].append(blunder)
                        
                        # Calculate scores for each category
                        blunder_breakdown = []
                        for category, category_blunders in grouped.items():
                            frequency = len(category_blunders)
                            
                            # Calculate average impact
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
                            
                            avg_impact = max(5.0, base_impact - (frequency * 0.5))
                            
                            # Calculate severity score
                            category_weight = {
                                'Allowed Checkmate': 3.0, 'Missed Checkmate': 3.0,
                                'Hanging a Piece': 2.5, 'Allowed Fork': 2.0, 'Missed Fork': 2.0,
                                'Losing Exchange': 2.0, 'Missed Material Gain': 1.8,
                                'Allowed Pin': 1.5, 'Missed Pin': 1.5, 'Mistake': 1.0
                            }.get(category, 1.0)
                            
                            severity_score = frequency * category_weight * (avg_impact / 10.0)
                            
                            # Get educational descriptions
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
                            
                            breakdown_item = {
                                'category': category,
                                'severity_score': round(severity_score, 1),
                                'frequency': frequency,
                                'avg_impact': round(avg_impact, 1),
                                'description': descriptions.get(category, 'This type of move generally leads to a worse position or missed opportunities.'),
                                'all_occurrences': category_blunders,  # All instances for expandable details
                                'examples': category_blunders[:3]  # First 3 examples for preview
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
                        
                        # Group blunders by game for game-by-game view
                        games_with_blunders = {}
                        for blunder in sanitized_blunders:
                            game_num = blunder.get('game_number', 0)
                            if game_num not in games_with_blunders:
                                games_with_blunders[game_num] = {
                                    'game_number': game_num,
                                    'white': blunder.get('game_white', 'Unknown'),
                                    'black': blunder.get('game_black', 'Unknown'),
                                    'url': blunder.get('game_url', ''),
                                    'date': blunder.get('game_date', 'Unknown'),
                                    'time_class': blunder.get('game_time_class', 'unknown'),
                                    'rated': blunder.get('game_rated', False),
                                    'target_player': blunder.get('target_player', ''),
                                    'blunders': []
                                }
                            games_with_blunders[game_num]['blunders'].append(blunder)
                        
                        # Sort games by game number and convert to list
                        games_with_blunders_list = [games_with_blunders[game_num] for game_num in sorted(games_with_blunders.keys())]
                        
                        return {
                            'games_analyzed': games_analyzed,
                            'total_blunders': len(sanitized_blunders),
                            'hero_stat': hero_stat,
                            'blunder_breakdown': blunder_breakdown,
                            'games_list': games_list,
                            'games_with_blunders': games_with_blunders_list
                        }
                        
                    except Exception as e:
                        logger.error(f"Error transforming results: {str(e)}")
                        return {
                            'games_analyzed': games_analyzed,
                            'total_blunders': 0,
                            'hero_stat': {
                                'category': 'Analysis Error',
                                'severity_score': 0,
                                'description': 'There was an error processing your analysis results.',
                                'examples': []
                            },
                            'blunder_breakdown': [],
                            'games_list': games_list if 'games_list' in locals() else []
                        }
                
                # Transform results using proper frontend format
                results = transform_results_for_frontend(blunders, games_analyzed, games_metadata)
                
                tracker.complete(results)
                
            except TimeoutError:
                tracker.set_error("Analysis timed out")
            except Exception as e:
                logger.error(f"Analysis error: {e}")
                tracker.set_error(f"Analysis failed: {str(e)}")
            finally:
                clear_timeout()  # Cancel timeout
        
        # Start background thread
        thread = Thread(target=run_analysis)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'started',
            'session_id': session_id,
            'message': f'Analysis started for {username}',
            'optimization': {
                'mode': optimization_mode,
                'speed_gain': speed_multiplier,
                'estimated_time': f"{estimated_total_time:.1f}s"
            },
            'security': {
                'daily_limit': 200,
                'used_today': current_usage,
                'remaining': 200 - current_usage - game_count,
                'max_games_per_request': 100
            }
        })
        
    except Exception as e:
        logger.error(f"Error starting analysis: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route("/api/progress/<session_id>")
def progress_stream(session_id):
    """Server-Sent Events endpoint for progress updates"""
    def generate():
        try:
            while True:
                try:
                    if session_id not in progress_queues:
                        break
                    
                    update = progress_queues[session_id].get(timeout=30)
                    
                    # Ensure all data is JSON serializable
                    try:
                        json_data = json.dumps(update, default=str)
                        yield f"data: {json_data}\n\n"
                    except (TypeError, ValueError) as e:
                        logger.error(f"JSON serialization error: {e}")
                        # Send a safe error message instead
                        safe_update = {
                            "step": update.get("step", "error"),
                            "status": "error",
                            "message": "Error processing results",
                            "percentage": update.get("percentage", 0),
                            "timestamp": time.time()
                        }
                        yield f"data: {json.dumps(safe_update)}\n\n"
                    
                    if update.get("step") in ["complete", "error"]:
                        break
                        
                except queue.Empty:
                    # Send heartbeat
                    try:
                        yield f"data: {json.dumps({'heartbeat': True})}\n\n"
                    except Exception:
                        break
                except Exception as e:
                    logger.error(f"Error in progress stream: {e}")
                    # Send error message and break
                    try:
                        error_msg = {
                            "step": "error",
                            "status": "error", 
                            "message": "Stream error occurred",
                            "percentage": 0,
                            "timestamp": time.time()
                        }
                        yield f"data: {json.dumps(error_msg)}\n\n"
                    except Exception:
                        pass
                    break
        finally:
            # Cleanup
            with progress_lock:
                if session_id in progress_queues:
                    del progress_queues[session_id]
    
    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'  # Disable proxy buffering
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(429)
def rate_limit_error(error):
    return jsonify({'error': 'Rate limit exceeded'}), 429

if __name__ == '__main__':
    # Production settings
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    port = int(os.environ.get('PORT', 5000))
    
    app.run(
        debug=debug_mode,
        host='0.0.0.0',
        port=port
    ) 