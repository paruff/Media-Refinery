"""B4 (#102/#103): atomic approve/reject/retry, honest 409 reasons, signed expiring UI sessions."""

import asyncio
import re

import httpx
import pytest
import pytest_asyncio
from typer.testing import CliRunner

from app.api import auth
from app.cli import app as cli_app
from app.core.config import settings
from app.core.database import get_async_session
from app.core.orchestrator import PipelineOrchestrator
from app.core.watcher import is_excluded
from app.main import app
from app.models.media import FileState, MediaItem, MediaType, NormalizationPlan
from tests.pipeline_helpers import make_config, make_session_factory

pytestmark = pytest.mark.unit
TOKEN = "s3cret"
HX = {"HX-Request": "true"}


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "API_HOST", "0.0.0.0")  # noqa: S104
    monkeypatch.setattr(settings, "API_TOKEN", TOKEN)
    engine, factory = await make_session_factory(tmp_path)

    async def session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_async_session] = session
    app.state.orchestrator = PipelineOrchestrator(factory, make_config(tmp_path))
    app.state.factory = factory
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    ) as c:
        yield c
    app.dependency_overrides.clear()
    del app.state.orchestrator
    await engine.dispose()


async def _seed(name, state, source=None):
    async with app.state.factory() as s:
        s.add(
            MediaItem(
                id=name,
                source_path=source or f"/in/{name}",
                state=state,
                media_type=MediaType.music,
            )
        )
        s.add(
            NormalizationPlan(
                media_item_id=name,
                target_path=f"/lib/{name}",
                original_hash=name,
                ffmpeg_args=["-c", "copy"],
            )
        )
        await s.commit()


async def _state(name):
    async with app.state.factory() as s:
        return (await s.get(MediaItem, name)).state


# ---- concurrency (#102) ---------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["approve", "reject"])
async def test_concurrent_transitions_win_exactly_once(client, action):
    await _seed("a.mp3", FileState.planned)
    orch = app.state.orchestrator
    results = await asyncio.gather(*(getattr(orch, action)("a.mp3") for _ in range(8)))
    assert results.count(True) == 1


@pytest.mark.asyncio
async def test_approve_and_reject_race_has_one_winner(client):
    await _seed("a.mp3", FileState.planned)
    orch = app.state.orchestrator
    results = await asyncio.gather(orch.approve("a.mp3"), orch.reject("a.mp3"))
    assert sorted(results) == [False, True]
    assert (await _state("a.mp3")) in (FileState.approved, FileState.quarantined)


@pytest.mark.asyncio
async def test_concurrent_retry_wins_once(client, tmp_path):
    src = tmp_path / "a.mp3"
    src.write_bytes(b"x")
    await _seed("a.mp3", FileState.error, str(src))
    orch = app.state.orchestrator
    results = await asyncio.gather(*(orch.retry("a.mp3") for _ in range(8)))
    assert results.count(True) == 1 and (await _state("a.mp3")) == FileState.pending


# ---- 409 reasons (#102, #103) ---------------------------------------------
@pytest.mark.asyncio
async def test_retry_409_names_missing_source_not_just_state(client):
    await _seed("gone.mp3", FileState.error, "/definitely/not/here.mp3")
    r = await client.post(
        "/api/v1/items/gone.mp3/retry",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 409 and "source file is missing" in r.json()["detail"]


@pytest.mark.asyncio
async def test_ui_retry_notice_says_source_missing_not_quarantined(client):
    await _seed("gone.mp3", FileState.quarantined, "/definitely/not/here.mp3")
    cookies = await _login(client)
    r = await client.post("/ui/items/gone.mp3/retry", cookies=cookies, headers=HX)
    assert "source file is missing" in r.text and "it is quarantined" not in r.text


# ---- EXCLUDE_PATTERNS match the file name, not parent dirs (#102) ---------
def test_exclude_patterns_ignore_parent_directory_names():
    assert not is_excluded("/music/.tmp-album/song.mp3")
    assert not is_excluded("/music/Best.part.1/song.mp3")
    assert is_excluded("/music/a/song.mp3.part") and is_excluded("/m/.DS_Store")


# ---- CLI approve needs an explicit flag for review-flagged items (#102) ----
def test_cli_approve_has_include_review_flag():
    out = CliRunner().invoke(cli_app, ["approve", "--help"]).output
    # CI forces colour; rich then wraps pieces of the option name in separate ANSI codes
    assert "--include-review" in re.sub(r"\x1b\[[0-9;]*m", "", out)


# ---- signed, expiring UI session (#103) -----------------------------------
async def _login(client):
    r = await client.post("/ui/login", data={"token": TOKEN})
    assert r.status_code == 303
    return {"mr_token": r.cookies["mr_token"]}


@pytest.mark.asyncio
async def test_cookie_is_a_signed_session_not_the_raw_token(client):
    cookies = await _login(client)
    assert TOKEN not in cookies["mr_token"]
    assert (await client.get("/ui/queue", cookies=cookies)).status_code == 200


@pytest.mark.asyncio
async def test_raw_token_in_cookie_is_rejected(client):
    r = await client.get("/ui/queue", cookies={"mr_token": TOKEN})
    assert r.status_code == 303


@pytest.mark.asyncio
async def test_session_expires_after_max_age(client, monkeypatch):
    cookies = await _login(client)
    real = auth.time.time()
    monkeypatch.setattr(auth.time, "time", lambda: real + auth.SESSION_MAX_AGE - 5)
    assert (await client.get("/ui/queue", cookies=cookies)).status_code == 200
    monkeypatch.setattr(auth.time, "time", lambda: real + auth.SESSION_MAX_AGE + 5)
    assert (await client.get("/ui/queue", cookies=cookies)).status_code == 303


@pytest.mark.asyncio
async def test_tampered_or_rotated_session_is_rejected(client, monkeypatch):
    cookies = await _login(client)
    issued, sig = cookies["mr_token"].split(".")
    forged = {"mr_token": f"{int(issued) + 99999}.{sig}"}
    assert (await client.get("/ui/queue", cookies=forged)).status_code == 303
    monkeypatch.setattr(settings, "API_TOKEN", "rotated")
    assert (await client.get("/ui/queue", cookies=cookies)).status_code == 303


@pytest.mark.asyncio
async def test_garbage_cookie_values_do_not_500(client):
    for bad in ("", ".", "x.y", "9" * 40 + ".00"):
        r = await client.get("/ui/queue", cookies={"mr_token": bad})
        assert r.status_code == 303
    raw = {"Cookie": "mr_token=1.é".encode("latin-1")}
    assert (await client.get("/ui/queue", headers=raw)).status_code == 303


@pytest.mark.asyncio
async def test_bearer_token_still_works_for_the_api(client):
    r = await client.get("/api/v1/items", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_expired_htmx_poll_gets_hx_redirect_not_the_login_page(client):
    r = await client.get("/ui/queue", headers=HX)
    assert r.status_code == 401 and r.headers["hx-redirect"] == "/ui/login"
    plain = await client.get("/ui/queue")
    assert plain.status_code == 303 and "hx-redirect" not in plain.headers
