# REVIEW.md — Code review guide

How to review a change to Media Refinery (humans and AI agents alike). This repo moves
and rewrites people's only copies of their media, so a review is about one question:
**can this change lose, corrupt, mislabel or expose a file?** Style is the linters' job.

Sources of truth: [spec.md](spec.md) (requirement IDs), [intent.md](intent.md)
(principles), [DESIGN.md](DESIGN.md) (UI). Cite the requirement ID in every finding
that one applies to.

## How to run a review

1. Read the linked goal/issue and its **Done when**. Confirm the PR actually proves it
   (a test or command output in the PR), not just claims it.
2. Read the full diff, then **trace each changed function's callers** (`grep -rn`); a fix
   in one caller that leaves siblings broken is a finding.
3. Run locally: `make ci` (ruff, mypy, pytest, behave). For pipeline/IO changes also run
   the relevant feature with real ffmpeg on generated fixtures.
4. Walk the three checklists below in order: **Safety & correctness → Security → Bugs**.
5. Report findings in the format at the end. No finding without a concrete failure
   scenario (input/state → wrong result).
6. Move the issue to **Human Review** only when CI is green and no `BLOCK` finding is open.

---

## 1. Data safety & correctness (highest priority)

| # | Check | Spec |
|---|---|---|
| S1 | No code path deletes, truncates, or overwrites an original in `input/`. Originals only move to `archive/` **after** a passing `VerificationRecord`. | R-SAFE-1 |
| S2 | Outputs are written to `work/` then published by atomic `os.replace` on the same filesystem, or copy → fsync → verify hash → rename across filesystems. No direct writes into library roots. | R-SAFE-2 |
| S3 | Every state transition is committed **before** the side effect it describes, and is recoverable after a crash between the two (what happens if the process dies on this line?). | R-PIPE-1 |
| S4 | Errors are not swallowed. `except Exception: pass`, logging-then-continuing as success, or returning a "SUCCESS" stub on failure is a BLOCK. Failures go to `error`/quarantine with reason. | R-VERIFY-1 |
| S5 | Dry-run paths perform zero writes outside `work/dry-run/` (check every new `open(..., "w")`, `shutil.*`, `os.rename/replace/remove`, `mkdir`). | R-SAFE-4 |
| S6 | Identity/duplicate logic uses content (sha256 / fingerprint), never path alone; a duplicate is a plan decision, never a silent skip. Perceptual hashes compare multiple frames. | R-PIPE-2, R-PIPE-7 |
| S7 | Output conforms to the media type's contract in spec §3 (container, codecs, tags, layout) and the verify step actually checks it — not just that ffmpeg exited 0. | §3, §6 |
| S8 | Re-encode only when needed: conformant inputs are remuxed/copied (assert the ffmpeg args). Lossy→lossy re-encodes need a justification. | R-VIDEO-1, R-MUSIC-1 |
| S9 | Multi-file units (album, audiobook, multi-part movie) succeed or fail as a unit; no half-published album. | R-PIPE-6 |
| S10 | Idempotency: running the same input twice produces identical output paths and no new items/duplicates. | intent |

## 2. Security

| # | Check | Spec |
|---|---|---|
| X1 | **Path traversal:** every path derived from metadata (titles, artists, TMDB/MusicBrainz responses, filenames) goes through the sanitizer and is checked with `Path.resolve().is_relative_to(library_root)`. `..`, absolute paths, leading dots, NUL, and >255-byte components rejected. | R-SAFE-3 |
| X2 | **Command injection:** subprocesses use `create_subprocess_exec`/`subprocess.run([...])` with a list — never `shell=True`, never f-string commands. Filenames beginning with `-` are passed after `--` or as `file:` URLs so ffmpeg can't read them as options. | R-SAFE-5 |
| X3 | Every subprocess and HTTP call has a timeout; stderr is captured and size-limited before logging. | R-SAFE-5 |
| X4 | **Secrets** (TMDB, AcoustID, Plex/Jellyfin/ABS tokens, `MR_API_TOKEN`) come from env/`*_FILE` only; never in logs, exceptions, API responses, or `VerificationRecord`. Check `repr`/`model_dump` of config objects. | R-SAFE-6 |
| X5 | **API auth:** non-health routes require the bearer token when bound beyond localhost; mutating routes are POST + JSON only (CSRF); no wildcard CORS with credentials. | R-API-1 |
| X6 | **Untrusted metadata is untrusted input:** API/tag/subtitle text is length-limited and escaped in the UI (Jinja autoescape on; no `\|safe` on external data). | R-UI |
| X7 | **SQL:** ORM or bound parameters only; no string-built SQL, including `text(f"...")`. | — |
| X8 | **Parsers:** no `yaml.load` (use `safe_load`), no `pickle`/`eval` on file or network data; XML (EPUB/OPF, NFO) parsed with `defusedxml`. | — |
| X9 | **Dependencies:** new runtime deps are justified, pinned, imported by `app/`, and pass `pip-audit`/Trivy. No dev tools in runtime requirements. | NF-2 |
| X10 | Container runs non-root; new volumes/ports are documented; no secrets baked into the image. | NF-5 |
| X11 | DRM content is detected and quarantined, never processed. | R-EBOOK-4 |

## 3. Bug hunt (common failure modes in this codebase)

- **Async correctness:** blocking calls (`subprocess.run`, `requests`, `os.walk` over a large tree, `time.sleep`, sync file hashing) inside `async def` — use `asyncio.to_thread` or async APIs. `loop.create_task` called from another thread (use `run_coroutine_threadsafe`). Fire-and-forget tasks with no reference or exception handler. `asyncio.run` nested inside a running loop.
- **SQLAlchemy:** `scalar_one_or_none()` where multiple rows are possible; lazy-loaded relationships accessed after the session closes; long transactions held across ffmpeg runs; missing `await session.commit()`; sessions shared across tasks.
- **Ordering bugs:** decisions made from fields populated by a later stage (e.g. checking `audio_codec` before ffprobe ran).
- **Time:** naive `datetime.utcnow()` in tz-aware columns; use `datetime.now(UTC)`.
- **ffprobe parsing:** missing keys (`bit_rate`, `tags`, `duration` are optional), multiple audio/subtitle streams (don't keep only the last), `r_frame_rate` as a fraction string, non-UTF-8 tags.
- **Filesystems:** case-insensitive macOS/SMB volumes (two names collide), cross-device `os.rename` (`EXDEV`), files still being written (stability window), symlinks escaping roots, Unicode normalization (NFC vs NFD) in paths.
- **Partial outputs:** `.tmp` files left behind on failure; lock files not released; output existing from a prior failed run treated as success.
- **Tests that prove nothing:** mocks returning the value under test, `assert True`, skipped-when-ffmpeg-missing tests that are therefore never run in CI, tests that only check a log line.
- **Resource leaks:** `cv2.VideoCapture` / file handles not closed; unbounded queues or in-memory dicts in the watcher.

---

## Severity

| Level | Meaning | Merge |
|---|---|---|
| **BLOCK** | Can lose/corrupt/overwrite media, security vulnerability, or violates an R-SAFE-* requirement | Must fix |
| **HIGH** | Wrong result for realistic input (mislabel, wrong path, skipped file, crash) | Fix before merge |
| **MEDIUM** | Edge-case bug, missing test for new logic, unclear error | Fix or file an issue |
| **LOW** | Readability, naming, small simplification | Optional |

## Finding format

```text
[SEVERITY] path/to/file.py:LINE — one-line defect statement (Spec: R-XXX-n)
Scenario: concrete input/state → what goes wrong
Fix: smallest change that removes the failure (and the test that proves it)
```

End the review with: `Verdict: APPROVE | REQUEST CHANGES` and the commands you ran.

## Automation

- `/code-review` (Claude Code) for diff review; point it at this file.
- `/security-review` for any change touching subprocess, paths, API auth, or secrets.
- Local gate: `make hooks` once, then every commit runs the same SHA-pinned hooks as CI (`.pre-commit-config.yaml`: ruff lint+format, mypy, bandit, gitleaks, yamllint, actionlint, zizmor, hadolint, markdownlint, codespell, conventional-commit message). `make precom` runs them on all files.
- CI (`ci.yml`) runs those hooks, pytest with coverage, behave and a Docker build; `security.yml` runs full-history gitleaks plus pip-audit/Trivy (report-only until G0).
- Reviewers: a new `# noqa`, `# nosec`, hook `exclude`, or lowered `--cov-fail-under` needs a reason and a goal tag (e.g. `TODO(G1)`); the existing baseline noqa comments must only shrink.
