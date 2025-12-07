import asyncio
from typing import Optional, Any
from utils.logger import setup_logger
from services.youtube_service import YoutubeService

logger = setup_logger()

class MockService:
    """A fake service to test the queue logic without real downloads."""
    def __init__(self):
        self.name = "MockService"

    def extract_url(self, text: str) -> Optional[str]:
        if "test.com" in text:
            return "http://test.com/video.mp4"
        return None

    async def download(self, url: str) -> dict:
        """Simulates a download by creating a dummy file."""
        logger.info("⏳ Simulating download delay (3 seconds)...")
        await asyncio.sleep(3)
        
        # Create a dummy MP4 file (10MB of zeros) to simulate content
        # We make it large enough to trigger compression logic if we want,
        # or small enough to pass. Let's make it 60MB to force compression.
        dummy_data = b'0' * (60 * 1024 * 1024) 
        
        return {
            'video_data': dummy_data,
            'title': 'Test Video',
            'description': 'This is a simulated video for queue testing.',
            'file_size_mb': 60.0
        }

class ServiceFactory:
    def __init__(self):
        """Initialize service factory with all available services."""
        self.youtube_service = YoutubeService()
    
    def get_service_for_url(self, text: str) -> Optional[Any]:
        """
        Detect service type from URL and return appropriate service.
        
        Args:
            text: Text that may contain a URL
            
        Returns:
            Service instance (YoutubeService, MockService, or None)
        """
        # Check for YouTube URLs first
        if self.youtube_service.extract_url(text):
            return self.youtube_service
        
        # Return our mock service if the URL looks like a test URL
        if "test.com" in text:
            return MockService()
        
        return None
    
    def shutdown(self) -> None:
        """
        Shutdown all services.
        
        Should be called when the bot is shutting down.
        """
        if self.youtube_service:
            self.youtube_service.shutdown()
