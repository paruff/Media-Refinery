"""R-NOTIFY: optional, independent, non-fatal rescan calls after PUBLISH."""

import logging
from pathlib import Path

import httpx

from app.core.config import settings

log = logging.getLogger("notify")


class Notifier:
    def __init__(self, cfg=settings, client: httpx.AsyncClient | None = None):
        self.cfg = cfg
        self.client = client or httpx.AsyncClient(timeout=10)

    async def published(self, media_type: str, dest: Path) -> list[str]:
        """Fire every configured server; return names that failed (each only warns)."""
        c, mt, folder = self.cfg, str(media_type), str(dest.parent)
        calls = []  # (server, request kwargs)
        if c.PLEX_URL and mt in c.PLEX_SECTIONS:
            calls.append(
                (
                    "plex",
                    {
                        "method": "GET",
                        "url": f"{c.PLEX_URL}/library/sections/{c.PLEX_SECTIONS[mt]}/refresh",
                        "params": {"path": folder},
                        "headers": {"X-Plex-Token": c.PLEX_TOKEN},
                    },
                )
            )
        if c.JELLYFIN_URL and mt in ("movie", "series", "music"):
            calls.append(
                (
                    "jellyfin",
                    {
                        "method": "POST",
                        "url": f"{c.JELLYFIN_URL}/Library/Media/Updated",
                        "json": {
                            "Updates": [{"Path": folder, "UpdateType": "Created"}]
                        },
                        "headers": {"X-Emby-Token": c.JELLYFIN_API_KEY},
                    },
                )
            )
        if c.ABS_URL and c.ABS_LIBRARY_ID and mt == "audiobook":
            calls.append(
                (
                    "audiobookshelf",
                    {
                        "method": "POST",
                        "url": f"{c.ABS_URL}/api/libraries/{c.ABS_LIBRARY_ID}/scan",
                        "headers": {"Authorization": f"Bearer {c.ABS_TOKEN}"},
                    },
                )
            )
        if c.MUSIC_ASSISTANT_URL and mt == "music":
            calls.append(
                (
                    "music_assistant",
                    {
                        "method": "POST",
                        "url": f"{c.MUSIC_ASSISTANT_URL}/api",
                        "json": {"command": "music/sync", "args": {}},
                        "headers": {
                            "Authorization": f"Bearer {c.MUSIC_ASSISTANT_TOKEN}"
                        },
                    },
                )
            )
        failed = []
        for server, req in calls:
            try:
                (await self.client.request(**req)).raise_for_status()
            except Exception as e:  # any failure is only a warning
                log.warning("%s rescan failed for %s: %s", server, folder, e)
                failed.append(server)
        return failed
