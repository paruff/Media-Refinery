Feature: Input detection
  Scenario: Detect new file in input directory
    Given a file "test_song.mp3" exists in the input directory
    When the watcher scans for new files
    Then the database should show the file "test_song.mp3" in "scanned" state
