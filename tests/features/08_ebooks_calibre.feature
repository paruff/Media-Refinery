Feature: Ebooks into Calibre
  R-EBOOK-1..4: EPUB/MOBI become EPUB 3 (epubcheck-clean), are added with
  `calibredb add` into the Calibre library with title, author and cover, and
  DRM-protected files are quarantined as `drm` without being processed.

  Scenario: An EPUB and a MOBI land in the Calibre library with metadata
    Given an ebook workspace
    And a generated EPUB "Test Epub" by "Epub Author"
    And a generated MOBI "Test Mobi" by "Mobi Author"
    When the pipeline runs until idle
    Then the Calibre library lists "Test Epub" by "Epub Author" with a cover
    And the Calibre library lists "Test Mobi" by "Mobi Author" with a cover
    And the library holds EPUB files only
    And both EPUBs passed epubcheck
    And the originals are archived

  Scenario: A DRM-protected book is quarantined and never processed
    Given an ebook workspace
    And a generated DRM EPUB "Locked Book" by "Locked Author"
    When the pipeline runs until idle
    Then the DRM file is in "quarantine/drm"
    And the Calibre library is empty
