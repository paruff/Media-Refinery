from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
import os
from sqlalchemy import text

Base = declarative_base()
engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    # Ensure data directory exists
    os.makedirs(os.path.dirname(settings.DATABASE_URL.replace('sqlite+aiosqlite:///', '')), exist_ok=True)
    async with engine.begin() as conn:
        # Create tables if not exist
        await conn.run_sync(Base.metadata.create_all)
        # Simple migration: ensure table exists
        await conn.execute(text("PRAGMA journal_mode=WAL;"))
