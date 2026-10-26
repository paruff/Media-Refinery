import asyncio
import json
import tempfile
from pathlib import Path

from behave import given, then, when  # type: ignore[import-untyped]
from sqlalchemy import select

from app.core.orchestrator import PipelineOrchestrator
from app.models.media import FileState, MediaItem, VerificationRecord
from tests.pipeline_helpers import (
    import_input,
    make_config,
    make_mkv,
    make_mp3,
    make_session_factory,
    tree_digest,
)


class Crash(BaseException):
    """The daemon is killed: not an Exception, so no stage handler swallows it."""


def _run(context, coro):
    return context.spine_loop.run_until_complete(coro)


def _setup(context, dry_run):
    tmp = tempfile.TemporaryDirectory()
    context.add_cleanup(tmp.cleanup)
    base = Path(tmp.name)
    context.spine_loop = asyncio.new_event_loop()
    context.add_cleanup(context.spine_loop.close)
    context.cfg = make_config(base, dry_run=dry_run)
    engine, context.factory = _run(context, make_session_factory(base))
    context.add_cleanup(lambda: _run(context, engine.dispose()))
    context.orch = PipelineOrchestrator(context.factory, context.cfg)


@given("a pipeline workspace")
def step_workspace(context):
    _setup(context, dry_run=False)


@given("a pipeline workspace in dry-run mode")
def step_workspace_dry(context):
    _setup(context, dry_run=True)


@given("a generated MP3 and a generated MKV in the input directory")
def step_mp3_and_mkv(context):
    make_mp3(
        context.cfg.input_dir / "song.mp3",
        artist="The Artist",
        album="The Album",
        title="Song",
        date="2020",
        track="1",
    )
    make_mkv(context.cfg.input_dir / "Test Movie (2020).mkv")
    context.originals = {
        p.name: p.read_bytes() for p in context.cfg.input_dir.iterdir()
    }
    _run(context, import_input(context.cfg, context.factory))
    context.before = tree_digest(
        context.cfg.input_dir,
        context.cfg.music_root,
        context.cfg.movies_root,
        context.cfg.tv_root,
    )


@given("a generated MP3 in the input directory")
def step_mp3(context):
    make_mp3(
        context.cfg.input_dir / "song.mp3",
        artist="The Artist",
        album="The Album",
        title="Song",
        date="2020",
        track="1",
    )
    context.originals = {"song.mp3": (context.cfg.input_dir / "song.mp3").read_bytes()}
    _run(context, import_input(context.cfg, context.factory))


async def _items(context):
    async with context.factory() as s:
        return (await s.execute(select(MediaItem))).scalars().all()


async def _approve_all(context):
    for item in await _items(context):
        if item.state == FileState.planned:
            assert await context.orch.approve(str(item.id))


@given("the item is planned and approved")
def step_planned_approved(context):
    _run(context, context.orch.run_until_idle())
    _run(context, _approve_all(context))


@when("the pipeline runs until idle")
def step_run(context):
    _run(context, context.orch.run_until_idle())


@when("I approve every planned item")
def step_approve(context):
    _run(context, _approve_all(context))


@when("the daemon is killed during EXECUTE")
def step_kill(context):
    async def die(source, args, out):
        out.write_bytes(b"partial")
        raise Crash

    context.orch._run_ffmpeg = die
    try:
        _run(context, context.orch.run_once())
    except Crash:
        return
    raise AssertionError("EXECUTE finished; the crash never happened")


@when("the daemon restarts")
def step_restart(context):
    context.orch = PipelineOrchestrator(context.factory, context.cfg)
    _run(context, context.orch.recover())
    _run(context, context.orch.run_until_idle())


@then("every item is awaiting approval")
def step_awaiting(context):
    items = _run(context, _items(context))
    assert items and {i.state for i in items} == {FileState.planned}, [
        (i.source_path, i.state, i.error_log) for i in items
    ]


@then("the library roots are empty")
def step_empty_roots(context):
    cfg = context.cfg
    assert not any(
        p.is_file()
        for r in (cfg.music_root, cfg.movies_root, cfg.tv_root)
        for p in r.rglob("*")
    )


@then('every item is in "{state}" state')
def step_state(context, state):
    items = _run(context, _items(context))
    assert items and {i.state for i in items} == {FileState(state)}, [
        (i.source_path, i.state, i.error_log) for i in items
    ]


@then('the item is in "{state}" state')
def step_item_state(context, state):
    step_state(context, state)


@then("the outputs exist under the library roots")
def step_outputs(context):
    cfg = context.cfg
    assert any(cfg.music_root.rglob("*.mp3")) or not any(
        n.endswith(".mp3") for n in context.originals
    )
    if any(n.endswith(".mkv") for n in context.originals):
        assert (
            cfg.movies_root / "Test Movie (2020)" / "Test Movie (2020).mkv"
        ).is_file()
    if any(n.endswith(".mp3") for n in context.originals):
        assert (
            cfg.music_root / "The Artist" / "The Album (2020)" / "01 - Song.mp3"
        ).is_file()


@then("the originals exist under the archive directory")
def step_archive(context):
    archived = {
        p.name: p.read_bytes()
        for p in context.cfg.archive_dir.rglob("*")
        if p.is_file()
    }
    assert archived == context.originals
    assert not any(context.cfg.input_dir.iterdir())


@then("every item has a passing verification record")
def step_records(context):
    async def fetch():
        async with context.factory() as s:
            return (await s.execute(select(VerificationRecord))).scalars().all()

    records = _run(context, fetch())
    assert len(records) == 2 and all(r.passed and r.output_sha256 for r in records)


@then("input and the library roots are byte-identical to before")
def step_identical(context):
    cfg = context.cfg
    assert (
        tree_digest(cfg.input_dir, cfg.music_root, cfg.movies_root, cfg.tv_root)
        == context.before
    )


@then("a dry-run report exists for every item")
def step_reports(context):
    reports = [
        json.loads(p.read_text())
        for p in (context.cfg.work_dir / "dry-run").glob("*.json")
    ]
    assert len(reports) == 2 and all(
        c["passed"] for r in reports for c in r["preflight"]
    )


@then("nothing was archived or quarantined")
def step_nothing(context):
    assert (
        not context.cfg.archive_dir.exists() and not context.cfg.quarantine_dir.exists()
    )
