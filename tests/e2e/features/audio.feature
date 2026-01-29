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