Feature: Pipeline spine
  Every dropped file runs discover -> probe -> classify -> plan -> approve ->
  execute -> verify -> publish -> archive without ever losing the original.

  Scenario: A generated MP3 and MKV reach validated after approval
    Given a pipeline workspace
    And a generated MP3 and a generated MKV in the input directory
    When the pipeline runs until idle
    Then every item is awaiting approval
    And the library roots are empty
    When I approve every planned item
    And the pipeline runs until idle
    Then every item is in "validated" state
    And the outputs exist under the library roots
    And the originals exist under the archive directory
    And every item has a passing verification record

  Scenario: Killing the daemon mid-EXECUTE and restarting completes the item
    Given a pipeline workspace
    And a generated MP3 in the input directory
    And the item is planned and approved
    When the daemon is killed during EXECUTE
    Then the item is in "executing" state
    When the daemon restarts
    Then every item is in "validated" state
    And the outputs exist under the library roots

  Scenario: Dry-run leaves input and library roots byte-identical
    Given a pipeline workspace in dry-run mode
    And a generated MP3 and a generated MKV in the input directory
    When the pipeline runs until idle
    Then input and the library roots are byte-identical to before
    And a dry-run report exists for every item
    And nothing was archived or quarantined
