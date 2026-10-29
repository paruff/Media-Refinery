"""G15 crash injection: kill the daemon at every commit, file move and conversion of the
pipeline (so every STAGE_ORDER step and the publish saga), restart, and assert the safety
invariants: source never lost or modified, no partial file in a library, a rerun converges to
the clean-run result, nothing duplicated."""

import contextlib
import hashlib
import shutil
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.orchestrator as orchestrator
import app.core.publish as publish
import app.media.ebook as ebook_media
import app.pipeline.publish as pipeline_publish
import app.pipeline.types.audiobook as audiobook
import app.pipeline.types.ebook as ebook_type
from app.core.orchestrator import STAGE_ORDER, PipelineOrchestrator
from app.models.media import FileState, MediaItem, VerificationRecord
from tests.ebook_helpers import make_epub
from tests.pipeline_helpers import (
    import_input,
    make_config,
    make_mkv,
    make_mp3,
    make_session_factory,
)

pytestmark = [pytest.mark.corpus, pytest.mark.integration, pytest.mark.asyncio]

KINDS = {
    "music": lambda d: make_mp3(
        d / "a.mp3", artist="X", album="Y", title="Z", track="1"
    ),
    "movie": lambda d: make_mkv(d / "Crash Movie (2020).mkv"),
    "ebook": lambda d: make_epub(d / "crash.epub", "Crash Book", "Crash Author"),
}
# music and ebook are byte-exact; a remuxed MKV embeds a muxing date, and Calibre's database
# and OPF files embed timestamps, so those are compared by name and checked another way
EXACT = {"music"}
# the side effects each kind must actually hit, or the sweep proves nothing about it
REQUIRED = {
    "music": {"commit:before", "move:before", "archive_original:after", "ffmpeg:after"},
    "movie": {"commit:before", "move:before", "archive_original:after", "ffmpeg:after"},
    "ebook": {
        "commit:before",
        "archive_original:after",
        "to_epub:after",
        "calibredb_add:before",
        "calibredb_add:after",
    },
}


class Crash(BaseException):
    """The daemon was killed: not an Exception, so no handler can clean up."""


class Injector:
    """Counts every before/after point of each side-effecting call; raises Crash at `target`."""

    def __init__(self, target: int | None = None):
        self.target, self.count, self.names = target, 0, []

    def point(self, name: str) -> None:
        self.names.append(name)
        self.count += 1
        if self.count - 1 == self.target:
            raise Crash(name)

    def wrap_sync(self, name, fn):
        def wrapped(*a, **kw):
            self.point(f"{name}:before")
            out = fn(*a, **kw)
            self.point(f"{name}:after")
            return out

        return wrapped

    def wrap_async(self, name, fn):
        async def wrapped(*a, **kw):
            self.point(f"{name}:before")
            out = await fn(*a, **kw)
            self.point(f"{name}:after")
            return out

        return wrapped

    def install(self, mp) -> None:
        mp.setattr(
            AsyncSession, "commit", self.wrap_async("commit", AsyncSession.commit)
        )
        mp.setattr(
            publish,
            "_move_into_place",
            self.wrap_sync("move", publish._move_into_place),
        )
        # one wrapper per function, installed in every module that imported it
        homes = {
            "archive_original": (pipeline_publish, audiobook),
            "quarantine_file": (orchestrator, ebook_type),
        }
        for fn, modules in homes.items():
            wrapped = self.wrap_sync(fn, getattr(modules[0], fn))
            for module in modules:
                mp.setattr(module, fn, wrapped)
        for fn in (
            "to_epub",
            "calibredb_add",
        ):  # the Calibre add step is the ebook publish
            mp.setattr(ebook_media, fn, self.wrap_async(fn, getattr(ebook_media, fn)))
        mp.setattr(
            PipelineOrchestrator,
            "_run_ffmpeg",
            self.wrap_async("ffmpeg", PipelineOrchestrator._run_ffmpeg),
        )


def _files(root: Path, exact: bool = True) -> dict[str, str]:
    """{relative path: sha256}. `exact=False` keeps names only: a remuxed MKV embeds a
    muxing date, so video output is checked against its VerificationRecord instead."""
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        if exact
        else ""
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


async def _drive(cfg, factory) -> None:
    """The daemon's life from a cold start: recover, ingest, plan, approve, run."""
    orch = PipelineOrchestrator(factory, cfg)
    await orch.recover()
    await import_input(cfg, factory)
    await orch.run_until_idle()
    async with factory() as s:
        planned = (
            (
                await s.execute(
                    select(MediaItem.id).where(MediaItem.state == FileState.planned)
                )
            )
            .scalars()
            .all()
        )
    for item_id in planned:
        await orch.approve(str(item_id))
    await orch.run_until_idle()


async def _published_matches_record(cfg, factory) -> list[str]:
    """Every library file is byte-identical to what VERIFY recorded (no partial output)."""
    async with factory() as s:
        shas = set(
            (await s.execute(select(VerificationRecord.output_sha256))).scalars()
        )
    lib = _files(cfg.music_root.parent)
    return [f"{rel} does not match a verification record" for rel, sha in lib.items()
            if sha not in shas and not rel.startswith("Books/")]  # fmt: skip


async def _states(factory) -> list[FileState]:
    async with factory() as s:
        return list((await s.execute(select(MediaItem.state))).scalars())


async def _scenario(base: Path, kind: str, target: int | None, ref=None):
    exact = kind in EXACT
    """Run the pipeline with a Crash injected at point `target` (None: clean run), then
    restart once if it crashed. Returns (injector, cfg, factory, source sha, states at crash, engine, problems at crash)."""
    cfg = make_config(base)
    engine, factory = await make_session_factory(base)
    src = KINDS[kind](cfg.input_dir)
    original = hashlib.sha256(src.read_bytes()).hexdigest()
    inj = Injector(target)
    with pytest.MonkeyPatch.context() as m:
        inj.install(m)
        with contextlib.suppress(Crash):
            await _drive(cfg, factory)
    crash_states = await _states(factory)
    at_crash = _problems(cfg, original, crash_states, final=False, ref=ref, exact=exact)
    if target is not None:
        await _drive(cfg, factory)  # restart: a fresh process
    return inj, cfg, factory, original, crash_states, engine, at_crash


def _problems(cfg, original, states, final, ref=None, exact=True) -> list[str]:
    out = []
    held = [
        h
        for root in (cfg.input_dir, cfg.archive_dir)
        for h in (_files(root).values() if root.exists() else [])
    ]
    if held.count(original) != 1:
        out.append(
            f"source not held exactly once in input/archive: {held.count(original)}"
        )
    lib = _files(cfg.music_root.parent, exact)
    if ref is not None:
        for rel, sha in lib.items():
            if Path(rel).name.startswith("."):
                if final:
                    out.append(f"temp file left in library: {rel}")
            elif ref.get(rel) != sha:
                out.append(f"partial or unexpected library file: {rel}")
        if final and lib != ref:
            out.append(f"did not converge: {sorted(lib)} != {sorted(ref)}")
    if final:
        if len(states) != 1 or states[0] != FileState.validated:
            out.append(f"final states {states}")
        if cfg.quarantine_dir.exists() and _files(cfg.quarantine_dir):
            out.append("quarantine not empty")
    return out


@pytest.mark.parametrize("kind", sorted(KINDS))
async def test_crash_at_every_step_preserves_invariants(tmp_path, kind, monkeypatch):
    if kind == "ebook" and not all(
        shutil.which(t) for t in ("calibredb", "ebook-convert")
    ):
        pytest.skip("Calibre CLI not installed")
    monkeypatch.setenv("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")  # Calibre as root
    inj, cfg, factory, _, _, engine, _ = await _scenario(tmp_path / "ref", kind, None)
    exact = kind in EXACT
    ref = _files(cfg.music_root.parent, exact)
    assert ref and await _states(factory) == [FileState.validated]
    await engine.dispose()
    names = inj.names
    assert REQUIRED[kind] <= set(names), REQUIRED[kind] - set(names)

    failures, seen = [], set()
    for k in range(len(names)):
        _, cfg, factory, original, crash_states, engine, problems = await _scenario(
            tmp_path / f"crash{k}", kind, k, ref
        )
        seen.update(crash_states)
        problems += _problems(
            cfg, original, await _states(factory), final=True, ref=ref, exact=exact
        )
        problems += await _published_matches_record(cfg, factory)
        before = _files(cfg.music_root.parent, exact)
        await _drive(cfg, factory)  # a second restart must change nothing
        if _files(cfg.music_root.parent, exact) != before:
            problems.append("second restart changed the library")
        await engine.dispose()
        if problems:
            failures.append((k, names[k], problems))
    assert set(STAGE_ORDER) <= seen, f"never crashed in {set(STAGE_ORDER) - seen}"
    assert not failures, failures
