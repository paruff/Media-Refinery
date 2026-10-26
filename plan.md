# Plan — Media Refinery

Goal-driven roadmap for [intent.md](intent.md) / [spec.md](spec.md). Each goal is one
GitHub issue (label `goal`) on the **Media Refinery** project board, sized for one
`/goal` run, with a **Done when** that a command can check. Paste the `/goal` line to run it.

Board flow: `Backlog → Ready → In Progress → Human Review → Done`. Every goal ends in
**Human Review** (PR open, CI green, [REVIEW.md](REVIEW.md) checklist run); only a human
moves it to Done.

## Dependency order

```text
G0 Foundation ─▶ G1 Correctness ─▶ G2 Pipeline spine ─┬─▶ G3 Absorb converter ─┐
                                                      ├─▶ G4 Absorb movies2vlib ┴─▶ G5 Movies & TV
                                                      ├─▶ G6 Music
                                                      ├─▶ G7 Audiobooks
                                                      └─▶ G8 Ebooks
G2 ─▶ G9 API+CLI ─▶ G10 Web UI ;  G5..G8 ─▶ G11 Server handoff ─▶ G12 Release ─▶ G13 Docs & archive
```

G3/G4 can run in parallel; G6/G7/G8 can run in parallel once G2 lands.

## Rules every goal follows

- TDD: failing test first; tiny generated fixtures (`ffmpeg -f lavfi`), never real media in git.
- Never weaken R-SAFE-* to make a test pass.
- `make ci` green locally and in GitHub Actions before moving to Human Review.
- Update `spec.md` if behaviour intentionally differs; tick the goal's checklist in its issue.

---

## G0 — Foundation: one Python, lean deps, green CI

**Why:** CI has been red on `main` since 2026-02; nothing else is trustworthy until it's green.
**Scope:** Python 3.12 everywhere (pyproject, CI, Dockerfile). `requirements.txt` = runtime imports of `app/` only; dev tools → `requirements-dev.txt` (drop Scrapy, kubernetes, Twisted, ipython, mkdocs, goodwe, python-jenkins…). Fix `docker-compose.yml` (single valid `media-refinery` service; *arr/Tdarr/beets removed). Dockerfile runs the daemon. Delete committed artifacts (`coverage.xml`, `test.mp3`, `scripts/diag_out.txt`). Close/rebase dependabot PRs after. Close Go issue #2.
**Already done (tooling PR):** SHA-pinned pre-commit config + CI/security workflows, ruff/bandit/mypy/hadolint clean, 173 baseline `# noqa` comments, coverage floor 49 %. **Remaining:** tests are red on main (197 errors, 18 failures, e.g. `patch_create_subprocess_exec did not yield a value`), `docker-compose.yml` is excluded from yamllint/compose-spec until fixed, raise `--cov-fail-under` to 80.
**Done when:** `make ci` exits 0; latest `main.yml` run on the PR is `success`; `docker compose config -q` exits 0; `docker build .` succeeds and the container answers `GET /health` 200.

```text
/goal G0 from plan.md: make CI green on Python 3.12 with lean requirements, valid docker-compose, and a Dockerfile that runs the daemon — done when make ci passes, the PR's CI run succeeds, docker compose config -q passes, and the built container returns 200 on /health.
```

## G1 — Correctness: fix known defects D1–D9

**Why:** The scan stage silently mislabels and skips files (spec §1 defects).
**Scope:** One regression test per defect in `spec.md` §1, then the fix. Content-hash identity (R-PIPE-2), stability check without serial blocking (R-PIPE-3), type decided after probe, multi-frame video hash (R-PIPE-7), no exception swallowing, tz-aware timestamps, lifespan handler, no `print`.
**Done when:** `pytest -m regression` has ≥9 tests named `test_d1_…`–`test_d9_…`, all pass; `ruff check app` and `mypy app` clean; the `# noqa` baseline in `app/` is gone (`grep -rn 'noqa' app | wc -l` → 0) and `_prune_old_errors` no longer deletes `media_items` rows (data-loss risk, R-SAFE-1).

```text
/goal G1 from plan.md: fix defects D1–D9 in spec.md §1, each with a named regression test written first — done when pytest -m regression passes with test_d1..test_d9 present and ruff + mypy on app/ are clean.
```

## G2 — Pipeline spine: discover → … → publish with saga + dry-run

**Why:** Only SCAN is wired; planners/executor/validators exist but aren't connected.
**Scope:** Orchestrator drives every state in spec §4 using existing services; APPROVE gate (auto-approve rules opt-in); EXECUTE writes to `work/` + atomic publish (R-SAFE-2); VERIFY framework + `VerificationRecord` (spec §6, generic checks: decode, duration, sha256); quarantine by reason; archive originals after verify (R-SAFE-1); crash-resume (R-PIPE-1); dry-run (R-SAFE-4); path sanitizer + root confinement (R-SAFE-3). Remove legacy `src/` after porting anything still used.
**Done when:** behave feature `pipeline_spine.feature` passes: a generated MP3 and a generated MKV dropped in `input/` reach `validated` after approval, outputs exist under library roots, originals exist under `archive/`, killing the daemon mid-EXECUTE and restarting completes the item; dry-run leaves `input/` and library roots byte-identical; `src/` deleted.

```text
/goal G2 from plan.md: wire the full pipeline (spec.md §4–6) with approval gate, saga publish, verification records, quarantine, archive-after-verify, crash resume and dry-run — done when behave features/pipeline_spine.feature passes all scenarios and src/ is removed with CI green.
```

## G3 — Absorb `paruff/converter` (video repair + encode engine)

**Why:** Proven repair pipelines and smart bitrate; single codebase (intent).
**Scope:** Port `ffprobe_utils, file_classifier, repair, smart_mode, encode` into `app/media/video/`; drop GUI, Homebrew, PyInstaller, tqdm. Port its 39 tests. Encoder selection VideoToolbox/VAAPI/NVENC → libx264/libx265 (R-VIDEO-6, R-VIDEO-7). Executor uses it for video plans.
**Done when:** ported converter tests pass under `tests/unit/media/video/`; integration test transcodes generated MPEG-1, WMV3 and XviD AVI samples to MKV that pass the `samsung_tizen` profile check; converter repo README points here.

```text
/goal G3 from plan.md: absorb paruff/converter's probe/classify/repair/smart-bitrate/encode into app/media/video with its tests — done when ported tests pass and generated MPEG-1, WMV3 and XviD samples convert to MKV that passes the samsung_tizen profile check.
```

## G4 — Absorb `paruff/movies2vlib` (health check, quarantine, trace, throttle)

**Why:** Its operational hardening is what the daemon lacks.
**Scope:** Health check = ffprobe + full decode scan; remux-repair fallback; Atmos/E-AC3 copy-track rule; quarantine reasons (`healthcheck_failed`, `convert_failed`); JSONL trace events (`timestamp, run_id, event, item_id, status, detail`) (NF-4); adaptive throttle (R-PIPE-5). Port its bats scenarios (dry-run, convert+move, healthcheck-fail→quarantine) to behave.
**Done when:** behave `movies2vlib_parity.feature` (3 scenarios) passes; a corrupted generated file lands in `quarantine/healthcheck_failed/`; trace JSONL lines validate against a schema test; movies2vlib README points here.

```text
/goal G4 from plan.md: port movies2vlib's health check, remux repair, E-AC3/Atmos rule, quarantine reasons, JSONL trace and adaptive throttling — done when features/movies2vlib_parity.feature passes all 3 scenarios and trace lines validate against the schema test.
```

## G5 — Movies & TV end-to-end (Plex/Jellyfin, Samsung-safe)

**Depends on:** G2, G3, G4.
**Scope:** R-VIDEO-1…5: TMDB/TVDB enrich, naming/layout, keep-if-conformant, AAC stereo + surround copy, subtitle → SRT, VMAF sampled check only when re-encoded, multi-part movies, specials.
**Done when:** `tests/features/03_movies_plex_samsung65.feature` and `04_tv_series_plex.feature` pass against generated fixtures with mocked TMDB/TVDB; output paths match R-VIDEO-4/5 exactly; an already-conformant H.264 MKV is remuxed, not re-encoded (asserted via ffmpeg args).

```text
/goal G5 from plan.md: deliver movies and TV per spec.md R-VIDEO-1..5 — done when features 03_movies_plex_samsung65 and 04_tv_series_plex pass with mocked TMDB/TVDB and conformant inputs are remuxed without re-encode.
```

## G6 — Music end-to-end (Music Assistant)

**Depends on:** G2. **Absorbs:** #12, #29, #30, #31, #32, #33, PR #38.
**Scope:** R-MUSIC-1…5: AcoustID→MusicBrainz match with confidence gate, FLAC policy, full tag map incl. MBIDs + ReplayGain, cover embed + `cover.jpg`, album-as-unit planning, `flac -t` verify.
**Done when:** `05_music_musicassistant.feature` passes: a generated 3-track album (mocked AcoustID/MB) publishes to `Music/{AlbumArtist}/{Album} ({Year})/` with all R-MUSIC-2 tags verified by mutagen and an embedded cover; low-confidence match stops at Review.

```text
/goal G6 from plan.md: deliver music per spec.md R-MUSIC-1..5 (closes #29–#33, #12) — done when features/05_music_musicassistant.feature passes with mocked AcoustID/MusicBrainz and mutagen confirms every R-MUSIC-2 tag and the embedded cover.
```

## G7 — Audiobooks end-to-end (Audiobookshelf)

**Depends on:** G2.
**Scope:** R-BOOK-1…5: classify, merge multi-file in natural order, chapters (source/cue/silence), M4B AAC, tags incl. narrator/series, cover, ABS layout.
**Done when:** `07_audiobooks_abs.feature` passes: 3 generated MP3 "chapters" become one M4B with 3 chapters, correct duration (±0.5 s), tags and cover, at the R-BOOK-4 path.

```text
/goal G7 from plan.md: deliver audiobooks per spec.md R-BOOK-1..5 — done when features/07_audiobooks_abs.feature passes and the generated 3-file book becomes one M4B with 3 chapters, correct duration, tags and cover at the R-BOOK-4 path.
```

## G8 — Ebooks end-to-end (Calibre)

**Depends on:** G2.
**Scope:** R-EBOOK-1…4: classify, DRM detect → quarantine, `ebook-convert` to EPUB, metadata fetch, `epubcheck`, `calibredb add` into configured library.
**Done when:** `08_ebooks_calibre.feature` passes (Calibre CLI in the CI image): a generated MOBI and EPUB are added to a temp Calibre library with title/author/cover; a fake-DRM file goes to `quarantine/drm/`.

```text
/goal G8 from plan.md: deliver ebooks per spec.md R-EBOOK-1..4 — done when features/08_ebooks_calibre.feature passes in CI with calibre installed, both samples land in a temp Calibre library with metadata, and the DRM sample is quarantined.
```

## G9 — API + CLI

**Depends on:** G2.
**Scope:** R-API routes, token auth when not bound to localhost (R-API-1), `/ready`, `/metrics`; Typer CLI R-CLI sharing services; OpenAPI snapshot test.
**Done when:** API tests cover every route incl. 401 without token on non-localhost bind; `refinery --help` lists all commands; `refinery run --dry-run tests/fixtures/…` exits 0 with a plan table.

```text
/goal G9 from plan.md: implement the R-API routes with token auth and the R-CLI commands over shared services — done when route tests (incl. 401 cases) pass, the OpenAPI snapshot test passes, and refinery run --dry-run on fixtures exits 0.
```

## G10 — Web UI (per DESIGN.md)

**Depends on:** G9.
**Scope:** Jinja2 + htmx views: Queue, Review (before→after diff, approve/reject/bulk), Item detail, Quarantine, Summary. Tokens/components from `DESIGN.md`; WCAG AA.
**Done when:** Playwright e2e: approve a pending item from Review and see it reach `validated`; axe-core reports 0 serious/critical violations on all 5 views; `npx @google/design.md lint DESIGN.md` passes.

```text
/goal G10 from plan.md: build the Jinja2+htmx web UI (Queue, Review, Item, Quarantine, Summary) following DESIGN.md — done when the Playwright approve-flow test passes, axe reports zero serious/critical issues on all views, and the DESIGN.md lint passes.
```

## G11 — Server handoff (notify)

**Depends on:** G5–G8.
**Scope:** R-NOTIFY clients for Plex, Jellyfin, Audiobookshelf, Music Assistant; optional, independent, non-fatal; secrets via env.
**Done when:** unit tests with recorded HTTP fixtures assert the exact refresh call per server; a failing server leaves the item `validated` with a warning.

```text
/goal G11 from plan.md: add optional Plex/Jellyfin/Audiobookshelf/Music Assistant rescan notifications per R-NOTIFY — done when fixture-based tests assert each refresh call and a server failure only logs a warning.
```

## G12 — Release: image + deployment

**Depends on:** G5–G11.
**Scope:** Multi-stage image (ffmpeg, chromaprint, flac, calibre CLI, epubcheck), non-root PUID/PGID, healthcheck `/ready`, compose example with volume layout for all 5 libraries, GHCR publish on tag, Trivy + Gitleaks in CI (as in movies2vlib).
**Done when:** tag `v0.2.0` publishes `ghcr.io/paruff/media-refinery:0.2.0`; Trivy shows 0 critical; `docker compose up` on a clean host processes one fixture of each media type end-to-end (smoke script).

```text
/goal G12 from plan.md: ship a non-root multi-stage image with all media tools, compose example, GHCR publish and Trivy/Gitleaks — done when the v0.2.0 image publishes, Trivy reports 0 critical, and the compose smoke script processes one fixture per media type.
```

## G13 — Docs consolidation & archive siblings

**Depends on:** G3, G4, G12.
**Scope:** Replace Go-era `docs/ARCHITECTURE.md`/`SUMMARY.md` with an architecture doc for the actual system; README quickstart = compose; fold DOCKER/TESTING/DEVELOPMENT/PERFORMANCE/METRICS/FAQ into `docs/`; archive `paruff/converter` and `paruff/movies2vlib` with pointer READMEs.
**Done when:** `grep -rn "pkg/\|Go module\|beets\|Tdarr" docs README.md` returns nothing; every link in README/docs resolves (lychee); both sibling repos archived.

```text
/goal G13 from plan.md: replace Go-era docs with current architecture, consolidate root docs into docs/, and archive converter + movies2vlib — done when no Go/beets/Tdarr references remain, lychee finds no broken links, and both repos are archived.
```

---

## Tracking

- Project: [Media Refinery](https://github.com/users/paruff/projects/10) (owner `paruff`) — Status: Backlog / Ready / In Progress / Human Review / Done.
- One issue per goal, title `G<n>: <name>`, label `goal`, body = that goal's section above. Edit the plan here, then re-sync issue bodies.
- Existing story issues #12, #29–#33 are sub-issues of G6 (#52).

| Goal | Issue | Goal | Issue |
|---|---|---|---|
| G0 Foundation | #46 | G7 Audiobooks | #53 |
| G1 Correctness | #47 | G8 Ebooks | #54 |
| G2 Pipeline spine | #48 | G9 API + CLI | #55 |
| G3 Absorb converter | #49 | G10 Web UI | #56 |
| G4 Absorb movies2vlib | #50 | G11 Server handoff | #57 |
| G5 Movies & TV | #51 | G12 Release | #58 |
| G6 Music | #52 | G13 Docs & archive | #59 |
