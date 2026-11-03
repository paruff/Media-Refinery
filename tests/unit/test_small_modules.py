def test_health_endpoint_returns_200_without_redirect():
    import asyncio

    from fastapi.testclient import TestClient

    from app.core.database import init_db
    from app.main import app

    asyncio.run(init_db())
    # no `with` block: skips startup (watcher/coordinator), only routing is under test
    resp = TestClient(app, base_url="http://localhost").get(
        "/health", follow_redirects=False
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_loopback_bind_refuses_foreign_host_names():
    from fastapi.testclient import TestClient

    from app.main import app

    foreign = TestClient(app, base_url="http://evil.example")
    assert foreign.get("/health").status_code == 400
