import chess
import chess.pgn
import chess.engine
import os 

# ================= 
# Configuration
# ================= 
try:
    STOCKFISH_PATH = os.path.join(os.path.dirname(__file__), "stockfish", "stockfish.exe")
    if not os.path.exists(STOCKFISH_PATH):
       raise FileNotFoundError
except FileNotFoundError:
    print("Error: Stockfish executable not found. Please ensure it is in the 'stockfish' directory.")
    exit()

# path to the pgn file to analyze
PGN_FILE_NAME = "roygbiv6_last_3_rapid_games.pgn"

# define blunder as move that woresens position by a lot (300 centipawns as default)
BLUNDER_THRESHOLD = 250

# define how long the engine should think per move (in seconds)
# 0.1 is fast, 1.0 is accurate.
ENGINE_TIME_PER_MOVE = 0.5

# define player name
PLAYER_NAME = "roygbiv6"
# ======================

def get_pov_score(score_obj, player_color):
    """converts a score object to the perspective of the player color"""
    if score_obj.is_mate():
        # A mate score is great if positive, bad if negative
        return 100000 * score_obj.pov(player_color).mate()
    else:
        # a centipawn score
        return score_obj.pov(player_color).score()
    
def analyze_game_for_blunders(game, engine):
    """Analyzes a single game for blunders made by the player"""
    blunders = []
    board = game.board()
    player_to_track= PLAYER_NAME.lower()

    white_player = game.headers.get("White", "?").lower()
    black_player = game.headers.get("Black", "?").lower()

    print(f"\nAnalyzing game: {game.headers.get('White', '?')} vs {game.headers.get('Black', '?')}")

    for move in game.mainline_moves():
        # determine whose turn it was before the move was made
        turn_color = board.turn
        is_player_turn = (turn_color == chess.WHITE and white_player == player_to_track) or \
                         (turn_color == chess.BLACK and black_player == player_to_track)
        
        if not is_player_turn:
            board.push(move)
            continue # skip analysis if it's not the player's turn

        # 1 analyze BEFORE the move, from perspective of player whose turn it is
        info_before = engine.analyse(board, chess.engine.Limit(time=ENGINE_TIME_PER_MOVE))
        score_before = get_pov_score(info_before["score"], turn_color)

        # 2 make the move
        board.push(move)

        # if the move resulted in checkmate, skip the rest of the analysis
        if board.is_checkmate():
            continue

        # 3 analyze AFTER the move, from perspective of player whose turn it is
        info_after = engine.analyse(board, chess.engine.Limit(time=ENGINE_TIME_PER_MOVE))
        
        
        score_after = get_pov_score(info_after["score"], turn_color)

        # 4 calculate the drop in evaluation
        evaluation_drop = score_before - score_after

        # 5 check if it's a blunder
        if evaluation_drop >= BLUNDER_THRESHOLD:
            move_num = board.fullmove_number if turn_color == chess.WHITE else f"{board.fullmove_number-1}..."
            blunder_info = {
                "move_number": move_num,
                "move": move.uci(),
                "evaluation_drop": evaluation_drop,
                "fen_before_move": board.fen(en_passant="fen")
            }
            blunders.append(blunder_info)
            print(f"  -> Blunder found: Move {blunder_info['move_number']} ({blunder_info['move']}), Eval Drop: {blunder_info['evaluation_drop']}cp")
    return blunders
    
def main():
    """Main function to analyze all games in the PGN file"""
    print("----MCB Blunder Analysis----")
    try:
        with open(PGN_FILE_NAME, encoding="utf-8") as pgn_file:
            with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
                game_count = 0
                all_blunders = []
                while True:
                    # new try/except block for potentially malformed PGN
                    try:
                        game = chess.pgn.read_game(pgn_file)
                        if game is None:
                            break # end of file
                    except Exception as e:
                        print(f"Error reading game: {e}")
                        continue # skip this game and move to the next
                        
                    game_count += 1
                    blunders_found = analyze_game_for_blunders(game, engine)
                    all_blunders.extend(blunders_found)
            print(f"\n--- Analysis Complete ---")
            print(f"Analyzed {game_count} games for user '{PLAYER_NAME}'.")
            print(f"Found a total of {len(all_blunders)} blunders.")
    except FileNotFoundError:
        print(f"ERROR: PGN file not found: '{PGN_FILE_NAME}'")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
                        
if __name__ == "__main__":
    main()