# Telegram Video Download Bot

A Telegram bot that downloads videos from various sources and processes them. Standalone project separated from SpellyBot.

## Features

- Download videos from multiple sources (YouTube, etc.)
- Queue management with concurrent processing
- Video compression
- Asynchronous message handling via Telethon

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/paulohpb/telegram_videodownload_bot.git
cd telegram_videodownload_bot
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` and fill in your Telegram credentials:

```bash
cp .env.example .env
```

Edit `.env` with:
```env
TELEGRAM_API_ID=your_api_id_here
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 5. (Optional) Configure Cookies

For downloading age-restricted or private content from sources like YouTube, you may need to provide browser cookies.

1.  Create a file named `cookies.txt` in the root directory.
2.  Install a browser extension that can export cookies in the Netscape format (e.g., "Get cookies.txt" for Chrome).
3.  Export your cookies for the relevant sites (e.g., `youtube.com`) and paste the content into the `cookies.txt` file.

The bot will automatically use this file if it exists.

### 6. Run the bot
```bash
python main.py
```

## Getting Telegram Credentials

1. Go to https://my.telegram.org
2. Log in with your phone number
3. Click "API development tools"
4. Create an app (if you haven't already)
5. Copy your **API ID** and **API Hash**
6. Create a bot via [@BotFather](https://t.me/botfather) to get your **BOT_TOKEN**

## Project Structure

```
.
├── main.py                 # Entry point
├── config.py              # Configuration management
├── queue_manager.py       # Task queue and concurrent processing
├── services/              # Service implementations
│   └── service_factory.py
├── processors/            # Media processing modules
├── utils/                 # Utility functions
│   ├── logger.py
│   └── video_compressor.py
├── requirements.txt       # Python dependencies
└── .env.example          # Environment variable template
```

## Architecture

- **TelegramClient**: Handles incoming messages and bot lifecycle
- **DownloadQueueManager**: Manages concurrent downloads with configurable worker limits
- **ServiceFactory**: Routes URLs to appropriate processors
- **VideoProcessor**: Handles video compression and processing

## Contributing

Feel free to submit issues and pull requests!

## License

MIT
