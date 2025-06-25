import chess
import chess.pgn
import chess.engine
import os 
import argparse
import math

# ---- Constants ----
STOCKFISH_PATH_DEFAULT = os.path.join(os.path.dirname(__file__), "stockfish", "stockfish.exe")
BLUNDER_THRESHOLD_DEFAULT = 10
ENGINE_THINK_TIME_DEFAULT = 0.1

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
    if not board.is_capture(move): return 0
    if board.is_en_passant(move):
        capture_value = PIECE_VALUES[chess.PAWN]
    else:
        captured_piece = board.piece_at(move.to_square)
        if not captured_piece: return 0
        capture_value = PIECE_VALUES.get(captured_piece.piece_type, 0)
    board_after_move = board.copy()
    board_after_move.push(move)
    value = capture_value - see_exchange(board_after_move, move.to_square)
    return value

def see_exchange(board, target_square):
    attackers = board.attackers(board.turn, target_square)
    if not attackers: return 0
    lva_square = min(attackers, key=lambda s: PIECE_VALUES.get(board.piece_at(s).piece_type, 0)) 
    lva_piece = board.piece_at(lva_square) 
    if not lva_piece: return 0
    recapture_value = PIECE_VALUES.get(lva_piece.piece_type, 0)
    board_after_recapture = board.copy()
    recapture_move = chess.Move(lva_square, target_square)
    if lva_piece.piece_type == chess.PAWN and chess.square_rank(target_square) in [0, 7]:
        recapture_move.promotion = chess.QUEEN
    board_after_recapture.push(recapture_move)
    value = recapture_value - see_exchange(board_after_recapture, target_square)
    return max(0, value)

def cp_to_win_prob(cp):
    if cp is None: return 0.5
    return 1 / (1 + math.exp(-0.004 * cp))

#---- Blunder Categorization Functions ----
def check_for_missed_mate(board_before, best_move_info, after_move_eval, turn_color, move_num):
    best_move_eval = best_move_info["score"].pov(turn_color)
    if best_move_eval.is_mate() and best_move_eval.mate() > 0 and not after_move_eval.is_mate():
        mate_in = best_move_eval.mate()
        best_move = best_move_info['pv'][0]
        best_move_san = board_before.san(best_move)
        description = f"You missed a checkmate in {mate_in}. The best move was {best_move_san}."
        return {"category": "Missed Checkmate", "move_number": move_num, "description": description, "specificity": 10}
    return None

def check_for_allowed_mate(board_before, after_move_eval, move_num, move_played, best_move_info, info_after_move):
    if after_move_eval.is_mate() and after_move_eval.mate() < 0:
        punishing_move = info_after_move['pv'][0] if info_after_move.get('pv') else None
        move_played_san = board_before.san(move_played)
        description = f"Your move {move_played_san} allows the opponent to force checkmate in {abs(after_move_eval.mate())}"
        return {"category": "Allowed Checkmate", "move_number": move_num, "description": description, "punishing_move": punishing_move, "specificity": 10}
    return None

def check_for_material_loss(board_before, move_played, board_after, turn_color):
    move_num = board_before.fullmove_number if turn_color == chess.WHITE else f"{board_before.fullmove_number}..."
    move_played_san = board_before.san(move_played)
    if board_before.is_capture(move_played):
        see_value = see(board_before, move_played)
        if see_value < -100:
            return {"category": "Losing Exchange", "move_number": move_num, "description": f"Your move {move_played_san} was a losing exchange.", "punishing_move": None, "specificity": 2}
    hanging_pieces = []
    for square in chess.SQUARES:
        piece = board_after.piece_at(square)
        if piece and piece.color == turn_color: 
            attackers = board_after.attackers(not turn_color, square)
            if attackers:
                lva_square = min(attackers, key=lambda s: PIECE_VALUES.get(board_after.piece_at(s).piece_type, 0))
                lva_piece = board_after.piece_at(lva_square)
                if not lva_piece: continue
                capture_move = chess.Move(lva_square, square)
                if lva_piece.piece_type == chess.PAWN and chess.square_rank(square) in [0, 7]:
                    capture_move.promotion = chess.QUEEN
                piece_value = PIECE_VALUES.get(piece.piece_type, 0)
                if see(board_after, capture_move) >= piece_value - 50:
                    piece_name = PIECE_NAMES.get(piece.piece_type, "piece")
                    description = f"Your move {move_played_san} left your {piece_name} on {chess.square_name(square)} undefended."
                    hanging_pieces.append({"category": "Hanging a Piece", "move_number": move_num, "description": description, "punishing_move": capture_move, "specificity": 2})
    if hanging_pieces:
        return hanging_pieces[0]
    return None

def check_for_missed_material_gain(board_before, best_move_info, turn_color):
    move_num = board_before.fullmove_number if turn_color == chess.WHITE else f"{board_before.fullmove_number}..."
    if not best_move_info.get('pv'): return None
    best_move = best_move_info['pv'][0]
    if board_before.is_capture(best_move):
        if see(board_before, best_move) > 100:
            captured_piece = board_before.piece_at(best_move.to_square)
            piece_name = PIECE_NAMES.get(captured_piece.piece_type, "piece") if captured_piece else "material"
            best_move_san = board_before.san(best_move)
            description = f"You missed a chance to win a {piece_name} with {best_move_san}."
            return {"category": "Missed Material Gain", "move_number": move_num, "description": description, "punishing_move": best_move, "specificity": 1}
    return None

def check_for_missed_fork(board_before, best_move_info, turn_color):
    if not best_move_info.get('pv'): return None
    move_num = board_before.fullmove_number if turn_color == chess.WHITE else f"{board_before.fullmove_number}..."
    best_move = best_move_info['pv'][0]
    
    board_with_best_move = board_before.copy()
    board_with_best_move.push(best_move)
    attacker_piece = board_with_best_move.piece_at(best_move.to_square)
    if not attacker_piece: return None
    attacked_squares = board_with_best_move.attacks(best_move.to_square)
    opponent_pieces_attacked = [board_with_best_move.piece_at(sq) for sq in attacked_squares if board_with_best_move.piece_at(sq) and board_with_best_move.piece_at(sq).color != turn_color]
    valuable_pieces_attacked = [p for p in opponent_pieces_attacked if p.piece_type > chess.PAWN]
    if len(valuable_pieces_attacked) >= 2:
        piece_names = [PIECE_NAMES.get(p.piece_type, "piece") for p in valuable_pieces_attacked]
        forked_pieces = " and ".join(piece_names)
        attacker_name = PIECE_NAMES.get(attacker_piece.piece_type, "piece")
        best_move_san = board_before.san(best_move)
        description = f"You missed a fork with {best_move_san}. The {attacker_name} could have attacked the {forked_pieces}."
        return {"category": "Missed Fork", "move_number": move_num, "description": description, "punishing_move": best_move, "specificity": 4}
    return None

def allowed_fork(board_after, info_after_move, turn_color, debug_mode):
    if not info_after_move.get('pv'): return None
    move_num = board_after.fullmove_number if turn_color == chess.WHITE else f"{board_after.fullmove_number}..."
    opponent_best_move = info_after_move['pv'][0]
    
    if opponent_best_move not in board_after.legal_moves: return None
    
    opponent_best_move_san = board_after.san(opponent_best_move)
    if debug_mode: print(f"[DEBUG]Engine's best move for opponent: {opponent_best_move_san}")

    board_after_opponent_move = board_after.copy()
    board_after_opponent_move.push(opponent_best_move)
    forker_piece = board_after_opponent_move.piece_at(opponent_best_move.to_square)
    if not forker_piece: return None
    attacked_squares = board_after_opponent_move.attacks(opponent_best_move.to_square)
    player_pieces_attacked = [{'piece': board_after_opponent_move.piece_at(sq), 'square': sq} for sq in attacked_squares if board_after_opponent_move.piece_at(sq) and board_after_opponent_move.piece_at(sq).color == turn_color]
    valuable_pieces_attacked = [p for p in player_pieces_attacked if p['piece'].piece_type > chess.PAWN]
    if len(valuable_pieces_attacked) >= 2:
        if debug_mode: print(f"[DEBUG][allowed_fork] Fork detected! Attacked pieces: {[PIECE_NAMES.get(p['piece'].piece_type) for p in valuable_pieces_attacked]}")
        total_value_attacked = sum(PIECE_VALUES.get(p['piece'].piece_type, 0) for p in valuable_pieces_attacked)
        forker_value = PIECE_VALUES.get(forker_piece.piece_type, 0)
        if total_value_attacked > forker_value:
            piece_names = [PIECE_NAMES.get(p['piece'].piece_type, "piece") for p in valuable_pieces_attacked]
            forked_pieces = " and ".join(piece_names)
            forker_name = PIECE_NAMES.get(forker_piece.piece_type, "piece")
            description = f"Your last move allows the opponent to play {opponent_best_move_san}, creating a fork with their {forker_name} that attacks your {forked_pieces}."
            return {"category": "Allowed Fork", "move_number": move_num, "description": description, "punishing_move": opponent_best_move, "specificity": 5}
    return None

def check_for_missed_pin(board_before, best_move_info, turn_color):
    if not best_move_info.get('pv'): return None
    move_num = board_before.fullmove_number if turn_color == chess.WHITE else f"{board_before.fullmove_number}..."
    best_move = best_move_info['pv'][0]
    
    board_with_best_move = board_before.copy()
    board_with_best_move.push(best_move)
    pinner_piece = board_with_best_move.piece_at(best_move.to_square)
    if not pinner_piece or pinner_piece.piece_type not in [chess.QUEEN, chess.ROOK, chess.BISHOP]:
        return None

    # This logic uses the board's built-in is_pinned() method for simplicity and accuracy
    for square in chess.SQUARES:
        if board_with_best_move.is_pinned(not turn_color, square):
            # Check if this pin was created by the best_move
            pinner_square = board_with_best_move.pin(not turn_color, square)
            if pinner_square == best_move.to_square:
                best_move_san = board_before.san(best_move)
                pinned_piece_name = PIECE_NAMES.get(board_with_best_move.piece_at(square).piece_type, "piece")
                description = f"You missed a pin on the {pinned_piece_name} with {best_move_san}."
                return {"category": "Missed Pin", "move_number": move_num, "description": description, "punishing_move": best_move, "specificity": 4}
    return None

def check_for_allowed_pin(board_after, info_after_move, turn_color):
    if not info_after_move.get('pv'): return None
    move_num = board_after.fullmove_number if turn_color == chess.WHITE else f"{board_after.fullmove_number}..."
    opponent_best_move = info_after_move['pv'][0]

    if opponent_best_move not in board_after.legal_moves: return None

    board_after_opponent_move = board_after.copy()
    board_after_opponent_move.push(opponent_best_move)
    
    # This logic uses the board's built-in is_pinned() method
    for square in chess.SQUARES:
        # We are checking if our (turn_color) piece is now pinned
        if board_after_opponent_move.is_pinned(turn_color, square):
            pinner_square = board_after_opponent_move.pin(turn_color, square)
            if pinner_square == opponent_best_move.to_square:
                opponent_best_move_san = board_after.san(opponent_best_move)
                pinned_piece_name = PIECE_NAMES.get(board_after_opponent_move.piece_at(square).piece_type, "piece")
                description = f"Your last move allows the opponent to create a pin on your {pinned_piece_name} with {opponent_best_move_san}."
                return {"category": "Allowed Pin", "move_number": move_num, "description": description, "punishing_move": opponent_best_move, "specificity": 5}
    return None


def categorize_blunder(board_before, board_after, move_played, info_before_move, info_after_move, best_move_info, blunder_threshold, engine, engine_think_time, debug_mode):
    move_played_san = board_before.san(move_played)
    if debug_mode: print(f"\n--- [DEBUG] Categorizing Blunder for move {move_played_san} ---")
    turn_color = board_before.turn
    move_num = board_before.fullmove_number if turn_color == chess.WHITE else f"{board_before.fullmove_number}..."
    after_move_eval = info_after_move["score"].pov(turn_color)
    
    possible_blunders = []
    
    check_functions = [
        (check_for_allowed_mate, [board_before, after_move_eval, move_num, move_played, best_move_info, info_after_move]),
        (check_for_missed_mate, [board_before, best_move_info, after_move_eval, turn_color, move_num]),
        (allowed_fork, [board_after, info_after_move, turn_color, debug_mode]),
        (check_for_missed_fork, [board_before, best_move_info, turn_color]),
        (check_for_allowed_pin, [board_after, info_after_move, turn_color]),
        (check_for_missed_pin, [board_before, best_move_info, turn_color]),
        (check_for_material_loss, [board_before, move_played, board_after, turn_color]),
        (check_for_missed_material_gain, [board_before, best_move_info, turn_color]),
    ]
    
    if debug_mode: print("[DEBUG] Step 1: Collecting all possible blunder categories...")
    for func, args in check_functions:
        result = func(*args)
        if result:
            if debug_mode: print(f"[DEBUG]   - Found possible blunder: {result['category']}")
            possible_blunders.append(result)

    if debug_mode: print(f"[DEBUG] Collected {len(possible_blunders)} possible blunder(s): {[b['category'] for b in possible_blunders]}")

    if not possible_blunders:
        if debug_mode: print("[DEBUG] No specific tactical blunders found. Checking for win probability drop...")
        win_prob_before = cp_to_win_prob(info_before_move["score"].pov(turn_color).score(mate_score=10000))
        win_prob_after = cp_to_win_prob(after_move_eval.score(mate_score=10000))
        win_prob_drop = (win_prob_before - win_prob_after) * 100
        if debug_mode: print(f"[DEBUG]   - Win prob drop: {win_prob_drop:.1f}%, Threshold: {blunder_threshold}%")
        if win_prob_drop >= blunder_threshold:
            if debug_mode: print("[DEBUG]   - Drop is above threshold. Categorizing as 'Mistake'.")
            best_move_san = board_before.san(best_move_info['pv'][0])
            description = f"Your move {move_played_san} dropped your win probability by {win_prob_drop:.1f}%. The best move was {best_move_san}."
            return {"category": "Mistake", "move_number": move_num, "description": description}
        if debug_mode: print("[DEBUG]   - Drop is below threshold. Not a blunder.")
        return None

    if debug_mode: print("\n[DEBUG] --- Step 2: Ranking Blunders (Eval Mode) ---")
    ranked_blunders = []
    for blunder in possible_blunders:
        punishing_move = blunder.get("punishing_move")
        punishing_move_san = "N/A"
        
        is_allowed_blunder = blunder['category'].startswith("Allowed") or blunder['category'] == "Hanging a Piece"
        board_for_san = board_after if is_allowed_blunder else board_before
        
        if punishing_move and punishing_move in board_for_san.legal_moves:
             punishing_move_san = board_for_san.san(punishing_move)

        if debug_mode: print(f"[DEBUG]   Evaluating: {blunder['category']}")
        if debug_mode: print(f"[DEBUG]     - Punishing Move: {punishing_move_san}")
        if punishing_move:
            temp_board = board_before.copy() if not is_allowed_blunder else board_after.copy()
            if punishing_move in temp_board.legal_moves:
                temp_board.push(punishing_move)
                if debug_mode: print(f"[DEBUG]     - Making extra engine call for {punishing_move_san}...")
                punishment_info = engine.analyse(temp_board, chess.engine.Limit(time=engine_think_time))
                if debug_mode: print(f"[DEBUG]     - Raw score from engine: {punishment_info['score']}")
                severity_score = punishment_info["score"].pov(turn_color).score(mate_score=10000)
                blunder["severity_score"] = severity_score if severity_score is not None else -99999
                if debug_mode: print(f"[DEBUG]     - Calculated Severity Score: {blunder['severity_score']}")
            else:
                if debug_mode: print(f"[DEBUG]     - Punishing move {punishing_move.uci()} is not legal in this context. Discarding.")
                blunder["severity_score"] = 99999 
        else:
            blunder["severity_score"] = blunder.get("severity_score", 0)
            if debug_mode: print(f"[DEBUG]     - Using pre-calculated Severity Score: {blunder['severity_score']}")
        ranked_blunders.append(blunder)
    
    if debug_mode: print("\n[DEBUG] --- Step 3: Final Ranking Data ---")
    if debug_mode: 
        for b in ranked_blunders:
            print(f"[DEBUG]   - Category: {b['category']}, Severity: {b.get('severity_score', 'N/A')}, Specificity: {b.get('specificity', 0)}")

    final_blunder = min(ranked_blunders, key=lambda x: (x.get("severity_score", 99999), -x.get("specificity", 0)))
    if debug_mode: print(f"\n[DEBUG] --- Final Decision ---")
    if debug_mode: print(f"[DEBUG] Selected Blunder: {final_blunder['category']} (Score: {final_blunder['severity_score']})")
    
    return final_blunder


def analyze_game(game, engine, target_user, blunder_threshold, engine_think_time, debug_mode):
    blunders = []
    board = game.board()
    user_color = None
    if game.headers.get("White", "").lower() == target_user.lower(): user_color = chess.WHITE
    elif game.headers.get("Black", "").lower() == target_user.lower(): user_color = chess.BLACK
    if user_color is None: return []

    for move in game.mainline_moves():
        if board.turn == user_color:
            board_before = board.copy()
            info_before_move = engine.analyse(board, chess.engine.Limit(time=engine_think_time))
            best_move_info = info_before_move
            board.push(move)
            info_after_move = engine.analyse(board, chess.engine.Limit(time=engine_think_time))
            blunder_info = categorize_blunder(board_before, board, move, info_before_move, info_after_move, best_move_info, blunder_threshold, engine, engine_think_time, debug_mode)
            if blunder_info:
                blunders.append(blunder_info)
        else:
            board.push(move)
    return blunders

def main():
    parser = argparse.ArgumentParser(description="Analyze chess games to find blunders.")
    parser.add_argument("--pgn", default="testgames.pgn", help="Path to the PGN file (default: testgames.pgn).")
    parser.add_argument("--username", default="test", help="Your username to analyze blunders for (default: test).")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug print statements.")
    parser.add_argument("--stockfish_path", default=STOCKFISH_PATH_DEFAULT, help="Path to the Stockfish executable.")
    parser.add_argument("--blunder_threshold", type=float, default=BLUNDER_THRESHOLD_DEFAULT, help="Win probability drop threshold for a blunder.")
    parser.add_argument("--engine_think_time", type=float, default=ENGINE_THINK_TIME_DEFAULT, help="Engine think time per move in seconds.")
    args = parser.parse_args()

    print("--- Running analysis ---\n")
    engine = chess.engine.SimpleEngine.popen_uci(args.stockfish_path)
    
    try:
        with open(args.pgn) as pgn_file:
            game_num = 1
            total_blunders = []
            while True:
                game = chess.pgn.read_game(pgn_file)
                if game is None: break
                white_player = game.headers.get("White", "Unknown")
                black_player = game.headers.get("Black", "Unknown")
                print(f"Analyzing game #{game_num}: {white_player} vs {black_player}")
                blunders = analyze_game(game, engine, args.username, args.blunder_threshold, args.engine_think_time, args.debug)
                for blunder in blunders:
                    print(f"  -> {blunder['category']}: On move {blunder['move_number']}, {blunder['description']}")
                total_blunders.extend(blunders)
                game_num += 1
    except FileNotFoundError:
        print(f"Error: The file '{args.pgn}' was not found.")
    finally:
        print("\n--- Quitting engine ---")
        engine.quit()

    print("\n--- Analysis Complete ---")
    print(f"Found a total of {len(total_blunders)} mistakes/blunders for user '{args.username}'.\n")

if __name__ == "__main__":
    main()
