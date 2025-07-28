"""
MCB Routes Module
Flask route handlers for the MCB web application.
Production-ready with security, rate limiting, and optimizations from app_production.py.
"""
import json
import logging
import time
import signal
from threading import Thread
from flask import Flask, jsonify, send_from_directory, Response, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

from config import (
    ANALYSIS_DEPTH_MAPPING, DEBUG_MODE, PORT, SECURITY_CONFIG, RATE_LIMITS,
    CORS_CONFIG, HTTPS_ENFORCEMENT, ANALYSIS_TIMEOUT, MAX_CONCURRENT_SESSIONS,
    MAX_GAMES_ALLOWED, DAILY_GAME_LIMIT
)
from utils import validate_username, create_error_response, log_error, generate_session_id
from progress_tracking import (
    create_progress_tracker, get_progress_generator, get_session_status, cleanup_tracker,
    progress_queues, progress_lock
)
from analysis_service import create_analysis_service

# Set up logging
logger = logging.getLogger(__name__)

# Create service instances
analysis_service = create_analysis_service()

# Redis-based rate limiting (production-ready)
from security.rate_limiter import RateLimiter
rate_limiter = RateLimiter()

# Timeout handlers for production
def timeout_handler(signum, frame):
    raise TimeoutError("Analysis timed out")

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

def register_routes(app: Flask):
    """
    Register all routes with the Flask application.
    Includes production security and optimization features.
    
    Args:
        app (Flask): Flask application instance
    """
    
    @app.route("/")
    def home():
        """Serve the main HTML page."""
        try:
            with open('index.html', 'r', encoding='utf-8') as f:
                html_content = f.read()
            return html_content
        except FileNotFoundError:
            return "Application not found", 404
    
    @app.route("/styles.css")
    def serve_css():
        """Serve the CSS file."""
        return send_from_directory('.', 'styles.css')
    
    @app.route("/main.js")
    def serve_js():
        """Serve the JavaScript file."""
        return send_from_directory('.', 'main.js')
    
    @app.route("/js/<filename>")
    def serve_js_modules(filename):
        """Serve JavaScript module files from js/ directory."""
        return send_from_directory('js', filename)
    
    @app.route("/api/analyze", methods=['POST'])
    @app.limiter.limit(RATE_LIMITS['analysis'])  # Rate limit analysis requests
    def analyze_endpoint():
        """Handle analysis requests with production security and optimizations."""
        try:
            data = request.json
            if not data:
                return jsonify(create_error_response('No data provided'))
            
            session_id = data.get('session_id')
            username = data.get('username', '').strip()
            
            # Get user settings
            game_count = data.get('gameCount', 20)
            game_types = data.get('gameTypes', ['blitz', 'rapid'])
            rating_filter = data.get('ratingFilter', 'rated')
            analysis_depth = data.get('analysisDepth', 'balanced')
            
            # Validate inputs
            if not session_id or not username:
                return jsonify(create_error_response('Session ID and username are required')), 400
            
            username_valid, username_error = validate_username(username)
            if not username_valid:
                return jsonify(create_error_response(username_error)), 400
            
            # SECURITY: Enhanced usage limits 
            if game_count > MAX_GAMES_ALLOWED:
                return jsonify(create_error_response(f'Maximum {MAX_GAMES_ALLOWED} games allowed'))
            
            # SECURITY: Redis-based rate limiting
            allowed, usage_info = rate_limiter.check_daily_limit(username, game_count, DAILY_GAME_LIMIT)
            if not allowed:
                return jsonify({
                    'error': f'Daily limit reached. You can analyze {usage_info["remaining"]} more games today.',
                    **usage_info
                }), 429
            
            # Check per-minute rate limit
            if not rate_limiter.check_minute_limit(username):
                return jsonify({'error': 'Too many requests per minute. Please wait before trying again.'}), 429
            
            # Map analysis depth to engine think time (production-optimized values)
            engine_think_time = ANALYSIS_DEPTH_MAPPING.get(analysis_depth, 0.08)
            
            # Calculate optimization info for user feedback
            optimization_info = analysis_service.calculate_optimization_info(engine_think_time, game_count)
            
            # Limit concurrent sessions
            with progress_lock:
                if len(progress_queues) > MAX_CONCURRENT_SESSIONS:
                    return jsonify(create_error_response('Server busy, try again later', 503))
            
            # Initialize progress tracker
            tracker = create_progress_tracker(session_id, game_count)
            
            # Start analysis in background thread
            def run_analysis():
                try:
                    # Set timeout for analysis
                    setup_timeout(ANALYSIS_TIMEOUT)
                    
                    # Phase 1: Game fetching with settings
                    tracker.start_phase("fetching_games", f"Fetching {game_count} {', '.join(game_types)} games ({rating_filter})")
                    
                    # Create filter object for game fetching
                    game_filters = {
                        'game_count': game_count,
                        'game_types': game_types,
                        'rating_filter': rating_filter
                    }
                    
                    # Get filtered games and metadata
                    pgn_content, games_metadata = analysis_service.fetch_games_with_filters(username, game_filters, tracker)
                    
                    if not pgn_content:
                        tracker.set_error("No games found matching the specified criteria")
                        return
                    
                    # Phase 2: Engine initialization
                    tracker.start_phase("engine_init", "Initializing Stockfish engine")
                    
                    # Phase 3: Game analysis with production optimizations
                    tracker.start_phase("analyzing_games", f"Analyzing games with {analysis_depth} depth")
                    
                    # Run analysis with optimized settings
                    results = analysis_service.analyze_games_with_settings(
                        pgn_content, 
                        username, 
                        engine_think_time,
                        tracker,
                        games_metadata
                    )
                    
                    if results:
                        # Phase 4: Pattern aggregation and scoring
                        tracker.start_phase("aggregating", "Calculating blunder patterns and scores")
                        
                        try:
                            # Update progress to show transformation is starting
                            tracker.update_progress(96, "🔄 Processing analysis results...")
                            
                            # Use actual games analyzed count from results
                            actual_games_analyzed = results.get('games_analyzed', game_count)
                            
                            # Log detailed info for debugging
                            logger.info(f"Transforming results for session {session_id}: {len(results.get('blunders', []))} blunders from {actual_games_analyzed} games")
                            logger.info(f"Games metadata length: {len(games_metadata) if games_metadata else 0}")
                            
                            # Transform results using production logic
                            final_results = analysis_service.transform_results_for_frontend(
                                results.get('blunders', []), 
                                actual_games_analyzed, 
                                games_metadata
                            )
                            logger.info(f"Successfully transformed results for session {session_id}")
                            
                            # Update progress to show completion
                            tracker.update_progress(99, "✨ Finalizing results...")
                            logger.info(f"About to call tracker.complete() for session {session_id}")
                            
                            # Complete with results
                            tracker.complete(final_results)
                            logger.info(f"Analysis completed for session {session_id}")
                            
                        except Exception as transform_error:
                            logger.error(f"Transform function failed for session {session_id}: {str(transform_error)}")
                            logger.error(f"Transform error traceback:", exc_info=True)
                            tracker.set_error(f"Failed to process analysis results: {str(transform_error)}")
                    else:
                        tracker.set_error("Analysis failed to produce results")
                        
                except TimeoutError:
                    tracker.set_error("Analysis timed out")
                except Exception as e:
                    logger.error(f"Analysis error for session {session_id}: {str(e)}")
                    tracker.set_error(f"Analysis failed: {str(e)}")
                finally:
                    clear_timeout()  # Cancel timeout
                    cleanup_tracker(session_id)
            
            # Start background thread
            thread = Thread(target=run_analysis)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'status': 'started',
                'session_id': session_id,
                'message': f'Analysis started for {username}',
                'optimization': optimization_info,
                'security': {
                    **usage_info,
                    'max_games_per_request': MAX_GAMES_ALLOWED
                }
            })
            
        except Exception as e:
            log_error(f"Error starting analysis: {str(e)}")
            return jsonify(create_error_response('Internal server error', 500))
    
    @app.route("/api/analyze-pgn", methods=['POST'])
    @app.limiter.limit("10 per minute")  # Rate limit PGN analysis
    def analyze_pgn_endpoint():
        """Handle direct PGN analysis for developer testing."""
        try:
            # Check if PGN file was uploaded
            if 'pgn_file' not in request.files:
                return create_error_response("No PGN file provided", 400)
            
            pgn_file = request.files['pgn_file']
            if pgn_file.filename == '':
                return create_error_response("No PGN file selected", 400)
            
            # Get parameters
            username = request.form.get('username', 'developer')
            blunder_threshold = float(request.form.get('blunder_threshold', 10.0))
            engine_think_time = float(request.form.get('engine_think_time', 0.15))
            debug_mode = request.form.get('debug', 'false').lower() == 'true'
            
            # Validate parameters
            if not validate_username(username):
                return create_error_response("Invalid username", 400)
            
            if blunder_threshold < 1 or blunder_threshold > 50:
                return create_error_response("Invalid blunder threshold", 400)
            
            if engine_think_time < 0.01 or engine_think_time > 1.0:
                return create_error_response("Invalid engine think time", 400)
            
            # Save PGN to temporary file
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.pgn', delete=False) as temp_file:
                pgn_content = pgn_file.read().decode('utf-8')
                temp_file.write(pgn_content)
                temp_file_path = temp_file.name
            
            try:
                # Run analysis using the existing analyze_games.py script
                import subprocess
                import sys
                
                # Build command
                cmd = [
                    sys.executable, 'analyze_games.py',
                    '--pgn', temp_file_path,
                    '--username', username,
                    '--blunder_threshold', str(blunder_threshold),
                    '--engine_think_time', str(engine_think_time)
                ]
                
                if debug_mode:
                    cmd.append('--debug')
                
                # Run analysis
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                
                if result.returncode != 0:
                    logger.error(f"PGN analysis failed: {result.stderr}")
                    return create_error_response(f"Analysis failed: {result.stderr}", 500)
                
                # Parse the output to extract blunders
                # The analyze_games.py script outputs blunders to stdout
                output_lines = result.stdout.strip().split('\n')
                blunders = []
                
                logger.info(f"Parsing {len(output_lines)} lines of output")
                
                # Look for the "Found X blunders:" line and parse from there
                for i, line in enumerate(output_lines):
                    if 'Found' in line and 'blunders:' in line:
                        logger.info(f"Found blunders line at index {i}: {line}")
                        # Parse blunders from the lines after this
                        for j in range(i + 1, len(output_lines)):
                            blunder_line = output_lines[j].strip()
                            
                            # Skip empty lines
                            if not blunder_line:
                                continue
                                
                            # Stop when we hit the summary section
                            if blunder_line.startswith('===') or blunder_line.startswith('[OK]') or blunder_line.startswith('Total'):
                                logger.info(f"Stopping at summary line: {blunder_line}")
                                break
                                
                            # Parse blunder lines that start with "Move"
                            if blunder_line.startswith('Move') and ':' in blunder_line:
                                logger.info(f"Parsing blunder line: {blunder_line}")
                                try:
                                    # Extract move number and description
                                    parts = blunder_line.split(':', 1)
                                    if len(parts) == 2:
                                        move_part = parts[0].strip()
                                        desc_part = parts[1].strip()
                                        
                                        # Extract move number
                                        move_num = None
                                        if 'Move' in move_part:
                                            move_num_str = move_part.replace('Move', '').strip()
                                            try:
                                                move_num = int(move_num_str)
                                            except ValueError:
                                                pass
                                        
                                        # Determine category from the description
                                        category = "Mistake"
                                        if "[Allowed Trap]" in desc_part:
                                            category = "Allowed Trap"
                                        elif "[Missed Material Gain]" in desc_part:
                                            category = "Missed Material Gain"
                                        elif "[Hanging a Piece]" in desc_part:
                                            category = "Hanging a Piece"
                                        elif "[Critical blunder]" in desc_part:
                                            category = "Critical Blunder"
                                        elif "[Blunder]" in desc_part:
                                            category = "Blunder"
                                        
                                        # Clean up the description (remove category tags)
                                        clean_desc = desc_part
                                        clean_desc = clean_desc.replace("[Allowed Trap]", "").strip()
                                        clean_desc = clean_desc.replace("[Missed Material Gain]", "").strip()
                                        clean_desc = clean_desc.replace("[Hanging a Piece]", "").strip()
                                        clean_desc = clean_desc.replace("[Critical blunder]", "").strip()
                                        clean_desc = clean_desc.replace("[Blunder]", "").strip()
                                        clean_desc = clean_desc.replace("[Mistake]", "").strip()
                                        
                                        logger.info(f"Parsed blunder: Move {move_num}, Category: {category}, Description: {clean_desc}")
                                        
                                        blunders.append({
                                            'move_number': move_num,
                                            'category': category,
                                            'description': clean_desc
                                        })
                                except Exception as e:
                                    logger.warning(f"Failed to parse blunder line: {blunder_line}, error: {e}")
                                    continue
                        break
                
                logger.info(f"Total blunders parsed: {len(blunders)}")
                
                return jsonify({
                    'success': True,
                    'blunders': blunders,
                    'total_blunders': len(blunders),
                    'analysis_time': 'completed'
                })
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file: {e}")
                    
        except subprocess.TimeoutExpired:
            return create_error_response("Analysis timed out", 408)
        except Exception as e:
            logger.error(f"PGN analysis error: {str(e)}")
            return create_error_response(f"Analysis failed: {str(e)}", 500)

    @app.route("/api/progress/<session_id>")
    @app.limiter.limit("100 per minute")  # Higher limit for progress streaming
    def progress_stream(session_id):
        """Server-Sent Events endpoint for progress updates with enhanced error handling."""
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
    
    @app.route("/api/status/<session_id>")
    def status_endpoint(session_id):
        """Simple status endpoint to check analysis completion."""
        try:
            status = get_session_status(session_id)
            return jsonify(status)
        except Exception as e:
            return jsonify({
                'status': 'error',
                'session_id': session_id,
                'error': str(e)
            }), 500
    
    @app.route("/health")
    def health_check():
        """Health check endpoint for monitoring."""
        rate_limiter_health = rate_limiter.health_check()
        return jsonify({
            'status': 'healthy',
            'service': 'MCB Analysis API',
            'version': '1.0.0',
            'concurrent_sessions': len(progress_queues),
            'max_concurrent': MAX_CONCURRENT_SESSIONS,
            'rate_limiter': rate_limiter_health
        })
    
    # Error handlers with production-ready responses
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return jsonify({
            'error': 'Not found',
            'message': 'The requested resource was not found'
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        logger.error(f"Internal server error: {error}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred'
        }), 500
    
    @app.errorhandler(429)
    def rate_limit_error(error):
        """Handle rate limit errors."""
        return jsonify({
            'error': 'Rate limit exceeded',
            'message': 'Too many requests, please try again later'
        }), 429


# ========================================
# APPLICATION FACTORY WITH PRODUCTION FEATURES
# ========================================

def create_app() -> Flask:
    """
    Create and configure the Flask application with production security features.
    
    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__)
    
    # Security Configuration
    app.config.update(SECURITY_CONFIG)
    
    # HTTPS enforcement (disable for local development)
    if HTTPS_ENFORCEMENT:
        Talisman(app, force_https=True)
    
    # Rate limiting
    app.limiter = Limiter(
        key_func=get_remote_address,
        default_limits=RATE_LIMITS['default']
    )
    app.limiter.init_app(app)
    
    # CORS - restrict to your domain in production
    if not DEBUG_MODE:
        CORS(app, origins=CORS_CONFIG['production_origins'])
    else:
        CORS(app, origins=CORS_CONFIG['development_origins'])
    
    # Configure Flask app
    app.config['DEBUG'] = DEBUG_MODE
    
    # Register routes
    register_routes(app)
    
    # Set up logging
    if not DEBUG_MODE:
        logging.basicConfig(level=logging.INFO)
    
    logger.info(f"MCB Application created with production features")
    logger.info(f"Debug mode: {DEBUG_MODE}")
    logger.info(f"HTTPS enforcement: {HTTPS_ENFORCEMENT}")
    logger.info(f"Rate limiting: {RATE_LIMITS}")
    logger.info(f"Max concurrent sessions: {MAX_CONCURRENT_SESSIONS}")
    
    return app


def run_app():
    """Run the Flask application with production settings."""
    app = create_app()
    
    # Production settings
    host = '0.0.0.0' if not DEBUG_MODE else '127.0.0.1'
    
    app.run(
        debug=DEBUG_MODE,
        port=PORT,
        host=host,
        threaded=True,
        use_reloader=DEBUG_MODE
    )


if __name__ == '__main__':
    run_app() 