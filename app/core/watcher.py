import asyncio
import hashlib
import logging
import os
import time

from sqlalchemy.future import select
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.models.media import FileState, MediaItem, MediaType

EXCLUDE_PATTERNS = (".DS_Store", ".tmp", ".part")
SIDECAR_IMAGES = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
)  # covers/posters are never media (#173)


def is_excluded(path) -> bool:
    """Match the file name only: a parent directory called `x.tmp-album` must not hide its files."""
    name = os.path.basename(str(path))
    return name.lower().endswith(SIDECAR_IMAGES) or any(
        p in name for p in EXCLUDE_PATTERNS
    )


STABILITY_WINDOW = 5  # seconds size+mtime must stay unchanged (R-PIPE-3)
POLL_INTERVAL = 1  # seconds between stability passes
HASH_CHUNK = 1024 * 1024
MAX_IMPORT_ATTEMPTS = 3  # a failing import is retried this many times, then dropped


class FileChangedError(Exception):
    """The file changed while it was being hashed; the hash is not trustworthy."""


def content_hash(path: str) -> str:
    """sha256 of the file bytes, streamed (R-PIPE-2)."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _stat_signature(path: str):
    """(size, mtime) or None if the file is gone. Blocking: call via to_thread."""
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None
    return st.st_size, st.st_mtime


class DebounceHandler(FileSystemEventHandler):
    """Runs on watchdog's observer thread; hands every write to the event loop."""

    def __init__(self, queue, loop):
        self.queue = queue
        self.loop = loop

    def _enqueue(self, path):
        now = time.time()
        if self.loop is None:
            self.queue[path] = now
        else:
            self.loop.call_soon_threadsafe(self.queue.__setitem__, path, now)

    def on_created(self, event):
        if event.is_directory or is_excluded(event.src_path):
            return
        self._enqueue(event.src_path)

    def on_moved(self, event):
        if event.is_directory or is_excluded(event.dest_path):
            return
        self._enqueue(event.dest_path)


async def import_file(path, db_session_factory, logger, coordinator=None):
    """Insert one pending item for `path`; return its id, or None for a duplicate."""
    before = await asyncio.to_thread(_stat_signature, path)
    file_hash = await asyncio.to_thread(content_hash, path)
    if await asyncio.to_thread(_stat_signature, path) != before:
        raise FileChangedError(f"{path} changed while hashing")
    async with db_session_factory() as session:
        result = await session.execute(
            select(MediaItem).where(MediaItem.id == file_hash)
        )
        existing = result.scalar_one_or_none()
        if existing:
            if existing.source_path == path:
                return file_hash
            # Same content at a new path: a move, unless the old path is still there.
            if await asyncio.to_thread(os.path.exists, existing.source_path):
                logger.warning(
                    f"Duplicate content at {path} (already imported as {existing.source_path})"
                )
                return None
            existing.source_path = path
            await session.commit()
            logger.info(f"Item {file_hash} moved to {path}")
            return file_hash
        session.add(
            MediaItem(
                source_path=path,
                state=FileState.pending,
                media_type=MediaType.unknown,
                id=file_hash,
            )
        )
        await session.commit()
        logger.info(f"Inserted new file: {path}")
        if coordinator:
            await coordinator.enqueue(file_hash)
        return file_hash


class InputWatcher:
    def __init__(self, input_dir, db_session_factory, logger=None, coordinator=None):
        self.input_dir = input_dir
        self.db_session_factory = db_session_factory
        self.logger = logger or logging.getLogger("InputWatcher")
        self.processing_queue = {}
        self.loop = asyncio.get_running_loop()
        self.observer = Observer()
        self.handler = DebounceHandler(self.processing_queue, self.loop)
        self.coordinator = coordinator
        self._tasks = []

    async def startup_scan(self):
        def walk():
            return [
                os.path.join(root, f)
                for root, _, files in os.walk(self.input_dir)
                for f in files
            ]

        for path in await asyncio.to_thread(walk):
            if not is_excluded(path):
                self.processing_queue[path] = time.time()

    async def process_queue(self):
        """Insert files whose (size, mtime) stayed unchanged for STABILITY_WINDOW.

        Every queued file is checked each pass, so waiting is concurrent, not serial.
        """
        seen = {}  # path -> (signature, monotonic time it was first seen with it)
        attempts = {}  # path -> failed import count
        while True:
            for path in list(self.processing_queue):
                signature = await asyncio.to_thread(_stat_signature, path)
                if signature is None:
                    self.processing_queue.pop(path, None)
                    seen.pop(path, None)
                    attempts.pop(path, None)
                    continue
                last_signature, since = seen.get(path, (None, 0.0))
                now = time.monotonic()
                if signature != last_signature:
                    seen[path] = (signature, now)
                elif now - since >= STABILITY_WINDOW:
                    queued_at = self.processing_queue.get(path)
                    seen.pop(
                        path, None
                    )  # a retry or re-event waits out the window again
                    try:
                        await self.insert_if_new(path)
                    except Exception:
                        attempts[path] = attempts.get(path, 0) + 1
                        self.logger.exception(
                            f"Failed to import {path} (attempt {attempts[path]})"
                        )
                        if attempts[path] < MAX_IMPORT_ATTEMPTS:
                            continue  # stays queued for a retry
                    # Drop only if no new event arrived during the import.
                    if self.processing_queue.get(path) == queued_at:
                        self.processing_queue.pop(path, None)
                    attempts.pop(path, None)
            await asyncio.sleep(POLL_INTERVAL)

    async def insert_if_new(self, path):
        return await import_file(
            path, self.db_session_factory, self.logger, self.coordinator
        )

    def run(self):
        """Start watching. Non-blocking; call from the event-loop thread."""
        self.observer.schedule(self.handler, self.input_dir, recursive=True)
        self.observer.start()
        self._tasks = [
            self.loop.create_task(self.process_queue()),
            self.loop.create_task(self.startup_scan()),
        ]

    def stop(self):
        for task in self._tasks:
            task.cancel()
        self.observer.stop()
        self.observer.join()
