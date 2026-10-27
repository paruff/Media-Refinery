"""G9: every R-API route, incl. R-API-1 token auth and the OpenAPI snapshot."""

import json
import os
from pathlib import Path

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
JSON = {"Content-Type": "application/json"}
SNAPSHOT = Path(__file__).parent.parent / "snapshots" / "openapi.json"


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "API_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "API_TOKEN", "")
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


async def _seed(state=FileState.planned, name="a.mp3", mtype=MediaType.music):
    async with app.state.factory() as s:
        item = MediaItem(
            id=name, source_path=f"/in/{name}", state=state, media_type=mtype
        )
        s.add(item)
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
    return name


async def test_health_ready_and_metrics(client):
    assert (await client.get("/health")).json()["status"] == "ok"
    ready = await client.get("/api/v1/ready")
    assert ready.status_code in (200, 503)
    assert set(ready.json()["checks"]) == {
        "ffmpeg",
        "database",
        "library_roots_writable",
    }
    await _seed()
    body = (await client.get("/api/v1/metrics")).text
    assert 'media_refinery_items{state="planned",type="music"} 1' in body


async def test_items_list_filter_and_detail(client):
    await _seed(name="a.mp3")
    await _seed(FileState.error, "b.mkv", MediaType.movie)
    assert len((await client.get("/api/v1/items")).json()) == 2
    only = (await client.get("/api/v1/items?state=error&type=movie")).json()
    assert [i["id"] for i in only] == ["b.mkv"]
    assert (await client.get("/api/v1/items?state=bogus")).status_code == 422
    detail = (await client.get("/api/v1/items/a.mp3")).json()
    assert detail["plan"]["target_path"] == "/lib/a.mp3"
    assert detail["verification"][0]["passed"] is True
    assert (await client.get("/api/v1/items/nope")).status_code == 404


async def test_approve_reject_and_conflicts(client):
    await _seed(name="a.mp3")
    await _seed(name="b.mp3")
    r = await client.post("/api/v1/items/a.mp3/approve", headers=JSON, json={})
    assert r.json() == {"id": "a.mp3", "state": "approved"}
    assert (
        await client.post("/api/v1/items/a.mp3/approve", headers=JSON, json={})
    ).status_code == 409
    r = await client.post("/api/v1/items/b.mp3/reject", headers=JSON, json={})
    assert r.json()["state"] == "quarantined"
    assert (
        await client.post("/api/v1/items/zz/approve", headers=JSON, json={})
    ).status_code == 404


async def test_retry_requeues_when_source_exists(client, tmp_path):
    src = tmp_path / "x.mp3"
    src.write_bytes(b"x")
    await _seed(FileState.error, "x.mp3")
    async with app.state.factory() as s:
        (await s.get(MediaItem, "x.mp3")).source_path = str(src)
        await s.commit()
    r = await client.post("/api/v1/items/x.mp3/retry", headers=JSON, json={})
    assert r.json()["state"] == "pending"
    again = await client.post("/api/v1/items/x.mp3/retry", headers=JSON, json={})
    assert again.status_code == 409


async def test_mutations_are_json_only(client):
    await _seed()
    r = await client.post(
        "/api/v1/items/a.mp3/approve",
        content=b"",
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 415
    assert (await client.post("/api/v1/scan")).status_code == 415


async def test_scan_imports_input(client):
    cfg = app.state.orchestrator.cfg
    (cfg.input_dir / "s.mp3").write_bytes(b"audio")
    r = await client.post("/api/v1/scan", headers=JSON, json={})
    assert r.json() == {"imported": 1}
    assert len((await client.get("/api/v1/items?state=pending")).json()) == 1
    assert (await client.get("/api/v1/summary")).json()["total"] == 1


SECURED = [
    ("GET", "/api/v1/items"),
    ("GET", "/api/v1/items/x"),
    ("GET", "/api/v1/summary"),
    ("GET", "/api/v1/metrics"),
    ("POST", "/api/v1/scan"),
    ("POST", "/api/v1/items/x/approve"),
    ("POST", "/api/v1/items/x/reject"),
    ("POST", "/api/v1/items/x/retry"),
]


@pytest.mark.parametrize(("method", "path"), SECURED)
async def test_non_localhost_requires_token(client, monkeypatch, method, path):
    monkeypatch.setattr(settings, "API_HOST", "0.0.0.0")  # noqa: S104
    monkeypatch.setattr(settings, "API_TOKEN", "s3cret")
    send = lambda h: client.request(method, path, headers={**JSON, **h})  # noqa: E731
    assert (await send({})).status_code == 401
    assert (await send({"Authorization": "Bearer wrong"})).status_code == 401
    assert (await send({"Authorization": "Bearer s3cret"})).status_code != 401


async def test_non_localhost_without_configured_token_fails_closed(client, monkeypatch):
    monkeypatch.setattr(settings, "API_HOST", "0.0.0.0")  # noqa: S104
    r = await client.get("/api/v1/items", headers={"Authorization": "Bearer "})
    assert r.status_code == 401
    assert (await client.get("/health")).status_code == 200  # probes stay open


async def test_openapi_snapshot():
    schema = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    if os.getenv("UPDATE_SNAPSHOT") or not SNAPSHOT.exists():
        SNAPSHOT.write_text(schema)
    assert schema == SNAPSHOT.read_text()
