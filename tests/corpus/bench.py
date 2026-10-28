"""NF-6 throughput: scan + plan a generated 1k-file library (dry run, no transcode).

python -m tests.corpus.bench [files] > report.json
"""

import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

from app.core.orchestrator import PipelineOrchestrator
from app.models.media import FileState
from app.services.refinery import Refinery
from tests.corpus.generate import bulk, messy
from tests.pipeline_helpers import make_config, make_session_factory


async def measure(files: int) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        cfg = make_config(base)
        cfg.dry_run = True
        messy(cfg.input_dir)
        bulk(cfg.input_dir, files, base)
        total = sum(1 for p in cfg.input_dir.rglob("*") if p.is_file())
        engine, factory = await make_session_factory(base)
        svc = Refinery(PipelineOrchestrator(factory, cfg))
        t0 = time.monotonic()
        ids = await svc.ingest(cfg.input_dir)
        t1 = time.monotonic()
        await svc.advance(ids, FileState.planned)
        t2 = time.monotonic()
        report = await svc.library_report(ids)
        await engine.dispose()
    secs = t2 - t0
    return {
        "files": total,
        "items": len(ids),
        "ingest_s": round(t1 - t0, 1),
        "plan_s": round(t2 - t1, 1),
        "total_s": round(secs, 1),
        "files_per_s": round(total / secs, 2),
        "extrapolated_10k_min": round(10_000 / (total / secs) / 60, 1),
        "outcomes": report["outcomes"],
    }


if __name__ == "__main__":
    print(
        json.dumps(
            asyncio.run(measure(int(sys.argv[1]) if len(sys.argv) > 1 else 1000)),
            indent=2,
        )
    )
