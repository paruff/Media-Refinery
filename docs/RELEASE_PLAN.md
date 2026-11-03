# Release plan: v0.3.0 (beta)

Audit date 2026-11-03, against `main` at `0f9f39d`. Last tag is `v0.3.0-rc.2`; `main` is 35 commits ahead.

## Where the product stands

- All five media types are promoted to beta (music, ebooks, audiobooks, movies, TV) and every PROMOTION.md gate is ticked.
- `main` CI is green on the last two merges (the P4 run was still in progress when audited). Single required check `CI gate`; the compose smoke test runs on PRs.
- The B7 real-library trial (3 runs, music only) found no data loss. No other type has met a real library yet.
- Open issues: 19, none labelled as a bug except #189. The rest are `goal` trackers and `review-finding` checklists.

## Findings that matter for the release

| # | Finding | Severity | Action |
|---|---------|----------|--------|
| 1 | Weekly **Security** workflow is red on `main` (2 Nov): gitleaks flags a commented-out `apiKey :=` line in `.github/copilot-instructions.md` (Go-era leftover), found in full history | Blocker for a clean release | Delete the file (or add a path allowlist in `.gitleaks.toml`) and re-run. Confirm it is a false positive first |
| 2 | **#189**: the PLAN backstop reports a `media_item_id` UNIQUE violation as `plan_conflict` (wrong label, hides a re-plan bug) | Medium, the only open bug | Fix before tag; small, has a suggested design in the issue |
| 3 | Only music has been trialled on real data. Movies, TV, audiobooks and ebooks are "beta" on generated corpora and contract fixtures alone | Release-note risk | Either run one real-data trial per type, or ship the tag as `-rc` for those types and say so in the notes |
| 4 | Version drift: `pyproject.toml` says `0.3.0-rc.2`; README badge, `requires-python >=3.14` and the Dockerfile are all 3.14, while plan.md G0 and #96 say 3.12 | Low | Decide 3.14 is intended (the `except A, B:` syntax in `smart_mode.py` needs it), then record it in plan.md and close that #96 item |
| 5 | #103 UI before→after diff is still a spec gap (UI shows the path pair) | Medium | Decide: build it, or amend `spec.md` R-UI to say path pair only. Listed in B6 |
| 6 | #104 (server handoff): Music Assistant is already flagged experimental in `docs/DEPLOYMENT.md`; a malformed `PLEX_SECTIONS` still fails startup (typed `dict` setting), URL validation not done | Low to medium | Fix the startup failure with a warning; tick the experimental item |
| 7 | #99 last box is stale: `music_id.py` now has the AcoustID 3 req/s pacer, 429/5xx backoff and honours `MUSICBRAINZ_USER_AGENT` (`_releases` eviction not re-checked) | Low | Tick the box |
| 8 | Issue hygiene: B1–B6 (#144–#149) are still open although their follow-ups (#168–#172) are merged | Housekeeping | Check each Done-when, close or comment |
| 9 | `sample_media/` (56 KB of real media) is tracked, against the "no real media in git" rule. `media-refinery.db`, `rotation.log`, `build/` are ignored, so fine | Low | `git rm -r sample_media` unless a test uses it |
| 10 | 119 remote branches (many `copilot/*`) | Low | Prune merged and stale ones |
| 11 | Deferred minors: `*.lock` left beside outputs, `_LocalCelery.send_task` swallows exceptions, noqa-count guard, base image by tag in canary, `_run.py` logs full stderr at ERROR | Low | Leave deferred (written in `docs/BACKLOG_DEFERRALS.md`); do not block the tag |

## Live check (2026-11-03, local colima)

`docker build -t media-refinery:ci .` from `main` succeeded and `scripts/smoke.sh` passed: doctor, plan and approve, then Movies, TV, Music, Audiobooks and Books each published ("all 5 media types processed"). Noise: fpcalc exits 2 on the 2-second smoke MP3s and logs a full traceback per file (handled, but loud). I did not run the unit suite or Trivy locally.

Corrections to the first draft: the `# noqa` count in `app/` is 5, not 176; `_prune_old_errors` no longer blanks `error_log`; `sample_media/` is only referenced by the stale copilot-instructions file.

## Plan

### Phase A: unblock (about 1 day)

1. Resolve the gitleaks finding (#1) and confirm `Security` goes green on a manual run.
2. Fix #189 with a regression test (re-plan of the same item).
3. Wait for the P4 CI run on `main` to finish green.
4. Close B1–B6 where their Done-when is met (#8); comment on any that are not.
5. Remove `sample_media/` and prune dead branches (#9, #10).

### Phase B: decide and document (about 1 day)

6. Pick one of: build the UI diff, or amend `spec.md` (#5). Recommended: amend the spec; the diff is a feature, not a release gate.
7. Fix the `PLEX_SECTIONS` startup failure (#6); mention Music Assistant as experimental in the README too.
8. Tick the stale #99 box (#7).
9. Record the Python 3.14 decision (#4).

### Phase C: validate on real data (2 to 4 days, parallelisable)

10. Repeat `scripts/beta_trial.sh` on a copy of a real library for each non-music type, as `docs/BETA_TRIAL.md` did for music. Record counts, quarantines and bugs. Minimum: one run each for movies and audiobooks (highest data-loss and re-encode risk). Exit rule: no open data-loss bug.
11. Run the nightly workflow once on `main` and confirm the contract-server job (Jellyfin, Audiobookshelf) is green.

### Phase D: cut the release

12. Move `CHANGELOG.md` `[Unreleased]` to `[0.3.0]` with a date, set `pyproject.toml` to `0.3.0`, and add a one-paragraph "what is beta, what is experimental" at the top of the notes (Music Assistant experimental; non-music types trialled on N libraries).
13. Tag `v0.3.0-rc.3` first: verify the GHCR image publishes, Trivy reports 0 critical, the smoke job passes, and `:latest` does not move.
14. If rc.3 is clean after a few days of use, tag `v0.3.0`, publish the GitHub release (none exists yet; there are only tags) and let `:latest` move.
15. Post-release: open P5 for the deferred minors, and update the plan.md Phase 3 tracking table (it still says "P1–P4: create when B7 is done").

## Go / no-go for v0.3.0

- [ ] `CI` and `Security` green on the tagged commit
- [ ] #189 closed; no open data-loss bug
- [ ] Real-data trial recorded for each type listed as supported in the notes
- [ ] rc.3 image published, Trivy 0 critical, `:latest` unmoved until final
- [ ] CHANGELOG, `pyproject.toml` version and README beta wording agree

## Status after the cleanup branch (`chore/release-cleanup-v0.3.0`)

Done: findings 1 (stale file removed), 2 (#189), 4 (3.14 recorded in plan.md), 6 (`PLEX_SECTIONS`), 9 (`sample_media/`). Finding 5 needed no work: `spec.md` R-UI was already amended in #166 (path pair, source codecs and planned actions; per-tag and artwork diffs out of scope) and the Review view implements exactly that. `DESIGN.md` is the UI spec: spec R-UI links it and pre-commit lints it.

Music Assistant 2.10.4 at `DS920plus.local:8095` is reachable and `music/sync` is in its command list (Bearer auth, scope `library.write` or higher). The end-to-end call is blocked on an API token in `.env` (`MUSIC_ASSISTANT_TOKEN` is empty).

Real-library trials (finding 3) are blocked on macOS privacy: the shell cannot read `/Volumes/music` and `/Volumes/media` ("Operation not permitted"). Grant the terminal/IDE Full Disk Access (or network-volume access), then copy a small slice per type and run `scripts/beta_trial.sh`.

Still open: branch pruning (needs your OK), the real-library trials, the MA token check, and tagging.
