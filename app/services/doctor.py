"""`refinery doctor`: first-run preflight. Nothing is written and nothing is modified."""

import asyncio
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.core.config import Settings

TOOLS = {  # tool -> media types that need it ("" = always)
    "ffmpeg": "",
    "ffprobe": "",
    "fpcalc": "music",
    "flac": "music",
    "ebook-convert": "ebook",
    "calibredb": "ebook",
}
# (label, URL setting, credential setting, path probed on the server)
SERVERS = (
    ("plex", "PLEX_URL", "PLEX_TOKEN", "/identity"),
    ("jellyfin", "JELLYFIN_URL", "JELLYFIN_API_KEY", "/System/Info/Public"),
    ("audiobookshelf", "ABS_URL", "ABS_TOKEN", "/ping"),
    ("music-assistant", "MUSIC_ASSISTANT_URL", "MUSIC_ASSISTANT_TOKEN", "/"),
)
# key setting -> (media type that benefits, what is lost without it)
KEYS = {
    "TMDB_API_KEY": ("movie", "movie titles come from file names only"),
    "TVDB_API_KEY": ("series", "TV metadata is unavailable"),
    "ACOUSTID_API_KEY": ("music", "untagged music cannot be identified"),
}


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # "ok" | "warn" | "fail"
    detail: str = ""


def is_writable(path: Path) -> bool:
    """True if `path` exists and is writable, or can be created under a writable parent."""
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return os.access(probe, os.W_OK)


async def _server(label, url, cred, probe, client) -> Check:
    try:
        r = await client.get(url.rstrip("/") + probe)
    except httpx.HTTPError as e:
        return Check(
            f"server {label}", "fail", f"{url} unreachable: {type(e).__name__}"
        )
    ok = r.status_code < 500
    detail = f"{url} answered {r.status_code}" + ("" if cred else "; no token set")
    return Check(
        f"server {label}", "ok" if ok and cred else "warn" if ok else "fail", detail
    )


async def run_checks(cfg: Settings) -> list[Check]:
    enabled = set(cfg.ENABLED_TYPES)
    checks = []
    for tool, kind in TOOLS.items():
        if kind and kind not in enabled:
            continue
        found = shutil.which(tool)
        checks.append(
            Check(f"tool {tool}", "ok" if found else "fail", found or "not on PATH")
        )
    dirs = {
        "INPUT_DIR": cfg.INPUT_DIR, "WORK_DIR": cfg.WORK_DIR, "ARCHIVE_DIR": cfg.ARCHIVE_DIR,
        "QUARANTINE_DIR": cfg.QUARANTINE_DIR, "MUSIC_ROOT": cfg.MUSIC_ROOT,
        "MOVIES_ROOT": cfg.MOVIES_ROOT, "TV_ROOT": cfg.TV_ROOT,
        "AUDIOBOOKS_ROOT": cfg.AUDIOBOOKS_ROOT, "CALIBRE_LIBRARY": cfg.CALIBRE_LIBRARY,
    }  # fmt: skip
    for name, d in dirs.items():
        ok = await asyncio.to_thread(is_writable, Path(d))
        checks.append(Check(f"path {name}", "ok" if ok else "fail", d))
    for key, (kind, lost) in KEYS.items():
        if kind in enabled:
            has = bool(getattr(cfg, key))
            checks.append(
                Check(f"key {key}", "ok" if has else "warn", "set" if has else lost)
            )
    async with httpx.AsyncClient(timeout=5) as client:
        checks += await asyncio.gather(
            *(
                _server(label, url, getattr(cfg, cred), probe, client)
                for label, url_key, cred, probe in SERVERS
                if (url := getattr(cfg, url_key))
            )
        )
    return checks
