"""Liveness/readiness, rescan, summary and Prometheus metrics."""

import asyncio
import logging
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_orchestrator, json_only
from app.core.database import get_async_session
from app.core.orchestrator import PipelineOrchestrator
from app.models.media import MediaItem
from app.services.doctor import is_writable
from app.services.refinery import Refinery
from app.services.reporting_service import (
    ReportingService,
    SystemSummary,
    quarantine_counts,
)

logger = logging.getLogger(__name__)

router = APIRouter()  # open: liveness/readiness probes
secured = APIRouter()  # mounted behind the bearer-token dependency


@router.get("/health", tags=["health"])
async def health(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        logger.exception("health check: database unavailable")
        response.status_code = 503
        return {"status": "error", "database": "unavailable"}


@router.get("/ready", tags=["health"])
async def ready(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    orch: Annotated[PipelineOrchestrator, Depends(get_orchestrator)],
):
    checks: dict[str, bool] = {"ffmpeg": shutil.which("ffmpeg") is not None}
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False
    dirs = (*orch.cfg.roots.values(), orch.cfg.work_dir, orch.cfg.quarantine_dir)
    writable = [await asyncio.to_thread(is_writable, Path(str(d))) for d in dirs]
    checks["library_roots_writable"] = all(writable)
    ok = all(checks.values())
    if not ok:
        response.status_code = 503
    return {"status": "ready" if ok else "not_ready", "checks": checks}


@secured.post("/scan", dependencies=[Depends(json_only)], tags=["ops"])
async def scan(orch: Annotated[PipelineOrchestrator, Depends(get_orchestrator)]):
    ids = await Refinery(orch).ingest(orch.cfg.input_dir)
    return {"imported": len(ids)}


@secured.get("/summary", response_model=SystemSummary, tags=["ops"])
async def summary(session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await ReportingService(session).get_summary()


@secured.get("/metrics", response_class=Response, tags=["ops"])
async def metrics(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    orch: Annotated[PipelineOrchestrator, Depends(get_orchestrator)],
):
    rows: Sequence = (
        await session.execute(
            select(MediaItem.state, MediaItem.media_type, func.count()).group_by(
                MediaItem.state, MediaItem.media_type
            )
        )
    ).all()
    lines = [
        "# HELP media_refinery_items Items by pipeline state and media type.",
        "# TYPE media_refinery_items gauge",
        *(
            f'media_refinery_items{{state="{s.value}",type="{t.value}"}} {n}'
            for s, t, n in rows
        ),
        "# HELP media_refinery_quarantined_items Quarantined items by reason.",
        "# TYPE media_refinery_quarantined_items gauge",
        *(
            f'media_refinery_quarantined_items{{reason="{r}"}} {n}'
            for r, n in (await quarantine_counts(session)).items()
        ),
        "# HELP media_refinery_stage_duration_seconds_sum Time spent in each stage since start.",
        "# TYPE media_refinery_stage_duration_seconds_sum counter",
        *(
            f'media_refinery_stage_duration_seconds_sum{{stage="{st}"}} {t:.3f}'
            for st, (t, _) in orch.stage_seconds.items()
        ),
        "# HELP media_refinery_stage_duration_seconds_count Stage runs since start.",
        "# TYPE media_refinery_stage_duration_seconds_count counter",
        *(
            f'media_refinery_stage_duration_seconds_count{{stage="{st}"}} {n}'
            for st, (_, n) in orch.stage_seconds.items()
        ),
    ]
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
