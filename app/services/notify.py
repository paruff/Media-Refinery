"""R-NOTIFY: optional, independent, non-fatal rescan calls after PUBLISH.

Rescans are coalesced: an album or a season triggers one folder rescan per server (and one
library-wide scan for Audiobookshelf / Music Assistant), sent once publishing goes quiet.
"""

import asyncio
import contextlib
import logging
from collections.abc import Iterable
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.redact import http_error_summary

log = logging.getLogger("notify")

QUIET_SECONDS = 10.0  # publishes closer together than this share one rescan


def map_path(path: str, mapping: dict[str, str]) -> str:
    """Rewrite a container path to the media server's view of it (longest prefix wins)."""
    for prefix in sorted(mapping, key=len, reverse=True):
        base = prefix.rstrip("/")
        if path == base or path.startswith(base + "/"):
            return mapping[prefix].rstrip("/") + path[len(base) :]
    return path


class Notifier:
    def __init__(
        self,
        cfg=settings,
        client: httpx.AsyncClient | None = None,
        quiet: float = QUIET_SECONDS,
    ):
        self.cfg = cfg
        self.client = client or httpx.AsyncClient(timeout=10)
        self.quiet = quiet
        self._pending: dict[str, set[Path]] = {}  # media type -> published files
        self._timer: asyncio.Task | None = None

    # ---- coalescing ---------------------------------------------------------
    def schedule(self, media_type: str, dest: Path) -> None:
        """Remember a published file; the rescans go out once publishing has been quiet."""
        self._pending.setdefault(str(media_type), set()).add(dest)
        if self._timer is not None:
            self._timer.cancel()
        self._timer = asyncio.get_running_loop().create_task(self._after_quiet())

    async def _after_quiet(self) -> None:
        await asyncio.sleep(self.quiet)
        await self.flush()

    async def flush(self) -> list[str]:
        """Send everything pending now; return the names of servers that failed."""
        if self._timer is not None and self._timer is not asyncio.current_task():
            self._timer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._timer
        pending, self._pending = self._pending, {}
        failed: list[str] = []
        for media_type, dests in pending.items():
            failed += await self.published_batch(media_type, dests)
        return failed

    # ---- sending ------------------------------------------------------------
    async def published(self, media_type: str, dest: Path) -> list[str]:
        return await self.published_batch(media_type, [dest])

    async def published_batch(
        self, media_type: str, dests: Iterable[Path]
    ) -> list[str]:
        """One rescan per distinct folder for Plex/Jellyfin, one scan for the others.
        Returns the names of servers that failed (each only warns)."""
        c, mt = self.cfg, str(media_type)
        mapping = getattr(c, "NOTIFY_PATH_MAP", None) or {}
        folders = sorted({map_path(str(d.parent), mapping) for d in dests})
        calls = []  # (server, folder, request kwargs)
        for folder in folders:
            if c.PLEX_URL and mt in c.PLEX_SECTIONS:
                calls.append(
                    (
                        "plex",
                        folder,
                        {
                            "method": "GET",
                            "url": f"{c.PLEX_URL.rstrip('/')}/library/sections/{c.PLEX_SECTIONS[mt]}/refresh",
                            "params": {"path": folder},
                            "headers": {"X-Plex-Token": c.PLEX_TOKEN},
                        },
                    )
                )
            if c.JELLYFIN_URL and mt in ("movie", "series", "music"):
                calls.append(
                    (
                        "jellyfin",
                        folder,
                        {
                            "method": "POST",
                            "url": f"{c.JELLYFIN_URL.rstrip('/')}/Library/Media/Updated",
                            "json": {
                                "Updates": [{"Path": folder, "UpdateType": "Created"}]
                            },
                            "headers": {"X-Emby-Token": c.JELLYFIN_API_KEY},
                        },
                    )
                )
        if folders and c.ABS_URL and c.ABS_LIBRARY_ID and mt == "audiobook":
            calls.append(
                (
                    "audiobookshelf",
                    "",
                    {
                        "method": "POST",
                        "url": f"{c.ABS_URL.rstrip('/')}/api/libraries/{c.ABS_LIBRARY_ID}/scan",
                        "headers": {"Authorization": f"Bearer {c.ABS_TOKEN}"},
                    },
                )
            )
        if folders and c.MUSIC_ASSISTANT_URL and mt == "music":
            calls.append(
                (
                    "music_assistant",
                    "",
                    {
                        "method": "POST",
                        "url": f"{c.MUSIC_ASSISTANT_URL.rstrip('/')}/api",
                        "json": {"command": "music/sync", "args": {}},
                        "headers": {
                            "Authorization": f"Bearer {c.MUSIC_ASSISTANT_TOKEN}"
                        },
                    },
                )
            )
        failed: list[str] = []
        for server, folder, req in calls:
            try:
                (await self.client.request(**req)).raise_for_status()
            except Exception as e:  # any failure is only a warning
                log.warning(
                    "%s rescan failed for %s: %s", server, folder, http_error_summary(e)
                )
                if server not in failed:
                    failed.append(server)
        return failed
