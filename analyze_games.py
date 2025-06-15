import chess
import chess.pgn
import chess.engine
import os 
import argparse
import math

STOCKFISH_PATH_DEFAULT = os.path.join(os.path.dirname(__file__), "stockfish", "stockfish.exe")
# default win probability threshold for a blunder. Represents a x% drop in win probability.
WIN_PROB_THRESHOLD_DEFAULT = 20.0
# default engine think time per move in seconds.
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


def see(board, move):
    """
    A simpler, standard implementation of Static Exchange Evaluation.
    A positive score is favorable for the side making the move.
    """
    if not board.is_capture(move):
        return 0
    
    # Get value of piece on destination square
    if board.is_en_passant(move):
        capture_value = PIECE_VALUES[chess.PAWN]
    else:
        captured_piece = board.piece_at(move.to_square)
        if not captured_piece: return 0 # Should not happen
        capture_value = PIECE_VALUES.get(captured_piece.piece_type, 0)

    # Make the move on a temporary board
    board_after_move = board.copy()
    board_after_move.push(move)
    
    # The value of the exchange is the captured piece minus what can be recaptured by the opponent.
    value = capture_value - _see_exchange(board_after_move, move.to_square)
    return value

def _see_exchange(board, target_square):
    """
    Calculates the value of the best recapture on a square, from the perspective of the side to move.
    """
    # Find the least valuable attacker for the side to move
    attackers = board.attackers(board.turn, target_square)
    if not attackers:
        return 0 # No attackers, exchange is over, no value lost for the opponent

    lva_square = min(attackers, key=lambda s: PIECE_VALUES.get(board.piece_at(s).piece_type, 0))
    lva_piece = board.piece_at(lva_square)
    if not lva_piece: return 0
    
    # Value of the piece making the recapture
    recapture_value = PIECE_VALUES.get(lva_piece.piece_type, 0)

    # Make the recapture on a temporary board
    board_after_recapture = board.copy()
    recapture_move = chess.Move(lva_square, target_square)
    if lva_piece.piece_type == chess.PAWN and chess.square_rank(target_square) in [0, 7]:
        recapture_move.promotion = chess.QUEEN
    board_after_recapture.push(recapture_move)
    
    # The value of this exchange is the piece we just captured (the previous attacker)
    # minus the value of the subsequent exchange from the other player's perspective.
    value = recapture_value - _see_exchange(board_after_recapture, target_square)

    # The side to move will not make a capture if it loses material, so cap at 0.
    return max(0, value)


def check_for_material_loss(board_before, move_played, info_after, board_after, turn_color):
    move_num = board_before.fullmove_number if turn_color == chess.WHITE else f"{board_before.fullmove_number}..."
    
    if board_before.is_capture(move_played):
        see_value = see(board_before, move_played)
        if see_value < -100:
            return {"category": "Losing Exchange", "move_number": move_num, "description": f"Your move {move_played.uci()} was a losing exchange."}

    for square in chess.SQUARES:
        piece = board_after.piece_at(square)
        if piece and piece.color == turn_color:
            attackers = board_after.attackers(not turn_color, square)
            if attackers:
                least_valuable_attacker_square = min(attackers, key=lambda s: PIECE_VALUES.get(board_after.piece_at(s).piece_type, 0))
                capture_move = chess.Move(least_valuable_attacker_square, square)
                if board_after.piece_at(least_valuable_attacker_square).piece_type == chess.PAWN and chess.square_rank(square) in [0, 7]:
                    capture_move.promotion = chess.QUEEN
                
                if see(board_after, capture_move) > 100:
                    piece_name = PIECE_NAMES.get(piece.piece_type, "piece")
                    description = f"Your move {move_played.uci()} left your {piece_name} on {chess.square_name(square)} undefended."
                    return {"category": "Hanging a Piece", "move_number": move_num, "description": description}

    return None

def check_for_missed_material_gain(board_before, best_move_info, board_after, turn_color):
    move_num = board_before.fullmove_number if turn_color == chess.WHITE else f"{board_before.fullmove_number}..."
    best_move = best_move_info['pv'][0]
    if board_before.is_capture(best_move):
        see_value = see(board_before, best_move)
        if see_value > 100:
            return {"category": "Missed Material Gain", "move_number": move_num, "description": f"You missed a chance to win material with {best_move.uci()}."}
    return None

def detect_fork(board_before, best_move, board_after, turn_color):
    move_num = board_before.fullmove_number if turn_color == chess.WHITE else f"{board_before.fullmove_number}..."
    
    board_with_best_move = board_before.copy()
    board_with_best_move.push(best_move)

    attacker_piece = board_with_best_move.piece_at(best_move.to_square)
    if not attacker_piece:
        return None

    attacked_squares = board_with_best_move.attacks(best_move.to_square)
    
    opponent_pieces_attacked = []
    for attacked_square in attacked_squares:
        piece = board_with_best_move.piece_at(attacked_square)
        if piece and piece.color != turn_color:
            opponent_pieces_attacked.append(piece)

    valuable_pieces_attacked = [p for p in opponent_pieces_attacked if p.piece_type > chess.PAWN]
    
    if len(valuable_pieces_attacked) >= 2:
        piece_names = [PIECE_NAMES.get(p.piece_type, "piece") for p in valuable_pieces_attacked]
        forked_pieces = " and ".join(piece_names)
        attacker_name = PIECE_NAMES.get(attacker_piece.piece_type, "piece")
        return {"category": "Missed Fork", "move_number": move_num, "description": f"You missed a fork with {best_move.uci()}. The {attacker_name} could have attacked the {forked_pieces}."}

    return None

def cp_to_win_prob(cp):
    if cp is None:
        return 0.5
    return 1 / (1 + math.exp(-0.004 * cp))

def categorize_blunder(board_before, move_played, info_before, info_after, best_move_info):
    turn_color = board_before.turn
    move_num = board_before.fullmove_number if turn_color == chess.WHITE else f"{board_before.fullmove_number}..."
    board_after = board_before.copy()
    board_after.push(move_played)

    if info_after["score"].is_mate() and info_after["score"].pov(turn_color).mate() < 0:
        mate_in = abs(info_after["score"].pov(turn_color).mate())
        return {"category": "Allowed Checkmate", "move_number": move_num, "description": f"Your move {move_played.uci()} allows the opponent to force checkmate in {mate_in} moves. The best move was {best_move_info['pv'][0].uci()}."}

    if best_move_info["score"].is_mate() and best_move_info["score"].pov(turn_color).mate() > 0:
        mate_in = best_move_info["score"].pov(turn_color).mate()
        return {"category": "Missed Checkmate", "move_number": move_num, "description": f"You missed a checkmate in {mate_in} moves. The best move was {best_move_info['pv'][0].uci()}."}
        
    material_loss = check_for_material_loss(board_before, move_played, info_after, board_after, turn_color)
    if material_loss:
        return material_loss
        
    best_move = best_move_info['pv'][0]
    missed_material = check_for_missed_material_gain(board_before, best_move_info, board_after, turn_color)
    if missed_material:
        return missed_material
    
    missed_fork = detect_fork(board_before, best_move, board_after, turn_color)
    if missed_fork:
        return missed_fork

    win_prob_before = cp_to_win_prob(info_before["score"].pov(turn_color).score(mate_score=10000))
    win_prob_after = cp_to_win_prob(info_after["score"].pov(turn_color).score(mate_score=10000))
    win_prob_drop = (win_prob_before - win_prob_after) * 100
    
    return {"category": "Mistake", "move_number": move_num, "description": f"On move {move_num}, you played {move_played.uci()}. This move dropped your win probability by {win_prob_drop:.1f}%. The best move was {best_move_info['pv'][0].uci()}."}

def analyze_game(game, engine, user_to_find, win_prob_threshold, engine_think_time):
    # ... (rest of the file is unchanged)
    # ... (I will only write the changed part of the file)
    blunders = []
    board = game.board()
    board_before = board.copy()

    for move in game.mainline_moves():
        user_color = None
        if game.headers["White"].lower() == user_to_find.lower():
            user_color = chess.WHITE
        elif game.headers["Black"].lower() == user_to_find.lower():
            user_color = chess.BLACK
        
        info_before = engine.analyse(board, chess.engine.Limit(time=engine_think_time))
        board.push(move)
        info_after = engine.analyse(board, chess.engine.Limit(time=engine_think_time))

        if board.turn != user_color and user_color is not None:
            best_move_info = info_before
            current_eval = info_after["score"].pov(user_color)
            best_eval = best_move_info["score"].pov(user_color)

            if not current_eval.is_mate() and not best_eval.is_mate():
                win_prob_before = cp_to_win_prob(best_eval.score())
                win_prob_after = cp_to_win_prob(current_eval.score())
                win_prob_drop = (win_prob_before - win_prob_after) * 100
                
                if win_prob_drop >= win_prob_threshold:
                    blunder_info = categorize_blunder(board_before, move, info_before, info_after, best_move_info)
                    if blunder_info:
                        blunders.append(blunder_info)
            
            elif best_eval.is_mate() and best_eval.mate() > 0 and not current_eval.is_mate():
                blunder_info = categorize_blunder(board_before, move, info_before, info_after, best_move_info)
                if blunder_info:
                    blunders.append(blunder_info)

            elif current_eval.is_mate() and current_eval.mate() < 0:
                 blunder_info = categorize_blunder(board_before, move, info_before, info_after, best_move_info)
                 if blunder_info:
                    blunders.append(blunder_info)

        board_before = board.copy()
        
    return blunders

def main():
    parser = argparse.ArgumentParser(description="Analyze chess games to find blunders.")
    parser.add_argument("--pgn", required=True, help="Path to the PGN file.")
    parser.add_argument("--username", required=True, help="Your chess.com username to analyze blunders for.")
    parser.add_argument("--stockfish_path", default=STOCKFISH_PATH_DEFAULT, help="Path to the Stockfish executable.")
    parser.add_argument("--win_prob_threshold", type=float, default=WIN_PROB_THRESHOLD_DEFAULT, help="Win probability drop threshold for a blunder.")
    parser.add_argument("--engine_think_time", type=float, default=ENGINE_THINK_TIME_DEFAULT, help="Engine think time per move in seconds.")
    args = parser.parse_args()

    # --- Standalone Test Mode ---
    print("--- Running analysis in standalone test mode ---\n")
    engine = chess.engine.SimpleEngine.popen_uci(args.stockfish_path)
    pgn_file = open(args.pgn)
    game_num = 1
    total_blunders = []

    while True:
        game = chess.pgn.read_game(pgn_file)
        if game is None:
            break

        white_player = game.headers.get("White", "Unknown")
        black_player = game.headers.get("Black", "Unknown")
        print(f"Analyzing game #{game_num}: {white_player} vs {black_player}")

        blunders = analyze_game(game, engine, args.username, args.win_prob_threshold, args.engine_think_time)
        
        for blunder in blunders:
            print(f"  -> {blunder['category']}: On move {blunder['move_number']}, {blunder['description']}")
            total_blunders.append(blunder)

        game_num += 1

    engine.quit()
    print("\n--- Analysis Complete ---")
    print(f"Found a total of {len(total_blunders)} mistakes/blunders for user '{args.username}'.\n")

if __name__ == "__main__":
    main()