"""G2 pipeline spine with real ffmpeg on generated fixtures (R-PIPE-1, R-SAFE-1..4)."""

import json

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.orchestrator import PipelineOrchestrator
from app.models.media import FileState, MediaItem, NormalizationPlan, VerificationRecord
from tests.pipeline_helpers import (
    import_input,
    make_avi,
    make_config,
    make_mkv,
    make_mp3,
    make_session_factory,
    tree_digest,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class Crash(BaseException):
    """Simulates the daemon being killed: not an Exception, so nothing handles it."""


@pytest_asyncio.fixture
async def env(tmp_path):
    cfg = make_config(tmp_path)
    engine, factory = await make_session_factory(tmp_path)
    yield cfg, factory
    await engine.dispose()


async def _items(factory):
    async with factory() as s:
        return (await s.execute(select(MediaItem))).scalars().all()


async def _approve_all(orch, factory):
    for item in await _items(factory):
        if item.state == FileState.planned:
            assert await orch.approve(str(item.id))


async def test_mp3_and_mkv_reach_validated_after_approval(env):
    cfg, factory = env
    make_mp3(
        cfg.input_dir / "song.mp3",
        artist="The Artist",
        album="The Album",
        title="Song",
        date="2020",
        track="1",
    )
    make_mkv(cfg.input_dir / "Test Movie (2020).mkv")
    originals = {p.name: p.read_bytes() for p in cfg.input_dir.iterdir()}
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)

    await orch.run_until_idle()
    states = {i.state for i in await _items(factory)}
    assert states == {FileState.planned}, "nothing runs before approval"
    assert not list(cfg.music_root.rglob("*")) and not list(cfg.movies_root.rglob("*"))

    await _approve_all(orch, factory)
    await orch.run_until_idle()

    items = await _items(factory)
    assert {i.state for i in items} == {FileState.validated}, [
        (i.source_path, i.state, i.error_log) for i in items
    ]
    assert (
        cfg.music_root / "The Artist" / "The Album (2020)" / "01 - Song.mp3"
    ).is_file()
    assert (cfg.movies_root / "Test Movie (2020)" / "Test Movie (2020).mkv").is_file()
    archived = {
        p.name: p.read_bytes() for p in cfg.archive_dir.rglob("*") if p.is_file()
    }
    assert archived == originals and not list(cfg.input_dir.iterdir())
    async with factory() as s:
        records = (await s.execute(select(VerificationRecord))).scalars().all()
    assert len(records) == 2 and all(r.passed and r.output_sha256 for r in records)
    assert {c["name"] for c in records[0].checks} == {"decode", "duration", "sha256"}


async def test_non_conformant_video_is_reencoded_to_h264(env):
    cfg, factory = env
    make_avi(cfg.input_dir / "Old Movie (1999).avi")
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)
    await orch.run_until_idle()
    await _approve_all(orch, factory)
    await orch.run_until_idle()
    (item,) = await _items(factory)
    assert item.state == FileState.validated, item.error_log
    out = cfg.movies_root / "Old Movie (1999)" / "Old Movie (1999).mkv"
    from app.core.tools import run_tool

    _, probe, _ = await run_tool(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "csv=p=0",
            str(out),
        ]
    )
    assert probe.strip() == "h264"


async def test_auto_approve_rule_is_opt_in(env):
    cfg, factory = env
    cfg.auto_approve_types = frozenset({"music"})
    make_mp3(cfg.input_dir / "a.mp3", artist="X", album="Y", title="Z")
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)
    await orch.run_until_idle()
    (item,) = await _items(factory)
    assert item.state == FileState.validated, item.error_log


async def test_crash_mid_execute_then_restart_completes(env):
    cfg, factory = env
    make_mp3(cfg.input_dir / "a.mp3", artist="X", album="Y", title="Z")
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)
    await orch.run_until_idle()
    await _approve_all(orch, factory)

    async def die(source, args, out):
        out.write_bytes(b"partial")  # half-written output, then the process dies
        raise Crash

    orch._run_ffmpeg = die  # type: ignore[method-assign]
    with pytest.raises(Crash):
        await orch.run_once()
    (item,) = await _items(factory)
    assert item.state == FileState.executing

    restarted = PipelineOrchestrator(factory, cfg)  # new process: fresh instance
    await restarted.recover()
    await restarted.run_until_idle()
    (item,) = await _items(factory)
    assert item.state == FileState.validated, item.error_log
    assert (cfg.music_root / "X" / "Y" / "Z.mp3").stat().st_size > len(b"partial")


async def _corrupt_output_case(env, src_name, make, garbage_root):
    cfg, factory = env
    src = make(cfg.input_dir / src_name)
    before = src.read_bytes()
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)
    await orch.run_until_idle()
    await _approve_all(orch, factory)

    async def garbage(source, args, out):
        out.write_bytes(b"not media at all")
        return 0, "", ""

    orch._run_ffmpeg = garbage  # type: ignore[method-assign]
    await orch.run_until_idle()
    (item,) = await _items(factory)
    assert src.read_bytes() == before and not list(garbage_root(cfg).rglob("*.*"))
    assert not cfg.archive_dir.exists()
    return cfg, item


async def test_corrupt_output_is_quarantined_and_original_untouched(env):
    cfg, item = await _corrupt_output_case(
        env, "Test Movie (2020).mkv", make_mkv, lambda c: c.movies_root
    )
    assert item.state == FileState.quarantined and item.error_log.startswith(
        "decode_failed"
    )
    assert len(list((cfg.quarantine_dir / "decode_failed").iterdir())) == 1


async def test_untaggable_music_output_is_quarantined(env):
    """Music output that cannot even be tagged never reaches VERIFY or the library."""
    _, item = await _corrupt_output_case(
        env, "a.mp3", lambda p: make_mp3(p, artist="X", album="Y", title="Z"),
        lambda c: c.music_root,
    )  # fmt: skip
    assert item.state == FileState.quarantined and item.error_log.startswith(
        "convert_failed"
    )


async def test_failed_conversion_is_quarantined(env):
    cfg, factory = env
    make_mp3(cfg.input_dir / "a.mp3", artist="X", album="Y", title="Z")
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)
    await orch.run_until_idle()
    await _approve_all(orch, factory)

    async def fail(source, args, out):
        return 1, "", "boom"

    orch._run_ffmpeg = fail  # type: ignore[method-assign]
    await orch.run_until_idle()
    (item,) = await _items(factory)
    assert item.state == FileState.quarantined and item.error_log.startswith(
        "convert_failed"
    )


async def test_dry_run_changes_nothing_outside_work_dry_run(env):
    cfg, factory = env
    cfg.dry_run = True
    make_mp3(cfg.input_dir / "a.mp3", artist="X", album="Y", title="Z")
    make_mkv(cfg.input_dir / "Test Movie (2020).mkv")
    await import_input(cfg, factory)
    before = tree_digest(cfg.input_dir, cfg.music_root, cfg.movies_root, cfg.tv_root)
    orch = PipelineOrchestrator(factory, cfg)
    await orch.run_until_idle()
    assert (
        tree_digest(cfg.input_dir, cfg.music_root, cfg.movies_root, cfg.tv_root)
        == before
    )
    assert {p.name for p in cfg.work_dir.rglob("*") if p.is_file()} and all(
        "dry-run" in p.parts for p in cfg.work_dir.rglob("*") if p.is_file()
    )
    assert not cfg.archive_dir.exists() and not cfg.quarantine_dir.exists()
    reports = [
        json.loads(p.read_text()) for p in (cfg.work_dir / "dry-run").glob("*.json")
    ]
    assert len(reports) == 2 and all(
        c["passed"] for r in reports for c in r["preflight"]
    )
    async with factory() as s:
        assert (await s.execute(select(NormalizationPlan))).scalars().all()


async def test_failing_server_only_warns_item_still_validated(env, caplog):
    import logging
    from types import SimpleNamespace

    import httpx

    from app.services.notify import Notifier

    cfg, factory = env
    make_mkv(cfg.input_dir / "Test Movie (2020).mkv")
    await import_input(cfg, factory)
    seen = []

    def down(req):
        seen.append(req)
        return httpx.Response(503)

    notifier = Notifier(
        SimpleNamespace(
            PLEX_URL="http://plex",
            PLEX_TOKEN="t",
            PLEX_SECTIONS={"movie": "1"},
            JELLYFIN_URL="",
            ABS_URL="",
            MUSIC_ASSISTANT_URL="",
        ),
        httpx.AsyncClient(transport=httpx.MockTransport(down)),
    )
    orch = PipelineOrchestrator(factory, cfg, notifier=notifier)
    await orch.run_until_idle()
    await _approve_all(orch, factory)
    with caplog.at_level(logging.WARNING, logger="notify"):
        await orch.run_until_idle()

    assert {i.state for i in await _items(factory)} == {FileState.validated}
    assert [r.url.path for r in seen] == ["/library/sections/1/refresh"]
    assert "plex rescan failed" in caplog.text


def _twin_mp3(cfg, name, freq):
    return make_mp3(
        cfg.input_dir / name, freq=freq, artist="X", album="Y", title="Z"
    )  # same tags, same target, different content


async def test_second_item_with_same_target_is_quarantined_plan_conflict(env):
    cfg, factory = env
    _twin_mp3(cfg, "a.mp3", 440)
    _twin_mp3(cfg, "b.mp3", 880)
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)
    await orch.run_until_idle()
    states = sorted(i.state.value for i in await _items(factory))
    assert states == ["planned", "quarantined"]
    quarantined = next(i for i in await _items(factory) if i.state != FileState.planned)
    assert quarantined.error_log.startswith("plan_conflict")


async def test_failed_plan_does_not_block_a_new_item_with_same_target(env):
    cfg, factory = env
    _twin_mp3(cfg, "a.mp3", 440)
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)
    await orch.run_until_idle()
    await _approve_all(orch, factory)

    async def garbage(source, args, out):
        out.write_bytes(b"not media at all")
        return 0, "", ""

    orch._run_ffmpeg = garbage  # type: ignore[method-assign]
    await orch.run_until_idle()  # first item fails and its plan is marked failed
    _twin_mp3(cfg, "b.mp3", 880)
    await import_input(cfg, factory)
    await PipelineOrchestrator(factory, cfg).run_until_idle()
    planned = [i for i in await _items(factory) if i.state == FileState.planned]
    assert len(planned) == 1, [i.error_log for i in await _items(factory)]


async def test_different_file_at_target_is_quarantined_target_exists(env):
    cfg, factory = env
    _twin_mp3(cfg, "a.mp3", 440)
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)
    await orch.run_until_idle()
    await _approve_all(orch, factory)
    squatter = cfg.music_root / "X" / "Y" / "Z.mp3"
    squatter.parent.mkdir(parents=True)
    squatter.write_bytes(b"someone else's file")
    await orch.run_until_idle()
    (item,) = await _items(factory)
    assert item.state == FileState.quarantined and item.error_log.startswith(
        "target_exists"
    )
    assert squatter.read_bytes() == b"someone else's file"


async def test_crash_after_file_landed_resumes_to_validated(env, monkeypatch):
    """Saga resume: PUBLISH moved the file but the process died before the state commit."""
    import app.core.orchestrator as orchestrator

    cfg, factory = env
    _twin_mp3(cfg, "a.mp3", 440)
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)
    await orch.run_until_idle()
    await _approve_all(orch, factory)
    real = orchestrator.publish_file

    async def land_then_die(*args):
        await real(*args)
        raise Crash

    monkeypatch.setattr(orchestrator, "publish_file", land_then_die)
    with pytest.raises(Crash):
        await orch.run_until_idle()
    monkeypatch.setattr(orchestrator, "publish_file", real)
    restarted = PipelineOrchestrator(factory, cfg)
    await restarted.recover()
    await restarted.run_until_idle()
    (item,) = await _items(factory)
    assert item.state == FileState.validated, item.error_log


async def test_missing_work_file_at_publish_is_reexecuted(env):
    cfg, factory = env
    _twin_mp3(cfg, "a.mp3", 440)
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg)
    await orch.run_until_idle()
    await _approve_all(orch, factory)
    real, lost = orch._publish, []

    async def drop_work_once(item_id):
        if not lost:
            lost.append(1)
            for f in cfg.work_dir.rglob("out.*"):
                f.unlink()
        return await real(item_id)

    orch._publish = drop_work_once  # type: ignore[method-assign]
    await orch.run_until_idle()
    (item,) = await _items(factory)
    assert item.state == FileState.validated, item.error_log
