Feature: Video file processing
  Scenario: Convert video file to target format
    Given a video file "sample_video.mp4"
    When the video file is processed
    Then the output should be in "mkv" format
    And the video codec should be "h264"
    And the audio codec should be "aac"