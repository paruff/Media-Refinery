Feature: Transactional Saga Pattern for File Moves
  As a system
  I want to ensure zero data loss during cross-volume moves
  So that unfinished .tmp files are always cleaned or resumed

  Scenario: Prepare-Commit-Cleanup lifecycle
    Given a NormalizationPlan with a valid source and target
    When the plan is executed
    Then the file is first written as .tmp
    And a WAL entry is created with status "prepared"
    When the file is verified and committed
    Then the WAL entry is updated to "committed"
    And the .tmp file is atomically renamed
    And the output file exists

  Scenario: Recovery of unfinished .tmp files
    Given a NormalizationPlan with a .tmp file left from a crash
    When the system restarts
    Then the .tmp file is either cleaned or atomically renamed
    And the WAL entry is updated accordingly
