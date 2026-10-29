"""#92/#93/#94: web UI auth + CSRF behaviour, security headers/CSP, honest bulk-action results."""

import httpx
import pytest
import pytest_asyncio

from app.core.config import settings
from app.core.database import get_async_session
from app.core.orchestrator import PipelineOrchestrator
from app.main import app
from app.models.media import (
    FileState,
    MediaItem,
    MediaType,
    NormalizationPlan,
    VerificationRecord,
)
from tests.pipeline_helpers import make_config, make_session_factory

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]
TOKEN = "s3cret"
HX = {"HX-Request": "true"}


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "API_HOST", "0.0.0.0")  # noqa: S104
    monkeypatch.setattr(settings, "API_TOKEN", TOKEN)
    cfg = make_config(tmp_path)
    engine, factory = await make_session_factory(tmp_path)

    async def session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_async_session] = session
    app.state.orchestrator = PipelineOrchestrator(factory, cfg)
    app.state.factory = factory
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c
    app.dependency_overrides.clear()
    del app.state.orchestrator
    await engine.dispose()


async def _seed(name, state):
    async with app.state.factory() as s:
        s.add(
            MediaItem(
                id=name,
                source_path=f"/in/{name}",
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
        s.add(VerificationRecord(media_item_id=name, passed=True, checks=[]))
        await s.commit()


async def _login(client):
    r = await client.post("/ui/login", data={"token": TOKEN})
    assert r.status_code == 303
    return {"mr_token": r.cookies["mr_token"]}


# ---- auth + CSRF (#93) ----------------------------------------------------
async def test_unauthenticated_page_redirects_to_login(client):
    r = await client.get("/ui/queue")
    assert r.status_code == 303 and r.headers["location"] == "/ui/login"


async def test_wrong_token_is_401_and_sets_no_cookie(client):
    r = await client.post("/ui/login", data={"token": "nope"})
    assert r.status_code == 401 and "mr_token" not in r.cookies


async def test_login_cookie_is_httponly_samesite_strict(client):
    r = await client.post("/ui/login", data={"token": TOKEN})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie


async def test_cookie_authenticates_pages(client):
    cookies = await _login(client)
    assert (await client.get("/ui/queue", cookies=cookies)).status_code == 200


async def test_post_without_hx_request_is_415(client):
    cookies = await _login(client)
    r = await client.post("/ui/items/x/approve", cookies=cookies)
    assert r.status_code == 415
    r = await client.post("/ui/items/x/approve", cookies=cookies, headers=HX)
    assert r.status_code == 404  # reached the handler; unknown item


async def test_unauthenticated_post_never_reaches_the_handler(client):
    r = await client.post("/ui/items/x/approve", headers=HX)
    assert r.status_code == 401 and r.headers["hx-redirect"] == "/ui/login"


# ---- headers / CSP (#92) --------------------------------------------------
async def test_ui_responses_carry_csp_and_framing_headers(client):
    r = await client.get("/ui/login")
    csp = r.headers["content-security-policy"]
    assert "default-src 'self'" in csp and "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"


async def test_api_responses_get_nosniff_and_framing_but_no_ui_csp(client):
    r = await client.get("/api/v1/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" not in r.headers


async def test_templates_need_no_inline_script_or_eval(client):
    cookies = await _login(client)
    await _seed("a.mp3", FileState.planned)
    page = (await client.get("/ui/items/a.mp3", cookies=cookies)).text
    assert "hx-on" not in page and "onclick" not in page
    login = (await client.get("/ui/login")).text
    assert '"allowEval":false' in login and '"includeIndicatorStyles":false' in login


# ---- bulk actions report failures (#94) -----------------------------------
async def test_bulk_approve_reports_items_that_could_not_be_actioned(client):
    cookies = await _login(client)
    await _seed("ok.mp3", FileState.planned)
    await _seed("moved-on.mp3", FileState.executed)
    r = await client.post(
        "/ui/review/approve",
        data={"ids": ["ok.mp3", "moved-on.mp3"]},
        cookies=cookies,
        headers=HX,
    )
    assert r.status_code == 200
    assert 'role="status"' in r.text and "1 of 2" in r.text


async def test_bulk_approve_all_ok_shows_no_warning(client):
    cookies = await _login(client)
    await _seed("ok.mp3", FileState.planned)
    r = await client.post(
        "/ui/review/approve", data={"ids": ["ok.mp3"]}, cookies=cookies, headers=HX
    )
    assert r.status_code == 200 and "skipped" not in r.text


async def test_login_cookie_flags_logout_and_throttle(client):
    ok = await client.post(
        "/ui/login", data={"token": TOKEN}, headers={"X-Forwarded-Proto": "https"}
    )
    cookie = ok.headers["set-cookie"].lower()
    assert "secure" in cookie and "max-age=" in cookie and "httponly" in cookie
    out = await client.post("/ui/logout")
    assert out.status_code == 303 and "max-age=0" in out.headers["set-cookie"].lower()
    for _ in range(5):
        assert (
            await client.post("/ui/login", data={"token": "bad"})
        ).status_code == 401
    assert (await client.post("/ui/login", data={"token": TOKEN})).status_code == 429
    from app.ui.routes import _failed_logins

    _failed_logins.clear()
