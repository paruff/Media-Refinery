import enum
import os
from collections.abc import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.models.media import Base as ModelsBase

# Use the project's model Base so metadata.create_all() creates model tables
Base = ModelsBase
DATABASE_URL = settings.DATABASE_URL

engine_kwargs: dict = {"echo": False, "future": True}
if DATABASE_URL == "sqlite+aiosqlite:///:memory:":
    engine_kwargs["poolclass"] = StaticPool

engine = create_async_engine(DATABASE_URL, **engine_kwargs)
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)  # type: ignore[call-overload]


def sync_schema(conn) -> None:
    """create_all only makes missing tables; add the columns and indexes an older DB lacks.

    Migrations are not run at startup, so an upgraded image would otherwise hit "no such
    column". Additive only: renames, drops and type changes still need a real migration.
    """
    Base.metadata.create_all(conn)
    inspector = inspect(conn)
    for table in Base.metadata.sorted_tables:
        have = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name in have:
                continue
            conn.execute(
                text(
                    f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" '
                    f"{col.type.compile(conn.dialect)}"
                )
            )
            default = getattr(col.default, "arg", None)
            if isinstance(default, str | int | float | bool | enum.Enum):
                value = default.name if isinstance(default, enum.Enum) else default
                conn.execute(
                    table.update().where(col.is_(None)).values({col.name: value})
                )
        for index in table.indexes:
            index.create(conn, checkfirst=True)


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
        await conn.run_sync(sync_schema)
        await conn.execute(text("PRAGMA journal_mode=WAL;"))


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
