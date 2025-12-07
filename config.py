import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Load Telegram bot credentials from environment variables.

    Avoid hardcoding sensitive credentials in source. Provide values in a
    `.env` file or environment variables named `TELEGRAM_API_ID`,
    `TELEGRAM_API_HASH`, and `TELEGRAM_BOT_TOKEN`.
    """

    API_ID = os.getenv("TELEGRAM_API_ID")
    API_HASH = os.getenv("TELEGRAM_API_HASH")
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    if not all([API_ID, API_HASH, BOT_TOKEN]):
        raise ValueError("Missing Telegram credentials in environment. See .env.example")
