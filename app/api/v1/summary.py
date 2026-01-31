from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.reporting_service import ReportingService, SystemSummary
from app.core.database import get_async_session

router = APIRouter()


@router.get("/v1/summary", response_model=SystemSummary)
async def get_summary(session: AsyncSession = Depends(get_async_session)):
    service = ReportingService(session)
    return await service.get_summary()
