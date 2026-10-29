from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_orchestrator, json_only
from app.core.database import get_async_session
from app.core.orchestrator import PipelineOrchestrator
from app.models.media import (
    FileState,
    MediaItem,
    MediaType,
    NormalizationPlan,
    VerificationRecord,
)

router = APIRouter(tags=["items"])


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_path: str
    state: FileState
    media_type: MediaType
    title: str | None = None
    updated_at: datetime | None = None


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_path: str
    ffmpeg_args: list[str] | None = None
    needs_transcode: bool
    plan_status: str
    execution_log: str


class VerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    passed: bool
    checks: list[dict]
    output_sha256: str | None = None
    created_at: datetime


class ItemDetail(ItemOut):
    plan: PlanOut | None = None
    log: list[str]
    verification: list[VerificationOut]


class Transition(BaseModel):
    id: str
    state: FileState


@router.get("/items", response_model=list[ItemOut])
async def list_items(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    state: FileState | None = None,
    type: MediaType | None = None,
):
    query = select(MediaItem).order_by(MediaItem.source_path)
    if state:
        query = query.where(MediaItem.state == state)
    if type:
        query = query.where(MediaItem.media_type == type)
    return (await session.execute(query)).scalars().all()


async def _item(session: AsyncSession, item_id: str) -> MediaItem:
    item = await session.get(MediaItem, item_id)
    if item is None:
        raise HTTPException(404, f"No item {item_id}")
    return item


@router.get("/items/{item_id}", response_model=ItemDetail)
async def get_item(
    item_id: str, session: Annotated[AsyncSession, Depends(get_async_session)]
):
    item = await _item(session, item_id)
    plan = (
        await session.execute(
            select(NormalizationPlan).where(NormalizationPlan.media_item_id == item_id)
        )
    ).scalar_one_or_none()
    records = (
        await session.execute(
            select(VerificationRecord)
            .where(VerificationRecord.media_item_id == item_id)
            .order_by(VerificationRecord.created_at)
        )
    ).scalars()
    log = [
        line
        for line in (str(item.error_log or ""), str(plan.execution_log if plan else ""))
        if line
    ]
    return ItemDetail(
        **ItemOut.model_validate(item).model_dump(),
        plan=PlanOut.model_validate(plan) if plan else None,
        log=log,
        verification=[VerificationOut.model_validate(r) for r in records],
    )


async def _transition(item_id: str, action: str, session: AsyncSession, orch):
    item = await _item(session, item_id)
    done = await getattr(orch, action)(item_id)
    await session.refresh(item)
    if not done:
        raise HTTPException(
            409, f"Cannot {action}: {await orch.refusal(item_id, action, item)}"
        )
    return Transition(id=item_id, state=FileState(str(item.state.value)))


for _action in ("approve", "reject", "retry"):

    def _make(action: str):
        async def endpoint(
            item_id: str,
            session: Annotated[AsyncSession, Depends(get_async_session)],
            orch: Annotated[PipelineOrchestrator, Depends(get_orchestrator)],
        ):
            return await _transition(item_id, action, session, orch)

        endpoint.__name__ = action
        return endpoint

    router.add_api_route(
        f"/items/{{item_id}}/{_action}",
        _make(_action),
        methods=["POST"],
        response_model=Transition,
        dependencies=[Depends(json_only)],
    )
