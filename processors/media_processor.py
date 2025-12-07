"""
Media processing module.
"""
import os
import tempfile
from typing import Any, List, Optional
from utils.logger import setup_logger
from utils.video_compressor import VideoCompressor

logger = setup_logger()

class MediaProcessor:
    def __init__(self, client: Any, queue_manager=None):
        self.client = client
        self.queue_manager = queue_manager
        self.compressor = VideoCompressor()
    
    async def process(self, task: Any, worker_id: int) -> None:
        processing_msg = None
        temp_files: List[str] = []
        temp_dirs: List[str] = []
        try:
            processing_msg = await task.event.reply(f"⏬ Downloading...")
            
            # 1. Download
            task.status = 'downloading'
            self._update_status('downloading', 1)
            result = await task.service.download(task.url)
            self._update_status('downloading', -1)
            
            # Handle different service return formats
            if 'file_path' in result:
                # Real service (YouTube) - file downloaded to temp directory
                video_path = result['file_path']
                if 'temp_dir' in result:
                    temp_dirs.append(result['temp_dir'])
                original_size_mb = result['file_size_mb']
                title = result.get('title', 'Video')
            else:
                # Mock service - returns raw video_data
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
                    f.write(result['video_data'])
                    video_path = f.name
                temp_files.append(video_path)
                original_size_mb = result['file_size_mb']
                title = result.get('title', 'Video')
            
            # 2. Compress
            task.status = 'compressing'
            self._update_status('compressing', 1)
            await processing_msg.edit(f"🔧 Compressing ({original_size_mb}MB)...")
            
            final_path, was_compressed = await self.compressor.compress_if_needed(video_path)
            self._update_status('compressing', -1)
            
            if was_compressed and final_path != video_path:
                temp_files.append(final_path)
            
            # 3. Upload
            task.status = 'uploading'
            self._update_status('uploading', 1)
            await processing_msg.edit("⏫ Uploading...")
            await self.client.send_file(
                task.event.chat_id,
                final_path,
                caption=f"📹 {title}",
                reply_to=task.event.reply_to_msg_id
            )
            self._update_status('uploading', -1)
            
            await processing_msg.delete()
            
        except Exception as e:
            logger.error(f"Process error: {e}")
            raise
        finally:
            # Clean up temporary files
            for p in temp_files:
                if os.path.exists(p):
                    os.unlink(p)
            
            # Clean up temporary directories (including downloaded videos)
            for temp_dir in temp_dirs:
                self._cleanup_temp_dir(temp_dir)
    
    def _cleanup_temp_dir(self, temp_dir: str) -> None:
        """Clean up temporary directory recursively."""
        if not temp_dir or not os.path.exists(temp_dir):
            return
        
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.debug(f"Cleaned up temp directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp directory {temp_dir}: {e}")
    
    def _update_status(self, type_s, inc):
        if self.queue_manager:
            self.queue_manager.update_status(type_s, inc)
