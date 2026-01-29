Feature: Audio processing
  As a media refinery operator
  I want audio files processed reliably
  So that music is converted, metadata preserved, and outputs organized

  Scenario Outline: Convert audio files to target format
    Given an input audio file "<input_file>" with metadata
    And pipeline is configured with dry_run = <dry_run>
    When the pipeline runs
    Then if dry_run is true no output files are written
    And if dry_run is false at least one output file with extension ".flac" exists
    And the output path matches the music pattern
    And metadata fields (title, artist, album) are present in the output or operation recorded

    Examples:
      | input_file           | dry_run |
      | testdata/sample.mp3  | true    |
      | testdata/sample.mp3  | false   |
