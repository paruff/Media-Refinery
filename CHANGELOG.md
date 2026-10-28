# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
- Onboarding (G19): README positioning (who it is for, what it is not, vs Tdarr/*arr/beets/Picard/Calibre), `refinery doctor` preflight, compose now passes `.env` API keys/server URLs/`ENABLED_TYPES` into the container (#106), `Settings` ignores unknown `.env` keys, `/api/v1/metrics` adds `media_refinery_quarantined_items` and `media_refinery_stage_duration_seconds_{sum,count}`, UI Summary shows quarantine reasons with a suggested action; smoke test now runs doctor and plan
- Corpus and crash safety (G15): generated messy-library corpus, crash injection at every commit/move/ffmpeg/archive/quarantine point with source-held-once, no-partial-file, convergence and no-duplicate invariants (`make corpus-test`), `refinery plan` library report (always a dry run), nightly NF-6 throughput (`make corpus-bench`)
- Fix: a crash between classification and enrichment left a music item `enriched` without its metadata, failing planning with `KeyError`; classification now leaves the item `scanned` until enrichment is committed

## [0.2.1]
- Fix: `scripts/smoke.sh` cleanup removes container-owned files as root (v0.2.0 Release run failed there; v0.2.0 was never published)

## [0.2.0]
- Release (G12): multi-stage non-root image (ffmpeg, chromaprint, flac, Calibre CLI, epubcheck) with `/ready` healthcheck, `user: PUID:PGID` compose example for all five libraries, `scripts/smoke.sh` compose smoke test, tag-triggered GHCR publish gated on smoke + Trivy (0 critical)
- Server handoff (G11): optional Plex / Jellyfin / Audiobookshelf / Music Assistant rescan after PUBLISH (`PLEX_URL`, `JELLYFIN_URL`, `ABS_URL`, `MUSIC_ASSISTANT_URL`, … see `.env.example`); a failing server only logs a warning
- Ebooks end-to-end (G8): MOBI/AZW3/PDF→EPUB 3 via Calibre, DRM detect → `quarantine/drm/`, scanned PDFs kept as PDF and flagged, optional `fetch-ebook-metadata`, `epubcheck`, `calibredb add` into `CALIBRE_LIBRARY`
- Audiobooks end-to-end (G7): folder of per-chapter files merged in natural order into one AAC M4B with embedded chapters (source/embedded/CUE/silence), narrator/series/ASIN tags, cover, Audiobookshelf layout (`AUDIOBOOKS_ROOT`)
- Music end-to-end (G6): AcoustID→MusicBrainz identification with confidence gate, full R-MUSIC-2 tag map + ReplayGain, cover embed + `cover.jpg`, album-as-unit, `flac -t` verify
- Moved documentation files into docs/
- Improved repo structure and documentation index
- Fixed CI dependency conflicts
- Cleaned up sample media and pycache

## [Earlier]
- See commit history for previous changes
