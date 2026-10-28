
# Media Refinery


[![CI](https://github.com/paruff/Media-Refinery/actions/workflows/ci.yml/badge.svg)](https://github.com/paruff/Media-Refinery/actions/workflows/ci.yml)
[![Coverage ≥80% enforced](https://img.shields.io/badge/coverage-%E2%89%A580%25%20enforced-brightgreen.svg)](docs/VERIFICATION.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](http://mypy-lang.org/)

Media Refinery watches a drop folder and normalizes music, audiobooks, movies, TV and ebooks
to one canonical, verified format per type, publishes them into your libraries and tells
Plex, Jellyfin, Audiobookshelf or Music Assistant to rescan. Originals are never modified.

## Who it is for

Self-hosters with a messy pile of downloads and a Plex, Jellyfin, Audiobookshelf or Music Assistant
server who want every file converted to one canonical, *verified* format and published into a clean
library, with a human approving the plan first. **Music is the supported lead type**; movies, TV,
audiobooks and ebooks are experimental and off until you list them in `ENABLED_TYPES`.

## What it is not

- Not a downloader or indexer manager: it never fetches media.
- Not a media server or player.
- Not an in-place tagger: sources are never modified; output goes to a new library.
- Not a cluster transcoder: one worker, one host.

## How it differs

| Tool | What it does | Media Refinery |
| --- | --- | --- |
| Tdarr | Transcodes a library in place by rules, at scale | Plan-then-approve, verifies each output, never touches the original, publishes to a separate library |
| Sonarr / Radarr / Lidarr | Find and download releases, then rename/import | Starts after download: normalizes whatever landed in the drop folder, any source |
| beets | Tags and organizes music from a CLI | Also converts, verifies and notifies servers; web review UI instead of an interactive prompt |
| MusicBrainz Picard | Interactive desktop tagger | Unattended pipeline with a review queue only for low-confidence matches |
| Calibre | Ebook library manager and converter | Uses Calibre underneath for ebooks, alongside the other four types |

## Quickstart

```bash
git clone https://github.com/paruff/Media-Refinery.git
cd Media-Refinery
cp .env.example .env     # set MR_API_TOKEN, PUID/PGID, folder paths, API keys
docker compose up -d

# 1. Preflight: tools present, paths writable, keys set, media servers reachable
docker compose exec media-refinery refinery doctor
# 2. Plan: reports what a run would do (counts, disk, time, items needing review); writes nothing
docker compose exec media-refinery refinery plan /input
```

3. Approve: open <http://localhost:8000/ui>, check the Review view and approve (or
   `POST /api/v1/items/{id}/approve`). Approved items are converted, verified and published; set
   `AUTO_APPROVE_TYPES` to skip review for a type you trust. `refinery approve` is for use while the
   server is stopped (`docker compose run --rm media-refinery refinery approve /input`): a second
   process writing the same database races the running pipeline.

Values in `.env` (API keys, server URLs, `ENABLED_TYPES`, ...) reach the container; see
[`.env.example`](.env.example). `scripts/smoke.sh` runs doctor, plan and publish against the real
image in CI.

Operating it: `/api/v1/metrics` exposes items by state/type, quarantined items by reason and
per-stage durations; the UI Summary lists quarantine reasons with a suggested action.

CLI: `refinery doctor|scan|plan|approve|run|verify|audit [--dry-run] PATH`.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) · [Deployment](docs/DEPLOYMENT.md) · [Development](docs/DEVELOPMENT.md)
- [Verification](docs/VERIFICATION.md) · [Contributing](docs/CONTRIBUTING.md) · [Maintainers](docs/MAINTAINERS_GUIDE.md) · [Product vision](docs/PRODUCT_VISION.md)
- [Intent](intent.md) · [Spec](spec.md) · [Plan](plan.md) · [Design](DESIGN.md) · [Security](SECURITY.md)
