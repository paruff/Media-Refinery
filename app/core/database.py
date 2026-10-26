import os
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.models.media import Base as ModelsBase

# Use the project's model Base so metadata.create_all() creates model tables
Base = ModelsBase
DATABASE_URL = os.getenv("DATABASE_URL", settings.DATABASE_URL)

engine_kwargs: dict = {"echo": False, "future": True}
if DATABASE_URL == "sqlite+aiosqlite:///:memory:":
    engine_kwargs["poolclass"] = StaticPool

engine = create_async_engine(DATABASE_URL, **engine_kwargs)
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)  # type: ignore[call-overload]


async def init_db():
    # Ensure data directory exists
    if DATABASE_URL.startswith("sqlite+aiosqlite:///") and DATABASE_URL.endswith(
        ":memory:"
    ):
        db_dir = ""
    else:
        db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    async with engine.begin() as conn:
        # Create tables if not exist
        await conn.run_sync(Base.metadata.create_all)
        # Simple migration: ensure table exists
        await conn.execute(text("PRAGMA journal_mode=WAL;"))


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
