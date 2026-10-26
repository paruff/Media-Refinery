import os
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.media import Base as ModelsBase

# Use the project's model Base so metadata.create_all() creates model tables
Base = ModelsBase
engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)  # type: ignore[call-overload]


async def init_db():
    # Ensure data directory exists
    os.makedirs(
        os.path.dirname(settings.DATABASE_URL.replace("sqlite+aiosqlite:///", ""))
        or ".",
        exist_ok=True,
    )
    async with engine.begin() as conn:
        # Create tables if not exist
        await conn.run_sync(Base.metadata.create_all)
        # Simple migration: ensure table exists
        await conn.execute(text("PRAGMA journal_mode=WAL;"))


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
