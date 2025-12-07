import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Load Telegram bot credentials from environment variables."""
    API_ID = os.getenv("TELEGRAM_API_ID")
    API_HASH = os.getenv("TELEGRAM_API_HASH")
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # Validation
    if not all([API_ID, API_HASH, BOT_TOKEN]):
        raise ValueError("Missing Telegram credentials in .env file. See .env.example")
