# Provider contract fixtures (G17)

`fixtures/` holds small provider responses parsed by the real code in `test_fixtures.py`.

| Fixture | Source |
|---|---|
| `musicbrainz_release.json` | recorded from musicbrainz.org (`python -m tests.contracts.refresh`) |
| `tmdb_*`, `tvdb_*`, `acoustid_*` | written to the documented response shape (API keys needed to record); re-record with `refresh.py` and commit the diff when keys are at hand |

Plex, Jellyfin, Audiobookshelf and Music Assistant answer our requests, not the other way round, so they are proved
by the nightly workflow (`make contract-servers`): Jellyfin and Audiobookshelf run for real; Plex is skipped (needs
a claimed account); Music Assistant is **experimental** (the `music/sync` call is unverified, see DEPLOYMENT.md).
