import os
import shutil
import asyncio
import traceback
from pathlib import Path
from datetime import datetime
from app.models.media import NormalizationPlan, MediaItem
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from app.core.ffmpeg_profiles import get_ffmpeg_args


class ExecutionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_plan(self, plan: NormalizationPlan):
        log = []
        start_time = datetime.utcnow().isoformat()
        plan_id = plan.id
        staging_dir = Path(f"/staging/{plan_id}")
        try:
            # Stage 1: Ingest to Staging
            os.makedirs(staging_dir, exist_ok=True)
            src = Path(plan.media_item.source_path)
            staged_file = staging_dir / src.name
            shutil.move(str(src), str(staged_file))
            log.append(f"[{start_time}] Moved to staging: {staged_file}")

            # Stage 2: Transformation (Transcoding)
            final_file = staged_file
            if plan.needs_transcode:
                # Determine profile and resolution (simple heuristic)
                profile = "Samsung_Series_65"
                # Use ffprobe to detect resolution
                probe_cmd = [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height",
                    "-of",
                    "csv=p=0",
                    str(staged_file),
                ]
                proc_probe = await asyncio.create_subprocess_exec(
                    *probe_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                out_probe, _ = await proc_probe.communicate()
                width, height = 0, 0
                try:
                    width, height = map(int, out_probe.decode().strip().split(","))
                except Exception:
                    pass
                resolution = "4k" if width >= 3840 or height >= 2160 else "1080p"
                surround = getattr(plan, "surround", False)
                ffmpeg_args = get_ffmpeg_args(profile, resolution, surround)
                # Always use -map 0 to preserve all streams
                transcode_out = staging_dir / (src.stem + ".normalized" + src.suffix)
                ffmpeg_cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(staged_file),
                    *ffmpeg_args,
                    str(transcode_out),
                ]
                proc = await asyncio.create_subprocess_exec(
                    *ffmpeg_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                # Optional: parse progress from stderr
                out, err = await proc.communicate()
                log.append((out + err).decode())
                if proc.returncode != 0:
                    raise RuntimeError(f"FFMPEG failed: {(out + err).decode()}")
                # Verify output with ffprobe
                verify_cmd = [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=codec_name",
                    "-of",
                    "csv=p=0",
                    str(transcode_out),
                ]
                proc_verify = await asyncio.create_subprocess_exec(
                    *verify_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                out_verify, _ = await proc_verify.communicate()
                codec = out_verify.decode().strip()
                if resolution == "4k" and codec != "hevc":
                    raise RuntimeError(f"Transcoded video is not HEVC: {codec}")
                if resolution == "1080p" and codec != "h264":
                    raise RuntimeError(f"Transcoded video is not H264: {codec}")
                final_file = transcode_out
            if getattr(plan, "needs_tagging", False):
                # Mutagen tagging logic placeholder
                log.append("Tagging with Mutagen (not implemented)")

            # Stage 3: Atomic Commit
            target_path = Path(plan.target_path)
            os.makedirs(target_path.parent, exist_ok=True)
            dest = target_path
            suffix = 1
            while dest.exists():
                dest = target_path.with_name(
                    f"{target_path.stem}-duplicate-{suffix}{target_path.suffix}"
                )
                suffix += 1
            shutil.move(str(final_file), str(dest))
            if not dest.exists() or dest.stat().st_size == 0:
                raise RuntimeError("Output file missing or empty after move")
            log.append(f"Moved to output: {dest}")

            # Update DB states
            await self.db.execute(
                update(MediaItem)
                .where(MediaItem.id == plan.media_item_id)
                .values(state="executed")
            )
            await self.db.execute(
                update(NormalizationPlan)
                .where(NormalizationPlan.id == plan.id)
                .values(execution_log="\n".join(log), plan_status="completed")
            )
            await self.db.commit()
        except Exception as e:
            tb = traceback.format_exc()
            log.append(f"ERROR: {e}\n{tb}")
            await self.db.execute(
                update(MediaItem)
                .where(MediaItem.id == plan.media_item_id)
                .values(state="error")
            )
            await self.db.execute(
                update(NormalizationPlan)
                .where(NormalizationPlan.id == plan.id)
                .values(execution_log="\n".join(log), plan_status="failed")
            )
            await self.db.commit()
            # Cleanup staging
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            raise
        # Cleanup staging
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
