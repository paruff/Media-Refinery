Feature: Video file processing
  Scenario: Convert video file to target format
    Given a video file "sample_video.mp4"
    When the video file is processed
    Then the output should be in "mkv" format
    And the resolution should be "1920x1080"
    And the codec should be "h264"

  Scenario Outline: Convert video file to mkv format
    Given a video file "<video_file>"
    When the video file is processed
    Then the output should be in "mkv" format

    Examples:
      | video_file   |
      | sample.mp4   |
      | sample.avi   |
      | sample.mov   |
      | sample 2.mp4 |
