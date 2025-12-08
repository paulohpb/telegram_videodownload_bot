import re
from typing import Optional, Any
from utils.logger import setup_logger

logger = setup_logger()

class ServiceFactory:
    YOUTUBE_PATTERNS = [
        r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
        r'https?://youtu\.be/[\w-]+',
        r'https?://(?:www\.)?youtube\.com/shorts/[\w-]+',
    ]
    
    def __init__(self, cookie_file: str = 'cookies.txt'):
        self._compiled = [re.compile(p) for p in self.YOUTUBE_PATTERNS]
        self.cookie_file = cookie_file
    
    def get_service_for_url(self, text: str) -> Optional[Any]:
        if not text: return None
        
        # Lazy import to avoid circular deps
        if any(p.search(text) for p in self._compiled):
            from services.youtube_service import YoutubeService
            return YoutubeService(cookie_file=self.cookie_file)
            
        if "test.com" in text:
            # Mock Service implementation would go here (omitted for brevity)
            return None
            
        return None