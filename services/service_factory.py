import re
from typing import Optional, Any
from utils.logger import setup_logger

# Import services
from services.youtube_service import YoutubeService
from services.twitter_service import TwitterService

logger = setup_logger()

class ServiceFactory:
    YOUTUBE_PATTERNS = [
        r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
        r'https?://youtu\.be/[\w-]+',
        r'https?://(?:www\.)?youtube\.com/shorts/[\w-]+',
    ]
    
    TWITTER_PATTERNS = [
        r'https?://(?:www\.)?twitter\.com/[\w/]+/status/\d+',
        r'https?://(?:www\.)?x\.com/[\w/]+/status/\d+',
        r'https?://mobile\.twitter\.com/[\w/]+/status/\d+',
        r'https?://t\.co/[\w]+',
        r'https?://(?:www\.)?twitter\.com/i/videos/\d+',
        r'https?://(?:www\.)?x\.com/i/videos/\d+',
    ]
    
    def __init__(self):
        self._youtube_compiled = [re.compile(p) for p in self.YOUTUBE_PATTERNS]
        self._twitter_compiled = [re.compile(p) for p in self.TWITTER_PATTERNS]
    
    def get_service_for_url(self, text: str) -> Optional[Any]:
        if not text: return None
        
        logger.info(f"Checking for service for text: {text}")

        if any(p.search(text) for p in self._youtube_compiled):
            logger.info("Youtube service selected")
            return YoutubeService()
            
        if any(p.search(text) for p in self._twitter_compiled):
            logger.info("Twitter service selected")
            return TwitterService()
            
        if "test.com" in text:
            # Mock Service implementation would go here (omitted for brevity)
            return None
            
        logger.info("No service found")
        return None