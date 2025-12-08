import os
import asyncio
from typing import Any, List, Optional
from utils.logger import setup_logger
from utils.video_compressor import VideoCompressor
from utils.progress import ProgressTracker, ProgressStage, format_progress_message

logger = setup_logger()

class MediaProcessor:
    def __init__(self, client: Any, queue_manager: Optional[Any] = None):
        self.client = client
        self.queue_manager = queue_manager
        self.compressor = VideoCompressor()
    
    async def process(self, task: Any, worker_id: int) -> None:
        service = task.service
        tracker = ProgressTracker(throttle_seconds=2.5) # Rate limit updates
        processing_msg = None
        temp_files = []
        progress_task = None
        title = "Video"
        
        try:
            processing_msg = await task.event.reply("⏳ Starting...")
            # Start background poller
            progress_task = asyncio.create_task(self._progress_updater(processing_msg, tracker, lambda: title))
            
            # === DOWNLOAD ===
            self._update_status('downloading', 1)
            tracker.update(stage=ProgressStage.DOWNLOADING, progress=0)
            result = await service.download(task.url, progress_tracker=tracker)
            self._update_status('downloading', -1)
            
            video_path = result['file_path']
            title = result.get('title', 'Video')
            
            # === COMPRESS ===
            final_path = video_path
            if result.get('needs_compression'):
                self._update_status('compressing', 1)
                tracker.update(stage=ProgressStage.COMPRESSING, progress=0, eta="Calculating...")
                
                async def comp_cb(p): tracker.update(stage=ProgressStage.COMPRESSING, progress=p)
                final_path, was_comp = await self.compressor.compress_if_needed(video_path, progress_callback=comp_cb)
                
                if was_comp and final_path != video_path: temp_files.append(final_path)
                self._update_status('compressing', -1)
            
            # === UPLOAD ===
            self._update_status('uploading', 1)
            tracker.update(stage=ProgressStage.UPLOADING, progress=0)
            
            def upload_cb(curr, tot):
                if tot > 0: tracker.update(stage=ProgressStage.UPLOADING, progress=(curr/tot)*100)

            await self.client.send_file(
                task.event.chat_id, final_path, 
                caption=f"📹 **{title}**", 
                progress_callback=upload_cb
            )
            self._update_status('uploading', -1)
            tracker.set_completed()

        except Exception as e:
            logger.error(f"Task failed: {e}")
            tracker.set_error(str(e))
            raise
        finally:
            if progress_task: 
                progress_task.cancel()
                try: await progress_task
                except asyncio.CancelledError: pass
            
            # Final UI update
            await self._safe_edit(processing_msg, format_progress_message(tracker.get_state(), title))
            if tracker.get_state().completed and processing_msg:
                await processing_msg.delete()

            # Cleanup
            for f in temp_files:
                if os.path.exists(f): os.unlink(f)
            if service and 'temp_dir' in locals():
                service.cleanup(result['temp_dir'])

    async def _progress_updater(self, msg, tracker, get_title):
        """Polls tracker state and edits message respecting rate limits."""
        last_text = ""
        try:
            while True:
                await asyncio.sleep(0.5)
                state = tracker.get_state()
                if state.completed or state.stage == ProgressStage.FAILED: break
                
                if tracker.should_update_message():
                    text = format_progress_message(state, get_title())
                    if text != last_text:
                        await self._safe_edit(msg, text)
                        last_text = text
        except asyncio.CancelledError: pass

    async def _safe_edit(self, msg, text):
        try: await msg.edit(text)
        except Exception: pass

    def _update_status(self, type_s, inc):
        if self.queue_manager: self.queue_manager.update_status(type_s, inc)