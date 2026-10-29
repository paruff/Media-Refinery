# Promoting a parked media type

`music`, `ebook` and `audiobook` are on by default (`ENABLED_TYPES`). Video and TV are experimental and
off. Promote **one type at a time**, by passing every gate below, then change the default and README.

## Checklist (the lead-type bar)

- [ ] **Corpus suite**: the type has a generated corpus in `tests/corpus/` (messy inputs, junk, duplicates)
      and the suite is green in `make docker-test`.
- [ ] **Idempotence**: re-running ingest over the output tree is a no-op; a moved file is not a new item.
- [ ] **Crash invariants**: `tests/corpus/test_crash_invariants.py` covers the type (no loss, no partial
      output, source untouched until verified).
- [ ] **Provider contracts**: every external provider the type uses has a recorded fixture and parse test in
      `tests/contracts/`; server notifications for it are verified or flagged experimental.
- [ ] **Review backlog**: every Important item for the type in its `review-finding` issue is closed; minors
      are closed or deferred in writing.
- [ ] **Docs**: README/DEPLOYMENT list the type as supported and its required tools (e.g. calibre).

## Status

| Type | Status | Why |
|------|--------|-----|
| music | promoted (lead) | meets all gates (G16) |
| audiobooks | promoted (beta) | meets all gates (P2): `tests/corpus/test_audiobook_corpus.py`, audiobook crash sweep (merge/concat step), late-part and gap review, #100 Important items done; minors done except three deferred (see #100): the `audio_args` copy branch and `max(kbps, 16)`, `expected_duration or probe(source)` masking a zero sum, series atoms untested against Audiobookshelf; Audiobookshelf notify call proved against the real server by the nightly `make contract-servers` |
| ebooks | promoted (beta) | meets all gates (P1): `tests/corpus/test_ebook_corpus.py`, ebook crash sweep, `fetch_ebook_metadata.txt` fixture, #101 minors done; needs calibre + epubcheck (in the image) |
| movies / TV | stays experimental | no corpus coverage; TMDB/TVDB contracts not recorded; minors in #97/#98 open |

Next candidate: movies / TV (corpus suite, TMDB/TVDB contracts, minors in #97/#98).
