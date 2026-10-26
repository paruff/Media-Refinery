import logging
import os
import shutil
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.media import MediaItem


class ValidationReport:
    def __init__(self):
        self.total_files = 0
        self.valid = 0
        self.invalid = 0
        self.issues: list[dict[str, Any]] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_files": self.total_files,
            "valid": self.valid,
            "invalid": self.invalid,
            "issues": self.issues,
        }


class ValidatorService:
    def __init__(self, output_dir: Path, staging_dir: Path, db: AsyncSession):
        self.output_dir = output_dir
        self.staging_dir = staging_dir
        self.db = db
        self.logger = logging.getLogger("ValidatorService")

    async def validate(self) -> ValidationReport:
        report = ValidationReport()
        db_items = await self._get_db_items()
        db_paths = {
            item.normalization_plan.target_path: item
            for item in db_items
            if item.normalization_plan
        }
        found_paths = set()
        # 1. Scan /output recursively
        for root, _, files in os.walk(self.output_dir):
            for fname in files:
                fpath = Path(root) / fname
                report.total_files += 1
                rel_path = str(fpath.relative_to(self.output_dir))
                found_paths.add(rel_path)
                # Path compliance
                if not self._path_compliant(rel_path):
                    report.invalid += 1
                    report.issues.append(
                        {"path": str(fpath), "issue": "Path non-compliant"}
                    )
                    continue
                # Technical compliance
                ffprobe_issue = self._ffprobe_check(fpath)
                if ffprobe_issue:
                    report.invalid += 1
                    report.issues.append({"path": str(fpath), "issue": ffprobe_issue})
                    continue
                # Metadata check (music/video)
                meta_issue = self._metadata_check(fpath)
                if meta_issue:
                    report.invalid += 1
                    report.issues.append({"path": str(fpath), "issue": meta_issue})
                    continue
                report.valid += 1
        # 2. Orphan detection
        for db_path, item in db_paths.items():
            if db_path not in found_paths and item.state == "executed":
                report.issues.append(
                    {"path": db_path, "issue": "DB record executed but file missing"}
                )
        for rel_path in found_paths:
            if rel_path not in db_paths:
                report.issues.append({"path": rel_path, "issue": "File not in DB"})
        # 3. Cleanup /staging
        self._cleanup_staging()
        # 4. Prune old error logs
        await self._prune_old_errors()
        # 5. Finalize states
        await self._finalize_states(db_items, found_paths)
        return report

    async def _get_db_items(self) -> Sequence[MediaItem]:
        result = await self.db.execute(select(MediaItem))
        return list(result.scalars().all())

    def _path_compliant(self, rel_path: str) -> bool:
        # Example: music/Artist/Year - Album/01 - Title.flac
        #          movies/Movie (Year)/Movie.mkv
        #          tv/Show/Season 01/Episode.mkv
        # This is a placeholder; real logic should match your canonical rules
        parts = rel_path.split(os.sep)
        if parts[0] == "music" and len(parts) >= 4:
            return True
        if parts[0] == "movies" and len(parts) >= 2:
            return True
        return parts[0] == "tv" and len(parts) >= 4

    def _ffprobe_check(self, fpath: Path) -> str:
        # Check for forbidden codecs (e.g., DTS)
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(fpath),
        ]
        try:
            out = subprocess.check_output(cmd, text=True).strip()
            if "dts" in out.lower():
                return "Unsupported Audio: DTS"
        except Exception as e:
            return f"ffprobe error: {e}"
        # Optional: integrity check
        cmd2 = ["ffmpeg", "-v", "error", "-i", str(fpath), "-f", "null", "-"]
        try:
            subprocess.run(cmd2, check=True, capture_output=True)
        except Exception as e:
            return f"ffmpeg integrity error: {e}"
        return ""

    def _metadata_check(self, fpath: Path) -> str:
        # Placeholder: check for required tags using mutagen
        try:
            from mutagen import File

            audio = File(fpath)
            if audio is None:
                return "Unrecognized file format"
            # For music, check for artist, album, title, tracknumber
            if fpath.suffix.lower() in (".flac", ".mp3", ".m4a"):
                for tag in ("artist", "album", "title", "tracknumber"):
                    if tag not in audio:
                        return f"Missing tag: {tag}"
            # For video, check for internal title (if required)
            # ...
        except Exception as e:
            return f"Metadata check error: {e}"
        return ""

    def _cleanup_staging(self):
        # Remove all subfolders in /staging
        for sub in self.staging_dir.iterdir():
            if sub.is_dir():
                shutil.rmtree(sub)

    async def _prune_old_errors(self):
        # Clear error logs older than 30 days. Rows are never deleted (R-SAFE-1).
        cutoff = datetime.now(UTC) - timedelta(days=30)
        await self.db.execute(
            text(
                "UPDATE media_items SET error_log = NULL "
                "WHERE error_log IS NOT NULL AND updated_at < :cutoff"
            ),
            {"cutoff": cutoff.strftime("%Y-%m-%d %H:%M:%S")},
        )
        await self.db.commit()

    async def _finalize_states(self, db_items, found_paths):
        # Set state to 'validated' if file exists and was executed
        for item in db_items:
            if (
                item.normalization_plan
                and item.normalization_plan.target_path in found_paths
                and item.state == "executed"
            ):
                item.state = "validated"
        await self.db.commit()
