Feature: Ideal Plex TV Series Library Structure
  Ensures that TV series are named, encoded, and organized so Plex can
  correctly match episodes and seasons.

  Background:
    Given a TV library root at "/TV"

  Scenario: Standard series directory layout
    Given a show titled "Show Name"
    Then the directory MUST be:
      """
      /TV/Show Name/
      """

  Scenario: Standard season directory layout
    Given season 1 of a show
    Then the directory MUST be:
      """
      /TV/Show Name/Season 01/
      """

  Scenario: Episode naming
    Given an episode with season 1 and episode 2
    Then the filename MUST be:
      """
      Show Name - S01E02 - Episode Title.mkv
      """

  Scenario: Multi‑episode files
    Given a file containing episodes 1 and 2
    Then the filename MUST be:
      """
      Show Name - S01E01E02.mkv
      """

  Scenario: Supported codecs for Samsung Series 65
    Then the video codec MUST be:
      | H.264 |
      | H.265 |
    And audio MUST be:
      | AAC |
      | AC3 |
      | EAC3 |

  Scenario: Subtitle compatibility
    Then subtitles MUST be:
      | SRT |
      | WebVTT |
    And MUST NOT be:
      | PGS |
      | VobSub |
