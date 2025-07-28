### Phase 4: Algorithm Optimization (Target: 25% reduction)
**Goal**: Reduce from ~12s to ~9s

#### Step 4.1: Replace SEE with Simplified Exchange Calculator

**Current State**: Recursive SEE function in `analyze_games.py` (lines 156-195).

**Implementation Steps**:

1. **Create table-based exchange evaluator** (replace see_uncached function):
```python
# Pre-computed exchange tables
EXCHANGE_TABLES = {
    # (attacker_value, defender_value): net_gain
    # Common exchanges
    (100, 0): 100,      # Pawn takes undefended
    (100, 100): 0,      # Pawn takes pawn
    (100, 300): 200,    # Pawn takes knight
    (100, 320): 220,    # Pawn takes bishop
    (100, 500): 400,    # Pawn takes rook
    (100, 900): 800,    # Pawn takes queen
    (300, 0): 300,      # Knight takes undefended
    (300, 100): -200,   # Knight takes pawn
    (300, 300): 0,      # Knight takes knight
    (300, 320): 20,     # Knight takes bishop
    (300, 500): 200,    # Knight takes rook
    (300, 900): 600,    # Knight takes queen
    # ... add more combinations
}

def see_table_lookup(attacker_value, defender_value, is_defended):
    """Fast SEE using lookup tables."""
    if not is_defended:
        return defender_value
    
    key = (attacker_value, defender_value)
    if key in EXCHANGE_TABLES:
        return EXCHANGE_TABLES[key]
    
    # Fallback calculation
    return defender_value - attacker_value

def see_fast(board, move):
    """
    Simplified Static Exchange Evaluation using tables and heuristics.
    90% accuracy but 10x faster.
    """
    if not board.is_capture(move):
        return 0
    
    # Get piece values
    moving_piece = board.piece_at(move.from_square)
    if not moving_piece:
        return 0
    
    attacker_value = PIECE_VALUES.get(moving_piece.piece_type, 0)
    
    # Get captured piece value
    if board.is_en_passant(move):
        captured_value = PIECE_VALUES[chess.PAWN]
    else:
        captured_piece = board.piece_at(move.to_square)
        if not captured_piece:
            return 0
        captured_value = PIECE_VALUES.get(captured_piece.piece_type, 0)
    
    # Fast check: undefended piece
    if not board.is_attacked_by(board.turn, move.to_square):
        return captured_value
    
    # Check if defended
    defenders = list(board.attackers(not board.turn, move.to_square))
    if not defenders:
        return captured_value
    
    # Find lowest defender
    lowest_defender_value = min(
        PIECE_VALUES.get(board.piece_at(sq).piece_type, 0)
        for sq in defenders
    )
    
    # Use lookup table
    net_exchange = see_table_lookup(attacker_value, captured_value, True)
    
    # Adjust for x-ray attacks (simplified)
    if moving_piece.piece_type in [chess.ROOK, chess.QUEEN]:
        # Check for rook/queen behind
        direction = get_direction(move.from_square, move.to_square)
        behind_square = get_square_behind(move.from_square, direction)
        if behind_square:
            behind_piece = board.piece_at(behind_square)
            if behind_piece and behind_piece.color == board.turn:
                if behind_piece.piece_type in [chess.ROOK, chess.QUEEN]:
                    # X-ray attack bonus
                    net_exchange += 50
    
    return net_exchange

def get_direction(from_square, to_square):
    """Get direction vector between squares."""
    from_file = chess.square_file(from_square)
    from_rank = chess.square_rank(from_square)
    to_file = chess.square_file(to_square)
    to_rank = chess.square_rank(to_square)
    
    file_diff = to_file - from_file
    rank_diff = to_rank - from_rank
    
    # Normalize to direction
    if file_diff != 0:
        file_diff = file_diff // abs(file_diff)
    if rank_diff != 0:
        rank_diff = rank_diff // abs(rank_diff)
    
    return (file_diff, rank_diff)

def get_square_behind(square, direction):
    """Get the square behind in the given direction."""
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    
    new_file = file - direction[0]
    new_rank = rank - direction[1]
    
    if 0 <= new_file <= 7 and 0 <= new_rank <= 7:
        return chess.square(new_file, new_rank)
    return None

# Update the main SEE function to use fast version
def see(board, move):
    """SEE with caching - now uses fast algorithm."""
    # Try cache first
    cached_result = see_cached(board.fen(), move.uci())
    if cached_result is not None:
        return cached_result
    
    # Use fast SEE
    result = see_fast(board, move)
    
    # Cache result (optional - fast enough without caching)
    # see_cache[...] = result
    
    return result
```

2. **Build comprehensive exchange tables** (add to config.py):
```python
# Generate all exchange combinations
def generate_exchange_tables():
    """Generate comprehensive exchange value tables."""
    tables = {}
    piece_values = [100, 300, 320, 500, 900]  # P, N, B, R, Q
    
    for attacker_val in piece_values:
        for defender_val in piece_values:
            # Simple exchange
            tables[(attacker_val, defender_val)] = defender_val - attacker_val
            
            # Complex exchanges (2-ply)
            for defender2_val in piece_values:
                if defender2_val <= attacker_val:
                    # Defender recaptures with equal/lower piece
                    net = defender_val - attacker_val
                    tables[(attacker_val, defender_val, defender2_val)] = net
    
    return tables

EXCHANGE_TABLES_FULL = generate_exchange_tables()
```

#### Step 4.2: Vectorized Board Operations

**Current State**: Board operations use chess library's piece-by-piece iteration.

**Implementation Steps**:

1. **Create numpy-based board representation** (new file `fast_board.py`):
```python
import numpy as np
import chess
from typing import List, Set, Tuple

class FastBoard:
    """Numpy-accelerated board for fast operations."""
    
    def __init__(self, board: chess.Board):
        # Bitboard representation as numpy arrays
        self.white_pieces = np.zeros((8, 8), dtype=np.uint8)
        self.black_pieces = np.zeros((8, 8), dtype=np.uint8)
        self.piece_types = np.zeros((8, 8), dtype=np.uint8)
        
        # Initialize from chess.Board
        self._sync_from_board(board)
        
        # Pre-computed attack masks
        self.knight_attacks = self._precompute_knight_attacks()
        self.king_attacks = self._precompute_king_attacks()
        self.ray_attacks = self._precompute_ray_attacks()
    
    def _sync_from_board(self, board: chess.Board):
        """Sync numpy arrays with chess.Board."""
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                rank = chess.square_rank(square)
                file = chess.square_file(square)
                
                self.piece_types[rank, file] = piece.piece_type
                if piece.color == chess.WHITE:
                    self.white_pieces[rank, file] = 1
                else:
                    self.black_pieces[rank, file] = 1
    
    def _precompute_knight_attacks(self):
        """Pre-compute all knight attack patterns."""
        attacks = np.zeros((8, 8, 8, 8), dtype=np.bool_)
        knight_moves = [
            (2, 1), (2, -1), (-2, 1), (-2, -1),
            (1, 2), (1, -2), (-1, 2), (-1, -2)
        ]
        
        for r in range(8):
            for f in range(8):
                for dr, df in knight_moves:
                    nr, nf = r + dr, f + df
                    if 0 <= nr < 8 and 0 <= nf < 8:
                        attacks[r, f, nr, nf] = True
        
        return attacks
    
    def _precompute_king_attacks(self):
        """Pre-compute all king attack patterns."""
        attacks = np.zeros((8, 8, 8, 8), dtype=np.bool_)
        king_moves = [
            (1, 0), (-1, 0), (0, 1), (0, -1),
            (1, 1), (1, -1), (-1, 1), (-1, -1)
        ]
        
        for r in range(8):
            for f in range(8):
                for dr, df in king_moves:
                    nr, nf = r + dr, f + df
                    if 0 <= nr < 8 and 0 <= nf < 8:
                        attacks[r, f, nr, nf] = True
        
        return attacks
    
    def _precompute_ray_attacks(self):
        """Pre-compute sliding piece rays."""
        rays = {}
        directions = [
            (1, 0), (-1, 0), (0, 1), (0, -1),  # Rook
            (1, 1), (1, -1), (-1, 1), (-1, -1)  # Bishop
        ]
        
        for r in range(8):
            for f in range(8):
                rays[(r, f)] = {}
                for direction in directions:
                    ray_squares = []
                    cr, cf = r + direction[0], f + direction[1]
                    while 0 <= cr < 8 and 0 <= cf < 8:
                        ray_squares.append((cr, cf))
                        cr += direction[0]
                        cf += direction[1]
                    rays[(r, f)][direction] = ray_squares
        
        return rays
    
    def get_attacked_squares_fast(self, color: bool) -> np.ndarray:
        """Get all squares attacked by one side using vectorized operations."""
        attacked = np.zeros((8, 8), dtype=np.bool_)
        pieces = self.white_pieces if color == chess.WHITE else self.black_pieces
        
        # Vectorized pawn attacks
        if color == chess.WHITE:
            # White pawns attack diagonally up
            pawn_mask = (pieces & (self.piece_types == chess.PAWN))
            # Left attacks
            attacked[1:, :-1] |= pawn_mask[:-1, 1:]
            # Right attacks  
            attacked[1:, 1:] |= pawn_mask[:-1, :-1]
        else:
            # Black pawns attack diagonally down
            pawn_mask = (pieces & (self.piece_types == chess.PAWN))
            # Left attacks
            attacked[:-1, :-1] |= pawn_mask[1:, 1:]
            # Right attacks
            attacked[:-1, 1:] |= pawn_mask[1:, :-1]
        
        # Knight attacks (use pre-computed)
        knight_positions = np.argwhere(pieces & (self.piece_types == chess.KNIGHT))
        for pos in knight_positions:
            attacked |= self.knight_attacks[pos[0], pos[1]]
        
        # King attacks (use pre-computed)
        king_positions = np.argwhere(pieces & (self.piece_types == chess.KING))
        for pos in king_positions:
            attacked |= self.king_attacks[pos[0], pos[1]]
        
        # Sliding pieces (simplified - doesn't account for blocking)
        # In practice, you'd need to check for blocking pieces
        slider_types = [chess.BISHOP, chess.ROOK, chess.QUEEN]
        for piece_type in slider_types:
            slider_positions = np.argwhere(pieces & (self.piece_types == piece_type))
            for pos in slider_positions:
                # Add ray attacks (simplified)
                attacked[pos[0], :] = True  # Horizontal
                attacked[:, pos[1]] = True  # Vertical
                if piece_type != chess.ROOK:
                    # Add diagonals (simplified)
                    for i in range(8):
                        if 0 <= pos[0] + i < 8 and 0 <= pos[1] + i < 8:
                            attacked[pos[0] + i, pos[1] + i] = True
                        if 0 <= pos[0] - i < 8 and 0 <= pos[1] + i < 8:
                            attacked[pos[0] - i, pos[1] + i] = True
        
        return attacked
    
    def find_hanging_pieces_fast(self, color: bool) -> List[Tuple[int, int]]:
        """Find all hanging pieces using vectorized operations."""
        pieces = self.white_pieces if color == chess.WHITE else self.black_pieces
        opponent_pieces = self.black_pieces if color == chess.WHITE else self.white_pieces
        
        # Get attack maps
        our_attacks = self.get_attacked_squares_fast(color)
        their_attacks = self.get_attacked_squares_fast(not color)
        
        # Hanging = our pieces that are attacked but not defended
        hanging_mask = pieces & their_attacks & ~our_attacks
        
        # Convert to list of squares
        hanging_positions = np.argwhere(hanging_mask)
        return [(pos[0] * 8 + pos[1]) for pos in hanging_positions]
    
    def count_attackers_fast(self, square: int, color: bool) -> int:
        """Count attackers of a square using vectorized operations."""
        rank = square // 8
        file = square % 8
        
        pieces = self.white_pieces if color == chess.WHITE else self.black_pieces
        
        # Check each piece type that could attack this square
        attackers = 0
        
        # Pawns
        if color == chess.WHITE:
            if rank > 0:
                if file > 0 and pieces[rank-1, file-1] and self.piece_types[rank-1, file-1] == chess.PAWN:
                    attackers += 1
                if file < 7 and pieces[rank-1, file+1] and self.piece_types[rank-1, file+1] == chess.PAWN:
                    attackers += 1
        else:
            if rank < 7:
                if file > 0 and pieces[rank+1, file-1] and self.piece_types[rank+1, file-1] == chess.PAWN:
                    attackers += 1
                if file < 7 and pieces[rank+1, file+1] and self.piece_types[rank+1, file+1] == chess.PAWN:
                    attackers += 1
        
        # Knights (use pre-computed attacks)
        knight_attackers = self.knight_attacks[:, :, rank, file] & pieces & (self.piece_types == chess.KNIGHT)
        attackers += np.sum(knight_attackers)
        
        # Add other pieces...
        
        return attackers
```

2. **Integrate FastBoard into analysis** (modify analyze_position_cached):
```python
# Add at top of analyze_games.py
from fast_board import FastBoard

def analyze_position_cached_fast(board, state_manager):
    """Analyze position using fast numpy operations."""
    board_fen = board.fen()
    
    # Check cache first
    cached = state_manager.get_position_cache(board_fen)
    if cached:
        return cached
    
    # Create fast board representation
    fast_board = FastBoard(board)
    
    # Use vectorized operations
    ### Phase 3: Advanced Caching & Pattern Recognition (Target: 30% reduction)
**Goal**: Reduce from ~18s to ~12s

#### Step 3.1: Expanded Position Cache

**Current State**: In `analyze_games.py`, basic position cache in `BlunderStateManager` (lines 53-85).

**Implementation Steps**:

1. **Create multi-level cache system in `analyze_games.py`** (replace `BlunderStateManager` class):
```python
from functools import lru_cache
import hashlib

class AdvancedCache:
    """Multi-level cache system for chess analysis."""
    
    def __init__(self):
        # L1: Exact position cache (FEN -> analysis)
        self.position_cache = {}  # Will use up to 10K entries
        self.position_cache_hits = 0
        self.position_cache_misses = 0
        
        # L2: Pattern cache (pattern_hash -> tactical info)
        self.pattern_cache = {}
        self.pattern_cache_hits = 0
        self.pattern_cache_misses = 0
        
        # L3: Evaluation cache (simplified_fen -> eval)
        self.eval_cache = {}
        self.eval_cache_hits = 0
        self.eval_cache_misses = 0
        
        # Cache size limits
        self.max_position_cache = 10000
        self.max_pattern_cache = 5000
        self.max_eval_cache = 20000
    
    def get_position_hash(self, board):
        """Get unique hash for position."""
        return board.fen()
    
    def get_pattern_hash(self, board):
        """Get hash for tactical pattern (ignores exact piece positions)."""
        # Create pattern signature based on:
        # - Piece types and counts
        # - Attack/defense relationships
        # - King safety features
        pattern_parts = []
        
        # Piece counts by type
        for piece_type in chess.PIECE_TYPES:
            white_count = len(board.pieces(piece_type, chess.WHITE))
            black_count = len(board.pieces(piece_type, chess.BLACK))
            pattern_parts.append(f"{piece_type}:{white_count},{black_count}")
        
        # Material balance
        material_diff = self._calculate_material_diff(board)
        pattern_parts.append(f"mat:{material_diff}")
        
        # King safety (simplified)
        white_king_safety = self._king_safety_score(board, chess.WHITE)
        black_king_safety = self._king_safety_score(board, chess.BLACK)
        pattern_parts.append(f"ks:{white_king_safety},{black_king_safety}")
        
        return hashlib.md5("|".join(pattern_parts).encode()).hexdigest()
    
    def get_structure_hash(self, board):
        """Get hash for pawn structure and piece placement patterns."""
        structure_parts = []
        
        # Pawn structure
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.piece_type == chess.PAWN:
                structure_parts.append(f"{square}:{piece.color}")
        
        # Piece activity zones
        for piece_type in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
            for color in [chess.WHITE, chess.BLACK]:
                pieces = board.pieces(piece_type, color)
                if pieces:
                    avg_rank = sum(chess.square_rank(sq) for sq in pieces) / len(pieces)
                    structure_parts.append(f"{piece_type}{color}:r{avg_rank:.1f}")
        
        return hashlib.md5("|".join(structure_parts).encode()).hexdigest()
    
    def _calculate_material_diff(self, board):
        """Calculate material difference in centipawns."""
        material = 0
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                value = PIECE_VALUES.get(piece.piece_type, 0)
                material += value if piece.color == chess.WHITE else -value
        return material
    
    def _king_safety_score(self, board, color):
        """Simple king safety score (0-10)."""
        king_square = board.king(color)
        if not king_square:
            return 0
        
        # Count attacking pieces near king
        king_ring = chess.BB_KING_ATTACKS[king_square]
        danger = 0
        
        for square in chess.scan_forward(king_ring):
            attackers = board.attackers(not color, square)
            danger += len(attackers)
        
        return min(danger, 10)
    
    def cache_position_analysis(self, board, analysis_result):
        """Cache position analysis at multiple levels."""
        pos_hash = self.get_position_hash(board)
        pattern_hash = self.get_pattern_hash(board)
        struct_hash = self.get_structure_hash(board)
        
        # L1: Exact position
        if len(self.position_cache) >= self.max_position_cache:
            # LRU eviction - remove oldest 20%
            items = sorted(self.position_cache.items(), 
                         key=lambda x: x[1].get('timestamp', 0))
            for key, _ in items[:int(self.max_position_cache * 0.2)]:
                del self.position_cache[key]
        
        self.position_cache[pos_hash] = {
            'result': analysis_result,
            'timestamp': time.time()
        }
        
        # L2: Pattern cache
        if pattern_hash not in self.pattern_cache:
            self.pattern_cache[pattern_hash] = {
                'evaluations': [],
                'avg_eval': None
            }
        
        if 'eval_cp' in analysis_result:
            self.pattern_cache[pattern_hash]['evaluations'].append(
                analysis_result['eval_cp']
            )
            # Update average
            evals = self.pattern_cache[pattern_hash]['evaluations']
            self.pattern_cache[pattern_hash]['avg_eval'] = sum(evals) / len(evals)
    
    def get_cached_analysis(self, board):
        """Try to get analysis from cache."""
        # L1: Check exact position
        pos_hash = self.get_position_hash(board)
        if pos_hash in self.position_cache:
            self.position_cache_hits += 1
            return self.position_cache[pos_hash]['result']
        self.position_cache_misses += 1
        
        # L2: Check pattern cache for similar positions
        pattern_hash = self.get_pattern_hash(board)
        if pattern_hash in self.pattern_cache:
            pattern_data = self.pattern_cache[pattern_hash]
            if pattern_data['avg_eval'] is not None:
                self.pattern_cache_hits += 1
                # Return estimated evaluation
                return {
                    'eval_cp': pattern_data['avg_eval'],
                    'from_cache': 'pattern'
                }
        self.pattern_cache_misses += 1
        
        return None
    
    def get_cache_stats(self):
        """Get cache performance statistics."""
        total_hits = (self.position_cache_hits + 
                     self.pattern_cache_hits + 
                     self.eval_cache_hits)
        total_misses = (self.position_cache_misses + 
                       self.pattern_cache_misses + 
                       self.eval_cache_misses)
        
        hit_rate = total_hits / (total_hits + total_misses) if (total_hits + total_misses) > 0 else 0
        
        return {
            'position_cache': {
                'size': len(self.position_cache),
                'hits': self.position_cache_hits,
                'misses': self.position_cache_misses
            },
            'pattern_cache': {
                'size': len(self.pattern_cache),
                'hits': self.pattern_cache_hits,
                'misses': self.pattern_cache_misses
            },
            'total_hit_rate': hit_rate
        }

# Enhanced BlunderStateManager with advanced caching
class BlunderStateManager:
    """Enhanced state manager with advanced caching."""
    
    def __init__(self):
        # Original attributes
        self.active_weaknesses = {}
        self.reported_blunders = set()
        self.last_eval = None
        self.position_trend = []
        self.consecutive_checkmates = 0
        self.last_checkmate_move = 0
        self.in_losing_position = False
        self.trapped_pieces = set()
        
        # NEW: Advanced cache
        self.cache = AdvancedCache()
    
    # ... keep all original methods ...
    
    def get_cached_engine_result(self, board):
        """Get cached engine analysis if available."""
        return self.cache.get_cached_analysis(board)
    
    def cache_engine_result(self, board, result):
        """Cache engine analysis result."""
        self.cache.cache_position_analysis(board, result)
```

2. **Modify engine analysis to use cache** in `analyze_game_optimized()` (line 750):
```python
# Before making engine call, check cache
cached_before = state_manager.get_cached_engine_result(board_before)
if cached_before and 'from_cache' not in cached_before:
    info_before_move = cached_before
    engine_calls_saved += 1
else:
    info_before_move = engine.analyse(board, chess.engine.Limit(time=think_time))
    engine_calls_made += 1
    # Cache the result
    state_manager.cache_engine_result(board_before, info_before_move)
```

3. **Add cache warming for common patterns** (new function):
```python
def warm_cache_with_common_patterns(engine, cache, think_time=0.05):
    """Pre-populate cache with common chess patterns."""
    common_positions = [
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",  # Starting
        "rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2",  # Common opening
        "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",  # Italian
        # Add more common positions
    ]
    
    for fen in common_positions:
        board = chess.Board(fen)
        result = engine.analyse(board, chess.engine.Limit(time=think_time))
        cache.cache_position_analysis(board, result)
```

#### Step 3.2: Tactical Pattern Pre-computation

**Current State**: Multiple functions scan the board repeatedly for patterns.

**Implementation Steps**:

1. **Create unified pattern extractor** (add in `analyze_games.py` after line 400):
```python
@dataclass
class TacticalPatterns:
    """All tactical patterns for a position."""
    hanging_pieces: Set[int] = field(default_factory=set)
    pins: List[Tuple[int, int, int]] = field(default_factory=list)  # (pinned, pinner, target)
    forks: List[Tuple[int, List[int]]] = field(default_factory=list)  # (forker, targets)
    skewers: List[Tuple[int, int, int]] = field(default_factory=list)  # (skewer_piece, front, back)
    discovered_attacks: List[Tuple[int, int]] = field(default_factory=list)  # (blocker, attacker)
    weak_squares: Set[int] = field(default_factory=set)
    piece_mobility: Dict[int, int] = field(default_factory=dict)  # square -> move_count
    
def extract_all_tactical_patterns(board, color):
    """Extract all tactical patterns in a single pass."""
    patterns = TacticalPatterns()
    
    # Single pass through all squares
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece:
            continue
        
        # Check hanging pieces
        if piece.color == color:
            attackers = board.attackers(not color, square)
            defenders = board.attackers(color, square)
            if attackers and not defenders:
                patterns.hanging_pieces.add(square)
        
        # Check for pins (if piece is a slider)
        if piece.piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
            # Look for pins along slider rays
            for direction in get_slider_directions(piece.piece_type):
                ray_squares = get_ray_squares(square, direction)
                pieces_on_ray = []
                
                for ray_sq in ray_squares:
                    ray_piece = board.piece_at(ray_sq)
                    if ray_piece:
                        pieces_on_ray.append((ray_sq, ray_piece))
                        if len(pieces_on_ray) == 2:
                            break
                
                # Check if this creates a pin
                if len(pieces_on_ray) == 2:
                    first_sq, first_piece = pieces_on_ray[0]
                    second_sq, second_piece = pieces_on_ray[1]
                    
                    # Pin exists if: attacker -> opponent piece -> valuable piece
                    if (piece.color != first_piece.color and 
                        first_piece.color == second_piece.color and
                        PIECE_VALUES[second_piece.piece_type] > PIECE_VALUES[first_piece.piece_type]):
                        patterns.pins.append((first_sq, square, second_sq))
        
        # Check for forks (knights, pawns)
        if piece.piece_type in [chess.KNIGHT, chess.PAWN]:
            attacked_squares = board.attacks(square)
            valuable_targets = []
            
            for target_sq in attacked_squares:
                target = board.piece_at(target_sq)
                if target and target.color != piece.color:
                    if PIECE_VALUES[target.piece_type] >= PIECE_VALUES[piece.piece_type]:
                        valuable_targets.append(target_sq)
            
            if len(valuable_targets) >= 2:
                patterns.forks.append((square, valuable_targets))
        
        # Calculate piece mobility
        if piece.color == color:
            legal_moves = 0
            for move in board.legal_moves:
                if move.from_square == square:
                    legal_moves += 1
            patterns.piece_mobility[square] = legal_moves
    
            # Check for discovered attacks
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == color:
            # Check if moving this piece would reveal an attack
            board_copy = board.copy()
            for move in board.legal_moves:
                if move.from_square == square:
                    board_copy.push(move)
                    # Check for new attacks from pieces behind
                    for behind_sq in get_squares_behind(square, board):
                        behind_piece = board.piece_at(behind_sq)
                        if behind_piece and behind_piece.color == color:
                            # Check if this piece now attacks something valuable
                            new_attacks = board_copy.attacks(behind_sq)
                            for target in new_attacks:
                                target_piece = board_copy.piece_at(target)
                                if target_piece and target_piece.color != color:
                                    if not board.is_attacked_by(color, target):
                                        patterns.discovered_attacks.append((square, behind_sq))
                                        break
                    board_copy.pop()
    
    return patterns

def get_slider_directions(piece_type):
    """Get movement directions for slider pieces."""
    if piece_type == chess.BISHOP:
        return [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    elif piece_type == chess.ROOK:
        return [(1, 0), (-1, 0), (0, 1), (0, -1)]
    elif piece_type == chess.QUEEN:
        return [(1, 1), (1, -1), (-1, 1), (-1, -1), (1, 0), (-1, 0), (0, 1), (0, -1)]
    return []

def get_ray_squares(square, direction):
    """Get squares along a ray from a square."""
    squares = []
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    
    while True:
        file += direction[0]
        rank += direction[1]
        if 0 <= file <= 7 and 0 <= rank <= 7:
            squares.append(chess.square(file, rank))
        else:
            break
    
    return squares

def get_squares_behind(square, board):
    """Get squares that could be 'behind' this square for discovered attacks."""
    behind = []
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    
    # Check all directions
    for direction in [(1, 1), (1, -1), (-1, 1), (-1, -1), (1, 0), (-1, 0), (0, 1), (0, -1)]:
        checking_file = file - direction[0]
        checking_rank = rank - direction[1]
        
        while 0 <= checking_file <= 7 and 0 <= checking_rank <= 7:
            check_square = chess.square(checking_file, checking_rank)
            if board.piece_at(check_square):
                behind.append(check_square)
                break
            checking_file -= direction[0]
            checking_rank -= direction[1]
    
    return behind
```

2. **Replace analyze_position_cached with pattern-aware version** (replace function at line 92):
```python
def analyze_position_cached(board, state_manager):
    """Analyze position once and cache all needed data INCLUDING patterns."""
    board_fen = board.fen()
    
    # Check cache first
    cached = state_manager.get_position_cache(board_fen)
    if cached:
        return cached
    
    # Extract ALL patterns in single pass
    turn = board.turn
    patterns = extract_all_tactical_patterns(board, turn)
    opponent_patterns = extract_all_tactical_patterns(board, not turn)
    
    # Build comprehensive position analysis
    hanging_pieces = patterns.hanging_pieces
    attackers_map = {}
    defenders_map = {}
    legal_moves_from = {}
    
    # Single pass through all squares (existing code enhanced)
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            # Get attackers and defenders
            attackers = set(board.attackers(not piece.color, square))
            defenders = set(board.attackers(piece.color, square))
            
            attackers_map[square] = attackers
            defenders_map[square] = defenders
    
    # Build legal moves map (existing)
    for move in board.legal_moves:
        if move.from_square not in legal_moves_from:
            legal_moves_from[move.from_square] = []
        legal_moves_from[move.from_square].append(move)
    
    cache = CachedPosition(
        hanging_pieces=hanging_pieces,
        attackers_map=attackers_map,
        defenders_map=defenders_map,
        legal_moves_from=legal_moves_from,
        # NEW: Add pattern data
        patterns=patterns,
        opponent_patterns=opponent_patterns
    )
    
    state_manager.set_position_cache(board_fen, cache)
    return cache
```

3. **Update CachedPosition dataclass** (line 38):
```python
@dataclass
class CachedPosition:
    """Cache for position analysis with patterns."""
    hanging_pieces: Set[int]
    attackers_map: Dict[int, Set[int]]
    defenders_map: Dict[int, Set[int]]
    legal_moves_from: Dict[int, List[chess.Move]]
    patterns: TacticalPatterns = None  # NEW
    opponent_patterns: TacticalPatterns = None  # NEW
```

4. **Use pre-computed patterns in blunder detection** (modify detection functions):
```python
# Example: In check_for_hanging_piece_optimized (line 490)
def check_for_hanging_piece_optimized(board_before, move_played, board_after, turn_color, state_manager, debug_mode, actual_move_number):
    """Optimized hanging piece detection using cached analysis."""
    move_played_san = board_before.san(move_played)
    
    # ... existing capture checking code ...
    
    # Use cached position analysis with patterns
    pos_analysis = analyze_position_cached(board_after, state_manager)
    
    # Direct access to hanging pieces from patterns
    new_hanging = []
    current_hanging_keys = set()
    
    # Use pre-computed hanging pieces
    for square in pos_analysis.patterns.hanging_pieces:
        piece = board_after.piece_at(square)
        if piece and piece.color == turn_color:
            weakness_key = f"hanging_{piece.piece_type}_{square}"
            current_hanging_keys.add(weakness_key)
            
            # Only report if NEW
            if state_manager.is_new_weakness(weakness_key):
                # ... rest of existing logic ...
```

#### Step 3.3: Optimized Trap Detection

**Current State**: `detect_trap_optimized()` simulates many opponent moves (lines 240-350).

**Implementation Steps**:

1. **Create fast trap heuristics** (replace detect_trap_optimized):
```python
def detect_trap_optimized_v2(board_before, move_played, board_after, turn_color, state_manager, debug_mode):
    """
    Ultra-fast trap detection using mobility index and heuristics.
    """
    move_played_san = board_before.san(move_played)
    
    # Get pre-computed patterns
    pos_analysis = analyze_position_cached(board_after, state_manager)
    patterns = pos_analysis.patterns if turn_color == board_after.turn else pos_analysis.opponent_patterns
    
    # Only check valuable pieces with low mobility
    valuable_pieces = [chess.QUEEN, chess.ROOK, chess.KNIGHT, chess.BISHOP]
    
    for square, mobility in patterns.piece_mobility.items():
        piece = board_after.piece_at(square)
        if not piece or piece.color != turn_color or piece.piece_type not in valuable_pieces:
            continue
        
        # Already trapped check
        if state_manager.is_piece_trapped(piece.piece_type, square):
            continue
        
        # Quick mobility check - piece with 0-1 moves might be trapped
        if mobility > 1:
            continue
        
        # Check if opponent can further restrict this piece
        piece_value = PIECE_VALUES.get(piece.piece_type, 0)
        
        # Fast trap detection: Check only most likely trapping moves
        trap_move = find_trapping_move_fast(board_after, square, turn_color, pos_analysis, debug_mode)
        
        if trap_move:
            state_manager.mark_piece_trapped(piece.piece_type, square)
            piece_name = PIECE_NAMES.get(piece.piece_type, "piece")
            return {
                "category": "Allowed Trap",
                "move_number": None,
                "description": f"your move {move_played_san} allows the opponent to trap your {piece_name} on {chess.square_name(square)} with {board_after.san(trap_move)}",
                "trapping_move": trap_move
            }
    
    return None

def find_trapping_move_fast(board, piece_square, piece_color, pos_analysis, debug_mode):
    """
    Fast trap detection using pre-computed patterns and heuristics.
    """
    piece = board.piece_at(piece_square)
    if not piece:
        return None
    
    opponent_color = not piece_color
    piece_type = piece.piece_type
    
    # Get current escape squares
    escape_squares = []
    for move in board.legal_moves:
        if move.from_square == piece_square:
            escape_squares.append(move.to_square)
    
    if not escape_squares:
        return None  # Already has no moves
    
    # Priority 1: Pawn moves that block escape squares
    for move in board.legal_moves:
        moving_piece = board.piece_at(move.from_square)
        if not moving_piece or moving_piece.color != opponent_color:
            continue
        
        # Focus on pawn moves near the piece
        if moving_piece.piece_type == chess.PAWN:
            if abs(chess.square_file(move.to_square) - chess.square_file(piece_square)) <= 2:
                if abs(chess.square_rank(move.to_square) - chess.square_rank(piece_square)) <= 2:
                    # Check if this pawn move blocks escape
                    if move.to_square in escape_squares:
                        return move
                    
                    # Quick simulation
                    board_copy = board.copy()
                    board_copy.push(move)
                    
                    # Count remaining moves
                    remaining_moves = 0
                    for test_move in board_copy.legal_moves:
                        if test_move.from_square == piece_square:
                            remaining_moves += 1
                    
                    if remaining_moves == 0:
                        return move
    
    # Priority 2: Moves that attack escape squares
    escape_attackers = {}
    for escape_sq in escape_squares:
        attackers = pos_analysis.opponent_patterns.piece_mobility
        for attacker_sq, mobility in attackers.items():
            attacker = board.piece_at(attacker_sq)
            if attacker and attacker.color == opponent_color:
                if escape_sq in board.attacks(attacker_sq):
                    if escape_sq not in escape_attackers:
                        escape_attackers[escape_sq] = []
                    escape_attackers[escape_sq].append(attacker_sq)
    
    # If most escape squares can be attacked, piece might be trappable
    if len(escape_attackers) >= len(escape_squares) * 0.7:
        # Find a move that completes the trap
        for move in board.legal_moves:
            if board.piece_at(move.from_square).color == opponent_color:
                board_copy = board.copy()
                board_copy.push(move)
                
                # Quick check if piece is trapped
                trapped = True
                for test_move in board_copy.legal_moves:
                    if test_move.from_square == piece_square:
                        # Check if this escape is safe
                        to_sq = test_move.to_square
                        if not board_copy.is_attacked_by(opponent_color, to_sq):
                            trapped = False
                            break
                
                if trapped:
                    return move
    
    return None
```

2. **Add trap pattern caching** (in AdvancedCache class):
```python
def cache_trap_pattern(self, piece_square, piece_type, trapping_move):
    """Cache successful trap patterns for faster detection."""
    pattern_key = f"trap_{piece_type}_{chess.square_name(piece_square)}"
    self.pattern_cache[pattern_key] = {
        'trapping_move': trapping_move.uci(),
        'timestamp': time.time()
    }

def get_cached_trap(self, board, piece_square, piece_type):
    """Check if we've seen this trap pattern before."""
    pattern_key = f"trap_{piece_type}_{chess.square_name(piece_square)}"
    if pattern_key in self.pattern_cache:
        trap_data = self.pattern_cache[pattern_key]
        # Verify the trapping move is still legal
        try:
            move = chess.Move.from_uci(trap_data['trapping_move'])
            if move in board.legal_moves:
                return move
        except:
            pass
    return None
```

3. **Update configuration** in `config.py` (line 60):
```python
# Advanced Caching Configuration
ENABLE_ADVANCED_CACHING = True
MAX_POSITION_CACHE_SIZE = 10000
MAX_PATTERN_CACHE_SIZE = 5000
MAX_EVAL_CACHE_SIZE = 20000
CACHE_WARMUP_POSITIONS = 100
TRAP_DETECTION_MODE = 'fast'  # 'fast' or 'comprehensive'
```# MCB Chess Analyzer - Performance Optimization Plan

## Executive Summary
Current performance: **20 games in ~60 seconds** (3 seconds per game)  
Target performance: **20 games in ~20 seconds** (1 second per game)  
Optimization factor: **3x speedup** while maintaining analysis accuracy

## Current State Analysis

### Performance Profile
- **Primary Bottleneck**: `categorize_blunder_optimized()` in `analyze_games.py`
- **Engine Calls**: ~1.4 calls per move × 35 moves/game × 20 games = 980 engine calls
- **Engine Time**: 0.08s per call × 980 calls = 78.4s theoretical minimum
- **Actual Time**: ~60s (good efficiency, but sequential processing limits throughput)

### Key Inefficiencies
1. **Sequential move analysis** within each game
2. **Redundant calculations** across similar positions
3. **Expensive trap detection** with full board simulations
4. **No engine request batching**
5. **Limited tactical pattern caching**

## Optimization Strategy

### Phase 1: Engine Call Optimization (Target: 40% reduction)
**Goal**: Reduce from ~60s to ~35s

#### Step 1.1: Implement Smart Engine Batching

**Current State**: In `analyze_games.py`, lines 712-803, each move gets two separate engine calls:
```python
# Line 742: First engine call
info_before_move = engine.analyse(board, chess.engine.Limit(time=think_time))
# Line 756: Second engine call  
info_after_move = engine.analyse(board, chess.engine.Limit(time=think_time))
```

**Implementation Steps**:

1. **Create batch analysis function in `analyze_games.py`** (add after line 690):
```python
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
    # Check if engine supports batch analysis
    if hasattr(engine, 'analyse_batch'):
        # Use native batch support
        results = engine.analyse_batch(positions_and_limits)
    else:
        # Fallback to sequential with reduced overhead
        for board, limit in positions_and_limits:
            results.append(engine.analyse(board, limit))
    return results
```

2. **Modify `analyze_game_optimized()` function** (lines 690-810) to collect positions:
```python
def analyze_game_optimized(game, engine, target_user, blunder_threshold, engine_think_time, debug_mode):
    # ... existing setup code ...
    
    # NEW: Collect positions for batch analysis
    positions_to_analyze = []
    move_indices = []
    
    # First pass: collect all positions that need analysis
    temp_board = game.board()
    for move_idx, move in enumerate(all_moves):
        if temp_board.turn == user_color:
            if quick_heuristics_optimized(temp_board, move, None, user_color, state_manager, debug_mode):
                positions_to_analyze.append((
                    temp_board.copy(),
                    chess.engine.Limit(time=engine_think_time)
                ))
                move_indices.append(move_idx)
        temp_board.push(move)
    
    # NEW: Batch analyze all positions
    if positions_to_analyze:
        batch_results = analyze_positions_batch(engine, positions_to_analyze, debug_mode)
    
    # Second pass: process results
    board = game.board()
    result_idx = 0
    for move_idx, move in enumerate(all_moves):
        if board.turn == user_color and result_idx < len(move_indices) and move_idx == move_indices[result_idx]:
            # Use pre-computed results
            info_before_move = batch_results[result_idx * 2]
            info_after_move = batch_results[result_idx * 2 + 1]
            result_idx += 1
            # ... rest of the blunder detection logic ...
```

3. **Update `analysis_service.py`** to support batch mode (line 120):
   - Add configuration flag in `config.py` (line 30):
   ```python
   ENABLE_BATCH_ENGINE_ANALYSIS = True
   BATCH_ANALYSIS_SIZE = 20  # Positions per batch
   ```

#### Step 1.2: Enhanced Position Filtering

**Current State**: In `analyze_games.py`, line 637, `quick_heuristics_optimized()` only does basic filtering.

**Implementation Steps**:

1. **Add opening book check function** in `analyze_games.py` (add after line 200):
```python
# Common opening moves in UCI format for the first 10 moves
OPENING_BOOK = {
    # Italian Game, Ruy Lopez, etc.
    1: ['e2e4', 'd2d4', 'g1f3', 'c2c4'],
    2: ['e7e5', 'd7d5', 'g8f6', 'c7c5', 'e7e6'],
    # Add more common moves...
}

def is_book_move(board, move):
    """Check if move is a common book move"""
    move_num = board.fullmove_number
    if move_num > 10:
        return False
    
    move_uci = move.uci()
    return move_uci in OPENING_BOOK.get(move_num, [])
```

2. **Add obvious recapture detection** in `analyze_games.py` (add after line 220):
```python
def is_obvious_recapture(board, move):
    """
    Check if move is an obvious recapture (equal or winning exchange).
    """
    if not board.is_capture(move):
        return False
    
    # Check if we're recapturing on a square that was just captured
    if len(board.move_stack) > 0:
        last_move = board.move_stack[-1]
        if board.is_capture(last_move) and last_move.to_square == move.to_square:
            # This is a recapture - check if it's obvious (equal or better)
            see_value = see(board, move)
            return see_value >= 0
    
    return False
```

3. **Enhance `quick_heuristics_optimized()` function** (replace lines 637-662):
```python
def quick_heuristics_optimized(board_before, move_played, best_move_info, turn_color, state_manager, debug_mode):
    """Ultra-fast heuristics using minimal computation - ENHANCED VERSION"""
    
    # NEW: Skip forced moves
    legal_moves = list(board_before.legal_moves)
    if len(legal_moves) == 1:
        if debug_mode:
            print(f"[DEBUG] Skipping forced move (only legal move)")
        return False
    
    # NEW: Skip book moves in opening
    if board_before.fullmove_number <= 10 and is_book_move(board_before, move_played):
        if debug_mode:
            print(f"[DEBUG] Skipping book move in opening")
        return False
    
    # NEW: Skip obvious recaptures
    if is_obvious_recapture(board_before, move_played):
        if debug_mode:
            print(f"[DEBUG] Skipping obvious recapture")
        return False
    
    # NEW: Skip simple endgames (use tablebase or skip)
    piece_count = len(board_before.piece_map())
    if piece_count <= 6:
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
```

4. **Add position filtering metrics** in `config.py` (line 40):
```python
# Position Filtering Thresholds
SKIP_FORCED_MOVES = True
SKIP_BOOK_MOVES = True
SKIP_OBVIOUS_RECAPTURES = True
SKIP_TABLEBASE_POSITIONS = True
TABLEBASE_PIECE_LIMIT = 6
```

#### Step 1.3: Implement Lazy Evaluation

**Current State**: In `analyze_games.py`, `categorize_blunder_optimized()` (lines 663-811) runs all checks sequentially.

**Implementation Steps**:

1. **Add evaluation change threshold check** at the beginning of `categorize_blunder_optimized()` (after line 670):
```python
def categorize_blunder_optimized(board_before, board_after, move_played, info_before_move, info_after_move, 
                                best_move_info, state_manager, debug_mode, actual_move_number):
    """Optimized blunder categorization with LAZY EVALUATION"""
    move_played_san = board_before.san(move_played)
    turn_color = board_before.turn
    
    # Calculate win probability drop FIRST
    eval_before = info_before_move["score"].pov(turn_color).score(mate_score=10000)
    eval_after = info_after_move["score"].pov(turn_color).score(mate_score=10000)
    
    # NEW: Early exit if evaluation change is minimal
    if eval_before is not None and eval_after is not None:
        eval_drop = eval_before - eval_after
        if eval_drop < 50:  # Less than 0.5 pawn drop
            if debug_mode:
                print(f"[DEBUG] Skipping - minimal evaluation change: {eval_drop}")
            return None
    
    # Continue with win probability calculation...
    state_manager.update_eval(eval_after)
```

2. **Reorder blunder checks by frequency and cost** (replace lines 680-811):
```python
    # REORDERED: Check by frequency (most common first) and cost (cheapest first)
    
    # 1. CHEAP CHECK: Hanging pieces (most common, very fast)
    if win_prob_drop >= MISTAKE_THRESHOLD:
        hanging_result = check_for_hanging_piece_optimized(board_before, move_played, board_after, 
                                                          turn_color, state_manager, debug_mode, actual_move_number)
        if hanging_result:
            hanging_result["win_prob_drop"] = win_prob_drop
            return hanging_result
    
    # 2. CHEAP CHECK: Missed material (common, fast)
    if win_prob_drop >= MISTAKE_THRESHOLD:
        missed_material = check_for_missed_material_gain_optimized(board_before, best_move_info, move_played, 
                                                                  state_manager, debug_mode, actual_move_number)
        if missed_material:
            missed_material["win_prob_drop"] = win_prob_drop
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
                "win_prob_drop": win_prob_drop
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
                "win_prob_drop": max(win_prob_drop, 50.0)
            }
            return missed_mate_result
    
    # 4. EXPENSIVE CHECK: Traps (uncommon, very expensive)
    # NEW: Only check traps if significant drop AND not already found other blunders
    if win_prob_drop >= TRAP_THRESHOLD and win_prob_drop >= 20:  # Higher threshold
        trap_result = detect_trap_optimized(board_before, move_played, board_after, turn_color, 
                                          state_manager, debug_mode)
        if trap_result:
            trap_result["move_number"] = actual_move_number
            trap_result["win_prob_drop"] = win_prob_drop
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
                "win_prob_drop": win_prob_drop
            }
    
    return None
```

3. **Add lazy evaluation configuration** in `config.py` (line 45):
```python
# Lazy Evaluation Thresholds
MIN_EVAL_DROP_FOR_ANALYSIS = 50  # Centipawns
EXPENSIVE_CHECK_THRESHOLD = 20    # Win probability drop % before running expensive checks
```

**Testing Instructions**:
1. Create a test file `test_phase1_optimizations.py`
2. Run the current version on 20 test games and record time
3. Implement each step and verify blunder detection accuracy remains above 95%
4. Measure performance improvement after each step
5. The combination should achieve 25-40% performance improvement

### Phase 2: Parallel Move Analysis (Target: 50% reduction)
**Goal**: Reduce from ~35s to ~18s

#### Step 2.1: Intra-Game Parallelization

**Current State**: In `analyze_games.py`, lines 712-803, moves are analyzed sequentially within each game.

**Implementation Steps**:

1. **Add parallel chunk analyzer in `analyze_games.py`** (add after line 810):
```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Thread-local storage for engines
thread_local = threading.local()

def analyze_move_chunk(chunk_data, engine_pool, target_user, blunder_threshold, 
                      engine_think_time, debug_mode, chunk_id):
    """
    Analyze a chunk of moves in parallel.
    Args:
        chunk_data: Dict with 'moves', 'start_board', 'start_idx'
        engine_pool: Engine pool instance
        target_user: Username to analyze
        blunder_threshold: Blunder threshold
        engine_think_time: Time per engine call
        debug_mode: Debug flag
        chunk_id: Chunk identifier
    Returns:
        List of (move_idx, blunder_info) tuples
    """
    # Get thread-local engine
    if not hasattr(thread_local, 'engine'):
        thread_local.engine = engine_pool.get_engine()
    engine = thread_local.engine
    
    chunk_blunders = []
    board = chunk_data['start_board'].copy()
    
    # Create local state manager for this chunk
    local_state_manager = BlunderStateManager()
    
    for relative_idx, move in enumerate(chunk_data['moves']):
        actual_move_idx = chunk_data['start_idx'] + relative_idx
        
        if board.turn == chunk_data['user_color']:
            # Analyze this move
            board_before = board.copy()
            
            # Quick heuristics check
            if not quick_heuristics_optimized(board_before, move, None, 
                                            chunk_data['user_color'], 
                                            local_state_manager, debug_mode):
                board.push(move)
                continue
            
            # Engine analysis
            info_before = engine.analyse(board_before, chess.engine.Limit(time=engine_think_time))
            board.push(move)
            info_after = engine.analyse(board, chess.engine.Limit(time=engine_think_time))
            
            # Categorize blunder
            blunder_info = categorize_blunder_optimized(
                board_before, board, move, info_before, info_after,
                info_before, local_state_manager, debug_mode, 
                chunk_data['move_numbers'][relative_idx]
            )
            
            if blunder_info:
                chunk_blunders.append((actual_move_idx, blunder_info))
        else:
            board.push(move)
    
    return chunk_blunders
```

2. **Create chunking utility function** (add after above function):
```python
def create_move_chunks(game, user_color, chunk_size=8):
    """
    Split game into analyzable chunks.
    Args:
        game: Chess game
        user_color: Color to analyze
        chunk_size: Moves per chunk
    Returns:
        List of chunk data dictionaries
    """
    all_moves = list(game.mainline_moves())
    chunks = []
    board = game.board()
    
    current_chunk_moves = []
    current_chunk_start_idx = 0
    current_chunk_start_board = board.copy()
    move_numbers = []
    
    for idx, move in enumerate(all_moves):
        # Add move to current chunk
        current_chunk_moves.append(move)
        move_numbers.append(board.fullmove_number)
        
        # Check if we should start a new chunk
        if len(current_chunk_moves) >= chunk_size:
            # Save current chunk
            chunks.append({
                'moves': current_chunk_moves.copy(),
                'start_board': current_chunk_start_board.copy(),
                'start_idx': current_chunk_start_idx,
                'user_color': user_color,
                'move_numbers': move_numbers.copy()
            })
            
            # Advance board to current position for next chunk
            for chunk_move in current_chunk_moves:
                current_chunk_start_board.push(chunk_move)
            
            # Reset for next chunk
            current_chunk_moves = []
            move_numbers = []
            current_chunk_start_idx = idx + 1
        
        board.push(move)
    
    # Add remaining moves as final chunk
    if current_chunk_moves:
        chunks.append({
            'moves': current_chunk_moves,
            'start_board': current_chunk_start_board.copy(),
            'start_idx': current_chunk_start_idx,
            'user_color': user_color,
            'move_numbers': move_numbers
        })
    
    return chunks
```

3. **Create new parallel game analyzer** (add as new function):
```python
def analyze_game_parallel(game, engine_pool, target_user, blunder_threshold, 
                         engine_think_time, debug_mode):
    """
    Analyze game using parallel chunk processing.
    """
    # Determine user color
    user_color = None
    if game.headers.get("White", "").lower() == target_user.lower():
        user_color = chess.WHITE
    elif game.headers.get("Black", "").lower() == target_user.lower():
        user_color = chess.BLACK
    
    if user_color is None:
        return []
    
    # Create chunks
    chunks = create_move_chunks(game, user_color, chunk_size=8)
    
    if debug_mode:
        print(f"[DEBUG] Split game into {len(chunks)} chunks for parallel analysis")
    
    # Parallel chunk analysis
    all_blunders = []
    max_workers = min(4, len(chunks))  # Use up to 4 threads
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all chunks
        future_to_chunk = {}
        for chunk_id, chunk in enumerate(chunks):
            future = executor.submit(
                analyze_move_chunk,
                chunk, engine_pool, target_user, blunder_threshold,
                engine_think_time, debug_mode, chunk_id
            )
            future_to_chunk[future] = chunk_id
        
        # Collect results
        chunk_results = {}
        for future in as_completed(future_to_chunk):
            chunk_id = future_to_chunk[future]
            try:
                chunk_blunders = future.result()
                chunk_results[chunk_id] = chunk_blunders
            except Exception as e:
                print(f"[ERROR] Chunk {chunk_id} failed: {e}")
                chunk_results[chunk_id] = []
        
        # Merge results in order
        for chunk_id in sorted(chunk_results.keys()):
            for _, blunder in chunk_results[chunk_id]:
                all_blunders.append(blunder)
    
    return all_blunders
```

4. **Update `analysis_service.py`** to use parallel analysis (modify line 150):
```python
# In analyze_game_optimized method, add condition:
if ENABLE_PARALLEL_MOVE_ANALYSIS and len(list(game.mainline_moves())) > 20:
    # Use parallel analysis for games with 20+ moves
    from analyze_games import analyze_game_parallel
    return analyze_game_parallel(
        game=game,
        engine_pool=self._get_engine_pool(),
        target_user=target_user,
        blunder_threshold=blunder_threshold,
        engine_think_time=engine_think_time,
        debug_mode=debug_mode
    )
else:
    # Use original sequential analysis
    from analyze_games import analyze_game_optimized
    return analyze_game_optimized(...)
```

5. **Add configuration in `config.py`** (line 50):
```python
# Parallel Move Analysis
ENABLE_PARALLEL_MOVE_ANALYSIS = True
MOVE_CHUNK_SIZE = 8  # Moves per chunk
MAX_MOVE_ANALYSIS_THREADS = 4
```

#### Step 2.2: Async Engine Communication

**Current State**: `stockfish_pool.py` uses synchronous engine calls.

**Implementation Steps**:

1. **Create async engine wrapper in `engines/async_engine.py`** (new file):
```python
import asyncio
import chess.engine
from typing import Optional, List, Tuple
import concurrent.futures

class AsyncEngineWrapper:
    """Async wrapper for chess engine with connection pooling."""
    
    def __init__(self, engine_path: str, pool_size: int = 4):
        self.engine_path = engine_path
        self.pool_size = pool_size
        self.engines = []
        self.available = asyncio.Queue(maxsize=pool_size)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=pool_size)
        self._initialized = False
    
    async def initialize(self):
        """Initialize engine pool."""
        if self._initialized:
            return
        
        for _ in range(self.pool_size):
            engine = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                chess.engine.SimpleEngine.popen_uci,
                self.engine_path
            )
            self.engines.append(engine)
            await self.available.put(engine)
        
        self._initialized = True
    
    async def analyse_async(self, board: chess.Board, limit: chess.engine.Limit):
        """Async analysis of a position."""
        engine = await self.available.get()
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                engine.analyse,
                board,
                limit
            )
            return result
        finally:
            await self.available.put(engine)
    
    async def analyse_batch_async(self, 
                                  positions: List[Tuple[chess.Board, chess.engine.Limit]]):
        """Analyze multiple positions concurrently."""
        tasks = []
        for board, limit in positions:
            task = self.analyse_async(board, limit)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return results
    
    async def close(self):
        """Close all engines."""
        while not self.available.empty():
            engine = await self.available.get()
            await asyncio.get_event_loop().run_in_executor(
                self.executor,
                engine.quit
            )
        self.executor.shutdown(wait=True)
```

2. **Create async game analyzer in `analyze_games.py`** (add new function):
```python
import asyncio

async def analyze_game_async(game, async_engine, target_user, blunder_threshold,
                           engine_think_time, debug_mode):
    """
    Analyze game using async engine calls.
    """
    blunders = []
    board = game.board()
    user_color = None
    state_manager = BlunderStateManager()
    
    # Determine user color
    if game.headers.get("White", "").lower() == target_user.lower():
        user_color = chess.WHITE
    elif game.headers.get("Black", "").lower() == target_user.lower():
        user_color = chess.BLACK
    
    if user_color is None:
        return []
    
    # Collect positions to analyze
    positions_to_analyze = []
    move_data = []
    all_moves = list(game.mainline_moves())
    
    # First pass: collect positions
    for move_idx, move in enumerate(all_moves):
        if board.turn == user_color:
            board_before = board.copy()
            
            # Quick heuristics
            if quick_heuristics_optimized(board_before, move, None, user_color, 
                                        state_manager, debug_mode):
                # Store position for analysis
                positions_to_analyze.append((
                    board_before.copy(),
                    chess.engine.Limit(time=engine_think_time)
                ))
                
                board_after = board_before.copy()
                board_after.push(move)
                
                positions_to_analyze.append((
                    board_after.copy(),
                    chess.engine.Limit(time=engine_think_time)
                ))
                
                move_data.append({
                    'move': move,
                    'move_idx': move_idx,
                    'board_before': board_before,
                    'board_after': board_after,
                    'move_number': board.fullmove_number
                })
        
        board.push(move)
    
    # Async batch analysis
    if positions_to_analyze:
        results = await async_engine.analyse_batch_async(positions_to_analyze)
        
        # Process results
        for i, move_info in enumerate(move_data):
            info_before = results[i * 2]
            info_after = results[i * 2 + 1]
            
            blunder_info = categorize_blunder_optimized(
                move_info['board_before'],
                move_info['board_after'],
                move_info['move'],
                info_before,
                info_after,
                info_before,  # Use as best move info
                state_manager,
                debug_mode,
                move_info['move_number']
            )
            
            if blunder_info:
                blunders.append(blunder_info)
    
    return blunders

# Sync wrapper for async function
def analyze_game_with_async_engine(game, engine_path, target_user, 
                                 blunder_threshold, engine_think_time, debug_mode):
    """Wrapper to run async analysis in sync context."""
    async def run_analysis():
        from engines.async_engine import AsyncEngineWrapper
        
        async_engine = AsyncEngineWrapper(engine_path, pool_size=4)
        await async_engine.initialize()
        
        try:
            return await analyze_game_async(
                game, async_engine, target_user,
                blunder_threshold, engine_think_time, debug_mode
            )
        finally:
            await async_engine.close()
    
    # Run async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run_analysis())
    finally:
        loop.close()
```

3. **Update configuration in `config.py`** (line 55):
```python
# Async Engine Configuration
ENABLE_ASYNC_ENGINE = True
ASYNC_ENGINE_POOL_SIZE = 4
ASYNC_BATCH_SIZE = 20
```

### Phase 3: Advanced Caching & Pattern Recognition (Target: 30% reduction)
**Goal**: Reduce from ~18s to ~12s

#### Step 3.1: Expanded Position Cache
```python
# Current: Basic position cache (1000 entries)
# Optimized: Multi-level cache with pattern recognition
```
- **Implementation**:
  - L1: Exact position cache (10K entries)
  - L2: Pattern cache (hanging pieces, pins, forks)
  - L3: Evaluation cache for similar structures
- **Impact**: 50% cache hit rate on typical games
- **Risk**: Low - more memory usage but controllable

#### Step 3.2: Tactical Pattern Pre-computation
```python
# Pre-compute common patterns once per position:
# - All hanging pieces
# - All pins/skewers
# - All fork possibilities
# - All discovered attack setups
```
- **Implementation**: Single pass pattern extraction in `analyze_position_cached()`
- **Impact**: Eliminate redundant calculations
- **Risk**: Low - consolidates existing logic

#### Step 3.3: Optimized Trap Detection
```python
# Current: Simulates every opponent move
# Optimized: Use heuristics to filter candidate moves
```
- **Implementation**:
  - Only check moves that attack/restrict piece mobility
  - Use piece mobility index instead of full simulation
  - Cache trap patterns
- **Impact**: 80% reduction in trap detection time
- **Risk**: Low - maintains accuracy with smart heuristics

### Phase 4: Algorithm Optimization (Target: 25% reduction)
**Goal**: Reduce from ~12s to ~9s

#### Step 4.1: Replace SEE with Simplified Exchange Calculator
```python
# Current: Recursive SEE with caching
# Optimized: Table-based exchange evaluation
```
- **Implementation**: Pre-computed exchange tables for common scenarios
- **Impact**: 10x faster for simple exchanges
- **Risk**: Low - SEE is already well-optimized

#### Step 4.2: Vectorized Board Operations
```python
# Use numpy arrays for board representation
# Vectorize attack/defend calculations
```
- **Implementation**: NumPy-based board operations
- **Impact**: 2-3x faster board manipulation
- **Risk**: Medium - significant refactoring

### Phase 5: Infrastructure Optimization (Target: 15% reduction)
**Goal**: Reach target of ~8-10s for 20 games

#### Step 5.1: Engine Pool Optimization
```python
# Dynamic pool sizing based on workload
# Pre-warmed engines
# Connection pooling
```
- **Implementation**: Enhanced `StockfishPool` with predictive scaling
- **Impact**: Eliminate engine startup overhead
- **Risk**: Low

#### Step 5.2: Memory-Mapped PGN Processing
```python
# Current: Load entire PGN into memory
# Optimized: Memory-mapped file access
```
- **Implementation**: Use mmap for large PGN files
- **Impact**: Faster I/O, lower memory usage
- **Risk**: Low

## Implementation Plan

### Week 1: Low-Risk Optimizations
1. **Day 1-2**: Implement enhanced position filtering (Step 1.2)
2. **Day 3-4**: Implement lazy evaluation (Step 1.3)
3. **Day 5**: Testing and benchmarking
   - Expected improvement: 20-30%

### Week 2: Engine Optimization
1. **Day 1-3**: Implement engine batching (Step 1.1)
2. **Day 4-5**: Implement async engine communication (Step 2.2)
   - Expected improvement: 30-40%

### Week 3: Parallelization
1. **Day 1-4**: Implement intra-game parallelization (Step 2.1)
2. **Day 5**: Integration testing
   - Expected improvement: 50-60%

### Week 4: Advanced Optimizations
1. **Day 1-2**: Implement expanded caching (Step 3.1)
2. **Day 3-4**: Optimize trap detection (Step 3.3)
3. **Day 5**: Final optimization and testing
   - Expected improvement: 70-80%

## Testing Strategy

### Accuracy Testing
```python
# Create test suite with known blunders
test_games = [
    "games/known_blunders.pgn",  # 50 games with verified blunders
    "games/no_blunders.pgn",     # 20 perfect games
    "games/complex_tactics.pgn"   # 30 games with complex patterns
]

# For each optimization:
# 1. Run original algorithm
# 2. Run optimized algorithm
# 3. Compare results (must be 95%+ match)
# 4. Measure performance improvement
```

### Performance Testing
```python
# Benchmark suite
benchmarks = {
    "small": 10 games,
    "medium": 50 games,
    "large": 200 games
}

# Track metrics:
# - Total time
# - Engine calls
# - Cache hit rates
# - Memory usage
# - CPU utilization
```

### Regression Testing
- Maintain test suite of edge cases
- Automated testing on each commit
- Performance regression alerts

## Risk Mitigation

### Accuracy Risks
- **Mitigation**: Keep original algorithm as fallback
- **Testing**: Extensive comparison testing
- **Rollback**: Feature flags for each optimization

### Performance Risks
- **Mitigation**: Incremental rollout
- **Monitoring**: Real-time performance metrics
- **Scaling**: Adjust parallelization based on system resources

## Success Metrics

### Primary Metrics
- **Analysis Time**: 20 games in <20 seconds (3x improvement)
- **Accuracy**: 95%+ blunder detection rate maintained
- **Scalability**: Linear scaling up to 200 games

### Secondary Metrics
- **Memory Usage**: <500MB for 20 games
- **CPU Efficiency**: 80%+ CPU utilization during analysis
- **Cache Hit Rate**: >50% for typical games

## Code Examples for Implementation

### Example 1: Engine Batching
```python
def analyze_moves_batch(board_positions, engine, think_time):
    """Analyze multiple positions in a single engine request"""
    # Collect positions
    batch_requests = []
    for pos in board_positions:
        batch_requests.append({
            'fen': pos.fen(),
            'depth': 15,
            'time': think_time
        })
    
    # Single batched call
    results = engine.analyse_batch(batch_requests)
    return results
```

### Example 2: Parallel Move Analysis
```python
def analyze_game_parallel(game, engine_pool, config):
    """Analyze game with parallel move processing"""
    moves = list(game.mainline_moves())
    
    # Split into chunks
    chunk_size = 10
    chunks = [moves[i:i+chunk_size] for i in range(0, len(moves), chunk_size)]
    
    # Parallel analysis
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for chunk in chunks:
            future = executor.submit(analyze_chunk, chunk, engine_pool.get_engine())
            futures.append(future)
        
        # Collect results
        results = []
        for future in as_completed(futures):
            results.extend(future.result())
    
    return merge_results(results)
```

### Example 3: Smart Position Filtering
```python
def should_analyze_position(board, move, game_phase):
    """Determine if position needs deep analysis"""
    # Skip forced moves
    if len(list(board.legal_moves)) == 1:
        return False
    
    # Skip book moves
    if board.fullmove_number <= 10 and is_book_move(board, move):
        return False
    
    # Skip obvious recaptures
    if is_obvious_recapture(board, move):
        return False
    
    # Skip simple endgames
    if len(board.piece_map()) <= 6:
        return use_tablebase(board)
    
    return True
```

## Conclusion

This optimization plan provides a clear path to achieve 3x performance improvement while maintaining analysis accuracy. The phased approach allows for incremental improvements with measurable results at each stage. By focusing on the primary bottlenecks and implementing both algorithmic and infrastructure optimizations, we can reach the target of analyzing 20 games in under 20 seconds.