import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.quality_guard_service import run_vmaf_ffmpeg


def _proc(returncode=0, err=b""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(b"", err))
    return proc


@pytest.mark.asyncio
async def test_vmaf_parses_log(tmp_path):
    dst = tmp_path / "out.mkv"
    (tmp_path / "out.vmaf.json").write_text(
        json.dumps({"pooled_metrics": {"vmaf": {"mean": 93.5}, "psnr": {"mean": 41.0}}})
    )
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=_proc())):
        metrics = await run_vmaf_ffmpeg("src.mkv", str(dst))
    assert (metrics.vmaf, metrics.psnr) == (93.5, 41.0)


@pytest.mark.asyncio
async def test_vmaf_failure_returns_empty_metrics(tmp_path):
    with patch(
        "asyncio.create_subprocess_exec", AsyncMock(return_value=_proc(1, b"boom"))
    ):
        metrics = await run_vmaf_ffmpeg("src.mkv", str(tmp_path / "out.mkv"))
    assert metrics.vmaf is None
    assert metrics.psnr is None
    assert metrics.error and "boom" in metrics.error


@pytest.mark.asyncio
async def test_missing_libvmaf_is_unavailable_not_an_error(tmp_path):
    err = b"No such filter: 'libvmaf'"
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=_proc(1, err))):
        metrics = await run_vmaf_ffmpeg("src.mkv", str(tmp_path / "out.mkv"))
    assert metrics.error is None and metrics.vmaf is None
