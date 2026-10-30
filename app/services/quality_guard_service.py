import asyncio
import logging
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger("QualityGuard")


class QualityMetrics(BaseModel):
    vmaf: float | None = None
    psnr: float | None = None
    error: str | None = (
        None  # set when VMAF could not be measured for a reason other than no libvmaf
    )


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
        f"[0:v]setpts=PTS-STARTPTS[ref];[1:v]setpts=PTS-STARTPTS[dist];[ref][dist]libvmaf=log_path={vmaf_log}:psnr=1",
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
        _, err = await proc.communicate()
        if proc.returncode != 0:
            text = err.decode(errors="replace")
            if "libvmaf" in text and ("No such filter" in text or "not found" in text):
                logger.warning("ffmpeg has no libvmaf; quality check unavailable")
                return QualityMetrics()
            raise RuntimeError(f"ffmpeg vmaf failed: {text[-300:]}")
        # Parse VMAF/PSNR from log
        import json

        data = json.loads(await asyncio.to_thread(vmaf_log.read_text))
        vmaf = data["pooled_metrics"]["vmaf"]["mean"]
        psnr = data["pooled_metrics"]["psnr"]["mean"]
        return QualityMetrics(vmaf=vmaf, psnr=psnr)
    except Exception as exc:
        logger.exception("VMAF/PSNR check failed")
        return QualityMetrics(error=str(exc)[:300])
