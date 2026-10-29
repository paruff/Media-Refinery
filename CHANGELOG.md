# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
- Audiobooks promoted to beta (P2, #153): `audiobook` joins the default `ENABLED_TYPES`; generated audiobook corpus (multi-file, mixed MP3/M4A and sample rates, gaps, late part, M4B input, CUE and silence-detected chapters, untagged long audio, multi-book author folder, podcasts) and a crash sweep over the merge step; a part that arrives after its book was planned or built is quarantined as `late_part` instead of becoming a second book; a multi-FILE CUE is ignored rather than misread; a failed silencedetect flags the plan for review; file names with newlines go through the concat filter; PNG covers are tagged as PNG; a retried plan reuses the book description and queries only its own folder's rows
- Ebooks promoted to beta (P1, #152): `ebook` joins `music` in the default `ENABLED_TYPES`; generated ebook corpus (epub/pdf/mobi/azw3, DRM'd AZW3, duplicate ISBNs, corrupt zip, `&` and unicode titles) and Calibre crash sweep; recorded `fetch-ebook-metadata` fixture; publisher and pubdate are written to Calibre and a cover is fetched when the book has none; `parse_meta` keeps `AT&T`-style names and the first value of a repeated field; `epub_text_length` is memory-bounded and survives a corrupt zip; two copies of one ISBN planned together are no longer both added; a scanned PDF kept as PDF gets a unique plan target (#188); #101 minors done; a book with no title (or Calibre's "Unknown") is filed under a title cleaned from its file name, and an untitled EPUB gets a `dc:title` added to its OPF rather than being quarantined; the corpus AZW3 check allows for Calibre 7.6, whose AZW3 to EPUB output fails epubcheck (use Calibre 8+)
- Fix (B4 follow-ups, #171): UI session cookies use a domain-separated HMAC key (existing sessions are logged out once); `retry` claims before checking the source; `.part`/`.tmp` exclusion matches the file suffix only (`report.partial.txt` is no longer skipped); test that `approve` skips review-flagged items

## [0.3.0-rc.2]
- Fix: sidecar images (cover.jpg etc.) are no longer ingested as media (#173); watcher import retries back off exponentially, giving up is an ERROR, and stat errors no longer kill the loop (#168); beta trial run 3 on a real library in `docs/BETA_TRIAL.md`
- Beta gate (B7): real-library trial (`scripts/beta_trial.sh`, report in `docs/BETA_TRIAL.md`); fix: unidentified music was filed under Unknown Artist/Unknown Album despite embedded ARTIST/ALBUM tags
- CI: the compose smoke test (all five media types via doctor, plan, approve) now runs on every PR and push to main, and gates the canary image; single required check `CI gate` (`scripts/protect_main.sh`) aggregates hooks, tests, build and smoke; offline contract-fixture, acceptance and regression suites join the test job; Codecov upload and badge replaced by the enforced 80% floor and a coverage artifact; README badge black→ruff; `make fmt` uses ruff; new `docs/VERIFICATION.md`
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
