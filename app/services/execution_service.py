import os
import shutil
import asyncio
import traceback
from pathlib import Path
from datetime import datetime
from app.models.media import NormalizationPlan, MediaItem
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update


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

            # Stage 2: Transformation
            final_file = staged_file
            if plan.needs_transcode:
                transcode_out = staging_dir / (src.stem + ".normalized" + src.suffix)
                proc = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    *plan.ffmpeg_args[1:-1],
                    str(staged_file),
                    str(transcode_out),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                out, _ = await proc.communicate()
                log.append(out.decode())
                if proc.returncode != 0:
                    raise RuntimeError(f"FFMPEG failed: {out.decode()}")
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
