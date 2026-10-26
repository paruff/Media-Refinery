Feature: Movies land in Plex/Jellyfin layout and play on a Samsung Series 65
  R-VIDEO-1/2/4: TMDB-named folders, conformant video kept (remuxed, never
  re-encoded), AAC stereo plus surround copy, subtitles as SRT, VMAF only
  when the video was re-encoded.

  Scenario: A conformant H.264 MKV is remuxed, not re-encoded
    Given a video workspace with mocked TMDB and TVDB
    And a generated conformant video "The Matrix (1999).mkv"
    When the video pipeline is approved and run to completion
    Then the movie is published at "Movies/The Matrix (1999) {tmdb-603}/The Matrix (1999).mkv"
    And the ffmpeg args copy the video and re-encode nothing
    And the output video codec is "h264"
    And no VMAF check was recorded

  Scenario: A legacy AVI is re-encoded to H.264 with a sampled VMAF check
    Given a video workspace with mocked TMDB and TVDB
    And a generated legacy AVI "The Matrix (1999).avi"
    When the video pipeline is approved and run to completion
    Then the movie is published at "Movies/The Matrix (1999) {tmdb-603}/The Matrix (1999).mkv"
    And the output video codec is "h264"
    And a VMAF check was recorded

  Scenario: Surround AC3 is copied and an AAC stereo track is added
    Given a video workspace with mocked TMDB and TVDB
    And a generated conformant video "The Matrix (1999).mkv" with 6-channel "ac3" audio
    When the video pipeline is approved and run to completion
    Then the output audio is:
      | codec | channels |
      | ac3   | 6        |
      | aac   | 2        |

  Scenario: Text subtitles are converted to SRT
    Given a video workspace with mocked TMDB and TVDB
    And a generated conformant video "The Matrix (1999).mkv" with an "ass" subtitle
    When the video pipeline is approved and run to completion
    Then the output subtitle codec is "subrip"

  Scenario: Multi-part movies share one folder
    Given a video workspace with mocked TMDB and TVDB
    And a generated conformant video "The Matrix (1999) part1.mkv"
    And a generated conformant video "The Matrix (1999) part2.mkv"
    When the video pipeline is approved and run to completion
    Then the movie is published at "Movies/The Matrix (1999) {tmdb-603}/The Matrix (1999) - part1.mkv"
    And the movie is published at "Movies/The Matrix (1999) {tmdb-603}/The Matrix (1999) - part2.mkv"

  Scenario: A movie TMDB cannot match keeps its parsed name
    Given a video workspace with mocked TMDB and TVDB
    And a generated conformant video "Obscure Home Video (2001).mkv"
    When the video pipeline is approved and run to completion
    Then the movie is published at "Movies/Obscure Home Video (2001)/Obscure Home Video (2001).mkv"
