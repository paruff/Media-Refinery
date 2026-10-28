# Verification and validation

What "CI is green" means. Every check below is deterministic: pinned tool versions and actions,
fixed runner image, generated fixtures, no live third-party services. The single required
status check is **CI gate** (`.github/workflows/ci.yml`); it fails unless every job below
succeeded.

| Question | Check | Where |
| --- | --- | --- |
| Is it built correctly? (verification) | ruff lint + format, mypy, bandit, gitleaks, yamllint, actionlint, zizmor, hadolint, markdownlint, codespell | CI `hooks` (same hooks as `make precom`) |
| Does the code behave as specified? | unit + integration tests, **coverage floor 80%** (`--cov-fail-under`), BDD features, offline recorded-provider fixtures, acceptance, regression | CI `test` |
| Does it survive messy data and crashes? | generated messy-library corpus, crash injection at every commit/move/ffmpeg/archive/quarantine point (source held once, no partial file, convergence, no duplicates) | CI `test` |
| Does the API contract hold? | OpenAPI snapshot, Alembic drift test | CI `test` (unit) |
| Does the shipped image work? (validation) | image builds; **compose smoke**: doctor, plan, approve through the API, then one fixture per media type must be published | CI `docker-build`, `smoke` |
| Is the published artifact the tested one? | release re-runs the smoke on the exact multi-arch digest, then Trivy (0 critical, amd64 + arm64) before promoting | `release.yml` |

## Not in the gate, on purpose

Anything whose result changes without a code change:

- Vulnerability databases (Trivy, dependency audit): `security.yml`, weekly and per PR, reporting.
- Real Jellyfin / Audiobookshelf servers, NF-6 throughput on a 1k-file corpus: `nightly.yml`.

A nightly failure is investigated and, if it reveals a missing deterministic check, a recorded
fixture or corpus case is added to the gate.

## Coverage

Coverage is enforced, not reported to a third party: the `test` job fails below 80% line+branch
coverage of `app/`, and uploads `coverage.xml` as a build artifact. There is no Codecov upload
(it needs a repository token and never blocked a merge).

## Branch protection

`scripts/protect_main.sh` requires **CI gate** plus a code-owner review. After adding or renaming
a job, add it to `needs:` of the `gate` job; branch protection never changes.
