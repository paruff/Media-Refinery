# Beta trial: real music library (B7, #150)

Run with `scripts/beta_trial.sh <library-copy>` (Docker only; the library is a copy, outputs go to a scratch dir).
Settings: `ENABLED_TYPES=["music"]`, no `ACOUSTID_API_KEY` (embedded tags only), image built from this branch's parent.

## Input

One real artist from the NAS music share: ABBA, 8 albums, 82 FLAC tracks fully tagged (MusicBrainz/Classical Extras tags,
ReplayGain, 1975-2021) plus one `cover.jpg` per album.

## Run 1 (before the fix)

| Step | Result |
| --- | --- |
| `doctor` | tools ok; warns only `ACOUSTID_API_KEY` unset |
| `plan` | 90 items: 82 copy/tag, 7 not planned (cover.jpg), 1 transcode-class |
| `approve` / `run` | 129 s for 82 tracks (~1.6 s per track, ~1 GB) |
| `verify` | every output `ok: true`, no problems |
| Quarantined | 0 files (the 7 conflicts were left in place, never moved) |
| Data loss | none: all 82 sources archived, outputs verified |

### Bugs found

1. **Wrong destination (fixed in this PR).** All 82 tracks were published to
   `Music/Unknown Artist/Unknown Album/`, collapsing 8 albums into one folder, although every file carries
   ARTIST/ALBUM/ALBUMARTIST. Cause: classification stored the embedded artist/album in `enrichment_data`, but the
   music step read only the empty `item.artist`/`item.album` columns. Fix in `app/pipeline/types/music.py` and
   `app/services/classification.py`; regression test `test_unidentified_music_is_filed_by_its_embedded_artist_and_album`.
   Not data loss (files intact and verified), but an unusable library layout.
2. **Sidecar `cover.jpg` planned as `cover.flac`** (7 plan_conflicts): filed as #173.

## Run 2 (after the fix)

Re-run on a tagged two-track fixture (the real-library copy was lost to a full disk, see below): published to
`Music/ABBA/ABBA (1975)/01 - T1.flac`, validated, 0 quarantined. **The full real-library re-run is still outstanding**
and should be done on the rc image before the final `v0.3.0`.

## Gaps and follow-ups

- Run 2 was not on the real library: the scratch disk filled during the re-run. Repeat with `scripts/beta_trial.sh`.
- Only one artist; no untagged, multi-disc, compilation or lossy-heavy material was exercised.
- Throughput is single-worker, run time includes ReplayGain measurement.
- No open data-loss bugs found.
