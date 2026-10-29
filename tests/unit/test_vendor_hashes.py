"""#147/#171: vendored files match the SHA-384 recorded in VENDOR.md."""

import base64
import hashlib
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def test_vendored_files_match_recorded_hashes():
    rows = re.findall(
        r"\| `([^`]+)` \|.*`(sha384-[^`]+)` \|", (ROOT / "VENDOR.md").read_text()
    )
    assert len(rows) >= 2
    for rel, recorded in rows:
        digest = hashlib.sha384((ROOT / rel).read_bytes()).digest()
        assert recorded == "sha384-" + base64.b64encode(digest).decode(), rel
