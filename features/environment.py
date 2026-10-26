import asyncio
import tempfile

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models.media import Base  # FIX: Use the correct Base


def before_all(context):
    # Ensure test DB is migrated before running features
    async def create_all():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    from app.core.database import Base, engine

    asyncio.run(create_all())


def before_scenario(context, scenario):
    # Setup temp dirs
    context.tempdirs = {}
    for d in ["input", "staging", "output"]:
        tempdir = tempfile.TemporaryDirectory()
        context.tempdirs[d] = tempdir
        setattr(context, f"{d}_dir", tempdir.name)

    # Setup in-memory DB
    context.engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    context.AsyncSessionLocal = sessionmaker(
        context.engine, expire_on_commit=False, class_=AsyncSession
    )

    async def create_all():
        async with context.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create_all())
    context.db = context.AsyncSessionLocal

    # FastAPI TestClient
    context.client = TestClient(app)


def after_scenario(context, scenario):
    # Cleanup temp dirs
    for tempdir in context.tempdirs.values():
        tempdir.cleanup()
    # Dispose DB
    asyncio.run(context.engine.dispose())
