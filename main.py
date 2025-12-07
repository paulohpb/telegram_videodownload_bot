import asyncio
import signal
from telethon import TelegramClient, events
from config import Config
from queue_manager import DownloadQueueManager
from services.service_factory import ServiceFactory
from utils.logger import setup_logger
from utils.video_compressor import shutdown_executor

logger = setup_logger()


class MediaFixBot:
    def __init__(self):
        self.config = Config()
        # Connect to Telegram
        # API_ID may be stored as a string in the environment; ensure int()
        client = TelegramClient(
            'media_fix_bot', int(self.config.API_ID), str(self.config.API_HASH)
        )
        # Start the client as a bot using the provided token
        client.start(bot_token=self.config.BOT_TOKEN)
        self.client = client

        self.queue_manager = DownloadQueueManager(max_concurrent=2)
        self.service_factory = ServiceFactory()
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        await self.queue_manager.start(self.client)
        
        @self.client.on(events.NewMessage(incoming=True))
        async def handle_message(event):
            try:
                if not event.message.text: return
                
                # Check if service can handle this URL
                service = self.service_factory.get_service_for_url(event.message.text)
                if service:
                    # Extract the actual URL from the message
                    url = service.extract_url(event.message.text)
                    if url:
                        logger.info(f"URL detected: {url} (Service: {service.name})")
                        sender = await event.get_sender()
                        name = sender.first_name if sender else "Unknown"
                        await self.queue_manager.add_to_queue(event, service, url, name, self.client)
            except Exception as e:
                logger.error(f"Error: {e}")

        logger.info("Bot started! Send a YouTube link or 'http://test.com/video' to trigger a job.")
        # Do not await a non-awaitable run_until_disconnected() here.
        # The caller runs this synchronously after starting the coroutine.
        return

if __name__ == '__main__':
    bot = MediaFixBot()
    # Start async setup (handlers, queue manager, etc.)
    bot.client.loop.run_until_complete(bot.start())
    # Block the thread until the client disconnects (synchronous)
    bot.client.run_until_disconnected()
