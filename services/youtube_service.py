import os
import re
import asyncio
import tempfile
import shutil
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError

from utils.logger import setup_logger


logger = setup_logger()


class YoutubeService:
    """YouTube video download service using yt-dlp with async support."""
    
    # YouTube URL regex patterns covering standard link formats
    YOUTUBE_PATTERNS = [
        # Standard watch URLs (with optional additional parameters)
        r'(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+(?:[&?][\w=%-]*)*)',
        # Short URLs
        r'(https?://youtu\.be/[\w-]+(?:\?[\w=%-]*)*)',
        # Shorts
        r'(https?://(?:www\.)?youtube\.com/shorts/[\w-]+(?:\?[\w=%-]*)*)',
        # Mobile URLs
        r'(https?://m\.youtube\.com/watch\?v=[\w-]+(?:[&?][\w=%-]*)*)',
        # Embed URLs
        r'(https?://(?:www\.)?youtube\.com/embed/[\w-]+)',
        # YouTube Music
        r'(https?://music\.youtube\.com/watch\?v=[\w-]+(?:[&?][\w=%-]*)*)',
    ]
    
    def __init__(self, max_workers: int = 2):
        """
        Initialize YouTube service.
        
        Args:
            max_workers: Maximum concurrent downloads in executor pool
        """
        self.name = "YoutubeService"
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._compiled_patterns = [re.compile(pattern) for pattern in self.YOUTUBE_PATTERNS]
    
    def extract_url(self, text: str) -> Optional[str]:
        """
        Extract YouTube URL from text message.
        
        Args:
            text: Text that may contain a YouTube URL
            
        Returns:
            Extracted YouTube URL or None if not found
        """
        if not text:
            return None
            
        for pattern in self._compiled_patterns:
            match = pattern.search(text)
            if match:
                url = match.group(1)
                logger.debug(f"Extracted YouTube URL: {url}")
                return url
        
        return None
    
    def _download_sync(self, url: str, temp_dir: str) -> Dict[str, Any]:
        """
        Synchronous download implementation using yt-dlp.
        
        Downloads video at 1080p or best available quality below,
        merges into MP4 container.
        
        Args:
            url: YouTube video URL
            temp_dir: Temporary directory path for download
            
        Returns:
            Dict containing file path and video metadata
            
        Raises:
            RuntimeError: If download fails or no MP4 file is produced
        """
        ydl_opts = {
            # Format selection: best video up to 1080p + best audio
            # Fallback to best combined format up to 1080p
            'format': (
                'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/'
                'bestvideo[height<=1080]+bestaudio/'
                'best[height<=1080]'
            ),
            
            # Force merge into MP4 container
            'merge_output_format': 'mp4',
            
            # Output template with restricted safe filenames
            'outtmpl': os.path.join(temp_dir, '%(id)s_%(title)s.%(ext)s'),
            'restrictfilenames': True,
            
            # Suppress console output
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            
            # Embed metadata
            'postprocessors': [
                {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                }
            ],
            
            # Don't download playlists, only single video
            'noplaylist': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore
                logger.info(f"Extracting info and downloading: {url}")
                
                # Extract info and download
                info = ydl.extract_info(url, download=True)
                
                if info is None:
                    raise RuntimeError("Failed to extract video information")
                
                # Find the downloaded MP4 file in temp directory
                mp4_files = [
                    f for f in os.listdir(temp_dir) 
                    if f.endswith('.mp4') and os.path.isfile(os.path.join(temp_dir, f))
                ]
                
                if not mp4_files:
                    # List what we got for debugging
                    all_files = os.listdir(temp_dir)
                    raise RuntimeError(
                        f"No MP4 file found after download. Files in temp dir: {all_files}"
                    )
                
                # Use the first (and should be only) MP4 file
                downloaded_file = os.path.join(temp_dir, mp4_files[0])
                file_size = os.path.getsize(downloaded_file)
                
                # Extract relevant metadata
                result = {
                    'file_path': downloaded_file,
                    'temp_dir': temp_dir,
                    'title': info.get('title', 'Unknown'),
                    'description': info.get('description', ''),
                    'duration': info.get('duration', 0),
                    'file_size_mb': file_size / (1024 * 1024),
                    'uploader': info.get('uploader', 'Unknown'),
                    'upload_date': info.get('upload_date', ''),
                    'view_count': info.get('view_count', 0),
                    'video_id': info.get('id', ''),
                    'resolution': info.get('resolution', 'Unknown'),
                    'ext': 'mp4',
                }
                
                logger.info(
                    f"Download successful: '{result['title']}' "
                    f"({result['file_size_mb']:.2f}MB, {result['duration']}s)"
                )
                
                return result
                
        except DownloadError as e:
            raise RuntimeError(f"Download failed: {str(e)}")
        except ExtractorError as e:
            raise RuntimeError(f"Failed to extract video info: {str(e)}")
    
    async def download(self, url: str) -> Dict[str, Any]:
        """
        Download YouTube video asynchronously.
        
        Creates a temporary directory and runs the download in an executor
        to avoid blocking the event loop.
        
        Args:
            url: YouTube video URL
            
        Returns:
            Dict containing:
                - file_path: Path to downloaded MP4 file
                - temp_dir: Temporary directory (caller must clean up)
                - title: Video title
                - description: Video description
                - duration: Video duration in seconds
                - file_size_mb: File size in megabytes
                - uploader: Channel name
                - upload_date: Upload date (YYYYMMDD format)
                - view_count: Number of views
                - video_id: YouTube video ID
                - resolution: Video resolution
                - ext: File extension (always 'mp4')
                
        Raises:
            RuntimeError: If download fails
            ValueError: If URL is invalid
        """
        if not url:
            raise ValueError("URL cannot be empty")
        
        loop = asyncio.get_running_loop()
        
        # Create temporary directory for this download
        temp_dir = tempfile.mkdtemp(prefix='yt_download_')
        logger.debug(f"Created temp directory: {temp_dir}")
        
        try:
            result = await loop.run_in_executor(
                self._executor,
                self._download_sync,
                url,
                temp_dir
            )
            return result
            
        except Exception as e:
            # Clean up temp directory on failure
            logger.error(f"YouTube download failed for {url}: {str(e)}")
            self.cleanup(temp_dir)
            raise
    
    def cleanup(self, temp_dir: str) -> None:
        """
        Clean up temporary directory after processing.
        
        Should be called by the consumer after the downloaded file
        is no longer needed.
        
        Args:
            temp_dir: Path to temporary directory to remove
        """
        if not temp_dir or not os.path.exists(temp_dir):
            return
            
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.debug(f"Cleaned up temp directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp directory {temp_dir}: {e}")
    
    def shutdown(self) -> None:
        """
        Shutdown the executor pool.
        
        Should be called when the service is no longer needed.
        """
        logger.info("Shutting down YoutubeService executor")
        self._executor.shutdown(wait=True)
