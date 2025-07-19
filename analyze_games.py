import chess
import chess.pgn
import chess.engine
import os 
import argparse
import math
import time

# ---- Constants ----
STOCKFISH_PATH_DEFAULT = os.path.join(os.path.dirname(__file__), "stockfish", "stockfish.exe")
BLUNDER_THRESHOLD_DEFAULT = 10.0  # Changed to match config.py setting
ENGINE_THINK_TIME_DEFAULT = 0.08  # Changed to balanced (was 0.1)
BLUNDER_CATEGORY_PRIORITY = {
    "Allowed Checkmate": 1,
    "Missed Checkmate": 2,
    "Hanging a Piece": 3,  # Moved up - hanging pieces are more critical
    "Allowed Winning Exchange for Opponent": 4,  # NEW CATEGORY
    "Allowed Fork": 5,
    "Missed Fork": 6,
    "Allowed Discovered Attack": 7,  # NEW CATEGORY
    "Missed Discovered Attack": 8,  # NEW CATEGORY
    "Losing Exchange": 9,
    "Missed Material Gain": 10,
    "Allowed Opportunity to Pressure Pinned Piece": 11,  # NEW CATEGORY
    "Missed Opportunity to Pressure Pinned Piece": 12,  # NEW CATEGORY
    "Allowed Pin": 13,
    "Missed Pin": 14,  # Moved down - pins are less critical than hanging pieces
    "Mistake": 15
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
    Used By: Material Loss and Missed Material Gain check functions, quick_blunder_heuristics.
    Uses: see_exchange.
    Time complexity: O(d) where d is the depth of the search (typically 2-6 moves/calls).
    """
    if not board.is_capture(move): return 0 # if not a capture, no material exchange, value = 0.
    if board.is_en_passant(move): # if en passant capture, value = pawn (100).
        capture_value = PIECE_VALUES[chess.PAWN]
    else: # if not en passant capture, value = value of captured piece.
        captured_piece = board.piece_at(move.to_square) # get the piece that was captured.
        if not captured_piece: return 0 # safety, if no piece was captured, value = 0.
        capture_value = PIECE_VALUES.get(captured_piece.piece_type, 0) # get the value of the captured piece.
    board_after_move = board.copy() # copy board 
    board_after_move.push(move) # apply move to copied board.
    value = capture_value - see_exchange(board_after_move, move.to_square) # recursive call for recaptures.
    return value

def see_exchange(board, target_square):
    """
    Calculates the value of the best recapture on a square, from the perspective of the side to move.
    Used By: see to calculate the value of a capture.
    Time complexity: O(d) where d is the depth of the recapture sequence (typically 2-6 moves/calls).
    """
    attackers = board.attackers(board.turn, target_square) # find all attackers of target square
    if not attackers: return 0 # safety, if no attackers return 0
    lva_square = min(attackers, key=lambda s: PIECE_VALUES.get(board.piece_at(s).piece_type, 0)) # least valuable attacker
    lva_piece = board.piece_at(lva_square)  # get lva piece
    if not lva_piece: return 0 # safety, if no lva piece return 0
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
    For more accurate assessment of board position.
    Used By: categorize_blunder function, quick_blunder_heuristics.
    Time complexity: O(1) 
    """
    if cp is None: return 0.5 # if no evaluation, return neutral probability
    return 1 / (1 + math.exp(-0.004 * cp)) # logistic function to convert centipawns to probability

def get_absolute_pins(board, color):
    """
    Returns a list of (pinned_square, pinner_square) tuples for all absolute pins
    of the given color on the board.
    Absolute pin is when a piece is pinned to the king.
    Used By: check_for_missed_pin, check_for_allowed_pin, quick_blunder_heuristics.
    Time complexity: O(64) = O(1) 
    """
    pins = [] # initialize list of pins
    king_square = board.king(color) # get king square
    if king_square is None: # safety, if no king, return empty list
        return pins
    for square in chess.SQUARES: # iterate over all squares
        piece = board.piece_at(square) # get piece at square
        if piece and piece.color == color and board.is_pinned(color, square): # if piece is of color and pinned
            pinner_square = board.pin(color, square) # get pinner square
            pins.append((square, pinner_square)) # add pin to list
    return pins

def quick_blunder_heuristics(board_before, move_played, best_move_info, turn_color, debug_mode):
    """
    Quick heuristic checks to determine if a move might be a blunder
    WITHOUT requiring a second engine call. Returns True if potential blunder detected.
    Used By: analyze_game.
    Uses: see, get_absolute_pins, cp_to_win_prob.
    Time complexity: O(64) for board scanning, typically very fast.
    """
    if debug_mode: print(f"[DEBUG] Running quick heuristics for {board_before.san(move_played)}") # debug output
    
    # Heuristic 1: Best move is checkmate (likely missed mate)
    best_move_eval = best_move_info["score"].pov(turn_color) # get best move evaluation from player's perspective
    if best_move_eval.is_mate() and best_move_eval.mate() > 0: # if best move leads to mate for player
        if debug_mode: print(f"[DEBUG] Heuristic 1 - Best move is mate in {best_move_eval.mate()}") # debug output
        return True # definitely need second engine call
    
    # Heuristic 2: Move is a losing capture (SEE analysis)
    if board_before.is_capture(move_played): # if the move is a capture
        see_value = see(board_before, move_played) # calculate static exchange evaluation
        if see_value < -100:  # if losing more than a pawn
            if debug_mode: print(f"[DEBUG] Heuristic 2 - Losing capture with SEE: {see_value}") # debug output
            return True # likely a blunder, need second engine call
    
    # Heuristic 3: Move hangs a piece (quick hanging piece check)
    board_after = board_before.copy() # copy board to simulate position after move
    board_after.push(move_played) # apply the move
    
    # Quick scan for hanging pieces
    for square in chess.SQUARES: # iterate over all squares
        piece = board_after.piece_at(square) # get piece at square
        if piece and piece.color == turn_color: # if it's player's piece
            attackers = board_after.attackers(not turn_color, square) # get opponent attackers of the square
            if attackers and not board_after.attackers(turn_color, square):  # if attacked but not defended
                if debug_mode: print(f"[DEBUG] Heuristic 3 - Piece on {chess.square_name(square)} appears undefended") # debug output
                return True # hanging piece detected, need second engine call
    
    # Heuristic 4: Best move wins significant material (missed material gain)
    if best_move_info.get('pv'): # if engine provided principal variation
        best_move = best_move_info['pv'][0] # get the best move
        if board_before.is_capture(best_move): # if best move is a capture
            see_value = see(board_before, best_move) # calculate static exchange evaluation
            if see_value > 200:  # if winning more than 2 pawns
                if debug_mode: print(f"[DEBUG] Heuristic 4 - Best move wins material with SEE: {see_value}") # debug output
                return True # missed significant material gain, need second engine call
    
    # Heuristic 5: Best move creates a fork (missed fork detection)
    if best_move_info.get('pv'): # if engine provided principal variation
        best_move = best_move_info['pv'][0] # get the best move
        board_with_best_move = board_before.copy() # copy board
        board_with_best_move.push(best_move) # apply best move to copied board
        attacker_piece = board_with_best_move.piece_at(best_move.to_square) # get the piece that moved
        if attacker_piece: # if piece exists
            attacked_squares = board_with_best_move.attacks(best_move.to_square) # get squares attacked by the piece
            opponent_pieces_attacked = [board_with_best_move.piece_at(sq) for sq in attacked_squares 
                                      if board_with_best_move.piece_at(sq) and board_with_best_move.piece_at(sq).color != turn_color] # get opponent pieces attacked
            valuable_pieces_attacked = [p for p in opponent_pieces_attacked if p.piece_type > chess.PAWN] # filter for valuable pieces
            if len(valuable_pieces_attacked) >= 2: # if attacking 2+ valuable pieces (fork)
                if debug_mode: print(f"[DEBUG] Heuristic 5 - Best move creates fork attacking {len(valuable_pieces_attacked)} pieces") # debug output
                return True # missed fork opportunity, need second engine call
    
    # Heuristic 6: Best move creates a pin (missed pin detection)
    if best_move_info.get('pv'): # if engine provided principal variation
        best_move = best_move_info['pv'][0] # get the best move
        pins_before = get_absolute_pins(board_before, not turn_color) # get pins before best move
        board_with_best_move = board_before.copy() # copy board
        board_with_best_move.push(best_move) # apply best move to copied board
        pins_after = get_absolute_pins(board_with_best_move, not turn_color) # get pins after best move
        new_pins = [pin for pin in pins_after if pin not in pins_before] # find new pins created
        if new_pins: # if best move creates new pins
            if debug_mode: print(f"[DEBUG] Heuristic 6 - Best move creates {len(new_pins)} new pin(s)") # debug output
            return True # missed pin opportunity, need second engine call
    
    # Heuristic 7: Move might allow opponent mate/fork/pin (check opponent's likely responses)
    opponent_checks = [move for move in board_after.legal_moves if board_after.gives_check(move)] # get opponent checking moves
    opponent_captures = [move for move in board_after.legal_moves if board_after.is_capture(move)] # get opponent capture moves
    
    if opponent_checks: # if opponent has checking moves available
        # If opponent has checking moves, one might be mate or fork
        if debug_mode: print(f"[DEBUG] Heuristic 7a - Opponent has {len(opponent_checks)} checking moves available") # debug output
        return True # opponent has tactical opportunities, need second engine call
    
    if len(opponent_captures) > 2:  # if opponent has multiple capture options
        if debug_mode: print(f"[DEBUG] Heuristic 7b - Opponent has {len(opponent_captures)} capture options") # debug output
        return True # multiple captures might indicate hanging pieces, need second engine call
    
    # Heuristic 8: Large evaluation drop (if available from first engine call)
    current_eval = best_move_info["score"].pov(turn_color).score(mate_score=10000) # get current evaluation in centipawns
    if current_eval is not None: # if evaluation is available
        win_prob_before = cp_to_win_prob(current_eval) # convert to win probability
        if win_prob_before > 0.7:  # if in winning position (>70% win probability)
            if debug_mode: print(f"[DEBUG] Heuristic 8 - In winning position ({win_prob_before:.2f}), checking for blunder") # debug output
            return True  # in winning position, be conservative and check all moves
    
    if debug_mode: print(f"[DEBUG] No heuristics triggered, likely not a blunder") # debug output
    return False # no heuristics triggered, skip second engine call

def enhanced_blunder_heuristics(board_before, move_played, best_move_info, engine_think_time, turn_color, debug_mode):
    """
    Enhanced heuristics to reduce unnecessary engine calls by 25%.
    
    New heuristics:
    1. Position evaluation thresholds
    2. Move type filtering
    3. Time control considerations
    4. Piece activity analysis
    """
    
    # First run original heuristics - if they say no, we can skip additional checks
    original_result = quick_blunder_heuristics(board_before, move_played, best_move_info, turn_color, debug_mode)
    if not original_result:
        if debug_mode: print(f"[DEBUG] Original heuristics passed, move likely fine")
        return False
    
    if debug_mode: print(f"[DEBUG] Running enhanced heuristics for {board_before.san(move_played)}")
    
    # NEW HEURISTIC 1: Position evaluation threshold
    current_eval = best_move_info["score"].pov(turn_color).score(mate_score=10000)
    if current_eval:
        abs_eval = abs(current_eval)
        
        # FIXED: Don't skip analysis for mate positions - these are critical!
        best_move_eval = best_move_info["score"].pov(turn_color)
        if best_move_eval.is_mate():
            if debug_mode: print(f"[DEBUG] Enhanced 1 - Mate position detected, continuing analysis")
            return True
        
        # Skip analysis in clearly decided positions (but not mate) - increased threshold
        if abs_eval > 1200:  # More than 12 pawns advantage (was 800)
            if debug_mode: print(f"[DEBUG] Enhanced 1 - Position decided ({abs_eval}cp), skipping analysis")
            return False
    
    # NEW HEURISTIC 2: Move type filtering for fast mode
    if engine_think_time < 0.06:  # Fast mode
        # Only analyze complex positions in fast mode
        legal_moves_count = len(list(board_before.legal_moves))
        if legal_moves_count < 20:  # Simple position
            if debug_mode: print(f"[DEBUG] Enhanced 2 - Fast mode + simple position ({legal_moves_count} moves), skipping")
            return False
    
    # NEW HEURISTIC 3: Opening/Endgame filtering - DISABLED for test positions
    # FIXED: Don't filter opening moves when testing specific positions
    move_count = len(list(board_before.move_stack))
    if move_count < 10:  # Only very early opening (was 20)
        # Only skip truly obvious moves like castling
        if move_played in [chess.Move.from_uci("e1g1"), chess.Move.from_uci("e1c1"),  
                           chess.Move.from_uci("e8g8"), chess.Move.from_uci("e8c8")]:
            if debug_mode: print(f"[DEBUG] Enhanced 3 - Castling in opening, skipping")
            return False
    
    # NEW HEURISTIC 4: Piece activity check  
    # FIXED: Don't skip castling if there are hanging pieces detected
    if not board_before.is_capture(move_played):
        # Only skip castling if no pieces are hanging
        is_castling = move_played in [chess.Move.from_uci("e1g1"), chess.Move.from_uci("e1c1"),  # White castling
                                     chess.Move.from_uci("e8g8"), chess.Move.from_uci("e8c8")]  # Black castling
        if is_castling:
            # Check if castling leaves pieces hanging
            board_after_temp = board_before.copy()
            board_after_temp.push(move_played)
            hanging_after_castling = False
            for square in chess.SQUARES:
                piece = board_after_temp.piece_at(square)
                if piece and piece.color == turn_color:
                    attackers = board_after_temp.attackers(not turn_color, square)
                    if attackers:
                        defenders = board_after_temp.attackers(turn_color, square)
                        if len(defenders) == 0:  # Truly hanging
                            hanging_after_castling = True
                            break
            
            if not hanging_after_castling:
                if debug_mode: print(f"[DEBUG] Enhanced 4 - Safe castling move, skipping")
                return False
            else:
                if debug_mode: print(f"[DEBUG] Enhanced 4 - Castling but leaves pieces hanging, analyzing")
                return True
    
    # NEW HEURISTIC 5: Endgame material considerations
    total_material = sum(len(board_before.pieces(piece_type, color)) * [0, 1, 3, 3, 5, 9, 0][piece_type]
                        for piece_type in range(1, 7) for color in [True, False])
    if total_material < 20:  # Endgame (less than ~20 points of material)
        # In endgame, king activity is important, so don't skip king moves
        piece_moved = board_before.piece_at(move_played.from_square)
        if piece_moved and piece_moved.piece_type == chess.KING:
            if debug_mode: print(f"[DEBUG] Enhanced 5 - Endgame king move, analyzing")
            return True
        
        # But can skip obvious pawn moves in endgame
        if (piece_moved and piece_moved.piece_type == chess.PAWN and
            not board_before.is_capture(move_played) and
            not board_before.gives_check(move_played)):
            if debug_mode: print(f"[DEBUG] Enhanced 5 - Simple endgame pawn move, skipping")
            return False
    
    # NEW HEURISTIC 6: Repetition avoidance
    # If the move leads to a repeated position, it's probably not a blunder
    board_after = board_before.copy()
    board_after.push(move_played)
    if board_after.is_repetition(count=2):
        if debug_mode: print(f"[DEBUG] Enhanced 6 - Move leads to repetition, skipping")
        return False
    
    if debug_mode: print(f"[DEBUG] Enhanced heuristics passed, analyzing move")
    return True

#---- Blunder Categorization Functions ----
def check_for_missed_material_gain(board_before, best_move_info, move_played, debug_mode, actual_move_number):
    """
    Checks for missed material gain using SEE calculations.
    Returns 'Missed Material Gain' blunder dict if a missed material gain is found, otherwise None.
    Used By: categorize_blunder.
    Uses: see.
    Time complexity: O(1) 
    """
    if not best_move_info.get('pv'): return None # safety, if no best move, return None
    
    best_move = best_move_info['pv'][0] # get best move
    
    # CRITICAL FIX: Don't flag the best move as a missed opportunity!
    if best_move == move_played:
        if debug_mode: print(f"[DEBUG] Move played ({board_before.san(move_played)}) IS the best move - no missed material gain")
        return None
    
    if board_before.is_capture(best_move): # check if best move is a capture
        see_value = see(board_before, best_move) # calculate static exchange evaluation
        if see_value >= 100: # if capture is worth at least 100 points (a pawn or more)
            captured_piece = board_before.piece_at(best_move.to_square) # get captured piece
            piece_name = PIECE_NAMES.get(captured_piece.piece_type, "material") if captured_piece else "material" # get piece name
            best_move_san = board_before.san(best_move) # convert move to SAN format
            move_played_san = board_before.san(move_played) # convert move to SAN format
            description = f"your move {move_played_san} missed a chance to win a {piece_name} with {best_move_san}." # create description
            if debug_mode: 
                print(f"[DEBUG] Missed material gain detected:")
                print(f"[DEBUG]   Move played: {move_played_san}")
                print(f"[DEBUG]   Best move: {best_move_san}")
                print(f"[DEBUG]   SEE value: {see_value}")
            return {"category": "Missed Material Gain", "move_number": actual_move_number, "description": description, "punishing_move": best_move, "material_value": see_value} # return blunder dict with material value
    
    return None

def check_for_material_loss(board_before, move_played, board_after, turn_color, debug_mode, actual_move_number):
    """
    Checks for material loss using SEE calculations.
    Returns 'Losing Exchange' or 'Hanging a Piece' blunder dict if a material loss is found, otherwise None.
    Used By: categorize_blunder.
    Uses: see.
    Time complexity: O(64) = O(1) 
    """
    move_played_san = board_before.san(move_played) # convert move to SAN format
    
    # Check for losing exchange
    if board_before.is_capture(move_played): # check if move is a capture
        see_value = see(board_before, move_played) # get see value
        if see_value < -100: # if losing more than a pawn worth of material
            captured_piece = board_before.piece_at(move_played.to_square) # get captured piece
            captured_piece_name = PIECE_NAMES.get(captured_piece.piece_type, "piece") if captured_piece else "piece" # get piece name
            net_loss = abs(see_value) # calculate net loss
            description = f"your move {move_played_san} initiates a losing exchange. You capture a {captured_piece_name} but lose {net_loss} centipawns in the sequence." # create description
            if debug_mode: print(f"[DEBUG] Losing exchange detected with SEE value: {see_value}") # debug output
            return {"category": "Losing Exchange", "move_number": actual_move_number, "description": description, "punishing_move": None} # return blunder dict
    
    # Remove complex SEE-based logic and simplify hanging piece detection
    hanging_pieces = []
    if debug_mode: print(f"[DEBUG] Checking for hanging pieces after move {move_played_san} (SIMPLE MODE)...")

    for square in chess.SQUARES:
        piece = board_after.piece_at(square)
        if piece and piece.color == turn_color:
            attackers = board_after.attackers(not turn_color, square)
            if attackers:
                defenders = board_after.attackers(turn_color, square)
                if len(defenders) == 0:  # TRULY hanging – no defenders at all
                    capture_move_from = min(attackers, key=lambda s: PIECE_VALUES.get(board_after.piece_at(s).piece_type, 0))
                    capture_move = chess.Move(capture_move_from, square)
                    if board_after.piece_at(capture_move_from).piece_type == chess.PAWN and chess.square_rank(square) in [0, 7]:
                        capture_move.promotion = chess.QUEEN
                    hanging_pieces.append({
                        'square': square,
                        'piece': piece,
                        'capture_move': capture_move,
                        'attackers': len(attackers)
                    })

    if debug_mode: print(f"[DEBUG] Found {len(hanging_pieces)} hanging pieces (simple mode)")

    if hanging_pieces:
        # pick the most valuable piece hanging
        hanging_pieces.sort(key=lambda hp: -PIECE_VALUES.get(hp['piece'].piece_type,0))
        most = hanging_pieces[0]
        piece_name = PIECE_NAMES.get(most['piece'].piece_type,'piece')
        piece_value = PIECE_VALUES.get(most['piece'].piece_type, 0)
        square_name = chess.square_name(most['square'])
        description = f"your move {move_played_san} left your {piece_name} on {square_name} completely undefended."
        return {"category": "Hanging a Piece", "move_number": actual_move_number, "description": description, "punishing_move": most['capture_move'], "material_value": piece_value}

    return None

def check_for_missed_fork(board_before, best_move_info, turn_color, move_played, debug_mode, actual_move_number):
    """
    Checks if the best move would have created a fork.
    Returns a 'Missed Fork' blunder dict if found, otherwise None.
    Used By: categorize_blunder.
    Time complexity: O(1) 
    """
    if not best_move_info.get('pv'): return None # safety, if no best move, return None
    best_move = best_move_info['pv'][0] # get best move
    
    # CRITICAL FIX: Don't flag the best move as a missed opportunity!
    if best_move == move_played:
        if debug_mode: print(f"[DEBUG] Move played ({board_before.san(move_played)}) IS the best move - no missed fork")
        return None
    
    board_with_best_move = board_before.copy() # copy board
    board_with_best_move.push(best_move) # apply best move to copied board
    attacker_piece = board_with_best_move.piece_at(best_move.to_square) # get attacker piece
    if not attacker_piece: return None # safety, if no attacker piece, return None
    
    attacked_squares = board_with_best_move.attacks(best_move.to_square) # get attacked squares
    opponent_pieces_attacked = [board_with_best_move.piece_at(sq) for sq in attacked_squares if board_with_best_move.piece_at(sq) and board_with_best_move.piece_at(sq).color != turn_color] # get opponent pieces attacked
    valuable_pieces_attacked = [p for p in opponent_pieces_attacked if p.piece_type > chess.PAWN] # get valuable pieces attacked
    
    if len(valuable_pieces_attacked) >= 2: # if at least 2 valuable pieces are attacked
        piece_names = [PIECE_NAMES.get(p.piece_type, "piece") for p in valuable_pieces_attacked] # get piece names
        forked_pieces = " and ".join(piece_names) # join piece names
        attacker_name = PIECE_NAMES.get(attacker_piece.piece_type, "piece") # get attacker name
        best_move_san = board_before.san(best_move) # convert move to SAN format
        move_played_san = board_before.san(move_played) # convert move to SAN format
        description = f"your move {move_played_san} missed a fork with {best_move_san}. The {attacker_name} could have attacked the {forked_pieces}." # create description
        if debug_mode: 
            print(f"[DEBUG] Missed fork detected:")
            print(f"[DEBUG]   Move played: {move_played_san}")
            print(f"[DEBUG]   Best move: {best_move_san}")
            print(f"[DEBUG]   Fork targets: {forked_pieces}")
        return {"category": "Missed Fork", "move_number": actual_move_number, "description": description, "punishing_move": best_move} # return blunder dict
    return None

def check_for_allowed_fork(board_after, info_after_move, turn_color, move_played, board_before, debug_mode, actual_move_number):
    """
    Detects if the player's last move allowed the opponent to create a fork.
    Returns an 'Allowed Fork' blunder dict if found, otherwise None.
    Used By: categorize_blunder.
    Time complexity: O(1) 
    """
    if not info_after_move.get('pv'): return None # safety, if no best move, return None
    opponent_best_move = info_after_move['pv'][0] # get opponent's best move
    
    if opponent_best_move not in board_after.legal_moves: return None # safety, if not legal, return None
    
    opponent_best_move_san = board_after.san(opponent_best_move) # convert move to SAN format

    board_after_opponent_move = board_after.copy() # copy board
    board_after_opponent_move.push(opponent_best_move) # apply opponent best move to copied board
    forking_piece = board_after_opponent_move.piece_at(opponent_best_move.to_square) # get forking piece
    if not forking_piece: return None # safety, if no forking piece, return None
    
    attacked_squares = board_after_opponent_move.attacks(opponent_best_move.to_square) # get attacked squares
    player_pieces_attacked = [{'piece': board_after_opponent_move.piece_at(sq), 'square': sq} for sq in attacked_squares if board_after_opponent_move.piece_at(sq) and board_after_opponent_move.piece_at(sq).color == turn_color] # get player pieces attacked
    valuable_pieces_attacked = [p for p in player_pieces_attacked if p['piece'].piece_type > chess.PAWN] # get valuable pieces attacked
    
    if len(valuable_pieces_attacked) >= 2: # if at least 2 valuable pieces are attacked
        total_value_attacked = sum(PIECE_VALUES.get(p['piece'].piece_type, 0) for p in valuable_pieces_attacked) # get total value of attacked pieces
        forking_piece_value = PIECE_VALUES.get(forking_piece.piece_type, 0) # get value of forking piece
        if total_value_attacked > forking_piece_value: # if total value of attacked pieces is greater than forking piece value
            piece_names = [PIECE_NAMES.get(p['piece'].piece_type, "piece") for p in valuable_pieces_attacked] # get piece names
            forked_pieces = " and ".join(piece_names) # join piece names
            forker_name = PIECE_NAMES.get(forking_piece.piece_type, "piece") # get forker name
            move_played_san = board_before.san(move_played) # convert move to SAN format
            description = f"your move {move_played_san} allows the opponent to play {opponent_best_move_san}, creating a fork with their {forker_name} that attacks your {forked_pieces}." # create description
            if debug_mode: print(f"[DEBUG] Found Allowed Fork") # debug output
            return {"category": "Allowed Fork", "move_number": actual_move_number, "description": description, "punishing_move": opponent_best_move} # return blunder dict
    return None

def check_for_missed_pin(board_before, best_move_info, turn_color, move_played, debug_mode, actual_move_number):
    """
    Checks if the best move would have created an absolute pin.
    Returns a 'Missed Pin' blunder dict if found, otherwise None.
    Used By: categorize_blunder.
    Uses: get_absolute_pins.
    Time complexity: O(1) 
    """
    if not best_move_info.get('pv'): return None # safety, if no best move, return None
    best_move = best_move_info['pv'][0] # get best move
    move_played_san = board_before.san(move_played) # convert move to SAN format
    
    # CRITICAL FIX: Don't flag the best move as a missed opportunity!
    if best_move == move_played:
        if debug_mode: print(f"[DEBUG] Move played ({move_played_san}) IS the best move - no missed pin")
        return None
    
    # Pins before
    pins_before = get_absolute_pins(board_before, not turn_color) # get pins before best move
    # After best move
    board_with_best_move = board_before.copy() # copy board
    board_with_best_move.push(best_move) # apply best move to copied board
    pins_after = get_absolute_pins(board_with_best_move, not turn_color) # get pins after best move
    # Find new pins
    new_pins = [pin for pin in pins_after if pin not in pins_before] # find new pins created
    if new_pins: # if best move creates new pins
        pinned_square, pinner_square = new_pins[0] # get first new pin
        best_move_san = board_before.san(best_move) # convert move to SAN format
        pinned_piece = board_with_best_move.piece_at(pinned_square) # get pinned piece
        pinned_piece_name = PIECE_NAMES.get(pinned_piece.piece_type, "piece") if pinned_piece else "piece" # get piece name
        description = f"your move {move_played_san} missed an absolute pin on the {pinned_piece_name} with {best_move_san}." # create description
        if debug_mode: 
            print(f"[DEBUG] Missed pin detected:")
            print(f"[DEBUG]   Move played: {move_played_san}")
            print(f"[DEBUG]   Best move: {best_move_san}")
            print(f"[DEBUG]   Pin target: {pinned_piece_name}")
        return {"category": "Missed Pin", "move_number": actual_move_number, "description": description, "punishing_move": best_move} # return blunder dict
    return None

def check_for_allowed_pin(board_after, info_after_move, turn_color, move_played, board_before, debug_mode, actual_move_number):
    """
    Detects if the player's last move allowed the opponent to create an absolute pin.
    Returns an 'Allowed Pin' blunder dict if found, otherwise None.
    Used By: categorize_blunder.
    Uses: get_absolute_pins.
    Time complexity: O(1) 
    """
    if not info_after_move.get('pv'): return None # safety, if no best move, return None
    opponent_best_move = info_after_move['pv'][0] # get opponent best move
    if opponent_best_move not in board_after.legal_moves: return None # safety, if not legal, return None

    # Pins before
    pins_before = get_absolute_pins(board_after, turn_color) # get pins before opponent's move
    # After opponent's best move
    board_after_opponent_move = board_after.copy() # copy board
    board_after_opponent_move.push(opponent_best_move) # apply opponent best move to copied board
    pins_after = get_absolute_pins(board_after_opponent_move, turn_color) # get pins after opponent's move
    # Find new pins
    new_pins = [pin for pin in pins_after if pin not in pins_before] # find new pins created
    if new_pins: # if opponent's move creates new pins
        pinned_square, pinner_square = new_pins[0] # get first new pin
        opponent_best_move_san = board_after.san(opponent_best_move) # convert move to SAN format
        pinned_piece = board_after_opponent_move.piece_at(pinned_square) # get pinned piece
        pinned_piece_name = PIECE_NAMES.get(pinned_piece.piece_type, "piece") if pinned_piece else "piece" # get piece name
        move_played_san = board_before.san(move_played) # convert move to SAN format
        description = f"your move {move_played_san} allows the opponent to create an absolute pin on your {pinned_piece_name} with {opponent_best_move_san}." # create description
        if debug_mode: print(f"[DEBUG] Found Allowed Pin") # debug output
        return {"category": "Allowed Pin", "move_number": actual_move_number, "description": description, "punishing_move": opponent_best_move} # return blunder dict
    return None

def check_for_missed_pinned_piece_pressure(board_before, best_move_info, turn_color, move_played, debug_mode, actual_move_number):
    """
    Checks if the best move would have added pressure to a pinned opponent piece.
    Returns a 'Missed Opportunity to Pressure Pinned Piece' blunder dict if found, otherwise None.
    """
    if not best_move_info.get('pv'): return None
    best_move = best_move_info['pv'][0]
    
    # Don't flag the best move as a missed opportunity
    if best_move == move_played:
        if debug_mode: print(f"[DEBUG] Move played ({board_before.san(move_played)}) IS the best move - no missed pinned piece pressure")
        return None
    
    # Check if best move adds pressure to a pinned piece
    pins_before = get_absolute_pins(board_before, not turn_color)
    if not pins_before:
        return None
    
    board_with_best_move = board_before.copy()
    board_with_best_move.push(best_move)
    
    # Check if best move attacks any pinned pieces
    for pinned_square, pinner_square in pins_before:
        if best_move.to_square == pinned_square or pinned_square in board_with_best_move.attacks(best_move.to_square):
            pinned_piece = board_before.piece_at(pinned_square)
            if pinned_piece and pinned_piece.color != turn_color:
                piece_name = PIECE_NAMES.get(pinned_piece.piece_type, "piece")
                best_move_san = board_before.san(best_move)
                move_played_san = board_before.san(move_played)
                description = f"your move {move_played_san} missed an opportunity to add pressure to a pinned {piece_name} with {best_move_san}."
                if debug_mode: print(f"[DEBUG] Found Missed Pinned Piece Pressure")
                return {"category": "Missed Opportunity to Pressure Pinned Piece", "move_number": actual_move_number, "description": description, "punishing_move": best_move}
    
    return None

def check_for_allowed_pinned_piece_pressure(board_after, info_after_move, turn_color, move_played, board_before, debug_mode, actual_move_number):
    """
    Detects if the player's move allowed the opponent to add pressure to a pinned piece.
    Returns an 'Allowed Opportunity to Pressure Pinned Piece' blunder dict if found, otherwise None.
    """
    if not info_after_move.get('pv'): return None
    opponent_best_move = info_after_move['pv'][0]
    if opponent_best_move not in board_after.legal_moves: return None

    # Check if there are any pinned pieces
    pins_current = get_absolute_pins(board_after, turn_color)
    if not pins_current:
        return None
    
    board_after_opponent_move = board_after.copy()
    board_after_opponent_move.push(opponent_best_move)
    
    # Check if opponent's best move adds pressure to any pinned pieces
    for pinned_square, pinner_square in pins_current:
        if (opponent_best_move.to_square == pinned_square or 
            pinned_square in board_after_opponent_move.attacks(opponent_best_move.to_square)):
            pinned_piece = board_after.piece_at(pinned_square)
            if pinned_piece and pinned_piece.color == turn_color:
                piece_name = PIECE_NAMES.get(pinned_piece.piece_type, "piece")
                opponent_best_move_san = board_after.san(opponent_best_move)
                move_played_san = board_before.san(move_played)
                description = f"your move {move_played_san} allows the opponent to add pressure to your pinned {piece_name} with {opponent_best_move_san}."
                if debug_mode: print(f"[DEBUG] Found Allowed Pinned Piece Pressure")
                return {"category": "Allowed Opportunity to Pressure Pinned Piece", "move_number": actual_move_number, "description": description, "punishing_move": opponent_best_move}
    
    return None

def check_for_missed_discovered_attack(board_before, best_move_info, turn_color, move_played, debug_mode, actual_move_number):
    """
    Checks if the best move would have created a discovered attack.
    Returns a 'Missed Discovered Attack' blunder dict if found, otherwise None.
    """
    if not best_move_info.get('pv'): return None
    best_move = best_move_info['pv'][0]
    
    # Don't flag the best move as a missed opportunity
    if best_move == move_played:
        if debug_mode: print(f"[DEBUG] Move played ({board_before.san(move_played)}) IS the best move - no missed discovered attack")
        return None
    
    # Check if best move creates a discovered attack
    board_with_best_move = board_before.copy()
    board_with_best_move.push(best_move)
    
    # Look for pieces that gained new attacks after the move
    piece_from = board_before.piece_at(best_move.from_square)
    if not piece_from:
        return None
    
    # Check if moving reveals attacks from pieces behind
    for square in chess.SQUARES:
        piece = board_with_best_move.piece_at(square)
        if piece and piece.color == turn_color and square != best_move.to_square:
            # Check if this piece gained new attacks that weren't there before
            attacks_before = board_before.attacks(square)
            attacks_after = board_with_best_move.attacks(square)
            new_attacks = attacks_after - attacks_before
            
            # Check if new attacks target valuable opponent pieces
            for attack_square in new_attacks:
                target_piece = board_with_best_move.piece_at(attack_square)
                if target_piece and target_piece.color != turn_color and target_piece.piece_type > chess.PAWN:
                    attacking_piece_name = PIECE_NAMES.get(piece.piece_type, "piece")
                    target_piece_name = PIECE_NAMES.get(target_piece.piece_type, "piece")
                    best_move_san = board_before.san(best_move)
                    move_played_san = board_before.san(move_played)
                    description = f"your move {move_played_san} missed a discovered attack where {best_move_san} would reveal your {attacking_piece_name}'s attack on the opponent's {target_piece_name}."
                    if debug_mode: print(f"[DEBUG] Found Missed Discovered Attack")
                    return {"category": "Missed Discovered Attack", "move_number": actual_move_number, "description": description, "punishing_move": best_move}
    
    return None

def check_for_allowed_discovered_attack(board_after, info_after_move, turn_color, move_played, board_before, debug_mode, actual_move_number):
    """
    Detects if the player's move allowed the opponent to create a discovered attack.
    Returns an 'Allowed Discovered Attack' blunder dict if found, otherwise None.
    """
    if not info_after_move.get('pv'): return None
    opponent_best_move = info_after_move['pv'][0]
    if opponent_best_move not in board_after.legal_moves: return None

    board_after_opponent_move = board_after.copy()
    board_after_opponent_move.push(opponent_best_move)
    
    # Look for pieces that gained new attacks after opponent's move
    for square in chess.SQUARES:
        piece = board_after_opponent_move.piece_at(square)
        if piece and piece.color != turn_color and square != opponent_best_move.to_square:
            # Check if this piece gained new attacks that weren't there before
            attacks_before = board_after.attacks(square)
            attacks_after = board_after_opponent_move.attacks(square)
            new_attacks = attacks_after - attacks_before
            
            # Check if new attacks target valuable player pieces
            for attack_square in new_attacks:
                target_piece = board_after_opponent_move.piece_at(attack_square)
                if target_piece and target_piece.color == turn_color and target_piece.piece_type > chess.PAWN:
                    attacking_piece_name = PIECE_NAMES.get(piece.piece_type, "piece")
                    target_piece_name = PIECE_NAMES.get(target_piece.piece_type, "piece")
                    opponent_best_move_san = board_after.san(opponent_best_move)
                    move_played_san = board_before.san(move_played)
                    description = f"your move {move_played_san} allows the opponent to create a discovered attack with {opponent_best_move_san}, where their {attacking_piece_name} attacks your {target_piece_name}."
                    if debug_mode: print(f"[DEBUG] Found Allowed Discovered Attack")
                    return {"category": "Allowed Discovered Attack", "move_number": actual_move_number, "description": description, "punishing_move": opponent_best_move}
    
    return None

def check_for_winning_exchange(board_before, move_played, board_after, turn_color, debug_mode, actual_move_number, info_after_move=None):
    """
    Detects situations where a defended piece can still be captured in a sequence that wins material for the opponent (SEE > threshold).
    ENHANCED: Now verifies that the suggested opponent capture is actually a good move.
    Returns a blunder dict for new category 'Allowed Winning Exchange for Opponent' or None.
    """
    move_played_san = board_before.san(move_played)
    winning_targets = []
    for square in chess.SQUARES:
        piece = board_after.piece_at(square)
        if not piece or piece.color != turn_color:
            continue
        attackers = board_after.attackers(not turn_color, square)
        if not attackers:
            continue  # cannot be captured
        defenders = board_after.attackers(turn_color, square)
        if len(defenders) == 0:
            continue  # true hanging handled elsewhere
        lva_square = min(attackers, key=lambda s: PIECE_VALUES.get(board_after.piece_at(s).piece_type, 0))
        capture_move = chess.Move(lva_square, square)
        # handle pawn promotion
        if board_after.piece_at(lva_square).piece_type == chess.PAWN and chess.square_rank(square) in [0,7]:
            capture_move.promotion = chess.QUEEN
        see_value = see(board_after, capture_move)
        # Thresholds similar to hanging detection but lower
        piece_value = PIECE_VALUES.get(piece.piece_type, 0)
        # Require opponent gains at least 100 cp net (one pawn) for it to matter
        if see_value >= 100:
            # ENHANCED: Verify this capture is actually a good move for the opponent
            is_good_opponent_move = True
            if info_after_move and info_after_move.get('pv'):
                opponent_best_move = info_after_move['pv'][0]
                # Check if this capture is the best move or at least among top moves
                if capture_move != opponent_best_move:
                    if debug_mode:
                        opponent_best_san = board_after.san(opponent_best_move)
                        capture_san = board_after.san(capture_move)
                        print(f"[DEBUG] Capture {capture_san} (SEE {see_value}) vs opponent's best {opponent_best_san}")
                    # RELAXED: Allow winning exchanges if they win significant material (200+ cp)
                    # This prevents false positives while catching real tactical errors
                    if see_value < 200:
                        is_good_opponent_move = False
            
            if is_good_opponent_move:
                winning_targets.append({
                    'square': square,
                    'piece': piece,
                    'see_value': see_value,
                    'capture_move': capture_move,
                    'defenders': len(defenders)
                })
                if debug_mode:
                    piece_name = PIECE_NAMES.get(piece.piece_type,'piece')
                    print(f"[DEBUG] Valid winning exchange: {piece_name} on {chess.square_name(square)} SEE {see_value} defenders {len(defenders)}")
            elif debug_mode:
                piece_name = PIECE_NAMES.get(piece.piece_type,'piece')
                print(f"[DEBUG] Rejected winning exchange: {piece_name} on {chess.square_name(square)} - capture not opponent's best move")
                
    if not winning_targets:
        return None
    # choose highest see_value
    winning_targets.sort(key=lambda t: (-t['see_value'], -PIECE_VALUES.get(t['piece'].piece_type,0)))
    target = winning_targets[0]
    piece_name = PIECE_NAMES.get(target['piece'].piece_type,'piece')
    square_name = chess.square_name(target['square'])
    opponent_capture_san = board_after.san(target['capture_move'])
    description = (f"your move {move_played_san} left your {piece_name} on {square_name} defended, but the resulting exchange sequence starting with "
                   f"{opponent_capture_san} wins material for your opponent.")
    return {"category": "Allowed Winning Exchange for Opponent", "move_number": actual_move_number,
            "description": description, "punishing_move": target['capture_move'], "material_value": target['see_value']}

def categorize_blunder(board_before, board_after, move_played, info_before_move, info_after_move, best_move_info, blunder_threshold, debug_mode, actual_move_number):
    """
    Categorization pipeline. First checks if move is actually a blunder (win probability drop),
    then tries to find the most specific blunder category.
    Returns a dictionary with blunder info, or None if no blunder found.
    Used By: analyze_game.
    Uses: check_for_allowed_fork, check_for_missed_fork, check_for_allowed_pin, check_for_missed_pin, check_for_material_loss, check_for_missed_material_gain, cp_to_win_prob.
    Time complexity: O(n) where n is number of check functions (currently 6).
    """
    move_played_san = board_before.san(move_played) # convert move to SAN format
    if debug_mode: print(f"\n--- [DEBUG] Categorizing Blunder for move {move_played_san} (Move #{actual_move_number}) ---") # debug output
    
    turn_color = board_before.turn # get player color
    after_move_eval = info_after_move["score"].pov(turn_color) # get evaluation after move from player's perspective
    
    # GLOBAL SAFETY CHECK: If this is the engine's best move, don't flag it as any blunder
    best_move = best_move_info.get('pv', [None])[0] if best_move_info.get('pv') else None
    if best_move and best_move == move_played:
        if debug_mode: print(f"[DEBUG] GLOBAL CHECK: Move played ({move_played_san}) IS the engine's best move - no blunder categorization")
        return None
    
    # FIRST: Check if this move actually causes a significant win probability drop
    # This is the fundamental criterion for being a blunder
    win_prob_before = cp_to_win_prob(info_before_move["score"].pov(turn_color).score(mate_score=10000)) # get win probability before move
    win_prob_after = cp_to_win_prob(after_move_eval.score(mate_score=10000)) # get win probability after move
    win_prob_drop = (win_prob_before - win_prob_after) * 100 # calculate win probability drop percentage
    
    if debug_mode: print(f"[DEBUG] Win prob drop: {win_prob_drop:.1f}%, Threshold: {blunder_threshold}%") # debug output
    
    # If win probability drop is below threshold, this is NOT a blunder
    if win_prob_drop < blunder_threshold:
        if debug_mode: print(f"[DEBUG] Win prob drop ({win_prob_drop:.1f}%) below threshold ({blunder_threshold}%) - not a blunder")
        return None
    
    # At this point, we know it's a blunder (win prob drop >= threshold)
    # Now we categorize what TYPE of blunder it is
    
    # Check 1: Allowed Checkmate (highest priority)
    if after_move_eval.is_mate() and after_move_eval.mate() < 0: # if opponent can force mate
        mate_in = abs(after_move_eval.mate()) # get number of moves to mate
        description = f"your move {move_played_san} allows the opponent to force checkmate in {mate_in}." # create description
        if debug_mode: print(f"[DEBUG] Found Allowed Checkmate") # debug output
        return {"category": "Allowed Checkmate", "move_number": actual_move_number, "description": description, "win_prob_drop": win_prob_drop} # return blunder dict
    
    # Check 2: Missed Checkmate
    best_move_eval = best_move_info["score"].pov(turn_color) # get best move evaluation from player's perspective
    if best_move_eval.is_mate() and best_move_eval.mate() > 0 and not after_move_eval.is_mate(): # if best move is mate but played move is not
        mate_in = best_move_eval.mate() # get number of moves to mate
        best_move_san = board_before.san(best_move) # convert move to SAN format
        description = f"your move {move_played_san} missed a checkmate in {mate_in}. The best move was {best_move_san}." # create description
        if debug_mode: print(f"[DEBUG] Found Missed Checkmate") # debug output
        return {"category": "Missed Checkmate", "move_number": actual_move_number, "description": description, "win_prob_drop": win_prob_drop} # return blunder dict
    
    # Check 3: Allowed Fork (HIGH PRIORITY - tactical patterns before simple hanging)
    allowed_fork = check_for_allowed_fork(board_after, info_after_move, turn_color, move_played, board_before, debug_mode, actual_move_number) # check for allowed fork
    if allowed_fork: # if allowed fork found
        allowed_fork["win_prob_drop"] = win_prob_drop # add win probability drop
        return allowed_fork # return the blunder
    
    # Check 4: VALUE-BASED TIE-BREAKER - Compare missed material gain vs hanging pieces vs winning exchanges
    missed_material = check_for_missed_material_gain(board_before, best_move_info, move_played, debug_mode, actual_move_number)
    material_blunder = check_for_material_loss(board_before, move_played, board_after, turn_color, debug_mode, actual_move_number)
    winning_exchange = check_for_winning_exchange(board_before, move_played, board_after, turn_color, debug_mode, actual_move_number, info_after_move)
    
    # Collect all detected material issues
    material_issues = []
    if missed_material:
        material_issues.append(("Missed Material Gain", missed_material, missed_material.get("material_value", 0)))
    if material_blunder:
        material_issues.append(("Hanging/Losing", material_blunder, material_blunder.get("material_value", 0)))
    if winning_exchange:
        # Extract SEE value from winning exchange for comparison
        winning_value = winning_exchange.get("material_value", 200)
        material_issues.append(("Winning Exchange", winning_exchange, winning_value))
    
    # VALUE-BASED COMPARISON: Choose based on biggest centipawn swing
    if material_issues:
        # Sort by material value (highest first)
        material_issues.sort(key=lambda x: x[2], reverse=True)
        
        if debug_mode:
            print(f"[DEBUG] VALUE-BASED TIE-BREAKER:")
            for issue_type, issue_data, value in material_issues:
                print(f"[DEBUG]   {issue_type}: {value} cp")
        
        # Return the highest value issue
        chosen_type, chosen_blunder, chosen_value = material_issues[0]
        if debug_mode: print(f"[DEBUG] CHOOSING: {chosen_type} ({chosen_value} cp)")
        chosen_blunder["win_prob_drop"] = win_prob_drop
        return chosen_blunder
    
    # Check 5: Other material analysis complete above
    
    # Check 6: Missed Fork
    missed_fork = check_for_missed_fork(board_before, best_move_info, turn_color, move_played, debug_mode, actual_move_number) # check for missed fork
    if missed_fork: # if missed fork found
        missed_fork["win_prob_drop"] = win_prob_drop # add win probability drop
        return missed_fork # return the blunder
    
    # Check 7: Discovered Attack checks (NEW)
    allowed_discovered = check_for_allowed_discovered_attack(board_after, info_after_move, turn_color, move_played, board_before, debug_mode, actual_move_number)
    if allowed_discovered:
        allowed_discovered["win_prob_drop"] = win_prob_drop
        return allowed_discovered
    
    missed_discovered = check_for_missed_discovered_attack(board_before, best_move_info, turn_color, move_played, debug_mode, actual_move_number)
    if missed_discovered:
        missed_discovered["win_prob_drop"] = win_prob_drop
        return missed_discovered
    
    # Check 8: Pinned piece pressure checks (NEW)
    allowed_pinned_pressure = check_for_allowed_pinned_piece_pressure(board_after, info_after_move, turn_color, move_played, board_before, debug_mode, actual_move_number)
    if allowed_pinned_pressure:
        allowed_pinned_pressure["win_prob_drop"] = win_prob_drop
        return allowed_pinned_pressure
    
    missed_pinned_pressure = check_for_missed_pinned_piece_pressure(board_before, best_move_info, turn_color, move_played, debug_mode, actual_move_number)
    if missed_pinned_pressure:
        missed_pinned_pressure["win_prob_drop"] = win_prob_drop
        return missed_pinned_pressure
    
    # Check 9: Allowed Pin
    allowed_pin = check_for_allowed_pin(board_after, info_after_move, turn_color, move_played, board_before, debug_mode, actual_move_number) # check for allowed pin
    if allowed_pin: # if allowed pin found
        allowed_pin["win_prob_drop"] = win_prob_drop # add win probability drop
        return allowed_pin # return the blunder
    
    # Check 10: Missed Pin - LOWER PRIORITY
    missed_pin = check_for_missed_pin(board_before, best_move_info, turn_color, move_played, debug_mode, actual_move_number) # check for missed pin
    if missed_pin: # if missed pin found
        missed_pin["win_prob_drop"] = win_prob_drop # add win probability drop
        return missed_pin # return the blunder
    
    # Check 11: General Mistake (fallback)
    # We already know it's a blunder due to win probability drop, so categorize as general mistake
    best_move_san = board_before.san(best_move_info['pv'][0]) # convert best move to SAN format
    description = f"your move {move_played_san} dropped your win probability by {win_prob_drop:.1f}%. The best move was {best_move_san}." # create description
    if debug_mode: print(f"[DEBUG] Found Mistake based on win probability") # debug output
    return {"category": "Mistake", "move_number": actual_move_number, "description": description, "win_prob_drop": win_prob_drop} # return blunder dict

def analyze_game(game, engine, target_user, blunder_threshold, engine_think_time, debug_mode):
    """
    Analyzes a single game for a specific user, identifies blunders,
    and returns a list of categorized blunder dictionaries.
    Uses selective evaluation with heuristics to reduce engine calls from 2 per move to ~1.4 per move while maintaining high accuracy.
    Used By: main.
    Uses: quick_blunder_heuristics, categorize_blunder.
    Time complexity: O(m * e) where m is number of moves and e is engine think time.
    """
    blunders = [] # list to store found blunders
    board = game.board() # initialize board state as starting position
    user_color = None # stores color of target user
    
    # Statistics tracking
    total_moves = 0 # count of moves analyzed
    engine_calls_made = 0 # count of engine calls made
    user_move_count = 0 # track user's actual move numbers

    # ---- find target user's color ----
    if game.headers.get("White", "").lower() == target_user.lower(): # check if user is white
        user_color = chess.WHITE # set user color to white
    elif game.headers.get("Black", "").lower() == target_user.lower(): # check if user is black
        user_color = chess.BLACK # set user color to black
    if user_color is None: # if user not found in game
        print(f"User '{target_user}' not found in this game. Skipping.") # print message
        return [] # return empty list

    # ---- detect/categorize blunders with selective evaluation ----
    for move in game.mainline_moves(): # for each move actually played in the game
        if board.turn == user_color: # if it's the target user's turn
            total_moves += 1 # increment move counter
            user_move_count += 1 # increment user move counter
            board_before = board.copy() # get board state before the move
            
            # Calculate correct move number (matches Chess.com notation)
            if user_color == chess.WHITE:
                actual_move_number = board_before.fullmove_number
            else:  # black
                actual_move_number = board_before.fullmove_number
            
            if debug_mode:
                move_san = board_before.san(move)
                color_str = "White" if user_color == chess.WHITE else "Black"
                print(f"[DEBUG] Analyzing {color_str} move #{user_move_count}: {move_san} (fullmove: {board_before.fullmove_number})")
            
            # ALWAYS do first engine call (get best move and evaluation)
            info_before_move = engine.analyse(board, chess.engine.Limit(time=engine_think_time)) # get eval and best move from before the move was made
            engine_calls_made += 1 # increment engine call counter
            best_move_info = info_before_move # alias for the best move info
            
            # Apply the move
            board.push(move) # make target player's move
            
            # SELECTIVE: Use enhanced heuristics to determine if second engine call is needed
            needs_second_call = enhanced_blunder_heuristics(board_before, move, best_move_info, engine_think_time, user_color, debug_mode) # check if second engine call needed
            
            if needs_second_call: # if heuristics suggest potential blunder
                # Do second engine call only when heuristics suggest potential blunder
                info_after_move = engine.analyse(board, chess.engine.Limit(time=engine_think_time)) # get eval from after the move was made
                engine_calls_made += 1 # increment engine call counter
                
                # Full blunder analysis with both evaluations
                blunder_info = categorize_blunder(
                    board_before, board, move, info_before_move, info_after_move, best_move_info,
                    blunder_threshold, debug_mode, actual_move_number
                ) # analyze for blunders
                if blunder_info: # if blunder found
                    blunders.append(blunder_info) # add to blunders list
            else: # if heuristics suggest move is fine
                # Skip second engine call - heuristics suggest move is fine
                if debug_mode: print(f"[DEBUG] Skipping second engine call for {board_before.san(move)}") # debug output
        else: # if it's opponent's turn
            board.push(move) # make opponent's move without analysis
    
    if debug_mode and total_moves > 0: # if debug mode and moves were analyzed
        engine_calls_per_move = engine_calls_made / total_moves # calculate average engine calls per move
        print(f"[DEBUG] STATS: {engine_calls_made} engine calls for {total_moves} moves = {engine_calls_per_move:.2f} calls/move") # debug output
    
    return blunders # return list of found blunders

def main():
    """
    Main function that handles command line arguments, initializes the engine,
    processes games, and outputs results.
    Uses: analyze_game.
    Time complexity: O(g * m * e) where g is number of games, m is moves per game, e is engine think time.
    """
    start = time.perf_counter()  # start timer for performance measurement

    parser = argparse.ArgumentParser(description="Analyze chess games to find blunders.") # create argument parser
    parser.add_argument("--pgn", default="testgames.pgn", help="Path to the PGN file (default: testgames.pgn).") # pgn file argument
    parser.add_argument("--username", default="test", help="Your username to analyze blunders for (default: test).") # username argument
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug print statements.") # debug flag
    parser.add_argument("--stockfish_path", default=STOCKFISH_PATH_DEFAULT, help="Path to the Stockfish executable.") # stockfish path argument
    parser.add_argument("--blunder_threshold", type=float, default=BLUNDER_THRESHOLD_DEFAULT, help="Win probability drop threshold for a blunder.") # blunder threshold argument
    parser.add_argument("--engine_think_time", type=float, default=ENGINE_THINK_TIME_DEFAULT, help="Engine think time per move in seconds.") # engine think time argument
    args = parser.parse_args() # parse command line arguments

    print(f"--- Running optimized analysis ---\n") # print header
    engine = chess.engine.SimpleEngine.popen_uci(args.stockfish_path) # initialize stockfish engine
    
    try: # try block for file operations
        with open(args.pgn) as pgn_file: # open pgn file
            game_num = 1 # initialize game counter
            total_blunders = [] # list to store all blunders found
            while True: # loop through all games in file
                game = chess.pgn.read_game(pgn_file) # read next game
                if game is None: break # if no more games, exit loop
                white_player = game.headers.get("White", "Unknown") # get white player name
                black_player = game.headers.get("Black", "Unknown") # get black player name
                print(f"Analyzing game #{game_num}: {white_player} vs {black_player}") # print game info
                
                blunders = analyze_game(game, engine, args.username, args.blunder_threshold, args.engine_think_time, args.debug) # analyze game for blunders
                
                for blunder in blunders: # for each blunder found
                    print(f"  -> {blunder['category']}: On move {blunder['move_number']}, {blunder['description']}") # print blunder info
                total_blunders.extend(blunders) # add blunders to total list
                game_num += 1 # increment game counter
    except FileNotFoundError: # if file not found
        print(f"Error: The file '{args.pgn}' was not found.") # print error message
    finally: # always execute
        print("\n--- Quitting engine ---") # print message
        engine.quit() # close engine

    print("\n--- Analysis Complete ---") # print completion message
    print(f"Found a total of {len(total_blunders)} mistakes/blunders for user '{args.username}'.\n") # print total blunders found

    end = time.perf_counter()  # end timer
    print(f"Total runtime: {end - start:.2f} seconds")  # print elapsed time

if __name__ == "__main__":
    main() # run main function if script is executed directly