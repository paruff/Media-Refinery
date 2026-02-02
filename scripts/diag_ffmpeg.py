#!/usr/bin/env python3
"""Diagnostic runner: run ffmpeg into a pytest-like tmpdir and capture PID, stderr,
and directory listings. Used to debug file visibility issues under pytest/tmp_path.
"""
import asyncio
import os
import shutil
import tempfile
import subprocess
from pathlib import Path


async def run_ffmpeg_to(path: Path):
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        "testdata/audio/test_valid.mp3",
        "-map_metadata",
        "0",
        "-c:a",
        "flac",
        "-compression_level",
        "5",
        str(path),
    ]
    print("CMD:", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    print("PID", proc.pid)
    await asyncio.sleep(0.01)
    try:
        running_list = [p.name for p in path.parent.iterdir()]
    except Exception as e:
        running_list = f"ls failed: {e}"
    print("LS while running:", running_list)
    out, err = await proc.communicate()
    print("RC", proc.returncode)
    print("STDERR (truncated):")
    print(err.decode("utf-8", errors="replace")[:2000])
    try:
        after_list = [p.name for p in path.parent.iterdir()]
    except Exception as e:
        after_list = f"ls failed: {e}"
    print("LS after:", after_list)
    print("Exists?", path.exists())
    if path.exists():
        st = path.stat()
        print("Size", st.st_size, "mtime", st.st_mtime)


async def main():
    tmpdir = Path(tempfile.mkdtemp(prefix="pytest-diag-"))
    out = tmpdir / "test_valid.flac"

    print("TMPDIR", tmpdir)
    print("CWD", Path.cwd())
    print("UID/GID", os.getuid(), os.getgid())

    try:
        df = subprocess.run(["df", "-h", str(tmpdir)], capture_output=True, text=True)
        print("DF:", df.stdout)
    except Exception as e:
        print("DF failed:", e)

    await run_ffmpeg_to(out)

    # Now run converter.convert to same dir for comparison
    try:
        from src.audio.converter import AudioConverter

        conv = AudioConverter()
        print("\nRunning converter.convert against same tmpdir")
        res = await conv.convert(Path("testdata/audio/test_valid.mp3"), tmpdir)
        print("CONVERTER RESULT:", res)
        try:
            final_list = [p.name for p in tmpdir.iterdir()]
        except Exception as e:
            final_list = f"ls failed: {e}"
        print("LS final:", final_list)
    except Exception as e:
        print("Converter call failed:", e)

    # cleanup
    try:
        shutil.rmtree(tmpdir)
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
