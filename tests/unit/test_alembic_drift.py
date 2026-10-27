"""#91: `alembic upgrade head` must build the same schema as the models (create_all)."""

import re
import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine

import app.models.device_profile
import app.models.saga  # noqa: F401
from alembic import command
from app.models.media import Base

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.unit


def schema(path: Path) -> dict[str, dict[str, tuple[str, int]]]:
    con = sqlite3.connect(path)
    tables = con.execute(
        "select name from sqlite_master where type='table' and name != 'alembic_version'"
    ).fetchall()
    return {
        t: {
            # SQLite ignores VARCHAR lengths; compare the type family only
            r[1]: (re.sub(r"\(.*\)", "", r[2]), r[3])
            for r in con.execute(f"pragma table_info({t})")
        }
        for (t,) in tables
    }


def test_alembic_head_matches_create_all(tmp_path):
    migrated, created = tmp_path / "migrated.db", tmp_path / "created.db"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{migrated}")
    command.upgrade(cfg, "head")
    Base.metadata.create_all(create_engine(f"sqlite:///{created}"))
    assert schema(migrated) == schema(created)
