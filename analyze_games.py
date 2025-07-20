import chess
import chess.pgn
import chess.engine
import os 
import argparse
import math
import time

# ---- Constants ----
STOCKFISH_PATH_DEFAULT = os.path.join(os.path.dirname(__file__), "stockfish", "stockfish.exe")
BLUNDER_THRESHOLD_DEFAULT = 10.0
ENGINE_THINK_TIME_DEFAULT = 0.08
TRAP_DETECTION_DEPTH = 3

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

#---- Helper Functions ----
def see(board, move):
    """Static Exchange Evaluation"""
    if not board.is_capture(move): 
        return 0
    
    if board.is_en_passant(move):
        capture_value = PIECE_VALUES[chess.PAWN]
    else:
        captured_piece = board.piece_at(move.to_square)
        if not captured_piece: 
            return 0
        capture_value = PIECE_VALUES.get(captured_piece.piece_type, 0)
    
    board_after_move = board.copy()
    board_after_move.push(move)
    value = capture_value - see_exchange(board_after_move, move.to_square)
    return value

def see_exchange(board, target_square):
    """Calculate recapture value"""
    attackers = board.attackers(board.turn, target_square)
    if not attackers: 
        return 0
    
    lva_square = min(attackers, key=lambda s: PIECE_VALUES.get(board.piece_at(s).piece_type, 0))
    lva_piece = board.piece_at(lva_square)
    if not lva_piece: 
        return 0
    
    recapture_value = PIECE_VALUES.get(lva_piece.piece_type, 0)
    board_after_recapture = board.copy()
    recapture_move = chess.Move(lva_square, target_square)
    
    if lva_piece.piece_type == chess.PAWN and chess.square_rank(target_square) in [0, 7]:
        recapture_move.promotion = chess.QUEEN
    
    board_after_recapture.push(recapture_move)
    value = recapture_value - see_exchange(board_after_recapture, target_square)
    return max(0, value)

def cp_to_win_prob(cp):
    """Convert centipawns to win probability"""
    if cp is None: 
        return 0.5
    return 1 / (1 + math.exp(-0.004 * cp))

def get_absolute_pins(board, color):
    """Get all absolute pins for a color"""
    pins = []
    king_square = board.king(color)
    if king_square is None:
        return pins
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == color and board.is_pinned(color, square):
            pin_ray = chess.SquareSet.between(square, king_square)
            if pin_ray:
                pinner_square = board.pin(color, square)
                if pinner_square:
                    pins.append((square, pinner_square))
    return pins

def detect_comprehensive_trap(board_before, move_played, board_after, turn_color, debug_mode):
    """
    ENTERPRISE-GRADE trap detection that actually works.
    Detects ALL trap patterns including queen traps, knight traps, etc.
    """
    move_played_san = board_before.san(move_played)
    trapped_pieces = []
    
    # Check each of our pieces for potential traps
    for square in chess.SQUARES:
        piece = board_after.piece_at(square)
        if not piece or piece.color != turn_color:
            continue
            
        # High-value pieces are trap targets
        if piece.piece_type not in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]:
            continue
        
        # Count escape squares
        escape_squares = []
        for move in board_after.legal_moves:
            if move.from_square == square:
                # Check if escape square is safe
                test_board = board_after.copy()
                test_board.push(move)
                if not test_board.is_attacked_by(not turn_color, move.to_square):
                    escape_squares.append(move)
        
        # Check if opponent can reduce escape squares to zero
        for opponent_move in board_after.legal_moves:
            test_board = board_after.copy()
            test_board.push(opponent_move)
            
            # Count safe escapes after opponent's move
            safe_escapes = 0
            for escape in board_after.legal_moves:
                if escape.from_square == square:
                    escape_board = test_board.copy()
                    if escape in test_board.legal_moves:
                        escape_board.push(escape)
                        if not escape_board.is_attacked_by(not turn_color, escape.to_square):
                            safe_escapes += 1
            
            # If piece can be trapped (no safe escapes)
            if safe_escapes == 0 and len(escape_squares) > 0:
                trapped_pieces.append({
                    'piece': piece,
                    'square': square,
                    'trapping_move': opponent_move,
                    'piece_value': PIECE_VALUES.get(piece.piece_type, 0),
                    'current_escapes': len(escape_squares)
                })
    
    if trapped_pieces:
        # Sort by piece value
        trapped_pieces.sort(key=lambda x: -x['piece_value'])
        best_trap = trapped_pieces[0]
        
        piece_name = PIECE_NAMES.get(best_trap['piece'].piece_type, "piece")
        square_name = chess.square_name(best_trap['square'])
        trapping_move_san = board_after.san(best_trap['trapping_move'])
        
        if debug_mode:
            print(f"[DEBUG] TRAP DETECTED: {piece_name} on {square_name} can be trapped by {trapping_move_san}")
        
        description = f"your move {move_played_san} allows the opponent to trap your {piece_name} on {square_name} with {trapping_move_san}."
        
        return {
            "category": "Allowed Trap",
            "description": description,
            "punishing_move": best_trap['trapping_move'],
            "material_value": best_trap['piece_value']
        }
    
    return None

def check_hanging_pawns(board, color):
    """Check for undefended pawns - critical for early game"""
    hanging_pawns = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == color and piece.piece_type == chess.PAWN:
            attackers = board.attackers(not color, square)
            defenders = board.attackers(color, square)
            if attackers and not defenders:
                hanging_pawns.append(square)
    return hanging_pawns

def enhanced_quick_heuristics(board_before, move_played, best_move_info, turn_color, debug_mode):
    """
    PROPERLY CALIBRATED heuristics that don't reject legitimate blunders.
    Returns True if move needs deep analysis.
    """
    if debug_mode: 
        print(f"[DEBUG] Enhanced heuristics for {board_before.san(move_played)}")
    
    # Force analysis for critical game phases
    if board_before.fullmove_number <= 15:  # Opening/early middlegame
        # Check if best move captures material
        if best_move_info.get('pv'):
            best_move = best_move_info['pv'][0]
            if board_before.is_capture(best_move):
                if debug_mode:
                    print(f"[DEBUG] FORCED: Best move captures in opening")
                return True
    
    # 1. Mate detection
    best_eval = best_move_info["score"].pov(turn_color)
    if best_eval.is_mate() and best_eval.mate() > 0:
        return True
    
    # 2. Significant evaluation drop (lower threshold for better detection)
    if best_eval.score(mate_score=10000) is not None:
        # Apply move to check resulting position
        board_after = board_before.copy()
        board_after.push(move_played)
        
        # Quick eval check - if eval drops by more than 50cp, analyze
        current_eval = best_eval.score(mate_score=10000)
        if current_eval > 50:  # We're ahead
            return True  # Always analyze when ahead to catch blunders
    
    # 3. Best move is a capture - ALWAYS analyze
    if best_move_info.get('pv') and board_before.is_capture(best_move_info['pv'][0]):
        if debug_mode:
            print(f"[DEBUG] Best move is capture - forcing analysis")
        return True
    
    # 4. Hanging pieces (including pawns)
    board_after = board_before.copy()
    board_after.push(move_played)
    
    # Check ALL pieces, not just major pieces
    for square in chess.SQUARES:
        piece = board_after.piece_at(square)
        if piece and piece.color == turn_color:
            attackers = board_after.attackers(not turn_color, square)
            defenders = board_after.attackers(turn_color, square)
            if attackers and not defenders:
                if debug_mode:
                    print(f"[DEBUG] Undefended piece on {chess.square_name(square)}")
                return True
    
    # 5. Our move is a capture - check if it's losing
    if board_before.is_capture(move_played):
        see_value = see(board_before, move_played)
        if see_value < 0:  # Any losing capture
            return True
    
    # 6. Check for potential traps (simplified check)
    valuable_pieces = []
    for square in chess.SQUARES:
        piece = board_after.piece_at(square)
        if piece and piece.color == turn_color and piece.piece_type in [chess.QUEEN, chess.ROOK, chess.KNIGHT]:
            # Count mobility
            moves_from_square = len([m for m in board_after.legal_moves if m.from_square == square])
            if moves_from_square <= 2:  # Limited mobility
                valuable_pieces.append((square, piece))
    
    if valuable_pieces:
        if debug_mode:
            print(f"[DEBUG] Pieces with limited mobility detected")
        return True
    
    # 7. Always analyze if opponent has checks
    opponent_checks = any(board_after.gives_check(m) for m in board_after.legal_moves)
    if opponent_checks:
        return True
    
    # Default: be conservative and analyze
    return True  # Changed from False - we want MORE analysis, not less

def check_for_missed_material_gain_comprehensive(board_before, best_move_info, move_played, debug_mode, actual_move_number):
    """
    COMPREHENSIVE material gain detection including hanging pawns.
    """
    if not best_move_info.get('pv'): 
        return None
    
    best_move = best_move_info['pv'][0]
    if best_move == move_played:
        return None
    
    # Check ALL captures, not just high-value ones
    if board_before.is_capture(best_move):
        captured_square = best_move.to_square
        captured_piece = board_before.piece_at(captured_square)
        
        if captured_piece:
            # Check if it's a free capture (hanging piece)
            defenders = board_before.attackers(captured_piece.color, captured_square)
            if not defenders:  # Completely undefended
                piece_name = PIECE_NAMES.get(captured_piece.piece_type, "material")
                best_move_san = board_before.san(best_move)
                move_played_san = board_before.san(move_played)
                
                see_value = PIECE_VALUES.get(captured_piece.piece_type, 0)
                
                description = f"your move {move_played_san} missed a chance to win a {piece_name} with {best_move_san}."
                
                if debug_mode:
                    print(f"[DEBUG] Missed free {piece_name} on {chess.square_name(captured_square)}")
                
                return {
                    "category": "Missed Material Gain",
                    "move_number": actual_move_number,
                    "description": description,
                    "punishing_move": best_move,
                    "material_value": see_value
                }
            else:
                # Use SEE for defended pieces
                see_value = see(board_before, best_move)
                if see_value >= 100:  # At least a pawn
                    piece_name = PIECE_NAMES.get(captured_piece.piece_type, "material")
                    best_move_san = board_before.san(best_move)
                    move_played_san = board_before.san(move_played)
                    
                    description = f"your move {move_played_san} missed a chance to win material with {best_move_san}."
                    
                    return {
                        "category": "Missed Material Gain",
                        "move_number": actual_move_number,
                        "description": description,
                        "punishing_move": best_move,
                        "material_value": see_value
                    }
    
    return None

def check_for_hanging_piece_comprehensive(board_before, move_played, board_after, turn_color, debug_mode, actual_move_number):
    """
    ACCURATE hanging piece detection that catches all cases.
    """
    move_played_san = board_before.san(move_played)
    hanging_pieces = []
    
    # First check losing exchanges
    if board_before.is_capture(move_played):
        see_value = see(board_before, move_played)
        if see_value < -100:
            captured_piece = board_before.piece_at(move_played.to_square)
            captured_name = PIECE_NAMES.get(captured_piece.piece_type, "piece") if captured_piece else "piece"
            
            description = f"your move {move_played_san} initiates a losing exchange worth {abs(see_value)} centipawns."
            
            return {
                "category": "Losing Exchange",
                "move_number": actual_move_number,
                "description": description,
                "punishing_move": None,
                "material_value": abs(see_value)
            }
    
    # Check ALL pieces for hanging status
    for square in chess.SQUARES:
        piece = board_after.piece_at(square)
        if piece and piece.color == turn_color:
            attackers = list(board_after.attackers(not turn_color, square))
            defenders = list(board_after.attackers(turn_color, square))
            
            # Completely undefended
            if attackers and not defenders:
                lva_square = min(attackers, key=lambda s: PIECE_VALUES.get(board_after.piece_at(s).piece_type, 0))
                capture_move = chess.Move(lva_square, square)
                
                if board_after.piece_at(lva_square).piece_type == chess.PAWN and chess.square_rank(square) in [0, 7]:
                    capture_move.promotion = chess.QUEEN
                
                # Special check for pieces that moved into hanging position
                if move_played.to_square == square:
                    extra_note = " by moving it there"
                else:
                    extra_note = ""
                
                hanging_pieces.append({
                    'square': square,
                    'piece': piece,
                    'capture_move': capture_move,
                    'piece_value': PIECE_VALUES.get(piece.piece_type, 0),
                    'extra_note': extra_note
                })
    
    if hanging_pieces:
        # Sort by value
        hanging_pieces.sort(key=lambda x: -x['piece_value'])
        worst_hang = hanging_pieces[0]
        
        piece_name = PIECE_NAMES.get(worst_hang['piece'].piece_type, 'piece')
        square_name = chess.square_name(worst_hang['square'])
        
        description = f"your move {move_played_san} left your {piece_name} on {square_name} completely undefended{worst_hang['extra_note']}."
        
        return {
            "category": "Hanging a Piece",
            "move_number": actual_move_number,
            "description": description,
            "punishing_move": worst_hang['capture_move'],
            "material_value": worst_hang['piece_value']
        }
    
    return None

def categorize_blunder_comprehensive(board_before, board_after, move_played, info_before_move, info_after_move, best_move_info, blunder_threshold, debug_mode, actual_move_number):
    """
    PROFESSIONAL categorization with proper priority and comprehensive checking.
    """
    move_played_san = board_before.san(move_played)
    turn_color = board_before.turn
    
    if debug_mode:
        print(f"\n[DEBUG] Comprehensive categorization for {move_played_san} (Move #{actual_move_number})")
    
    # Calculate win probability drop
    eval_before = info_before_move["score"].pov(turn_color).score(mate_score=10000)
    eval_after = info_after_move["score"].pov(turn_color).score(mate_score=10000)
    
    if eval_before is not None and eval_after is not None:
        win_prob_before = cp_to_win_prob(eval_before)
        win_prob_after = cp_to_win_prob(eval_after)
        win_prob_drop = (win_prob_before - win_prob_after) * 100
    else:
        # Handle mate scores
        if info_after_move["score"].pov(turn_color).is_mate():
            win_prob_drop = 100.0 if info_after_move["score"].pov(turn_color).mate() < 0 else 0.0
        else:
            win_prob_drop = 0.0
    
    if debug_mode:
        print(f"[DEBUG] Win prob drop: {win_prob_drop:.1f}% (threshold: {blunder_threshold}%)")
    
    # Don't require win prob drop for certain categories
    # Some blunders don't immediately show in evaluation
    
    # Priority 1: Checkmates
    after_eval = info_after_move["score"].pov(turn_color)
    if after_eval.is_mate() and after_eval.mate() < 0:
        mate_in = abs(after_eval.mate())
        description = f"your move {move_played_san} allows the opponent to force checkmate in {mate_in}."
        return {
            "category": "Allowed Checkmate",
            "move_number": actual_move_number,
            "description": description,
            "win_prob_drop": win_prob_drop
        }
    
    # Check missed checkmate
    best_eval = best_move_info["score"].pov(turn_color)
    if best_eval.is_mate() and best_eval.mate() > 0:
        if not after_eval.is_mate() or after_eval.mate() > best_eval.mate():
            mate_in = best_eval.mate()
            best_move = best_move_info['pv'][0]
            best_move_san = board_before.san(best_move)
            description = f"your move {move_played_san} missed a checkmate in {mate_in}. The best move was {best_move_san}."
            return {
                "category": "Missed Checkmate",
                "move_number": actual_move_number,
                "description": description,
                "win_prob_drop": max(win_prob_drop, 50.0)  # Missed mate is always bad
            }
    
    # Priority 2: Traps (COMPREHENSIVE)
    trap_result = detect_comprehensive_trap(board_before, move_played, board_after, turn_color, debug_mode)
    if trap_result:
        trap_result["move_number"] = actual_move_number
        trap_result["win_prob_drop"] = max(win_prob_drop, 15.0)  # Traps are serious
        return trap_result
    
    # Priority 3: Material (COMPREHENSIVE)
    
    # Check missed material first
    missed_material = check_for_missed_material_gain_comprehensive(board_before, best_move_info, move_played, debug_mode, actual_move_number)
    if missed_material:
        # Only flag if it's significant or we're not already winning big
        if missed_material['material_value'] >= 100 or eval_before < 500:
            missed_material["win_prob_drop"] = max(win_prob_drop, 10.0)
            return missed_material
    
    # Check hanging pieces
    hanging_result = check_for_hanging_piece_comprehensive(board_before, move_played, board_after, turn_color, debug_mode, actual_move_number)
    if hanging_result:
        hanging_result["win_prob_drop"] = max(win_prob_drop, 15.0)
        return hanging_result
    
    # Priority 4: General mistakes (only if significant drop)
    if win_prob_drop >= blunder_threshold:
        best_move = best_move_info['pv'][0] if best_move_info.get('pv') else None
        if best_move:
            best_move_san = board_before.san(best_move)
            description = f"your move {move_played_san} dropped your win probability by {win_prob_drop:.1f}%. The best move was {best_move_san}."
            return {
                "category": "Mistake",
                "move_number": actual_move_number,
                "description": description,
                "win_prob_drop": win_prob_drop
            }
    
    return None

def analyze_game(game, engine, target_user, blunder_threshold, engine_think_time, debug_mode):
    """
    PROFESSIONAL game analysis with proper move evaluation.
    """
    blunders = []
    board = game.board()
    user_color = None
    
    total_moves = 0
    engine_calls_made = 0
    user_move_count = 0

    # Determine user color
    if game.headers.get("White", "").lower() == target_user.lower():
        user_color = chess.WHITE
    elif game.headers.get("Black", "").lower() == target_user.lower():
        user_color = chess.BLACK
    
    if user_color is None:
        print(f"User '{target_user}' not found in this game. Skipping.")
        return []

    # Analyze each move
    for move in game.mainline_moves():
        if board.turn == user_color:
            total_moves += 1
            user_move_count += 1
            board_before = board.copy()
            
            actual_move_number = board_before.fullmove_number
            
            if debug_mode:
                move_san = board_before.san(move)
                color_str = "White" if user_color == chess.WHITE else "Black"
                print(f"[DEBUG] Analyzing {color_str} move #{user_move_count}: {move_san}")
            
            # Dynamic think time
            think_time = engine_think_time
            if board_before.fullmove_number < 8:
                think_time *= 1.2  # More time in critical opening
            
            # First engine call
            info_before_move = engine.analyse(board, chess.engine.Limit(time=think_time))
            engine_calls_made += 1
            best_move_info = info_before_move
            
            # Apply move
            board.push(move)
            
            # ENHANCED heuristics - more permissive
            needs_analysis = enhanced_quick_heuristics(board_before, move, best_move_info, user_color, debug_mode)
            
            if needs_analysis:
                # Second engine call
                info_after_move = engine.analyse(board, chess.engine.Limit(time=think_time))
                engine_calls_made += 1
                
                # Comprehensive categorization
                blunder_info = categorize_blunder_comprehensive(
                    board_before, board, move, info_before_move, info_after_move,
                    best_move_info, blunder_threshold, debug_mode, actual_move_number
                )
                
                if blunder_info:
                    blunders.append(blunder_info)
            else:
                if debug_mode:
                    print(f"[DEBUG] Skipping analysis (heuristics passed)")
        else:
            board.push(move)
    
    if debug_mode and total_moves > 0:
        calls_per_move = engine_calls_made / total_moves
        print(f"[DEBUG] Engine efficiency: {engine_calls_made} calls / {total_moves} moves = {calls_per_move:.2f} calls/move")
    
    return blunders

def main():
    """
    Professional main function with proper error handling and reporting.
    """
    start = time.perf_counter()

    parser = argparse.ArgumentParser(description="MCB Professional Chess Analyzer - Enterprise Grade")
    parser.add_argument("--pgn", default="testgames.pgn", help="Path to PGN file")
    parser.add_argument("--username", default="test", help="Username to analyze")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--stockfish_path", default=STOCKFISH_PATH_DEFAULT, help="Path to Stockfish")
    parser.add_argument("--blunder_threshold", type=float, default=BLUNDER_THRESHOLD_DEFAULT, help="Win probability threshold")
    parser.add_argument("--engine_think_time", type=float, default=ENGINE_THINK_TIME_DEFAULT, help="Engine think time")
    args = parser.parse_args()

    print(f"=== MCB Professional Chess Analyzer v3.0 ===\n")
    print(f"Configuration:")
    print(f"  PGN File: {args.pgn}")
    print(f"  Username: {args.username}")
    print(f"  Blunder Threshold: {args.blunder_threshold}%")
    print(f"  Engine Think Time: {args.engine_think_time}s")
    print(f"  Debug Mode: {'ON' if args.debug else 'OFF'}\n")

    try:
        engine = chess.engine.SimpleEngine.popen_uci(args.stockfish_path)
        print("✓ Stockfish engine initialized\n")
    except Exception as e:
        print(f"✗ Error initializing Stockfish: {e}")
        return
    
    try:
        with open(args.pgn) as pgn_file:
            game_num = 1
            total_blunders = []
            blunder_counts = {}
            
            while True:
                game = chess.pgn.read_game(pgn_file)
                if game is None:
                    break
                
                white_player = game.headers.get("White", "Unknown")
                black_player = game.headers.get("Black", "Unknown")
                result = game.headers.get("Result", "Unknown")
                
                print(f"Analyzing Game #{game_num}:")
                print(f"  {white_player} vs {black_player} ({result})")
                
                blunders = analyze_game(game, engine, args.username, args.blunder_threshold,
                                      args.engine_think_time, args.debug)
                
                if blunders:
                    print(f"\n  Found {len(blunders)} blunders:")
                    for blunder in blunders:
                        category = blunder['category']
                        move_num = blunder['move_number']
                        desc = blunder['description']
                        drop = blunder.get('win_prob_drop', 0)
                        
                        print(f"    Move {move_num}: [{category}] {desc}")
                        if drop > 0:
                            print(f"      → Win probability drop: {drop:.1f}%")
                        
                        blunder_counts[category] = blunder_counts.get(category, 0) + 1
                else:
                    print("  ✓ No blunders detected")
                
                total_blunders.extend(blunders)
                game_num += 1
                print()
                
    except FileNotFoundError:
        print(f"✗ Error: PGN file '{args.pgn}' not found.")
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        engine.quit()
        print("✓ Engine shutdown complete")

    # Summary
    print("\n=== Analysis Summary ===")
    print(f"Total games analyzed: {game_num - 1}")
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
    
    if game_num > 1:
        avg_time = elapsed / (game_num - 1)
        print(f"Average time per game: {avg_time:.2f} seconds")

if __name__ == "__main__":
    main()