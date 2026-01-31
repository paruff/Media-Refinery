Feature: Perceptual & Acoustic Fingerprinting
  As a user
  I want the system to detect duplicate media by content, not filename
  So that renames and copies are not re-processed

  Scenario: Duplicate audio file is detected by fingerprint
    Given a media library with an audio file "song1.mp3"
    And the file has a unique fingerprint
    When I scan a new file "song1_copy.mp3" with the same content
    Then the system should detect it as a duplicate and not re-process it

  Scenario: Duplicate video file is detected by fingerprint
    Given a media library with a video file "movie1.mp4"
    And the file has a unique fingerprint
    When I scan a new file "movie1_copy.mp4" with the same content
    Then the system should detect it as a duplicate and not re-process it
