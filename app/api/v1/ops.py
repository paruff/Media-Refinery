"""Liveness/readiness, rescan, summary and Prometheus metrics."""

import asyncio
import os
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
from app.services.refinery import Refinery
from app.services.reporting_service import ReportingService, SystemSummary

router = APIRouter()  # open: liveness/readiness probes
secured = APIRouter()  # mounted behind the bearer-token dependency


def _writable(path: Path) -> bool:
    """True if `path` exists and is writable, or can be created under a writable parent."""
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return os.access(probe, os.W_OK)


@router.get("/health", tags=["health"])
async def health(session: Annotated[AsyncSession, Depends(get_async_session)]):
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}


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
    writable = [await asyncio.to_thread(_writable, Path(str(d))) for d in dirs]
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
async def metrics(session: Annotated[AsyncSession, Depends(get_async_session)]):
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
    ]
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
