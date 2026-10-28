"""run_tool against real processes (the unit-test conftest mocks subprocesses)."""

import pytest

from app.core.tools import run_tool

pytestmark = pytest.mark.asyncio


async def test_missing_binary_is_a_failed_result_not_an_exception():
    rc, out, err = await run_tool(["definitely-not-a-real-binary-xyz", "--x"], 5)
    assert rc == 127 and out == "" and "definitely-not-a-real-binary-xyz" in err


async def test_timeout_sends_sigterm_first_so_tools_can_clean_up(tmp_path):
    flag = tmp_path / "terminated"
    script = f"trap 'touch {flag}; exit 0' TERM; sleep 30 & wait"
    rc, _, err = await run_tool(["sh", "-c", script], 0.5)
    assert rc == -1 and "timed out" in err
    assert flag.exists()
