#!/bin/sh
# Refuse to release a tag that is not a version tag, disagrees with pyproject.toml,
# or points at a commit that is not on main. Writes latest=true|false to $GITHUB_OUTPUT
# (pre-release tags such as v1.0.0-rc1 must not move :latest).
# Usage: scripts/release_guard.sh <tag>   (needs origin/main fetched)
set -eu

tag=${1:?usage: release_guard.sh <tag>}
version=${tag#v}
case $tag in
  v[0-9]*.[0-9]*.[0-9]*) ;;
  *) echo "not a version tag: $tag" >&2; exit 1 ;;
esac
declared=$(sed -n 's/^version = "\(.*\)"$/\1/p' pyproject.toml | head -n 1)
[ "$declared" = "$version" ] || { echo "tag $tag does not match pyproject.toml version $declared" >&2; exit 1; }
git merge-base --is-ancestor HEAD origin/main || { echo "tag $tag is not on main" >&2; exit 1; }
case $version in
  *-*) latest=false ;;
  *) latest=true ;;
esac
echo "latest=$latest" >> "${GITHUB_OUTPUT:-/dev/null}"
