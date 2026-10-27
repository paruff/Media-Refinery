# Architecture

Media Refinery is a single Python 3.14 FastAPI daemon that watches `input/`, normalizes
music, audiobooks, movies, TV and ebooks to one canonical format per type, verifies the
result, publishes it into the library and tells the media server to rescan.
Requirements live in [spec.md](../spec.md); this page describes how they are met.

## Pipeline

```text
input/ ─watch─▶ DISCOVER ─▶ PROBE ─▶ CLASSIFY ─▶ ENRICH ─▶ PLAN ─▶ [APPROVE] ─▶ EXECUTE ─▶ VERIFY ─▶ PUBLISH ─▶ NOTIFY
                                                                                              │fail
                                                                                              ▼
                                                                                    quarantine/{reason}/
```

Each stage is a `FileState` transition on `MediaItem`, persisted before side effects so the
daemon resumes after a crash. States: `pending → scanning → scanned → enriched → planned →
approved → executing → executed → verified → published` (`validated`/`audited` after later
checks), with `quarantined` and `error` as exits.

## Components

| Path | Role |
|---|---|
| `app/main.py` | FastAPI app and lifespan: starts the watcher and orchestrator, mounts API and UI. |
| `app/core/watcher.py` | watchdog `InputWatcher`; waits for file stability, imports by content hash. |
| `app/core/scanner.py`, `pipeline.py`, `orchestrator.py` | ffprobe scan, per-stage bounded workers, stage driver. |
| `app/core/planning.py`, `publish.py`, `verify.py` | plan building, atomic publish (work → library), verification checks. |
| `app/core/throttle.py`, `supervisor.py`, `tools.py` | adaptive worker throttle, crash recovery, subprocess wrapper (argument lists, timeouts). |
| `app/services/` | enrichment (TMDB, TVDB, MusicBrainz/AcoustID), per-type planners, tagging, subtitles, VMAF guardrail, duplicate detection, server notify. |
| `app/media/video/` | probe, health check, repair, encode/profile logic for movies and TV. |
| `app/media/audiobook.py`, `ebook.py` | audiobook (M4B) and ebook (Calibre) handling. |
| `app/models/` | SQLAlchemy models: `MediaItem`, `NormalizationPlan`, `SagaFileMoveLog`, device profiles. Schema managed by Alembic. |
| `app/api/v1/` | REST API (`/api/v1`). |
| `app/ui/` | Jinja2 + htmx web UI, styled per [DESIGN.md](../DESIGN.md). |
| `app/cli.py` | `refinery` Typer CLI; shares `app/services/refinery.py` with the API (no logic in either). |

## Safety invariants

- Originals are never modified; after VERIFY they move to `archive/` (R-SAFE-1).
- All writes go to `work/` first, then an atomic rename (or copy + fsync + verify) into the library (R-SAFE-2).
- Generated paths are sanitized and must resolve inside the library root (R-SAFE-3).
- `--dry-run` writes nothing outside `work/dry-run/` (R-SAFE-4).
- Every subprocess (ffmpeg, ffprobe, fpcalc, calibre) runs without a shell, with a timeout (R-SAFE-5).
- API keys come from the environment only and are never logged or returned (R-SAFE-6).

## Interfaces

- **REST** `/api/v1`: `GET /health`, `GET /ready` (open); `GET /items`, `GET /items/{id}`, `POST /items/{id}/approve|reject|retry`, `POST /scan`, `GET /summary`, `GET /metrics` need `Authorization: Bearer <MR_API_TOKEN>`. Bound to `127.0.0.1` by default; any other `MR_API_HOST` requires `MR_API_TOKEN`.
- **Web UI** at `/ui`: queue, review (approve/reject plans, bulk actions), item detail, quarantine, summary.
- **CLI**: `refinery scan|plan|approve|run|verify|audit [--dry-run] [--type …] PATH`.
- **Notify**: optional Plex, Jellyfin, Audiobookshelf and Music Assistant rescan after publish; Calibre via `calibredb add`.

## Data and deployment

SQLite (`data/`) holds item state. The Docker image (non-root, ffmpeg, chromaprint, flac,
calibre) is the supported runtime; see [DEPLOYMENT.md](DEPLOYMENT.md).

## Observability

Structured logs carry `item_id` and `run_id`; each run writes a JSONL trace. `/health` is
liveness, `/ready` checks the database, ffmpeg and writable library roots.
