import os
import asyncio
import tempfile
import shutil
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import yt_dlp
from utils.logger import setup_logger
from utils.progress import ProgressTracker, ProgressStage

logger = setup_logger()

class YoutubeService:
    YOUTUBE_PATTERNS = [
        r'(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+(?:[&?][\w=%-]*)*)',
        r'(https?://youtu\.be/[\w-]+(?:\?[\w=%-]*)*)',
        r'(https?://(?:www\.)?youtube\.com/shorts/[\w-]+(?:\?[\w=%-]*)*)',
        r'(https?://m\.youtube\.com/watch\?v=[\w-]+(?:[&?][\w=%-]*)*)',
    ]
    
    COMPRESSION_THRESHOLD_BYTES = 49 * 1024 * 1024 
    
    def __init__(self, max_workers: int = 4, cookie_file: str = 'cookies.txt'):
        self.name = "YoutubeService" 
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self.cookie_file = cookie_file if os.path.exists(cookie_file) else None 

    def extract_url(self, text: str) -> Optional[str]:
        if not text: return None 
        import re
        for pattern in [re.compile(p) for p in self.YOUTUBE_PATTERNS]:
            match = pattern.search(text)
            if match: return match.group(1)
        return None 

    def _download_sync(self, url: str, temp_dir: str, tracker: Optional[ProgressTracker] = None) -> Dict[str, Any]:
        """Sync download with smart format selection.""" 
        
        def progress_hook(d: dict) -> None:
            if not tracker: return 
            if d['status'] == 'downloading':
                p = d.get('_percent_str', '0%').replace('%','')
                try: 
                    tracker.update(stage=ProgressStage.DOWNLOADING, progress=float(p))
                except: pass

        # SMART FORMAT SELECTION: 
        # 1. Try to find a video+audio combo under 50MB (filesize<50M)
        # 2. Fallback to best quality (will require compression later)
        format_str = (
            'bestvideo[ext=mp4][filesize<50M]+bestaudio[ext=m4a]/'  # Best MP4 video < 50MB + audio
            'best[ext=mp4][filesize<50M]/'                          # Best single file < 50MB
            'bestvideo[ext=mp4]+bestaudio[ext=m4a]/'                # Fallback: Best quality (compress later)
            'best[ext=mp4]/best'                                    # Fallback: Absolute best
        )

        ydl_opts = {
            'format': format_str,
            'merge_output_format': 'mp4',
            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
            'restrictfilenames': True,
            'progress_hooks': [progress_hook],
            'quiet': True, 'no_warnings': True, 'noplaylist': True,
        }
        
        if self.cookie_file: ydl_opts['cookiefile'] = self.cookie_file
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[arg-type]
                if tracker: tracker.update(stage=ProgressStage.DOWNLOADING, progress=0, speed="Starting...")
                info = ydl.extract_info(url, download=True)
                
                mp4_files = [f for f in os.listdir(temp_dir) if f.endswith('.mp4')]
                if not mp4_files: raise RuntimeError("No MP4 file found")
                
                downloaded_file = os.path.join(temp_dir, mp4_files[0])
                file_size = os.path.getsize(downloaded_file)

                # Move to a new temp file that persists after cleanup
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_dest:
                    final_path = temp_dest.name
                shutil.move(downloaded_file, final_path)
                
                # Check if compression is actually needed
                needs_compression = file_size > self.COMPRESSION_THRESHOLD_BYTES
                
                return {
                    'file_path': final_path,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'file_size_mb': file_size / (1024 * 1024),
                    'needs_compression': needs_compression, 
                    'uploader': info.get('uploader', ''),
                }
        except Exception as e:
            if tracker: tracker.set_error(str(e))
            raise

    async def download(self, url: str, progress_tracker: Optional[ProgressTracker] = None) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        temp_dir = tempfile.mkdtemp(prefix='yt_download_')
        try:
            return await loop.run_in_executor(self._executor, self._download_sync, url, temp_dir, progress_tracker)
        finally:
            self.cleanup(temp_dir)
    
    def cleanup(self, temp_dir: str) -> None:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.debug(f"Cleaned up {temp_dir}")
    
    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)