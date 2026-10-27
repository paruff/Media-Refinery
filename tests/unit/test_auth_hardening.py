"""#88/#89: constant-time compare must not 500 on non-ASCII, /health must not leak, startup must fail closed."""

import httpx
import pytest

from app.api.auth import check_bind_security, is_loopback, token_matches
from app.core.config import settings
from app.core.database import get_async_session
from app.main import app

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.fixture
def exposed(monkeypatch):
    monkeypatch.setattr(settings, "API_HOST", "0.0.0.0")  # noqa: S104
    monkeypatch.setattr(settings, "API_TOKEN", "s3cret")


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    )


def test_token_matches_handles_non_ascii_and_empty():
    assert token_matches("s3cret", "s3cret")
    assert not token_matches("é", "s3cret")
    assert not token_matches("s3cret", "sécret")
    assert not token_matches("anything", "")


@pytest.mark.parametrize(
    "host,expected",
    [
        ("127.0.0.1", True),
        ("127.0.0.2", True),
        ("::1", True),
        ("0:0:0:0:0:0:0:1", True),
        ("localhost", True),
        ("0.0.0.0", False),  # noqa: S104
        ("192.168.1.5", False),
        ("::", False),
    ],
)
def test_is_loopback(host, expected):
    assert is_loopback(host) is expected


def test_startup_refuses_exposed_bind_without_token():
    with pytest.raises(RuntimeError, match="MR_API_TOKEN"):
        check_bind_security("0.0.0.0", "")  # noqa: S104
    check_bind_security("0.0.0.0", "s3cret")  # noqa: S104
    check_bind_security("127.0.0.1", "")


async def test_non_ascii_bearer_is_401_not_500(exposed):
    async with client() as c:
        r = await c.get(
            "/api/v1/items", headers={"Authorization": "Bearer é".encode("latin-1")}
        )
    assert r.status_code == 401


async def test_non_ascii_cookie_is_401_not_500(exposed):
    async with client() as c:
        r = await c.get(
            "/api/v1/items", headers={"Cookie": "mr_token=é".encode("latin-1")}
        )
    assert r.status_code == 401


async def test_non_ascii_ui_login_is_401_not_500(exposed):
    async with client() as c:
        r = await c.post("/ui/login", data={"token": "é"})
    assert r.status_code == 401


async def test_health_failure_is_503_and_does_not_leak(monkeypatch):
    class Broken:
        async def execute(self, *_):
            raise RuntimeError("sqlite:////secret/path/db.sqlite is locked")

    async def broken_session():
        yield Broken()

    app.dependency_overrides[get_async_session] = broken_session
    try:
        async with client() as c:
            r = await c.get("/api/v1/health")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503
    assert r.json() == {"status": "error", "database": "unavailable"}
    assert "secret" not in r.text
