import os
from dotenv import load_dotenv
from typing import cast

load_dotenv()


class Config:
    """Load Telegram bot credentials from environment variables.

    Avoid hardcoding sensitive credentials in source. Provide values in a
    `.env` file or environment variables named `TELEGRAM_API_ID`,
    `TELEGRAM_API_HASH`, and `TELEGRAM_BOT_TOKEN`.
    """

    # Load from environment
    _api_id_str = os.getenv("TELEGRAM_API_ID")
    _api_hash = os.getenv("TELEGRAM_API_HASH")
    _bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

    # Validate all required credentials are present
    if not _api_id_str or not _api_hash or not _bot_token:
        raise ValueError("Missing Telegram credentials in environment. See .env.example")

    # Convert and validate API_ID
    try:
        API_ID: int = int(_api_id_str)
    except (ValueError, TypeError):
        raise ValueError(f"TELEGRAM_API_ID must be an integer, got: {_api_id_str}")

    # Assign remaining credentials (now guaranteed non-None by validation)
    API_HASH: str = cast(str, _api_hash)
    BOT_TOKEN: str = cast(str, _bot_token)
