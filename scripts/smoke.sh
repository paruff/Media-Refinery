#!/bin/sh
# G12 compose smoke test: one generated fixture per media type goes through the
# real image via docker compose and must land in its library. Host needs only Docker.
# Usage: scripts/smoke.sh [image]   (default media-refinery:ci)
set -eu

IMAGE=${1:-media-refinery:ci}
ROOT=$(mktemp -d "$HOME/.mrsmoke.XXXXXX")  # under $HOME: colima/Docker Desktop share it with the VM
P=mrsmoke
# container-written files belong to uid 1000, which the host user may not be: delete as root
trap 'docker compose -p $P -f docker-compose.yml -f "$ROOT/override.yml" down >/dev/null 2>&1 || true
  docker run --rm --user root -v "$ROOT":/r "$IMAGE" sh -c "rm -rf /r/*" >/dev/null 2>&1 || true; rm -rf "$ROOT"' EXIT
for d in input output work archive quarantine data; do mkdir -p "$ROOT/$d"; done
chmod -R 777 "$ROOT"

# Fixtures are generated inside the image (ffmpeg, calibre).
docker run --rm --user root -v "$ROOT/input":/input "$IMAGE" sh -c '
set -e
cd /input
V="-f lavfi -i testsrc=d=2:s=320x240:r=24 -f lavfi -i sine=d=2 -c:v libx264 -c:a aac -shortest"
ffmpeg -loglevel error $V "Smoke Movie (2020).mkv"
# different picture: identical video content is rejected as a duplicate (R-PIPE-7)
mkdir tv && ffmpeg -loglevel error -f lavfi -i mandelbrot=s=320x240:r=24 -f lavfi -i sine=f=880:d=2 \
  -t 2 -c:v libx264 -c:a aac "tv/Smoke.Show.S01E01.mkv"
mkdir music && ffmpeg -loglevel error -f lavfi -i sine=d=3 -metadata artist="Smoke Artist" \
  -metadata album="Smoke Album" -metadata title="Smoke Song" -metadata track=1 -metadata date=2020 music/01.flac
mkdir -p "audiobook/Smoke Book" && for n in 1 2; do ffmpeg -loglevel error -f lavfi -i sine=d=2 \
  -metadata artist="Smoke Author" -metadata genre=Audiobook -metadata album="Smoke Book" -metadata title="Chapter $n" \
  -metadata track=$n "audiobook/Smoke Book/$n.mp3"; done
echo "Smoke Book text" > /tmp/b.txt
ebook-convert /tmp/b.txt "Smoke Ebook.epub" --title "Smoke Ebook" --authors "Smoke Writer" >/dev/null
chmod -R a+rwX /input'

cat > "$ROOT/override.yml" <<EOF
services:
  media-refinery:
    image: $IMAGE
    environment:
      # hermetic: a developer's .env keys must not reach the providers
      TMDB_API_KEY: ''
      TVDB_API_KEY: ''
      ACOUSTID_API_KEY: ''
      ENABLED_TYPES: '["movie","series","music","audiobook","ebook"]'
    ports: !override ["18000:8000"]
    volumes: !override
      - $ROOT/input:/input
      - $ROOT/output:/output
      - $ROOT/work:/work
      - $ROOT/archive:/archive
      - $ROOT/quarantine:/quarantine
      - $ROOT/data:/data
EOF
export MR_API_TOKEN=smoke-token
export ABS_TOKEN=smoke-abs  # proves .env/shell values reach the container (#106)
docker compose -p $P -f docker-compose.yml -f "$ROOT/override.yml" up -d --no-build

fail() { # label: show item states and recent logs, then exit
  curl -s -H "Authorization: Bearer $MR_API_TOKEN" http://localhost:18000/api/v1/items || true
  docker compose -p $P exec -T media-refinery python -c "import sqlite3;print(sqlite3.connect('/data/media_refinery.sqlite').execute('select source_path,state,error_log from media_items where state not in (\"validated\",\"published\")').fetchall())" || true
  docker compose -p $P logs --tail 80
  echo "FAIL: $1"
  exit 1
}
wait_for() { # label, command that succeeds when done
  i=0
  until sh -c "$2" >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -gt 90 ]; then fail "$1"; fi
    sleep 2
  done
  echo "ok: $1"
}
wait_for ready "curl -fs http://localhost:18000/ready"
# README quickstart: doctor, then plan (writes nothing), then approve, exactly as in the README
dc() { docker compose -p $P -f docker-compose.yml -f "$ROOT/override.yml" exec -T media-refinery "$@"; }
[ "$(dc printenv ABS_TOKEN)" = smoke-abs ] || fail "env passthrough"
dc refinery doctor || fail "refinery doctor"
dc refinery plan /input || fail "refinery plan"
# (6 items: the two audiobook chapters merge into one plan, leaving 5 to approve)
# approve through the running server (the UI's Approve button); a second process writing the same
# database races the pipeline (plan_conflict), so the CLI approve is for a stopped server only
api() { curl -fs -H "Authorization: Bearer $MR_API_TOKEN" -H "Content-Type: application/json" "$@"; }
planned() { api "http://localhost:18000/api/v1/items?state=planned" | grep -o '"id":"[^"]*"' | cut -d'"' -f4; }
i=0
until [ "$(planned | wc -l)" -ge 5 ]; do
  i=$((i + 1))
  if [ "$i" -gt 90 ]; then fail "5 items planned"; fi
  sleep 2
done
for id in $(planned); do
  api -X POST "http://localhost:18000/api/v1/items/$id/approve" >/dev/null || fail "approve $id"
done
echo "ok: doctor, plan, approve"
published() { # library dir, then one or more extensions
  d=$1; shift
  for ext in "$@"; do find "$ROOT/output/$d" -type f -name "*.$ext" 2>/dev/null; done | grep -q .
}
for lib in "Movies mkv mp4" "TV mkv mp4" "Music flac" "Audiobooks m4b" "Books epub"; do
  set -- $lib
  i=0
  until published "$@"; do
    i=$((i + 1))
    if [ "$i" -gt 90 ]; then fail "$1"; fi
    sleep 2
  done
  echo "ok: $1"
done
curl -fs -H "Authorization: Bearer $MR_API_TOKEN" http://localhost:18000/api/v1/metrics \
  | grep -q media_refinery_stage_duration_seconds_count || fail "metrics"
echo "smoke: all 5 media types processed"
