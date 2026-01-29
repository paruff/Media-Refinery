Title: feature(test): audio/music end-to-end BDD + integration + unit tests (audio processing)

Add a focused test story for audio/music processing to validate end-to-end behavior and build supporting integration and unit tests. This story introduces a BDD feature for audio processing and breaks work into integration tests that exercise the pipeline, plus focused unit tests for `pkg/processors`, `pkg/validator`, and `pkg/storage`.

Motivation:
Ensure audio processing is reliable, idempotent, and observable. Tests will prove conversion (dry-run vs real), metadata preservation, checksum/validation, and error handling.

Acceptance criteria:
- BDD feature file exists at `test/integration/features/audio.feature`.
- Integration tests exercise both dry-run and real-conversion and skip real when `ffprobe`/`ffmpeg` are not available.
- Unit tests validate ffmpeg argument branches, `ComputeChecksum`, `ProbeMediaFile` failure paths, and storage dry-run recording/rollback.
- CI runs integration tests in an `ffmpeg`-enabled job or container.

Files added/changed:
- `test/integration/features/audio.feature` (BDD)
- `test/integration/audio_integration_test.go` (integration scaffold)
- `pkg/processors/audio_processor_test.go` (unit scaffolding)

Estimate: 3–5 points
Labels: enhancement, tests, audio, integration
