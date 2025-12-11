import asyncio
import traceback  # Import traceback
from telethon import TelegramClient, events
from config import Config
from queue_manager import DownloadQueueManager
from services.service_factory import ServiceFactory
from utils.logger import setup_logger
from utils.cache import init_cache

logger = setup_logger()

class MediaFixBot:
    def __init__(self):
        self.config = Config()
        client = TelegramClient(
            'media_fix_bot', self.config.API_ID, self.config.API_HASH
        )
        client.start(bot_token=self.config.BOT_TOKEN)
        self.client = client

        self.queue_manager = DownloadQueueManager(max_concurrent=2)
        self.service_factory = ServiceFactory()

    async def start(self) -> None:
        init_cache()
        logger.info("Cache database initialized.")

        await self.queue_manager.start(self.client)
        
        @self.client.on(events.NewMessage(incoming=True))
        async def handle_message(event):
            try:
                logger.info(f"Received message: {event.message.text}")
                if not event.message.text: return
                
                service = self.service_factory.get_service_for_url(event.message.text)
                if service:
                    url = service.extract_url(event.message.text)
                    if url:
                        logger.info(f"URL detected: {url} (Service: {service.name})")
                        sender = await event.get_sender()
                        name = sender.first_name if sender else "Unknown"
                        await self.queue_manager.add_to_queue(event, service, url, name, self.client)
                    else:
                        logger.warning(f"Service '{service.name}' was selected, but could not extract a valid URL from message: {event.message.text}")
            
            except ValueError as e:
                logger.warning(f"Validation error: {e}")
            except Exception:
                logger.error(f"An unexpected error occurred: {traceback.format_exc()}")

        logger.info("Bot started! Send a link to process.")
        return

if __name__ == '__main__':
    bot = MediaFixBot()
    bot.client.loop.run_until_complete(bot.start())
    bot.client.run_until_disconnected()