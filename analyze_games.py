import chess
import chess.pgn
import chess.engine
import os
import argparse

STOCKFISH_PATH_DEFAULT = os.path.join(os.path.dirname(__file__), "stockfish", "stockfish.exe")
BLUNDER_THRESHOLD_DEFAULT = 300
ENGINE_THINK_TIME_DEFAULT = 0.1

def get_pov_score(score_obj, player_color):
    """Converts a score object to an integer from the perspective of the player color."""
    if score_obj.is_mate():
        mate_in_x = score_obj.pov(player_color).mate()
        return 100000 - (abs(mate_in_x) * 10)
    else:
        return score_obj.pov(player_color).score()

def find_blunders(pgn_filename, stockfish_path, player_name, threshold, think_time):
    """
    Analyzes a PGN file for a player's blunders and returns a list of them.
    """
    if not os.path.exists(stockfish_path):
        print(f"ERROR: Stockfish not found at '{stockfish_path}'")
        return None

    all_blunders = []
    try:
        with open(pgn_filename, encoding='utf-8') as pgn_file:
            with chess.engine.SimpleEngine.popen_uci(stockfish_path) as engine:
                while True:
                    game = chess.pgn.read_game(pgn_file)
                    if game is None:
                        break

                    board = game.board()
                    white_player = game.headers.get("White", "?").lower()
                    black_player = game.headers.get("Black", "?").lower()
                    
                    print(f"\nAnalyzing game: {game.headers.get('White', '?')} vs {game.headers.get('Black', '?')}")

                    for move in game.mainline_moves():
                        turn_color = board.turn
                        is_player_turn = (turn_color == chess.WHITE and white_player == player_name.lower()) or \
                                         (turn_color == chess.BLACK and black_player == player_name.lower())
                        
                        if not is_player_turn:
                            board.push(move)
                            continue

                        info_before = engine.analyse(board, chess.engine.Limit(time=think_time))
                        score_before = get_pov_score(info_before["score"], turn_color)
                        board.push(move)

                        if board.is_checkmate():
                            continue
                        
                        info_after = engine.analyse(board, chess.engine.Limit(time=think_time))
                        score_after = get_pov_score(info_after["score"], turn_color)
                        evaluation_drop = score_before - score_after

                        if evaluation_drop >= threshold:
                            move_num = board.fullmove_number if turn_color == chess.WHITE else f"{board.fullmove_number-1}..."
                            blunder_info = {
                                "move_number": move_num,
                                "move": move.uci(),
                                "evaluation_drop": evaluation_drop,
                                "fen_before_move": board.fen(en_passant="fen"),
                                "game_link": game.headers.get("Link", "#")
                            }
                            all_blunders.append(blunder_info)
                            print(f"  -> Blunder found: Move {blunder_info['move_number']} ({blunder_info['move']}), Eval Drop: {blunder_info['evaluation_drop']}cp")
    except FileNotFoundError:
        print(f"ERROR: PGN file not found: '{pgn_filename}'")
        return None
    
    return all_blunders

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze a PGN file for a player's blunders.")
    parser.add_argument("--pgn", type=str, required=True, help="Path to the PGN file to analyze.")
    parser.add_argument("--username", type=str, required=True, help="The username of the player to analyze.")
    parser.add_argument("--think_time", type=float, default=ENGINE_THINK_TIME_DEFAULT, help="Engine think time per move in seconds.")
    parser.add_argument("--threshold", type=int, default=BLUNDER_THRESHOLD_DEFAULT, help="Centipawn drop to be considered a blunder.")
    args = parser.parse_args()

    print("\n--- Running analysis in standalone test mode ---")
    blunders_found = find_blunders(
        pgn_filename=args.pgn,
        stockfish_path=STOCKFISH_PATH_DEFAULT,
        player_name=args.username,
        threshold=args.threshold,
        think_time=args.think_time
    )
    if blunders_found is not None:
        print(f"\n--- Analysis Complete ---")
        print(f"Found a total of {len(blunders_found)} blunders for user '{args.username}'.")