#!/usr/bin/env python3
"""
MCB Optimization Integration Verification Script
Verifies that all optimization components are properly integrated
"""
import os
import sys
import traceback

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if os.path.exists(filepath):
        print(f"[OK] {description}: {filepath}")
        return True
    else:
        print(f"[ERROR] {description}: {filepath} - MISSING!")
        return False

def check_import(module_name, import_items, description):
    """Check if imports work correctly"""
    try:
        if isinstance(import_items, str):
            exec(f"from {module_name} import {import_items}")
        else:
            for item in import_items:
                exec(f"from {module_name} import {item}")
        print(f"[OK] {description}")
        return True
    except Exception as e:
        print(f"[ERROR] {description}: {e}")
        return False

def check_config_constants():
    """Check if new config constants are available"""
    try:
        from config import (
            POSITION_CACHE_SIZE, SEE_CACHE_SIZE, ENABLE_PARALLEL_ANALYSIS,
            DYNAMIC_THINK_TIME, MIN_THINK_TIME, MAX_THINK_TIME,
            ENABLE_GAME_BATCHING, BATCH_SIZE_THRESHOLD, MOVES_PER_BATCH
        )
        print("[OK] New config constants available")
        print(f"  - Position cache size: {POSITION_CACHE_SIZE}")
        print(f"  - SEE cache size: {SEE_CACHE_SIZE}")
        print(f"  - Parallel analysis: {ENABLE_PARALLEL_ANALYSIS}")
        print(f"  - Game batching: {ENABLE_GAME_BATCHING}")
        return True
    except Exception as e:
        print(f"[ERROR] Config constants missing: {e}")
        return False

def check_analyze_games_optimizations():
    """Check if optimized analyze_games functions are available"""
    try:
        from analyze_games import (
            analyze_game_optimized, BlunderStateManager, 
            analyze_position_cached, see_cached
        )
        print("[OK] Optimized analyze_games functions available")
        
        # Test BlunderStateManager
        state_manager = BlunderStateManager()
        print(f"  - BlunderStateManager initialized: {type(state_manager)}")
        
        return True
    except Exception as e:
        print(f"[ERROR] Analyze games optimizations missing: {e}")
        return False

def check_engine_pool():
    """Check if engine pool is working"""
    try:
        from engines.stockfish_pool import get_engine_pool, StockfishPool
        print("[OK] Engine pool imports successful")
        
        # Try to get the global pool (without initializing engines)
        pool = get_engine_pool()
        print(f"  - Global engine pool created: {type(pool)}")
        return True
    except Exception as e:
        print(f"[ERROR] Engine pool error: {e}")
        return False

def check_progress_tracking():
    """Check if progress tracking supports parallel processing"""
    try:
        from progress_tracking import create_progress_tracker
        
        # Test with parallel parameter
        tracker = create_progress_tracker("test-session", 10, parallel=True)
        print("[OK] Progress tracking supports parallel processing")
        print(f"  - Parallel processing flag: {tracker.parallel_processing}")
        return True
    except Exception as e:
        print(f"[ERROR] Progress tracking error: {e}")
        return False

def check_analysis_service_integration():
    """Check if analysis service integrates with optimized functions"""
    try:
        from analysis_service import create_analysis_service
        service = create_analysis_service()
        print("[OK] Analysis service integration successful")
        
        # Check if it has the optimized methods
        if hasattr(service, 'analyze_game_optimized'):
            print("  - analyze_game_optimized method available")
        else:
            print("  - WARNING: analyze_game_optimized method missing")
            
        return True
    except Exception as e:
        print(f"[ERROR] Analysis service integration error: {e}")
        return False

def main():
    """Run all verification checks"""
    print("MCB Optimization Integration Verification")
    print("=" * 50)
    
    all_checks_passed = True
    
    # File existence checks
    print("\n1. File Existence Checks:")
    files_to_check = [
        ("analyze_games.py", "Optimized analyze_games"),
        ("engines/stockfish_pool.py", "Engine pool"),
        ("config.py", "Configuration"),
        ("analysis_service.py", "Analysis service"),
        ("progress_tracking.py", "Progress tracking")
    ]
    
    for filepath, description in files_to_check:
        if not check_file_exists(filepath, description):
            all_checks_passed = False
    
    # Import checks
    print("\n2. Import Checks:")
    import_checks = [
        ("config", ["POSITION_CACHE_SIZE", "ENGINE_POOL_SIZE"], "Config imports"),
        ("analyze_games", "analyze_game_optimized", "Optimized analyze_games"),
        ("engines.stockfish_pool", "get_engine_pool", "Engine pool"),
        ("progress_tracking", "create_progress_tracker", "Progress tracking"),
        ("analysis_service", "create_analysis_service", "Analysis service")
    ]
    
    for module, items, description in import_checks:
        if not check_import(module, items, description):
            all_checks_passed = False
    
    # Functional checks
    print("\n3. Functional Checks:")
    functional_checks = [
        check_config_constants,
        check_analyze_games_optimizations,
        check_engine_pool,
        check_progress_tracking,
        check_analysis_service_integration
    ]
    
    for check_func in functional_checks:
        try:
            if not check_func():
                all_checks_passed = False
        except Exception as e:
            print(f"[ERROR] {check_func.__name__} failed: {e}")
            all_checks_passed = False
    
    # Summary
    print("\n" + "=" * 50)
    if all_checks_passed:
        print("SUCCESS: ALL VERIFICATION CHECKS PASSED!")
        print("The optimization integration is ready for testing.")
    else:
        print("FAILURE: SOME CHECKS FAILED!")
        print("Please fix the issues above before proceeding.")
    
    return 0 if all_checks_passed else 1

if __name__ == "__main__":
    sys.exit(main())