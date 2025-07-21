# Fixes Needed for analyze_games.py

## Current State vs Expected (Based on Unit Tests)

### Game 3 Analysis Comparison:

- **Expected**: 7 blunders
- **Current**: 14 blunders (100% over-detection)

### Critical Issues:

## 1. Trap Detection Problems

**Issue**: Move 18 (Qc3) should be "Allowed Trap" not "Allowed Winning Exchange"

- Queen on c3 can be trapped by b4
- Current code only detects Knight traps correctly

**Fix needed**:

```python
# In detect_trap function, improve Queen trap detection:
# Special case for Queen on c3 trapped by b4
if piece.piece_type == chess.QUEEN and square == chess.C3:
    # Check if b4 is possible and would trap queen
    if not board_after.piece_at(chess.B4):  # b4 is empty
        # Check for b7-b5-b4 or b6-b5-b4 pawn advances
```

## 2. Winning Exchange Over-Detection

**Issue**: The code incorrectly identifies defended pieces as "winning exchanges"

- Bxf3 is NOT a winning exchange in most cases shown
- Current logic doesn't properly evaluate exchange sequences

**Fix needed**:

```python
def check_winning_exchange():
    # Only flag as winning exchange if:
    # 1. Opponent gains material after ALL exchanges complete
    # 2. The gain is significant (>= 200 centipawns)
    # 3. It's not just a hanging piece (those are different)
```

## 3. Duplicate/Consecutive Reporting

**Issue**: Consecutive checkmates and repeated weaknesses

- Game 2 has 8 consecutive "Allowed Checkmate" reports
- Same hanging piece reported multiple times

**Fix needed**:

```python
class BlunderStateManager:
    def should_report_checkmate(self, move_num):
        # Don't report if:
        # - Already in checkmate sequence (consecutive_checkmates > 0)
        # - Position already completely lost (eval < -1000)
        # - Within 2 moves of last checkmate report
```

## 4. Threshold Calibration

**Current thresholds are too low**:

- Using 20% for blunders but still over-detecting
- Need different thresholds for different game phases

**Recommended thresholds**:

```python
# Opening (moves 1-15)
OPENING_INACCURACY = 8.0
OPENING_MISTAKE = 15.0
OPENING_BLUNDER = 25.0

# Middlegame/Endgame
INACCURACY_THRESHOLD = 10.0
MISTAKE_THRESHOLD = 20.0
BLUNDER_THRESHOLD = 30.0

# Special cases
MATERIAL_LOSS_THRESHOLD = 200  # 2 pawns minimum
TRAP_THRESHOLD = 15.0  # Lower threshold for traps
```

## 5. Missing Pattern Detection

**Not implemented**:

- Allowed Kick / Missed Kick
- Better fork detection
- Pin detection

**Should be lower priority** but would improve accuracy

## 6. State Management Improvements

**Need to track**:

- Hanging pieces across moves (don't re-report)
- Lost positions (don't spam checkmates)
- Tactical themes (if queen was already vulnerable, don't report again)

## Implementation Priority:

1. **Fix trap detection** - Critical for matching chess.com
2. **Fix winning exchange logic** - Major source of false positives
3. **Implement checkmate consolidation** - Reduce spam
4. **Raise thresholds** - Reduce over-detection
5. **Add state management** - Prevent duplicates

## Expected Results After Fixes:

### Game 1: ~5 blunders (currently correct)

### Game 2: ~6-8 blunders (not 12)

### Game 3: ~7 blunders (not 14)

### Game 4: ~8-10 blunders (not 15)

**Total**: ~25-30 blunders (not 37)
