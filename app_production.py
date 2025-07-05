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
        
        # Security limits (more generous than before)
        if game_count > 50:  # Prevent excessive resource usage
            return jsonify({'error': 'Maximum 50 games allowed'}), 400
        
        # Map analysis depth to engine think time (same as original)
        depth_mapping = {
            'fast': 0.1,
            'balanced': 0.2,
            'deep': 0.5
        }
        engine_think_time = depth_mapping.get(analysis_depth, 0.2)
        
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
                        
                        # Analyze this game
                        game_blunders = analyze_game(
                            game=game,
                            engine=engine,
                            target_user=username,
                            blunder_threshold=15,  # Match terminal version
                            engine_think_time=engine_think_time,  # Use user's setting
                            debug_mode=False
                        )
                        
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
                
                # Convert chess Move objects to strings for JSON serialization
                def serialize_blunder(blunder):
                    """Convert blunder data to JSON-serializable format"""
                    if not blunder:
                        return blunder
                    
                    serialized = blunder.copy()
                    
                    # Convert Move objects to strings
                    if 'punishing_move' in serialized and serialized['punishing_move']:
                        try:
                            # If it's a Move object, convert to string
                            move = serialized['punishing_move']
                            if hasattr(move, 'uci'):  # Check if it's a Move object
                                serialized['punishing_move'] = move.uci()
                            else:
                                serialized['punishing_move'] = str(move)
                        except Exception:
                            # If conversion fails, remove the field
                            serialized.pop('punishing_move', None)
                    
                    return serialized
                
                # Process and clean blunder data
                clean_blunders = []
                for blunder in blunders[:10]:  # Limit to 10 results
                    try:
                        clean_blunder = serialize_blunder(blunder)
                        
                        # Add general description for frontend
                        category = clean_blunder.get('category', 'Unknown')
                        if 'general_description' not in clean_blunder:
                            descriptions = {
                                'Missed Fork': 'You missed an opportunity to attack multiple opponent pieces simultaneously.',
                                'Allowed Fork': 'Your move allowed the opponent to attack multiple of your pieces.',
                                'Missed Pin': 'You missed a chance to pin an opponent piece to a more valuable target.',
                                'Allowed Pin': 'Your move allowed the opponent to pin one of your pieces.',
                                'Hanging a Piece': 'You left a piece undefended where it could be captured.',
                                'Losing Exchange': 'You initiated a trade that lost material value.',
                                'Missed Material Gain': 'You missed an opportunity to win material.',
                                'Missed Checkmate': 'You missed a forced checkmate sequence.',
                                'Allowed Checkmate': 'Your move allowed the opponent to force checkmate.',
                                'Mistake': 'This move significantly worsened your position.'
                            }
                            clean_blunder['general_description'] = descriptions.get(category, 'A significant tactical or positional error.')
                        
                        clean_blunders.append(clean_blunder)
                    except Exception as e:
                        logger.warning(f"Error serializing blunder: {e}")
                        # Add a simplified version
                        clean_blunders.append({
                            'category': blunder.get('category', 'Unknown'),
                            'move_number': blunder.get('move_number', 0),
                            'description': blunder.get('description', 'Error processing blunder'),
                            'general_description': 'A tactical or positional error occurred.'
                        })
                
                # Calculate most common blunder (hero stat)
                from collections import Counter
                if blunders:
                    blunder_categories = [blunder.get('category', 'Unknown') for blunder in blunders]
                    category_counts = Counter(blunder_categories)
                    most_common = category_counts.most_common(1)[0]
                    most_common_category = most_common[0]
                    most_common_count = most_common[1]
                    most_common_percentage = round((most_common_count / len(blunders)) * 100, 1)
                    
                    # Get the general description for the most common category
                    descriptions = {
                        'Missed Fork': 'You missed an opportunity to attack multiple opponent pieces simultaneously.',
                        'Allowed Fork': 'Your move allowed the opponent to attack multiple of your pieces.',
                        'Missed Pin': 'You missed a chance to pin an opponent piece to a more valuable target.',
                        'Allowed Pin': 'Your move allowed the opponent to pin one of your pieces.',
                        'Hanging a Piece': 'You left a piece undefended where it could be captured.',
                        'Losing Exchange': 'You initiated a trade that lost material value.',
                        'Missed Material Gain': 'You missed an opportunity to win material.',
                        'Missed Checkmate': 'You missed a forced checkmate sequence.',
                        'Allowed Checkmate': 'Your move allowed the opponent to force checkmate.',
                        'Mistake': 'This move significantly worsened your position.'
                    }
                    
                    hero_stat = {
                        "category": most_common_category,
                        "count": most_common_count,
                        "percentage": most_common_percentage,
                        "general_description": descriptions.get(most_common_category, 'A significant tactical or positional error.')
                    }
                else:
                    hero_stat = None
                
                # Complete results with hero stat
                results = {
                    'games_analyzed': games_analyzed,
                    'total_blunders': len(blunders),
                    'blunders': clean_blunders,
                    'games_list': games_metadata[:games_analyzed] if games_metadata else [],
                    'summary': {
                        'total_blunders': len(blunders),
                        'most_common_blunder': hero_stat,
                        'category_breakdown': dict(Counter([b.get('category', 'Unknown') for b in blunders])) if blunders else {}
                    }
                }
                
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
            'message': f'Analysis started for {username}'
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