# Intent — Media Refinery

## Why this exists

My media is spread over decades of formats: MP3 rips, AVI/WMV/MPEG video, loose
audiobook MP3s, mixed ebook files. Every media server I use (Plex/Jellyfin, Music
Assistant, Audiobookshelf, Calibre) works best when files arrive in one predictable
shape — the right container, codecs, tags, artwork, and folder/filename layout.

Media Refinery is the single place that turns messy input into that shape, proves it
did so correctly, and hands the result to the servers that serve it to me and my
household.

## Outcome

Drop files into `input/`. Media Refinery:

1. **Identifies** what each file is (music, audiobook, movie, TV episode, ebook).
2. **Enriches** it from authoritative open sources (MusicBrainz/AcoustID, TMDB/TVDB,
   Open Library/Audible-style metadata).
3. **Plans** the conversion and placement, and shows the plan to a human.
4. **Converts** to open, standard, quality-verified containers.
5. **Verifies** the output (decode check, compliance check, quality metric) before the
   original is ever archived.
6. **Publishes** into the library tree each server watches, and triggers a rescan.

| Media      | Canonical output                                   | Served by                 |
|------------|----------------------------------------------------|---------------------------|
| Music      | FLAC, MusicBrainz tags, embedded cover             | Music Assistant           |
| Audiobooks | M4B (AAC), chapters, cover, author/narrator/series | Audiobookshelf            |
| Movies     | MKV, H.264 or HEVC, AAC/AC3, SRT subtitles         | Plex / Jellyfin           |
| TV series  | MKV, same video profile, `Show/Season NN/` layout  | Plex / Jellyfin           |
| Ebooks     | EPUB, Calibre metadata + cover                     | Calibre / Calibre-Web     |

Video profile must direct-play on a Samsung Series 6 (65") TV without server transcoding.

## Principles (non-negotiable)

- **Never lose an original.** Originals are archived, not deleted, and only after the
  output passes verification.
- **Human in the loop.** Nothing is published without an approved plan (auto-approve is
  an explicit, per-rule opt-in).
- **Open formats, open metadata sources.** No proprietary containers or DRM.
- **Idempotent.** Re-running on the same input produces the same output and no duplicates.
- **One codebase.** `paruff/converter` and `paruff/movies2vlib` are absorbed into this
  repo; their repos are archived after parity.

## Shape

A Docker container running a FastAPI daemon (watcher + pipeline + API), a small web UI
for reviewing plans and results, and a CLI for batch runs. SQLite holds state.

## Out of scope

- Acquiring media (that is the *arr stack's job).
- Serving media or managing users (that is the media servers' job).
- DRM removal.
- Cloud storage backends (until a real need appears).

## Success looks like

- My whole library has been through the refinery, and the servers show zero
  "unmatched" or "needs transcode" items attributable to file shape.
- Every published file has a verification record I can inspect.
- A new file dropped in `input/` reaches the server in one approval click.
