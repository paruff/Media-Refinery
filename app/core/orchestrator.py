"""Drives every MediaItem through spec §4: scan → classify → plan → approve →
execute → verify → publish → archive. State is committed before side effects (R-PIPE-1)."""

import asyncio
import json
import logging
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.paths import ensure_inside
from app.core.planning import IMAGE_SUBS, VIDEO_COPY_CODECS, build_plan, is_audio_only
from app.core.publish import archive_original, publish_file, quarantine_file
from app.core.scanner import ScannerService
from app.core.throttle import AdaptiveLimiter
from app.core.tools import probe_duration, run_tool
from app.core.trace import Status, TraceWriter
from app.core.verify import sha256_file, verify_ebook, verify_output
from app.media import ebook
from app.media.audiobook import (
    book_dir,
    concat_list,
    describe_book,
    ffmetadata,
    natural_key,
    tag_m4b,
)
from app.media.video.convert import convert_video
from app.media.video.health import health_check, repair_remux
from app.models.media import (
    FileState,
    MediaItem,
    MediaType,
    NormalizationPlan,
    PlanStatus,
    VerificationRecord,
)
from app.models.saga import SagaFileMoveLog, SagaLogStatus
from app.services.music_id import local_cover, write_album_cover
from app.services.notify import Notifier
from app.services.quality_guard_service import run_vmaf_ffmpeg
from app.services.replaygain import measure
from app.services.tagging_service import TaggingService

MIN_VMAF = 90.0
STAGE_ORDER = (
    FileState.pending,
    FileState.scanned,
    FileState.enriched,
    FileState.planned,
    FileState.approved,
    FileState.executed,
    FileState.verified,
    FileState.published,
)
ACTIONABLE = (
    FileState.pending,
    FileState.scanned,
    FileState.enriched,
    FileState.planned,
    FileState.approved,
    FileState.executed,
    FileState.verified,
    FileState.published,
)


@dataclass
class PipelineConfig:
    input_dir: Path
    work_dir: Path
    archive_dir: Path
    quarantine_dir: Path
    music_root: Path
    movies_root: Path
    tv_root: Path
    audiobooks_root: Path
    ebooks_root: Path  # the Calibre library
    ebook_fetch: bool = False
    dry_run: bool = False
    auto_approve_types: frozenset[str] = field(default_factory=frozenset)
    ffmpeg_timeout: float = 6 * 3600
    max_concurrent_execute: int = 2  # CPU-heavy stage bounded separately (R-PIPE-5)
    max_concurrent_io: int = 5
    throttle_after_failures: int = 2  # consecutive EXECUTE failures that halve workers
    trace_path: Path | None = None  # JSONL trace (NF-4); default work/trace.jsonl

    @classmethod
    def from_settings(cls) -> PipelineConfig:
        return cls(
            input_dir=Path(settings.INPUT_DIR),
            work_dir=Path(settings.WORK_DIR),
            archive_dir=Path(settings.ARCHIVE_DIR),
            quarantine_dir=Path(settings.QUARANTINE_DIR),
            music_root=Path(settings.MUSIC_ROOT),
            movies_root=Path(settings.MOVIES_ROOT),
            tv_root=Path(settings.TV_ROOT),
            audiobooks_root=Path(settings.AUDIOBOOKS_ROOT),
            ebooks_root=Path(settings.CALIBRE_LIBRARY),
            ebook_fetch=settings.EBOOK_FETCH_METADATA,
            trace_path=Path(settings.LOG_DIR) / "trace.jsonl",
            dry_run=settings.DRY_RUN,
            auto_approve_types=frozenset(settings.AUTO_APPROVE_TYPES),
        )

    @property
    def roots(self) -> dict[str, str]:
        return {
            "music": str(self.music_root),
            "movie": str(self.movies_root),
            "series": str(self.tv_root),
            "audiobook": str(self.audiobooks_root),
            "ebook": str(self.ebooks_root),
        }

    def root_for(self, media_type) -> Path:
        return {
            MediaType.music: self.music_root,
            MediaType.movie: self.movies_root,
            MediaType.series: self.tv_root,
            MediaType.audiobook: self.audiobooks_root,
            MediaType.ebook: self.ebooks_root,
        }[MediaType(media_type)]


def _preflight(source: Path, target: Path, root: Path) -> list[dict]:
    """Dry-run checks that touch the filesystem (read-only)."""
    checks = [{"name": "source_readable", "passed": source.is_file()}]
    try:
        ensure_inside(root, target)
        checks.append({"name": "target_confined", "passed": True})
    except ValueError as e:
        checks.append({"name": "target_confined", "passed": False, "detail": str(e)})
    checks.append({"name": "target_free", "passed": not target.exists()})
    return checks


def _now() -> datetime:
    return datetime.now(UTC)


class PipelineOrchestrator:
    def __init__(
        self,
        session_factory,
        config: PipelineConfig,
        logger=None,
        poll_interval=2,
        enricher=None,
        identifier=None,
        notifier=None,
    ):
        self.session_factory = session_factory
        self.cfg = config
        self.enricher = (
            enricher  # VideoEnricher (TMDB/TVDB) or None = guessit names only
        )
        self.identifier = (
            identifier  # MusicIdentifier (AcoustID/MB) or None = tags only
        )
        self.notifier = notifier or Notifier()
        self.logger = logger or logging.getLogger("PipelineOrchestrator")
        self.poll_interval = poll_interval
        self.run_id = (
            datetime.now(UTC).strftime("%Y%m%dT%H%M%S-") + uuid.uuid4().hex[:6]
        )
        self.running = False
        self._io = asyncio.Semaphore(config.max_concurrent_io)
        self._exec = AdaptiveLimiter(
            config.max_concurrent_execute, config.throttle_after_failures
        )
        trace_path = config.trace_path or config.work_dir / "trace.jsonl"
        if config.dry_run:  # R-SAFE-4: dry-run writes only under work/dry-run/
            trace_path = config.work_dir / "dry-run" / "trace.jsonl"
        self.trace = TraceWriter(trace_path, self.run_id)
        self._scanner = ScannerService(session_factory, logger=self.logger)
        self._album_lock = asyncio.Lock()
        self._calibre_lock = asyncio.Lock()  # one calibredb writer per library
        self._album_gain: dict[Path, tuple[str, str] | None] = {}

    # ---- loop -----------------------------------------------------------
    async def run_forever(self):
        self.running = True
        await self.recover()
        while self.running:
            try:
                await self.run_once()
            except Exception:
                self.logger.exception("Orchestrator pass failed")
            await asyncio.sleep(self.poll_interval)

    async def run_once(
        self,
        until: FileState | None = None,
        only: set[str] | None = None,
        types: set[str] | None = None,
    ) -> int:
        """Advance every actionable item by one stage; return how many moved.

        `until` leaves items already at that stage alone, `only` limits to item ids
        and `types` to media types (unclassified items still pass, to get classified).
        """
        async with self.session_factory() as session:
            result = await session.execute(
                select(MediaItem.id, MediaItem.state, MediaItem.media_type).where(
                    MediaItem.state.in_(ACTIONABLE)
                )
            )
            rows = result.all()
        stop = STAGE_ORDER.index(until) if until else len(STAGE_ORDER)
        if (
            self.cfg.dry_run
        ):  # R-SAFE-4: never act past planning, whatever state the DB is in
            stop = min(stop, STAGE_ORDER.index(FileState.approved))
        todo = [
            (i, s)
            for i, s, t in rows
            if STAGE_ORDER.index(s) < stop
            and (only is None or i in only)
            and (not types or t == MediaType.unknown or t.value in types)
        ]
        moved = await asyncio.gather(*(self._guarded(i, s) for i, s in todo))
        return sum(moved)

    async def run_until_idle(self, max_passes: int = 100, **filters) -> None:
        for _ in range(max_passes):
            if not await self.run_once(**filters):
                return

    # ---- crash resume (R-PIPE-1) -----------------------------------------
    async def recover(self) -> None:
        """Reset items caught mid-flight and drop half-finished publish temp files."""
        if self.cfg.dry_run:  # R-SAFE-4: recovery deletes work files and rewrites sagas
            return
        async with self.session_factory() as session:
            for item in await self._items(session, FileState.scanning):
                item.state = FileState.pending
            for item in await self._items(session, FileState.executing):
                item.state = FileState.approved
                shutil.rmtree(self.cfg.work_dir / str(item.id), ignore_errors=True)
            sagas = await session.execute(
                select(SagaFileMoveLog).where(
                    SagaFileMoveLog.status == SagaLogStatus.prepared
                )
            )
            for log in sagas.scalars():
                await asyncio.to_thread(Path(str(log.tmp_path)).unlink, missing_ok=True)
                log.status = SagaLogStatus.failed
                log.error = "recovered after crash"
            await session.commit()

    async def _items(self, session, state):
        result = await session.execute(
            select(MediaItem).where(MediaItem.state == state)
        )
        return result.scalars().all()

    # ---- approval gate ----------------------------------------------------
    async def approve(self, item_id: str) -> bool:
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            if item is None or item.state != FileState.planned:
                return False
            plan = await self._plan(session, item_id)
            plan.plan_status = PlanStatus.approved
            item.state = FileState.approved
            item.updated_at = _now()
            await session.commit()
            return True

    async def reject(self, item_id: str) -> bool:
        """A reviewer declines a plan: nothing is touched, the item parks in quarantine."""
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            if item is None or item.state != FileState.planned:
                return False
            await self._quarantine(session, item, "rejected", "declined at review")
            return True

    async def retry(self, item_id: str) -> bool:
        """Re-queue a failed/quarantined item from the start; its source must still exist."""
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            if item is None or item.state not in (
                FileState.error,
                FileState.quarantined,
            ):
                return False
            if not await asyncio.to_thread(Path(str(item.source_path)).is_file):
                return False
            plan = await session.execute(
                select(NormalizationPlan).where(
                    NormalizationPlan.media_item_id == item_id
                )
            )
            if (old := plan.scalar_one_or_none()) is not None:
                await session.delete(old)
            item.state, item.error_log, item.updated_at = (
                FileState.pending,
                None,
                _now(),
            )
            await session.commit()
        shutil.rmtree(self.cfg.work_dir / item_id, ignore_errors=True)
        return True

    # ---- dispatch -----------------------------------------------------------
    async def _guarded(self, item_id, state) -> bool:
        sem = self._exec if state == FileState.approved else self._io
        async with sem:
            try:
                return await self._advance(item_id, state)
            except Exception as e:
                self.logger.exception(f"Pipeline failed for {item_id}")
                if state == FileState.approved:
                    self._record_execute(False)
                await self._mark(item_id, FileState.error, str(e))
                return True

    async def _advance(self, item_id, state) -> bool:
        handlers = {
            FileState.pending: self._scan,
            FileState.scanned: self._classify,
            FileState.enriched: self._plan_stage,
            FileState.planned: self._gate,
            FileState.approved: self._execute,
            FileState.executed: self._verify,
            FileState.verified: self._publish,
            FileState.published: self._archive,
        }
        return await handlers[state](item_id)

    def _record_execute(self, ok: bool) -> None:
        """Feed the adaptive throttle; trace when it halves the EXECUTE workers."""
        if (limit := self._exec.record(ok)) is not None:
            self.logger.warning(f"EXECUTE failures: reducing workers to {limit}")
            self.trace.emit("workers.throttle", "", "degraded", f"new_workers={limit}")

    def _emit(self, event: str, item_id, status: Status, detail: str = "") -> None:
        self.trace.emit(event, str(item_id), status, detail)

    async def _mark(self, item_id, state, error=None):
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            if item is not None:
                item.state = state
                item.error_log = error
                item.updated_at = _now()
                await session.commit()

    async def _plan(self, session, item_id) -> NormalizationPlan:
        result = await session.execute(
            select(NormalizationPlan).where(NormalizationPlan.media_item_id == item_id)
        )
        return result.scalar_one()

    async def _quarantine(
        self, session, item, reason, detail, file: Path | None = None
    ):
        if file is not None:
            await asyncio.to_thread(
                quarantine_file, file, self.cfg.quarantine_dir, reason, str(item.id)
            )
        plan = await self._plan(session, str(item.id))
        plan.plan_status = PlanStatus.failed
        item.state = FileState.quarantined
        item.error_log = f"{reason}: {detail}"
        item.updated_at = _now()
        shutil.rmtree(self.cfg.work_dir / str(item.id), ignore_errors=True)
        await session.commit()
        self.logger.warning(f"Quarantined {item.id} ({reason}): {detail}")
        self._emit("quarantine", item.id, "success", reason)

    def _work(self, item_id, ext="") -> Path:
        return self.cfg.work_dir / str(item_id) / f"out{ext}"

    # ---- stages -------------------------------------------------------------
    async def _scan(self, item_id) -> bool:
        await self._scanner.run(item_id)  # ends in scanned or error
        return True

    async def _classify(self, item_id) -> bool:
        from app.services.classification import ClassificationService

        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            if ebook.is_ebook(str(item.source_path)):
                await self._classify_ebook(session, item)
                return True
            await ClassificationService(session).classify_file(item_id)  # type: ignore[arg-type]
            await session.refresh(item)
            if (
                item.media_type == MediaType.unknown
            ):  # R-PIPE-4: audio ⇒ music, else movie
                item.media_type = (
                    MediaType.music if is_audio_only(item) else MediaType.movie
                )
            if item.media_type == MediaType.series:
                data = json.loads(str(item.enrichment_data or "{}"))
                if data.get("season_number") is None or not data.get("episode_number"):
                    self._flag_review(item, "season_or_episode_unknown")
            if self.enricher and item.media_type in (MediaType.movie, MediaType.series):
                await self._enrich(item)
            if item.media_type == MediaType.music:
                await self._identify(item)
            item.state = FileState.enriched
            await session.commit()
        return True

    async def _classify_ebook(self, session, item) -> None:
        """R-EBOOK-4 DRM -> quarantine/drm, never processed; R-EBOOK-2 metadata."""
        source = Path(str(item.source_path))
        item.media_type = MediaType.ebook
        if drm := await asyncio.to_thread(ebook.detect_drm, source):
            await asyncio.to_thread(
                quarantine_file, source, self.cfg.quarantine_dir, "drm", str(item.id)
            )
            item.state, item.error_log = FileState.quarantined, f"drm: {drm}"
            self._emit("quarantine", item.id, "success", "drm")
            await session.commit()
            return
        meta = await ebook.read_meta(source)
        if self.cfg.ebook_fetch:
            fetched = await ebook.fetch_meta(meta)
            self._emit("enrich", item.id, "success" if fetched else "skipped")
            meta = ebook.merge_meta(meta, fetched)  # embedded values win
        ext = source.suffix.lstrip(".").lower()
        meta["title"] = meta.get("title") or source.stem
        meta["authors"] = meta.get("authors") or ["Unknown"]
        meta["format"], meta["convert"] = "epub" if ext != "pdf" else ext, ext != "epub"
        item.enrichment_data = json.dumps({"ebook": meta})
        item.state = FileState.enriched
        await session.commit()

    async def _enrich(self, item) -> None:
        """TMDB (movies) / TVDB (series) identity; a miss keeps the guessit names."""
        meta = json.loads(str(item.enrichment_data or "{}"))
        if item.media_type == MediaType.movie:
            year = meta.get("year")
            match = await self.enricher.movie(meta.get("title", ""), year)
            if match:
                item.tmdb_id, item.canonical_title = match.tmdb_id, match.title
                item.release_year = match.year or year
                if not match.confident:
                    self._flag_review(item, "ambiguous_match")
        else:
            match = await self.enricher.episode(
                meta.get("series_title", ""),
                meta.get("year"),
                int(meta.get("season_number") or 0),
                int(meta.get("episode_number") or 0),
            )
            if match:
                item.canonical_series_name, item.release_year = match.show, match.year
                item.episode_title = match.episode_title
                meta["tvdb_id"] = match.tvdb_id
                item.enrichment_data = json.dumps(meta)
                if not match.confident:
                    self._flag_review(item, "ambiguous_match")
        self._emit(
            "enrich",
            item.id,
            "success" if match else "skipped",
            "no_match" if not match else "",
        )

    async def _identify(self, item) -> None:
        """R-MUSIC-5: AcoustID -> MusicBrainz tags. Below the threshold (or no match) the
        embedded tags stay and the plan needs a human."""
        meta = json.loads(str(item.enrichment_data or "{}"))
        tags = {
            "artist": item.artist,
            "album": item.album,
            "title": item.title or meta.get("track_title"),
            "year": item.year,
            "track_number": meta.get("track_number"),
        }
        tags = {k: v for k, v in tags.items() if v}
        found = (
            await self.identifier.identify(str(item.source_path))
            if self.identifier
            else None
        )
        review = self.identifier is not None and (
            found is None or found[0] < self.identifier.threshold
        )
        if found and not review:
            tags.update(found[1])
            item.album_artist, item.album_name = tags["album_artist"], tags["album"]
            item.release_year = int(tags["year"]) if tags.get("year") else None
            item.disc_number = tags["disc_number"]
            item.mbid, item.release_mbid = (
                tags["musicbrainz_trackid"],
                tags["musicbrainz_albumid"],
            )
        meta["music"] = {
            "tags": tags,
            "score": found[0] if found else None,
            "needs_review": review,
        }
        item.enrichment_data = json.dumps(meta)
        if self.identifier:
            self._emit(
                "identify",
                item.id,
                "degraded" if review else "success",
                "low_confidence" if found and review else "no_match" if review else "",
            )

    async def _album_pending(self, session, item) -> bool:
        """Album-as-unit: hold until every sibling in the same folder has been classified."""
        unit = self._unit
        if item.media_type == MediaType.audiobook:  # a book spans disc subfolders
            unit = lambda p: book_dir(p, self.cfg.input_dir)  # noqa: E731
        folder = unit(str(item.source_path))
        rows = await session.execute(
            select(MediaItem.source_path).where(
                MediaItem.state.in_(
                    (FileState.pending, FileState.scanning, FileState.scanned)
                )
            )
        )
        return any(unit(p) == folder for (p,) in rows)

    @staticmethod
    def _unit(path) -> Path:
        return Path(str(path)).parent

    async def _plan_book(self, session, item) -> bool | None:
        """R-BOOK-5: the first file (natural order) carries the whole book; the rest follow it.
        Returns a stage result when this item is done for now, None to plan the book."""
        if await self._album_pending(session, item):
            return False
        unit = book_dir(str(item.source_path), self.cfg.input_dir)
        rows = await session.execute(
            select(MediaItem).where(MediaItem.media_type == MediaType.audiobook)
        )
        members = sorted(
            (
                m
                for m in rows.scalars()
                if book_dir(str(m.source_path), self.cfg.input_dir) == unit
            ),
            key=lambda m: natural_key(str(m.source_path)),
        )
        lead = members[0]
        if lead.id != item.id:
            if lead.state in (FileState.error, FileState.quarantined):
                item.state = FileState.quarantined
                item.error_log = f"book_failed: {lead.id}"
                await session.commit()
                return True
            return False
        meta = json.loads(str(item.enrichment_data or "{}"))
        meta["book"] = await describe_book(
            [Path(str(m.source_path)) for m in members], unit.name
        )
        meta["book"]["members"] = [m.id for m in members[1:]]
        item.enrichment_data = json.dumps(meta)
        return None

    async def _replaygain(self, session, item, meta) -> None:
        """R-MUSIC-2: track gain from the item, album gain from the folder played as one."""
        tags = meta["music"]["tags"]
        track = await measure([Path(str(item.source_path))])
        folder = Path(str(item.source_path)).parent
        async with self._album_lock:
            if folder not in self._album_gain:
                rows = await session.execute(
                    select(MediaItem.source_path).where(
                        MediaItem.media_type == MediaType.music,
                        MediaItem.state == FileState.enriched,
                    )
                )
                # ponytail: folder = album; a late arrival reuses the first measurement
                siblings = sorted(Path(p) for (p,) in rows if Path(p).parent == folder)
                self._album_gain[folder] = await measure(siblings)
        album = self._album_gain[folder]
        if track and album:
            tags.update(
                replaygain_track_gain=track[0],
                replaygain_track_peak=track[1],
                replaygain_album_gain=album[0],
                replaygain_album_peak=album[1],
            )
        else:
            self._emit("replaygain", item.id, "skipped", "ffmpeg could not measure")

    async def _probe_streams(self, source: str) -> list[dict]:
        rc, out, _ = await run_tool(
            ["ffprobe", "-v", "error", "-show_streams", "-of", "json", source], 120
        )
        try:
            return json.loads(out).get("streams", []) if rc == 0 else []
        except ValueError:
            return []

    async def _plan_stage(self, item_id) -> bool:
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            review = ""
            if item.media_type == MediaType.audiobook:
                done = await self._plan_book(session, item)
                if done is not None:
                    return done
            if item.media_type == MediaType.music:
                if await self._album_pending(session, item):
                    return False
                meta = json.loads(str(item.enrichment_data or "{}"))
                await self._replaygain(session, item, meta)
                item.enrichment_data = json.dumps(meta)
                if meta["music"]["needs_review"]:
                    score = meta["music"]["score"]
                    review = f"review_required: match score {score}"
                    self._emit("review", item_id, "degraded", review)
            if item.media_type == MediaType.ebook:
                await self._flag_ebook_duplicate(item)
            if flags := json.loads(str(item.enrichment_data or "{}")).get("review"):
                review = f"review_required: {', '.join(flags)}"
                self._emit("review", item_id, "degraded", review)
            streams = (
                []
                if is_audio_only(item)
                else await self._probe_streams(str(item.source_path))
            )
            if any(s.get("codec_name") in IMAGE_SUBS for s in streams):
                self._emit("subtitle.image", item_id, "flagged", "kept_as_is")
            try:
                spec = build_plan(item, self.cfg.roots, streams)
            except ValueError as e:
                item.state, item.error_log = FileState.error, str(e)
                await session.commit()
                return True
            clash = await session.execute(
                select(NormalizationPlan.id).where(
                    NormalizationPlan.target_path == spec.target_path
                )
            )
            if clash.first():
                item.state, item.error_log = (
                    FileState.quarantined,
                    f"plan_conflict: {spec.target_path}",
                )
                await session.commit()
                return True
            session.add(
                NormalizationPlan(
                    media_item_id=item.id,
                    target_path=spec.target_path,
                    ffmpeg_args=spec.ffmpeg_args,
                    original_hash=str(item.id),
                    needs_transcode=spec.needs_transcode,
                    needs_rename=True,
                    execution_log=review,
                )
            )
            item.state = FileState.planned
            await session.commit()
        return True

    async def _flag_ebook_duplicate(self, item) -> None:
        """R-PIPE-7: a book already in Calibre is a plan decision: approve keeps both, reject skips."""
        meta = json.loads(str(item.enrichment_data or "{}"))
        dup = await ebook.find_duplicate(self.cfg.ebooks_root, meta.get("ebook", {}))
        if dup is None:
            return
        meta["ebook"].update(allow_duplicate=True, duplicate_of=dup)
        item.enrichment_data = json.dumps(meta)
        self._flag_review(item, "duplicate_ebook")

    async def _gate(self, item_id) -> bool:
        """APPROVE gate: dry-run reports; opt-in rules approve; otherwise wait for a human."""
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            media_type = str(MediaType(item.media_type).value)
        if self.cfg.dry_run:
            return await self._dry_run_report(item_id)
        if media_type in self.cfg.auto_approve_types and not self._needs_review(item):
            return await self.approve(item_id)
        return False

    @staticmethod
    def _needs_review(item) -> bool:
        meta = json.loads(str(item.enrichment_data or "{}"))
        return bool(meta.get("music", {}).get("needs_review") or meta.get("review"))

    @staticmethod
    def _flag_review(item, reason: str) -> None:
        """Record why a human must look at this plan; blocks AUTO_APPROVE_TYPES."""
        meta = json.loads(str(item.enrichment_data or "{}"))
        meta["review"] = sorted({*meta.get("review", []), reason})
        item.enrichment_data = json.dumps(meta)

    async def _dry_run_report(self, item_id) -> bool:
        """Plan + verify-preflight; the only writes are under work/dry-run/ (R-SAFE-4)."""
        report_path = self.cfg.work_dir / "dry-run" / f"{item_id}.json"
        if report_path.exists():
            return False
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            plan = await self._plan(session, item_id)
            target, source = Path(str(plan.target_path)), Path(str(item.source_path))
            checks = await asyncio.to_thread(
                _preflight, source, target, self.cfg.root_for(item.media_type)
            )
            duration = await probe_duration(str(source))
            checks.append({"name": "source_probe", "passed": duration is not None})
            report = {
                "item_id": item_id,
                "source": str(source),
                "target": str(target),
                "ffmpeg_args": plan.ffmpeg_args,
                "needs_transcode": plan.needs_transcode,
                "preflight": checks,
            }

        def write():
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2))

        await asyncio.to_thread(write)
        self._emit("plan", item_id, "dry_run", report["target"])
        return True

    async def _run_ffmpeg(self, source: str, args: list[str], out: Path):
        return await run_tool(
            ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", source, *args, str(out)],
            self.cfg.ffmpeg_timeout,
        )

    @staticmethod
    def _is_video_reencode(item) -> bool:
        """Legacy-codec video (MPEG-1/2, WMV, XviD...) goes through the converter engine."""
        return not is_audio_only(item) and item.video_codec not in VIDEO_COPY_CODECS

    async def _convert_video(self, item, source: Path, out: Path) -> tuple[int, str]:
        def on_event(event: str, status: Status, detail: str) -> None:
            self._emit(event, item.id, status, detail)

        try:
            await asyncio.to_thread(
                convert_video, source, out, out.parent / "repair", on_event=on_event
            )
        except subprocess.CalledProcessError as e:
            return 1, f"{e}\n{e.stderr or ''}".strip()
        except Exception as e:
            return 1, str(e)
        return 0, ""

    async def _execute(self, item_id) -> bool:
        if self.cfg.dry_run:
            return False
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            plan = await self._plan(session, item_id)
            ext = Path(str(plan.target_path)).suffix
            item.state, plan.plan_status = FileState.executing, PlanStatus.executing
            await session.commit()  # persisted before any side effect
            work = self._work(item_id, ext)
            shutil.rmtree(work.parent, ignore_errors=True)
            work.parent.mkdir(parents=True)
            tmp = work.with_name(
                f"out.tmp{ext}"
            )  # ffmpeg infers the container from the suffix
            source = Path(str(item.source_path))
            if item.media_type != MediaType.ebook and not is_audio_only(item):
                healthy, detail = await asyncio.to_thread(health_check, source)
                self._emit(
                    "healthcheck", item_id, "passed" if healthy else "failed", detail
                )
                if detail == "healthcheck_timeout":
                    # inconclusive: do not call good media corrupt; VERIFY checks the output
                    self._emit("healthcheck", item_id, "inconclusive", detail)
                elif not healthy:  # remux-repair fallback, else quarantine the original
                    repaired = await asyncio.to_thread(
                        repair_remux, source, work.parent / "repair"
                    )
                    self._emit(
                        "repair",
                        item_id,
                        "success" if repaired else "failed",
                        "remux_to_mkv",
                    )
                    if repaired is None:
                        # bad input is not resource pressure: don't feed the throttle
                        await self._quarantine(
                            session, item, "healthcheck_failed", detail, source
                        )
                        return True
                    source = repaired
            self._emit("execute", item_id, "started")
            if item.media_type == MediaType.ebook:
                rc, err, tmp = await self._build_ebook(item, source, tmp)
                if (
                    rc == 0 and tmp.suffix == ".pdf"
                ):  # kept as PDF: plan follows the file
                    plan.target_path = str(
                        Path(str(plan.target_path)).with_suffix(".pdf")
                    )
                    work = self._work(item_id, ".pdf")
            elif item.media_type == MediaType.audiobook:
                rc, err = await self._build_book(item, plan, tmp)
            elif plan.needs_transcode and self._is_video_reencode(item):
                rc, err = await self._convert_video(item, source, tmp)  # smart bitrate
            else:
                rc, _, err = await self._run_ffmpeg(
                    str(source), list(plan.ffmpeg_args or []), tmp
                )
            if rc == 0 and item.media_type == MediaType.music:
                rc, err = await self._tag_music(item, source, tmp)
            plan.execution_log = f"{plan.execution_log}\nffmpeg rc={rc}\n{err}".strip()
            if rc != 0:
                tmp.unlink(missing_ok=True)
                await self._quarantine(
                    session, item, "convert_failed", err.strip()[:500]
                )
                self._record_execute(False)
                return True
            tmp.replace(work)
            item.state = FileState.executed
            await session.commit()
            self._emit("execute", item_id, "success")
            self._record_execute(True)
        return True

    async def _build_ebook(self, item, source: Path, out: Path):
        """R-EBOOK-1: EPUB 3 via ebook-convert; scanned-image PDFs stay PDF and are flagged."""
        await ebook.extract_cover(source, out.with_name("cover.jpg"))
        rc, err = await ebook.to_epub(source, out)
        if (
            rc == 0
            and source.suffix.lower() == ".pdf"
            and (
                await asyncio.to_thread(ebook.epub_text_length, out)
                < ebook.MIN_PDF_TEXT
            )
        ):
            self._emit("ebook.scanned_pdf", item.id, "flagged", "kept_as_pdf")
            await asyncio.to_thread(out.unlink)
            out = out.with_suffix(".pdf")
            await asyncio.to_thread(shutil.copyfile, source, out)
        return rc, err, out

    async def _build_book(self, item, plan, out: Path) -> tuple[int, str]:
        """R-BOOK-1/2/3/5: concat the files in order, embed chapters, AAC M4B, tags + cover."""
        book = json.loads(str(item.enrichment_data))["book"]
        listing, chapters = out.with_name("files.txt"), out.with_name("chapters.ffmeta")
        listing.write_text(concat_list(book["files"]))
        chapters.write_text(ffmetadata(book["chapters"]))
        rc, _, err = await run_tool(
            [
                *("ffmpeg", "-nostdin", "-y", "-v", "error"),
                *("-f", "concat", "-safe", "0", "-i", str(listing)),
                *("-i", str(chapters), "-map", "0:a", "-map_metadata", "1"),
                *("-map_chapters", "1", *(plan.ffmpeg_args or [])),
                *("-f", "ipod", str(out)),
            ],
            self.cfg.ffmpeg_timeout,
        )
        if rc != 0:
            return rc, err
        cover = next(
            filter(
                None, [await asyncio.to_thread(local_cover, f) for f in book["files"]]
            ),
            None,
        )
        if cover is None:
            self._emit("cover", item.id, "skipped", "no usable cover (>=500px)")
        await asyncio.to_thread(tag_m4b, out, book, cover)
        return 0, ""

    async def _tag_music(self, item, source: Path, out: Path) -> tuple[int, str]:
        """R-MUSIC-2/3: write the tag map and the embedded front cover into the output."""
        meta = json.loads(str(item.enrichment_data or "{}"))["music"]
        cover = await (
            self.identifier.cover(str(source), item.release_mbid)
            if self.identifier
            else asyncio.to_thread(local_cover, source)
        )
        if cover is None:
            self._emit("cover", item.id, "skipped", "no usable cover (>=500px)")
        tags = {**meta["tags"], "cover": cover}
        # tags from an identified release replace the file's; otherwise merge into them
        clean = item.release_mbid is not None
        if not await asyncio.to_thread(
            TaggingService().apply_tags, str(out), tags, clean
        ):
            return 1, "tagging failed"
        return 0, ""

    @staticmethod
    def _video_reencoded(item, plan) -> bool:
        return not is_audio_only(item) and (
            item.video_codec not in VIDEO_COPY_CODECS
            or "libx264" in (plan.ffmpeg_args or [])
        )

    async def _vmaf_check(
        self, source: str, out: str, checks: list[dict]
    ) -> str | None:
        """Sampled VMAF, only for re-encodes. No libvmaf in ffmpeg = recorded, not failed."""
        metrics = await run_vmaf_ffmpeg(source, out)
        ok = metrics.vmaf is None or metrics.vmaf >= MIN_VMAF
        detail = "unavailable" if metrics.vmaf is None else f"vmaf {metrics.vmaf:.1f}"
        checks.append({"name": "vmaf", "passed": ok, "detail": detail})
        return None if ok else "quality_below_threshold"

    async def _verify(self, item_id) -> bool:
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            plan = await self._plan(session, item_id)
            work = self._work(item_id, Path(str(plan.target_path)).suffix)
            if not work.exists():  # lost between stages: redo the conversion
                item.state, plan.plan_status = FileState.approved, PlanStatus.approved
                await session.commit()
                return True
            book = (
                json.loads(str(item.enrichment_data))["book"]
                if item.media_type == MediaType.audiobook
                else None
            )
            if item.media_type == MediaType.ebook:
                checks, digest, reason = await verify_ebook(str(work))
            else:
                checks, digest, reason = await verify_output(
                    str(item.source_path),
                    str(work),
                    is_audio_only(item),
                    book["duration"] if book else None,
                    len(book["chapters"]) if book else None,
                )
            if reason is None and self._video_reencoded(item, plan):
                reason = await self._vmaf_check(
                    str(item.source_path), str(work), checks
                )
            session.add(
                VerificationRecord(
                    media_item_id=item_id,
                    passed=reason is None,
                    checks=checks,
                    output_sha256=digest,
                )
            )
            self._emit(
                "verify", item_id, "failed" if reason else "passed", reason or ""
            )
            if reason:
                detail = "; ".join(
                    f"{c['name']}: {c['detail']}" for c in checks if not c["passed"]
                )
                await self._quarantine(session, item, reason, detail, work)
            else:
                item.state = FileState.verified
                await session.commit()
        return True

    async def _publish(self, item_id) -> bool:
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            plan = await self._plan(session, item_id)
            dest = ensure_inside(
                self.cfg.root_for(item.media_type), str(plan.target_path)
            )
            work = self._work(item_id, dest.suffix)
            record = (
                (
                    await session.execute(
                        select(VerificationRecord)
                        .where(
                            VerificationRecord.media_item_id == item_id,
                            VerificationRecord.passed,
                        )
                        .order_by(VerificationRecord.created_at.desc())
                    )
                )
                .scalars()
                .first()
            )
            if record is None:
                raise RuntimeError("verified item has no passing VerificationRecord")
            sha = str(record.output_sha256)
            if item.media_type == MediaType.ebook:
                return await self._publish_ebook(session, item, plan, work)
            if dest.exists():
                if await asyncio.to_thread(sha256_file, str(dest)) != sha:
                    await self._quarantine(
                        session, item, "target_exists", str(dest), work
                    )
                    return True
                # resumed after a crash that landed the file but not the state
            else:
                await publish_file(session, str(plan.id), work, dest, sha)
            if item.media_type == MediaType.music:
                await asyncio.to_thread(write_album_cover, dest)
            item.state = FileState.published
            await session.commit()
            self._emit("publish", item_id, "success", str(dest))
        await self.notifier.published(str(item.media_type), dest)  # non-fatal
        return True

    async def _publish_ebook(self, session, item, plan, work: Path) -> bool:
        """R-EBOOK-3: calibredb add; Calibre owns the layout. A duplicate is skipped, not an error."""
        meta = json.loads(str(item.enrichment_data))["ebook"]
        cover = work.with_name("cover.jpg")
        async with self._calibre_lock:
            book_id, err = await ebook.calibredb_add(
                self.cfg.ebooks_root, work, meta, cover if cover.exists() else None
            )
        if err.startswith(
            ebook.BUSY_PREFIX
        ):  # held by another Calibre program: retry next pass
            self._emit("publish", item.id, "skipped", err)
            return False
        if err:
            await self._quarantine(session, item, "calibre_add_failed", err, work)
            return True
        detail = f"calibre id {book_id}" if book_id else "duplicate skipped by calibre"
        plan.execution_log = f"{plan.execution_log}\n{detail}".strip()
        item.state = FileState.published
        await session.commit()
        self._emit("publish", item.id, "success" if book_id else "skipped", detail)
        return True

    async def _archive_members(self, session, lead) -> None:
        """The other files of a merged book are archived with the lead, never deleted."""
        book = json.loads(str(lead.enrichment_data))["book"]
        for member_id in book["members"]:
            member = await session.get(MediaItem, member_id)
            await asyncio.to_thread(
                archive_original,
                Path(str(member.source_path)),
                self.cfg.input_dir,
                self.cfg.archive_dir,
                self.run_id,
            )
            member.state = FileState.validated
            member.error_log = f"merged into {lead.id}"
            member.updated_at = _now()

    async def _archive(self, item_id) -> bool:
        """After VERIFY passed and the file is published, move (never delete) the original."""
        async with self.session_factory() as session:
            item = await session.get(MediaItem, item_id)
            plan = await self._plan(session, item_id)
            source = Path(str(item.source_path))
            archived = await asyncio.to_thread(
                archive_original,
                source,
                self.cfg.input_dir,
                self.cfg.archive_dir,
                self.run_id,
            )
            if archived:
                plan.execution_log = (
                    f"{plan.execution_log}\narchived: {archived}".strip()
                )
            if item.media_type == MediaType.audiobook:
                await self._archive_members(session, item)
            shutil.rmtree(self.cfg.work_dir / item_id, ignore_errors=True)
            plan.plan_status = PlanStatus.completed
            item.state = FileState.validated
            item.updated_at = _now()
            await session.commit()
            self._emit("archive", item_id, "success", str(archived or ""))
        return True
