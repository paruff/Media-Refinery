# Contributing

1. Fork and clone the repository.
2. Set up the environment as described in [DEVELOPMENT.md](DEVELOPMENT.md).
3. Create a branch and write a failing test first.
4. Run `make test` and `make precom` until both pass.
5. Open a pull request using the template; CI must be green and the [REVIEW.md](../REVIEW.md) checklist run.

Layout: application code in `app/`, tests in `tests/`, design in [ARCHITECTURE.md](ARCHITECTURE.md),
requirements in [spec.md](../spec.md). Update the spec when behaviour intentionally changes.
