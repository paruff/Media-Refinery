import argparse
import json
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path
from zipfile import ZipFile


def mask_path(path):
    # Replace user home and known sensitive roots with <MASKED>
    home = str(Path.home())
    path = re.sub(re.escape(home), "<HOME>", path)
    # Mask absolute paths
    path = re.sub(r"/[^/]+/([^/]+)", r"/<MASKED>/\1", path)
    return path


def dump_db_anonymized(db_path, out_path):
    with sqlite3.connect(db_path) as conn, open(out_path, "w") as f:
        for line in conn.iterdump():
            # Mask file paths in SQL
            masked = re.sub(r"(/[^'\"]+)+", lambda m: mask_path(m.group()), line)
            f.write(f"{masked}\n")


def collect_ffprobe(media_id, output_dir):
    # Simulate ffprobe output (in real use, call ffprobe or use DB cache)
    ffprobe_json = output_dir / f"ffprobe_{media_id}.json"
    # For demo, just write a stub
    ffprobe_data = {
        "streams": [
            {"codec_name": "h264", "codec_type": "video"},
            {"codec_name": "dts", "codec_type": "audio"},
        ],
        "format": {"filename": f"/media/{media_id}.mkv"},
    }
    with open(ffprobe_json, "w") as f:
        json.dump(ffprobe_data, f, indent=2)
    return ffprobe_json


def collect_logs(output_dir):
    logs_dir = Path("logs")
    if logs_dir.exists():
        for log_file in logs_dir.glob("*.log"):
            shutil.copy(log_file, output_dir / log_file.name)


def main():
    parser = argparse.ArgumentParser(description="Media-Refinery Debug Bundle Tool")
    parser.add_argument("media_id", help="Media ID to debug")
    parser.add_argument("--db", default="data/media_refinery.sqlite", help="Path to DB")
    parser.add_argument("--out", default=None, help="Output zip file path")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # Dump anonymized DB
        db_dump = tmp / "db_dump.sql"
        dump_db_anonymized(args.db, db_dump)
        # Collect logs
        collect_logs(tmp)
        # Collect ffprobe data
        ffprobe_json = collect_ffprobe(args.media_id, tmp)
        # Bundle
        bundle_path = args.out or f"bugreport_{args.media_id}.zip"
        with ZipFile(bundle_path, "w") as z:
            z.write(db_dump, arcname="db_dump.sql")
            z.write(ffprobe_json, arcname=ffprobe_json.name)
            for log in tmp.glob("*.log"):
                z.write(log, arcname=log.name)
        print(f"Bug Report Bundle created: {bundle_path}")


if __name__ == "__main__":
    main()
