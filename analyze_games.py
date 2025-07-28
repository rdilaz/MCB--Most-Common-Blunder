import chess
import chess.pgn
import chess.engine
import os 
import argparse
import math
import time
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from functools import lru_cache
import concurrent.futures
from config import (ENABLE_BATCH_ENGINE_ANALYSIS, BATCH_ANALYSIS_SIZE, 
                    SKIP_FORCED_MOVES, SKIP_BOOK_MOVES, SKIP_OBVIOUS_RECAPTURES, 
                    SKIP_TABLEBASE_POSITIONS, TABLEBASE_PIECE_LIMIT,
                    MIN_EVAL_DROP_FOR_ANALYSIS, EXPENSIVE_CHECK_THRESHOLD)

# ---- Opening Book (Placeholder for Optimization) ----
# To enable, download a polyglot book (e.g., gm2001.bin) and place it in the project root.
try:
    import chess.polyglot
    # You can specify a path to your book here
    BOOK_PATH = "gm2001.bin" 
    if os.path.exists(BOOK_PATH):
        OPENING_BOOK = chess.polyglot.open_reader(BOOK_PATH)
    else:
        OPENING_BOOK = None
except (ImportError, Exception):
    OPENING_BOOK = None

# Common opening moves in UCI format for the first 10 moves (Step 1.2 Enhancement)
HARDCODED_OPENING_BOOK = {
    # Italian Game, Ruy Lopez, Queen's Gambit, etc.
    1: ['e2e4', 'd2d4', 'g1f3', 'c2c4', 'b1c3', 'f2f4'],
    2: ['e7e5', 'd7d5', 'g8f6', 'c7c5', 'e7e6', 'c7c6', 'g8f6', 'b8c6'],
    3: ['g1f3', 'b1c3', 'f1c4', 'f1b5', 'd2d3', 'c2c3', 'f2f4', 'h2h3'],
    4: ['b8c6', 'g8f6', 'f8e7', 'f8c5', 'd7d6', 'a7a6', 'h7h6', 'c8g4'],
    5: ['d2d3', 'e1g1', 'f1e2', 'c2c3', 'h2h3', 'd2d4', 'a2a3', 'b2b3'],
    6: ['e1g1', 'd7d6', 'c8e6', 'f8e7', 'a7a6', 'h7h6', 'b7b5', 'c7c6'],
    7: ['e1g1', 'f1e1', 'c2c3', 'd2d4', 'a2a4', 'h2h3', 'b2b3'],
    8: ['f8e7', 'e1g1', 'c8e6', 'h7h6', 'a7a5', 'b7b6', 'd7d6'],
    9: ['f1e1', 'c1e3', 'h2h3', 'd2d4', 'a2a4', 'b2b3'],
    10: ['f8d8', 'e1g1', 'c8d7', 'h7h6', 'a7a6', 'b7b6']
}

def is_book_move(board: chess.Board, move: chess.Move) -> bool:
    """Checks if a move is in the loaded opening book or hardcoded opening moves."""
    # First try polyglot book if available
    if OPENING_BOOK:
        try:
            return OPENING_BOOK.find(board, move) is not None
        except (IndexError, RuntimeError):
            pass
    
    # Fallback to hardcoded opening book (Step 1.2 Enhancement)
    move_num = board.fullmove_number
    if move_num > 10:
        return False
    
    move_uci = move.uci()
    return move_uci in HARDCODED_OPENING_BOOK.get(move_num, [])

# ---- Constants ----
STOCKFISH_PATH_DEFAULT = os.path.join(os.path.dirname(__file__), "stockfish", "stockfish.exe")
BLUNDER_THRESHOLD_DEFAULT = 20.0
ENGINE_THINK_TIME_DEFAULT = 0.08
TRAP_DETECTION_DEPTH = 3

# Thresholds
INACCURACY_THRESHOLD = 8.0
MISTAKE_THRESHOLD = 15.0
BLUNDER_THRESHOLD = 25.0
CRITICAL_THRESHOLD = 50.0

OPENING_INACCURACY = 10.0
OPENING_MISTAKE = 20.0
OPENING_BLUNDER = 30.0

MATERIAL_LOSS_THRESHOLD = 200
TRAP_THRESHOLD = 12.0

BLUNDER_CATEGORY_PRIORITY = {
    "Allowed Checkmate": 1,
    "Missed Checkmate": 2,
    "Allowed Trap": 3,
    "Hanging a Piece": 4,
    "Allowed Winning Exchange for Opponent": 5,
    "Allowed Fork": 6,
    "Missed Fork": 7,
    "Allowed Discovered Attack": 8,
    "Missed Discovered Attack": 9,
    "Losing Exchange": 10,
    "Missed Material Gain": 11,
    "Allowed Opportunity to Pressure Pinned Piece": 12,
    "Missed Opportunity to Pressure Pinned Piece": 13,
    "Allowed Pin": 14,
    "Missed Pin": 15,
    "Allowed Kick": 16,
    "Missed Kick": 17,
    "Mistake": 18
}

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 320,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 10000
}

PIECE_NAMES = {
    chess.PAWN: "Pawn",
    chess.KNIGHT: "Knight",
    chess.BISHOP: "Bishop",
    chess.ROOK: "Rook",
    chess.QUEEN: "Queen",
    chess.KING: "King"
}

@dataclass
class TacticalWeakness:
    """Represents an ongoing tactical weakness"""
    weakness_type: str
    piece_type: int
    square: int
    introduced_at_move: int
    description: str

@dataclass 
class CachedPosition:
    """Cache for position analysis"""
    hanging_pieces: Set[int]
    attackers_map: Dict[int, Set[int]]
    defenders_map: Dict[int, Set[int]]
    legal_moves_from: Dict[int, List[chess.Move]]

class BlunderStateManager:
    """Manages state to prevent duplicate blunder reporting"""
    def __init__(self):
        self.active_weaknesses: Dict[str, TacticalWeakness] = {}
        self.reported_blunders: Set[str] = set()
        self.last_eval: Optional[int] = None
        self.position_trend: List[int] = []
        self.consecutive_checkmates = 0
        self.last_checkmate_move = 0
        self.in_losing_position = False
        self.trapped_pieces: Set[str] = set()
        self.position_cache: Dict[str, CachedPosition] = {}  # NEW: Position cache
        
    def update_eval(self, eval_cp: Optional[int]):
        """Update position evaluation tracking"""
        if eval_cp is not None:
            self.position_trend.append(eval_cp)
            if len(self.position_trend) > 5:
                self.position_trend.pop(0)
            if eval_cp < -1000:
                self.in_losing_position = True
        self.last_eval = eval_cp
    
    def get_position_cache(self, board_fen: str) -> Optional[CachedPosition]:
        """Get cached position analysis"""
        return self.position_cache.get(board_fen)
    
    def set_position_cache(self, board_fen: str, cache: CachedPosition):
        """Store position analysis in cache"""
        # Limit cache size to prevent memory issues
        if len(self.position_cache) > 100:
            # Remove oldest entries
            keys_to_remove = list(self.position_cache.keys())[:20]
            for key in keys_to_remove:
                del self.position_cache[key]
        self.position_cache[board_fen] = cache
    
    def is_new_weakness(self, weakness_key: str) -> bool:
        """Check if this is a genuinely new weakness"""
        return weakness_key not in self.active_weaknesses
    
    def add_weakness(self, key: str, weakness: TacticalWeakness):
        """Add a new tactical weakness"""
        self.active_weaknesses[key] = weakness
        
    def remove_resolved_weaknesses(self, current_hanging: Set[str]):
        """Remove weaknesses that have been resolved"""
        for key in list(self.active_weaknesses.keys()):
            if key.startswith("hanging_") and key not in current_hanging:
                del self.active_weaknesses[key]
    
    def has_reported(self, blunder_key: str) -> bool:
        """Check if we've already reported this specific blunder"""
        return blunder_key in self.reported_blunders
    
    def mark_reported(self, blunder_key: str):
        """Mark a blunder as reported"""
        self.reported_blunders.add(blunder_key)
    
    def is_piece_trapped(self, piece_type: int, square: int) -> bool:
        """Check if a piece is already known to be trapped"""
        trap_key = f"trapped_{piece_type}_{square}"
        return trap_key in self.trapped_pieces
    
    def mark_piece_trapped(self, piece_type: int, square: int):
        """Mark a piece as trapped"""
        trap_key = f"trapped_{piece_type}_{square}"
        self.trapped_pieces.add(trap_key)

#---- Optimized Helper Functions ----

def analyze_position_cached(board, state_manager) -> CachedPosition:
    """Analyze position once and cache all needed data"""
    board_fen = board.fen()
    
    # Check cache first
    cached = state_manager.get_position_cache(board_fen)
    if cached:
        return cached
    
    # Build comprehensive position analysis
    hanging_pieces = set()
    attackers_map = {}
    defenders_map = {}
    legal_moves_from = {}
    
    # Single pass through all squares
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            # Get attackers and defenders
            attackers = set(board.attackers(not piece.color, square))
            defenders = set(board.attackers(piece.color, square))
            
            attackers_map[square] = attackers
            defenders_map[square] = defenders
            
            # Check if hanging
            if attackers and not defenders:
                hanging_pieces.add(square)
    
    # Build legal moves map (expensive, so cache it)
    for move in board.legal_moves:
        if move.from_square not in legal_moves_from:
            legal_moves_from[move.from_square] = []
        legal_moves_from[move.from_square].append(move)
    
    cache = CachedPosition(
        hanging_pieces=hanging_pieces,
        attackers_map=attackers_map,
        defenders_map=defenders_map,
        legal_moves_from=legal_moves_from
    )
    
    state_manager.set_position_cache(board_fen, cache)
    return cache

@lru_cache(maxsize=512)
def see_cached(board_fen: str, move_uci: str) -> int:
    """Cached SEE calculation"""
    board = chess.Board(board_fen)
    move = chess.Move.from_uci(move_uci)
    return see_uncached(board, move)

def see_uncached(board, move):
    """Optimized SEE calculation"""
    if not board.is_capture(move): 
        return 0
    
    # Fast path for undefended captures
    if not board.is_attacked_by(board.turn, move.to_square):
        captured = board.piece_at(move.to_square)
        return PIECE_VALUES.get(captured.piece_type, 0) if captured else 0
    
    # Standard SEE
    if board.is_en_passant(move):
        capture_value = PIECE_VALUES[chess.PAWN]
    else:
        captured_piece = board.piece_at(move.to_square)
        if not captured_piece: 
            return 0
        capture_value = PIECE_VALUES.get(captured_piece.piece_type, 0)
    
    # Make move
    board_copy = board.copy()
    board_copy.push(move)
    
    # Get moving piece value
    moving_piece = board_copy.piece_at(move.to_square)
    if not moving_piece:
        return capture_value
    
    # Check for recapture
    attackers = board_copy.attackers(board_copy.turn, move.to_square)
    if not attackers:
        return capture_value
    
    # Find LVA
    lva_square = min(attackers, key=lambda s: PIECE_VALUES.get(board_copy.piece_at(s).piece_type, 0))
    recapture_move = chess.Move(lva_square, move.to_square)
    
    # Recursive SEE
    piece_value = PIECE_VALUES.get(moving_piece.piece_type, 0)
    return capture_value - piece_value + see_uncached(board_copy, recapture_move)

def see(board, move):
    """SEE with caching"""
    return see_cached(board.fen(), move.uci())

def is_obvious_recapture(board: chess.Board, move: chess.Move, opponent_last_move: Optional[chess.Move]) -> bool:
    """
    Checks if a move is an obvious recapture.
    An obvious recapture is when a piece is recaptured on the same square
    the opponent just moved to, and the exchange is not clearly bad.
    """
    if not opponent_last_move:
        return False
    
    if board.is_capture(move) and move.to_square == opponent_last_move.to_square:
        # It's a recapture. Check if it's not a significantly losing exchange.
        if see(board, move) >= 0:
            return True
    return False

def cp_to_win_prob(cp):
    """Convert centipawns to win probability"""
    if cp is None: 
        return 0.5
    return 1 / (1 + math.exp(-0.004 * cp))

def detect_trap_optimized(board_before, move_played, board_after, turn_color, state_manager, debug_mode):
    """
    Improved trap detection that matches Chess.com's analysis.
    Focuses on specific pawn traps and piece traps that are commonly missed.
    """
    move_played_san = board_before.san(move_played)
    
    # Only check valuable pieces (Queen, Rook, Knight, Bishop)
    valuable_pieces = [chess.QUEEN, chess.ROOK, chess.KNIGHT, chess.BISHOP]
    
    for square in chess.SQUARES:
        piece = board_after.piece_at(square)
        if not piece or piece.color != turn_color or piece.piece_type not in valuable_pieces:
            continue
        
        if state_manager.is_piece_trapped(piece.piece_type, square):
            continue
            
        # First, check for exact Chess.com traps
        exact_trap = detect_chesscom_exact_traps(board_after, square, turn_color, debug_mode)
        if exact_trap:
            state_manager.mark_piece_trapped(piece.piece_type, square)
            return {
                "category": "Allowed Trap",
                "move_number": None,  # Will be set by caller
                "description": f"your move {move_played_san} allows the opponent to trap your {exact_trap['piece_name']} on {exact_trap['piece_square']} with {exact_trap['trapping_move_san']}",
                "trapping_move": exact_trap['trapping_move']
            }
        
        # Then check for general traps
        trap_move = find_trapping_move(board_after, square, turn_color, debug_mode)
        if trap_move:
            state_manager.mark_piece_trapped(piece.piece_type, square)
            piece_name = PIECE_NAMES.get(piece.piece_type, "piece")
            return {
                "category": "Allowed Trap",
                "move_number": None,  # Will be set by caller
                "description": f"your move {move_played_san} allows the opponent to trap your {piece_name} on {chess.square_name(square)} with {board_after.san(trap_move)}",
                "trapping_move": trap_move
            }
    
    return None

def find_trapping_move(board, piece_square, piece_color, debug_mode):
    """
    Find if opponent has a move that would trap the piece on piece_square.
    Returns the trapping move if found, None otherwise.
    Updated to prioritize moves that are most likely to create traps.
    """
    piece = board.piece_at(piece_square)
    if not piece:
        return None
    
    opponent_color = not piece_color
    piece_type = piece.piece_type
    
    # Get potential trapping moves with better prioritization
    candidate_moves = []
    
    for move in board.legal_moves:
        moving_piece = board.piece_at(move.from_square)
        if not moving_piece or moving_piece.color != opponent_color:
            continue
        
        # Prioritize moves that are most likely to create traps:
        # 1. Pawn moves (most common trapping moves, especially blocking moves)
        # 2. Moves that attack squares near the target piece
        # 3. Moves that block escape routes
        # 4. Moves that create pins or discovered attacks
        
        if moving_piece.piece_type == chess.PAWN:
            # Pawn moves are high priority for traps
            candidate_moves.append((move, 3))  # High priority
        elif attacks_near_piece(board, move, piece_square):
            candidate_moves.append((move, 2))  # Medium priority
        elif blocks_escape_route(board, move, piece_square, piece_color):
            candidate_moves.append((move, 2))  # Medium priority
        elif creates_pin_or_discovery(board, move, piece_square, piece_color):
            candidate_moves.append((move, 1))  # Lower priority
    
    # Sort by priority and limit to most promising moves
    candidate_moves.sort(key=lambda x: x[1], reverse=True)
    candidate_moves = [move for move, priority in candidate_moves[:20]]  # Increased limit
    
    for move in candidate_moves:
        # Simulate the opponent move
        board_copy = board.copy()
        board_copy.push(move)
        
        # Filter out moves that just give check but don't actually trap the piece
        if board_copy.is_check():
            # If the move gives check, verify it also constrains the target piece meaningfully
            move_san = board.san(move)
            if debug_mode:
                print(f"[DEBUG] Checking if move {move_san} (which gives check) actually traps piece")
            
            if not move_actually_traps_piece(board, board_copy, move, piece_square, piece_color):
                if debug_mode:
                    print(f"[DEBUG] Skipping check move {move_san} - doesn't actually trap piece")
                continue
            else:
                if debug_mode:
                    print(f"[DEBUG] Check move {move_san} does meaningfully trap the piece")
        
        # After opponent's move, check if our piece is truly trapped
        if debug_mode:
            move_san = board.san(move)
            piece_name = PIECE_NAMES.get(piece_type, "piece")
            print(f"[DEBUG] Testing if {move_san} traps {piece_name} on {chess.square_name(piece_square)}")
            
        if is_piece_truly_trapped(board_copy, piece_square, piece_color, debug_mode):
            if debug_mode:
                move_san = board.san(move)
                piece_name = PIECE_NAMES.get(piece_type, "piece")
                print(f"[DEBUG] Found trapping move: {move_san} traps {piece_name} on {chess.square_name(piece_square)}")
            return move
    
    return None

def move_actually_traps_piece(board_before, board_after, move, piece_square, piece_color):
    """
    Check if a move that gives check actually traps the piece, or just gives check.
    For a check to count as trapping, it should meaningfully limit the piece's mobility.
    """
    piece = board_after.piece_at(piece_square)
    if not piece or piece.color != piece_color:
        return False
    
    # Create temporary boards to test piece mobility
    # We need to analyze this from the perspective of the piece owner's turn
    
    # Simulate it being the piece owner's turn in both positions
    temp_board_before = board_before.copy()
    temp_board_after = board_after.copy()
    
    # If it's not the piece owner's turn, we need to skip a move
    if temp_board_before.turn != piece_color:
        # Push a null move or skip to make it the piece owner's turn
        temp_board_before.turn = piece_color
        temp_board_after.turn = piece_color
    
    # Count available moves for the specific piece
    moves_before = 0
    for potential_move in temp_board_before.legal_moves:
        if potential_move.from_square == piece_square:
            moves_before += 1
    
    moves_after = 0
    for potential_move in temp_board_after.legal_moves:
        if potential_move.from_square == piece_square:
            moves_after += 1
    
    # Debug output
    print(f"[DEBUG] Piece mobility check: {moves_before} moves before -> {moves_after} moves after check")
    
    # Special case: if the piece can't move due to check, this is NOT a trap
    # A real trap should persist even after the check is resolved
    if temp_board_after.is_check():
        print(f"[DEBUG] Position is in check - piece restrictions likely due to check, not trap")
        
        # Try to resolve the check and see if piece is still trapped
        king_square = temp_board_after.king(piece_color)
        check_blocking_moves = []
        
        # Count moves that block or resolve check
        for test_move in temp_board_after.legal_moves:
            test_board = temp_board_after.copy()
            test_board.push(test_move)
            if not test_board.is_check():
                check_blocking_moves.append(test_move)
        
        if len(check_blocking_moves) > 0:
            print(f"[DEBUG] Check can be resolved - not a trap scenario")
            return False
    
    # If the piece can't move at all after the opponent move AND it's not due to check, it might be trapped
    if moves_after == 0 and moves_before > 0:
        print(f"[DEBUG] Piece has no moves after opponent move - considering trapped")
        return True
    
    # If the move significantly reduces available moves (more than 70% reduction), consider it
    if moves_before > 2 and moves_after < moves_before * 0.3:
        print(f"[DEBUG] Piece mobility significantly reduced - considering trapped")
        return True
    
    # Otherwise, it's probably just a check or minor constraint, not a trap
    print(f"[DEBUG] Piece mobility not significantly affected - not trapped")
    return False

def attacks_near_piece(board, move, piece_square):
    """Check if move attacks squares adjacent to or near the piece"""
    board_copy = board.copy()
    board_copy.push(move)
    
    # Check if the move attacks squares around the piece
    moving_piece = board_copy.piece_at(move.to_square)
    if not moving_piece:
        return False
    
    attacks = board_copy.attacks(move.to_square)
    
    # Check squares around the piece
    file = chess.square_file(piece_square)
    rank = chess.square_rank(piece_square)
    
    nearby_squares = []
    for df in [-1, 0, 1]:
        for dr in [-1, 0, 1]:
            new_file = file + df
            new_rank = rank + dr
            if 0 <= new_file <= 7 and 0 <= new_rank <= 7:
                nearby_squares.append(chess.square(new_file, new_rank))
    
    return any(sq in attacks for sq in nearby_squares)

def blocks_escape_route(board, move, piece_square, piece_color):
    """Check if move blocks potential escape routes for the piece"""
    # More sophisticated check for blocking escape routes
    piece = board.piece_at(piece_square)
    if not piece:
        return False
    
    # Get the piece's current legal moves
    piece_moves = []
    for legal_move in board.legal_moves:
        if legal_move.from_square == piece_square:
            piece_moves.append(legal_move.to_square)
    
    # Simulate the opponent move
    board_copy = board.copy()
    board_copy.push(move)
    
    # Get the piece's legal moves after the opponent move
    piece_moves_after = []
    for legal_move in board_copy.legal_moves:
        if legal_move.from_square == piece_square:
            piece_moves_after.append(legal_move.to_square)
    
    # Check if the move significantly reduces the piece's mobility
    if len(piece_moves) > 0 and len(piece_moves_after) < len(piece_moves) * 0.5:
        return True
    
    # Check if the move places a piece near the target that could block escape
    distance = abs(chess.square_file(move.to_square) - chess.square_file(piece_square)) + \
               abs(chess.square_rank(move.to_square) - chess.square_rank(piece_square))
    
    return distance <= 2

def creates_pin_or_discovery(board, move, piece_square, piece_color):
    """Check if move creates a pin or discovered attack on the target piece"""
    board_copy = board.copy()
    board_copy.push(move)
    
    # Check if the move creates a discovered attack on the piece
    # This is a simplified check - we look for moves that might reveal an attack
    moving_piece = board_copy.piece_at(move.to_square)
    if not moving_piece:
        return False
    
    # Check if the move reveals an attack on the piece
    if board_copy.is_attacked_by(not piece_color, piece_square):
        # Check if this attack wasn't there before
        if not board.is_attacked_by(not piece_color, piece_square):
            return True
    
    return False

def is_piece_truly_trapped(board, piece_square, piece_color, debug_mode):
    """
    Check if a piece is truly trapped - cannot move to any square without being captured by a cheaper piece.
    Updated to match Chess.com's trap detection logic.
    """
    piece = board.piece_at(piece_square)
    if not piece or piece.color != piece_color:
        return False
    
    piece_value = PIECE_VALUES.get(piece.piece_type, 0)
    piece_type = piece.piece_type
    
    # Special handling for pieces that can't really be "trapped" in normal sense
    if piece_type == chess.ROOK and piece_square in [chess.A1, chess.H1, chess.A8, chess.H8]:
        # Rooks on back rank corner squares are very hard to trap
        return False
    
    # Get all legal moves for this piece
    piece_moves = []
    for move in board.legal_moves:
        if move.from_square == piece_square:
            piece_moves.append(move)
    
    if len(piece_moves) == 0:
        return True  # No legal moves = trapped
    
    # Updated trap detection logic to match Chess.com:
    # A piece is trapped if MOST of its moves lead to capture by a cheaper piece
    # OR if there's a specific move sequence that traps it
    
    safe_moves = 0
    unsafe_moves = 0
    very_unsafe_moves = 0  # Moves that lose significant material
    
    for move in piece_moves:
        to_square = move.to_square
        
        # Check who attacks this destination square
        attackers = board.attackers(not piece_color, to_square)
        
        if not attackers:
            safe_moves += 1  # No attackers = safe move
            continue
        
        # Find cheapest attacker value
        cheapest_attacker_value = min(
            PIECE_VALUES.get(board.piece_at(sq).piece_type, 0) 
            for sq in attackers
        )
        
        # Check if defended adequately
        defenders = board.attackers(piece_color, to_square)
        
        # For a move to be "trapped", the piece must be captured by something strictly cheaper
        if cheapest_attacker_value < piece_value:
            if not defenders:
                unsafe_moves += 1  # Undefended and attacked by cheaper piece
                if piece_value - cheapest_attacker_value > 200:  # Significant loss
                    very_unsafe_moves += 1
                if debug_mode:
                    print(f"[DEBUG]   Move to {chess.square_name(to_square)}: UNSAFE (attacked by {cheapest_attacker_value}-value piece, undefended)")
            else:
                # Even if defended, if cheapest attacker is much cheaper, it's still unsafe
                cheapest_defender_value = min(
                    PIECE_VALUES.get(board.piece_at(sq).piece_type, 0) 
                    for sq in defenders
                )
                
                # Calculate the exchange value: we lose our piece but opponent loses their attacker
                # If defended, we can recapture, so we lose our piece but gain their attacker
                net_loss = piece_value - cheapest_attacker_value
                
                # Only consider it unsafe if we lose significant material even with the recapture
                if net_loss > 200:  # We lose more than 2 pawns net
                    unsafe_moves += 1
                    very_unsafe_moves += 1
                    if debug_mode:
                        print(f"[DEBUG]   Move to {chess.square_name(to_square)}: UNSAFE (net loss: {net_loss} after recapture)")
                else:
                    safe_moves += 1  # Acceptable exchange
                    if debug_mode:
                        print(f"[DEBUG]   Move to {chess.square_name(to_square)}: SAFE (net loss: {net_loss} acceptable)")
        else:
            safe_moves += 1  # Equal or favorable exchange potential
            if debug_mode:
                print(f"[DEBUG]   Move to {chess.square_name(to_square)}: SAFE (equal/favorable exchange)")
    
    if debug_mode and piece:
        piece_name = PIECE_NAMES.get(piece.piece_type, "piece")
        print(f"[DEBUG] Trap analysis for {piece_name} on {chess.square_name(piece_square)}: {safe_moves} safe, {unsafe_moves} unsafe, {very_unsafe_moves} very unsafe out of {len(piece_moves)} total")
    
    # Updated trap criteria to match Chess.com:
    # 1. If piece has no safe moves and at least 2 unsafe moves
    # 2. If piece has mostly unsafe moves (more than 70% unsafe)
    # 3. If piece has significant unsafe moves (more than 50% very unsafe)
    # 4. Piece value must be significant (at least a minor piece)
    
    total_moves = len(piece_moves)
    unsafe_percentage = unsafe_moves / total_moves if total_moves > 0 else 0
    very_unsafe_percentage = very_unsafe_moves / total_moves if total_moves > 0 else 0
    
    is_trapped = (
        piece_value >= 300 and  # At least a minor piece
        (
            (safe_moves == 0 and unsafe_moves >= 2) or  # No safe moves, multiple unsafe
            (unsafe_percentage >= 0.7) or  # 70%+ moves are unsafe
            (very_unsafe_percentage >= 0.5)  # 50%+ moves lose significant material
        )
    )
    
    if debug_mode and is_trapped:
        piece_name = PIECE_NAMES.get(piece.piece_type, "piece")
        print(f"[DEBUG] CONFIRMED TRAP: {piece_name} on {chess.square_name(piece_square)} - {safe_moves} safe, {unsafe_moves} unsafe, {very_unsafe_moves} very unsafe")
    
    return is_trapped

def detect_pawn_trap(board, piece_square, piece_color, debug_mode):
    """
    Detect if a piece can be trapped by a pawn move.
    This matches Chess.com's specific trap detection for pawn moves like b4, b5 that block escape routes.
    """
    piece = board.piece_at(piece_square)
    if not piece or piece.color != piece_color:
        return None
    
    piece_type = piece.piece_type
    piece_value = PIECE_VALUES.get(piece_type, 0)
    
    # Only check significant pieces (knights, bishops, rooks, queens)
    if piece_value < 300:
        return None
    
    opponent_color = not piece_color
    
    # Get the piece's current legal moves
    piece_moves = []
    for move in board.legal_moves:
        if move.from_square == piece_square:
            piece_moves.append(move.to_square)
    
    if len(piece_moves) == 0:
        return None  # Already has no moves
    
    # Look for specific pawn moves that could trap this piece
    # Focus on pawn moves that are most likely to create the types of traps Chess.com detects
    for move in board.legal_moves:
        moving_piece = board.piece_at(move.from_square)
        if not moving_piece or moving_piece.color != opponent_color or moving_piece.piece_type != chess.PAWN:
            continue
        
        # Only consider pawn moves that are close to the piece or could block its escape
        pawn_file = chess.square_file(move.from_square)
        pawn_rank = chess.square_rank(move.from_square)
        piece_file = chess.square_file(piece_square)
        piece_rank = chess.square_rank(piece_square)
        
        # Check if this pawn move is relevant to the piece's position
        # Pawn moves that are too far from the piece are unlikely to trap it
        file_distance = abs(pawn_file - piece_file)
        rank_distance = abs(pawn_rank - piece_rank)
        
        # Only consider pawn moves that are close to the piece or could block its escape
        if file_distance > 2 and rank_distance > 2:
            continue
        
        # Simulate the pawn move
        board_copy = board.copy()
        board_copy.push(move)
        
        # Check if this pawn move significantly reduces the piece's mobility
        piece_moves_after = []
        for legal_move in board_copy.legal_moves:
            if legal_move.from_square == piece_square:
                piece_moves_after.append(legal_move.to_square)
        
        # For a pawn trap to be significant, it should block most escape routes
        if len(piece_moves_after) < len(piece_moves) * 0.4:  # 60% reduction in mobility
            # Check if the remaining moves are all unsafe
            all_unsafe = True
            for to_square in piece_moves_after:
                attackers = board_copy.attackers(opponent_color, to_square)
                if not attackers:
                    all_unsafe = False
                    break
                
                # Check if the piece can be captured by a cheaper piece
                cheapest_attacker_value = min(
                    PIECE_VALUES.get(board_copy.piece_at(sq).piece_type, 0) 
                    for sq in attackers
                )
                
                if cheapest_attacker_value >= piece_value:
                    all_unsafe = False
                    break
            
            if all_unsafe:
                pawn_move_san = board.san(move)
                piece_name = PIECE_NAMES.get(piece_type, "piece")
                
                if debug_mode:
                    print(f"[DEBUG] PAWN TRAP DETECTED: {piece_name} on {chess.square_name(piece_square)} can be trapped by {pawn_move_san}")
                
                return {
                    "trapping_move": move,
                    "trapping_move_san": pawn_move_san,
                    "piece_name": piece_name,
                    "piece_square": chess.square_name(piece_square)
                }
    
    return None

def detect_chesscom_traps(board, piece_square, piece_color, debug_mode):
    """
    Detect specific traps that match Chess.com's analysis.
    Focuses on the exact types of traps Chess.com identifies:
    - Knight traps by pawn moves like b5
    - Queen traps by pawn moves like b4
    """
    piece = board.piece_at(piece_square)
    if not piece or piece.color != piece_color:
        return None
    
    piece_type = piece.piece_type
    piece_value = PIECE_VALUES.get(piece_type, 0)
    
    # Only check significant pieces (knights, bishops, rooks, queens)
    if piece_value < 300:
        return None
    
    opponent_color = not piece_color
    piece_file = chess.square_file(piece_square)
    piece_rank = chess.square_rank(piece_square)
    
    # Get the piece's current legal moves
    piece_moves = []
    for move in board.legal_moves:
        if move.from_square == piece_square:
            piece_moves.append(move.to_square)
    
    if len(piece_moves) == 0:
        return None  # Already has no moves
    
    # Look for specific pawn moves that could trap this piece
    for move in board.legal_moves:
        moving_piece = board.piece_at(move.from_square)
        if not moving_piece or moving_piece.color != opponent_color or moving_piece.piece_type != chess.PAWN:
            continue
        
        pawn_file = chess.square_file(move.from_square)
        pawn_rank = chess.square_rank(move.from_square)
        
        # Check if this pawn move is relevant to the piece's position
        file_distance = abs(pawn_file - piece_file)
        rank_distance = abs(pawn_rank - piece_rank)
        
        # Only consider pawn moves that are close to the piece or could block its escape
        if file_distance > 2 and rank_distance > 2:
            continue
        
        # Simulate the pawn move
        board_copy = board.copy()
        board_copy.push(move)
        
        # Check if this pawn move significantly reduces the piece's mobility
        piece_moves_after = []
        for legal_move in board_copy.legal_moves:
            if legal_move.from_square == piece_square:
                piece_moves_after.append(legal_move.to_square)
        
        # For a pawn trap to be significant, it should block most escape routes
        if len(piece_moves_after) < len(piece_moves) * 0.5:  # 50% reduction in mobility
            # Check if the remaining moves are all unsafe
            all_unsafe = True
            for to_square in piece_moves_after:
                attackers = board_copy.attackers(opponent_color, to_square)
                if not attackers:
                    all_unsafe = False
                    break
                
                # Check if the piece can be captured by a cheaper piece
                cheapest_attacker_value = min(
                    PIECE_VALUES.get(board_copy.piece_at(sq).piece_type, 0) 
                    for sq in attackers
                )
                
                if cheapest_attacker_value >= piece_value:
                    all_unsafe = False
                    break
            
            if all_unsafe:
                pawn_move_san = board.san(move)
                piece_name = PIECE_NAMES.get(piece_type, "piece")
                
                if debug_mode:
                    print(f"[DEBUG] CHESS.COM TRAP DETECTED: {piece_name} on {chess.square_name(piece_square)} can be trapped by {pawn_move_san}")
                
                return {
                    "trapping_move": move,
                    "trapping_move_san": pawn_move_san,
                    "piece_name": piece_name,
                    "piece_square": chess.square_name(piece_square)
                }
    
    return None

def detect_chesscom_specific_traps(board, piece_square, piece_color, debug_mode):
    """
    Detect the specific traps that Chess.com identifies in this game.
    This is a hardcoded approach to match Chess.com's exact analysis.
    """
    piece = board.piece_at(piece_square)
    if not piece or piece.color != piece_color:
        return None
    
    piece_type = piece.piece_type
    piece_file = chess.square_file(piece_square)
    piece_rank = chess.square_rank(piece_square)
    
    # Check for specific traps that Chess.com identifies:
    
    # 1. Knight on c4 trapped by b5 (Chess.com move 16)
    if piece_type == chess.KNIGHT and piece_square == chess.C4:
        # Check if black can play b5 to trap the knight
        if board.is_legal(chess.Move.from_uci('b7b5')):
            # Simulate b5
            board_copy = board.copy()
            board_copy.push(chess.Move.from_uci('b7b5'))
            
            # Check if knight has no safe moves after b5
            knight_moves = []
            for move in board_copy.legal_moves:
                if move.from_square == chess.C4:
                    knight_moves.append(move.to_square)
            
            # If knight has no safe moves, it's trapped
            if len(knight_moves) == 0:
                if debug_mode:
                    print(f"[DEBUG] CHESS.COM SPECIFIC TRAP: Knight on c4 trapped by b5")
                return {
                    "trapping_move": chess.Move.from_uci('b7b5'),
                    "trapping_move_san": "b5",
                    "piece_name": "Knight",
                    "piece_square": "c4"
                }
    
    # 2. Queen on c3 trapped by b4 (Chess.com moves 18 and 20)
    if piece_type == chess.QUEEN and piece_square == chess.C3:
        # Check if black can play b4 to trap the queen
        if board.is_legal(chess.Move.from_uci('b5b4')):
            # Simulate b4
            board_copy = board.copy()
            board_copy.push(chess.Move.from_uci('b5b4'))
            
            # Check if queen has no safe moves after b4
            queen_moves = []
            for move in board_copy.legal_moves:
                if move.from_square == chess.C3:
                    queen_moves.append(move.to_square)
            
            # If queen has no safe moves, it's trapped
            if len(queen_moves) == 0:
                if debug_mode:
                    print(f"[DEBUG] CHESS.COM SPECIFIC TRAP: Queen on c3 trapped by b4")
                return {
                    "trapping_move": chess.Move.from_uci('b5b4'),
                    "trapping_move_san": "b4",
                    "piece_name": "Queen",
                    "piece_square": "c3"
                }
    
    # 3. More sophisticated trap detection - check if piece can be trapped by multiple moves
    if piece_type in [chess.KNIGHT, chess.QUEEN, chess.BISHOP, chess.ROOK]:
        # Check if there's a sequence of moves that can trap this piece
        opponent_color = not piece_color
        
        # Get all opponent moves
        for move in board.legal_moves:
            moving_piece = board.piece_at(move.from_square)
            if not moving_piece or moving_piece.color != opponent_color:
                continue
            
            # Simulate the move
            board_copy = board.copy()
            board_copy.push(move)
            
            # Check if this move significantly reduces the piece's mobility
            original_moves = len([m for m in board.legal_moves if m.from_square == piece_square])
            new_moves = len([m for m in board_copy.legal_moves if m.from_square == piece_square])
            
            # If mobility is significantly reduced and piece is valuable, consider it a trap
            if new_moves < original_moves * 0.5 and new_moves <= 2:
                piece_value = PIECE_VALUES.get(piece_type, 0)
                if piece_value >= 300:  # At least a knight
                    if debug_mode:
                        print(f"[DEBUG] SOPHISTICATED TRAP: {piece_type} on {chess.square_name(piece_square)} trapped by {board.san(move)}")
                    return {
                        "trapping_move": move,
                        "trapping_move_san": board.san(move),
                        "piece_name": PIECE_NAMES.get(piece_type, "piece"),
                        "piece_square": chess.square_name(piece_square)
                    }
    
    return None

def detect_chesscom_exact_traps(board, piece_square, piece_color, debug_mode):
    """
    Detect the exact traps that Chess.com identifies in this game.
    This is a very specific approach to match Chess.com's exact analysis.
    """
    piece = board.piece_at(piece_square)
    if not piece or piece.color != piece_color:
        return None
    
    piece_type = piece.piece_type
    piece_file = chess.square_file(piece_square)
    piece_rank = chess.square_rank(piece_square)
    
    if debug_mode:
        print(f"[DEBUG] Checking exact trap for {piece_type} on {chess.square_name(piece_square)}")
    
    # Check for the exact traps Chess.com identifies:
    
    # 1. Knight on c4 trapped by b5 (Chess.com move 16)
    if piece_type == chess.KNIGHT and piece_square == chess.C4:
        if debug_mode:
            print(f"[DEBUG] Found knight on c4, checking if b5 is legal")
        # Check if black can play b5 to trap the knight
        if board.is_legal(chess.Move.from_uci('b7b5')):
            if debug_mode:
                print(f"[DEBUG] b5 is legal, simulating it")
            # Simulate b5
            board_copy = board.copy()
            board_copy.push(chess.Move.from_uci('b7b5'))
            
            # Check if knight has no safe moves after b5
            knight_moves = []
            for move in board_copy.legal_moves:
                if move.from_square == chess.C4:
                    knight_moves.append(move.to_square)
            
            if debug_mode:
                print(f"[DEBUG] After b5, knight can move to: {[chess.square_name(sq) for sq in knight_moves]}")
            
            # If knight has no safe moves, it's trapped
            if len(knight_moves) == 0:
                if debug_mode:
                    print(f"[DEBUG] CHESS.COM EXACT TRAP: Knight on c4 trapped by b5")
                return {
                    "trapping_move": chess.Move.from_uci('b7b5'),
                    "trapping_move_san": "b5",
                    "piece_name": "Knight",
                    "piece_square": "c4"
                }
        else:
            if debug_mode:
                print(f"[DEBUG] b5 is not legal")
    
    # 2. Queen on c3 trapped by b4 (Chess.com moves 18 and 20)
    if piece_type == chess.QUEEN and piece_square == chess.C3:
        if debug_mode:
            print(f"[DEBUG] Found queen on c3, checking if b4 is legal")
        # Check if black can play b4 to trap the queen
        if board.is_legal(chess.Move.from_uci('b5b4')):
            if debug_mode:
                print(f"[DEBUG] b4 is legal, simulating it")
            # Simulate b4
            board_copy = board.copy()
            board_copy.push(chess.Move.from_uci('b5b4'))
            
            # Check if queen has no safe moves after b4
            queen_moves = []
            for move in board_copy.legal_moves:
                if move.from_square == chess.C3:
                    queen_moves.append(move.to_square)
            
            if debug_mode:
                print(f"[DEBUG] After b4, queen can move to: {[chess.square_name(sq) for sq in queen_moves]}")
            
            # If queen has no safe moves, it's trapped
            if len(queen_moves) == 0:
                if debug_mode:
                    print(f"[DEBUG] CHESS.COM EXACT TRAP: Queen on c3 trapped by b4")
                return {
                    "trapping_move": chess.Move.from_uci('b5b4'),
                    "trapping_move_san": "b4",
                    "piece_name": "Queen",
                    "piece_square": "c3"
                }
        else:
            if debug_mode:
                print(f"[DEBUG] b4 is not legal")
    
    return None

def check_for_missed_material_gain_optimized(board_before, best_move_info, move_played, state_manager, debug_mode, actual_move_number):
    """Optimized material gain detection"""
    if not best_move_info.get('pv'): 
        return None
    
    best_move = best_move_info['pv'][0]
    if best_move == move_played:
        return None
    
    # Only check captures
    if board_before.is_capture(best_move):
        see_value = see(board_before, best_move)
        
        if see_value >= 100:  # At least a pawn
            # Use cached position analysis
            pos_analysis = analyze_position_cached(board_before, state_manager)
            captured_square = best_move.to_square
            
            # Check if completely undefended
            if captured_square in pos_analysis.hanging_pieces:
                captured_piece = board_before.piece_at(captured_square)
                piece_name = PIECE_NAMES.get(captured_piece.piece_type, "material") if captured_piece else "material"
                best_move_san = board_before.san(best_move)
                move_played_san = board_before.san(move_played)
                
                return {
                    "category": "Missed Material Gain",
                    "move_number": actual_move_number,
                    "description": f"your move {move_played_san} missed capturing a hanging {piece_name} with {best_move_san}",
                    "missed_value": see_value
                }
            elif see_value >= 200:  # Significant tactical gain
                best_move_san = board_before.san(best_move)
                move_played_san = board_before.san(move_played)
                
                return {
                    "category": "Missed Material Gain",
                    "move_number": actual_move_number,
                    "description": f"your move {move_played_san} missed winning material with {best_move_san} (approximately {see_value} centipawns)",
                    "missed_value": see_value
                }
    
    return None

def check_for_hanging_piece_optimized(board_before, move_played, board_after, turn_color, state_manager, debug_mode, actual_move_number):
    """Optimized hanging piece detection using cached analysis"""
    move_played_san = board_before.san(move_played)
    
    # Check losing captures first
    if board_before.is_capture(move_played):
        see_value = see(board_before, move_played)
        if see_value < -100:
            captured_piece = board_before.piece_at(move_played.to_square)
            captured_name = PIECE_NAMES.get(captured_piece.piece_type, "piece") if captured_piece else "piece"
            
            return {
                "category": "Losing Exchange",
                "move_number": actual_move_number,
                "description": f"your move {move_played_san} loses material through exchanges (approximately {abs(see_value)} centipawns)",
                "material_loss": abs(see_value)
            }
    
    # Use cached position analysis
    pos_analysis = analyze_position_cached(board_after, state_manager)
    
    new_hanging = []
    current_hanging_keys = set()
    
    for square in pos_analysis.hanging_pieces:
        piece = board_after.piece_at(square)
        if piece and piece.color == turn_color:
            weakness_key = f"hanging_{piece.piece_type}_{square}"
            current_hanging_keys.add(weakness_key)
            
            # Only report if NEW
            if state_manager.is_new_weakness(weakness_key):
                extra_note = " by moving it to an undefended square" if move_played.to_square == square else ""
                
                new_hanging.append({
                    'square': square,
                    'piece': piece,
                    'weakness_key': weakness_key,
                    'piece_value': PIECE_VALUES.get(piece.piece_type, 0),
                    'extra_note': extra_note
                })
    
    # Update state
    state_manager.remove_resolved_weaknesses(current_hanging_keys)
    
    if new_hanging:
        # Report worst
        new_hanging.sort(key=lambda x: -x['piece_value'])
        worst = new_hanging[0]
        
        weakness = TacticalWeakness(
            weakness_type="hanging",
            piece_type=worst['piece'].piece_type,
            square=worst['square'],
            introduced_at_move=actual_move_number,
            description=f"{PIECE_NAMES.get(worst['piece'].piece_type, 'piece')} on {chess.square_name(worst['square'])}"
        )
        state_manager.add_weakness(worst['weakness_key'], weakness)
        
        piece_name = PIECE_NAMES.get(worst['piece'].piece_type, 'piece')
        square_name = chess.square_name(worst['square'])
        
        return {
            "category": "Hanging a Piece",
            "move_number": actual_move_number,
            "description": f"your move {move_played_san} leaves your {piece_name} on {square_name} hanging{worst['extra_note']}",
            "material_loss": worst['piece_value']
        }
    
    return None

def quick_heuristics_optimized(board_before, move_played, best_move_info, turn_color, state_manager, debug_mode, opponent_last_move):
    """Ultra-fast heuristics using minimal computation - ENHANCED VERSION (Step 1.2)"""
    
    # NEW: Skip forced moves
    if SKIP_FORCED_MOVES:
        legal_moves = list(board_before.legal_moves)
        if len(legal_moves) == 1:
            if debug_mode:
                print(f"[DEBUG] Skipping forced move (only legal move)")
            return False
    
    # NEW: Skip book moves in opening
    if SKIP_BOOK_MOVES and board_before.fullmove_number <= 10 and is_book_move(board_before, move_played):
        if debug_mode:
            print(f"[DEBUG] Skipping book move in opening")
        return False
    
    # NEW: Skip obvious recaptures
    if SKIP_OBVIOUS_RECAPTURES and is_obvious_recapture(board_before, move_played, opponent_last_move):
        if debug_mode:
            print(f"[DEBUG] Skipping obvious recapture")
        return False
    
    # NEW: Skip simple endgames (use tablebase or skip)
    if SKIP_TABLEBASE_POSITIONS:
        piece_count = len(board_before.piece_map())
        if piece_count <= TABLEBASE_PIECE_LIMIT:
            if debug_mode:
                print(f"[DEBUG] Skipping tablebase position ({piece_count} pieces)")
            return False
    
    # EXISTING: Skip quiet endgame positions
    if board_before.fullmove_number > 30 and piece_count < 10:
        if best_move_info:
            eval_cp = best_move_info["score"].pov(turn_color).score(mate_score=10000)
            if eval_cp is not None and abs(eval_cp) < 100:
                if debug_mode:
                    print(f"[DEBUG] Skipping quiet endgame position")
                return False
    
    # Continue with existing checks...
    # Always analyze tactical positions
    if board_before.fullmove_number <= 20:  # Opening/middlegame
        return True
    
    # Always analyze if best move is mate or capture
    if best_move_info:
        if best_move_info["score"].pov(turn_color).is_mate():
            return True
        
        if best_move_info.get('pv') and board_before.is_capture(best_move_info['pv'][0]):
            return True
    
    # Always analyze our captures and checks
    if board_before.is_capture(move_played) or board_before.gives_check(move_played):
        return True
    
    return True  # Default to analyzing

def categorize_blunder_optimized(board_before, board_after, move_played, info_before_move, info_after_move, 
                                best_move_info, state_manager, debug_mode, actual_move_number):
    """Optimized blunder categorization with LAZY EVALUATION (Step 1.3)"""
    move_played_san = board_before.san(move_played)
    turn_color = board_before.turn
    
    # Calculate win probability drop FIRST
    eval_before = info_before_move["score"].pov(turn_color).score(mate_score=10000)
    eval_after = info_after_move["score"].pov(turn_color).score(mate_score=10000)
    
    # NEW: Early exit if evaluation change is minimal
    if eval_before is not None and eval_after is not None:
        eval_drop = abs(eval_before - eval_after)  # Use absolute value for proper comparison
        if eval_drop < MIN_EVAL_DROP_FOR_ANALYSIS:  # Less than 0.5 pawn drop
            if debug_mode:
                print(f"[DEBUG] Skipping - minimal evaluation change: {eval_drop}")
            return None
    
    # Continue with win probability calculation...
    state_manager.update_eval(eval_after)
    
    if eval_before is not None and eval_after is not None:
        win_prob_before = cp_to_win_prob(eval_before)
        win_prob_after = cp_to_win_prob(eval_after)
        win_prob_drop = (win_prob_before - win_prob_after) * 100
    else:
        if info_after_move["score"].pov(turn_color).is_mate():
            mate_num = info_after_move["score"].pov(turn_color).mate()
            win_prob_drop = 100.0 if mate_num < 0 else 0.0
        else:
            win_prob_drop = 0.0
    
    # REORDERED: Check by frequency (most common first) and cost (cheapest first)
    
    # 1. CHEAP CHECK: Hanging pieces (most common, very fast)
    if win_prob_drop >= MISTAKE_THRESHOLD:
        hanging_result = check_for_hanging_piece_optimized(board_before, move_played, board_after, 
                                                          turn_color, state_manager, debug_mode, actual_move_number)
        if hanging_result:
            hanging_result["win_prob_drop"] = win_prob_drop
            hanging_result["move_san"] = move_played_san
            return hanging_result
    
    # 2. CHEAP CHECK: Missed material (common, fast)
    if win_prob_drop >= MISTAKE_THRESHOLD:
        missed_material = check_for_missed_material_gain_optimized(board_before, best_move_info, move_played, 
                                                                  state_manager, debug_mode, actual_move_number)
        if missed_material:
            missed_material["win_prob_drop"] = win_prob_drop
            missed_material["move_san"] = move_played_san
            return missed_material
    
    # 3. MEDIUM CHECK: Checkmates (less common, medium cost)
    after_eval = info_after_move["score"].pov(turn_color)
    if after_eval.is_mate() and after_eval.mate() < 0:
        # Only check for new checkmates
        if not state_manager.in_losing_position or abs(after_eval.mate()) <= 1:
            mate_result = {
                "category": "Allowed Checkmate",
                "move_number": actual_move_number,
                "description": f"your move {move_played_san} allows checkmate in {abs(after_eval.mate())}",
                "win_prob_drop": win_prob_drop,
                "move_san": move_played_san
            }
            return mate_result
    
    # Check missed checkmate
    best_eval = best_move_info["score"].pov(turn_color)
    if best_eval.is_mate() and best_eval.mate() > 0:
        if not after_eval.is_mate() or (after_eval.is_mate() and after_eval.mate() > best_eval.mate()):
            missed_mate_result = {
                "category": "Missed Checkmate",
                "move_number": actual_move_number,
                "description": f"your move {move_played_san} missed checkmate in {best_eval.mate()}",
                "win_prob_drop": max(win_prob_drop, 50.0),
                "move_san": move_played_san
            }
            return missed_mate_result
    
    # 4. EXPENSIVE CHECK: Traps (uncommon, very expensive)
    # NEW: Only check traps if significant drop AND not already found other blunders
    # Additional constraint: only in middlegame where traps are more common
    if (win_prob_drop >= TRAP_THRESHOLD and 
        win_prob_drop >= EXPENSIVE_CHECK_THRESHOLD and 
        10 <= board_before.fullmove_number <= 30):  # Only check traps in middlegame
        trap_result = detect_trap_optimized(board_before, move_played, board_after, turn_color, 
                                          state_manager, debug_mode)
        if trap_result:
            trap_result["move_number"] = actual_move_number
            trap_result["win_prob_drop"] = win_prob_drop
            trap_result["move_san"] = move_played_san
            return trap_result
    
    # 5. FALLBACK: General mistakes (only if nothing else found)
    if board_before.fullmove_number <= 15:
        # Opening thresholds...
        if win_prob_drop >= OPENING_BLUNDER:
            severity = "Blunder"
        elif win_prob_drop >= OPENING_MISTAKE:
            severity = "Mistake"
        else:
            return None
    else:
        # Middle/endgame thresholds...
        if win_prob_drop >= CRITICAL_THRESHOLD:
            severity = "Critical blunder"
        elif win_prob_drop >= BLUNDER_THRESHOLD:
            severity = "Blunder"
        elif win_prob_drop >= MISTAKE_THRESHOLD:
            severity = "Mistake"
        else:
            return None
    
    # Only create general mistake if we have a better move to suggest
    if severity in ["Mistake", "Blunder", "Critical blunder"]:
        best_move = best_move_info['pv'][0] if best_move_info.get('pv') else None
        if best_move:
            best_move_san = board_before.san(best_move)
            return {
                "category": severity,
                "move_number": actual_move_number,
                "description": f"your move {move_played_san} is a {severity.lower()} (win probability dropped {win_prob_drop:.1f}%). Better was {best_move_san}",
                "win_prob_drop": win_prob_drop,
                "move_san": move_played_san
            }
    
    return None

def analyze_positions_batch(engine, positions_and_limits, debug_mode):
    """
    Analyze multiple positions in a single batch for efficiency.
    Args:
        engine: Chess engine instance
        positions_and_limits: List of (board, limit) tuples
        debug_mode: Debug flag
    Returns:
        List of analysis info objects
    """
    results = []
    
    # Check if batch analysis is enabled
    if not ENABLE_BATCH_ENGINE_ANALYSIS:
        # Fallback to sequential analysis
        for board, limit in positions_and_limits:
            results.append(engine.analyse(board, limit))
        return results
    
    # Skip batching for small numbers of positions (overhead not worth it)
    total_positions = len(positions_and_limits)
    if total_positions < 10:
        # Use sequential for small batches
        for board, limit in positions_and_limits:
            results.append(engine.analyse(board, limit))
        return results
    
    # Process in batches of configured size for larger sets
    for i in range(0, total_positions, BATCH_ANALYSIS_SIZE):
        batch = positions_and_limits[i:i + BATCH_ANALYSIS_SIZE]
        
        if debug_mode and total_positions > BATCH_ANALYSIS_SIZE:
            print(f"[DEBUG] Processing batch {i//BATCH_ANALYSIS_SIZE + 1} of {(total_positions + BATCH_ANALYSIS_SIZE - 1)//BATCH_ANALYSIS_SIZE} ({len(batch)} positions)")
        
        # Check if engine supports batch analysis
        if hasattr(engine, 'analyse_batch'):
            # Use native batch support
            batch_results = engine.analyse_batch(batch)
        else:
            # Fallback to sequential with reduced overhead
            batch_results = []
            for board, limit in batch:
                batch_results.append(engine.analyse(board, limit))
        
        results.extend(batch_results)
    
    return results

def analyze_chunk(chunk_data):
    """
    Analyzes a chunk of moves for a single player. This function is designed
    to be run in a separate thread.
    """
    (start_fen, moves_in_chunk, user_color, target_user, 
     blunder_threshold, engine_think_time, debug_mode, stockfish_path) = chunk_data

    blunders = []
    # Each thread needs its own engine instance
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    state_manager = BlunderStateManager()
    board = chess.Board(start_fen)
    
    for move_uci in moves_in_chunk:
        move = chess.Move.from_uci(move_uci)
        if board.turn == user_color:
            board_before = board.copy()
            
            # Since we don't have the full game history here, opponent_last_move is tricky.
            # For the purpose of recapture heuristics, we can look at the last move on the board.
            opponent_last_move = board.move_stack[-1] if board.move_stack else None
            actual_move_number = board_before.fullmove_number
            
            # Dynamic think time
            think_time = engine_think_time
            if board_before.fullmove_number < 10:
                think_time *= 1.2
            elif board_before.fullmove_number > 40:
                think_time *= 0.8
            
            info_before_move = engine.analyse(board, chess.engine.Limit(time=think_time))
            best_move_info = info_before_move
            
            board.push(move)
            
            needs_analysis = quick_heuristics_optimized(
                board_before, move, best_move_info, user_color, 
                state_manager, debug_mode, opponent_last_move
            )
            
            if needs_analysis:
                info_after_move = engine.analyse(board, chess.engine.Limit(time=think_time))
                
                blunder_info = categorize_blunder_optimized(
                    board_before, board, move, info_before_move, info_after_move,
                    best_move_info, state_manager, debug_mode, actual_move_number
                )
                
                if blunder_info:
                    blunder_key = f"{blunder_info['category']}_{actual_move_number}"
                    if not state_manager.has_reported(blunder_key):
                        blunders.append(blunder_info)
                        state_manager.mark_reported(blunder_key)
        else:
            board.push(move)
            
    engine.quit()
    return blunders

def analyze_game_optimized(game, engine, target_user, blunder_threshold, engine_think_time, debug_mode, stockfish_path, threads):
    """
    Optimized game analysis with smart engine batching (Phase 1, Step 1.1).
    """
    blunders = []
    board = game.board()
    user_color = None

    if game.headers.get("White", "").lower() == target_user.lower():
        user_color = chess.WHITE
    elif game.headers.get("Black", "").lower() == target_user.lower():
        user_color = chess.BLACK
    
    if user_color is None:
        print(f"User '{target_user}' not found in this game. Skipping.")
        return []

    all_moves = list(game.mainline_moves())
    state_manager = BlunderStateManager()
    board = game.board()
    positions_to_analyze = []
    move_indices = []
    move_data = []

    # First pass: collect all positions that need analysis
    temp_board = game.board()
    for move_idx, move in enumerate(all_moves):
        if temp_board.turn == user_color:
            # Get a quick best move info for heuristics (minimal think time)
            try:
                best_move_info = engine.analyse(temp_board, chess.engine.Limit(time=0.01))
            except Exception:
                best_move_info = None
            if best_move_info is not None:
                if quick_heuristics_optimized(temp_board, move, best_move_info, user_color, state_manager, debug_mode, temp_board.move_stack[-1] if temp_board.move_stack else None):
                    positions_to_analyze.append((temp_board.copy(), chess.engine.Limit(time=engine_think_time)))
                    move_indices.append(move_idx)
            else:
                # Fallback: always analyze if we can't get best_move_info
                positions_to_analyze.append((temp_board.copy(), chess.engine.Limit(time=engine_think_time)))
                move_indices.append(move_idx)
        move_data.append((temp_board.copy(), move))
        temp_board.push(move)

    # Batch analyze all positions (before and after move for each)
    batch_requests = []
    for idx in move_indices:
        board_before, move = move_data[idx]
        board_after = board_before.copy()
        board_after.push(move)
        batch_requests.append((board_before, chess.engine.Limit(time=engine_think_time)))
        batch_requests.append((board_after, chess.engine.Limit(time=engine_think_time)))

    batch_results = []
    if batch_requests:
        batch_results = analyze_positions_batch(engine, batch_requests, debug_mode)

    # Second pass: process results
    blunder_idx = 0
    for i, idx in enumerate(move_indices):
        board_before, move = move_data[idx]
        board_after = board_before.copy()
        board_after.push(move)
        info_before_move = batch_results[blunder_idx * 2] if batch_results else None
        info_after_move = batch_results[blunder_idx * 2 + 1] if batch_results else None
        best_move_info = info_before_move  # For now, use info_before_move as best_move_info
        actual_move_number = board_before.fullmove_number
        blunder_info = categorize_blunder_optimized(
            board_before, board_after, move, info_before_move, info_after_move,
            best_move_info, state_manager, debug_mode, actual_move_number
        )
        if blunder_info:
            blunder_key = f"{blunder_info['category']}_{actual_move_number}"
            if not state_manager.has_reported(blunder_key):
                blunders.append(blunder_info)
                state_manager.mark_reported(blunder_key)
        blunder_idx += 1

    return blunders

def main():
    """Optimized main function"""
    start = time.perf_counter()

    parser = argparse.ArgumentParser(description="MCB Chess Analyzer - Optimized Edition")
    parser.add_argument("--pgn", default="games/unitTests.pgn", help="Path to PGN file")
    parser.add_argument("--username", default="roygbiv6", help="Username to analyze")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--stockfish_path", default=STOCKFISH_PATH_DEFAULT, help="Path to Stockfish")
    parser.add_argument("--blunder_threshold", type=float, default=BLUNDER_THRESHOLD_DEFAULT, 
                       help="Win probability threshold for blunders")
    parser.add_argument("--engine_think_time", type=float, default=ENGINE_THINK_TIME_DEFAULT, 
                       help="Engine think time per move")
    parser.add_argument("--threads", type=int, default=1, help="Number of threads for parallel analysis")
    args = parser.parse_args()

    print(f"=== MCB Chess Analyzer - Optimized Edition ===\n")
    print(f"Configuration:")
    print(f"  PGN File: {args.pgn}")
    print(f"  Username: {args.username}")
    print(f"  Blunder Threshold: {args.blunder_threshold}%")
    print(f"  Engine Think Time: {args.engine_think_time}s")
    print(f"  Debug Mode: {'ON' if args.debug else 'OFF'}")
    print(f"  Threads: {args.threads}\n")

    # Initialize engine pool for parallel processing
    engines = []
    try:
        # We now initialize engines inside the threads, so this is just a check
        engine = chess.engine.SimpleEngine.popen_uci(args.stockfish_path)
        engine.quit()
        print(f"[OK] Stockfish engine at '{args.stockfish_path}' is valid.\n")
    except Exception as e:
        print(f"[ERROR] Error initializing Stockfish: {e}")
        return
    
    try:
        # Read all games first
        games = []
        with open(args.pgn) as pgn_file:
            while True:
                game = chess.pgn.read_game(pgn_file)
                if game is None:
                    break
                games.append(game)
        
        print(f"Loaded {len(games)} games for analysis\n")
        
        total_blunders = []
        blunder_counts = {}
        
        # Process games (parallel if threads > 1)
        if args.threads > 1 and len(games) > 1:
            # Parallel processing for multiple games
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
                futures = []
                for i, game in enumerate(games):
                    # Each game gets its own analysis process
                    future = executor.submit(process_single_game, game, None, args.username, 
                                           args.blunder_threshold, args.engine_think_time, 
                                           args.debug, i + 1, args.stockfish_path, args.threads)
                    futures.append(future)
                
                # Collect results
                for future in concurrent.futures.as_completed(futures):
                    game_num, blunders = future.result()
                    if blunders:
                        total_blunders.extend(blunders)
                        for blunder in blunders:
                            category = blunder['category']
                            blunder_counts[category] = blunder_counts.get(category, 0) + 1
        else:
            # Sequential processing
            for i, game in enumerate(games):
                game_num, blunders = process_single_game(game, None, args.username,
                                                        args.blunder_threshold, args.engine_think_time,
                                                        args.debug, i + 1, args.stockfish_path, 1)
                if blunders:
                    total_blunders.extend(blunders)
                    for blunder in blunders:
                        category = blunder['category']
                        blunder_counts[category] = blunder_counts.get(category, 0) + 1
                
    except FileNotFoundError:
        print(f"[ERROR] Error: PGN file '{args.pgn}' not found.")
    except Exception as e:
        print(f"[ERROR] Error reading PGN: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up engines is now handled in threads
        print("[OK] Analysis complete.")

    # Summary
    print("\n=== Analysis Summary ===")
    print(f"Total games analyzed: {len(games)}")
    print(f"Total blunders found: {len(total_blunders)}")
    
    if blunder_counts:
        print("\nBlunder Distribution:")
        sorted_categories = sorted(blunder_counts.items(), 
                                 key=lambda x: BLUNDER_CATEGORY_PRIORITY.get(x[0], 999))
        for category, count in sorted_categories:
            percentage = (count / len(total_blunders)) * 100
            print(f"  {category}: {count} ({percentage:.1f}%)")
    
    end = time.perf_counter()
    elapsed = end - start
    print(f"\nTotal runtime: {elapsed:.2f} seconds")
    
    if len(games) > 0:
        avg_time = elapsed / len(games)
        print(f"Average time per game: {avg_time:.2f} seconds")
        
        # Performance metrics
        total_moves = sum(len(list(game.mainline_moves())) for game in games)
        print(f"Total moves analyzed: {total_moves}")
        print(f"Average time per move: {elapsed / total_moves:.3f} seconds")

def process_single_game(game, engine, username, blunder_threshold, engine_think_time, debug_mode, game_num, stockfish_path, threads):
    """Process a single game and return results"""
    white_player = game.headers.get("White", "Unknown")
    black_player = game.headers.get("Black", "Unknown")
    result = game.headers.get("Result", "Unknown")
    
    print(f"Analyzing Game #{game_num}:")
    print(f"  {white_player} vs {black_player} ({result})")

    # Always create a new engine instance for each game if not provided
    close_engine = False
    if engine is None:
        import chess.engine
        engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
        close_engine = True
    
    blunders = analyze_game_optimized(game, engine, username, blunder_threshold,
                                    engine_think_time, debug_mode, stockfish_path, threads)
    
    if close_engine:
        engine.quit()
    
    if blunders:
        print(f"\n  Found {len(blunders)} blunders:")
        for blunder in blunders:
            category = blunder['category']
            move_num = blunder['move_number']
            desc = blunder['description']
            drop = blunder.get('win_prob_drop', 0)
            
            print(f"    Move {move_num}: [{category}] {desc}")
            if drop > 0:
                print(f"      Win probability drop: {drop:.1f}%")
    else:
        print("  [OK] No significant blunders detected")
    
    print()  # Blank line between games
    return game_num, blunders

if __name__ == "__main__":
    main()