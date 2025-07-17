"""
MCB Utilities Module
Common utility functions for data validation, transformation, and helper operations.
Production-ready with security features from app_production.py.
"""
import re
import time
import json
import logging
import uuid
import html
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from urllib.parse import quote

from config import (
    USERNAME_PATTERN, DANGEROUS_PATTERNS, CATEGORY_WEIGHTS,
    BLUNDER_GENERAL_DESCRIPTIONS, PIECE_VALUES, PIECE_NAMES
)

# Set up logging
logger = logging.getLogger(__name__)

# ========================================
# PRODUCTION VALIDATION FUNCTIONS
# ========================================

def validate_username(username: str) -> tuple[bool, Optional[str]]:
    """
    Comprehensive username validation with detailed error reporting.
    
    Args:
        username (str): Username to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not username:
        return False, "Username is required"
    
    # Length validation
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    if len(username) > 25:
        return False, "Username must be 25 characters or less"
    
    # Character validation (Chess.com format)
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username can only contain letters, numbers, underscores, and hyphens"
    
    # Security checks
    username_lower = username.lower()
    dangerous_patterns = [
        r'script', r'javascript', r'<', r'>', r'&', r'"', r"'",
        r'drop\s+table', r'union\s+select', r'insert\s+into',
        r'delete\s+from', r'update\s+set', r'--', r'/\*', r'\*/',
        r'exec\s*\(', r'eval\s*\(', r'system\s*\('
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, username_lower):
            return False, "Username contains invalid characters"
    
    return True, None

def sanitize_input(input_str: str) -> str:
    """
    Sanitize input string for safe processing.
    
    Args:
        input_str (str): Input string to sanitize
        
    Returns:
        str: Sanitized string safe for processing
    """
    if not input_str:
        return ""
    
    # HTML encode to prevent XSS
    sanitized = html.escape(input_str)
    
    # URL encode for additional safety
    sanitized = quote(sanitized, safe='')
    
    return sanitized

def validate_analysis_settings(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate analysis request data with production security checks.
    
    Args:
        data (Dict): Request data to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not data:
        return False, "No data provided"
    
    # Check required fields
    required_fields = ['session_id', 'username']
    for field in required_fields:
        if not data.get(field):
            return False, f"Missing required field: {field}"
    
    # Validate username
    username = data.get('username', '').strip()
    username_valid, username_error = validate_username(username)
    if not username_valid:
        return False, username_error
    
    # Validate game count
    game_count = data.get('gameCount', 20)
    if not isinstance(game_count, int) or game_count < 1 or game_count > 100:
        return False, "Game count must be between 1 and 100"
    
    # Validate game types
    game_types = data.get('gameTypes', [])
    if not isinstance(game_types, list):
        return False, "Game types must be a list"
    
    valid_types = ['all', 'rapid', 'blitz', 'bullet', 'daily']
    for game_type in game_types:
        if game_type not in valid_types:
            return False, f"Invalid game type: {game_type}"
    
    # Validate rating filter
    rating_filter = data.get('ratingFilter', 'rated')
    valid_filters = ['all', 'rated', 'unrated']
    if rating_filter not in valid_filters:
        return False, f"Invalid rating filter: {rating_filter}"
    
    # Validate analysis depth
    analysis_depth = data.get('analysisDepth', 'balanced')
    valid_depths = ['fast', 'balanced', 'deep']
    if analysis_depth not in valid_depths:
        return False, f"Invalid analysis depth: {analysis_depth}"
    
    return True, None

# ========================================
# DATA TRANSFORMATION FUNCTIONS
# ========================================

def sanitize_blunders_for_json(blunders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sanitize blunder data to ensure JSON serialization compatibility.
    Handles Move objects and other non-serializable data.
    
    Args:
        blunders (List[Dict]): Raw blunder data
        
    Returns:
        List[Dict]: JSON-safe blunder data
    """
    sanitized = []
    
    for blunder in blunders:
        clean_blunder = blunder.copy()
        
        # Handle Move objects by converting to UCI notation
        for key, value in clean_blunder.items():
            if hasattr(value, 'uci'):  # Chess move object
                try:
                    clean_blunder[key] = value.uci()
                except Exception:
                    clean_blunder[key] = str(value)
            elif hasattr(value, '__dict__') and not isinstance(value, (str, int, float, bool, list, dict)):
                # Other complex objects
                try:
                    clean_blunder[key] = str(value)
                except Exception:
                    clean_blunder[key] = None
        
        # Ensure required fields exist with defaults
        clean_blunder.setdefault('category', 'Unknown')
        clean_blunder.setdefault('impact', 0)
        clean_blunder.setdefault('move', 'unknown')
        clean_blunder.setdefault('position_fen', '')
        
        sanitized.append(clean_blunder)
    
    return sanitized

def format_game_metadata(games_metadata: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format games metadata for frontend consumption.
    
    Args:
        games_metadata (List[Dict]): Raw metadata from game fetching
        
    Returns:
        List[Dict]: Formatted metadata for frontend
    """
    formatted = []
    
    for i, game in enumerate(games_metadata, 1):
        formatted_game = {
            'number': i,
            'white': game.get('white', 'Unknown'),
            'black': game.get('black', 'Unknown'),
            'date': game.get('date', 'Unknown date'),
            'time_class': game.get('time_class', 'unknown'),
            'rated': game.get('rated', False),
            'url': game.get('url', ''),
            'target_player': game.get('target_player', '')
        }
        formatted.append(formatted_game)
    
    return formatted

# ========================================
# SCORING AND CALCULATION UTILITIES
# ========================================

def calculate_category_weight(category: str) -> float:
    """
    Calculate the severity weight for a blunder category.
    
    Args:
        category (str): Blunder category name
        
    Returns:
        float: Weight value for scoring
    """
    return CATEGORY_WEIGHTS.get(category, 1.0)

def calculate_blunder_impact(blunder: Dict[str, Any]) -> float:
    """
    Calculate the impact score for a specific blunder.
    
    Args:
        blunder (Dict): Blunder data
        
    Returns:
        float: Impact score
    """
    # Get evaluation change if available
    eval_change = blunder.get('evaluation_change', 0)
    
    # Base impact from evaluation change
    base_impact = abs(eval_change) / 10.0  # Convert centipawns to impact units
    
    # Category modifier
    category = blunder.get('category', 'Mistake')
    category_weight = calculate_category_weight(category)
    
    # Calculate final impact
    impact = base_impact * category_weight
    
    # Cap impact at reasonable maximum
    return min(impact, 50.0)

def get_piece_value(piece_type: int) -> int:
    """
    Get the value of a chess piece in centipawns.
    
    Args:
        piece_type (int): Chess piece type constant
        
    Returns:
        int: Piece value in centipawns
    """
    return PIECE_VALUES.get(piece_type, 0)

def get_piece_name(piece_type: int) -> str:
    """
    Get the human-readable name of a chess piece.
    
    Args:
        piece_type (int): Chess piece type constant
        
    Returns:
        str: Piece name
    """
    return PIECE_NAMES.get(piece_type, "Unknown")

# ========================================
# SESSION AND ID UTILITIES
# ========================================

def generate_session_id() -> str:
    """
    Generate a unique session ID for tracking analysis progress.
    
    Returns:
        str: Unique session identifier
    """
    return str(uuid.uuid4())

def format_timestamp(timestamp: Optional[float] = None) -> str:
    """
    Format a timestamp for display.
    
    Args:
        timestamp (Optional[float]): Unix timestamp, defaults to current time
        
    Returns:
        str: Formatted timestamp string
    """
    if timestamp is None:
        timestamp = time.time()
    
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

# ========================================
# ERROR HANDLING UTILITIES
# ========================================

def create_error_response(message: str, status_code: int = 400) -> Dict[str, Any]:
    """
    Create a standardized error response.
    
    Args:
        message (str): Error message
        status_code (int): HTTP status code
        
    Returns:
        Dict: Standardized error response
    """
    return {
        'error': message,
        'status_code': status_code,
        'timestamp': time.time()
    }

def log_error(message: str, session_id: Optional[str] = None, exception: Optional[Exception] = None) -> None:
    """
    Log an error with consistent formatting and optional context.
    
    Args:
        message (str): Error message
        session_id (Optional[str]): Session ID for tracking
        exception (Optional[Exception]): Exception object for traceback
    """
    log_message = f"ERROR: {message}"
    
    if session_id:
        log_message += f" [Session: {session_id}]"
    
    if exception:
        logger.error(log_message, exc_info=True)
    else:
        logger.error(log_message)

# ========================================
# PERFORMANCE UTILITIES
# ========================================

class Timer:
    """Context manager for timing operations."""
    
    def __init__(self, operation_name: str, logger: Optional[logging.Logger] = None):
        self.operation_name = operation_name
        self.logger = logger or logging.getLogger(__name__)
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.logger.info(f"{self.operation_name} completed in {duration:.2f}s")

def format_duration(seconds: float) -> str:
    """
    Format a duration in seconds to a human-readable string.
    
    Args:
        seconds (float): Duration in seconds
        
    Returns:
        str: Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

def calculate_eta(completed: int, total: int, elapsed_time: float) -> Optional[float]:
    """
    Calculate estimated time of arrival based on progress.
    
    Args:
        completed (int): Number of completed items
        total (int): Total number of items
        elapsed_time (float): Time elapsed so far
        
    Returns:
        Optional[float]: Estimated remaining time in seconds, None if cannot calculate
    """
    if completed <= 0 or total <= 0 or completed >= total:
        return None
    
    rate = completed / elapsed_time
    remaining = total - completed
    return remaining / rate

# ========================================
# DATA VALIDATION UTILITIES
# ========================================

def is_valid_fen(fen: str) -> bool:
    """
    Validate a FEN (Forsyth-Edwards Notation) string.
    
    Args:
        fen (str): FEN string to validate
        
    Returns:
        bool: True if FEN is valid
    """
    if not fen or not isinstance(fen, str):
        return False
    
    try:
        import chess
        chess.Board(fen)
        return True
    except (ValueError, chess.InvalidFenError):
        return False

def is_valid_uci_move(move: str) -> bool:
    """
    Validate a UCI (Universal Chess Interface) move string.
    
    Args:
        move (str): UCI move string to validate
        
    Returns:
        bool: True if move is valid UCI format
    """
    if not move or not isinstance(move, str):
        return False
    
    # Basic UCI format check: 4-5 characters, squares in a1-h8 format
    uci_pattern = r'^[a-h][1-8][a-h][1-8][qrbn]?$'
    return bool(re.match(uci_pattern, move.lower()))

# ========================================
# EXPORT UTILITIES
# ========================================

def export_results_to_json(results: Dict[str, Any], filename: Optional[str] = None) -> str:
    """
    Export analysis results to JSON format.
    
    Args:
        results (Dict): Analysis results
        filename (Optional[str]): Output filename
        
    Returns:
        str: JSON string or filename if saved
    """
    json_data = json.dumps(results, indent=2, default=str)
    
    if filename:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(json_data)
        return filename
    
    return json_data

# ========================================
# CONFIGURATION HELPERS
# ========================================

def get_blunder_description(category: str) -> str:
    """
    Get the general description for a blunder category.
    
    Args:
        category (str): Blunder category name
        
    Returns:
        str: Description text
    """
    return BLUNDER_GENERAL_DESCRIPTIONS.get(
        category, 
        f"You frequently made {category.lower()} errors during your games."
    )

# ========================================
# SAFE FILE OPERATIONS
# ========================================

def safe_file_operations(filename: str) -> str:
    """
    Safely handle file operations with proper validation.
    
    Args:
        filename (str): Filename to sanitize
        
    Returns:
        str: Safe file path within temporary directory
        
    Raises:
        ValueError: If file path is invalid or unsafe
    """
    import os
    import tempfile
    from pathlib import Path
    
    # Use temporary directory for all file operations
    temp_dir = Path(tempfile.gettempdir()) / "mcb_analysis"
    temp_dir.mkdir(exist_ok=True)
    
    # Sanitize filename - only allow alphanumeric, underscore, hyphen, and dot
    safe_filename = "".join(c for c in filename if c.isalnum() or c in ('-', '_', '.'))
    
    # Ensure filename is not empty after sanitization
    if not safe_filename:
        raise ValueError("Invalid filename - no safe characters remaining")
    
    # Create safe path within temp directory
    safe_path = temp_dir / safe_filename
    
    # Ensure path is within temp directory (prevent path traversal)
    try:
        safe_path.resolve().relative_to(temp_dir.resolve())
    except ValueError:
        raise ValueError("Invalid file path - path traversal detected")
    
    return str(safe_path)

def safe_file_removal(filepath: str) -> bool:
    """
    Safely remove a file with proper validation.
    
    Args:
        filepath (str): Path to file to remove
        
    Returns:
        bool: True if file was removed successfully, False otherwise
    """
    import os
    import tempfile
    from pathlib import Path
    
    try:
        file_path = Path(filepath)
        temp_dir = Path(tempfile.gettempdir()) / "mcb_analysis"
        
        # Ensure file is within our temp directory
        file_path.resolve().relative_to(temp_dir.resolve())
        
        # Check if file exists and remove it
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Safely removed file: {filepath}")
            return True
        else:
            logger.debug(f"File not found for removal: {filepath}")
            return False
            
    except Exception as e:
        logger.error(f"Error removing file {filepath}: {e}")
        return False

def safe_file_check(filepath: str) -> bool:
    """
    Safely check if a file exists with proper validation.
    
    Args:
        filepath (str): Path to file to check
        
    Returns:
        bool: True if file exists and is safe, False otherwise
    """
    import tempfile
    from pathlib import Path
    
    try:
        file_path = Path(filepath)
        temp_dir = Path(tempfile.gettempdir()) / "mcb_analysis"
        
        # Ensure file is within our temp directory
        file_path.resolve().relative_to(temp_dir.resolve())
        
        return file_path.exists()
        
    except Exception as e:
        logger.error(f"Error checking file {filepath}: {e}")
        return False 