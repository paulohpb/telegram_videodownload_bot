"""
Thread-safe progress tracking with Telegram-friendly progress bars.
""" 
import threading
import time
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class ProgressStage(Enum):
    IDLE = "idle" 
    DOWNLOADING = "downloading" 
    PROCESSING = "processing" 
    COMPRESSING = "compressing" 
    UPLOADING = "uploading" 
    COMPLETED = "completed" 
    FAILED = "failed" 

@dataclass
class ProgressState:
    """Current progress state snapshot.""" 
    stage: ProgressStage = ProgressStage.IDLE
    progress: float = 0.0   # 0-100 
    speed: str = "" 
    eta: str = "" 
    filename: str = "" 
    error: Optional[str] = None 
    completed: bool = False 
    last_update: float = field(default_factory=time.time)

class ProgressTracker:
    """
    Thread-safe progress tracker for cross-thread progress updates.
    Designed to be updated from worker threads (yt-dlp, ffmpeg) and
    read from the async main loop safely.
    """ 
    def __init__(self, throttle_seconds: float = 2.5):
        self._state = ProgressState()
        self._lock = threading.Lock()
        self._throttle_seconds = throttle_seconds
        self._last_message_update = 0.0 
    
    def update(
        self,
        stage: Optional[ProgressStage] = None,
        progress: Optional[float] = None,
        speed: Optional[str] = None,
        eta: Optional[str] = None,
        filename: Optional[str] = None,
        error: Optional[str] = None,
        completed: Optional[bool] = None 
    ) -> None:
        """Thread-safe progress update.""" 
        with self._lock:
            if stage is not None: self._state.stage = stage
            if progress is not None: self._state.progress = min(100.0, max(0.0, progress))
            if speed is not None: self._state.speed = speed
            if eta is not None: self._state.eta = eta
            if filename is not None: self._state.filename = filename
            if error is not None:
                self._state.error = error
                self._state.stage = ProgressStage.FAILED
            if completed is not None:
                self._state.completed = completed
                if completed: self._state.stage = ProgressStage.COMPLETED
            self._state.last_update = time.time()
    
    def get_state(self) -> ProgressState:
        """Get current state as a thread-safe copy.""" 
        with self._lock:
            return ProgressState(
                stage=self._state.stage,
                progress=self._state.progress,
                speed=self._state.speed,
                eta=self._state.eta,
                filename=self._state.filename,
                error=self._state.error,
                completed=self._state.completed,
                last_update=self._state.last_update
            )
    
    def should_update_message(self) -> bool:
        """Check if enough time has passed to send another Telegram update.""" 
        current_time = time.time()
        with self._lock:
            if current_time - self._last_message_update >= self._throttle_seconds:
                self._last_message_update = current_time
                return True 
            return False 
    
    def force_update_allowed(self) -> None:
        """Force allow the next message update.""" 
        with self._lock:
            self._last_message_update = 0.0 

    def set_error(self, error_message: str) -> None:
        self.update(error=error_message, completed=True)
    
    def set_completed(self) -> None:
        self.update(progress=100.0, completed=True)

def generate_progress_bar(progress: float, length: int = 10) -> str:
    """Generate a text-based progress bar [████░░].""" 
    progress = min(100.0, max(0.0, progress))
    filled = int(progress / 100 * length)
    empty = length - filled
    bar = "█" * filled + "░" * empty
    return f"[{bar}] {progress:.1f}%"

def format_progress_message(state: ProgressState, title: str) -> str:
    """Format the Telegram message based on current state.""" 
    display_title = title[:40] + "..." if len(title) > 40 else title
    bar = generate_progress_bar(state.progress)
    
    if state.stage == ProgressStage.FAILED:
        return f"❌ Failed\n📹 {display_title}\n\n{state.error or 'Unknown error'}" 
    
    if state.stage == ProgressStage.DOWNLOADING:
        stats = []
        if state.speed: stats.append(f"⚡ {state.speed}")
        if state.eta: stats.append(f"⏱ ETA: {state.eta}")
        stats_line = " | ".join(stats)
        return f"⏬ Downloading\n📹 {display_title}\n\n{bar}\n{stats_line}"
    
    elif state.stage == ProgressStage.COMPRESSING:
        return f"🔧 Compressing\n📹 {display_title}\n\n{bar}\n⏱ ETA: {state.eta}"
    
    elif state.stage == ProgressStage.UPLOADING:
        return f"⏫ Uploading\n📹 {display_title}\n\n{bar}\n⚡ {state.speed}"
    
    elif state.stage == ProgressStage.COMPLETED:
        return f"✅ Completed\n📹 {display_title}" 
    
    return f"⏳ Processing\n📹 {display_title}"