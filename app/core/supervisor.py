import asyncio
import logging
import os
import signal
import sys
import shutil
from datetime import datetime
from app.core.orchestrator import PipelineOrchestrator
from app.services.reporting_service import ReportingService


class DaemonSupervisor:
    def __init__(
        self,
        orchestrator: PipelineOrchestrator,
        reporting_service: ReportingService,
        staging_dir: str,
        output_dir: str,
        logger=None,
    ):
        self.orchestrator = orchestrator
        self.reporting_service = reporting_service
        self.staging_dir = staging_dir
        self.output_dir = output_dir
        self.logger = logger or logging.getLogger("DaemonSupervisor")
        self._shutdown = asyncio.Event()
        self._backoff = 1
        self._max_backoff = 300
        self._heartbeat_interval = 3600  # 60 minutes
        self._last_heartbeat = datetime.now(datetime.UTC)

    async def run(self):
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(
                    sig, lambda: asyncio.create_task(self.shutdown())
                )
            except NotImplementedError:
                # Windows compatibility
                signal.signal(sig, lambda s, f: asyncio.create_task(self.shutdown()))
        self.logger.info("DaemonSupervisor started.")
        while not self._shutdown.is_set():
            try:
                await self._health_checks()
                await self.orchestrator.run_forever()
                self._backoff = 1
            except Exception as e:
                self.logger.error(f"Top-level exception: {e}", exc_info=True)
                with open("crash.log", "a") as f:
                    f.write(f"{datetime.utcnow().isoformat()}\n{e}\n")
                await self._backoff_wait()
            await self._maybe_heartbeat()
        self.logger.info("DaemonSupervisor exiting cleanly.")
        sys.exit(0)

    async def shutdown(self):
        self.logger.info("Shutdown signal received. Initiating graceful shutdown.")
        self._shutdown.set()
        # Let orchestrator finish non-FFMPEG tasks, signal FFMPEG to wrap up
        self.orchestrator.running = False
        # Optionally: signal FFMPEG processes to checkpoint/exit

    async def _backoff_wait(self):
        wait = min(self._backoff, self._max_backoff)
        self.logger.warning(f"Backing off for {wait} seconds due to error.")
        await asyncio.sleep(wait)
        self._backoff = min(self._backoff * 2, self._max_backoff)

    async def _health_checks(self):
        for path in [self.staging_dir, self.output_dir]:
            if not os.path.exists(path):
                self.logger.critical(f"Critical: Path unreachable: {path}")
                await self._backoff_wait()
                return
            total, used, free = shutil.disk_usage(path)
            percent_free = free / total * 100
            if percent_free < 5:
                self.logger.critical(
                    f"Critical: Disk Full at {path} ({percent_free:.2f}% free). Pausing orchestrator."
                )
                self.orchestrator.running = False
                await self._backoff_wait()
                return
        self.orchestrator.running = True

    async def _maybe_heartbeat(self):
        now = datetime.utcnow()
        if (now - self._last_heartbeat).total_seconds() > self._heartbeat_interval:
            summary = await self.reporting_service.get_summary()
            self.logger.info(f"Daemon Heartbeat: {summary.json(indent=2)}")
            self._last_heartbeat = now
