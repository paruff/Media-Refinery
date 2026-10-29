# Development

Host tools such as ffmpeg are not required: anything that needs them runs in Docker.

## Setup

```bash
make venv                  # uv, Python 3.14, hash-locked requirements
source .venv/bin/activate
pre-commit install
```

## Workflow

1. Branch, then write a failing test first (TDD).
2. Implement, then `make test` (unit, integration, behave features).
3. `make precom` runs the same hooks as CI (ruff, mypy, bandit, yamllint, hadolint, …).
4. Commit with `<type>: <description>` (feat, fix, refactor, docs, test, chore, perf, ci) and open a PR; see [REVIEW.md](../REVIEW.md).

Useful targets: `make unit`, `make integration`, `make features`, `make coverage`,
`make run`, `make docker-test`, `make ui-test`, `make ci`.

`make docker-test` is authoritative: it runs the same suites as the CI `test` job (unit,
integration, behave, corpus, contract fixtures, acceptance, regression) with real ffmpeg and the
80 % coverage floor. Host `make test` skips ffmpeg-dependent tests, so green there is not CI green.
`make ci` = `make precom` + `make docker-test` + `make compose-check`.

The `# noqa` count may only shrink (`tests/unit/test_noqa_ratchet.py`): lower `BASELINE` when you
remove one. Requirements drift: `make deps-lock` re-locks everything; review the diff.

## Security scans: ignoring a finding

`security.yml` (pip-audit, Trivy, gitleaks) is blocking. Prefer upgrading or pinning. If a finding
has no fix or does not apply, ignore it narrowly, with a reason and an expiry (re-check by then):

- pip-audit: add `--ignore-vuln GHSA-xxxx-xxxx-xxxx` to the step, with a comment
  `# reason; expires YYYY-MM-DD`.
- Trivy: add the ID to `.trivyignore` at the repo root (`CVE-YYYY-NNNN exp:YYYY-MM-DD`, with a
  `#` comment line above it giving the reason) and set `trivyignores: .trivyignore` on the
  trivy-action step. Trivy ignores an entry after its `exp:` date, so it fails loudly again.
- gitleaks: use `.gitleaksignore` (fingerprints) for a verified false positive only.

## Testing

```text
tests/unit         fast, isolated
tests/integration  real ffmpeg on tiny generated fixtures
tests/e2e          full pipeline per media type
tests/features     behave (Gherkin) happy paths
tests/corpus       generated messy library, crash injection, throughput (make corpus-test)
```

- Fixtures are generated (`ffmpeg -f lavfi`); never commit real media.
- Coverage floor is 80 % on `app/`.
- Never weaken an `R-SAFE-*` rule to make a test pass.

### Messy-library corpus and crash injection (G15)

`make corpus-test` (inside the CI image) runs `tests/corpus`:

- `generate.py` builds the corpus: missing and contradictory tags, multi-disc, duplicate albums,
  unicode and odd filenames, mixed sample rates and VBR, truncated, zero-byte and garbage files,
  lossy next to lossless. `bulk()` pads it to any size. Nothing is committed.
- `test_crash_invariants.py` kills the daemon before and after every DB commit, file move,
  ffmpeg call, archive and quarantine step (this covers every `STAGE_ORDER` state and the
  publish saga), restarts, and asserts: the source is held exactly once in input or archive,
  no partial file ever sits in a library, the run converges to the clean-run result, nothing is
  duplicated, and a second restart changes nothing.
- `test_messy_library.py` runs the whole pipeline over the corpus: no source lost, nothing
  broken published, every library file decodes, a rerun is a no-op.

`refinery plan <dir>` prints the library-level report (counts by outcome, items needing review
or not planned, estimated disk and time) and never writes outside `work/dry-run/`.

Known gaps the corpus surfaced, left for G16: byte-identical duplicates are marked `error`
rather than being a plan decision (R-PIPE-7), and a 1 s track makes `fpcalc` exit 2, which is
logged as an error but handled.

## Performance

NF-6 throughput (`make corpus-bench`: scan + plan, dry run, no transcode), measured on a
1,000-file generated corpus in the CI image on a 2018 Intel MacBook Pro (colima VM, 4 CPUs,
8 GiB), 2026-10-28:

| files | ingest | plan | total | files/s | 10k tracks (extrapolated) |
|------:|-------:|-----:|------:|--------:|--------------------------:|
| 1,000 | 9.8 s  | 180.8 s | 190.6 s | 5.25 | about 32 min (target: under 60 min) |

The nightly workflow re-measures this and uploads `throughput.json`.

- Concurrency is bounded per stage; the adaptive throttle halves workers after consecutive failures.
- Keep `/work` on fast storage and on the same filesystem as `/output`.
- Encode settings (including hardware acceleration) come from the device profiles in `profiles/`.

## Observability

Logs are structured with `item_id` and `run_id`. `/health` and `/ready` are the probes; the image `HEALTHCHECK` probes `/ready`.
Prometheus metrics (`media_refinery_items{state,type}`) are at `GET /api/v1/metrics` (bearer token required).

## FAQ

- **Where do I put media for testing?** Generate fixtures; `sample_media/` holds a few tiny samples.
- **How do I report a security issue?** See [SECURITY.md](../SECURITY.md).
