Feature: Device Profile Constraint Solver
  Scenario: Plan for Samsung Tizen
    Given a file with audio "aac", video "h264", width 1920, height 1080, container "mp4"
    And a device profile "samsung_tizen"
    When I plan for the device
    Then the plan should not require transcode_audio
    And the plan should not require transcode_video
    And the plan should not require resize
    And the plan should not require remux

  Scenario: Plan for unsupported audio
    Given a file with audio "flac", video "h264", width 1920, height 1080, container "mp4"
    And a device profile "samsung_tizen"
    When I plan for the device
    Then the plan should require transcode_audio
