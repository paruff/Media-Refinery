Feature: Audio file processing
  Scenario: Convert audio file to target format
    Given an audio file "sample_audio.mp3"
    When the audio file is processed
    Then the output should be in "flac" format
    And the bitrate should be "320k"
    And the sample rate should be "44100 Hz"

  Scenario Outline: Convert audio file to flac format
    Given an audio file "<audio_file>"
    When the audio file is processed
    Then the output should be in "flac" format

    Examples:
      | audio_file   |
      | sample.mp3   |
      | sample.ogg   |
      | sample.wav   |
      | sample 2.mp3 |

  Scenario: Normalize file names based on metadata
    Given an audio file "track_01.mp3"
    And the metadata includes "Artist: Example Artist" and "Title: Example Title"
    When the audio file is processed for normalization
    Then the file name should be "Example Artist - Example Title.mp3"
    And the file name should align with Music Assistant standards

  Scenario: Organize audio files into artist/album-year structure
    Given an audio file "track_01.mp3"
    And the metadata includes "Artist: Example Artist", "Album: Example Album", and "Year: 2026"
    When the audio file is processed for organization
    Then the file should be moved to "Example Artist/Example Album - 2026/track_01.mp3"
    And the directory structure should align with Music Assistant standards
