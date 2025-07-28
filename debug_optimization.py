#!/usr/bin/env python3
"""
Debug script to test Phase 1 optimizations and measure actual performance impact.
This will help identify if optimizations are working as expected.
"""

import time
import chess
import chess.pgn
import chess.engine
import os
import sys
from analyze_games import (
    analyze_game_optimized, BlunderStateManager, 
    quick_heuristics_optimized, categorize_blunder_optimized,
    is_book_move, is_obvious_recapture, analyze_positions_batch
)
from engines.stockfish_pool import get_engine_pool
from config import (
    ENABLE_BATCH_ENGINE_ANALYSIS, BATCH_ANALYSIS_SIZE,
    SKIP_FORCED_MOVES, SKIP_BOOK_MOVES, SKIP_OBVIOUS_RECAPTURES,
    SKIP_TABLEBASE_POSITIONS, MIN_EVAL_DROP_FOR_ANALYSIS,
    EXPENSIVE_CHECK_THRESHOLD, STOCKFISH_PATH
)

def test_configuration():
    """Test that all configuration flags are properly set"""
    print("=== CONFIGURATION TEST ===")
    print(f"ENABLE_BATCH_ENGINE_ANALYSIS: {ENABLE_BATCH_ENGINE_ANALYSIS}")
    print(f"BATCH_ANALYSIS_SIZE: {BATCH_ANALYSIS_SIZE}")
    print(f"SKIP_FORCED_MOVES: {SKIP_FORCED_MOVES}")
    print(f"SKIP_BOOK_MOVES: {SKIP_BOOK_MOVES}")
    print(f"SKIP_OBVIOUS_RECAPTURES: {SKIP_OBVIOUS_RECAPTURES}")
    print(f"SKIP_TABLEBASE_POSITIONS: {SKIP_TABLEBASE_POSITIONS}")
    print(f"MIN_EVAL_DROP_FOR_ANALYSIS: {MIN_EVAL_DROP_FOR_ANALYSIS}")
    print(f"EXPENSIVE_CHECK_THRESHOLD: {EXPENSIVE_CHECK_THRESHOLD}")
    print()

def test_position_filtering():
    """Test position filtering functions"""
    print("=== POSITION FILTERING TEST ===")
    
    # Test book move detection
    board = chess.Board()
    e4_move = chess.Move.from_uci('e2e4')
    d4_move = chess.Move.from_uci('d2d4')
    weird_move = chess.Move.from_uci('a2a4')
    
    print(f"e2e4 is book move: {is_book_move(board, e4_move)}")
    print(f"d2d4 is book move: {is_book_move(board, d4_move)}")
    print(f"a2a4 is book move: {is_book_move(board, weird_move)}")
    
    # Test forced move detection
    # Create a position with only one legal move
    board_check = chess.Board("rnbqkb1r/pppp1ppp/5n2/4p3/2B1P3/8/PPPP1PpP/RNBQK1NR w KQkq - 0 4")
    legal_moves = list(board_check.legal_moves)
    print(f"Legal moves in test position: {len(legal_moves)}")
    
    # Test obvious recapture
    board_recap = chess.Board()
    board_recap.push_san("e4")
    board_recap.push_san("e5")
    board_recap.push_san("Nf3")
    board_recap.push_san("Nc6")
    board_recap.push_san("Nxe5")  # Capture
    last_move = board_recap.move_stack[-1]
    recap_move = chess.Move.from_uci('c6e5')  # Recapture
    
    print(f"Nxe5 recapture is obvious: {is_obvious_recapture(board_recap, recap_move, last_move)}")
    print()

def test_quick_heuristics():
    """Test quick_heuristics_optimized function with different scenarios"""
    print("=== QUICK HEURISTICS TEST ===")
    
    # Mock best_move_info
    mock_best_info = {
        'score': chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE),
        'pv': [chess.Move.from_uci('e2e4')]
    }
    
    state_manager = BlunderStateManager()
    
    # Test 1: Book move in opening
    board = chess.Board()
    e4_move = chess.Move.from_uci('e2e4')
    result1 = quick_heuristics_optimized(board, e4_move, mock_best_info, chess.WHITE, state_manager, True, None)
    print(f"Book move e2e4 should be skipped: {not result1}")
    
    # Test 2: Non-book move in opening
    a4_move = chess.Move.from_uci('a2a4')
    result2 = quick_heuristics_optimized(board, a4_move, mock_best_info, chess.WHITE, state_manager, True, None)
    print(f"Non-book move a2a4 should be analyzed: {result2}")
    
    # Test 3: Forced move (only one legal move)
    board_forced = chess.Board("8/8/8/8/8/8/7k/7K w - - 0 1")  # King vs King, limited moves
    legal_moves = list(board_forced.legal_moves)
    if len(legal_moves) == 1:
        forced_move = legal_moves[0]
        result3 = quick_heuristics_optimized(board_forced, forced_move, mock_best_info, chess.WHITE, state_manager, True, None)
        print(f"Forced move should be skipped: {not result3}")
    else:
        print(f"Test position has {len(legal_moves)} legal moves, not forced")
    
    print()

def test_batch_analysis():
    """Test batch analysis functionality"""
    print("=== BATCH ANALYSIS TEST ===")
    
    engine_pool = get_engine_pool()
    engine = engine_pool.get_engine()
    
    try:
        # Create test positions
        positions = [
            (chess.Board(), chess.engine.Limit(time=0.01)),
            (chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"), chess.engine.Limit(time=0.01))
        ]
        
        print(f"Testing batch analysis with {len(positions)} positions")
        print(f"Batch analysis enabled: {ENABLE_BATCH_ENGINE_ANALYSIS}")
        print(f"Batch size: {BATCH_ANALYSIS_SIZE}")
        
        start_time = time.time()
        results = analyze_positions_batch(engine, positions, True)
        end_time = time.time()
        
        print(f"Batch analysis completed in {end_time - start_time:.3f}s")
        print(f"Results: {len(results)} analyses returned")
        
        # Compare with sequential analysis
        start_time = time.time()
        sequential_results = []
        for board, limit in positions:
            sequential_results.append(engine.analyse(board, limit))
        end_time = time.time()
        
        print(f"Sequential analysis completed in {end_time - start_time:.3f}s")
        
    finally:
        engine_pool.return_engine(engine)
    
    print()

def test_lazy_evaluation():
    """Test lazy evaluation in categorize_blunder_optimized"""
    print("=== LAZY EVALUATION TEST ===")
    
    # Create mock engine info with minimal evaluation change
    minimal_change_before = {
        'score': chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE)
    }
    minimal_change_after = {
        'score': chess.engine.PovScore(chess.engine.Cp(10), chess.WHITE)  # Only 10cp drop
    }
    
    # Create mock engine info with significant change
    significant_change_before = {
        'score': chess.engine.PovScore(chess.engine.Cp(100), chess.WHITE)
    }
    significant_change_after = {
        'score': chess.engine.PovScore(chess.engine.Cp(-100), chess.WHITE)  # 200cp drop
    }
    
    board = chess.Board()
    move = chess.Move.from_uci('e2e4')
    board_after = board.copy()
    board_after.push(move)
    state_manager = BlunderStateManager()
    
    # Test minimal change (should be skipped)
    result1 = categorize_blunder_optimized(
        board, board_after, move, minimal_change_before, minimal_change_after,
        minimal_change_before, state_manager, True, 1
    )
    print(f"Minimal change (10cp) should be skipped: {result1 is None}")
    
    # Test significant change (should be analyzed)
    result2 = categorize_blunder_optimized(
        board, board_after, move, significant_change_before, significant_change_after,
        significant_change_before, state_manager, True, 1
    )
    print(f"Significant change (200cp) should be analyzed: {result2 is not None}")
    
    print()

def benchmark_game_analysis():
    """Benchmark game analysis with optimizations enabled vs disabled"""
    print("=== GAME ANALYSIS BENCHMARK ===")
    
    # Load a test game
    test_pgn_path = "games/testgames.pgn"
    if not os.path.exists(test_pgn_path):
        print(f"Test PGN file not found: {test_pgn_path}")
        return
    
    with open(test_pgn_path, 'r') as f:
        game = chess.pgn.read_game(f)
    
    if not game:
        print("Could not load test game")
        return
    
    engine_pool = get_engine_pool()
    engine = engine_pool.get_engine()
    
    try:
        # Find a username from the game headers
        username = None
        if game.headers.get("White"):
            username = game.headers["White"]
        elif game.headers.get("Black"):
            username = game.headers["Black"]
        
        if not username:
            print("Could not find username in game headers")
            return
        
        print(f"Testing with game: {game.headers.get('White', '?')} vs {game.headers.get('Black', '?')}")
        print(f"Analyzing as: {username}")
        
        # Test with optimizations enabled
        print("\n--- WITH OPTIMIZATIONS ---")
        start_time = time.time()
        blunders_optimized = analyze_game_optimized(
            game, engine, username, 15.0, 0.08, True, STOCKFISH_PATH, 1
        )
        end_time = time.time()
        optimized_time = end_time - start_time
        
        print(f"Optimized analysis: {optimized_time:.2f}s, {len(blunders_optimized)} blunders")
        
        # Show some debug output about what was skipped
        print(f"Found {len(blunders_optimized)} blunders with optimizations")
        
    except Exception as e:
        print(f"Error during benchmark: {e}")
    finally:
        engine_pool.return_engine(engine)
    
    print()

def test_production_vs_debug_mode():
    """Test performance difference between debug and production modes"""
    print("=== PRODUCTION VS DEBUG MODE TEST ===")
    
    # Load a test game
    test_pgn_path = "games/testgames.pgn"
    if not os.path.exists(test_pgn_path):
        print(f"Test PGN file not found: {test_pgn_path}")
        return
    
    with open(test_pgn_path, 'r') as f:
        game = chess.pgn.read_game(f)
    
    if not game:
        print("Could not load test game")
        return
    
    engine_pool = get_engine_pool()
    engine = engine_pool.get_engine()
    
    try:
        username = game.headers.get("White", game.headers.get("Black", "unknown"))
        
        # Test different engine think times
        think_times = [0.05, 0.08, 0.12, 0.15]  # fast, balanced, deep, very deep
        
        for think_time in think_times:
            print(f"\n--- Think time: {think_time}s ---")
            
            # Test with debug mode ON (like our debug test)
            start_time = time.time()
            blunders_debug = analyze_game_optimized(
                game, engine, username, 15.0, think_time, True, STOCKFISH_PATH, 1
            )
            debug_time = time.time() - start_time
            
            # Test with debug mode OFF (like production)
            start_time = time.time()
            blunders_prod = analyze_game_optimized(
                game, engine, username, 15.0, think_time, False, STOCKFISH_PATH, 1
            )
            prod_time = time.time() - start_time
            
            print(f"  Debug mode ON:  {debug_time:.2f}s, {len(blunders_debug)} blunders")
            print(f"  Debug mode OFF: {prod_time:.2f}s, {len(blunders_prod)} blunders")
            print(f"  Difference: {((prod_time - debug_time) / debug_time * 100):+.1f}%")
        
    finally:
        engine_pool.return_engine(engine)
    
    print()

def run_performance_test():
    """Run a comprehensive performance test"""
    print("=== COMPREHENSIVE PERFORMANCE TEST ===")
    
    # Test multiple games
    test_pgn_path = "games/testgames.pgn"
    if not os.path.exists(test_pgn_path):
        print(f"Test PGN file not found: {test_pgn_path}")
        return
    
    games = []
    with open(test_pgn_path, 'r') as f:
        while len(games) < 5:  # Test with 5 games
            game = chess.pgn.read_game(f)
            if not game:
                break
            games.append(game)
    
    if not games:
        print("No games loaded for testing")
        return
    
    print(f"Testing with {len(games)} games")
    
    engine_pool = get_engine_pool()
    engine = engine_pool.get_engine()
    
    try:
        total_start = time.time()
        total_blunders = 0
        
        for i, game in enumerate(games, 1):
            # Find username
            username = game.headers.get("White", game.headers.get("Black", "unknown"))
            
            print(f"Analyzing game {i}/{len(games)}: {username}")
            
            game_start = time.time()
            blunders = analyze_game_optimized(
                game, engine, username, 15.0, 0.08, False, STOCKFISH_PATH, 1
            )
            game_end = time.time()
            
            total_blunders += len(blunders)
            print(f"  Game {i}: {game_end - game_start:.2f}s, {len(blunders)} blunders")
        
        total_end = time.time()
        total_time = total_end - total_start
        
        print(f"\nTOTAL RESULTS:")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Average per game: {total_time / len(games):.2f}s")
        print(f"  Total blunders: {total_blunders}")
        print(f"  Games per second: {len(games) / total_time:.3f}")
        
    finally:
        engine_pool.return_engine(engine)

def main():
    """Run all debugging tests"""
    print("MCB Phase 1 Optimization Debug Tool")
    print("=" * 50)
    
    test_configuration()
    test_position_filtering()
    test_quick_heuristics()
    test_batch_analysis()
    test_lazy_evaluation()
    benchmark_game_analysis()
    test_production_vs_debug_mode()  # NEW TEST
    run_performance_test()
    
    print("=" * 50)
    print("Debug testing complete!")

if __name__ == "__main__":
    main() 