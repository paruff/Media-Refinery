import errno
import os

import pytest
from sqlalchemy import select

from app.core.publish import archive_original, publish_file, quarantine_file
from app.core.verify import sha256_file
from app.models.saga import SagaFileMoveLog, SagaLogStatus


@pytest.mark.asyncio
async def test_publish_commits_saga_and_moves_file(async_session, tmp_path):
    work = tmp_path / "work" / "out.mkv"
    work.parent.mkdir()
    work.write_bytes(b"data")
    dest = tmp_path / "lib" / "A" / "a.mkv"
    await publish_file(async_session, "p1", work, dest, sha256_file(str(work)))
    assert dest.read_bytes() == b"data" and not work.exists()
    log = (await async_session.execute(select(SagaFileMoveLog))).scalars().one()
    assert log.status == SagaLogStatus.committed
    assert not list(dest.parent.glob(".*.tmp"))


@pytest.mark.asyncio
async def test_publish_copies_when_bind_mounts_share_st_dev(
    async_session, tmp_path, monkeypatch
):
    """Separate bind mounts of one host fs report the same st_dev but rename gives EXDEV."""
    work = tmp_path / "work" / "out.mkv"
    work.parent.mkdir()
    work.write_bytes(b"data")
    dest = tmp_path / "lib" / "a.mkv"
    real_replace = os.replace

    def replace(src, dst):
        if src == work:
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    await publish_file(async_session, "p2", work, dest, sha256_file(str(work)))
    assert dest.read_bytes() == b"data" and not work.exists()


def test_archive_moves_and_never_overwrites(tmp_path):
    inp, arc = tmp_path / "in", tmp_path / "arc"
    (inp / "sub").mkdir(parents=True)
    for n in range(2):
        f = inp / "sub" / "a.mp3"
        f.write_bytes(bytes([n]))
        archive_original(f, inp, arc, "run1")
    assert sorted(p.name for p in (arc / "run1" / "sub").iterdir()) == [
        "a.mp3",
        "a.mp3.1",
    ]
    assert not (inp / "sub" / "a.mp3").exists()


def test_quarantine_by_reason(tmp_path):
    f = tmp_path / "x.mkv"
    f.write_bytes(b"x")
    dest = quarantine_file(f, tmp_path / "q", "decode_failed", "id1")
    assert dest == tmp_path / "q" / "decode_failed" / "id1-x.mkv" and dest.exists()
