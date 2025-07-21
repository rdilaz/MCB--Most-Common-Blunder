"""
MCB Progress Tracking Module
Handles real-time progress updates and session management for chess analysis.
"""
import time
import json
import queue
import logging
import threading
from typing import Dict, Any, Optional

from config import PROGRESS_PHASE_WEIGHTS, PROGRESS_QUEUE_MAX_SIZE, PROGRESS_HEARTBEAT_TIMEOUT

# Set up logging
logger = logging.getLogger(__name__)

# Global progress tracking state
progress_queues = {}
progress_lock = threading.Lock()
progress_trackers = {}

class ProgressTracker:
    """
    Helper class to track and report progress during analysis with time-weighted calculations.
    """
    
    def __init__(self, session_id: str, games_to_analyze: int = 1, parallel: bool = False):
        """
        Initialize progress tracker for a session.
        
        Args:
            session_id (str): Unique session identifier
            games_to_analyze (int): Number of games to analyze
            parallel (bool): Whether using parallel processing
        """
        self.session_id = session_id
        self.start_time = time.time()
        self.completed = False
        self.error_occurred = False
        self.results = None
        self.parallel_processing = parallel
        
        # Create progress queue for this session immediately
        with progress_lock:
            progress_queues[session_id] = queue.Queue(maxsize=PROGRESS_QUEUE_MAX_SIZE)
        
        # Adjust time estimates for parallel processing
        time_multiplier = 0.3 if parallel and games_to_analyze > 20 else 1.0
        
        # Time-weighted progress phases with parallel optimization
        self.phases = {
            "starting": {"weight": PROGRESS_PHASE_WEIGHTS["starting"], "completed": False},
            "fetching_games": {"weight": PROGRESS_PHASE_WEIGHTS["fetching_games"], "completed": False},
            "engine_init": {"weight": PROGRESS_PHASE_WEIGHTS["engine_init"] * (2 if parallel else 1), "completed": False},
            "reading_pgn": {"weight": PROGRESS_PHASE_WEIGHTS["reading_pgn"], "completed": False},
            "analyzing_games": {"weight": PROGRESS_PHASE_WEIGHTS["analyzing_games"] * games_to_analyze * time_multiplier, "completed": False},
            "aggregating": {"weight": PROGRESS_PHASE_WEIGHTS["aggregating"], "completed": False},
        }
        
        # Calculate total estimated time
        self.total_estimated_time = sum(phase["weight"] for phase in self.phases.values())
        self.current_progress = 0.0

    def start_phase(self, phase_name: str, message: str):
        """
        Start a new phase of analysis.
        
        Args:
            phase_name (str): Name of the phase
            message (str): Status message for this phase
        """
        if phase_name in self.phases:
            self.phases[phase_name]["completed"] = False
        
        self.update_progress_percentage()
        self._send_update({
            "step": phase_name,
            "message": message,
            "percentage": self.current_progress,
            "time_elapsed": time.time() - self.start_time
        })

    def update(self, phase_name: str, message: str, mark_complete: bool = True):
        """
        Update progress for current phase.
        
        Args:
            phase_name (str): Name of the phase
            message (str): Progress message
            mark_complete (bool): Whether to mark phase as complete
        """
        if mark_complete and phase_name in self.phases:
            self.phases[phase_name]["completed"] = True
        
        self.update_progress_percentage()
        self._send_update({
            "step": phase_name,
            "message": message,
            "percentage": self.current_progress,
            "time_elapsed": time.time() - self.start_time
        })

    def update_progress(self, percent: float, message: str):
        """
        Update progress with manual percentage.
        
        Args:
            percent (float): Progress percentage (0-100)
            message (str): Progress message
        """
        self.current_progress = percent
        self._send_update({
            "step": "manual_progress",
            "message": message,
            "percentage": percent,
            "time_elapsed": time.time() - self.start_time
        })

    def complete(self, results: Optional[Dict[str, Any]] = None):
        """
        Mark analysis as completed.
        
        Args:
            results (Optional[Dict]): Analysis results to send
        """
        try:
            self.completed = True
            self.results = results
            self.current_progress = 100.0
            
            completion_update = {
                "step": "complete",
                "status": "completed",
                "message": "Analysis completed successfully!",
                "percentage": 100.0,
                "time_elapsed": time.time() - self.start_time,
                "results": results
            }
            
            self._send_update(completion_update)
            logger.info(f"Progress tracker completed for session {self.session_id}")
            
        except Exception as e:
            logger.error(f"Error in complete() for session {self.session_id}: {str(e)}")
            self.set_error(f"Completion failed: {str(e)}")

    def set_error(self, error_message: str):
        """
        Mark analysis as failed with error.
        
        Args:
            error_message (str): Error description
        """
        self.error_occurred = True
        self._send_update({
            "step": "error",
            "status": "error",
            "message": f"❌ {error_message}",
            "error": error_message,
            "time_elapsed": time.time() - self.start_time
        })

    def update_progress_percentage(self):
        """Calculate and update current progress percentage based on completed phases."""
        completed_weight = sum(
            phase["weight"] for phase in self.phases.values() if phase["completed"]
        )
        self.current_progress = min(95.0, (completed_weight / self.total_estimated_time) * 100)

    def _send_update(self, update_data: Dict[str, Any]):
        """
        Send progress update to the queue.
        
        Args:
            update_data (Dict): Update data to send
        """
        try:
            with progress_lock:
                if self.session_id in progress_queues:
                    update_data["timestamp"] = time.time()
                    progress_queues[self.session_id].put_nowait(update_data)
                    logger.debug(f"Progress update sent for session {self.session_id}: {update_data.get('message', 'no message')}")
        except queue.Full:
            logger.warning(f"Progress queue full for session {self.session_id}")
        except Exception as e:
            logger.error(f"Error sending progress update for session {self.session_id}: {str(e)}")

# ========================================
# PROGRESS MANAGEMENT FUNCTIONS
# ========================================

def send_progress_update(session_id: str, step: str, message: str, progress_percent: Optional[float] = None, time_elapsed: Optional[float] = None):
    """
    Send a progress update to the specified session.
    
    Args:
        session_id (str): Session identifier
        step (str): Current step name
        message (str): Progress message
        progress_percent (Optional[float]): Progress percentage
        time_elapsed (Optional[float]): Elapsed time in seconds
    """
    with progress_lock:
        if session_id in progress_queues:
            update = {
                "step": step,
                "message": message,
                "progress": progress_percent,
                "time_elapsed": time_elapsed,
                "timestamp": time.time()
            }
            try:
                progress_queues[session_id].put_nowait(update)
            except queue.Full:
                logger.warning(f"Progress queue full for session {session_id}")

def cleanup_progress_session(session_id: str):
    """
    Clean up progress tracking for a session.
    
    Args:
        session_id (str): Session to clean up
    """
    with progress_lock:
        if session_id in progress_queues:
            del progress_queues[session_id]
            logger.info(f"Cleaned up progress queue for session {session_id}")

def get_progress_generator(session_id: str):
    """
    Generator function for Server-Sent Events progress streaming.
    
    Args:
        session_id (str): Session identifier
        
    Yields:
        str: Formatted SSE data
    """
    logger.info(f"Starting progress stream for session {session_id}")
    
    # Create queue for this session if it doesn't exist
    with progress_lock:
        if session_id not in progress_queues:
            progress_queues[session_id] = queue.Queue(maxsize=PROGRESS_QUEUE_MAX_SIZE)
            logger.info(f"Created new progress queue for session {session_id}")
    
    try:
        while True:
            try:
                # Wait for progress update with timeout
                update = progress_queues[session_id].get(timeout=PROGRESS_HEARTBEAT_TIMEOUT)
                logger.debug(f"Sending progress update for {session_id}: {update.get('step', 'no-step')} - {update.get('message', 'no-message')}")
                
                # Send the update as SSE
                yield f"data: {json.dumps(update)}\n\n"
                
                # Check if this is completion
                if update.get("step") == "complete" or update.get("step") == "error":
                    logger.info(f"Stream ending for session {session_id} with step: {update.get('step')}")
                    break
                    
            except queue.Empty:
                # Send heartbeat
                logger.debug(f"Sending heartbeat for session {session_id}")
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"
            except Exception as e:
                logger.error(f"Error in progress stream for session {session_id}: {str(e)}")
                break
    finally:
        logger.info(f"Cleaning up progress session {session_id}")
        cleanup_progress_session(session_id)

# ========================================
# TRACKER MANAGEMENT
# ========================================

def create_progress_tracker(session_id: str, games_to_analyze: int = 1, parallel: bool = False) -> ProgressTracker:
    """
    Create and register a new progress tracker.
    
    Args:
        session_id (str): Session identifier
        games_to_analyze (int): Number of games to analyze
        parallel (bool): Whether using parallel processing
        
    Returns:
        ProgressTracker: Configured progress tracker
    """
    tracker = ProgressTracker(session_id, games_to_analyze, parallel)
    progress_trackers[session_id] = tracker
    return tracker

def get_progress_tracker(session_id: str) -> Optional[ProgressTracker]:
    """
    Get existing progress tracker for session.
    
    Args:
        session_id (str): Session identifier
        
    Returns:
        Optional[ProgressTracker]: Tracker if exists, None otherwise
    """
    return progress_trackers.get(session_id)

def cleanup_tracker(session_id: str):
    """
    Clean up progress tracker for session.
    
    Args:
        session_id (str): Session identifier
    """
    if session_id in progress_trackers:
        del progress_trackers[session_id]
        logger.info(f"Cleaned up progress tracker for session {session_id}")

# ========================================
# STATUS CHECKING
# ========================================

def get_session_status(session_id: str) -> Dict[str, Any]:
    """
    Get current status of a session.
    
    Args:
        session_id (str): Session identifier
        
    Returns:
        Dict: Session status information
    """
    if session_id in progress_trackers:
        tracker = progress_trackers[session_id]
        return {
            'status': 'running',
            'session_id': session_id,
            'progress': tracker.current_progress,
            'completed': tracker.completed,
            'error_occurred': tracker.error_occurred,
            'time_elapsed': time.time() - tracker.start_time
        }
    else:
        return {
            'status': 'unknown',
            'session_id': session_id,
            'message': 'Session not found'
        } 