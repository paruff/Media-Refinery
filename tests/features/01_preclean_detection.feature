Feature: Detect messy or inconsistent media library elements
  Ensures that all files, folders, and metadata issues are identified before
  normalization begins.

  Background:
    Given a media library root at "/Media"

  Scenario: Detect files with missing or invalid metadata
    Given a file in the library
    When scanning metadata
    Then flag the file if any required tags are missing:
      | Title |
      | Year |
      | Season/Episode (for series) |
      | Artist/Album (for music) |

  Scenario: Detect non‑UTF8 filenames
    Given a filename
    Then flag it if it contains non‑UTF8 characters

  Scenario: Detect illegal filesystem characters
    Given a filename
    Then flag it if it contains:
      | / | \ | : | * | ? | " | < | > | | |

  Scenario: Detect duplicate or conflicting versions
    Given multiple files with the same title
    Then flag them if:
      | Different years |
      | Different resolutions |
      | Different cuts |
      | Different audio codecs |

  Scenario: Detect misplaced files
    Given a file not inside a recognized movie, series, or music structure
    Then flag it as "unclassified"
