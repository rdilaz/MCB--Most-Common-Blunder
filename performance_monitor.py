"""
MCB Performance Monitoring Module
Tracks performance metrics for analysis operations to measure optimization improvements.
"""
import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class PerformanceMetrics:
    """Track performance metrics for analysis operations"""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    games_analyzed: int = 0
    total_blunders: int = 0
    engine_calls: int = 0
    engine_calls_saved: int = 0
    parallel_processing: bool = False
    processing_mode: str = "sequential"
    memory_usage_mb: Optional[float] = None
    
    @property
    def total_time(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time
    
    @property
    def games_per_second(self) -> float:
        if self.total_time == 0:
            return 0
        return self.games_analyzed / self.total_time
    
    @property
    def engine_efficiency(self) -> float:
        total_calls = self.engine_calls + self.engine_calls_saved
        if total_calls == 0:
            return 0
        return (self.engine_calls_saved / total_calls) * 100

class PerformanceMonitor:
    """Monitor and log performance metrics"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.current_metrics: Optional[PerformanceMetrics] = None
    
    def start_analysis(self, estimated_games: int, processing_mode: str = "sequential") -> PerformanceMetrics:
        """Start performance monitoring"""
        self.current_metrics = PerformanceMetrics(
            processing_mode=processing_mode,
            parallel_processing=processing_mode == "parallel"
        )
        self.logger.info(f"Starting {processing_mode} analysis for ~{estimated_games} games")
        return self.current_metrics
    
    def update_metrics(self, games_analyzed: int = 0, blunders_found: int = 0, 
                      engine_calls: int = 0, engine_calls_saved: int = 0):
        """Update performance metrics"""
        if self.current_metrics:
            self.current_metrics.games_analyzed += games_analyzed
            self.current_metrics.total_blunders += blunders_found
            self.current_metrics.engine_calls += engine_calls
            self.current_metrics.engine_calls_saved += engine_calls_saved
    
    def finish_analysis(self) -> Dict[str, any]:
        """Finish monitoring and return performance report"""
        if not self.current_metrics:
            return {}
        
        self.current_metrics.end_time = time.time()
        
        # Get memory usage
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            self.current_metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
        except ImportError:
            # psutil not available, skip memory monitoring
            pass
        except Exception as e:
            self.logger.warning(f"Could not get memory usage: {e}")
        
        report = {
            "total_time": self.current_metrics.total_time,
            "games_analyzed": self.current_metrics.games_analyzed,
            "games_per_second": self.current_metrics.games_per_second,
            "total_blunders": self.current_metrics.total_blunders,
            "engine_calls": self.current_metrics.engine_calls,
            "engine_efficiency": self.current_metrics.engine_efficiency,
            "parallel_processing": self.current_metrics.parallel_processing,
            "processing_mode": self.current_metrics.processing_mode,
            "memory_usage_mb": self.current_metrics.memory_usage_mb
        }
        
        self.logger.info(f"Analysis complete: {report}")
        return report
    
    def get_current_metrics(self) -> Dict[str, any]:
        """Get current metrics without finishing the analysis"""
        if not self.current_metrics:
            return {}
        
        return {
            "elapsed_time": self.current_metrics.total_time,
            "games_analyzed": self.current_metrics.games_analyzed,
            "games_per_second": self.current_metrics.games_per_second,
            "total_blunders": self.current_metrics.total_blunders,
            "engine_calls": self.current_metrics.engine_calls,
            "engine_efficiency": self.current_metrics.engine_efficiency,
            "processing_mode": self.current_metrics.processing_mode,
            "parallel_processing": self.current_metrics.parallel_processing
        }

# Global performance monitor instance
performance_monitor = PerformanceMonitor()