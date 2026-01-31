import asyncio
import logging
from pathlib import Path
from typing import Optional
from pydantic import BaseModel


class QualityMetrics(BaseModel):
    vmaf: Optional[float] = None
    psnr: Optional[float] = None


async def run_vmaf_ffmpeg(src: str, dst: str) -> QualityMetrics:
    """Run ffmpeg VMAF/PSNR quality check on a 10s sample."""
    # Use a 10s sample from the start
    vmaf_log = Path(dst).with_suffix(".vmaf.json")
    cmd = [
        "ffmpeg",
        "-i",
        src,
        "-i",
        dst,
        "-filter_complex",
        "[0:v]setpts=PTS-STARTPTS[ref];[1:v]setpts=PTS-STARTPTS[dist];[ref][dist]libvmaf=log_path=%s:psnr=1"
        % vmaf_log,
        "-t",
        "10",
        "-f",
        "null",
        "-",
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg vmaf failed: {err.decode()}")
        # Parse VMAF/PSNR from log
        import json

        with open(vmaf_log, "r") as f:
            data = json.load(f)
        vmaf = data["pooled_metrics"]["vmaf"]["mean"]
        psnr = data["pooled_metrics"]["psnr"]["mean"]
        return QualityMetrics(vmaf=vmaf, psnr=psnr)
    except Exception as e:
        logging.error(f"VMAF/PSNR check failed: {e}")
        return QualityMetrics()
