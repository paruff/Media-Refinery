def test_quality_metrics_schema_defaults():
    from app.schemas.quality_metrics import QualityMetricsSchema

    assert QualityMetricsSchema().vmaf is None
    assert QualityMetricsSchema(vmaf=90, psnr=40).psnr == 40


def test_worker_celery_app_configured():
    from app.worker import celery_app

    assert celery_app.main == "media_refinery"


def test_health_endpoint_returns_200_without_redirect():
    import asyncio

    from fastapi.testclient import TestClient

    from app.core.database import init_db
    from app.main import app

    asyncio.run(init_db())
    # no `with` block: skips startup (watcher/coordinator), only routing is under test
    resp = TestClient(app).get("/health", follow_redirects=False)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
