"""Twitter/X video download service using yt-dlp for metadata extraction
and FFmpeg for HLS/m3u8 stream download.
"""
import os
import re
import asyncio
import tempfile
import shutil
import subprocess
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

import yt_dlp
import aiohttp

from utils.logger import setup_logger
from utils.progress import ProgressTracker, ProgressStage


logger = setup_logger()


class TwitterService:
    """
    Twitter/X video download service.
    
    Strategy:
    1. Use yt-dlp to extract metadata and stream URLs (skip download).
    2. Attempt Direct MP4 download first (fast, efficient).
    3. Fallback to FFmpeg HLS/m3u8 download if direct fails (robust).
    """
    
    # Combined patterns for Twitter and X
    TWITTER_PATTERNS = [
        r'(https?://(?:www\.)?twitter\.com/[\w/]+/status/\d+)',
        r'(https?://(?:www\.)?x\.com/[\w/]+/status/\d+)',
        r'(https?://mobile\.twitter\.com/[\w/]+/status/\d+)',
        r'(https?://t\.co/[\w]+)',
        r'(https?://(?:www\.)?twitter\.com/i/videos/\d+)',
        r'(https?://(?:www\.)?x\.com/i/videos/\d+)',
    ]
    
    COMPRESSION_THRESHOLD_BYTES = 49 * 1024 * 1024
    
    # Primary User Agent (TwitterBot often bypasses strict rate limits)
    USER_AGENT = 'TwitterBot/1.0'
    
    # Fallback User Agents
    FALLBACK_USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    ]
    
    FFMPEG_TIMEOUT = 600
    
    def __init__(self, max_workers: int = 4):
        self.name = "TwitterService"
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._compiled_patterns = [re.compile(p) for p in self.TWITTER_PATTERNS]
    
    def extract_url(self, text: str) -> Optional[str]:
        """Extract and clean Twitter/X URL."""
        if not text: return None
        
        for pattern in self._compiled_patterns:
            match = pattern.search(text)
            if match:
                url = match.group(1)
                # Remove tracking parameters for cleaner logging
                url = re.sub(r'\?.*$', '', url)
                return url
        return None

    async def _download_direct_aiohttp(
        self, url: str, output_path: str, user_agent: str, progress_tracker: Optional[ProgressTracker]
    ) -> bool:
        """Download a file directly using aiohttp with progress."""
        logger.info("Attempting Direct MP4 download via aiohttp...")
        try:
            headers = {'User-Agent': user_agent}
            timeout = aiohttp.ClientTimeout(total=self.FFMPEG_TIMEOUT)
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"Aiohttp download failed with status: {response.status}")
                        return False
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0
                    
                    with open(output_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            if progress_tracker and total_size > 0:
                                progress = 10 + min(90.0, (downloaded_size / total_size) * 90)
                                progress_tracker.update(stage=ProgressStage.DOWNLOADING, progress=progress)
            
            logger.info("Aiohttp download successful")
            return True
        except Exception as e:
            logger.warning(f"Aiohttp download failed: {e}")
            if os.path.exists(output_path): os.remove(output_path)
            return False

    def _extract_metadata_sync(self, url: str, user_agent: str) -> Dict[str, Any]:
        """Use yt-dlp to get the m3u8 manifest and metadata without downloading."""
        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'http_headers': {'User-Agent': user_agent},
            'nocheckcertificate': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore
            logger.info(f"Extracting Twitter metadata: {url}")
            info = ydl.extract_info(url, download=False)
            
            if not info:
                raise RuntimeError("Failed to extract video information")
            
            # Find best streams
            m3u8_url = None
            direct_url = None
            formats = info.get('formats') or []
            
            # Fallback if formats are empty but 'url' exists
            if not formats and info.get('url'):
                direct_url = info.get('url')
            
            best_height = 0
            for fmt in formats:
                f_url = fmt.get('url', '')
                ext = fmt.get('ext', '')
                height = fmt.get('height') or 0
                
                # Check for HLS
                if '.m3u8' in f_url or fmt.get('protocol') == 'm3u8_native':
                    if height >= best_height: # Prefer higher quality
                        m3u8_url = f_url
                # Check for Direct MP4
                elif ext == 'mp4':
                    if height >= best_height:
                        direct_url = f_url
                        
                best_height = max(best_height, height)

            # Title Cleanup
            title = info.get('title') or info.get('description', 'Twitter Video')
            title = re.sub(r'https?://\S+', '', title).strip()[:100]

            return {
                'm3u8_url': m3u8_url,
                'direct_url': direct_url,
                'title': title,
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'video_id': info.get('id', ''),
                'ext': 'mp4'
            }

    def _download_with_ffmpeg(
        self, video_url: str, output_path: str, is_hls: bool, 
        duration: float, user_agent: str, progress_tracker: Optional[ProgressTracker]
    ) -> None: 
        """Robust FFmpeg downloader with reconnect flags and progress parsing."""
        
        cmd = [
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'info', '-stats',
            '-user_agent', user_agent,
            '-headers', 'Referer: https://twitter.com/\r\n',
        ]

        if is_hls:
            # Crucial flags for resilient HLS downloading
            cmd.extend([
                '-reconnect', '1',
                '-reconnect_streamed', '1',
                '-reconnect_delay_max', '5',
                '-protocol_whitelist', 'file,http,https,tcp,tls,crypto',
            ])
        
        cmd.extend(['-i', video_url])
        
        # Audio/Video encoding options
        cmd.extend([
            '-c', 'copy',                # Copy stream (fastest)
            '-bsf:a', 'aac_adtstoasc',   # Fix AAC audio bitstream (Critical for Twitter HLS)
            '-movflags', '+faststart',   # Optimize MP4 for streaming
            '-f', 'mp4',
            output_path
        ])

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
        )

        try:
            assert process.stderr is not None
            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None: break
                
                # Parse Progress
                if line and progress_tracker and duration > 0:
                    # Regex to find "time=00:00:15.40"
                    time_match = re.search(r'time=(\d+):(\d+):(\d+\.?\d*)', line)
                    if time_match:
                        h, m, s = int(time_match.group(1)), int(time_match.group(2)), float(time_match.group(3))
                        curr_seconds = h*3600 + m*60 + s
                        
                        # Calculate % (10% allocated to extraction, 90% to download)
                        prog = 10 + min(90.0, (curr_seconds / duration) * 90)
                        
                        # Extract speed if possible
                        speed_match = re.search(r'speed=\s*([\d.]+)x', line)
                        speed = f"{speed_match.group(1)}x" if speed_match else ""
                        
                        progress_tracker.update(
                            stage=ProgressStage.DOWNLOADING,
                            progress=prog,
                            speed=speed
                        )

            if process.returncode != 0:
                raise RuntimeError(f"FFmpeg failed with code {process.returncode}")
                
        except subprocess.TimeoutExpired:
            process.kill()
            raise RuntimeError("Download timed out")
        except Exception as e:
            if os.path.exists(output_path): os.remove(output_path)
            raise e

    async def download(self, url: str, progress_tracker: Optional[ProgressTracker] = None) -> Dict[str, Any]:
        """Async entry point. Tries direct aiohttp download first, then falls back."""
        loop = asyncio.get_running_loop()
        temp_dir = tempfile.mkdtemp(prefix='twitter_dl_')
        
        try:
            # --- 1. Metadata Extraction ---
            if progress_tracker:
                progress_tracker.update(stage=ProgressStage.DOWNLOADING, progress=5, speed="Extracting info...")

            last_error = None
            meta = None
            for user_agent in [self.USER_AGENT] + self.FALLBACK_USER_AGENTS:
                try:
                    logger.info(f"Attempting to extract metadata with user agent: {user_agent}")
                    meta = await loop.run_in_executor(self._executor, self._extract_metadata_sync, url, user_agent)
                    logger.info(f"Metadata extracted: {meta}")
                    break 
                except Exception as e:
                    last_error = e
                    logger.warning(f"Metadata extraction failed with UA {user_agent}: {e}")
                    if any(x in str(e).lower() for x in ['not found', 'private']): break
            
            if not meta:
                raise RuntimeError(f"Failed to extract metadata after all attempts. Last error: {last_error}")

            safe_title = re.sub(r'[^\w\s-]', '', meta['title'])[:50].strip().replace(' ', '_')
            output_path = os.path.join(temp_dir, f"{safe_title}_{meta['video_id']}.mp4")

            # --- 2. Direct Download Attempt ---
            downloaded = False
            if meta['direct_url']:
                downloaded = await self._download_direct_aiohttp(
                    meta['direct_url'], output_path, self.USER_AGENT, progress_tracker
                )

            # --- 3. FFmpeg HLS Fallback ---
            if not downloaded:
                logger.info("Direct download failed or unavailable, falling back to FFmpeg HLS.")
                if not meta['m3u8_url']:
                    raise RuntimeError("No m3u8 stream found for FFmpeg fallback.")

                await loop.run_in_executor(
                    self._executor, self._download_with_ffmpeg,
                    meta['m3u8_url'], output_path, True, meta['duration'], self.USER_AGENT, progress_tracker
                )
            
            # --- 4. Finalize ---
            if not os.path.exists(output_path) or os.path.getsize(output_path) < 10000:
                raise RuntimeError("File not created or empty after all download attempts.")

            file_size = os.path.getsize(output_path)
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_dest:
                final_path = temp_dest.name
            shutil.move(output_path, final_path)

            if progress_tracker:
                progress_tracker.update(stage=ProgressStage.PROCESSING, progress=100)

            logger.info(f"Download successful. Final path: {final_path}")
            return {
                'file_path': final_path,
                'title': meta['title'],
                'duration': meta['duration'],
                'file_size_mb': file_size / (1024 * 1024),
                'needs_compression': file_size > self.COMPRESSION_THRESHOLD_BYTES,
                'uploader': meta['uploader'],
                'ext': 'mp4'
            }

        except Exception as e:
            if progress_tracker: progress_tracker.set_error(str(e))
            logger.error(f"Download orchestration failed: {e}")
            raise
        finally:
            self.cleanup(temp_dir)


    def cleanup(self, temp_dir: str) -> None:
        if temp_dir and os.path.exists(temp_dir):
            logger.info(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)
