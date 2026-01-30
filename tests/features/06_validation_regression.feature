Feature: Validate final library structure after migration
  Ensures that all media now conforms to ideal formats and Plex/Music
  Assistant can index without errors.

  Scenario: Validate movie structure
    Given a movie directory
    Then the directory MUST contain exactly one correctly named movie file
    And the file MUST use supported codecs and audio

  Scenario: Validate TV series structure
    Given a show directory
    Then all episodes MUST follow SxxEyy naming
    And all seasons MUST be in Season NN folders

  Scenario: Validate music structure
    Given an album directory
    Then all tracks MUST have:
      | Track Number |
      | Title |
      | Artist |
      | Album Artist |
    And filenames MUST follow:
      | 01 - Track.flac |

  Scenario: Validate artwork
    Given any media directory
    Then artwork MUST be present or retrievable

  Scenario: Validate no orphan files remain
    Given the library root
    Then no files SHOULD remain in unclassified locations
