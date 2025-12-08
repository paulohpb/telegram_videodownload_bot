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
        r'https?://(?:www\.)?twitter\.com/\w+/status/\d+',
        r'https?://(?:www\.)?x\.com/\w+/status/\d+',
    ]
    
    def __init__(self, cookie_file: str = 'cookies.txt'):
        self._youtube_compiled = [re.compile(p) for p in self.YOUTUBE_PATTERNS]
        self._twitter_compiled = [re.compile(p) for p in self.TWITTER_PATTERNS]
        self.cookie_file = cookie_file
    
    def get_service_for_url(self, text: str) -> Optional[Any]:
        if not text: return None
        
        if any(p.search(text) for p in self._youtube_compiled):
            return YoutubeService(cookie_file=self.cookie_file)
            
        if any(p.search(text) for p in self._twitter_compiled):
            return TwitterService()
            
        if "test.com" in text:
            # Mock Service implementation would go here (omitted for brevity)
            return None
            
        return None