"""Re-record provider fixtures from the real services: python -m tests.contracts.refresh.

Needs TMDB_API_KEY, TVDB_API_KEY, ACOUSTID_API_KEY in the environment; MusicBrainz needs none.
Review the diff before committing: recordings must stay small and hold no secrets.
"""

import os
from pathlib import Path

import httpx

OUT = Path(__file__).parent / "fixtures"
UA = {"User-Agent": "Media-Refinery/1.0 (https://github.com/paruff/Media-Refinery)"}
RELEASE = (
    "b84ee12a-09ef-421b-82de-0441a926375b"  # Pink Floyd, The Dark Side of the Moon
)


def save(name: str, resp: httpx.Response) -> None:
    resp.raise_for_status()
    (OUT / name).write_text(resp.text.strip() + "\n")
    print("recorded", name)


def main() -> None:
    with httpx.Client(timeout=30, headers=UA) as c:
        mb = "https://musicbrainz.org/ws/2"
        save(
            "musicbrainz_release.json",
            c.get(
                f"{mb}/release/{RELEASE}",
                params={"inc": "recordings+artist-credits+genres", "fmt": "json"},
            ),
        )
        if key := os.environ.get("TMDB_API_KEY"):
            save(
                "tmdb_search_movie.json",
                c.get(
                    "https://api.themoviedb.org/3/search/movie",
                    params={"api_key": key, "query": "Dune", "year": 2021},
                ),
            )
        if key := os.environ.get("TVDB_API_KEY"):
            tv = "https://api4.thetvdb.com/v4"
            login = c.post(f"{tv}/login", json={"apikey": key})
            login.raise_for_status()
            auth = {"Authorization": f"Bearer {login.json()['data']['token']}"}
            save(
                "tvdb_search.json",
                c.get(
                    f"{tv}/search",
                    params={"query": "Game of Thrones", "type": "series"},
                    headers=auth,
                ),
            )
            save(
                "tvdb_episodes.json",
                c.get(
                    f"{tv}/series/121361/episodes/default",
                    params={"season": 1, "episodeNumber": 1},
                    headers=auth,
                ),
            )
        if key := os.environ.get("ACOUSTID_API_KEY"):
            print("AcoustID needs a real fingerprint: record by hand, see README.md")


if __name__ == "__main__":
    main()
