import asyncio
import os
import sys

import pytest

from app.core.tools import run_tool

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_cancelled_run_tool_kills_the_child(tmp_path):
    pidfile = tmp_path / "pid"
    code = f"import os,time; open({str(pidfile)!r},'w').write(str(os.getpid())); time.sleep(60)"
    task = asyncio.create_task(run_tool([sys.executable, "-c", code]))
    for _ in range(200):
        if task.done() or (pidfile.exists() and pidfile.read_text().strip()):
            break
        await asyncio.sleep(0.05)
    assert not task.done(), task.result()
    pid = int(pidfile.read_text())
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
