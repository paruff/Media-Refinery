
# Media Refinery


[![CI](https://github.com/paruff/Media-Refinery/actions/workflows/ci.yml/badge.svg)](https://github.com/paruff/Media-Refinery/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/paruff/Media-Refinery/branch/main/graph/badge.svg)](https://codecov.io/gh/paruff/Media-Refinery)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](http://mypy-lang.org/)

Media Refinery watches a drop folder and normalizes music, audiobooks, movies, TV and ebooks
to one canonical, verified format per type, publishes them into your libraries and tells
Plex, Jellyfin, Audiobookshelf or Music Assistant to rescan. Originals are never modified.

## Quickstart

```bash
git clone https://github.com/paruff/Media-Refinery.git
cd Media-Refinery
cp .env.example .env     # set MR_API_TOKEN, PUID/PGID, folder paths
docker compose up -d
```

Open <http://localhost:8000/ui>, drop files into the input folder and approve plans in the Review view.

CLI: `docker compose exec media-refinery refinery scan|plan|approve|run|verify|audit [--dry-run] PATH`.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) · [Deployment](docs/DEPLOYMENT.md) · [Development](docs/DEVELOPMENT.md)
- [Contributing](docs/CONTRIBUTING.md) · [Maintainers](docs/MAINTAINERS_GUIDE.md) · [Product vision](docs/PRODUCT_VISION.md)
- [Intent](intent.md) · [Spec](spec.md) · [Plan](plan.md) · [Design](DESIGN.md) · [Security](SECURITY.md)
