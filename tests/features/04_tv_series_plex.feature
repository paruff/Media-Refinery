Feature: TV episodes land in the Plex/Jellyfin series layout
  R-VIDEO-5: TV/{Show} ({Year}) {tvdb-id}/Season NN/{Show} - SxxEyy - {Title}.mkv,
  specials in Season 00.

  Scenario: Episode naming and season folder
    Given a video workspace with mocked TMDB and TVDB
    And a generated conformant video "Show Name S01E02.mkv"
    When the video pipeline is approved and run to completion
    Then the episode is published at "TV/Show Name (2020) {tvdb-81189}/Season 01/Show Name - S01E02 - Second Episode.mkv"

  Scenario: Specials go to Season 00
    Given a video workspace with mocked TMDB and TVDB
    And a generated conformant video "Show Name S00E01.mkv"
    When the video pipeline is approved and run to completion
    Then the episode is published at "TV/Show Name (2020) {tvdb-81189}/Season 00/Show Name - S00E01 - Behind The Scenes.mkv"

  Scenario: A file holding two episodes
    Given a video workspace with mocked TMDB and TVDB
    And a generated conformant video "Show Name S01E01E02.mkv"
    When the video pipeline is approved and run to completion
    Then the episode is published at "TV/Show Name (2020) {tvdb-81189}/Season 01/Show Name - S01E01-E02 - First Episode.mkv"

  Scenario: Conformant episodes are remuxed, not re-encoded
    Given a video workspace with mocked TMDB and TVDB
    And a generated conformant video "Show Name S01E02.mkv"
    When the video pipeline is approved and run to completion
    Then the ffmpeg args copy the video and re-encode nothing
    And the output video codec is "h264"
