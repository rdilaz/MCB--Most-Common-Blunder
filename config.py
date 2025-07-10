"""
MCB Configuration Module
Centralized configuration and constants for the MCB application.
Based on app_production.py for production-ready settings.
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ========================================
# CORE APPLICATION CONFIGURATION
# ========================================

# Engine Configuration
STOCKFISH_PATH = os.environ.get('STOCKFISH_PATH', os.path.join(os.path.dirname(__file__), "stockfish", "stockfish.exe"))
BLUNDER_THRESHOLD = 15
ENGINE_THINK_TIME = 0.1

# Game Analysis Settings
GAMES_TO_FETCH = 1
MAX_GAMES_ALLOWED = 100  # Hard cap to prevent server overload
DAILY_GAME_LIMIT = 200   # Games per user per day

# Analysis Depth Mapping (Optimized for production speed)
ANALYSIS_DEPTH_MAPPING = {
    'fast': 0.05,     # ULTRA FAST: 50ms per move (was 100ms)
    'balanced': 0.08, # FAST: 80ms per move (was 200ms)  
    'deep': 0.15      # NORMAL: 150ms per move (was 500ms)
}

# ========================================
# PRODUCTION SECURITY CONFIGURATION
# ========================================

# Flask Security Settings
SECURITY_CONFIG = {
    'SECRET_KEY': os.environ.get('SECRET_KEY', 'your-secret-key-change-this'),
    'MAX_CONTENT_LENGTH': 16 * 1024 * 1024,  # 16MB max
}

# Rate Limiting Configuration
RATE_LIMITS = {
    'default': ["200 per day", "50 per hour"],
    'analysis': "5 per minute"  # Rate limit analysis requests
}

# CORS Configuration
CORS_CONFIG = {
    'production_origins': [os.environ.get('ALLOWED_ORIGIN', 'https://yourdomain.com')],
    'development_origins': ['*']  # Allow all origins for development
}

# HTTPS Configuration
HTTPS_ENFORCEMENT = os.environ.get('FLASK_ENV') == 'production'

# Timeout Configuration
ANALYSIS_TIMEOUT = 300  # 5 minute timeout
MAX_CONCURRENT_SESSIONS = 10  # Max concurrent analyses

# ========================================
# USERNAME VALIDATION CONFIGURATION
# ========================================

# Chess.com username validation pattern
USERNAME_PATTERN = r'^[a-zA-Z0-9_-]{3,25}$'

# Dangerous patterns to reject (SQL injection prevention)
DANGEROUS_PATTERNS = ['drop', 'select', 'insert', 'delete', 'update', 'union', '--', ';']

# ========================================
# BLUNDER ANALYSIS CONSTANTS
# ========================================

# Blunder Category Priority (for sorting and processing)
BLUNDER_CATEGORY_PRIORITY = {
    "Allowed Checkmate": 1,
    "Missed Checkmate": 2,
    "Allowed Fork": 3,
    "Missed Fork": 4,
    "Allowed Pin": 5,
    "Missed Pin": 6,
    "Hanging a Piece": 7,
    "Losing Exchange": 8,
    "Missed Material Gain": 9,
    "Mistake": 10
}

# Chess Piece Values (in centipawns)
PIECE_VALUES = {
    1: 100,   # chess.PAWN
    2: 300,   # chess.KNIGHT
    3: 320,   # chess.BISHOP
    4: 500,   # chess.ROOK
    5: 900,   # chess.QUEEN
    6: 10000  # chess.KING
}

# Piece Names for Display
PIECE_NAMES = {
    1: "Pawn",
    2: "Knight", 
    3: "Bishop",
    4: "Rook",
    5: "Queen",
    6: "King"
}

# Category Weights for Severity Scoring (Production values)
CATEGORY_WEIGHTS = {
    "Allowed Checkmate": 3.0,
    "Missed Checkmate": 3.0,
    "Hanging a Piece": 2.5,
    "Allowed Fork": 2.0,
    "Missed Fork": 2.0,
    "Losing Exchange": 2.0,
    "Allowed Pin": 1.5,
    "Missed Pin": 1.5,
    "Missed Material Gain": 1.8,
    "Mistake": 1.0
}

# Base Impact Values for Categories (Production tuned)
BASE_IMPACT_VALUES = {
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
}

# Educational descriptions for blunder categories (Production version)
BLUNDER_EDUCATIONAL_DESCRIPTIONS = {
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

# ========================================
# FLASK APPLICATION SETTINGS
# ========================================

# Development Settings
DEBUG_MODE = os.environ.get('FLASK_ENV') != 'production'
PORT = int(os.environ.get('PORT', 5000))

# ========================================
# PROGRESS TRACKING CONFIGURATION  
# ========================================

# Time-weighted progress phases (in seconds) - Production optimized
PROGRESS_PHASE_WEIGHTS = {
    "starting": 0.5,
    "fetching_games": 2.0,
    "engine_init": 0.5, 
    "reading_pgn": 0.2,
    "analyzing_games": 8.0,  # Will be multiplied by game count
    "aggregating": 0.3
}

# Progress Queue Settings
PROGRESS_QUEUE_MAX_SIZE = 50
PROGRESS_HEARTBEAT_TIMEOUT = 30

# ========================================
# PERFORMANCE OPTIMIZATION SETTINGS
# ========================================

# Speed optimization settings
ESTIMATED_MOVES_PER_GAME = 35  # Average chess game length
SPEED_OPTIMIZATION_ENABLED = True

# Speed optimization descriptions for user feedback
OPTIMIZATION_DESCRIPTIONS = {
    'fast': {
        'mode': 'Fast',
        'speed_gain': '2-4x faster'
    },
    'balanced': {
        'mode': 'Balanced', 
        'speed_gain': '1.5-2.5x faster'
    },
    'deep': {
        'mode': 'Deep',
        'speed_gain': '1.5x faster'
    }
}

# ========================================
# FILE PATHS AND DEFAULTS
# ========================================

# Default paths
DEFAULT_PGN_FILE = "testgames.pgn"
STOCKFISH_EXECUTABLE = "stockfish.exe"

# Directory structure
STOCKFISH_DIR = "stockfish"
GAMES_DIR = "games"
OLD_FILES_DIR = "old files"

# ========================================
# LOGGING CONFIGURATION
# ========================================

LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
} 