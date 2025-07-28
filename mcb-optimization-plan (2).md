# MCB Chess Analyzer - Performance Optimization Plan

## Executive Summary

Current performance: **20 games in ~60 seconds** (3 seconds per game)  
Target performance: **20 games in ~20 seconds** (1 second per game)  
Optimization factor: **3x speedup** while maintaining analysis accuracy

## Current State Analysis

### Performance Profile

- **Primary Bottleneck**: `categorize_blunder_optimized()` in `analyze_games.py`
- **Engine Calls**: ~1.4 calls per move × 35 moves/game × 20 games = 980 engine calls
- **Engine Time**: 0.08s per call × 980 calls = 78.4s theoretical minimum
- **Actual Time**: ~60s (good efficiency, but sequential processing limits throughput)

### Key Inefficiencies

1. **Sequential move analysis** within each game
2. **Redundant calculations** across similar positions
3. **Expensive trap detection** with full board simulations
4. **No engine request batching**
5. **Limited tactical pattern caching**

## Optimization Strategy

### Phase 1: Engine Call Optimization (Target: 40% reduction)

**Goal**: Reduce from ~60s to ~35s

#### Step 1.1: Implement Smart Engine Batching (DONE)

**Current State**: In `analyze_games.py`, lines 712-803, each move gets two separate engine calls:

```python
# Line 742: First engine call
info_before_move = engine.analyse(board, chess.engine.Limit(time=think_time))
# Line 756: Second engine call
info_after_move = engine.analyse(board, chess.engine.Limit(time=think_time))
```

**Implementation Steps**:

1. **Create batch analysis function in `analyze_games.py`** (add after line 690):

```python
def analyze_positions_batch(engine, positions_and_limits, debug_mode):
    """
    Analyze multiple positions in a single batch for efficiency.
    Args:
        engine: Chess engine instance
        positions_and_limits: List of (board, limit) tuples
        debug_mode: Debug flag
    Returns:
        List of analysis info objects
    """
    results = []
    # Check if engine supports batch analysis
    if hasattr(engine, 'analyse_batch'):
        # Use native batch support
        results = engine.analyse_batch(positions_and_limits)
    else:
        # Fallback to sequential with reduced overhead
        for board, limit in positions_and_limits:
            results.append(engine.analyse(board, limit))
    return results
```

2. **Modify `analyze_game_optimized()` function** (lines 690-810) to collect positions:

```python
def analyze_game_optimized(game, engine, target_user, blunder_threshold, engine_think_time, debug_mode):
    # ... existing setup code ...

    # NEW: Collect positions for batch analysis
    positions_to_analyze = []
    move_indices = []

    # First pass: collect all positions that need analysis
    temp_board = game.board()
    for move_idx, move in enumerate(all_moves):
        if temp_board.turn == user_color:
            if quick_heuristics_optimized(temp_board, move, None, user_color, state_manager, debug_mode):
                positions_to_analyze.append((
                    temp_board.copy(),
                    chess.engine.Limit(time=engine_think_time)
                ))
                move_indices.append(move_idx)
        temp_board.push(move)

    # NEW: Batch analyze all positions
    if positions_to_analyze:
        batch_results = analyze_positions_batch(engine, positions_to_analyze, debug_mode)

    # Second pass: process results
    board = game.board()
    result_idx = 0
    for move_idx, move in enumerate(all_moves):
        if board.turn == user_color and result_idx < len(move_indices) and move_idx == move_indices[result_idx]:
            # Use pre-computed results
            info_before_move = batch_results[result_idx * 2]
            info_after_move = batch_results[result_idx * 2 + 1]
            result_idx += 1
            # ... rest of the blunder detection logic ...
```

3. **Update `analysis_service.py`** to support batch mode (line 120):
   - Add configuration flag in `config.py` (line 30):
   ```python
   ENABLE_BATCH_ENGINE_ANALYSIS = True
   BATCH_ANALYSIS_SIZE = 20  # Positions per batch
   ```

#### Step 1.2: Enhanced Position Filtering (DONE)

**Current State**: In `analyze_games.py`, line 637, `quick_heuristics_optimized()` only does basic filtering.

**Implementation Steps**:

1. **Add opening book check function** in `analyze_games.py` (add after line 200):

```python
# Common opening moves in UCI format for the first 10 moves
OPENING_BOOK = {
    # Italian Game, Ruy Lopez, etc.
    1: ['e2e4', 'd2d4', 'g1f3', 'c2c4'],
    2: ['e7e5', 'd7d5', 'g8f6', 'c7c5', 'e7e6'],
    # Add more common moves...
}

def is_book_move(board, move):
    """Check if move is a common book move"""
    move_num = board.fullmove_number
    if move_num > 10:
        return False

    move_uci = move.uci()
    return move_uci in OPENING_BOOK.get(move_num, [])
```

2. **Add obvious recapture detection** in `analyze_games.py` (add after line 220):

```python
def is_obvious_recapture(board, move):
    """
    Check if move is an obvious recapture (equal or winning exchange).
    """
    if not board.is_capture(move):
        return False

    # Check if we're recapturing on a square that was just captured
    if len(board.move_stack) > 0:
        last_move = board.move_stack[-1]
        if board.is_capture(last_move) and last_move.to_square == move.to_square:
            # This is a recapture - check if it's obvious (equal or better)
            see_value = see(board, move)
            return see_value >= 0

    return False
```

3. **Enhance `quick_heuristics_optimized()` function** (replace lines 637-662):

```python
def quick_heuristics_optimized(board_before, move_played, best_move_info, turn_color, state_manager, debug_mode):
    """Ultra-fast heuristics using minimal computation - ENHANCED VERSION"""

    # NEW: Skip forced moves
    legal_moves = list(board_before.legal_moves)
    if len(legal_moves) == 1:
        if debug_mode:
            print(f"[DEBUG] Skipping forced move (only legal move)")
        return False

    # NEW: Skip book moves in opening
    if board_before.fullmove_number <= 10 and is_book_move(board_before, move_played):
        if debug_mode:
            print(f"[DEBUG] Skipping book move in opening")
        return False

    # NEW: Skip obvious recaptures
    if is_obvious_recapture(board_before, move_played):
        if debug_mode:
            print(f"[DEBUG] Skipping obvious recapture")
        return False

    # NEW: Skip simple endgames (use tablebase or skip)
    piece_count = len(board_before.piece_map())
    if piece_count <= 6:
        if debug_mode:
            print(f"[DEBUG] Skipping tablebase position ({piece_count} pieces)")
        return False

    # EXISTING: Skip quiet endgame positions
    if board_before.fullmove_number > 30 and piece_count < 10:
        if best_move_info:
            eval_cp = best_move_info["score"].pov(turn_color).score(mate_score=10000)
            if eval_cp is not None and abs(eval_cp) < 100:
                if debug_mode:
                    print(f"[DEBUG] Skipping quiet endgame position")
                return False

    # Continue with existing checks...
    # Always analyze tactical positions
    if board_before.fullmove_number <= 20:  # Opening/middlegame
        return True

    # Always analyze if best move is mate or capture
    if best_move_info:
        if best_move_info["score"].pov(turn_color).is_mate():
            return True

        if best_move_info.get('pv') and board_before.is_capture(best_move_info['pv'][0]):
            return True

    # Always analyze our captures and checks
    if board_before.is_capture(move_played) or board_before.gives_check(move_played):
        return True

    return True  # Default to analyzing
```

4. **Add position filtering metrics** in `config.py` (line 40):

```python
# Position Filtering Thresholds
SKIP_FORCED_MOVES = True
SKIP_BOOK_MOVES = True
SKIP_OBVIOUS_RECAPTURES = True
SKIP_TABLEBASE_POSITIONS = True
TABLEBASE_PIECE_LIMIT = 6
```

#### Step 1.3: Implement Lazy Evaluation (DONE)

**Current State**: In `analyze_games.py`, `categorize_blunder_optimized()` (lines 663-811) runs all checks sequentially.

**Implementation Steps**:

1. **Add evaluation change threshold check** at the beginning of `categorize_blunder_optimized()` (after line 670):

```python
def categorize_blunder_optimized(board_before, board_after, move_played, info_before_move, info_after_move,
                                best_move_info, state_manager, debug_mode, actual_move_number):
    """Optimized blunder categorization with LAZY EVALUATION"""
    move_played_san = board_before.san(move_played)
    turn_color = board_before.turn

    # Calculate win probability drop FIRST
    eval_before = info_before_move["score"].pov(turn_color).score(mate_score=10000)
    eval_after = info_after_move["score"].pov(turn_color).score(mate_score=10000)

    # NEW: Early exit if evaluation change is minimal
    if eval_before is not None and eval_after is not None:
        eval_drop = eval_before - eval_after
        if eval_drop < 50:  # Less than 0.5 pawn drop
            if debug_mode:
                print(f"[DEBUG] Skipping - minimal evaluation change: {eval_drop}")
            return None

    # Continue with win probability calculation...
    state_manager.update_eval(eval_after)
```

2. **Reorder blunder checks by frequency and cost** (replace lines 680-811):

```python
    # REORDERED: Check by frequency (most common first) and cost (cheapest first)

    # 1. CHEAP CHECK: Hanging pieces (most common, very fast)
    if win_prob_drop >= MISTAKE_THRESHOLD:
        hanging_result = check_for_hanging_piece_optimized(board_before, move_played, board_after,
                                                          turn_color, state_manager, debug_mode, actual_move_number)
        if hanging_result:
            hanging_result["win_prob_drop"] = win_prob_drop
            return hanging_result

    # 2. CHEAP CHECK: Missed material (common, fast)
    if win_prob_drop >= MISTAKE_THRESHOLD:
        missed_material = check_for_missed_material_gain_optimized(board_before, best_move_info, move_played,
                                                                  state_manager, debug_mode, actual_move_number)
        if missed_material:
            missed_material["win_prob_drop"] = win_prob_drop
            return missed_material

    # 3. MEDIUM CHECK: Checkmates (less common, medium cost)
    after_eval = info_after_move["score"].pov(turn_color)
    if after_eval.is_mate() and after_eval.mate() < 0:
        # Only check for new checkmates
        if not state_manager.in_losing_position or abs(after_eval.mate()) <= 1:
            mate_result = {
                "category": "Allowed Checkmate",
                "move_number": actual_move_number,
                "description": f"your move {move_played_san} allows checkmate in {abs(after_eval.mate())}",
                "win_prob_drop": win_prob_drop
            }
            return mate_result

    # Check missed checkmate
    best_eval = best_move_info["score"].pov(turn_color)
    if best_eval.is_mate() and best_eval.mate() > 0:
        if not after_eval.is_mate() or (after_eval.is_mate() and after_eval.mate() > best_eval.mate()):
            missed_mate_result = {
                "category": "Missed Checkmate",
                "move_number": actual_move_number,
                "description": f"your move {move_played_san} missed checkmate in {best_eval.mate()}",
                "win_prob_drop": max(win_prob_drop, 50.0)
            }
            return missed_mate_result

    # 4. EXPENSIVE CHECK: Traps (uncommon, very expensive)
    # NEW: Only check traps if significant drop AND not already found other blunders
    if win_prob_drop >= TRAP_THRESHOLD and win_prob_drop >= 20:  # Higher threshold
        trap_result = detect_trap_optimized(board_before, move_played, board_after, turn_color,
                                          state_manager, debug_mode)
        if trap_result:
            trap_result["move_number"] = actual_move_number
            trap_result["win_prob_drop"] = win_prob_drop
            return trap_result

    # 5. FALLBACK: General mistakes (only if nothing else found)
    if board_before.fullmove_number <= 15:
        # Opening thresholds...
        if win_prob_drop >= OPENING_BLUNDER:
            severity = "Blunder"
        elif win_prob_drop >= OPENING_MISTAKE:
            severity = "Mistake"
        else:
            return None
    else:
        # Middle/endgame thresholds...
        if win_prob_drop >= CRITICAL_THRESHOLD:
            severity = "Critical blunder"
        elif win_prob_drop >= BLUNDER_THRESHOLD:
            severity = "Blunder"
        elif win_prob_drop >= MISTAKE_THRESHOLD:
            severity = "Mistake"
        else:
            return None

    # Only create general mistake if we have a better move to suggest
    if severity in ["Mistake", "Blunder", "Critical blunder"]:
        best_move = best_move_info['pv'][0] if best_move_info.get('pv') else None
        if best_move:
            best_move_san = board_before.san(best_move)
            return {
                "category": severity,
                "move_number": actual_move_number,
                "description": f"your move {move_played_san} is a {severity.lower()} (win probability dropped {win_prob_drop:.1f}%). Better was {best_move_san}",
                "win_prob_drop": win_prob_drop
            }

    return None
```

3. **Add lazy evaluation configuration** in `config.py` (line 45):

```python
# Lazy Evaluation Thresholds
MIN_EVAL_DROP_FOR_ANALYSIS = 50  # Centipawns
EXPENSIVE_CHECK_THRESHOLD = 20    # Win probability drop % before running expensive checks
```

**Testing Instructions**:

1. Create a test file `test_phase1_optimizations.py`
2. Run the current version on 20 test games and record time
3. Implement each step and verify blunder detection accuracy remains above 95%
4. Measure performance improvement after each step
5. The combination should achieve 25-40% performance improvement

### Phase 2: Parallel Move Analysis (Target: 50% reduction)

**Goal**: Reduce from ~35s to ~18s

#### Step 2.1: Intra-Game Parallelization

```python
# Current: Sequential move-by-move analysis
# Optimized: Analyze independent move sequences in parallel
```

- **Implementation**:
  - Split game into move chunks (5-10 moves each)
  - Use ThreadPoolExecutor for parallel chunk analysis
  - Maintain move ordering for dependencies
- **Impact**: 2-3x speedup on multi-core systems
- **Risk**: Medium - need careful state management

#### Step 2.2: Async Engine Communication

```python
# Current: Synchronous engine.analyse() calls
# Optimized: Async/await pattern with engine pool
```

- **Implementation**: Create async wrapper for engine calls
- **Impact**: Hide I/O latency, 20-30% improvement
- **Risk**: Medium - requires refactoring engine pool

### Phase 3: Advanced Caching & Pattern Recognition (Target: 30% reduction)

**Goal**: Reduce from ~18s to ~12s

#### Step 3.1: Expanded Position Cache

```python
# Current: Basic position cache (1000 entries)
# Optimized: Multi-level cache with pattern recognition
```

- **Implementation**:
  - L1: Exact position cache (10K entries)
  - L2: Pattern cache (hanging pieces, pins, forks)
  - L3: Evaluation cache for similar structures
- **Impact**: 50% cache hit rate on typical games
- **Risk**: Low - more memory usage but controllable

#### Step 3.2: Tactical Pattern Pre-computation

```python
# Pre-compute common patterns once per position:
# - All hanging pieces
# - All pins/skewers
# - All fork possibilities
# - All discovered attack setups
```

- **Implementation**: Single pass pattern extraction in `analyze_position_cached()`
- **Impact**: Eliminate redundant calculations
- **Risk**: Low - consolidates existing logic

#### Step 3.3: Optimized Trap Detection

```python
# Current: Simulates every opponent move
# Optimized: Use heuristics to filter candidate moves
```

- **Implementation**:
  - Only check moves that attack/restrict piece mobility
  - Use piece mobility index instead of full simulation
  - Cache trap patterns
- **Impact**: 80% reduction in trap detection time
- **Risk**: Low - maintains accuracy with smart heuristics

### Phase 4: Algorithm Optimization (Target: 25% reduction)

**Goal**: Reduce from ~12s to ~9s

#### Step 4.1: Replace SEE with Simplified Exchange Calculator

```python
# Current: Recursive SEE with caching
# Optimized: Table-based exchange evaluation
```

- **Implementation**: Pre-computed exchange tables for common scenarios
- **Impact**: 10x faster for simple exchanges
- **Risk**: Low - SEE is already well-optimized

#### Step 4.2: Vectorized Board Operations

```python
# Use numpy arrays for board representation
# Vectorize attack/defend calculations
```

- **Implementation**: NumPy-based board operations
- **Impact**: 2-3x faster board manipulation
- **Risk**: Medium - significant refactoring

### Phase 5: Infrastructure Optimization (Target: 15% reduction)

**Goal**: Reach target of ~8-10s for 20 games

#### Step 5.1: Engine Pool Optimization

```python
# Dynamic pool sizing based on workload
# Pre-warmed engines
# Connection pooling
```

- **Implementation**: Enhanced `StockfishPool` with predictive scaling
- **Impact**: Eliminate engine startup overhead
- **Risk**: Low

#### Step 5.2: Memory-Mapped PGN Processing

```python
# Current: Load entire PGN into memory
# Optimized: Memory-mapped file access
```

- **Implementation**: Use mmap for large PGN files
- **Impact**: Faster I/O, lower memory usage
- **Risk**: Low

## Implementation Plan

### Week 1: Low-Risk Optimizations

1. **Day 1-2**: Implement enhanced position filtering (Step 1.2)
2. **Day 3-4**: Implement lazy evaluation (Step 1.3)
3. **Day 5**: Testing and benchmarking
   - Expected improvement: 20-30%

### Week 2: Engine Optimization

1. **Day 1-3**: Implement engine batching (Step 1.1)
2. **Day 4-5**: Implement async engine communication (Step 2.2)
   - Expected improvement: 30-40%

### Week 3: Parallelization

1. **Day 1-4**: Implement intra-game parallelization (Step 2.1)
2. **Day 5**: Integration testing
   - Expected improvement: 50-60%

### Week 4: Advanced Optimizations

1. **Day 1-2**: Implement expanded caching (Step 3.1)
2. **Day 3-4**: Optimize trap detection (Step 3.3)
3. **Day 5**: Final optimization and testing
   - Expected improvement: 70-80%

## Testing Strategy

### Accuracy Testing

```python
# Create test suite with known blunders
test_games = [
    "games/known_blunders.pgn",  # 50 games with verified blunders
    "games/no_blunders.pgn",     # 20 perfect games
    "games/complex_tactics.pgn"   # 30 games with complex patterns
]

# For each optimization:
# 1. Run original algorithm
# 2. Run optimized algorithm
# 3. Compare results (must be 95%+ match)
# 4. Measure performance improvement
```

### Performance Testing

```python
# Benchmark suite
benchmarks = {
    "small": 10 games,
    "medium": 50 games,
    "large": 200 games
}

# Track metrics:
# - Total time
# - Engine calls
# - Cache hit rates
# - Memory usage
# - CPU utilization
```

### Regression Testing

- Maintain test suite of edge cases
- Automated testing on each commit
- Performance regression alerts

## Risk Mitigation

### Accuracy Risks

- **Mitigation**: Keep original algorithm as fallback
- **Testing**: Extensive comparison testing
- **Rollback**: Feature flags for each optimization

### Performance Risks

- **Mitigation**: Incremental rollout
- **Monitoring**: Real-time performance metrics
- **Scaling**: Adjust parallelization based on system resources

## Success Metrics

### Primary Metrics

- **Analysis Time**: 20 games in <20 seconds (3x improvement)
- **Accuracy**: 95%+ blunder detection rate maintained
- **Scalability**: Linear scaling up to 200 games

### Secondary Metrics

- **Memory Usage**: <500MB for 20 games
- **CPU Efficiency**: 80%+ CPU utilization during analysis
- **Cache Hit Rate**: >50% for typical games

## Code Examples for Implementation

### Example 1: Engine Batching

```python
def analyze_moves_batch(board_positions, engine, think_time):
    """Analyze multiple positions in a single engine request"""
    # Collect positions
    batch_requests = []
    for pos in board_positions:
        batch_requests.append({
            'fen': pos.fen(),
            'depth': 15,
            'time': think_time
        })

    # Single batched call
    results = engine.analyse_batch(batch_requests)
    return results
```

### Example 2: Parallel Move Analysis

```python
def analyze_game_parallel(game, engine_pool, config):
    """Analyze game with parallel move processing"""
    moves = list(game.mainline_moves())

    # Split into chunks
    chunk_size = 10
    chunks = [moves[i:i+chunk_size] for i in range(0, len(moves), chunk_size)]

    # Parallel analysis
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for chunk in chunks:
            future = executor.submit(analyze_chunk, chunk, engine_pool.get_engine())
            futures.append(future)

        # Collect results
        results = []
        for future in as_completed(futures):
            results.extend(future.result())

    return merge_results(results)
```

### Example 3: Smart Position Filtering

```python
def should_analyze_position(board, move, game_phase):
    """Determine if position needs deep analysis"""
    # Skip forced moves
    if len(list(board.legal_moves)) == 1:
        return False

    # Skip book moves
    if board.fullmove_number <= 10 and is_book_move(board, move):
        return False

    # Skip obvious recaptures
    if is_obvious_recapture(board, move):
        return False

    # Skip simple endgames
    if len(board.piece_map()) <= 6:
        return use_tablebase(board)

    return True
```

## Conclusion

This optimization plan provides a clear path to achieve 3x performance improvement while maintaining analysis accuracy. The phased approach allows for incremental improvements with measurable results at each stage. By focusing on the primary bottlenecks and implementing both algorithmic and infrastructure optimizations, we can reach the target of analyzing 20 games in under 20 seconds.
