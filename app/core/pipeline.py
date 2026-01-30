import asyncio
import logging
from app.models.media import MediaItem, FileState
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from app.core.scanner import ScannerService

MAX_CONCURRENT_SCANS = 2

class PipelineCoordinator:
    def __init__(self, db_session_factory, logger=None):
        self.db_session_factory = db_session_factory
        self.logger = logger or logging.getLogger("PipelineCoordinator")
        self.queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCANS)
        self.running = False
        self.scanner = ScannerService(db_session_factory, logger=self.logger)

    async def start(self):
        self.running = True
        asyncio.create_task(self.worker_loop())

    async def stop(self):
        self.running = False

    async def enqueue(self, media_id):
        await self.queue.put(media_id)

    async def worker_loop(self):
        while self.running:
            media_id = await self.queue.get()
            async with self.semaphore:
                await self.process(media_id)
            self.queue.task_done()

    async def process(self, media_id):
        async with self.db_session_factory() as session:
            result = await session.execute(select(MediaItem).where(MediaItem.id == media_id))
            item = result.scalar_one_or_none()
            if not item:
                self.logger.error(f"MediaItem {media_id} not found.")
                return
            if item.state != FileState.pending:
                self.logger.info(f"MediaItem {media_id} not pending, skipping.")
                return
            # Transition to scanning
            item.state = FileState.scanning
            item.updated_at = datetime.utcnow()
            await session.commit()
            self.logger.info(f"MediaItem {media_id} state: PENDING -> SCANNING")
        try:
            await self.scanner.run(media_id)
        except Exception as e:
            async with self.db_session_factory() as session:
                result = await session.execute(select(MediaItem).where(MediaItem.id == media_id))
                item = result.scalar_one_or_none()
                if item:
                    item.state = FileState.error
                    item.error_log = str(e)
                    await session.commit()
            self.logger.error(f"Scanner failed for {media_id}: {e}")

# Example MediaScanner stub
class MediaScanner:
    async def run(self, media_id):
        # Simulate scanning
        await asyncio.sleep(1)
        print(f"Scanned media {media_id}")
