# Deployment

Docker Compose is the supported way to run Media Refinery.

## Quick start

```bash
git clone https://github.com/paruff/Media-Refinery.git
cd Media-Refinery
cp .env.example .env        # set MR_API_TOKEN, PUID/PGID and the folder paths
docker compose up -d
```

The UI and API are on <http://localhost:8000> (web UI at `/ui`). Drop files into `INPUT_DIR`; plans wait in
the Review view until approved (unless the type is in `AUTO_APPROVE_TYPES`).

## Volumes

| Mount | Purpose |
|---|---|
| `/input` | Watched drop folder. |
| `/output` | Libraries: `Movies/ TV/ Music/ Audiobooks/ Books/`. |
| `/work` | Scratch space; keep on the same filesystem as `/output` for atomic renames. |
| `/archive` | Originals after verification. |
| `/quarantine` | Items that failed verification, grouped by reason. |
| `/data` | SQLite database. |

The container runs as `PUID:PGID` (default 1000:1000); make the host folders writable by that user.

## Configuration

`.env` is read by Docker Compose only for `${…}` substitution in `docker-compose.yml`:
`MR_API_TOKEN` (required), `PUID`, `PGID`, `TZ` and the six folder variables. It is **not**
passed into the container. To set any other option, add it under `environment:` in
`docker-compose.yml` (or an `env_file:` limited to those keys):

- `TMDB_API_KEY`, `TVDB_API_KEY`, `ACOUSTID_API_KEY`, `ACOUSTID_MIN_SCORE`
- `ENABLED_TYPES` (JSON list, default `["music", "ebook"]`): only these types are processed. Music is the supported lead pipeline and ebooks are supported (beta; they need the Calibre CLI and epubcheck, both in the image, or a Calibre library you point `CALIBRE_LIBRARY` at; use Calibre 8 or newer, as 7.6 converts some AZW3 files to EPUBs that fail epubcheck and are quarantined); `movie`, `series` and `audiobook` are **experimental and off by default**. Files of a disabled type stay untouched in the input folder.
- `AUTO_APPROVE_TYPES` (`music`, `movie`, `series`, `audiobook`, `ebook`), `DRY_RUN`
- Server rescan (Jellyfin/Audiobookshelf proved nightly, Plex untested in CI, **Music Assistant experimental**: the `music/sync` call is unverified against a real instance), each optional: `PLEX_URL`/`PLEX_TOKEN`/`PLEX_SECTIONS`, `JELLYFIN_URL`/`JELLYFIN_API_KEY`, `ABS_URL`/`ABS_TOKEN`/`ABS_LIBRARY_ID`, `MUSIC_ASSISTANT_URL`/`MUSIC_ASSISTANT_TOKEN`, and `NOTIFY_PATH_MAP` (JSON, container path to the path the server sees, e.g. `{"/output/Music":"/data/music"}`; Plex and Jellyfin scan by their own paths)

All names are defined in `app/core/config.py`. The Celery/Redis distributed mode is not supported.

## Operations

```bash
docker compose logs -f media-refinery
curl localhost:8000/ready            # database, ffmpeg, library roots
git pull && docker compose up -d --build
```

`scripts/smoke.sh` runs one generated file per media type through the image; `make ci`
includes `compose-check`.

## Troubleshooting

- **`/ready` fails:** a library root is not writable by `PUID:PGID`.
- **Compose refuses to start:** `MR_API_TOKEN` is unset.
- **Nothing happens to a file:** it is still inside the stability window, or a plan is waiting for approval in the UI.
- **Music held for review:** AcoustID score below `ACOUSTID_MIN_SCORE`, or `ACOUSTID_API_KEY` not set in the container environment.

## Hardware and platforms

The published image is multi-arch (`linux/amd64`, `linux/arm64`): Apple Silicon (M-series Mac mini),
Raspberry Pi 5 and x86 servers all pull the native build. Video encoding picks the first working
encoder from VideoToolbox, NVENC, VAAPI, else software `libx264`/`libx265`.

| Host | What runs | Hardware encode |
|---|---|---|
| Linux + Intel/AMD GPU | container | VAAPI: add `docker-compose.hwaccel.yml` |
| Linux + NVIDIA | container | NVENC: NVIDIA Container Toolkit + `gpus: all` |
| macOS (Apple Silicon or Intel) | container, in Docker's Linux VM | none: software on ARM64 NEON / x86; give Docker Desktop/OrbStack enough CPUs |
| macOS, VideoToolbox wanted | run natively (`pip install .` + Homebrew `ffmpeg`), not in Docker | VideoToolbox |

Encodes run two at a time; give Docker enough CPU cores for that.
