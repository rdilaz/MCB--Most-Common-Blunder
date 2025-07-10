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

# Daily usage tracking (in production, this would use Redis or database)
daily_usage = {}

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
                return jsonify(create_error_response('Session ID and username are required'))
            
            if not validate_username(username):
                return jsonify(create_error_response('Invalid username format'))
            
            # SECURITY: Enhanced usage limits 
            if game_count > MAX_GAMES_ALLOWED:
                return jsonify(create_error_response(f'Maximum {MAX_GAMES_ALLOWED} games allowed'))
            
            # SECURITY: Daily usage tracking
            daily_limit_key = f"daily_usage_{username}_{time.strftime('%Y-%m-%d')}"
            current_usage = daily_usage.get(daily_limit_key, 0)
            
            if current_usage + game_count > DAILY_GAME_LIMIT:
                remaining = max(0, DAILY_GAME_LIMIT - current_usage)
                return jsonify({
                    'error': f'Daily limit reached. You can analyze {remaining} more games today.',
                    'daily_limit': DAILY_GAME_LIMIT,
                    'used_today': current_usage,
                    'remaining': remaining
                }), 429
            
            # Update usage counter
            daily_usage[daily_limit_key] = current_usage + game_count
            
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
                    'daily_limit': DAILY_GAME_LIMIT,
                    'used_today': current_usage,
                    'remaining': DAILY_GAME_LIMIT - current_usage - game_count,
                    'max_games_per_request': MAX_GAMES_ALLOWED
                }
            })
            
        except Exception as e:
            log_error(f"Error starting analysis: {str(e)}")
            return jsonify(create_error_response('Internal server error', 500))
    
    @app.route("/api/progress/<session_id>")
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
        return jsonify({
            'status': 'healthy',
            'service': 'MCB Analysis API',
            'version': '1.0.0',
            'concurrent_sessions': len(progress_queues),
            'max_concurrent': MAX_CONCURRENT_SESSIONS
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