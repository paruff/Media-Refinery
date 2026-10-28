"""PUBLISH / archive / quarantine file operations (R-SAFE-1, R-SAFE-2)."""

import asyncio
import errno
import os
import shutil
from pathlib import Path

from app.core.verify import sha256_file
from app.models.saga import SagaFileMoveLog, SagaLogStatus


def _fsync_copy(src: Path, dst: Path) -> None:
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        shutil.copyfileobj(fin, fout, 1024 * 1024)
        fout.flush()
        os.fsync(fout.fileno())


def _unique(path: Path) -> Path:
    candidate, n = path, 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.{n}")
        n += 1
    return candidate


def _move_into_place(
    work_file: Path, dest: Path, tmp: Path, sha: str | None = None
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        try:
            os.replace(work_file, dest)  # atomic when work and dest share a mount
        except OSError as e:
            if e.errno != errno.EXDEV:  # separate bind mounts: same st_dev, still EXDEV
                raise
            _fsync_copy(work_file, tmp)
            if sha256_file(str(tmp)) != (sha or sha256_file(str(work_file))):
                raise OSError("checksum mismatch after copy") from e
            os.replace(tmp, dest)
            work_file.unlink()
    finally:
        tmp.unlink(missing_ok=True)


async def publish_file(
    session, plan_id: str, work_file: Path, dest: Path, sha: str
) -> None:
    """Saga: prepared -> (copy+fsync+verify+rename | atomic rename) -> committed.

    Refuses to overwrite (caller checks).
    """
    tmp = dest.with_name(f".{dest.name}.tmp")
    log = SagaFileMoveLog(
        plan_id=plan_id, src_path=str(work_file), tmp_path=str(tmp), dest_path=str(dest)
    )
    session.add(log)
    await session.commit()  # WAL entry persisted before any side effect
    try:
        await asyncio.to_thread(_move_into_place, work_file, dest, tmp, sha)
    except Exception as e:
        log.status = SagaLogStatus.failed
        log.error = str(e)
        await session.commit()
        raise
    log.status = SagaLogStatus.committed
    await session.commit()


def archive_original(
    source: Path, input_root: Path, archive_dir: Path, run_id: str
) -> Path | None:
    """Move (never delete) the original to archive/{run_id}/<path relative to input>."""
    if not source.exists():
        return None
    try:
        rel = source.resolve().relative_to(input_root.resolve())
    except ValueError:
        rel = Path(source.name)
    dest = _unique(archive_dir / run_id / rel)
    tmp = dest.with_name(f".{dest.name}.tmp")
    _move_into_place(source, dest, tmp)  # checksummed across volumes
    return dest


def quarantine_file(
    path: Path, quarantine_dir: Path, reason: str, item_id: str
) -> Path | None:
    if not path.exists():
        return None
    dest = _unique(quarantine_dir / reason / f"{item_id}-{path.name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(dest))
    return dest


# CODEOWNERS probe (G14); do not merge
