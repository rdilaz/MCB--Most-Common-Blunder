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
# Standard Piece Value in Centipawns
PIECE_VALUES = {

    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 950,
    chess.KING: 200000
}
# ---------------------------------------
# Helper Functions
# ---------------------------------------

# # Calculate the Static Exchange Evaluation (SEE) for a move.
# # Determines material gain/loss from a series of captures on the mov's target square.
# # A positive score is favorable for the moving side. 
# def see(board: chess.Board, move: chess.Move) -> int:
#     if not move.is_capture(): return 0

#     gain = [0]
#     from_sq = move.from_square
#     to_sq = move.to_square

#     # Initial Capture
#     captured_piece_type = board.piece_type_at(to_sq)
#     if captured_piece_type is None:
#         return 0
#     gain.append(PIECE_VALUES.get(captured_piece_type, 0))
    
#     side_to_move = board.turn
#     attack_piece_type = board.piece_type_at(from_sq)

#     # create copy of board to simulate exchange
#     temp_board = board.copy(stack=False)
#     temp_board.push(move)
#     side_to_move = not temp_board.turn

#     while True:
#         attackers = temp_board.attackers(side_to_move, to_sq)
#         if not attackers:
#             break
#         # find least valuable attacker
#         lva_square = -1
#         min_piece_value = float('inf')
#         for attacker_sq in attackers:
#             piece_val = PIECE_VALUES.get(temp_board.piece_type_at(attacker_sq), 0)
#             if piece_val < min_piece_value:
#                 min_piece_value = piece_val
#                 lva_square = attacker_sq

#         if lva_square == -1:
#             break
        
#         gain.append(PIECE_VALUES.get(attack_piece_type, 0) - gain[-1])

#         # Simulate the capture by the least valuable attacker
#         attack_piece_type = temp_board.piece_type_at(lva_square)
#         temp_board.remove_piece_at(lva_square)
#         temp_board.set_piece_at(to_sq, chess.Piece(attack_piece_type, side_to_move))
#         side_to_move = not side_to_move

#     # Negamax the gain list to find the final score
#     while len(gain) > 1:
#         gain[-2] = max(-gain[-1], gain[-2])
#         gain.pop()

#     return gain[0]



# Converts a score object (from Stockfish) to an integer used for calculations.
# This number is always from the perspective of the target player.
def get_pov_score(score_obj, player_color):
    # The score object from Stockfish is always either a mate score or a centipawn score.
    # So if it's a mate score:
    if score_obj.is_mate():
        # get mate in x object from the perspective of the player.
        # note, positive score means player can force mate in x moves.
        # negative score means opponent can force mate in x moves.
        mate_in_x = score_obj.pov(player_color).mate()
        # if positive, return large positive value. if negative, return large negative value.
        # subtract mateinx * 10 to differentiate between mates of different lengths (Min1: 99990, Min2: 99980, etc)
        return (100000 if mate_in_x > 0 else -100000) - (mate_in_x * 10)
    else:
        # if it's a centipawn score, just return the score.
        return score_obj.pov(player_color).score()

# Modern logic, converts centipawns to win probability using a sigmoid function.
# Win probability is preferred becuase change in centipawns have different impacts 
# depending on the current win probability of the player. 
# (i.e. -200 centipawns is weighted more if position is equal 
# than if player is close to winning)
def get_win_probability(centipawns: int) -> float:
    """Converts a centipawn evaluation to a win probability (0.0 to 100.0)."""
    # Formula inspired by Lichess's win probability formula.
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * centipawns)) - 1)
    
# Compares current move and engines best move,decides if its a blunder, and if so, what category.
# Checks for most severe blunders first, then moves down the list.
# info returned if blunder is found currently includes:
# - category
# - move number
 # - description
def categorize_blunder(engine, board_before, move_played, best_move_info, win_prob_threshold, think_time):
    # Get color of target player
    turn_color = board_before.turn

    # Check 1: "Missed Checkmate"
    # Check best move, if it was checkmate 
    if best_move_info["score"].is_mate() and best_move_info["score"].pov(turn_color).mate() > 0:
        # Return info about blunder
        temp_board = board_before.copy(); temp_board.push(move_played)
        move_num = temp_board.fullmove_number if turn_color == chess.WHITE else f"{temp_board.fullmove_number-1}..."
        return {"category": "Missed Checkmate", "move_number": move_num, "description": f"You missed a checkmate in {best_move_info['score'].pov(turn_color).mate()} moves."}

    # Check 2: "Allowed Checkmate"
    # Create temp board se see position after player move, then analyze that position.
    board_after = board_before.copy(); board_after.push(move_played)
    info_after = engine.analyse(board_after, chess.engine.Limit(time=think_time))

    # if the move allowed opponent to force checkmate, return info about blunder
    if info_after["score"].is_mate() and info_after["score"].pov(turn_color).mate() < 0:
        move_num = board_after.fullmove_number if turn_color == chess.WHITE else f"{board_after.fullmove_number-1}..."
        return {"category": "Allowed Checkmate", "move_number": move_num, "description": f"Your move allows the opponent to force checkmate in {abs(info_after['score'].pov(turn_color).mate())} moves."}

    # Bottom Check: "Mistake"
    # If no other more severe blunder is found above, check if the move is at least a mistake.
    # get win prob of best move
    cp_best_move = get_pov_score(best_move_info["score"], turn_color) 
    win_prob_best_move = get_win_probability(cp_best_move)  
     # get win prob of move after played move
    cp_after_player_move = get_pov_score(info_after["score"], turn_color)
    win_prob_after_player_move = get_win_probability(cp_after_player_move)

    # Calculate win probability diff
    win_prob_drop = win_prob_best_move - win_prob_after_player_move

    # If win prob drop is greater than threshold, return info about blunder
    if win_prob_drop >= win_prob_threshold:
        move_num = board_after.fullmove_number if turn_color == chess.WHITE else f"{board_after.fullmove_number-1}..."
        return {
            "category": "Mistake",
            "move_number": move_num,
            "description": f"This move dropped your win probability by {round(win_prob_drop, 1)}%.",
            "win_prob_drop": round(win_prob_drop, 2),
            "eval_after": cp_after_player_move,
            "eval_before": cp_best_move, 
        }
    
    # If no blunder is found, return None
    return None

# Analyzes each move in a game.
# Calls categorize_blunder for each move.
# Returns list of blunders found.
def find_blunders(pgn_filename, stockfish_path, player_name, win_prob_threshold, think_time):
    if not os.path.exists(stockfish_path): return None
    all_blunders = []
    try:
        # Open pgn bulk file
        with open(pgn_filename, encoding='utf-8') as pgn_file:
            # Start engine only once for efficiency
            with chess.engine.SimpleEngine.popen_uci(stockfish_path) as engine:
                game_count = 0
                # Iterate through each game in the pgn file
                while True:
                    game = chess.pgn.read_game(pgn_file)
                    if game is None: break # End of file
                    game_count += 1
                    board = game.board() # Get board object for current game
                    white_player = game.headers.get("White", "?").lower() # Get white player
                    black_player = game.headers.get("Black", "?").lower() # Get black player
                    print(f"\nAnalyzing game #{game_count}: {white_player} vs {black_player}")
                    # Iterate through each move in the game
                    for move in game.mainline_moves():
                        # Get color of current turn and check if its the players turn
                        turn_color = board.turn 
                        is_player_turn = (turn_color == chess.WHITE and white_player == player_name.lower()) or \
                                         (turn_color == chess.BLACK and black_player == player_name.lower()) 
                        
                        board_before_move = board.copy() # Get board before move
                        board.push(move) # Play a move on board

                        # If its not target players turn, skip to next move
                        if not is_player_turn: continue

                        # If it is target players turn, analyze move
                        analysis_results = engine.analyse(board_before_move, chess.engine.Limit(time=think_time), multipv=1)
                        best_move_info = analysis_results[0]

                        # Categorize blunder
                        blunder_data = categorize_blunder(engine, board_before_move, move, best_move_info, win_prob_threshold, think_time)
                        if blunder_data:
                            # Update blunder data with move info
                            blunder_data.update({
                                "move_played": move.uci(),
                                "best_move": best_move_info['pv'][0].uci(),
                                "fen_before_move": board_before_move.fen(),
                                "game_link": game.headers.get("Link", "#")})
                            all_blunders.append(blunder_data)
                            print(f"  -> {blunder_data['category']}: On move {blunder_data['move_number']}, you played {blunder_data['move_played']}. {blunder_data['description']} The best move was {blunder_data['best_move']}.")
    except FileNotFoundError: return None
    return all_blunders

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze a PGN file for a player's blunders.")
    parser.add_argument("--pgn", type=str, required=True, help="Path to the PGN file to analyze.")
    parser.add_argument("--username", type=str, required=True, help="The username of the player to analyze.")
    parser.add_argument("--think_time", type=float, default=ENGINE_THINK_TIME_DEFAULT, help="Engine think time per move in seconds.")
    parser.add_argument("--threshold", type=float, default=WIN_PROB_THRESHOLD_DEFAULT, help="Win probability drop to be considered a mistake (e.g., 20.0 for a blunder).")
    args = parser.parse_args()
    print("\n--- Running analysis in standalone test mode ---")
    blunders_found = find_blunders(pgn_filename=args.pgn, stockfish_path=STOCKFISH_PATH_DEFAULT, player_name=args.username, win_prob_threshold=args.threshold, think_time=args.think_time)
    if blunders_found is not None:
        print(f"\n--- Analysis Complete ---")
        print(f"Found a total of {len(blunders_found)} mistakes/blunders for user '{args.username}'.")