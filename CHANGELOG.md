# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
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
