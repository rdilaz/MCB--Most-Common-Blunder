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
                        engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
                        self.total_engines += 1
                        logger.info(f"Created Stockfish engine {self.total_engines}/{self.pool_size}")
                        return engine
                    except Exception as e:
                        logger.error(f"Failed to create Stockfish engine: {e}")
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

# For backwards compatibility and global pool management
def create_stockfish_pool(stockfish_path: str, pool_size: int = 3) -> StockfishPool:
    """Create a new Stockfish pool"""
    return StockfishPool(stockfish_path, pool_size)