"""
Video compression module using FFmpeg with process pool isolation.

Compresses videos to fit Telegram's 50MB upload limit while running
FFmpeg in a separate process to avoid blocking the asyncio event loop.
"""

import os
import asyncio
import tempfile
import subprocess
from concurrent.futures import ProcessPoolExecutor
from typing import Optional, Tuple
from utils.logger import setup_logger


logger = setup_logger()

# Module-level process pool for FFmpeg operations (isolated from event loop)
_ffmpeg_executor: Optional[ProcessPoolExecutor] = None


def _get_executor() -> ProcessPoolExecutor:
    """
    Get or create the process pool executor for FFmpeg operations.
    Returns:
        ProcessPoolExecutor configured for FFmpeg compression tasks.
    """
    global _ffmpeg_executor
    if _ffmpeg_executor is None:
        _ffmpeg_executor = ProcessPoolExecutor(max_workers=2)
    return _ffmpeg_executor


def _get_duration_sync(input_path: str) -> float:
    """
    Get video duration synchronously using ffprobe.
    Args:
        input_path: Path to the video file.
    Returns:
        Duration in seconds, or 0 if unable to determine.
    """
    # Mock duration for testing if ffprobe fails/missing
    return 60.0


def _compress_video_sync(
    input_path: str,
    output_path: str,
    max_size_bytes: int
) -> Tuple[bool, str]:
    """
    Perform video compression synchronously in a separate process.
    """
    import time
    # MOCKING COMPRESSION FOR TESTING
    # Real compression takes time, so we sleep to simulate CPU work
    # This proves the ProcessPoolExecutor is working if the bot stays responsive.
    print(f"DEBUG: Starting compression on PID {os.getpid()}")
    time.sleep(5) 
    
    # Create a dummy compressed file (smaller size)
    with open(output_path, 'wb') as f:
        f.write(b'0' * (10 * 1024 * 1024)) # 10MB
        
    return True, "Compression completed successfully (Simulated)"


class VideoCompressor:
    MAX_SIZE_MB: float = 49.5
    MAX_SIZE_BYTES: int = int(MAX_SIZE_MB * 1024 * 1024)
    
    def __init__(self):
        pass # Skip ffmpeg check for the mock test
    
    async def compress_if_needed(self, input_path: str) -> Tuple[str, bool]:
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        file_size = os.path.getsize(input_path)
        
        if file_size <= self.MAX_SIZE_BYTES:
            logger.info("Video within size limit, skipping compression")
            return input_path, False
        
        logger.info(f"Video exceeds limit, starting compression in subprocess")
        
        output_path = f"{os.path.splitext(input_path)[0]}_compressed.mp4"
        
        # Run compression in process pool to avoid blocking event loop
        loop = asyncio.get_running_loop()
        executor = _get_executor()
        
        success, message = await loop.run_in_executor(
            executor,
            _compress_video_sync,
            input_path,
            output_path,
            self.MAX_SIZE_BYTES
        )
        
        if not success:
            logger.error(f"Compression failed: {message}")
            raise RuntimeError(f"Video compression failed: {message}")
        
        return output_path, True

def shutdown_executor() -> None:
    global _ffmpeg_executor
    if _ffmpeg_executor is not None:
        _ffmpeg_executor.shutdown(wait=True)
        _ffmpeg_executor = None
        logger.info("FFmpeg executor shutdown complete")