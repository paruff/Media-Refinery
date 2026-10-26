import json

from behave import given, then  # type: ignore[import-untyped]
from sqlalchemy import select

from app.core.trace import TraceEvent
from app.models.media import FileState, MediaItem
from tests.pipeline_helpers import (
    import_input,
    make_avi,
    make_mkv,
    tree_digest,
)

MOVIE = "Test Movie (2020)"


def _run(context, coro):
    return context.spine_loop.run_until_complete(coro)


def _import(context, path):
    context.originals = {path.name: path.read_bytes()}
    _run(context, import_input(context.cfg, context.factory))
    cfg = context.cfg
    context.before = tree_digest(
        cfg.input_dir, cfg.music_root, cfg.movies_root, cfg.tv_root
    )


def _corrupt(path):
    """Garble a slice of the payload: ffprobe still reads it, a decode scan does not."""
    data = bytearray(path.read_bytes())
    start = len(data) // 3
    for i in range(start, start + 3000):
        data[i] = 0xA5 ^ (i & 0xFF)
    path.write_bytes(data)


def _trace(context) -> list[str]:
    path = context.orch.trace.path
    return path.read_text().splitlines() if path.exists() else []


@given("a generated MKV in the input directory")
def step_mkv(context):
    _import(context, make_mkv(context.cfg.input_dir / f"{MOVIE}.mkv"))


@given("a generated AVI in the input directory")
def step_avi(context):
    _import(context, make_avi(context.cfg.input_dir / f"{MOVIE}.avi"))


@given("a generated MKV with corrupted video data in the input directory")
def step_corrupt(context):
    path = make_mkv(context.cfg.input_dir / f"{MOVIE}.mkv")
    _corrupt(path)
    _import(context, path)


@then('the movie "{name}" exists in the movies library as MKV')
def step_movie(context, name):
    assert (context.cfg.movies_root / name / f"{name}.mkv").is_file()


@then("the original is archived")
def step_original_archived(context):
    archived = [p for p in context.cfg.archive_dir.rglob("*") if p.is_file()]
    assert [p.name for p in archived] == list(context.originals)
    assert not any(context.cfg.input_dir.iterdir())


@then('the file is quarantined as "{reason}"')
def step_quarantined(context, reason):
    held = list((context.cfg.quarantine_dir / reason).glob("*"))
    assert [p.name.split("-", 1)[1] for p in held] == list(context.originals), held
    assert not any(context.cfg.input_dir.iterdir())

    async def states():
        async with context.factory() as s:
            return (await s.execute(select(MediaItem.state))).scalars().all()

    assert set(_run(context, states())) == {FileState.quarantined}


@then('the trace has a "{event}" event with status "{status}"')
def step_trace_event(context, event, status):
    events = [json.loads(line) for line in _trace(context)]
    assert any(e["event"] == event and e["status"] == status for e in events), events


@then("every trace line is valid against the trace schema")
def step_trace_schema(context):
    lines = _trace(context)
    assert lines
    for line in lines:
        event = TraceEvent.model_validate_json(line)
        assert event.run_id == context.orch.run_id
