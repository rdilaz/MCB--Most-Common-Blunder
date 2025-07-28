import chess.engine
import threading
from queue import Queue, Empty
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class StockfishPool:
    """A pool of Stockfish engines with on-demand creation"""
    
    def __init__(self, stockfish_path: str, pool_size: int = 5):
        self.stockfish_path = stockfish_path
        self.pool_size = pool_size
        self.available_engines = Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        self.total_engines = 0

    def get_engine(self, timeout: float = 10.0) -> Optional[chess.engine.SimpleEngine]:
        """
        Get an available engine from the pool.
        Creates engines on demand up to pool_size.
        """
        try:
            # Try to get existing engine first (non-blocking)
            return self.available_engines.get(timeout=0.01)
        except Empty:
            # No engines available, try to create one
            with self.lock:
                if self.total_engines < self.pool_size:
                    # Create a new engine
                    try:
                        logger.info(f"Attempting to create Stockfish engine with path: {self.stockfish_path}")
                        engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
                        self.total_engines += 1
                        logger.info(f"✅ Created Stockfish engine {self.total_engines}/{self.pool_size}")
                        return engine
                    except FileNotFoundError as e:
                        logger.error(f"❌ Stockfish binary not found at: {self.stockfish_path}")
                        logger.error(f"❌ FileNotFoundError: {e}")
                        return None
                    except Exception as e:
                        logger.error(f"❌ Failed to create Stockfish engine: {e}")
                        logger.error(f"❌ Engine path was: {self.stockfish_path}")
                        return None
                else:
                    # Pool is full, wait for an engine to become available
                    try:
                        return self.available_engines.get(timeout=timeout)
                    except Empty:
                        logger.warning("No engines available and pool is full")
                        return None

    def return_engine(self, engine: chess.engine.SimpleEngine):
        """Return an engine to the pool"""
        if engine:
            try:
                self.available_engines.put(engine, block=False)
            except:
                # Pool is full, close the engine instead
                try:
                    engine.quit()
                except:
                    pass

    def shutdown(self):
        """Shutdown all engines in the pool"""
        while not self.available_engines.empty():
            try:
                engine = self.available_engines.get_nowait()
                engine.quit()
            except:
                pass

# Global engine pool instance
_engine_pool = None

def get_engine_pool() -> StockfishPool:
    """Get the global engine pool instance"""
    global _engine_pool
    if _engine_pool is None:
        from config import STOCKFISH_PATH, ENGINE_POOL_SIZE
        _engine_pool = StockfishPool(STOCKFISH_PATH, ENGINE_POOL_SIZE)
    return _engine_pool

# For backwards compatibility and global pool management
def create_stockfish_pool(stockfish_path: str, pool_size: int = 3) -> StockfishPool:
    """Create a new Stockfish pool"""
    return StockfishPool(stockfish_path, pool_size)