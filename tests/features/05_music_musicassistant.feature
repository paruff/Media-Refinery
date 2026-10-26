Feature: Ideal Music Assistant Local Library Structure
  R-MUSIC-1..5: albums are identified (AcoustID -> MusicBrainz), tagged, given a
  cover, and published as Music/{AlbumArtist}/{Album} ({Year})/. A low-confidence
  match stops at Review.

  Scenario: A three-track album is identified, tagged and published
    Given a music workspace with mocked AcoustID, MusicBrainz and Cover Art Archive
    And a generated FLAC album of 3 tracks
    When the pipeline runs until idle
    Then the album is published in "Test Artist/Test Album (2021)" as:
      | file                 |
      | 01 - Track One.flac  |
      | 02 - Track Two.flac  |
      | 03 - Track Three.flac |
    And every published track carries all R-MUSIC-2 tags
    And every published track embeds a front cover of at least 500 px
    And the album folder holds cover.jpg
    And flac verifies every published track

  Scenario: A two-disc release gets a disc prefix
    Given a music workspace with mocked AcoustID, MusicBrainz and Cover Art Archive
    And a generated FLAC album of 3 tracks on 2 discs
    When the pipeline runs until idle
    Then the album is published in "Test Artist/Test Album (2021)" as:
      | file                 |
      | 1-01 - Track One.flac |
      | 1-02 - Track Two.flac |
      | 2-01 - Track Three.flac |

  Scenario: Lossy sources are tagged but never transcoded
    Given a music workspace with mocked AcoustID, MusicBrainz and Cover Art Archive
    And a generated MP3 album of 3 tracks
    When the pipeline runs until idle
    Then the album is published in "Test Artist/Test Album (2021)" as:
      | file                 |
      | 01 - Track One.mp3   |
      | 02 - Track Two.mp3   |
      | 03 - Track Three.mp3 |
    And every published track is still "mp3"
    And every published track carries all R-MUSIC-2 tags

  Scenario: A low-confidence match stops at Review
    Given a music workspace with mocked AcoustID, MusicBrainz and Cover Art Archive
    And a generated FLAC album of 3 tracks
    And AcoustID answers with a score of 0.42
    When the pipeline runs until idle
    Then every item is awaiting approval
    And nothing is published
    When I approve every planned item
    And the pipeline runs until idle
    Then 3 tracks are published
