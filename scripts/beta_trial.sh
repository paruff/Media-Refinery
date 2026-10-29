#!/bin/sh
# B7 beta gate: run doctor, plan, approve, run and verify on a COPY of a real music library
# inside the image and print the numbers the trial report (docs/BETA_TRIAL.md) needs.
# Host needs only Docker. The library COPY is mounted writable (sources are archived from it); outputs go to a scratch dir.
# Usage: scripts/beta_trial.sh /path/to/library-copy [image]   (default media-refinery:ci)
set -eu
LIB=${1:?usage: beta_trial.sh <library-copy> [image]}
IMAGE=${2:-media-refinery:ci}
[ -d "$LIB" ] || { echo "not a directory: $LIB" >&2; exit 2; }
LIB=$(cd "$LIB" && pwd)
ROOT=$(mktemp -d "$HOME/.mrtrial.XXXXXX")  # under $HOME so Docker Desktop/colima can share it
for d in output work archive quarantine data; do mkdir -p "$ROOT/$d"; done
chmod 777 "$ROOT"/*
run() { # refinery sub-command and args
  docker run --rm --user root -e ENABLED_TYPES='["music"]' -e DATABASE_URL=sqlite+aiosqlite:////data/trial.sqlite \
    -v "$LIB":/input -v "$ROOT/output":/output -v "$ROOT/work":/work -v "$ROOT/archive":/archive \
    -v "$ROOT/quarantine":/quarantine -v "$ROOT/data":/data "$IMAGE" refinery "$@"
}
now() { date +%s; }
echo "## input"; find "$LIB" -type f | sed 's/.*\.//' | sort | uniq -c | sort -rn
echo "## doctor"; run doctor
echo "## plan"; run plan /input
echo "## approve"; run approve /input
t0=$(now); echo "## run"; run run /input; t1=$(now)
echo "## verify"; run verify /output
echo "## summary"
echo "run seconds: $((t1 - t0))"
echo "input files:  $(find "$LIB" -type f | wc -l)  bytes: $(du -sk "$LIB" | cut -f1) KiB"
echo "output files: $(find "$ROOT/output" -type f | wc -l)"
echo "quarantined:  $(find "$ROOT/quarantine" -type f | wc -l)"
find "$ROOT/quarantine" -mindepth 1 -maxdepth 2 -type d | sed "s|$ROOT/||"
echo "scratch (root-owned; inspect, then: docker run --rm --user root -v $ROOT:/r $IMAGE rm -rf /r/*): $ROOT"
