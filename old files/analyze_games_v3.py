import chess
import chess.pgn
import chess.engine
import os 
import argparse
import math
import time  # <-- Add this at the top with other imports

# ---- Constants ----
STOCKFISH_PATH_DEFAULT = os.path.join(os.path.dirname(__file__), "stockfish", "stockfish.exe")
BLUNDER_THRESHOLD_DEFAULT = 15
ENGINE_THINK_TIME_DEFAULT = 0.1
BLUNDER_CATEGORY_PRIORITY = {
    "Allowed Checkmate": 1,
    "Missed Checkmate": 2,
    "Allowed Fork": 3,
    "Missed Fork": 4,
    "Allowed Pin": 5,
    "Missed Pin": 6,
    "Hanging a Piece": 7,
    "Losing Exchange": 8,
    "Missed Material Gain": 9,
    "Mistake": 10
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
    """
    Static Exchange Evaluation (SEE) calculates material gain/loss of a move 
    by simulating all possible captures and recaptures on a square. 
    A positive score is favorable for the side making the move.
    Used By: Material Loss and Missed Material Gain check functions.
    Uses: SEE exchange.
    Time complexity: O(d) where d is the depth of the search (typically 2-6 moves/calls).
    """
    if not board.is_capture(move): return 0 # if not a capture, no material exchange, value = 0.
    if board.is_en_passant(move): # if en passant capture, value = pawn (100).
        capture_value = PIECE_VALUES[chess.PAWN]
    else: # if not en passant capture, value = value of captured piece.
        captured_piece = board.piece_at(move.to_square) # get the piece that was captured.
        if not captured_piece: return 0 # saftey, if no piece was captured, value = 0.
        capture_value = PIECE_VALUES.get(captured_piece.piece_type, 0) # get the value of the captured piece.
    board_after_move = board.copy() # copy board 
    board_after_move.push(move) # apply move to copied board.
    value = capture_value - see_exchange(board_after_move, move.to_square) # recursive call for recaptures.
    return value

def see_exchange(board, target_square):
    """
    Calculates the value of the best recapture on a square, from the perspective of the side to move.
    Used By: SEE to calculate the value of a capture.
    Time complexity: O(d) where d is the depth of the recapture sequence (typically 2-6 moves/calls).
    """
    attackers = board.attackers(board.turn, target_square) # find all attackers of target square
    if not attackers: return 0 # saftey, if no attackers return 0
    lva_square = min(attackers, key=lambda s: PIECE_VALUES.get(board.piece_at(s).piece_type, 0)) # least valuable attacker
    lva_piece = board.piece_at(lva_square)  # get lva piece
    if not lva_piece: return 0 # saftey, if no lva piece return 0
    recapture_value = PIECE_VALUES.get(lva_piece.piece_type, 0) # get value of lva piece
    board_after_recapture = board.copy() # copy board for simulation
    recapture_move = chess.Move(lva_square, target_square) # create recapture move 
    if lva_piece.piece_type == chess.PAWN and chess.square_rank(target_square) in [0, 7]: # if pawn promotion, assume promotion to queen
        recapture_move.promotion = chess.QUEEN # promote to queen
    board_after_recapture.push(recapture_move) # apply recapture move to copied board
    value = recapture_value - see_exchange(board_after_recapture, target_square) # recursive call for recaptures
    return max(0, value)

def cp_to_win_prob(cp):
    """
    Converts a centipawn evaluation to a win probability using a logistic function.
    For more accurate assessment of board.
    Used By: Categorize Blunder function.
    Time complexity: O(1) 
    """
    if cp is None: return 0.5
    return 1 / (1 + math.exp(-0.004 * cp))

def get_absolute_pins(board, color):
    """
    Returns a list of (pinned_square, pinner_square) tuples for all absolute pins
    of the given color on the board.
    Absolute pin is when a piece is pinned to the king.
    Used By: check for pin functions.
    Time complexity: O(64) = O(1) 
    """
    pins = [] # initialize list of pins
    king_square = board.king(color) # get king square
    if king_square is None: # saftey, if no king, return empty list
        return pins
    for square in chess.SQUARES: # iterate over all squares
        piece = board.piece_at(square) # get piece at square
        if piece and piece.color == color and board.is_pinned(color, square): # if piece is of color and pinned
            pinner_square = board.pin(color, square) # get pinner square
            pins.append((square, pinner_square)) # add pin to list
    return pins

#---- Blunder Categorization Functions ----
def check_for_missed_mate(board_before, best_move_info, after_move_eval, turn_color, move_num, move_played):
    """
    Checks if the player missed a forced checkmate.
    Returns a 'Missed Checkmate' blunder dict if found, otherwise None.
    Used By: Categorize Blunder function.
    Time complexity: O(1) 
    """
    best_move_eval = best_move_info["score"].pov(turn_color) # get best move evaluation
    if best_move_eval.is_mate() and best_move_eval.mate() > 0 and not after_move_eval.is_mate(): # if best move is a checkmate and players move is not a checkmate
        mate_in = best_move_eval.mate() # get mate count
        best_move = best_move_info['pv'][0] # get best move
        move_played_san = board_before.san(move_played) # convert move to SAN format
        best_move_san = board_before.san(best_move) # convert move to SAN format
        description = f"your move {move_played_san} missed a checkmate in {mate_in}. The best move was {best_move_san}." # create description
        return {"category": "Missed Checkmate", "move_number": move_num, "description": description} # return blunder dict
    return None

def check_for_allowed_mate(board_before, after_move_eval, move_num, move_played, info_after_move):
    """
    Checks if the player's move allowed the opponent to force a checkmate.
    Returns an 'Allowed Checkmate' blunder dict if found, otherwise None.
    Used By: Categorize Blunder function.
    Time complexity: O(1) 
    """
    if after_move_eval.is_mate() and after_move_eval.mate() < 0: # check if opponent can mate
        punishing_move = info_after_move['pv'][0] if info_after_move.get('pv') else None # get opponents best move
        move_played_san = board_before.san(move_played) # convert move to SAN format
        description = f"your move {move_played_san} allows the opponent to force checkmate in {abs(after_move_eval.mate())}." # create description
        return {"category": "Allowed Checkmate", "move_number": move_num, "description": description, "punishing_move": punishing_move} # return blunder dict
    return None

def check_for_material_loss(board_before, move_played, board_after, turn_color):
    """
    Checks for material loss using SEE and SEE exchange.
    Returns 'Losing Exchange' or 'Hanging a Piece' blunder dict if a material loss is found, otherwise None.
    Used By: Categorize Blunder function.
    Uses: SEE.
    Time complexity: O(64) = O(1) 
    """
    move_num = board_before.fullmove_number # get move number
    move_played_san = board_before.san(move_played) # convert move to SAN format
    if board_before.is_capture(move_played): # check if move is a capture
        see_value = see(board_before, move_played) # get see value
        if see_value < -100: # if losing more than a pawn worth of material
            captured_piece = board_before.piece_at(move_played.to_square) # get captured piece
            captured_piece_name = PIECE_NAMES.get(captured_piece.piece_type, "piece") if captured_piece else "piece" # get piece name
            net_loss = abs(see_value) # calculate net loss
            description = f"your move {move_played_san} initiates a losing exchange. You capture a {captured_piece_name} but lose {net_loss} centipawns in the sequence." # create description
            return {"category": "Losing Exchange", "move_number": move_num, "description": description, "punishing_move": None} # return blunder dict
    hanging_pieces = [] # initialize list of hanging pieces
    for square in chess.SQUARES: # iterate over all squares
        piece = board_after.piece_at(square) # get piece at square
        if piece and piece.color == turn_color: # check if its player's piece 
            attackers = board_after.attackers(not turn_color, square) # get the attackers of that square
            if attackers: 
                lva_square = min(attackers, key=lambda s: PIECE_VALUES.get(board_after.piece_at(s).piece_type, 0))  # find lva square
                lva_piece = board_after.piece_at(lva_square) # get lva piece
                if not lva_piece: continue # saftey, if no lva piece, continue
                capture_move = chess.Move(lva_square, square) # create capture move
                if lva_piece.piece_type == chess.PAWN and chess.square_rank(square) in [0, 7]: # if pawn promotion, assume promotion to queen
                    capture_move.promotion = chess.QUEEN
                piece_value = PIECE_VALUES.get(piece.piece_type, 0) # get value of piece
                if see(board_after, capture_move) >= piece_value - 50: # if capture is worth more than 50 points
                    piece_name = PIECE_NAMES.get(piece.piece_type, "piece") # get name of piece
                    description = f"your move {move_played_san} left your {piece_name} on {chess.square_name(square)} undefended." # create description
                    hanging_pieces.append({"category": "Hanging a Piece", "move_number": move_num, "description": description, "punishing_move": capture_move})
    if hanging_pieces:
        return hanging_pieces[0]
    return None

def check_for_missed_material_gain(board_before, best_move_info, move_played):
    """
    Checks for missed material gain.
    Returns 'Missed Material Gain' blunder dict if a missed material gain is found, otherwise None.
    Used By: Categorize Blunder function.
    Uses: SEE.
    Time complexity: O(1) 
    """
    move_num = board_before.fullmove_number # get move number
    if not best_move_info.get('pv'): return None # saftey, if no best move, return None
    best_move = best_move_info['pv'][0] # get best move
    if board_before.is_capture(best_move): # check if best move is a capture
        if see(board_before, best_move) > 100: # if capture is worth more than 100 points
            captured_piece = board_before.piece_at(best_move.to_square) # get captured piece
            piece_name = PIECE_NAMES.get(captured_piece.piece_type, "material") if captured_piece else "material" # get piece name
            best_move_san = board_before.san(best_move) # convert move to SAN format
            move_played_san = board_before.san(move_played) # convert move to SAN format
            description = f"your move {move_played_san} missed a chance to win a {piece_name} with {best_move_san}." # create description
            return {"category": "Missed Material Gain", "move_number": move_num, "description": description, "punishing_move": best_move} # return blunder dict
    return None

def check_for_missed_fork(board_before, best_move_info, turn_color, move_played):
    """
    Checks if the best move would have created a fork.
    Returns a 'Missed Fork' blunder dict if found, otherwise None.
    Used By: Categorize Blunder function.
    Time complexity: O(1) 
    """
    if not best_move_info.get('pv'): return None # saftey, if no best move, return None
    move_num = board_before.fullmove_number # get move number
    best_move = best_move_info['pv'][0] # get best move
    
    board_with_best_move = board_before.copy() # copy board
    board_with_best_move.push(best_move) # apply best move to copied board
    attacker_piece = board_with_best_move.piece_at(best_move.to_square) # get attacker piece
    if not attacker_piece: return None # saftey, if no attacker piece, return None
    attacked_squares = board_with_best_move.attacks(best_move.to_square) # get attacked squares
    opponent_pieces_attacked = [board_with_best_move.piece_at(sq) for sq in attacked_squares if board_with_best_move.piece_at(sq) and board_with_best_move.piece_at(sq).color != turn_color] # get opponent pieces attacked
    valuable_pieces_attacked = [p for p in opponent_pieces_attacked if p.piece_type > chess.PAWN] # get valuable pieces attacked
    if len(valuable_pieces_attacked) >= 2: # if at least 2 valuable pieces are attacked
        piece_names = [PIECE_NAMES.get(p.piece_type, "piece") for p in valuable_pieces_attacked] # get piece names
        forked_pieces = " and ".join(piece_names) # join piece names
        attacker_name = PIECE_NAMES.get(attacker_piece.piece_type, "piece") # get attacker name
        best_move_san = board_before.san(best_move) # convert move to SAN format
        move_played_san = board_before.san(move_played) # convert move to SAN format
        description = f"your move {move_played_san} missed a fork with {best_move_san}. The {attacker_name} could have attacked the {forked_pieces}."
        return {"category": "Missed Fork", "move_number": move_num, "description": description, "punishing_move": best_move}
    return None

def check_for_allowed_fork(board_after, info_after_move, turn_color, move_played, board_before):
    """
    Detects if the player's last move allowed the opponent to create a fork that wins material.
    Returns an 'Allowed Fork' blunder dict if found, otherwise None.
    Used By: Categorize Blunder function.
    Time complexity: O(1) 
    """
    if not info_after_move.get('pv'): return None # saftey, if no best move, return None
    move_num = board_after.fullmove_number # get move number
    opponent_best_move = info_after_move['pv'][0] 
    
    if opponent_best_move not in board_after.legal_moves: return None # saftey, if not legal, return None
    
    opponent_best_move_san = board_after.san(opponent_best_move) # convert move to SAN format

    board_after_opponent_move = board_after.copy() # copy board
    board_after_opponent_move.push(opponent_best_move) # apply opponent best move to copied board
    forking_piece = board_after_opponent_move.piece_at(opponent_best_move.to_square) # get forking piece
    if not forking_piece: return None # saftey, if no forking piece, return None
    attacked_squares = board_after_opponent_move.attacks(opponent_best_move.to_square) # get attacked squares
    player_pieces_attacked = [{'piece': board_after_opponent_move.piece_at(sq), 'square': sq} for sq in attacked_squares if board_after_opponent_move.piece_at(sq) and board_after_opponent_move.piece_at(sq).color == turn_color] # get player pieces attacked
    valuable_pieces_attacked = [p for p in player_pieces_attacked if p['piece'].piece_type > chess.PAWN] # get valuable pieces attacked
    if len(valuable_pieces_attacked) >= 2: # if at least 2 valuable pieces are attacked
        total_value_attacked = sum(PIECE_VALUES.get(p['piece'].piece_type, 0) for p in valuable_pieces_attacked) # get total value of attacked pieces
        forking_piece_value = PIECE_VALUES.get(forking_piece.piece_type, 0) # get value of forking piece
        if total_value_attacked > forking_piece_value: # if total value of attacked pieces is greater than forking piece value
            piece_names = [PIECE_NAMES.get(p['piece'].piece_type, "piece") for p in valuable_pieces_attacked] # get piece names
            forked_pieces = " and ".join(piece_names)
            forker_name = PIECE_NAMES.get(forking_piece.piece_type, "piece")
            move_played_san = board_before.san(move_played) # convert move to SAN format
            description = f"your move {move_played_san} allows the opponent to play {opponent_best_move_san}, creating a fork with their {forker_name} that attacks your {forked_pieces}."
            return {"category": "Allowed Fork", "move_number": move_num, "description": description, "punishing_move": opponent_best_move}
    return None

def check_for_missed_pin(board_before, best_move_info, turn_color, move_played):
    """
    Checks if the best move would have created an absolute pin.
    Returns a 'Missed Pin' blunder dict if found, otherwise None.
    Used By: Categorize Blunder function.
    Uses: get_absolute_pins.
    Time complexity: O(1) 
    """
    if not best_move_info.get('pv'): return None # saftey, if no best move, return None
    move_num = board_before.fullmove_number # get move number
    best_move = best_move_info['pv'][0]
    move_played_san = board_before.san(move_played) # convert move to SAN format
    # Pins before
    pins_before = get_absolute_pins(board_before, not turn_color)
    # After best move
    board_with_best_move = board_before.copy()
    board_with_best_move.push(best_move)
    pins_after = get_absolute_pins(board_with_best_move, not turn_color)
    # Find new pins
    new_pins = [pin for pin in pins_after if pin not in pins_before]
    if new_pins:
        pinned_square, pinner_square = new_pins[0]
        best_move_san = board_before.san(best_move)
        pinned_piece = board_with_best_move.piece_at(pinned_square)
        pinned_piece_name = PIECE_NAMES.get(pinned_piece.piece_type, "piece") if pinned_piece else "piece"
        description = f"your move {move_played_san} missed an absolute pin on the {pinned_piece_name} with {best_move_san}."
        return {"category": "Missed Pin", "move_number": move_num, "description": description, "punishing_move": best_move}
    return None

def check_for_allowed_pin(board_after, info_after_move, turn_color, move_played, board_before):
    """
    Detects if the player's last move allowed the opponent to create an absolute pin.
    Returns an 'Allowed Pin' blunder dict if found, otherwise None.
    Used By: Categorize Blunder function.
    Uses: get_absolute_pins.
    Time complexity: O(1) 
    """
    if not info_after_move.get('pv'): return None # saftey, if no best move, return None
    move_num = board_after.fullmove_number # get move number
    opponent_best_move = info_after_move['pv'][0] # get opponent best move
    if opponent_best_move not in board_after.legal_moves: return None # saftey, if not legal, return None

    # Pins before
    pins_before = get_absolute_pins(board_after, turn_color) # get pins before
    # After opponent's best move
    board_after_opponent_move = board_after.copy() # copy board
    board_after_opponent_move.push(opponent_best_move) # apply opponent best move to copied board
    pins_after = get_absolute_pins(board_after_opponent_move, turn_color) # get pins after
    # Find new pins
    new_pins = [pin for pin in pins_after if pin not in pins_before] # find new pins
    if new_pins:
        pinned_square, pinner_square = new_pins[0]
        opponent_best_move_san = board_after.san(opponent_best_move)
        pinned_piece = board_after_opponent_move.piece_at(pinned_square)
        pinned_piece_name = PIECE_NAMES.get(pinned_piece.piece_type, "piece") if pinned_piece else "piece"
        move_played_san = board_before.san(move_played) # convert move to SAN format
        description = f"your move {move_played_san} allows the opponent to create an absolute pin on your {pinned_piece_name} with {opponent_best_move_san}."
        return {"category": "Allowed Pin", "move_number": move_num, "description": description, "punishing_move": opponent_best_move}
    return None

def categorize_blunder(board_before, board_after, move_played, info_before_move, info_after_move, best_move_info, blunder_threshold, engine, engine_think_time, debug_mode):
    """
    Categorization pipeline. Tries to find the most specific blunder category.
    Returns a dictionary with blunder info, or a general 'Mistake' if no specific category is found.
    Used By: Analyze Game function.
    Uses: check_for_allowed_mate, check_for_missed_mate, check_for_allowed_fork, check_for_missed_fork, check_for_allowed_pin, check_for_missed_pin, check_for_material_loss, check_for_missed_material_gain.
    Time complexity: O(n) + O(t), n is number of check functions (currently 8), t is engine think time per move
    """
    move_played_san = board_before.san(move_played)
    if debug_mode: print(f"\n--- [DEBUG] Categorizing Blunder for move {move_played_san} ---")
    turn_color = board_before.turn
    move_num = board_before.fullmove_number # get move number
    after_move_eval = info_after_move["score"].pov(turn_color)
    
    possible_blunders = []
    
    check_functions = [
        (check_for_allowed_mate, [board_before, after_move_eval, move_num, move_played, info_after_move]),
        (check_for_missed_mate, [board_before, best_move_info, after_move_eval, turn_color, move_num, move_played]),
        (check_for_allowed_fork, [board_after, info_after_move, turn_color, move_played, board_before]),
        (check_for_missed_fork, [board_before, best_move_info, turn_color, move_played]),
        (check_for_allowed_pin, [board_after, info_after_move, turn_color, move_played, board_before]),
        (check_for_missed_pin, [board_before, best_move_info, turn_color, move_played]),
        (check_for_material_loss, [board_before, move_played, board_after, turn_color]),
        (check_for_missed_material_gain, [board_before, best_move_info, move_played]),
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
            description = f"your move {move_played_san} dropped your win probability by {win_prob_drop:.1f}%. The best move was {best_move_san}."
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
            print(f"[DEBUG]   - Category: {b['category']}, Severity: {b.get('severity_score', 'N/A')}")

    final_blunder = min(
        ranked_blunders,
        key=lambda x: (
            BLUNDER_CATEGORY_PRIORITY.get(x.get("category", "Mistake"), 99),
            x.get("severity_score", 99999)
        )
    )
    if debug_mode: print(f"\n[DEBUG] --- Final Decision ---")
    if debug_mode: print(f"[DEBUG] Selected Blunder: {final_blunder['category']} (Score: {final_blunder['severity_score']})")
    
    return final_blunder

def analyze_game(game, engine, target_user, blunder_threshold, engine_think_time, debug_mode):
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
            board_before = board.copy() # get board state before the move
            info_before_move = engine.analyse(board, chess.engine.Limit(time=engine_think_time)) # get eval and best move from before the move was made
            best_move_info = info_before_move # alias for the best move info (taken from before the move was made)

            # ---- make the move and run all blunder checks ----
            board.push(move) # make target player's move
            info_after_move = engine.analyse(board, chess.engine.Limit(time=engine_think_time)) # get eval from after the move was made

            # ---- pass to blunder categorization function ----
            blunder_info = categorize_blunder(
                board_before, board, move, info_before_move, info_after_move, best_move_info,
                blunder_threshold, engine, engine_think_time, debug_mode
            )
            if blunder_info:
                blunders.append(blunder_info)
        else:
            board.push(move)
    
    return blunders

def main():
    start = time.perf_counter()  # Start timer

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

    end = time.perf_counter()  # End timer
    print(f"Total runtime: {end - start:.2f} seconds")  # Print elapsed time

if __name__ == "__main__":
    main()