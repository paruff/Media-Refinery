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

## Testing

```text
tests/unit         fast, isolated
tests/integration  real ffmpeg on tiny generated fixtures
tests/e2e          full pipeline per media type
tests/features     behave (Gherkin) happy paths
```

- Fixtures are generated (`ffmpeg -f lavfi`); never commit real media.
- Coverage floor is 80 % on `app/`.
- Never weaken an `R-SAFE-*` rule to make a test pass.

## Performance

- Concurrency is bounded per stage; the adaptive throttle halves workers after consecutive failures.
- Keep `/work` on fast storage and on the same filesystem as `/output`.
- Encode settings (including hardware acceleration) come from the device profiles in `profiles/`.

## Observability

Logs are structured with `item_id` and `run_id`. `/health` and `/ready` are the probes.
Prometheus metrics (`media_refinery_items{state,type}`) are at `GET /api/v1/metrics` (bearer token required).

## FAQ

- **Where do I put media for testing?** Generate fixtures; `sample_media/` holds a few tiny samples.
- **How do I report a security issue?** See [SECURITY.md](../SECURITY.md).
