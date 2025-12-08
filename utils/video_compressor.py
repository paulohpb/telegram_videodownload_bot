import os
import asyncio
import subprocess
from typing import Optional, Callable, Awaitable
from utils.logger import setup_logger

logger = setup_logger()

class VideoCompressor:
    # 49.5 MB to be safe
    MAX_SIZE_BYTES = int(49.5 * 1024 * 1024)

    async def compress_if_needed(
        self,
        input_path: str,
        progress_callback: Optional[Callable[[float], Awaitable[None]]] = None
    ) -> tuple[str, bool]:
        
        # 1. Quick check: Skip if already small enough
        if os.path.getsize(input_path) <= self.MAX_SIZE_BYTES:
            logger.info("Video fits within limit. Skipping compression.")
            return input_path, False

        output_path = f"{os.path.splitext(input_path)[0]}_compressed.mp4"
        
        # 2. Single-Pass Compression (CRF 28 + veryfast)
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "veryfast",  # Fast encoding
            "-crf", "28",           # Balance quality/size
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            output_path
        ]

        logger.info(f"Starting Single-Pass Compression: {os.path.basename(input_path)}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, stderr=subprocess.PIPE
            )
            
            if progress_callback: await progress_callback(50.0)
            
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"FFmpeg failed: {stderr.decode()}")

            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise Exception("Compressed file created but empty.")
                
            if progress_callback: await progress_callback(100.0)

            logger.info(f"Compression finished. New size: {os.path.getsize(output_path)/1024/1024:.2f}MB")
            return output_path, True

        except Exception as e:
            logger.error(f"Compression error: {e}")
            if os.path.exists(output_path): os.remove(output_path)
            raise e