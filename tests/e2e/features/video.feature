Feature: Video file processing
  Scenario: Convert video file to target format
    Given a video file "sample_video.mp4"
    When the video file is processed
    Then the output should be in "mkv" format
    And the video codec should be "h264"
    And the audio codec should be "aac"

  Scenario Outline: Convert video file to mkv format with h264 codec
    Given a video file "<video_file>"
    When the video file is processed
    Then the output should be in "mkv" format
    And the video codec should be "h264"

    Examples:
      | video_file   |
      | sample.avi   |
      | sample.mov   |
      | sample.mp4   |
      | sample.wmv   |

  Scenario Outline: Convert video file to mkv format with h265 codec
    Given a video file "<video_file>"
    When the video file is processed
    Then the output should be in "mkv" format
    And the video codec should be "h265"

    Examples:
      | video_file   |
      | sample.avi   |
      | sample.mov   |
      | sample.mp4   |
      | sample.wmv   |