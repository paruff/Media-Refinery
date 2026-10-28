# Provider contract fixtures (G17)

`fixtures/` holds small provider responses parsed by the real code in `test_fixtures.py`.

| Fixture | Source |
|---|---|
| `musicbrainz_release.json` | recorded from musicbrainz.org (`python -m tests.contracts.refresh`) |
| `tmdb_search_movie.json` | recorded from the live API |
| `tvdb_search.json`, `tvdb_episodes.json` | recorded from the live API, trimmed to the fields the parser reads |
| `tvdb_login.json`, `acoustid_lookup.json` | written to the documented shape: login holds a fake token; AcoustID needs a fingerprint of a real track, so it is accepted as documented-shape until one is recorded |

Plex, Jellyfin, Audiobookshelf and Music Assistant answer our requests, not the other way round, so they are proved
by the nightly workflow (`make contract-servers`): Jellyfin and Audiobookshelf run for real; Plex is skipped (needs
a claimed account); Music Assistant is **experimental** (the `music/sync` call is unverified, see DEPLOYMENT.md).
