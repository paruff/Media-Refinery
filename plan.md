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
**Scope:** Python 3.12 everywhere (pyproject, CI, Dockerfile). `requirements.txt` = runtime imports of `app/` only; dev tools → `requirements-dev.txt` (drop Scrapy, kubernetes, Twisted, ipython, mkdocs, goodwe, python-jenkins…). Fix `docker-compose.yml` (single valid `media-refinery` service; legacy *arr/transcoder/tagger services removed). Dockerfile runs the daemon. Delete committed artifacts (`coverage.xml`, `test.mp3`, `scripts/diag_out.txt`). Close/rebase dependabot PRs after. Close Go issue #2.
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
**Done when:** no Go-era references remain in the repo, lychee finds no broken links, and both sibling repos are archived. **Status:** done (PR #84; `paruff/converter` and `paruff/movies2vlib` archived with pointer READMEs).

---

## Phase 2 — Make it trustworthy

G0–G13 built the breadth (five media types, API, UI, release). The review of those goals
([review-finding issues](https://github.com/paruff/Media-Refinery/issues?q=label%3Areview-finding))
showed the product is wide but shallow, and that it has never met a realistic library.
Phase 2 trades breadth for trust: prove one pipeline on messy data, then repeat the pattern.

```text
G14 review gate ─▶ G15 corpus + invariants ─▶ G16 lead pipeline (music) ─▶ G18 decompose orchestrator
                                         └──▶ G17 provider contracts ──┘            │
G19 positioning + onboarding (after G15/G16) ──────────────────────────────────────┴▶ G20 backlog + promotion
```

Same rules as above, plus: **one PR per goal, always based on `main`** (a stacked PR merged into
its base branch never reaches `main`; this happened to #116).

## G14 — Review gate for risky code

**Why:** The G0-G13 review found bugs after merge (key leaks, a book-merging data bug, a dry-run hole). Safety-critical paths need a human before merge, not after.
**Depends on:** nothing. Do this first; it is cheap.
**Scope:** `CODEOWNERS` for `app/core/{publish,orchestrator,verify,paths}.py`, `app/api/auth.py`, `scripts/release_guard.sh`, `.github/workflows/`. Branch protection on `main`: PR required, CI checks required, code-owner review required on those paths. PR template asks "which `R-SAFE-*` does this touch?". CONTRIBUTING: one PR per goal, always based on `main` (no stacked PRs; #116 never reached `main`).
**Done when:** `gh api repos/paruff/Media-Refinery/branches/main/protection` shows the required checks and code-owner review; a test PR touching `publish.py` requests the owner automatically; CONTRIBUTING states the no-stack rule.
**Note:** branch protection is a repository setting, so a human applies it (the goal prepares the exact `gh api` call).

```text
/goal G14 from plan.md: add CODEOWNERS, a safety-invariant PR checklist and the no-stacked-PR rule, and prepare the branch-protection call — done when CODEOWNERS validates and the protection settings are applied and verifiable via gh api.
```

## G15 — Messy-library corpus, crash invariants, library dry-run report

**Why:** Nothing has run against a realistic, messy library; NF-6 throughput is unmeasured; the zero-loss promise is argued, not proven.
**Depends on:** G14 (review gate), but can start in parallel.
**Scope:** (1) A generated "messy library" corpus (`tests/corpus/`, no real media in git): missing/contradictory tags, multi-disc, duplicate albums, odd filenames and unicode, mixed sample rates and VBR, truncated and zero-byte files, lossy next to lossless. (2) Crash-injection tests: kill the daemon at every saga/state step and assert the invariants: source never modified, no partial file in a library, a rerun converges to the same result, nothing duplicated. (3) `refinery plan <dir>` prints a library-level report (counts by outcome, items needing review, estimated disk and time) with zero writes. (4) Nightly job measures throughput (NF-6) on a 1k-file corpus.
**Done when:** `make corpus-test` passes in the CI image; the crash-injection suite enumerates every step in `STAGE_ORDER` plus the publish saga and asserts all four invariants; a dry-run report on the 1k-file corpus completes in the time stated in the PR and is attached to the issue; throughput numbers are recorded in `docs/DEVELOPMENT.md`.

```text
/goal G15 from plan.md: build the generated messy-library corpus, crash-injection invariants and library-level dry-run report — done when make corpus-test passes in the CI image and measured throughput is recorded.
```

## G16 — Lead pipeline (music) boringly reliable

**Why:** Five media types at "first cut" is breadth over depth. The product is trust: one lost or mangled file costs more than ten missing features. Make ONE pipeline boringly reliable, then repeat the pattern.
**Depends on:** G15 (corpus + invariants).
**Lead pipeline:** music (the best-specified contract, highest file volume). Change this line if you prefer movies; the goal is otherwise identical.
**Scope:** Per-type enable flags (spec §8) with only the lead type on by default; other types documented as experimental and off. Close every open item for the lead type in #99, #95, #107, #108 or defer it in writing. Idempotent re-ingest (same file twice is a no-op; a moved file is not a new item). Verify lossy sources are never transcoded and tags/cover/ReplayGain survive, on the corpus.
**Done when:** the music corpus suite is green with no unexpected quarantines; running the pipeline over its own output tree is a no-op (idempotence test); `ENABLED_TYPES` defaults to music and is documented; the music-related checklists in #99/#95/#107/#108 are fully ticked or have a written deferral.

```text
/goal G16 from plan.md: make the music pipeline reliable on the corpus with per-type enable flags — done when the music corpus suite is green, re-running over the output tree is a no-op, and the lead-type review checklists are closed or deferred in writing.
```

## G17 — External-service contract tests

**Why:** TMDB, TVDB, MusicBrainz, AcoustID, Plex, Jellyfin, Audiobookshelf and Music Assistant are only mocked. Mocks encode our assumptions, not the providers' behaviour. Music Assistant's call was never verified.
**Depends on:** none (feeds G16).
**Scope:** Small recorded real responses per provider (kept under `tests/contracts/`, with a script to refresh them) parsed by the real code. A nightly workflow with a docker compose profile starting Jellyfin and Audiobookshelf (and Plex only if feasible) to prove the notify endpoints. Mark Music Assistant experimental until verified against a real instance.
**Done when:** each provider has a recorded fixture and a test that parses it; the nightly contract workflow exists and is green or documents the skipped servers; the Music Assistant call is either verified or flagged experimental in docs.

```text
/goal G17 from plan.md: add recorded provider fixtures with parse tests and a nightly server-contract workflow — done when every provider has a fixture test and the nightly workflow is green or its skips are documented.
```

## G18 — Decompose the orchestrator

**Why:** `app/core/orchestrator.py` is a god class (over 1,100 lines, per-media-type `if` ladders), breaking the repo's own 800-line rule and making every type hard to test alone.
**Depends on:** G15/G16 (characterization tests must exist first; this refactor must change no behaviour).
**Scope:** Extract per-media-type strategies (classify, enrich, plan, execute, verify, publish hooks) into `app/pipeline/types/{music,video,audiobook,ebook}.py`. The orchestrator becomes the stage driver only.
**Done when:** `wc -l app/core/orchestrator.py` < 400; no `MediaType.` branching ladders remain in it (`grep -c "MediaType\." app/core/orchestrator.py` <= 5); the full suite, corpus and behave features are unchanged and green; ruff complexity limits (C901, PLR0915) are enabled and pass.

```text
/goal G18 from plan.md: split the orchestrator into a stage driver plus per-media-type strategies with no behaviour change — done when orchestrator.py is under 400 lines, complexity lint is on, and all tests and the corpus are unchanged.
```

## G19 — Positioning, onboarding, operability

**Why:** "Who is this for and why not Tdarr/beets/Picard/Calibre?" is unanswered, and a new user has no safe first run.
**Depends on:** G16 (what is supported), G15 (`refinery plan` report).
**Scope:** README: who it is for, what it is not, how it differs from Tdarr, the *arr apps, beets, Picard and Calibre. First-run flow: `refinery doctor` (tools present, paths writable, keys set, servers reachable) then `refinery plan <library>` (no writes) then approve. Fix compose env passthrough so `.env` reaches the container (#106). Metrics: items by state/type, failures by quarantine reason, stage durations. UI summary shows quarantine reasons with a suggested action.
**Done when:** a fresh clone reaches "published" via doctor, plan, approve in the README quickstart, proven by the compose smoke test; `/api/v1/metrics` exposes the three new series; #106 is closed.

```text
/goal G19 from plan.md: add positioning docs, refinery doctor, env passthrough and richer metrics — done when the README quickstart is proven by the smoke test and #106 is closed.
```

## G20 — Review backlog burn-down and promotion checklist

**Why:** The G0-G13 reviews left ~70 unchecked minor/Important items, and four media types are parked. Decide deliberately instead of drifting.
**Depends on:** G16 (the bar), G17.
**Scope:** Burn down remaining review items in priority order: security first (#103 cookie flags/Host allow-list/login throttle, #102, #105), then correctness. Promotion checklist in `docs/`: a parked type (video, TV, audiobooks, ebooks) is switched on only when it meets the lead-type bar (corpus suite, idempotence, provider contracts, crash invariants). Promote one type at a time.
**Done when:** every `review-finding` issue is closed or carries a written deferral; `docs/PROMOTION.md` exists; at least the second type has either been promoted by checklist or has an explicit "stays experimental because..." note.

```text
/goal G20 from plan.md: burn down the review-finding backlog and define the promotion checklist for parked media types — done when every review-finding issue is closed or deferred in writing and docs/PROMOTION.md exists.
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

### Phase 2

| Goal | Issue |
|---|---|
| G14 Review gate for risky code | #122 |
| G15 Messy-library corpus, crash invariants, library dry-run report | #123 |
| G16 Lead pipeline (music) boringly reliable | #124 |
| G17 External-service contract tests | #125 |
| G18 Decompose the orchestrator | #126 |
| G19 Positioning, onboarding, operability | #127 |
| G20 Review backlog burn-down and promotion checklist | #128 |
