import subprocess
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.media import Base


@pytest_asyncio.fixture(scope="session", autouse=True)
def apply_alembic_migrations():
    """Ensure all Alembic migrations are applied before tests run."""
    subprocess.run(["alembic", "upgrade", "head"], check=True)


@pytest_asyncio.fixture(scope="function")
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session_factory = sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with async_session_factory() as session:
        yield session
    await engine.dispose()
