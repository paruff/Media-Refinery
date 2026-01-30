from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal

router = APIRouter()

@router.get("/", tags=["health"])
async def healthcheck():
    try:
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}
