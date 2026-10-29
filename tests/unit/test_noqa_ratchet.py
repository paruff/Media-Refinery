"""#170: the `# noqa` count may only shrink. Lower BASELINE when you remove one; never raise it."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASELINE = 111
pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        shutil.which("git") is None, reason="git not installed (the CI image has none)"
    ),
]


def test_noqa_count_does_not_grow() -> None:
    files = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    count = sum(
        line.count("# noqa")
        for f in files
        if (ROOT / f).is_file() and f != "tests/unit/test_noqa_ratchet.py"
        for line in (ROOT / f).read_text(encoding="utf-8").splitlines()
    )
    assert count <= BASELINE, (
        f"{count} `# noqa` markers > baseline {BASELINE}; fix the lint instead"
    )
