import asyncio
import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.media import MediaItem, FileState, MediaType
import hashlib
import logging

EXCLUDE_PATTERNS = ('.DS_Store', '.tmp', '.part')
STABILITY_WINDOW = 5  # seconds

class DebounceHandler(FileSystemEventHandler):
    def __init__(self, queue, loop):
        self.queue = queue
        self.loop = loop

    def on_created(self, event):
        if event.is_directory or any(p in event.src_path for p in EXCLUDE_PATTERNS):
            return
        self.queue[event.src_path] = time.time()

    def on_moved(self, event):
        if event.is_directory or any(p in event.dest_path for p in EXCLUDE_PATTERNS):
            return
        self.queue[event.dest_path] = time.time()

class InputWatcher:
    def __init__(self, input_dir, db_session_factory, logger=None, coordinator=None):
        self.input_dir = input_dir
        self.db_session_factory = db_session_factory
        self.logger = logger or logging.getLogger("InputWatcher")
        self.processing_queue = {}
        self.loop = asyncio.get_event_loop()
        self.observer = Observer()
        self.handler = DebounceHandler(self.processing_queue, self.loop)
        self.coordinator = coordinator

    async def startup_scan(self):
        for root, _, files in os.walk(self.input_dir):
            for f in files:
                path = os.path.join(root, f)
                if any(p in path for p in EXCLUDE_PATTERNS):
                    continue
                self.processing_queue[path] = time.time()

    async def process_queue(self):
        while True:
            to_remove = []
            for path, last_seen in list(self.processing_queue.items()):
                if not os.path.exists(path):
                    to_remove.append(path)
                    continue
                stat = os.stat(path)
                size = stat.st_size
                mtime = stat.st_mtime
                await asyncio.sleep(STABILITY_WINDOW)
                stat2 = os.stat(path)
                if stat2.st_size == size and stat2.st_mtime == mtime:
                    await self.insert_if_new(path)
                    to_remove.append(path)
            for path in to_remove:
                self.processing_queue.pop(path, None)
            await asyncio.sleep(1)

    async def insert_if_new(self, path):
        async with self.db_session_factory() as session:
            exists = await session.execute(select(MediaItem).where(MediaItem.source_path == path))
            if exists.scalar_one_or_none():
                return
            file_hash = hashlib.sha256(path.encode()).hexdigest()
            item = MediaItem(
                source_path=path,
                state=FileState.pending,
                media_type=MediaType.unknown,
                id=file_hash
            )
            session.add(item)
            await session.commit()
            self.logger.info(f"Inserted new file: {path}")
            if self.coordinator:
                await self.coordinator.enqueue(file_hash)

    def run(self):
        self.observer.schedule(self.handler, self.input_dir, recursive=True)
        self.observer.start()
        self.loop.create_task(self.process_queue())
        self.loop.create_task(self.startup_scan())

    def stop(self):
        self.observer.stop()
        self.observer.join()
