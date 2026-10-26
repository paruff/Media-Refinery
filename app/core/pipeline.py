import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from sqlalchemy.future import select

from app.core.scanner import ScannerService
from app.models.media import FileState, MediaItem

MAX_CONCURRENT_SCANS = 2


class PipelineCoordinator:
    def __init__(self, db_session_factory, logger=None):
        self.db_session_factory = db_session_factory
        self.logger = logger or logging.getLogger("PipelineCoordinator")
        self.queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCANS)
        self.running = False
        self.scanner = ScannerService(db_session_factory, logger=self.logger)
        self._worker: asyncio.Task | None = None

    async def start(self):
        self.running = True
        self._worker = asyncio.create_task(self.worker_loop())

    async def stop(self):
        self.running = False
        if self._worker:
            self._worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker
            self._worker = None

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
            result = await session.execute(
                select(MediaItem).where(MediaItem.id == media_id)
            )
            item = result.scalar_one_or_none()
            if not item:
                self.logger.error(f"MediaItem {media_id} not found.")
                return
            if item.state != FileState.pending:
                self.logger.info(f"MediaItem {media_id} not pending, skipping.")
                return
            # Transition to scanning
            item.state = FileState.scanning
            item.updated_at = datetime.now(UTC)
            await session.commit()
            self.logger.info(f"MediaItem {media_id} state: PENDING -> SCANNING")
        try:
            await self.scanner.run(media_id)
        except Exception as e:
            async with self.db_session_factory() as session:
                result = await session.execute(
                    select(MediaItem).where(MediaItem.id == media_id)
                )
                item = result.scalar_one_or_none()
                if item:
                    item.state = FileState.error
                    item.error_log = str(e)
                    await session.commit()
            self.logger.error(f"Scanner failed for {media_id}: {e}")
