Feature: TV show processing
  Scenario: Extract metadata from TV show file
    Given a TV show file "Show.Name.S01E01.mkv"
    When the file is processed
    Then the metadata should include:
      | show   | Show Name |
      | season | 01        |
      | episode| 01        |