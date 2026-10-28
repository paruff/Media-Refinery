# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.3.0-rc1]
- Release candidate: first run of the hardened release workflow (one multi-arch image, smoke + Trivy on that digest, promoted by digest, provenance + SBOM, tag guard). Pre-releases never move `:latest`.
- Security: provider API keys and fingerprints no longer reach logs; non-ASCII tokens return 401; `/health` no longer leaks and returns 503; the API refuses to start on a non-loopback host without `MR_API_TOKEN`; UI gets a strict CSP and security headers.
- Safety: dry-run never acts past planning; migration for `verification_records` / `saga_file_move_log`.
- Correctness: audiobooks are one book per folder (not per author), mixed-format merges, part-gap and chapter-bound checks; music album ReplayGain/release/disc handling; confident TMDB/TVDB matching with review; ebook duplicate review and busy-library retry; coalesced server rescans with `NOTIFY_PATH_MAP`; video remux keeps all streams.

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
