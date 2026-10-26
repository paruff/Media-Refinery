import asyncio
import json
import subprocess
import tempfile
from pathlib import Path

import httpx
from behave import given, then, when  # type: ignore[import-untyped]
from sqlalchemy import select

from app.core.orchestrator import PipelineOrchestrator
from app.models.media import FileState, NormalizationPlan, VerificationRecord
from app.services.enrich import VideoEnricher
from tests.pipeline_helpers import (
    import_input,
    make_avi,
    make_config,
    make_session_factory,
    make_video,
)

EPISODES = {
    (1, 1): "First Episode",
    (1, 2): "Second Episode",
    (0, 1): "Behind The Scenes",
}


def tmdb_tvdb_handler(request: httpx.Request) -> httpx.Response:
    """Offline TMDB v3 + TVDB v4 stand-in."""
    path, q = request.url.path, dict(request.url.params)
    if path.endswith("/search/movie"):
        known = q["query"] == "The Matrix"
        results = [{"id": 603, "title": "The Matrix", "release_date": "1999-03-30"}]
        return httpx.Response(200, json={"results": results if known else []})
    if path.endswith("/login"):
        return httpx.Response(200, json={"data": {"token": "t"}})
    if path.endswith("/search"):
        return httpx.Response(
            200,
            json={"data": [{"tvdb_id": "81189", "name": "Show Name", "year": "2020"}]},
        )
    if "/episodes/" in path:
        name = EPISODES.get((int(q["season"]), int(q["episodeNumber"])))
        return httpx.Response(
            200, json={"data": {"episodes": [{"name": name}] if name else []}}
        )
    return httpx.Response(404)


def _run(context, coro):
    return context.spine_loop.run_until_complete(coro)


@given("a video workspace with mocked TMDB and TVDB")
def step_workspace(context):
    tmp = tempfile.TemporaryDirectory()
    context.add_cleanup(tmp.cleanup)
    base = Path(tmp.name)
    context.spine_loop = asyncio.new_event_loop()
    context.add_cleanup(context.spine_loop.close)
    context.cfg = make_config(base)
    engine, context.factory = _run(context, make_session_factory(base))
    context.add_cleanup(lambda: _run(context, engine.dispose()))
    client = httpx.AsyncClient(transport=httpx.MockTransport(tmdb_tvdb_handler))
    enricher = VideoEnricher("k", "k", client=client)
    context.orch = PipelineOrchestrator(context.factory, context.cfg, enricher=enricher)


@given('a generated conformant video "{name}"')
def step_conformant(context, name):
    # distinct content per name, or duplicate detection skips the second part
    make_video(context.cfg.input_dir / name, seconds=2 + sum(map(ord, name)) % 3)


@given(
    'a generated conformant video "{name}" with {channels:d}-channel "{codec}" audio'
)
def step_surround(context, name, channels, codec):
    make_video(context.cfg.input_dir / name, audio=(codec, channels))


@given('a generated conformant video "{name}" with an "{codec}" subtitle')
def step_subtitle(context, name, codec):
    make_video(context.cfg.input_dir / name, subtitle=codec)


@given('a generated legacy AVI "{name}"')
def step_avi(context, name):
    make_avi(context.cfg.input_dir / name)


@when("the video pipeline is approved and run to completion")
def step_run(context):
    _run(context, import_input(context.cfg, context.factory))
    _run(context, context.orch.run_until_idle())

    async def approve():
        from app.models.media import MediaItem

        async with context.factory() as s:
            items = (await s.execute(select(MediaItem))).scalars().all()
        for item in items:
            if item.state == FileState.planned:
                assert await context.orch.approve(str(item.id))

    _run(context, approve())
    _run(context, context.orch.run_until_idle())


def _published(context, rel):
    lib = {"Movies": context.cfg.movies_root, "TV": context.cfg.tv_root}
    top, _, rest = rel.partition("/")
    return lib[top] / rest


def _one_output(context) -> Path:
    files = [
        p
        for r in (context.cfg.movies_root, context.cfg.tv_root)
        for p in r.rglob("*.mkv")
    ]
    assert len(files) == 1, files
    return files[0]


def _streams(path: Path, kind: str) -> list[dict]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", kind, "-show_streams",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    return json.loads(out)["streams"]


@then('the movie is published at "{rel}"')
def step_movie(context, rel):
    path = _published(context, rel)
    assert path.is_file(), sorted(
        str(p.relative_to(context.cfg.movies_root))
        for p in context.cfg.movies_root.rglob("*")
    )


@then('the episode is published at "{rel}"')
def step_episode(context, rel):
    path = _published(context, rel)
    assert path.is_file(), sorted(
        str(p.relative_to(context.cfg.tv_root)) for p in context.cfg.tv_root.rglob("*")
    )


async def _plans(context):
    async with context.factory() as s:
        return (await s.execute(select(NormalizationPlan))).scalars().all()


@then("the ffmpeg args copy the video and re-encode nothing")
def step_remux(context):
    for plan in _run(context, _plans(context)):
        args = list(plan.ffmpeg_args)
        assert args[args.index("-c:v") + 1] == "copy", args
        assert not {"libx264", "libx265"} & set(args), args


@then('the output video codec is "{codec}"')
def step_vcodec(context, codec):
    assert _streams(_one_output(context), "v")[0]["codec_name"] == codec


@then('the output subtitle codec is "{codec}"')
def step_scodec(context, codec):
    assert [s["codec_name"] for s in _streams(_one_output(context), "s")] == [codec]


@then("the output audio is:")
def step_audio(context):
    got = [
        (s["codec_name"], str(s["channels"]))
        for s in _streams(_one_output(context), "a")
    ]
    assert got == [(r["codec"], r["channels"]) for r in context.table], got


async def _vmaf_checks(context):
    async with context.factory() as s:
        records = (await s.execute(select(VerificationRecord))).scalars().all()
    return [c for r in records for c in r.checks if c["name"] == "vmaf"]


@then("no VMAF check was recorded")
def step_no_vmaf(context):
    assert not _run(context, _vmaf_checks(context))


@then("a VMAF check was recorded")
def step_vmaf(context):
    assert _run(context, _vmaf_checks(context))
