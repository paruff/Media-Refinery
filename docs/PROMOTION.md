# Promoting a parked media type

Every type is on by default (`ENABLED_TYPES`); this is how each was promoted. Promote **one type at a time**, by passing every gate below, then change the default and README.

## Checklist (the lead-type bar)

- [x] **Corpus suite**: the type has a generated corpus in `tests/corpus/` (messy inputs, junk, duplicates)
      and the suite is green in `make docker-test`.
- [x] **Idempotence**: re-running ingest over the output tree is a no-op; a moved file is not a new item.
- [x] **Crash invariants**: `tests/corpus/test_crash_invariants.py` covers the type (no loss, no partial
      output, source untouched until verified).
- [x] **Provider contracts**: every external provider the type uses has a recorded fixture and parse test in
      `tests/contracts/`; server notifications for it are verified or flagged experimental.
- [x] **Review backlog**: every Important item for the type in its `review-finding` issue is closed; minors
      are closed or deferred in writing.
- [x] **Docs**: README/DEPLOYMENT list the type as supported and its required tools (e.g. calibre).

## Status

| Type | Status | Why |
|------|--------|-----|
| music | promoted (lead) | meets all gates (G16) |
| audiobooks | promoted (beta) | meets all gates (P2; the `audio_args` HE-AAC, zero-duration and series-atom minors are done too): `tests/corpus/test_audiobook_corpus.py`, audiobook crash sweep (merge/concat step), late-part and gap review, #100 Important items and minors done (series atoms are asserted by round trip; the real server check is the nightly job); Audiobookshelf notify call proved against the real server by the nightly `make contract-servers` |
| ebooks | promoted (beta) | meets all gates (P1): `tests/corpus/test_ebook_corpus.py`, ebook crash sweep, `fetch_ebook_metadata.txt` fixture, #101 minors done; needs calibre + epubcheck (in the image) |
| movies | promoted (beta) | meets all gates (P3): `tests/corpus/test_movie_corpus.py`, movie crash sweep, `tmdb_search_movie.json` fixture, #96/#97 and the #108 video items done |
| TV | promoted (beta) | meets all gates (P4): `tests/corpus/test_tv_corpus.py`, series crash sweep, `tvdb_*.json` fixtures, token-refresh/401/429/key-not-in-logs tests, #98 done |

All parked types are promoted.
