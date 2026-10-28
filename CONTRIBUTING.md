# Contributing

- **One PR per goal, always based on `main`.** No stacked PRs: a PR merged into another PR's branch
  never reaches `main` (this happened to #116).
- Tests first; run them in Docker (`make docker-test`), not on the host.
- The PR template asks which `R-SAFE-*` rules (see `spec.md`) your change touches.
- Changes to the paths in `.github/CODEOWNERS` (publish, orchestrator, verify, paths, auth,
  release guard, workflows) need code-owner approval before merge.
- `main` is protected: PR required, CI checks required. Maintainers apply the settings with
  `scripts/protect_main.sh`.
