# Product Vision: Media Normalizer

## Product
**Media Normalizer**

## Goal
Transform a messy media library (movies, series, music) into a clean, canonical staging library that:
- Is **Plex‑perfect** for movies and series
- Is **Samsung Series 65–safe** for playback (codecs, containers, subtitles)
- Is **Music Assistant–perfect** for music (encoding, tags, structure)
- Runs as a **web app** with a staging area and fully automated enrichment + transcoding
- Uses **SQLite** for state and **GitHub Actions** for CI

## High‑Level Architecture

### Frontend (web)
- Simple web UI (can be added later; backend first)
- Views:
  - Library scan status
  - Issues list
  - Normalization plan
  - Execution status
  - Validation results

### Backend (Python)
- FastAPI service
- SQLite via SQLAlchemy
- Behave for BDD tests (backed by feature files)
- ffmpeg for transcoding
- External APIs: TMDB, TVDB, MusicBrainz

#### Core Layers
- **Scanner** – walks source library, classifies files, extracts raw metadata
- **Enricher** – calls external APIs to fill gaps (movies, series, music)
- **Planner** – builds a NormalizationPlan for each file into the staging area
- **Executor** – applies renames, moves, metadata writes, transcoding
- **Validator** – checks staging library against “ideal” rules
- **API** – exposes operations to the web UI

## Project Scaffold (Python backend)

```
media-normalizer/
  backend/
    app/
      __init__.py
      main.py              # FastAPI entrypoint
      config.py
      db.py                # SQLite setup
      models/
        __init__.py
        media_file.py
        normalization_plan.py
      services/
        scanner.py
        metadata_enricher.py
        planner.py
        executor.py
        validator.py
        ffmpeg_profiles.py
      api/
        __init__.py
        routes_scan.py
        routes_plan.py
        routes_execute.py
        routes_validate.py
    tests/
      features/
        01_preclean_detection.feature
        02_normalization.feature
        03_movies_plex_samsung65.feature
        04_tv_series_plex.feature
        05_music_musicassistant.feature
        06_validation_regression.feature
      steps/
        test_steps_scan.py
        test_steps_normalization.py
        test_steps_movies.py
        test_steps_series.py
        test_steps_music.py
        test_steps_validation.py
      conftest.py
  .github/
    workflows/
      ci.yml
  pyproject.toml
  README.md
```

## Core Data Models (Backend)

### MediaFile
- id
- source_path
- type (movie, series, music, unknown)
- title
- year
- season
- episode
- artist
- album
- track_number
- disc_number
- video_codec
- audio_codec
- container
- subtitles (JSON)
- issues (JSON)

### NormalizationPlan
- id
- media_file_id
- target_path
- target_container
- transcode (bool)
- transcode_profile (e.g. samsung65)
- fix_subtitles (bool)
- fix_metadata (bool)
- status (planned, running, done, failed)
- log (text/JSON)
