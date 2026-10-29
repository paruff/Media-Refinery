# Spec — Media Refinery

Companion to [intent.md](intent.md) (why) and [plan.md](plan.md) (how/when).
Requirement IDs (`R-…`) are referenced by plan goals and GitHub issues. Each requirement
is written so that a test can prove it.

---

## 1. Current state (baseline, 2026-10-26)

What exists, so goals start from facts rather than the stale docs.

| Area | State |
|---|---|
| Runtime | FastAPI daemon `app/main.py`: watchdog `InputWatcher` → asyncio `PipelineCoordinator` → `ScannerService`. Only the **scan** stage is wired into the daemon. |
| Models | SQLite via SQLAlchemy async: `MediaItem` (state machine `pending→scanning→scanned→enriched→planned→executed→validated→audited/error`), `NormalizationPlan`, `SagaFileMoveLog`, device profiles. Alembic exists, but `init_db()` uses `create_all` (two schema sources). |
| Services (not wired into daemon) | `classification`, `tmdb`, `tv_metadata`, `musicbrainz`, `movie/series/music_planner`, `planning_service`, `execution_service`, `subtitle_service`, `tagging_service`, `validator_service`, `vmaf_guardrail_service`, `quality_guard_service`, `auditor`, `fingerprint_service`, `reporting_service`. |
| Legacy tree | `src/` (audio/video converters, pipeline, storage, validator) — older Python port, overlaps `app/`. |
| Docs | Rewritten in G13 for the current system (`docs/ARCHITECTURE.md`, `DEPLOYMENT.md`, `DEVELOPMENT.md`); Go-era docs removed. |
| Packaging | `Dockerfile` (python 3.14) runs `src/audio/converter.py`, not the daemon. `docker-compose.yml` is structurally invalid (services nested inside a service). `pyproject.toml` requires ≥3.12; CI matrix tests 3.11. `requirements.txt` pins ~170 packages incl. Scrapy, kubernetes, Twisted, ipython, mkdocs (not used by the app). |
| CI | `main.yml` red on `main` since 2026-02; dependabot PRs #39–#45 all failing. |
| Siblings | `paruff/converter` (Python, ~2.5k LOC): ffprobe classify → repair (MPEG-1 GOP, WMV resync, XviD unpack) → smart bitrate → H.264/AAC MKV, VideoToolbox/libx264, parallel. `paruff/movies2vlib` (zsh): incoming→processing→final/quarantine for movies, ffprobe+decode health check, remux repair, TMDB naming, H.264+AAC+E-AC3 (Atmos copy), JSONL trace, adaptive worker throttling. |

### Known defects (fix in G1)

| ID | Location | Defect |
|---|---|---|
| D1 | `app/core/scanner.py` | Audio-vs-video is decided **before** ffprobe runs (`item.audio_codec` is always empty), so every new file gets a video fingerprint. |
| D2 | `app/core/scanner.py` | Duplicate lookup uses `scalar_one_or_none()`; ≥2 matches raises `MultipleResultsFound` → item goes to `error` for the wrong reason. |
| D3 | `app/services/fingerprint_service.py` | Video fingerprint = pHash of the **first frame**; black/leader frames collide, so unrelated videos are flagged duplicates and skipped. Also `imagehash`/`Pillow` are not dependencies, and the frame is BGR fed as RGB. |
| D4 | `app/core/watcher.py` | `MediaItem.id` = sha256 of the **path**, not content; renames re-import, identical content under two paths is not detected. |
| D5 | `app/core/watcher.py` + `app/main.py` | `watcher.run()` executes in `asyncio.to_thread` but calls `self.loop.create_task(...)` on the main loop from a worker thread (not thread-safe); `process_queue` sleeps `STABILITY_WINDOW` per file serially. |
| D6 | `app/services/execution_service.py` | "Transcode" runs `ffmpeg -version`; `src` and `output_file` are both `plan.target_path` (copies a file onto itself); `_execute_normalization_plan` swallows all exceptions, so the local stub always reports `SUCCESS`. |
| D7 | `app/services/execution_service.py` `ExecutionService.execute_plan` | `shutil.move` of the **original** with failures ignored, then logs "Moved to output" regardless. Violates R-SAFE-1. |
| D8 | `app/core/pipeline.py` | `datetime.utcnow()` (naive) written into tz-aware column; `PipelineCoordinator.stop()` doesn't cancel the worker task; stray `MediaScanner` stub with `print`. |
| D9 | `app/main.py` | Log file `rotation.log` written to CWD; deprecated `on_event` hooks. |

---

## 2. Scope

**In:** music, audiobooks, movies, TV series, ebooks. Identify → enrich → plan → approve →
convert → verify → publish → notify server.

**Out:** acquisition, serving/streaming, user management, DRM removal, cloud storage.

---

## 3. Canonical output (the "contract" per media type)

### R-MUSIC — Music → Music Assistant

- R-MUSIC-1 Container/codec: FLAC, 16 or 24-bit, source sample rate preserved (no resampling up). Lossy sources (MP3/AAC/Opus/OGG) are **never** transcoded: they keep their original codec and are only tagged, renamed and verified (FLAC-from-lossy adds size, not quality).
- R-MUSIC-2 Tags (Vorbis comments): `ARTIST, ALBUMARTIST, ALBUM, TITLE, TRACKNUMBER, TRACKTOTAL, DISCNUMBER, DISCTOTAL, DATE, GENRE, MUSICBRAINZ_TRACKID, MUSICBRAINZ_ALBUMID, MUSICBRAINZ_ARTISTID, MUSICBRAINZ_ALBUMARTISTID`; ReplayGain track+album.
- R-MUSIC-3 Embedded front cover (PICTURE type 3, ≥500 px, ≤2 MB) **and** `cover.jpg` in the album folder.
- R-MUSIC-4 Layout: `Music/{AlbumArtist}/{Album} ({Year})/{Disc:0>1}-{Track:02} - {Title}.flac` (disc prefix only when `DISCTOTAL>1`).
- R-MUSIC-5 Identification: AcoustID (Chromaprint `fpcalc`) → MusicBrainz release match; confidence below threshold ⇒ plan requires manual approval.
  Implemented in `app/services/music_id.py`: the best AcoustID result with a release is looked up in MusicBrainz (first release of the recording; one fetch per album, 1 req/s). A score below `ACOUSTID_MIN_SCORE` (default 0.85), no match, or no fingerprint keeps the embedded tags and leaves the plan in Review even for `AUTO_APPROVE_TYPES`; a human `approve()` still publishes it. Without `ACOUSTID_API_KEY` music uses embedded tags and is never held.
  Album as unit: a track waits in ENRICHED until every file in its folder is classified; ReplayGain track gain is measured per file and album gain over the folder played as one (ffmpeg `replaygain`, 48 kHz stereo mix). Cover: embedded picture first, else Cover Art Archive `front`; JPEG, ≥500 px, ≤2 MB (shrunk if needed), embedded as PICTURE type 3 and written as `cover.jpg` at publish; none usable ⇒ trace `cover` skipped, track still published. A sidecar `cover.jpg` in the input folder is not read. VERIFY adds `flac -t` for FLAC outputs. Disc/track totals come from MusicBrainz medium counts.

### R-BOOK — Audiobooks → Audiobookshelf

- R-BOOK-1 Single M4B per book, AAC-LC (or copy if already AAC), mono ≤64 kbps / stereo ≤128 kbps unless source lower.
- R-BOOK-2 Chapters embedded (from source files, cue, or silence detection); chapter count ≥1.
- R-BOOK-3 Tags: title, author (`artist`), narrator (`composer`), series + sequence, year, description, ASIN/ISBN when known; embedded cover.
- R-BOOK-4 Layout: `Audiobooks/{Author}/{Series}/{Sequence} - {Title}/{Title}.m4b` (series folders omitted when none).
- R-BOOK-5 Multi-file input (MP3 per chapter/disc) is merged in natural sort order.

### R-VIDEO — Movies & TV → Plex / Jellyfin (Samsung-safe)

- R-VIDEO-1 Container MKV. Video H.264 (High ≤ L4.1) or HEVC (Main/Main10). A conformant source (either codec) is kept as-is (no re-encode); anything that must be re-encoded becomes **H.264**. Audio: AAC stereo + (copy) AC3/E-AC3 surround when present; Atmos E-AC3 copied as-is (from movies2vlib). movies2vlib's unconditional 640k E-AC3 transcode is not ported: E-AC3 is only copied, never synthesised.
- R-VIDEO-2 Subtitles: text subs converted to SRT (UTF-8); image subs (PGS/VobSub) kept as-is but flagged; external `.srt` muxed or placed as `{name}.{lang}.srt`.
- R-VIDEO-3 Device profile `samsung_tizen` (from `profiles/`) must validate: direct-play without server transcode.
- R-VIDEO-4 Movie layout: `Movies/{Title} ({Year}) {tmdb-{id}}/{Title} ({Year}).mkv`.
- R-VIDEO-5 TV layout: `TV/{Show} ({Year}) {tvdb-{id}}/Season {SS:02}/{Show} - S{SS:02}E{EE:02} - {EpisodeTitle}.mkv`; specials in `Season 00`.
- R-VIDEO-5a Multi-episode files: `S01E01-E02`. Multi-part movies: `{Title} ({Year}) - part{N}.mkv` in the same folder. Enrichment: TMDB (movies), TVDB v4 (series/episodes); a miss keeps the guessit names. External `.srt` muxing is not implemented yet.
- R-VIDEO-6 Repair before encode (from converter): MPEG-1 timestamp/GOP repair, WMV packet resync, XviD packed-B-frame unpack; remux-repair fallback (from movies2vlib). Implemented in `app/media/video/`; WMV1/2/3 are all classified `wmv` (ffmpeg can only generate WMV2 fixtures).
- R-VIDEO-7 Encoder selection: hardware (VideoToolbox / VAAPI / NVENC) when available, libx264/libx265 fallback; smart bitrate scaling (grayscale ×0.75, low-complexity ×0.85).

### R-EBOOK — Ebooks → Calibre

- R-EBOOK-1 Output EPUB (EPUB 3 preferred). MOBI/AZW3 (DRM-free)/PDF→EPUB via Calibre `ebook-convert`; PDFs that are scanned images are kept as PDF and flagged.
- R-EBOOK-2 Metadata via Calibre `fetch-ebook-metadata` / Open Library: title, authors, series+index, ISBN, publisher, pubdate, cover.
- R-EBOOK-3 Ingest by `calibredb add` into the configured Calibre library (Calibre owns layout), not by writing files into the library tree directly.
- R-EBOOK-4 DRM-protected input is detected and quarantined with reason `drm`, never processed.

---

## 4. Pipeline

```text
input/ ──watch──▶ DISCOVER ─▶ PROBE ─▶ CLASSIFY ─▶ ENRICH ─▶ PLAN ─▶ [APPROVE] ─▶ EXECUTE ─▶ VERIFY ─▶ PUBLISH ─▶ NOTIFY
                                                                                                │fail
                                                                                                ▼
                                                                                         quarantine/{reason}/
```

- R-PIPE-1 Each stage is a state transition on `MediaItem`, persisted before side effects; the daemon resumes correctly after a crash (items in a transient state are retried or reset).
- R-PIPE-2 Item identity = content hash (sha256 of file bytes, streamed) **plus** path; same content at a new path is a move, not a new item.
- R-PIPE-3 Discovery waits for file stability (size+mtime unchanged for `stability_window`) without serial blocking per file.
- R-PIPE-4 Classification uses ffprobe streams + path + extension: audio with ≥1 h total duration or in an `audiobooks/` folder ⇒ audiobook; EPUB/MOBI/AZW3/PDF ⇒ ebook; video + SxxEyy / season folders ⇒ series; else movie.
- R-PIPE-5 Concurrency is bounded per stage (CPU-heavy EXECUTE separately from I/O-bound ENRICH); adaptive throttle halves workers after consecutive failures (from movies2vlib).
- R-PIPE-6 Multi-file units (album, multi-part audiobook, multi-disc movie) are planned and published as one unit.
- R-PIPE-7 Duplicates: audio by AcoustID fingerprint; video by duration + multi-frame perceptual hash (≥5 frames spread over the runtime); ebooks by ISBN or normalized title+author. A duplicate is a **plan decision** (keep best / keep both / skip), not an error.

## 5. Safety

- R-SAFE-1 Originals are never deleted or modified. After VERIFY passes they are moved to `archive/{run_id}/…` and kept for `archive.retention_days` (default 30), then purged; before that they stay in `input/`.
- R-SAFE-2 All writes go to `work/` first, then atomic rename into the library (same filesystem) or copy+fsync+verify+rename (cross-filesystem). Saga log records each step.
- R-SAFE-3 Generated paths are sanitized (illegal chars, length ≤ 255 bytes per component, no `..`, no leading dots) and must resolve inside the configured library root.
- R-SAFE-4 Dry-run mode produces the full plan and verify-preflight with zero filesystem writes outside `work/dry-run/`.
- R-SAFE-5 Every subprocess (ffmpeg/ffprobe/fpcalc/calibre) is invoked with an argument list (no shell), a timeout, and its stderr captured to the item log.
- R-SAFE-6 External API keys (TMDB, AcoustID, server tokens) come from env/secret files only, are never logged, and are never returned by the API.

## 6. Verification ("quality verified")

An output is publishable only if all checks for its type pass; results are stored as a
`VerificationRecord` (per item, JSON) and shown in the UI.

| Check | Music | Audiobook | Video | Ebook |
|---|---|---|---|---|
| Full decode with no errors (`ffmpeg -v error -f null -`) | ✓ | ✓ | ✓ | – |
| Duration within ±0.5 s (video ±1 s) of source | ✓ | ✓ (sum) | ✓ | – |
| Container/codec/profile conforms to §3 | ✓ | ✓ | ✓ (device profile) | ✓ |
| `flac -t` integrity / MD5 | ✓ | – | – | – |
| Required tags present | ✓ | ✓ | – | ✓ |
| Chapters ≥1 | – | ✓ | – | – |
| VMAF (sampled, ≥ `vmaf_min`, default 93) — only when re-encoded | – | – | ✓ | – |
| Stream count/language preserved (audio + text subs) | – | – | ✓ | – |
| `epubcheck` passes with no errors | – | – | – | ✓ |
| Output sha256 recorded | ✓ | ✓ | ✓ | ✓ |

- R-VERIFY-1 A failing check moves the output to `quarantine/{reason}/` and leaves the original untouched.
- R-VERIFY-2 A library re-audit job re-runs the non-destructive checks over published files and reports drift.

## 7. Interfaces

### R-API (FastAPI, `/api/v1`)

- `GET /health` (liveness), `GET /ready` (DB + ffmpeg + library roots writable).
- `GET /items?state=&type=` · `GET /items/{id}` (incl. plan, log, verification).
- `POST /items/{id}/approve` · `POST /items/{id}/reject` · `POST /items/{id}/retry`.
- `POST /scan` (rescan input) · `GET /summary` (exists) · `GET /metrics` (Prometheus text).
- R-API-1 Single-user LAN app: bind to `127.0.0.1` by default; when bound elsewhere, a static bearer token (`MR_API_TOKEN`) is required on all non-health routes. CSRF-safe: mutating routes accept JSON only.

### R-UI (web)

- Server-rendered (Jinja2 + htmx; no SPA build step) following [DESIGN.md](DESIGN.md).
- Views: **Queue** (by state), **Review** (pending plans with a before→after diff of path, plus source container/codecs and planned actions (transcode, rename, retag, subtitle conversion); per-tag and artwork diffs are out of scope because plans do not store target tags; approve/reject, bulk approve), **Item detail** (log, verification record), **Quarantine**, **Summary**.

### R-CLI (Typer)

- `refinery scan|plan|approve|run|verify|audit [--dry-run] [--type music|audiobook|movie|series|ebook] PATH`.
- Same services as the daemon; no logic in CLI layer.

### R-NOTIFY (server handoff)

- After PUBLISH, trigger a targeted rescan: Plex (`/library/sections/{id}/refresh?path=`), Jellyfin (`/Library/Media/Updated`), Audiobookshelf (`/api/libraries/{id}/scan`), Music Assistant (library sync API), Calibre (implicit via `calibredb add`; Calibre-Web reads the DB). Each is optional and configured independently; failures are logged, never fail the item.

## 8. Configuration

- One YAML file (`config.yaml`) validated by pydantic-settings, env overrides `MR_*`. Library roots per type, quarantine/archive/work dirs, per-type enable flags, thresholds (`vmaf_min`, match confidence), concurrency, server endpoints. Secrets only via env / `*_FILE`.

## 9. Non-functional

- NF-1 Python 3.12 (one version across pyproject, CI, Docker).
- NF-2 Runtime dependencies are only what `app/` imports; dev tools in `requirements-dev.txt`.
- NF-3 Tests: pytest unit + integration (real ffmpeg on tiny generated fixtures), behave features for each media type's happy path; coverage ≥80 % on `app/`. CI green on `main` is a merge gate.
- NF-4 Structured JSON logs with `item_id` and `run_id` on every line (JSONL trace from movies2vlib).
- NF-5 Docker image runs as non-root `PUID/PGID`, includes ffmpeg, chromaprint, flac, calibre (CLI), epubcheck; healthcheck on `/ready`.
- NF-6 Throughput target: library of 10k tracks scanned+planned in < 1 h on a 4-core NAS (excluding transcode).

## 10. Decisions (2026-10-26)

- Q1 Lossy music stays in its original codec (tagged, renamed, verified; never transcoded to FLAC). `music.lossy_to_flac` is removed.
- Q2 Archived originals are kept **30 days** after publish, then purged by a scheduled job (`archive.retention_days: 30`); purge is logged and skipped for items re-opened in that window.
- Q3 Re-encodes target **H.264** (High ≤ L4.1). HEVC sources that already conform are kept, but never produced.
- Q4 Both Plex and Jellyfin are supported; **Plex is primary** (naming, NFO-less layout and notify ordering optimise for Plex; Jellyfin must still match).
