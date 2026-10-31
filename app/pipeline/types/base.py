"""Per-media-type strategy contract. The stage drivers in app/pipeline call these hooks;
the base implements the generic behaviour, a type overrides only where it differs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.planning import VIDEO_COPY_CODECS, is_audio_only
from app.core.verify import verify_output
from app.services.quality_guard_service import run_vmaf_ffmpeg

if TYPE_CHECKING:
    from app.core.orchestrator import PipelineOrchestrator

MIN_VMAF = 90.0


def now() -> datetime:
    return datetime.now(UTC)


def load_meta(item) -> dict:
    return json.loads(str(item.enrichment_data or "{}"))


def flag_review(item, reason: str) -> None:
    """Record why a human must look at this plan; blocks AUTO_APPROVE_TYPES."""
    meta = load_meta(item)
    meta["review"] = sorted({*meta.get("review", []), reason})
    item.enrichment_data = json.dumps(meta)


def needs_review(item) -> bool:
    meta = load_meta(item)
    return bool(meta.get("music", {}).get("needs_review") or meta.get("review"))


class MediaStrategy:
    """Default hooks = the movie/series-free generic path; `o` is the orchestrator."""

    healthcheck = True  # probe + remux-repair the source before EXECUTE

    @staticmethod
    def unit(o: PipelineOrchestrator, path) -> Path:
        """The folder whose files form one unit (album, book) and are planned together."""
        return Path(str(path)).parent

    async def classify(self, o, session, item) -> None:
        """Full classification for types recognised by extension alone (ebooks)."""
        raise NotImplementedError

    async def enrich(self, o, item) -> None:
        """Identity lookup between classify and plan; a miss keeps the file's own names."""

    async def prepare_plan(self, o, session, item) -> tuple[bool | None, str]:
        """Pre-plan work. Returns (stage result when the item is done for now | None,
        review note for the plan's execution_log)."""
        return None, ""

    async def build(
        self, o, item, plan, source: Path, tmp: Path
    ) -> tuple[int, str, Path]:
        """Produce the output at `tmp`; returns (rc, stderr, the file actually written)."""
        rc, _, err = await o._run_ffmpeg(str(source), list(plan.ffmpeg_args or []), tmp)
        return rc, err, tmp

    async def verify(self, o, item, plan, work: Path) -> tuple[list, str, str | None]:
        return await verify_output(
            str(item.source_path), str(work), is_audio_only(item), None, None
        )

    async def publish(self, o, session, item, plan, work: Path) -> bool | None:
        """Replace the file-copy publish entirely (ebooks); None = use the default."""
        return None

    async def after_publish(self, o, item, dest: Path) -> None:
        """Runs once the file is in place and the state is about to flip to published."""

    async def after_archive(self, o, session, item) -> None:
        """Runs after the item's own original has been archived."""


def video_reencoded(item, plan) -> bool:
    return not is_audio_only(item) and (
        item.video_codec not in VIDEO_COPY_CODECS
        or "libx264" in (plan.ffmpeg_args or [])
    )


async def vmaf_check(source: str, out: str, checks: list[dict]) -> str | None:
    """Sampled VMAF, only for re-encodes. No libvmaf in ffmpeg = recorded, not failed."""
    metrics = await run_vmaf_ffmpeg(source, out)
    if metrics.error:  # a measurement that broke is not "unavailable": fail loudly
        checks.append({"name": "vmaf", "passed": False, "detail": metrics.error})
        return "vmaf_failed"
    ok = metrics.vmaf is None or metrics.vmaf >= MIN_VMAF
    detail = "unavailable" if metrics.vmaf is None else f"vmaf {metrics.vmaf:.1f}"
    checks.append({"name": "vmaf", "passed": ok, "detail": detail})
    return None if ok else "quality_below_threshold"
