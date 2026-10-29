"""G10 web UI: server-rendered Jinja2 views with htmx actions over the shared services."""

import time
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import TOKEN_COOKIE, get_orchestrator, require_token, token_matches
from app.api.v1.items import get_item
from app.core.config import settings
from app.core.database import get_async_session
from app.core.orchestrator import PipelineOrchestrator
from app.models.media import FileState, MediaItem, MediaType, NormalizationPlan
from app.services.reporting_service import ReportingService

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=HERE / "templates")
PARKED = (FileState.quarantined, FileState.error)
Session = Annotated[AsyncSession, Depends(get_async_session)]


def ui_auth(request: Request) -> None:
    """Same R-API-1 check as the API, but an unauthenticated browser gets the login page."""
    try:
        require_token(request, None)
    except HTTPException as e:
        raise HTTPException(303, headers={"Location": "/ui/login"}) from e


def htmx_only(hx_request: Annotated[str | None, Header()] = None) -> None:
    """CSRF guard: a cross-site form cannot add a custom header without a preflight."""
    if hx_request != "true":
        raise HTTPException(415, "UI actions must be sent by the UI (HX-Request)")


router = APIRouter(prefix="/ui", include_in_schema=False)
secured = APIRouter(dependencies=[Depends(ui_auth)])


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse(
        request, "login.html", {"nav": None, "bad": False}
    )


COOKIE_MAX_AGE = 7 * 24 * 3600
MAX_FAILED_LOGINS = 5
LOGIN_WINDOW = 60.0
_failed_logins: dict[
    str, list[float]
] = {}  # ponytail: per-process, per client IP; shared store if multi-worker


def _login_throttled(ip: str) -> bool:
    now = time.monotonic()
    recent = [t for t in _failed_logins.get(ip, []) if now - t < LOGIN_WINDOW]
    _failed_logins[ip] = recent
    return len(recent) >= MAX_FAILED_LOGINS


@router.post("/login")
async def login(request: Request, token: Annotated[str, Form()]):
    ip = request.client.host if request.client else "?"
    if _login_throttled(ip):
        raise HTTPException(429, "Too many failed logins; wait a minute")
    if not token_matches(token, settings.API_TOKEN):
        _failed_logins[ip].append(time.monotonic())
        return templates.TemplateResponse(
            request, "login.html", {"nav": None, "bad": True}, status_code=401
        )
    out = RedirectResponse("/ui/queue", status_code=303)
    https = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https"
    )
    out.set_cookie(
        TOKEN_COOKIE,
        token,
        httponly=True,
        samesite="strict",
        secure=https,
        max_age=COOKIE_MAX_AGE,
    )
    return out


@router.post("/logout")
async def logout():
    out = RedirectResponse("/ui/login", status_code=303)
    out.delete_cookie(TOKEN_COOKIE)
    return out


@secured.get("/")
async def index():
    return RedirectResponse("/ui/queue")


def _queue_query(state: str | None, type: str | None):
    query = select(MediaItem).order_by(MediaItem.source_path)
    if state:
        query = query.where(MediaItem.state == FileState(state))
    if type:
        query = query.where(MediaItem.media_type == MediaType(type))
    return query


async def _queue_ctx(session: AsyncSession, state: str | None, type: str | None):
    try:
        items = (await session.execute(_queue_query(state, type))).scalars().all()
    except ValueError as e:
        raise HTTPException(422, "Unknown state or type filter") from e
    return {
        "items": items,
        "state": state or "",
        "type": type or "",
        "qs": urlencode({"state": state or "", "type": type or ""}),
        "states": [s.value for s in FileState],
        "types": [t.value for t in MediaType],
    }


@secured.get("/queue", response_class=HTMLResponse)
async def queue(
    request: Request,
    session: Session,
    state: str | None = None,
    type: str | None = None,
):
    ctx = await _queue_ctx(session, state, type)
    return templates.TemplateResponse(request, "queue.html", {"nav": "queue", **ctx})


@secured.get("/queue/rows", response_class=HTMLResponse)
async def queue_rows(
    request: Request,
    session: Session,
    state: str | None = None,
    type: str | None = None,
):
    ctx = await _queue_ctx(session, state, type)
    return templates.TemplateResponse(request, "_queue_rows.html", ctx)


async def _review_rows(session: AsyncSession):
    rows = await session.execute(
        select(MediaItem, NormalizationPlan)
        .join(NormalizationPlan, NormalizationPlan.media_item_id == MediaItem.id)
        .where(MediaItem.state == FileState.planned)
        .order_by(MediaItem.source_path)
    )
    return rows.all()


@secured.get("/review", response_class=HTMLResponse)
async def review(request: Request, session: Session):
    rows = await _review_rows(session)
    return templates.TemplateResponse(
        request, "review.html", {"nav": "review", "rows": rows}
    )


@secured.get("/items/{item_id}", response_class=HTMLResponse)
async def item(request: Request, item_id: str, session: Session):
    row = await session.get(MediaItem, item_id)
    detail = await get_item(item_id, session)  # 404s like the API
    return templates.TemplateResponse(
        request, "item.html", {"nav": "queue", "item": row, "detail": detail}
    )


@secured.get("/quarantine", response_class=HTMLResponse)
async def quarantine(request: Request, session: Session):
    items = (
        (
            await session.execute(
                select(MediaItem)
                .where(MediaItem.state.in_(PARKED))
                .order_by(MediaItem.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        request, "quarantine.html", {"nav": "quarantine", "items": items}
    )


@secured.get("/summary", response_class=HTMLResponse)
async def summary(request: Request, session: Session):
    data = await ReportingService(session).get_summary()
    return templates.TemplateResponse(
        request, "summary.html", {"nav": "summary", "s": data}
    )


Orch = Annotated[PipelineOrchestrator, Depends(get_orchestrator)]
write = [Depends(htmx_only)]


async def _act(orch: PipelineOrchestrator, action: str, item_id: str) -> bool:
    return await getattr(orch, action)(item_id)


@secured.post(
    "/items/{item_id}/{action}", dependencies=write, response_class=HTMLResponse
)
async def act_one(
    request: Request, item_id: str, action: str, orch: Orch, session: Session
):
    if action not in ("approve", "reject", "retry"):
        raise HTTPException(404)
    if not await _act(orch, action, item_id):
        row = await session.get(MediaItem, item_id)
        if row is None:
            raise HTTPException(404)
        await session.refresh(row)
        return templates.TemplateResponse(
            request,
            "_notice_row.html",
            {
                "msg": f"Could not {action} {Path(str(row.source_path)).name}: it is {row.state.value}."
            },
        )
    return Response(status_code=200)  # htmx swaps the row away


@secured.post("/review/{action}", dependencies=write, response_class=HTMLResponse)
async def act_bulk(
    request: Request,
    action: str,
    orch: Orch,
    session: Session,
    ids: Annotated[list[str], Form()] = [],  # noqa: B006 (never mutated)
):
    if action not in ("approve", "reject"):
        raise HTTPException(404)
    skipped = 0
    for item_id in ids:
        if not await _act(orch, action, item_id):
            skipped += 1
    return templates.TemplateResponse(
        request,
        "_review_rows.html",
        {"rows": await _review_rows(session), "skipped": skipped, "total": len(ids)},
    )


router.include_router(secured)
