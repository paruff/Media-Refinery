Feature: Audiobooks for Audiobookshelf
  R-BOOK-1..5: a folder of per-chapter files becomes one AAC M4B with embedded
  chapters, narrator/series tags and a cover, published as
  Audiobooks/{Author}/{Series}/{Sequence} - {Title}/{Title}.m4b.

  Scenario: Three MP3 chapters become one M4B with three chapters
    Given an audiobook workspace
    And a generated book "The Test Book" of 3 MP3 chapters in series "Test Saga" book 2
    When the pipeline runs until idle
    Then the book is published at "Test Author/Test Saga/2 - The Test Book/The Test Book.m4b"
    And it is a single AAC file
    And it has 3 chapters titled "Chapter One", "Chapter Two", "Chapter Three"
    And its duration matches the 3 sources within 0.5 s
    And it carries the R-BOOK-3 tags
    And it embeds a cover
    And the source chapters are archived

  Scenario: Chapters are merged in natural sort order
    Given an audiobook workspace
    And a generated book "Ordered" of 3 MP3 chapters named "2.mp3", "10.mp3", "1.mp3"
    When the pipeline runs until idle
    Then the chapter titles in order are "Chapter One", "Chapter Two", "Chapter Three"

  Scenario: A book without a series has no series folder
    Given an audiobook workspace
    And a generated book "Standalone" of 2 MP3 chapters
    When the pipeline runs until idle
    Then the book is published at "Test Author/Standalone/Standalone.m4b"

  Scenario: Low source bitrate is not inflated
    Given an audiobook workspace
    And a generated book "Quiet" of 2 mono MP3 chapters at 32 kbps
    When the pipeline runs until idle
    Then the published bitrate is at most 40 kbps
