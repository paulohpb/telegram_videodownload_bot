import os
import asyncio
import tempfile
import re
import subprocess
from typing import Optional, Callable, Awaitable

from utils.logger import setup_logger

logger = setup_logger()

class CompressionError(Exception):
    """Custom exception for video compression failures."""
    pass

class VideoCompressor:
    """
    A self-contained, asynchronous video compressor using FFmpeg.

    This class manages the entire compression process, including running FFmpeg
    in two passes for better quality and bitrate control. It uses asyncio
    subprocesses for non-blocking operations.
    """
    # Target size is slightly less than 50MB to leave a margin for safety.
    MAX_SIZE_BYTES = int(49.5 * 1024 * 1024)

    async def _get_video_duration(self, input_path: str) -> float:
        """Get video duration in seconds using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", input_path
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise CompressionError(f"ffprobe failed: {stderr.decode()}")
        
        try:
            return float(stdout.decode().strip())
        except (ValueError, IndexError):
            raise CompressionError("Could not parse video duration from ffprobe.")

    async def _run_ffmpeg_pass(
        self,
        cmd: list[str],
        duration: float,
        progress_callback: Optional[Callable[[float], Awaitable[None]]] = None
    ) -> None:
        """Run an FFmpeg command pass and handle progress reporting."""
        process = await asyncio.create_subprocess_exec(
            *cmd, stderr=subprocess.PIPE
        )
        
        assert process.stderr is not None, "stderr cannot be None when subprocess.PIPE is used"

        while True:
            line = await process.stderr.readline()
            if not line:
                break
            
            line_str = line.decode('utf-8', errors='ignore')
            logger.debug(f"ffmpeg: {line_str.strip()}") # Log ffmpeg output for debugging
            if progress_callback:
                match = re.search(r'time=(\d+):(\d+):(\d+\.?\d*)', line_str)
                if match:
                    hours = int(match.group(1))
                    minutes = int(match.group(2))
                    seconds = float(match.group(3))
                    elapsed_time = hours * 3600 + minutes * 60 + seconds
                    # We do two passes, so we scale progress to 50% for each pass.
                    # This is a simplification but gives a reasonable progress indication.
                    progress = min(99.9, (elapsed_time / duration) * 100)
                    await progress_callback(progress)
        
        await process.wait()
        if process.returncode != 0:
            # Try to read any remaining stderr content for the error message
            remaining_err = await process.stderr.read()
            err_msg = remaining_err.decode('utf-8', errors='ignore').strip()
            raise CompressionError(f"FFmpeg pass failed with code {process.returncode}. Error: {err_msg}. Command: {' '.join(cmd)}")

    async def compress_if_needed(
        self,
        input_path: str,
        progress_callback: Optional[Callable[[float], Awaitable[None]]] = None
    ) -> tuple[str, bool]:
        """
        Compresses a video file if it exceeds MAX_SIZE_BYTES.

        Args:
            input_path: Path to the video file.
            progress_callback: An async function to call with progress updates (0-100).

        Returns:
            A tuple containing the path to the final video and a boolean indicating
            if compression was performed.

        Raises:
            CompressionError: If FFmpeg fails at any stage.
        """
        if os.path.getsize(input_path) <= self.MAX_SIZE_BYTES:
            return input_path, False

        output_path = f"{os.path.splitext(input_path)[0]}_compressed.mp4"
        
        duration = await self._get_video_duration(input_path)
        if duration <= 0:
            raise CompressionError("Video has invalid or zero duration.")

        # Target 95% of max size to be safe. Bitrate in bits/sec.
        target_bits = (self.MAX_SIZE_BYTES * 0.95) * 8
        # Subtract audio bitrate (128k) from total to get video budget
        video_bitrate = int((target_bits / duration) - (128 * 1000))

        if video_bitrate <= 0:
            raise CompressionError(f"Video is too long ({duration}s) to be compressed to the target size.")

        with tempfile.TemporaryDirectory() as temp_dir:
            pass_log_file = os.path.join(temp_dir, "ffmpeg-pass")
            
            common_args = [
                "ffmpeg", "-y", "-i", input_path,
                "-c:v", "libx264",
                "-preset", "fast",
                "-b:v", str(video_bitrate),
                "-passlogfile", pass_log_file,
            ]
            
            # --- Pass 1 ---
            pass1_cmd = common_args + ["-pass", "1", "-an", "-f", "null", os.devnull]
            logger.info(f"Starting FFmpeg pass 1 for {os.path.basename(input_path)}...")
            await self._run_ffmpeg_pass(pass1_cmd, duration, progress_callback)
            
            # --- Pass 2 ---
            pass2_cmd = common_args + [
                "-pass", "2",
                "-c:a", "aac",
                "-b:a", "128k",
                output_path
            ]
            logger.info(f"Starting FFmpeg pass 2 for {os.path.basename(input_path)}...")
            await self._run_ffmpeg_pass(pass2_cmd, duration, progress_callback)

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise CompressionError("Compression finished, but output file is missing or empty.")

        logger.info(f"Successfully compressed {os.path.basename(input_path)} to {os.path.getsize(output_path) / 1024 / 1024:.2f} MB")
        return output_path, True
