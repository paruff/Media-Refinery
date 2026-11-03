"""An older database (made before a column existed) must still open after an upgrade."""

import pytest
from sqlalchemy import create_engine, inspect, text

import app.models.saga  # noqa: F401
from app.core.database import sync_schema

pytestmark = pytest.mark.unit


def test_missing_columns_and_indexes_are_added_and_old_rows_survive(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE media_items (id VARCHAR PRIMARY KEY, source_path VARCHAR, "
                "state VARCHAR NOT NULL, media_type VARCHAR)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO media_items VALUES ('a', '/in/a.mp3', 'pending', 'unknown')"
            )
        )
    with engine.begin() as conn:
        sync_schema(conn)
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("media_items")}
    assert {"size", "subtitles", "audio_fingerprint"} <= cols
    assert "saga_file_move_log" in insp.get_table_names()
    with engine.begin() as conn:
        assert conn.execute(text("SELECT id FROM media_items")).scalar() == "a"
        sync_schema(conn)  # idempotent
