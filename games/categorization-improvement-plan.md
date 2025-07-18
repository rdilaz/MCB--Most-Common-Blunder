# MCB Blunder Categorization Improvement Plan

## Implementation Steps for AI Agent

### Phase 1: Fix "Hanging a Piece" Definition

1. **Locate the function**: Open `analyze_games.py` and find `check_for_material_loss()` (lines 335-549)

2. **Simplify the hanging piece detection**:
   ```python
   # Replace the complex SEE-based logic with simple defender counting
   # Around line 390-450, replace the current logic with:
   
   for square in chess.SQUARES:
       piece = board_after.piece_at(square)
       if piece and piece.color == turn_color:
           attackers = board_after.attackers(not turn_color, square)
           if attackers:
               defenders = board_after.attackers(turn_color, square)
               
               # CRITICAL: A piece is hanging ONLY if it has NO defenders
               if len(defenders) == 0:
                   # This is a truly hanging piece
                   # Add to hanging_pieces list with appropriate metadata
               else:
                   # This piece is defended - NOT hanging
                   # Save this for the new "Allowed Winning Exchange" category
   ```

3. **Remove the tactical filtering logic** (lines ~470-510):
   - Delete the section that checks for "strong tactical responses"
   - Remove the `should_filter_out` logic
   - Keep only the basic hanging piece detection

### Phase 2: Add "Allowed Winning Exchange for Opponent" Category

1. **Update `config.py`**:
   ```python
   # Add to BLUNDER_CATEGORY_PRIORITY (after "Hanging a Piece"):
   "Allowed Winning Exchange for Opponent": 4,
   # Shift other priorities down by 1
   
   # Add to CATEGORY_WEIGHTS:
   "Allowed Winning Exchange for Opponent": 1.8,
   
   # Add to BASE_IMPACT_VALUES:
   "Allowed Winning Exchange for Opponent": 20.0,
   
   # Add to BLUNDER_EDUCATIONAL_DESCRIPTIONS:
   "Allowed Winning Exchange for Opponent": "You left pieces in positions where they could be captured with a favorable exchange for your opponent. While the piece was defended, the sequence of captures would result in material loss."
   
   # Add to BLUNDER_GENERAL_DESCRIPTIONS:
   "Allowed Winning Exchange for Opponent": "You positioned pieces where capturing them would win material for your opponent through a series of exchanges."
   ```

2. **Create new check function in `analyze_games.py`**:
   ```python
   def check_for_winning_exchange(board_before, move_played, board_after, turn_color, debug_mode, actual_move_number):
       """
       Checks if the move allows opponent to win material through exchanges.
       This captures defended pieces where SEE favors the opponent.
       """
       # Implementation:
       # 1. Iterate through all player's pieces
       # 2. Check if they have attackers
       # 3. Check if they have defenders (len(defenders) > 0)
       # 4. Calculate SEE for opponent capturing
       # 5. If SEE > threshold (e.g., 100), it's a winning exchange
       # 6. Return appropriate blunder dict
   ```

3. **Integrate into `categorize_blunder()` function**:
   - Add call to `check_for_winning_exchange()` after `check_for_material_loss()`
   - Ensure proper priority ordering

### Phase 3: Adjust Weights and Priorities

1. **In `config.py`, update weights**:
   ```python
   CATEGORY_WEIGHTS = {
       "Allowed Checkmate": 3.0,
       "Missed Checkmate": 3.0,
       "Hanging a Piece": 2.5,  # Reduce from 3.0
       "Allowed Winning Exchange for Opponent": 1.8,  # New
       "Allowed Fork": 2.0,
       # ... rest remains the same
   }
   ```

2. **Update BASE_IMPACT_VALUES**:
   ```python
   BASE_IMPACT_VALUES = {
       'Hanging a Piece': 30.0,  # Reduce from 35.0
       'Allowed Winning Exchange for Opponent': 20.0,  # New
       # ... rest remains the same
   }
   ```

### Phase 4: Testing and Validation

1. **Create test positions** in a test PGN file:
   - Position 1: Truly hanging piece (0 defenders)
   - Position 2: Defended piece with unfavorable exchange
   - Position 3: Well-defended piece (should not trigger any category)

2. **Run analysis with debug mode**:
   ```bash
   python analyze_games.py --pgn test_positions.pgn --username test --debug
   ```

3. **Verify categorization**:
   - Hanging pieces only when defenders = 0
   - Winning exchanges when defenders > 0 but SEE favors opponent
   - No false positives for well-defended pieces

### Phase 5: Update Frontend Display

1. **Update any frontend components** that display category descriptions to include the new category

2. **Ensure the new category appears in**:
   - Blunder breakdown displays
   - Category statistics
   - Educational tooltips

### Critical Implementation Notes

1. **Preserve existing functionality**: Don't break other categorization functions
2. **Maintain performance**: The new checks shouldn't significantly slow analysis
3. **Consider edge cases**:
   - En passant captures
   - Pinned pieces
   - Discovered attacks
4. **Debug thoroughly**: Use debug mode to verify each change

### Rollback Plan

If issues arise:
1. Keep original `analyze_games.py` as backup
2. Test changes on small game sets first
3. Monitor for unexpected categorization patterns
4. Have ability to revert config changes quickly

### Success Metrics

After implementation, verify:
1. "Hanging a Piece" count decreases significantly
2. New "Allowed Winning Exchange" category captures previously miscategorized blunders
3. Overall categorization distribution is more balanced
4. User feedback improves regarding accuracy of "hanging piece" identification