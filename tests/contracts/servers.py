"""Prove Notifier's Jellyfin and Audiobookshelf calls against real servers (compose.yml).

Plex is not covered (needs a claimed account); Music Assistant stays experimental.
Exits non-zero when a server rejects the call.
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx

from app.services.notify import Notifier

JF, ABS = "http://localhost:8096", "http://localhost:13378"


def jellyfin_key(c: httpx.Client) -> str:
    c.post(f"{JF}/Startup/Configuration", json={}).raise_for_status()
    c.get(f"{JF}/Startup/User")  # the wizard must have a user before it completes
    c.post(
        f"{JF}/Startup/User", json={"Name": "ci", "Password": "ci-pass"}
    ).raise_for_status()
    c.post(f"{JF}/Startup/Complete").raise_for_status()
    auth = 'MediaBrowser Client="ci", Device="ci", DeviceId="ci", Version="1"'
    login = c.post(
        f"{JF}/Users/AuthenticateByName",
        json={"Username": "ci", "Pw": "ci-pass"},
        headers={"Authorization": auth},
    )
    login.raise_for_status()
    head = {"Authorization": f'{auth}, Token="{login.json()["AccessToken"]}"'}
    c.post(f"{JF}/Auth/Keys", params={"app": "ci"}, headers=head).raise_for_status()
    return c.get(f"{JF}/Auth/Keys", headers=head).json()["Items"][0]["AccessToken"]


def abs_token_and_library(c: httpx.Client) -> tuple[str, str]:
    c.post(
        f"{ABS}/init", json={"newRoot": {"username": "ci", "password": "ci-pass"}}
    ).raise_for_status()
    login = c.post(f"{ABS}/login", json={"username": "ci", "password": "ci-pass"})
    login.raise_for_status()
    token = login.json()["user"]["token"]
    lib = c.post(
        f"{ABS}/api/libraries",
        json={
            "name": "ci",
            "folders": [{"fullPath": "/audiobooks"}],
            "mediaType": "book",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    lib.raise_for_status()
    return token, lib.json()["id"]


async def main() -> int:
    with httpx.Client(timeout=30) as c:
        cfg = SimpleNamespace(
            PLEX_URL="",
            PLEX_TOKEN="",
            PLEX_SECTIONS={},
            JELLYFIN_URL=JF,
            JELLYFIN_API_KEY=jellyfin_key(c),
            ABS_URL=ABS,
            MUSIC_ASSISTANT_URL="",
            MUSIC_ASSISTANT_TOKEN="",
        )
        cfg.ABS_TOKEN, cfg.ABS_LIBRARY_ID = abs_token_and_library(c)
    n = Notifier(cfg)
    failed = await n.published("music", Path("/data/music/A/B/01.flac"))
    failed += await n.published("audiobook", Path("/audiobooks/A/B.m4b"))
    print("failed servers:", failed or "none")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
