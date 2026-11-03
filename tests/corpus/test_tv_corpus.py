"""P4: the pipeline over a generated messy TV library with real ffmpeg and a fake TVDB. Whatever
the input, no source is lost, episodes land under {Show}/Season NN with the right code, anything
the names do not settle (no season, no episode, dated, ambiguous show) is held for review and
never published unapproved, hostile titles stay inside the library, and re-ingest is a no-op."""

import hashlib
import shutil
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.core.orchestrator import PipelineOrchestrator
from app.models.media import FileState, MediaItem, NormalizationPlan
from app.services.enrich import VideoEnricher
from tests.pipeline_helpers import (
    import_input,
    make_config,
    make_mkv,
    make_session_factory,
)

pytestmark = [pytest.mark.corpus, pytest.mark.integration, pytest.mark.asyncio]

HOSTILE_TITLE = "../../../evil: a/b\\c?"
# file name -> (published folder prefix, episode code); None = held for review
PUBLISHED = {
    "Alpha Show S01E01.mkv": ("Alpha Show", "S01E01"),
    "Alpha Show 1x02.mkv": ("Alpha Show", "S01E02"),
    "Delta Show S00E01.mkv": ("Delta Show", "S00E01"),
    "Epsilon Show S01E01-E02.mkv": ("Epsilon Show", "S01E01-E02"),
    "Hostile Show S01E03.mkv": ("Hostile Show", "S01E03"),
}
REVIEW = {
    "Gamma Show - 05.mkv",  # no season
    "Beta Daily 2024-03-05.mkv",  # dated: no season or episode
    "[SubGroup] Anime Show - 03 [1080p].mkv",  # anime absolute number, no season
    "Zeta Show S01E01.mkv",  # two shows of that name, no year: wrong-show ambiguity
}


def tvdb() -> VideoEnricher:
    """A fake TVDB: one series per name (two for Zeta), episode name from the request."""
    ids: dict[str, int] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path, q = request.url.path, request.url.params
        if path.endswith("/login"):
            return httpx.Response(200, json={"data": {"token": "t"}})
        if path.endswith("/search"):
            name = q["query"]
            hits = [
                {
                    "tvdb_id": str(ids.setdefault(name, len(ids) + 1)),
                    "name": name,
                    "year": "2020",
                }
            ]
            if name == "Zeta Show":
                hits.append({"tvdb_id": "999", "name": name, "year": "1999"})
            return httpx.Response(200, json={"data": hits})
        title = (
            HOSTILE_TITLE
            if f"/series/{ids.get('Hostile Show', -1)}/" in path
            else "Pilot"
        )
        return httpx.Response(200, json={"data": {"episodes": [{"name": title}]}})

    async def nosleep(_):
        return None

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return VideoEnricher("", "k", client=client, sleep=nosleep)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def held(cfg, digest: str) -> int:
    return sum(
        sha(p) == digest
        for root in (cfg.input_dir, cfg.archive_dir, cfg.quarantine_dir)
        if root.exists()
        for p in root.rglob("*")
        if p.is_file()
    )


async def states(factory) -> dict[str, FileState]:
    async with factory() as s:
        return {
            Path(str(i.source_path)).name: i.state
            for i in (await s.execute(select(MediaItem))).scalars()
        }


async def drive(orch, factory) -> None:
    """Approve what is not held for review, as an operator would."""
    await orch.run_until_idle()
    async with factory() as s:
        planned = (
            await s.execute(select(MediaItem).where(MediaItem.state == FileState.planned))
        ).scalars().all()  # fmt: skip
    for item in planned:
        if not orch._needs_review(item):
            await orch.approve(str(item.id))
    await orch.run_until_idle()


async def test_messy_tv_library_converges_without_loss_or_junk(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    cfg = make_config(tmp_path, enabled_types=frozenset({"series"}))
    engine, factory = await make_session_factory(tmp_path)
    pristine = tmp_path / "pristine"
    pristine.mkdir()
    # one distinct duration per file keeps the duplicate-fingerprint check from merging them
    made = [
        make_mkv(pristine / name, seconds=2 + n)
        for n, name in enumerate([*PUBLISHED, *sorted(REVIEW)])
    ]
    sources = {p.name: sha(p) for p in made}
    shutil.copytree(pristine, cfg.input_dir, dirs_exist_ok=True)
    await import_input(cfg, factory)
    orch = PipelineOrchestrator(factory, cfg, enricher=tvdb())
    await drive(orch, factory)

    # no source is lost: archived after verify, quarantined, or still in input
    assert [n for n, d in sources.items() if held(cfg, d) < 1] == []
    out = {p.name: p for p in cfg.tv_root.rglob("*.mkv")}
    # every episode is filed as {Show} (year) {tvdb-N}/Season NN/{Show} - SxxEyy - {title}.mkv
    for source, (show, code) in PUBLISHED.items():
        season = f"Season {code[1:3]}"
        found = [
            p for p in out.values()
            if p.parent.name == season and p.parent.parent.name.startswith(f"{show} (2020)")
            and f"- {code}" in p.name
        ]  # fmt: skip
        assert len(found) == 1, (source, tree(cfg.tv_root), await states(factory))
    # a hostile provider title is sanitised and stays under the TV root
    root = cfg.tv_root.resolve()
    assert all(p.resolve().is_relative_to(root) for p in out.values())
    assert len(out) == len(PUBLISHED), tree(cfg.tv_root)
    # nothing unsettled is published: held for review, source untouched in input
    st = await states(factory)
    assert {n: st[n] for n in REVIEW} == dict.fromkeys(REVIEW, FileState.planned)
    assert all((cfg.input_dir / n).is_file() for n in REVIEW)
    async with factory() as s:
        notes = [
            str(p.execution_log)
            for p in (await s.execute(select(NormalizationPlan))).scalars()
            if "Season" not in str(p.target_path).split("(")[0]
        ]
    assert sum("review_required" in n for n in notes) >= len(REVIEW)

    # idempotence: the sources dropped again under other names, and the library fed back in
    before = tree(cfg.tv_root)
    for n, p in enumerate(pristine.iterdir()):
        shutil.copy(p, cfg.input_dir / f"renamed {n}.mkv")
    shutil.copytree(cfg.tv_root, cfg.input_dir / "reingest")
    await import_input(cfg, factory)
    await drive(orch, factory)
    assert tree(cfg.tv_root) == before
    await engine.dispose()
