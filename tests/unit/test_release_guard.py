"""G12 review: a release tag must be a version tag on main matching pyproject.toml."""

import subprocess
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[2] / "scripts" / "release_guard.sh"
pytestmark = pytest.mark.unit


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "1.2.3"\n'
    )
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "init")
    git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")  # what CI fetches
    return tmp_path


def guard(repo, tag, tmp_path):
    out = tmp_path / "out.txt"
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "GITHUB_OUTPUT": str(out)}
    result = subprocess.run(
        [str(GUARD), tag], cwd=repo, env=env, capture_output=True, text=True
    )
    return result, out.read_text() if out.exists() else ""


def test_matching_tag_on_main_releases_and_moves_latest(repo, tmp_path):
    result, out = guard(repo, "v1.2.3", tmp_path)
    assert result.returncode == 0 and "latest=true" in out


def test_tag_must_match_pyproject_version(repo, tmp_path):
    result, _ = guard(repo, "v1.2.4", tmp_path)
    assert result.returncode == 1 and "pyproject.toml version 1.2.3" in result.stderr


def test_non_version_tag_is_refused(repo, tmp_path):
    assert guard(repo, "release-1", tmp_path)[0].returncode == 1


def test_commit_not_on_main_is_refused(repo, tmp_path):
    (repo / "x.txt").write_text("x")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "unmerged work")  # HEAD is ahead of origin/main
    result, _ = guard(repo, "v1.2.3", tmp_path)
    assert result.returncode == 1 and "not on main" in result.stderr


def test_prerelease_does_not_move_latest(repo, tmp_path):
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "1.3.0-rc1"\n'
    )
    git(repo, "commit", "-qam", "rc")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    result, out = guard(repo, "v1.3.0-rc1", tmp_path)
    assert result.returncode == 0 and "latest=false" in out
