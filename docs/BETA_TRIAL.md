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

## Run 2 (after the fix, fixture)

Tagged two-track fixture published to `Music/ABBA/ABBA (1975)/01 - T1.flac`, validated, 0 quarantined.

## Run 3 (rc image plus #173 fix, real library: Talking Heads, 8 albums)

Subset of a 694-track / 24 GB copy of a messy real collection (16-bit and 24-bit/96 kHz editions, compilations,
live albums, nfo/accurip/log/cue/jpg sidecars): 93 files, 3.0 GB, hard-linked so the full copy stayed untouched.

| Step | Result |
| --- | --- |
| `doctor` | ok (ACOUSTID key unset, embedded tags only) |
| `plan` | 85 items: 66 copy/tag, 13 error, 6 quarantined; sidecar images no longer planned (#173 fixed) |
| `approve` / `run` | 123 s |
| Published and verified | 42 tracks, 0 failed `verify` |
| Quarantined (`decode_failed`) | 21 derived outputs; sources stay in input/archive |
| Source accounting | 93 inputs = 51 left in input + 42 archived; nothing deleted |

Throughput: the unsubset full copy (694 tracks, 24 GB) spent about 25 minutes in `plan` alone (fingerprint plus
ReplayGain), so expect roughly 30-45 minutes end to end for a library that size on one worker. The full run was
stopped before publishing because it would have needed about 24 GB of free disk; use a subset or a roomy volume.

### Findings

1. **Damaged source files, correctly caught.** 6 of 8, 6 of 14, 9 of 36 and 2 of 8 FLACs in four checked albums fail
   `flac -t` in the unmodified copy (e.g. a 41,944,499-byte file, close to a 40 MiB cut-off, looks truncated), `fpcalc`
   fails on them (50 logged failures) and the pipeline quarantines them rather than publishing. Verify these against the
   NAS originals: they may be truncated by the copy, not bit rot.
2. **UNIQUE constraint on `normalization_plans.target_path`** for remaster-variant titles surfaces as a raw SQL error
   (item in `error`): filed as a review-finding issue.
3. **Compilation tracks skipped by fingerprint de-duplication**, so compilations publish incomplete: filed as a
   review-finding issue.
4. Hi-res (24-bit/96 kHz) and 16-bit editions of the same album are both planned; handling of 24-bit is the R-MUSIC-1
   follow-up in #172.

## Gaps

- One artist only; no untagged, multi-disc or lossy-heavy material, and no AcoustID identification.
- Single worker; throughput numbers are for CPU-bound plan/verify on a laptop VM.
- No open data-loss bugs found: every source file is accounted for after the run.
