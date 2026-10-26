Feature: movies2vlib parity
  The daemon keeps movies2vlib's operational hardening: dry-run, conversion
  with a move into the library, and health-check failures landing in quarantine,
  with a JSONL trace of every step.

  Scenario: Dry-run leaves the library untouched and traces a dry_run event
    Given a pipeline workspace in dry-run mode
    And a generated MKV in the input directory
    When the pipeline runs until idle
    Then input and the library roots are byte-identical to before
    And the trace has a "plan" event with status "dry_run"
    And every trace line is valid against the trace schema

  Scenario: A file needing conversion is converted and moved into the library
    Given a pipeline workspace
    And a generated AVI in the input directory
    When the pipeline runs until idle
    And I approve every planned item
    And the pipeline runs until idle
    Then every item is in "validated" state
    And the movie "Test Movie (2020)" exists in the movies library as MKV
    And the original is archived
    And the trace has a "execute" event with status "success"
    And the trace has a "audio.atmos" event with status "skipped"
    And every trace line is valid against the trace schema

  Scenario: A corrupted file fails the health check and is quarantined
    Given a pipeline workspace
    And a generated MKV with corrupted video data in the input directory
    When the pipeline runs until idle
    And I approve every planned item
    And the pipeline runs until idle
    Then the file is quarantined as "healthcheck_failed"
    And the library roots are empty
    And the trace has a "healthcheck" event with status "failed"
    And the trace has a "repair" event with status "failed"
    And every trace line is valid against the trace schema
