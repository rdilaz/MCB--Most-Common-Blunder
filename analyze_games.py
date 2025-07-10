import chess
import chess.pgn
import chess.engine
import os 
import argparse
import math
import time

# ---- Constants ----
STOCKFISH_PATH_DEFAULT = os.path.join(os.path.dirname(__file__), "stockfish", "stockfish.exe")
BLUNDER_THRESHOLD_DEFAULT = 15
ENGINE_THINK_TIME_DEFAULT = 0.1
BLUNDER_CATEGORY_PRIORITY = {
    "Allowed Checkmate": 1,
    "Missed Checkmate": 2,
    "Hanging a Piece": 3,  # Moved up - hanging pieces are more critical
    "Allowed Fork": 4,
    "Missed Fork": 5,
    "Losing Exchange": 6,
    "Missed Material Gain": 7,
    "Allowed Pin": 8,
    "Missed Pin": 9,  # Moved down - pins are less critical than hanging pieces
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
        if see_value > 100: # if capture is worth more than 100 points (more than a pawn)
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
            return {"category": "Missed Material Gain", "move_number": actual_move_number, "description": description, "punishing_move": best_move} # return blunder dict
    
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
    
    # Check for hanging pieces using improved SEE logic
    hanging_pieces = [] # list to store hanging pieces with their tactical significance
    
    if debug_mode: print(f"[DEBUG] Checking for hanging pieces after move {move_played_san}...")
    
    for square in chess.SQUARES: # iterate over all squares
        piece = board_after.piece_at(square) # get piece at square
        if piece and piece.color == turn_color: # check if its player's piece 
            if debug_mode: print(f"[DEBUG]   Checking {PIECE_NAMES.get(piece.piece_type, 'piece')} on {chess.square_name(square)}")
            
            attackers = board_after.attackers(not turn_color, square) # get attackers of that square
            if attackers: # if there are attackers
                defenders = board_after.attackers(turn_color, square) # get defenders of that square
                defenders_before = board_before.attackers(turn_color, square) # get defenders before the move
                defenders_changed = len(defenders) != len(defenders_before) # check if defenders changed
                
                if debug_mode: 
                    print(f"[DEBUG]     Attackers: {len(attackers)}, Defenders: {len(defenders)} (was {len(defenders_before)})")
                    if defenders_changed:
                        print(f"[DEBUG]     ** Defenders changed due to move! **")
                
                lva_square = min(attackers, key=lambda s: PIECE_VALUES.get(board_after.piece_at(s).piece_type, 0)) # find least valuable attacker
                lva_piece = board_after.piece_at(lva_square) # get lva piece
                if not lva_piece: continue # safety, if no lva piece, continue
                
                capture_move = chess.Move(lva_square, square) # create capture move
                if lva_piece.piece_type == chess.PAWN and chess.square_rank(square) in [0, 7]: # if pawn promotion, assume promotion to queen
                    capture_move.promotion = chess.QUEEN # promote to queen
                
                piece_value = PIECE_VALUES.get(piece.piece_type, 0) # get value of piece
                see_value = see(board_after, capture_move) # calculate static exchange evaluation
                
                if debug_mode: print(f"[DEBUG]     SEE value: {see_value}, Piece value: {piece_value}")
                
                # Get thresholds based on piece type
                if piece.piece_type == chess.PAWN:
                    hanging_threshold = 50  # For pawns, need to win at least 50 centipawns
                elif piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
                    hanging_threshold = 150  # For minor pieces, need to win at least 150 centipawns
                elif piece.piece_type == chess.ROOK:
                    hanging_threshold = 200  # For rooks, need to win at least 200 centipawns
                elif piece.piece_type == chess.QUEEN:
                    hanging_threshold = 400  # For queens, need to win at least 400 centipawns
                else:
                    hanging_threshold = 100  # Default threshold
                
                if debug_mode: print(f"[DEBUG]     Threshold: {hanging_threshold}")
                
                # Check if the piece is truly hanging
                if see_value >= hanging_threshold:
                    if debug_mode: print(f"[DEBUG]     SEE value ({see_value}) >= threshold ({hanging_threshold}), checking for tactical responses...")
                    # ENHANCED: Check if the opponent's capture would be a blunder for them
                    # Simulate the opponent capturing this piece
                    board_after_capture = board_after.copy()
                    board_after_capture.push(capture_move)
                    
                    # Check if we have a strong tactical response (like capturing a queen)
                    our_best_responses = []
                    for response_move in board_after_capture.legal_moves:
                        if board_after_capture.is_capture(response_move):
                            response_see = see(board_after_capture, response_move)
                            if response_see > 200:  # Lower threshold - rook+ value material
                                our_best_responses.append((response_move, response_see))
                    
                    if debug_mode: print(f"[DEBUG]     Found {len(our_best_responses)} tactical responses")
                    
                    # IMPROVED LOGIC: Only filter out if our response wins SIGNIFICANTLY more than we lose
                    # This prevents filtering out legitimate hanging pieces
                    should_filter_out = False
                    if our_best_responses:
                        max_response_value = max(response[1] for response in our_best_responses)
                        # Only filter out if:
                        # 1. Our response wins at least 200 more centipawns than we lose (not just more)
                        # 2. AND the response value is substantial (500+ centipawns, like a queen)
                        net_gain = max_response_value - piece_value
                        if debug_mode: print(f"[DEBUG]     Max response value: {max_response_value}, Net gain: {net_gain}")
                        if net_gain >= 200 and max_response_value >= 500:
                            should_filter_out = True
                            if debug_mode:
                                print(f"[DEBUG]     Filtering out: Piece {PIECE_NAMES.get(piece.piece_type, 'piece')} on {chess.square_name(square)} appears hanging but capturing it would be a blunder for opponent (net gain: {net_gain}, response value: {max_response_value})")
                    
                    if not should_filter_out:
                        if debug_mode: print(f"[DEBUG]     Adding to hanging pieces list")
                        # Store hanging piece info for comparison
                        hanging_pieces.append({
                            'square': square,
                            'piece': piece,
                            'see_value': see_value,
                            'piece_value': piece_value,
                            'capture_move': capture_move,
                            'attackers': len(attackers),
                            'defenders': len(defenders),
                            'defenders_changed': defenders_changed  # Track if this move affected the piece's defense
                        })
                    else:
                        if debug_mode: print(f"[DEBUG]     Filtered out due to tactical response")
                else:
                    # ENHANCED: Check if this piece is hanging due to a checking capture
                    # Even if SEE is below threshold, a check might make it hanging
                    if board_after.gives_check(capture_move):
                        if debug_mode: print(f"[DEBUG]     Capture gives check - piece may be hanging despite low SEE")
                        # When the capture gives check, the defending side must respond to check
                        # This often means they can't immediately recapture, making the piece effectively hanging
                        
                        # For checking captures, use a lower threshold
                        check_hanging_threshold = max(50, hanging_threshold // 3)  # Much lower threshold for checks
                        
                        if see_value >= check_hanging_threshold:
                            if debug_mode: print(f"[DEBUG]     Check capture SEE ({see_value}) >= check threshold ({check_hanging_threshold}), piece is hanging")
                            
                            # Store hanging piece info for comparison
                            hanging_pieces.append({
                                'square': square,
                                'piece': piece,
                                'see_value': see_value,
                                'piece_value': piece_value,
                                'capture_move': capture_move,
                                'attackers': len(attackers),
                                'defenders': len(defenders),
                                'defenders_changed': defenders_changed,  # Track if this move affected the piece's defense
                                'is_check': True  # Flag this as a checking capture
                            })
                        else:
                            if debug_mode: print(f"[DEBUG]     Check capture SEE ({see_value}) < check threshold ({check_hanging_threshold}), not hanging")
                    else:
                        if debug_mode: print(f"[DEBUG]     SEE value ({see_value}) < threshold ({hanging_threshold}), not hanging")
            else:
                if debug_mode: print(f"[DEBUG]     No attackers")
    
    if debug_mode: print(f"[DEBUG] Found {len(hanging_pieces)} hanging pieces total")
    
    # If we found hanging pieces, report the most significant one
    if hanging_pieces:
        # IMPROVED LOGIC: Prioritize pieces most affected by the move
        # Sort by: 1) Defenders changed by move, 2) Undefended pieces first (defenders = 0), 3) Then by piece value (higher first), 4) Then by SEE value
        def hanging_priority(piece_info):
            defenders = piece_info['defenders']
            piece_value = piece_info['piece_value']
            see_value = piece_info['see_value']
            defenders_changed = piece_info.get('defenders_changed', False)
            
            # Pieces whose defense was affected by the move get highest priority
            if defenders_changed:
                move_affected_priority = -2000  # Highest priority
            else:
                move_affected_priority = 0  # Lower priority
            
            # Truly undefended pieces get second highest priority
            if defenders == 0:
                undefended_priority = -1000  # Very high priority
            else:
                undefended_priority = defenders  # Lower priority for defended pieces
            
            # Tertiary sort by piece value (higher value pieces are more significant)
            # Quaternary sort by SEE value
            return (move_affected_priority, undefended_priority, -piece_value, -see_value)
        
        hanging_pieces.sort(key=hanging_priority)
        most_significant = hanging_pieces[0]
        
        piece_name = PIECE_NAMES.get(most_significant['piece'].piece_type, "piece")
        square_name = chess.square_name(most_significant['square'])
        
        # Check if this is a checking capture
        is_check_capture = most_significant.get('is_check', False)
        if is_check_capture:
            # For checking captures, provide a more detailed explanation
            capture_move_san = board_after.san(most_significant['capture_move'])
            description = f"your move {move_played_san} left your {piece_name} on {square_name} hanging. The opponent can play {capture_move_san} (check), forcing you to respond to the check before you can recapture."
        else:
            description = f"your move {move_played_san} left your {piece_name} on {square_name} undefended."
        
        if debug_mode: 
            print(f"[DEBUG] Most significant hanging piece:")
            print(f"[DEBUG]   Move played: {move_played_san}")
            print(f"[DEBUG]   Hanging piece: {piece_name} on {square_name}")
            print(f"[DEBUG]   Attackers: {most_significant['attackers']}, Defenders: {most_significant['defenders']}")
            print(f"[DEBUG]   SEE value: {most_significant['see_value']}, Piece value: {most_significant['piece_value']}")
            if is_check_capture:
                print(f"[DEBUG]   Note: This is a checking capture")
            if len(hanging_pieces) > 1:
                print(f"[DEBUG]   Note: {len(hanging_pieces)} pieces are hanging, reporting the most significant")
                print(f"[DEBUG]   All hanging pieces:")
                for i, hp in enumerate(hanging_pieces):
                    hp_name = PIECE_NAMES.get(hp['piece'].piece_type, "piece")
                    hp_square = chess.square_name(hp['square'])
                    def_changed = hp.get('defenders_changed', False)
                    priority_info = f"Def:{hp['defenders']}, Val:{hp['piece_value']}, SEE:{hp['see_value']}, DefChanged:{def_changed}"
                    print(f"[DEBUG]     {i+1}. {hp_name} on {hp_square} ({priority_info})")
                print(f"[DEBUG]   Selected: #{1} {piece_name} on {square_name} (prioritized by defense_affected > undefended > piece_value > SEE)")
        
        return {"category": "Hanging a Piece", "move_number": actual_move_number, "description": description, "punishing_move": most_significant['capture_move']}
    
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
    
    # Check 3: Material Loss using SEE (Hanging a Piece) - HIGH PRIORITY
    material_blunder = check_for_material_loss(board_before, move_played, board_after, turn_color, debug_mode, actual_move_number) # check for material loss
    if material_blunder: # if material loss found
        material_blunder["win_prob_drop"] = win_prob_drop # add win probability drop
        return material_blunder # return the blunder
    
    # Check 4: Allowed Fork
    allowed_fork = check_for_allowed_fork(board_after, info_after_move, turn_color, move_played, board_before, debug_mode, actual_move_number) # check for allowed fork
    if allowed_fork: # if allowed fork found
        allowed_fork["win_prob_drop"] = win_prob_drop # add win probability drop
        return allowed_fork # return the blunder
    
    # Check 5: Missed Fork
    missed_fork = check_for_missed_fork(board_before, best_move_info, turn_color, move_played, debug_mode, actual_move_number) # check for missed fork
    if missed_fork: # if missed fork found
        missed_fork["win_prob_drop"] = win_prob_drop # add win probability drop
        return missed_fork # return the blunder
    
    # Check 6: Allowed Pin
    allowed_pin = check_for_allowed_pin(board_after, info_after_move, turn_color, move_played, board_before, debug_mode, actual_move_number) # check for allowed pin
    if allowed_pin: # if allowed pin found
        allowed_pin["win_prob_drop"] = win_prob_drop # add win probability drop
        return allowed_pin # return the blunder
    
    # Check 7: Missed Pin - LOWER PRIORITY
    missed_pin = check_for_missed_pin(board_before, best_move_info, turn_color, move_played, debug_mode, actual_move_number) # check for missed pin
    if missed_pin: # if missed pin found
        missed_pin["win_prob_drop"] = win_prob_drop # add win probability drop
        return missed_pin # return the blunder
    
    # Check 8: Missed Material Gain using SEE
    missed_material = check_for_missed_material_gain(board_before, best_move_info, move_played, debug_mode, actual_move_number) # check for missed material gain
    if missed_material: # if missed material gain found
        missed_material["win_prob_drop"] = win_prob_drop # add win probability drop
        return missed_material # return the blunder
    
    # Check 9: General Mistake (fallback)
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
            
            # SELECTIVE: Use heuristics to determine if second engine call is needed
            needs_second_call = quick_blunder_heuristics(board_before, move, best_move_info, user_color, debug_mode) # check if second engine call needed
            
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