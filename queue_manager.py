"""
Download queue management with concurrent processing control.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, Any, Set
from datetime import datetime
from enum import Enum
from utils.logger import setup_logger


logger = setup_logger()


class TaskStatus(Enum):
    PENDING = 'pending'
    DOWNLOADING = 'downloading'
    COMPRESSING = 'compressing'
    UPLOADING = 'uploading'
    COMPLETED = 'completed'
    FAILED = 'failed'


@dataclass
class DownloadTask:
    event: Any
    service: Any
    url: str
    sender_name: str
    client: Any
    added_at: datetime = field(default_factory=datetime.now)
    status: TaskStatus = TaskStatus.PENDING
    error: Optional[str] = None


class DownloadQueueManager:
    def __init__(self, max_concurrent: int = 2):
        self.max_concurrent = max_concurrent
        self.queue: asyncio.Queue[DownloadTask] = asyncio.Queue()
        self.active_tasks: Set[DownloadTask] = set()
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._client: Optional[Any] = None
        
        self.stats = {
            'total_queued': 0, 'total_processed': 0, 'total_failed': 0,
            'total_compressed': 0, 'active': 0, 'currently_downloading': 0,
            'currently_compressing': 0, 'currently_uploading': 0,
        }
    
    async def start(self, client: Any) -> None:
        self._client = client
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(i), name=f"queue_worker_{i}")
            for i in range(self.max_concurrent)
        ]
        logger.info(f"Queue manager started with {self.max_concurrent} workers")
    
    async def stop(self) -> None:
        self._running = False
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Queue manager stopped")
    
    async def add_to_queue(self, event, service, url, sender_name, client) -> None:
        task = DownloadTask(event, service, url, sender_name, client)
        await self.queue.put(task)
        self.stats['total_queued'] += 1
        
        queue_size = self.queue.qsize()
        active_count = len(self.active_tasks)
        
        logger.info(f"Task queued from {sender_name}. Queue: {queue_size}, Active: {active_count}")
        
        if queue_size > 1 or active_count >= self.max_concurrent:
            await self._notify_queue_position(event, queue_size, active_count)
    
    async def _notify_queue_position(self, event, queue_size, active_count) -> None:
        msg = f"⏳ Added to queue\n📊 Position: {queue_size}\n⚙️ Active: {active_count}/{self.max_concurrent}"
        try:
            await event.reply(msg)
        except Exception:
            pass
    
    async def _worker(self, worker_id: int) -> None:
        logger.info(f"Worker {worker_id} started")
        while self._running:
            try:
                try:
                    task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                async with self.semaphore:
                    await self._process_task_safely(task, worker_id)
                    self.queue.task_done()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
    
    async def _process_task_safely(self, task, worker_id) -> None:
        self.active_tasks.add(task)
        self.stats['active'] = len(self.active_tasks)
        logger.info(f"Worker {worker_id} processing task")
        
        try:
            from processors.media_processor import MediaProcessor
            processor = MediaProcessor(task.client, self)
            await processor.process(task, worker_id)
            task.status = TaskStatus.COMPLETED
            self.stats['total_processed'] += 1
        except Exception as e:
            task.status = TaskStatus.FAILED
            logger.error(f"Task failed: {e}")
            try:
                await task.event.reply(f"❌ Failed: {e}")
            except: pass
        finally:
            self.active_tasks.discard(task)
            self.stats['active'] = len(self.active_tasks)
            logger.info(f"Worker {worker_id} finished")
    
    def update_status(self, status_type: str, increment: int) -> None:
        key = f'currently_{status_type}'
        if key in self.stats:
            self.stats[key] = max(0, self.stats[key] + increment)
