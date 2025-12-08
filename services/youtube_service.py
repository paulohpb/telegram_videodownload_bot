import os
import re
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
    """YouTube video download service using yt-dlp with async support.""" 
    
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
        self._compiled_patterns = [re.compile(p) for p in self.YOUTUBE_PATTERNS]
        self.cookie_file = cookie_file if os.path.exists(cookie_file) else None 
        if self.cookie_file: logger.info(f"Using cookie file: {self.cookie_file}")
    
    def extract_url(self, text: str) -> Optional[str]:
        if not text: return None 
        for pattern in self._compiled_patterns:
            match = pattern.search(text)
            if match: return match.group(1)
        return None 
    
    def _download_sync(self, url: str, temp_dir: str, tracker: Optional[ProgressTracker] = None) -> Dict[str, Any]:
        """Sync download with progress hooks.""" 
        
        def progress_hook(d: dict) -> None:
            if not tracker: return 
            try:
                status = d.get('status', '')
                if status == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    progress = (downloaded / total * 100) if total > 0 else 0
                    
                    # Parse Speed
                    speed_str = ""
                    speed = d.get('speed')
                    if speed:
                        speed_str = f"{speed/1024/1024:.1f} MB/s" if speed > 1024*1024 else f"{speed/1024:.1f} KB/s"
                    
                    # Parse ETA
                    eta_str = ""
                    eta = d.get('eta')
                    if eta: eta_str = f"{eta}s"

                    tracker.update(
                        stage=ProgressStage.DOWNLOADING,
                        progress=progress,
                        speed=speed_str,
                        eta=eta_str,
                        filename=os.path.basename(d.get('filename', ''))
                    )
                elif status == 'finished':
                    tracker.update(stage=ProgressStage.PROCESSING, progress=100, eta="Merging...")
            except Exception as e:
                logger.warning(f"Hook error: {e}")

        ydl_opts: Dict[str, Any] = {
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'postprocessor_args': {'merger': ['-preset', 'fast']}, # Speed optimization
            'outtmpl': os.path.join(temp_dir, '%(id)s_%(title)s.%(ext)s'),
            'restrictfilenames': True,
            'progress_hooks': [progress_hook],
            'quiet': True, 'no_warnings': True, 'noplaylist': True,
        }
        
        if self.cookie_file: ydl_opts['cookiefile'] = self.cookie_file
        
        try:
            # type: ignore 
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: # type: ignore
                if tracker: tracker.update(stage=ProgressStage.DOWNLOADING, progress=0, speed="Starting...")
                info = ydl.extract_info(url, download=True)
                
                # Find file
                mp4_files = [f for f in os.listdir(temp_dir) if f.endswith('.mp4')]
                if not mp4_files: raise RuntimeError("No MP4 file found after download")
                
                downloaded_file = os.path.join(temp_dir, mp4_files[0])
                file_size = os.path.getsize(downloaded_file)
                needs_compression = file_size > self.COMPRESSION_THRESHOLD_BYTES
                
                return {
                    'file_path': downloaded_file,
                    'temp_dir': temp_dir,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'file_size_mb': file_size / (1024 * 1024),
                    'needs_compression': needs_compression,
                    'uploader': info.get('uploader', ''),
                    'ext': 'mp4',
                }
        except Exception as e:
            if tracker: tracker.set_error(str(e))
            raise

    async def download(self, url: str, progress_tracker: Optional[ProgressTracker] = None) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        temp_dir = tempfile.mkdtemp(prefix='yt_download_')
        try:
            return await loop.run_in_executor(self._executor, self._download_sync, url, temp_dir, progress_tracker)
        except Exception:
            self.cleanup(temp_dir)
            raise 
    
    def cleanup(self, temp_dir: str) -> None:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.debug(f"Cleaned up {temp_dir}")
    
    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)