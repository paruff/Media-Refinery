Feature: Normalize filenames, folders, and metadata
  Converts messy or inconsistent media into clean, predictable structures.

  Scenario: Normalize movie filenames
    Given a movie file with messy naming
    Then rename it to:
      """
      Movie Name (Year).mkv
      """

  Scenario: Normalize TV series filenames
    Given a series episode file
    Then rename it to:
      """
      Show Name - S01E02 - Episode Title.mkv
      """

  Scenario: Normalize music filenames
    Given a track file
    Then rename it to:
      """
      01 - Track Title.flac
      """

  Scenario: Normalize directory structure
    Given a movie, series, or album
    Then move it into the correct canonical directory:
      | Movies/Movie Name (Year)/ |
      | TV/Show Name/Season 01/   |
      | Music/Artist/Year - Album/ |

  Scenario: Normalize metadata tags
    Given a file with incomplete metadata
    Then enrich metadata using:
      | MusicBrainz (music) |
      | TMDB (movies) |
      | TVDB/TMDB (series) |
