Feature: TV show processing
  Scenario: Process TV show metadata
    Given a TV show file "Breaking Bad - S01E01.mkv"
    When the TV show file is processed
    Then the metadata should include "Title: Pilot"
    And the metadata should include "Season: 1"
    And the metadata should include "Episode: 1"

  Scenario Outline: Process TV show metadata for multiple files
    Given a TV show file "<tvshow_file>"
    When the TV show file is processed
    Then the metadata should include "Title: <title>"
    And the metadata should include "Season: <season>"
    And the metadata should include "Episode: <episode>"

    Examples:
      | tvshow_file                     | title   | season | episode |
      | Breaking Bad - S01E01.mkv      | Pilot   | 1      | 1       |
      | Breaking Bad - S01E02.mkv      | Cat's   | 1      | 2       |
      | Breaking Bad - S01E03.mkv      | Dog's   | 1      | 3       |