"""
Media processing module.
"""
import os
import tempfile
from typing import Any, List
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
        try:
            processing_msg = await task.event.reply(f"⏬ Downloading...")
            
            # 1. Download (Mock)
            task.status = 'downloading'
            self._update_status('downloading', 1)
            result = await task.service.download("mock_url")
            self._update_status('downloading', -1)
            
            # Save temp
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
                f.write(result['video_data'])
                video_path = f.name
            temp_files.append(video_path)
            
            # 2. Compress
            original_size_mb = result['file_size_mb']
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
                caption="Here is your processed video",
                reply_to=task.event.reply_to_msg_id
            )
            self._update_status('uploading', -1)
            
            await processing_msg.delete()
            
        except Exception as e:
            logger.error(f"Process error: {e}")
            raise
        finally:
            for p in temp_files:
                if os.path.exists(p):
                    os.unlink(p)
    
    def _update_status(self, type_s, inc):
        if self.queue_manager:
            self.queue_manager.update_status(type_s, inc)
