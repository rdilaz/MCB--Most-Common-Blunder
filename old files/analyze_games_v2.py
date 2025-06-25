import chess
import chess.pgn
import chess.engine
import os 
import argparse
import math
import time

# ---- Constants ----
# path to stockfish
STOCKFISH_PATH_DEFAULT = os.path.join(os.path.dirname(__file__), "stockfish", "stockfish.exe")
# default win probability threshold for a blunder. Represents a % drop in win probability.
BLUNDER_THRESHOLD_DEFAULT = 10
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

#---- Helper Functions ----
def see(board, move):
    """
    Static Exchange Evaluation (SEE) evaluates the material gain/loss of a move.
    A positive score is favorable for the side making the move.
    """
    if not board.is_capture(move): # If the move is not a capture, the SEE is 0.
        return 0
    
    # Get value of piece on destination square
    if board.is_en_passant(move): # If the move is an en passant capture, the SEE is the value of a pawn.
        capture_value = PIECE_VALUES[chess.PAWN]
    else: # Otherwise, the SEE is the value of the captured piece.
        captured_piece = board.piece_at(move.to_square)
        if not captured_piece: return 0 # Safeguard in case piece is not found.
        capture_value = PIECE_VALUES.get(captured_piece.piece_type, 0)

    # Make the move on a temporary board
    board_after_move = board.copy()
    board_after_move.push(move)
    
    # The value of the exchange is the captured piece minus what can be recaptured by the opponent.
    value = capture_value - see_exchange(board_after_move, move.to_square)
    # --- TESTING ---
    # print(f"--- see(): Final SEE value for {move.uci()} is {value}")
    return value

def see_exchange(board, target_square):
    """
    Calculates the value of the best recapture on a square, from the perspective of the side to move.
    Used by SEE to calculate the value of a capture.
    """
    attackers = board.attackers(board.turn, target_square)
    if not attackers:
        return 0 # No attackers, exchange is over, no value lost for the opponent

    # lva: least valuable attacker 
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
    value = recapture_value - see_exchange(board_after_recapture, target_square)

    return max(0, value)

def cp_to_win_prob(cp):
    if cp is None:
        return 0.5
    return 1 / (1 + math.exp(-0.004 * cp))

#---- Blunder Categorization Functions ----
def missed_mate(best_move_info, after_move_eval, turn_color, move_num):
    """
    Checks if the player missed a forced checkmate.
    Returns a "Missed Checkmate" blunder dict if found, otherwise None.
    """
    best_move_eval = best_move_info["score"].pov(turn_color)
    
    if best_move_eval.is_mate() and best_move_eval.mate() > 0 and not after_move_eval.is_mate():
        mate_in = best_move_eval.mate()
        best_move_uci = best_move_info['pv'][0].uci()
        description = f"You missed a checkmate in {mate_in}. The best move was {best_move_uci}."
        return {"category": "Missed Checkmate", "move_number": move_num, "description": description}
        
    return None

def allowed_mate(after_move_eval, move_num, move_played, best_move_info):
    """
    Checks if the player's move allowed the opponent to force checkmate.
    Returns an "Allowed Checkmate" blunder dict if found, otherwise None.
    """
    if after_move_eval.is_mate() and after_move_eval.mate() < 0:
        mate_in = abs(after_move_eval.mate())
        best_move_uci = best_move_info['pv'][0].uci()
        description = f"Your move {move_played.uci()} allows the opponent to force checkmate in {mate_in} moves. The best move was {best_move_uci}."
        return {"category": "Allowed Checkmate", "move_number": move_num, "description": description}
        
    return None

def material_loss(board_before, move_played, board_after, turn_color):
    """
    Checks for material loss using SEE and SEE exchange.
    Returns "Losing Exchange" or "Hanging a Piece" blunder dict if a material loss is found, otherwise None.
    """
    move_num = board_before.fullmove_number if turn_color == chess.WHITE else f"{board_before.fullmove_number}..." 
    
    # Case 1: Move is a capture.
    if board_before.is_capture(move_played):
        see_value = see(board_before, move_played) # Calculate the SEE value of the move.

        if see_value < -100: # If the SEE value is negative, the move is a losing exchange.
            return {"category": "Losing Exchange", "move_number": move_num, "description": f"Your move {move_played.uci()} was a losing exchange."}

    # Case 2: Move is not a capture.
    # Check if the move hangs a piece.
    hanging_pieces = []
    for square in chess.SQUARES: # Check each square on the board.
        piece = board_after.piece_at(square)
        if piece and piece.color == turn_color: 
            attackers = board_after.attackers(not turn_color, square)
            if attackers: # If there are attackers, find the least valuable attacker.
                least_valuable_attacker_square = min(attackers, key=lambda s: PIECE_VALUES.get(board_after.piece_at(s).piece_type, 0))
                lva_piece = board_after.piece_at(least_valuable_attacker_square)
                if not lva_piece:
                    continue

                capture_move = chess.Move(least_valuable_attacker_square, square)
                # If the piece is a pawn and is on the 8th rank, promote to a queen.
                if lva_piece.piece_type == chess.PAWN and chess.square_rank(square) in [0, 7]:
                    capture_move.promotion = chess.QUEEN
                
                piece_value = PIECE_VALUES.get(piece.piece_type, 0)
                if see(board_after, capture_move) >= piece_value - 50:
                    hanging_pieces.append({'piece': piece, 'square': square})
    
    if hanging_pieces:
        most_valuable_hanging_piece_info = max(hanging_pieces, key=lambda p: PIECE_VALUES.get(p['piece'].piece_type, 0))
        piece = most_valuable_hanging_piece_info['piece']
        square = most_valuable_hanging_piece_info['square']
        piece_name = PIECE_NAMES.get(piece.piece_type, "piece")
        description = f"Your move {move_played.uci()} left your {piece_name} on {chess.square_name(square)} undefended."
        return {"category": "Hanging a Piece", "move_number": move_num, "description": description}

    return None

def missed_material_gain(board_before, best_move_info, turn_color):
    """
    Checks for missed material gain using SEE.
    Returns "Missed Material Gain" blunder dict if a missed material gain is found, otherwise None.
    """
    move_num = board_before.fullmove_number if turn_color == chess.WHITE else f"{board_before.fullmove_number}..."
    best_move = best_move_info['pv'][0]
   
    if board_before.is_capture(best_move): # If the best move is a capture, check if it is a missed material gain.
        see_value = see(board_before, best_move)
        if see_value > 100:
            return {"category": "Missed Material Gain", "move_number": move_num, "description": f"You missed a chance to win material with {best_move.uci()}."}
    return None

def missed_fork(board_before, best_move, turn_color):
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

def allowed_fork(board_after, info_after_move, turn_color):
    """
    Detects if the player's last move allowed the opponent to create a fork that wins material.
    """
    if not info_after_move.get('pv'):
        return None

    move_num = board_after.fullmove_number if turn_color == chess.WHITE else f"{board_after.fullmove_number}..."
    
    opponent_best_move = info_after_move['pv'][0]
    
    # Simulate the opponent's best move
    board_after_opponent_move = board_after.copy()
    board_after_opponent_move.push(opponent_best_move)

    # The piece the opponent just moved to create the fork
    forker_piece = board_after_opponent_move.piece_at(opponent_best_move.to_square)
    if not forker_piece:
        return None

    # Find all squares attacked by the forking piece
    attacked_squares = board_after_opponent_move.attacks(opponent_best_move.to_square)
    
    # Find pieces of the player that are now under attack
    player_pieces_attacked = []
    for attacked_square in attacked_squares:
        piece = board_after_opponent_move.piece_at(attacked_square)
        if piece and piece.color == turn_color:
            player_pieces_attacked.append({'piece': piece, 'square': attacked_square})

    # Check if at least two valuable pieces are under attack (fork)
    valuable_pieces_attacked = [p for p in player_pieces_attacked if p['piece'].piece_type > chess.PAWN]
    
    if len(valuable_pieces_attacked) >= 2:
        # Calculate the material value of the fork
        total_value_attacked = sum(PIECE_VALUES.get(p['piece'].piece_type, 0) for p in valuable_pieces_attacked)
        forker_value = PIECE_VALUES.get(forker_piece.piece_type, 0)
        
        # Only consider it a blunder if the fork wins material (attacked pieces worth more than forker)
        if total_value_attacked > forker_value:
            piece_names = [PIECE_NAMES.get(p['piece'].piece_type, "piece") for p in valuable_pieces_attacked]
            forked_pieces = " and ".join(piece_names)
            forker_name = PIECE_NAMES.get(forker_piece.piece_type, "piece")
            
            return {
                "category": "Allowed Fork",
                "move_number": move_num,
                "description": (
                    f"Your last move allows the opponent to play {opponent_best_move.uci()}, "
                    f"creating a fork with their {forker_name} that attacks your {forked_pieces}."
                )
            }
    
    return None

def detect_pin(board_before, best_move, turn_color):
    """
    Detects if the best move would have created an absolute or relative pin.
    Returns a blunder dict if a pin is missed, otherwise None.
    """
    move_num = board_before.fullmove_number if turn_color == chess.WHITE else f"{board_before.fullmove_number}..."

    # Simulate the best move
    board_with_best_move = board_before.copy()
    board_with_best_move.push(best_move)

    # Find the piece that moved (the pinner)
    pinner_piece = board_with_best_move.piece_at(best_move.to_square)
    if not pinner_piece or pinner_piece.piece_type not in [chess.QUEEN, chess.ROOK, chess.BISHOP]:
        return None # Only sliding pieces can pin

    pinner_square = best_move.to_square

    # Check for pins created by this move by looking for lines of three pieces
    for pinned_candidate_square in board_with_best_move.attacks(pinner_square):
        pinned_candidate_piece = board_with_best_move.piece_at(pinned_candidate_square)

        # The pinned piece must be an opponent's piece
        if not pinned_candidate_piece or pinned_candidate_piece.color == turn_color:
            continue

        # Find pieces on the ray from the pinner through the candidate
        ray = chess.SquareSet.ray(pinner_square, pinned_candidate_square)
        blockers_on_ray = ray & board_with_best_move.occupied
        
        if len(blockers_on_ray) < 2:
            continue
            
        squares_on_ray = sorted(list(blockers_on_ray), key=lambda s: chess.square_distance(pinner_square, s))
        
        if squares_on_ray[0] != pinned_candidate_square:
            continue
            
        target_square = squares_on_ray[1]
        target_piece = board_with_best_move.piece_at(target_square)

        if not target_piece or target_piece.color == turn_color:
            continue
            
        is_absolute_pin = (target_piece.piece_type == chess.KING)
        is_relative_pin = (PIECE_VALUES.get(target_piece.piece_type, 0) > PIECE_VALUES.get(pinned_candidate_piece.piece_type, 0))

        if is_absolute_pin or is_relative_pin:
            pin_type = "absolute" if is_absolute_pin else "relative"
            pinned_piece_name = PIECE_NAMES.get(pinned_candidate_piece.piece_type, "piece")
            pinner_name = PIECE_NAMES.get(pinner_piece.piece_type, "piece")
            target_piece_name = PIECE_NAMES.get(target_piece.piece_type, "piece")
            
            description = (
                f"You missed an {pin_type} pin with {best_move.uci()}. "
                f"The {pinner_name} could have pinned the enemy "
                f"{pinned_piece_name} on {chess.square_name(pinned_candidate_square)} to their {target_piece_name}."
            )
            return {
                "category": "Missed Pin",
                "move_number": move_num,
                "description": description
            }
            
    return None

def detect_allowed_pin(board_after, info_after_move, turn_color):
    """
    Detects if the player's last move allowed the opponent to create an absolute or relative pin.
    """
    if not info_after_move.get('pv'):
        return None

    move_num = board_after.fullmove_number if turn_color == chess.WHITE else f"{board_after.fullmove_number}..."
    
    opponent_best_move = info_after_move['pv'][0]
    pinner_square = opponent_best_move.to_square

    board_after_opponent_move = board_after.copy()
    board_after_opponent_move.push(opponent_best_move)

    pinner_piece = board_after_opponent_move.piece_at(pinner_square)
    if not pinner_piece or pinner_piece.piece_type not in [chess.QUEEN, chess.ROOK, chess.BISHOP]:
        return None
    
    for pinned_candidate_square in board_after_opponent_move.attacks(pinner_square):
        pinned_candidate_piece = board_after_opponent_move.piece_at(pinned_candidate_square)

        if not pinned_candidate_piece or pinned_candidate_piece.color != turn_color:
            continue

        ray = chess.SquareSet.ray(pinner_square, pinned_candidate_square)
        blockers_on_ray = ray & board_after_opponent_move.occupied
        
        if len(blockers_on_ray) < 2:
            continue
            
        squares_on_ray = sorted(list(blockers_on_ray), key=lambda s: chess.square_distance(pinner_square, s))
        
        if squares_on_ray[0] != pinned_candidate_square:
            continue
            
        target_square = squares_on_ray[1]
        target_piece = board_after_opponent_move.piece_at(target_square)

        if not target_piece or target_piece.color != turn_color:
            continue
            
        is_absolute_pin = (target_piece.piece_type == chess.KING)
        is_relative_pin = (PIECE_VALUES.get(target_piece.piece_type, 0) > PIECE_VALUES.get(pinned_candidate_piece.piece_type, 0))

        if is_absolute_pin or is_relative_pin:
            pin_type = "absolute" if is_absolute_pin else "relative"
            pinned_piece_name = PIECE_NAMES.get(pinned_candidate_piece.piece_type, "piece")
            pinner_name = PIECE_NAMES.get(pinner_piece.piece_type, "piece")
            target_piece_name = PIECE_NAMES.get(target_piece.piece_type, "piece")
            
            description = (
                f"Your last move allows the opponent to play {opponent_best_move.uci()}, creating an {pin_type} pin. "
                f"Their {pinner_name} would pin your {pinned_piece_name} on {chess.square_name(pinned_candidate_square)} to your {target_piece_name}."
            )
            return {
                "category": "Allowed Pin",
                "move_number": move_num,
                "description": description
            }
            
    return None

def categorize_blunder(board_before, board_after, move_played, info_before_move, info_after_move, best_move_info, blunder_threshold):
    """
    Categorization pipeline. Tries to find the most specific blunder category.
    Returns a dictionary with blunder info, or a general "Mistake" if no specific category is found.
    """
    turn_color = board_before.turn
    move_num = board_before.fullmove_number if turn_color == chess.WHITE else f"{board_before.fullmove_number}..."
    after_move_eval = info_after_move["score"].pov(turn_color)
    
    # ---- Blunder Categorization Pipeline ----
    # Functions checked in order of severity
    # 1) Mates
    # allowed mate
    allowed_mate_flag = allowed_mate(after_move_eval, move_num, move_played, best_move_info)
    if allowed_mate_flag:
        return allowed_mate_flag
    # missed mate
    missed_mate_flag = missed_mate(best_move_info, after_move_eval, turn_color, move_num)
    if missed_mate_flag:
        return missed_mate_flag
    
    # 2) Tactical Blunders (Material, Forks, Pins)
    allowed_pin_flag = detect_allowed_pin(board_after, info_after_move, turn_color)
    if allowed_pin_flag:
        return allowed_pin_flag
        
    allowed_fork_flag = allowed_fork(board_after, info_after_move, turn_color)
    if allowed_fork_flag:
        return allowed_fork_flag
    
    material_loss_flag = material_loss(board_before, move_played, board_after, turn_color)
    if material_loss_flag:
        return material_loss_flag
        
    best_move = best_move_info['pv'][0]
    missed_material_gain_flag = missed_material_gain(board_before, best_move_info, turn_color)
    if missed_material_gain_flag:
        return missed_material_gain_flag
    
    missed_fork_flag = missed_fork(board_before, best_move, turn_color)
    if missed_fork_flag:
        return missed_fork_flag

    missed_pin_flag = detect_pin(board_before, best_move, turn_color)
    if missed_pin_flag:
        return missed_pin_flag

    # 3) All other Blunders: Categorize as "Mistake"
    win_prob_before = cp_to_win_prob(info_before_move["score"].pov(turn_color).score(mate_score=10000))
    win_prob_after = cp_to_win_prob(info_after_move["score"].pov(turn_color).score(mate_score=10000))
    win_prob_drop = (win_prob_before - win_prob_after) * 100
    
    if win_prob_drop >= blunder_threshold:
        description = f"your move {move_played.uci()} dropped your win probability by {win_prob_drop:.1f}%. The best move was {best_move_info['pv'][0].uci()}."
        return {"category": "Mistake", "move_number": move_num, "description": description}
    return None

def analyze_game(game, engine, target_user, blunder_threshold, engine_think_time):
    """
    Analyzes a single game for a specific user, identifies blunders,
    and returns a list of categorized blunder dictionaries.
    """
    blunders = [] # whenever a move is a blunder, dictionary of blunder stored in blunders array which is returned by function
    board = game.board() # initialize board state as starting position
    user_color = None # stores color of target user

    # ---- find target user's color ----
    if game.headers.get("White", "").lower() == target_user.lower():
        user_color = chess.WHITE
    elif game.headers.get("Black", "").lower() == target_user.lower():
        user_color = chess.BLACK
    if user_color is None: # if user not found, exit and return empty blunder list
        print(f"User '{target_user}' not found in this game. Skipping.")
        return []

    # ---- detect/categorize blunders ----
    for move in game.mainline_moves(): # for each move actually played in the game (skips side variations)
        if board.turn == user_color: # if it's the target user's turn
            # ---- get eval before and after the move as well as eval of best move ----
            board_before = board.copy() # get board state before the move
            info_before_move = engine.analyse(board, chess.engine.Limit(time=engine_think_time)) # get eval and best move from before the move was made
            best_move_info = info_before_move # alias for the best move info (taken from before the move was made)
            board.push(move) # make target player's move
            info_after_move = engine.analyse(board, chess.engine.Limit(time=engine_think_time)) # get eval from after the move was made

            # ---- pass to blunder categorization function ----
            blunder_info = categorize_blunder(board_before, board, move, info_before_move, info_after_move, best_move_info, blunder_threshold)
            if blunder_info:
                blunders.append(blunder_info)
        else:
            board.push(move)
    
    return blunders

def main():
    parser = argparse.ArgumentParser(description="Analyze chess games to find blunders.")
    # Set default values for pgn and username for easy testing.
    # They are no longer 'required'.
    parser.add_argument("--pgn", default="testgames.pgn", help="Path to the PGN file (default: testgames.pgn).")
    parser.add_argument("--username", default="test", help="Your username to analyze blunders for (default: test).")
    
    parser.add_argument("--stockfish_path", default=STOCKFISH_PATH_DEFAULT, help="Path to the Stockfish executable.")
    parser.add_argument("--blunder_threshold", type=float, default=BLUNDER_THRESHOLD_DEFAULT, help="Win probability drop threshold for a blunder.")
    parser.add_argument("--engine_think_time", type=float, default=ENGINE_THINK_TIME_DEFAULT, help="Engine think time per move in seconds.")
    args = parser.parse_args()

    start_time = time.time()
    print("--- Running analysis in standalone test mode ---\n")
    engine = chess.engine.SimpleEngine.popen_uci(args.stockfish_path)
    
    total_blunders = []
    try:
        with open(args.pgn) as pgn_file:
            game_num = 1
            while True:
                game = chess.pgn.read_game(pgn_file)
                if game is None:
                    break

                white_player = game.headers.get("White", "Unknown")
                black_player = game.headers.get("Black", "Unknown")
                print(f"Analyzing game #{game_num}: {white_player} vs {black_player}")

                blunders = analyze_game(game, engine, args.username, args.blunder_threshold, args.engine_think_time)
                
                for blunder in blunders:
                    print(f"  -> {blunder['category']}: On move {blunder['move_number']}, {blunder['description']}")
                total_blunders.extend(blunders)
                game_num += 1
    except FileNotFoundError:
        print(f"Error: The file '{args.pgn}' was not found.")
    finally:
        print("\n--- Quitting engine ---")
        engine.quit()

    end_time = time.time()
    print(f"\n--- Analysis Complete in {end_time - start_time:.2f} seconds ---")
    print(f"Found a total of {len(total_blunders)} mistakes/blunders for user '{args.username}'.\n")

if __name__ == "__main__":
    main()