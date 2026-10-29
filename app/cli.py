"""`refinery` CLI (R-CLI): thin Typer wrappers over app.services.refinery."""

import asyncio
import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.orchestrator import PipelineConfig
from app.models.media import Base, FileState
from app.services.refinery import Refinery, build_orchestrator

app = typer.Typer(
    help="Media Refinery: normalise, verify and publish a media library.",
    no_args_is_help=True,
)
console = Console(width=200)


class MediaKind(StrEnum):
    music = "music"
    audiobook = "audiobook"
    movie = "movie"
    series = "series"
    ebook = "ebook"


PathArg = Annotated[Path, typer.Argument(exists=True, help="File or directory.")]
DryRun = Annotated[
    bool,
    typer.Option("--dry-run", help="Plan only; write nothing outside work/dry-run/."),
]
Kind = Annotated[
    MediaKind | None, typer.Option("--type", help="Only handle this media type.")
]


async def _open(dry_run: bool):
    """(service, dispose). Dry-run uses a throwaway DB under work/dry-run/ (R-SAFE-4)."""
    cfg = PipelineConfig.from_settings()
    cfg.dry_run = dry_run
    if dry_run:
        db = cfg.work_dir / "dry-run" / "cli.sqlite"
        db.parent.mkdir(parents=True, exist_ok=True)
        db.unlink(missing_ok=True)
        engine = create_async_engine(f"sqlite+aiosqlite:///{db}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = sessionmaker(  # type: ignore[call-overload]
            engine, expire_on_commit=False, class_=AsyncSession
        )
    else:
        from app.core.database import AsyncSessionLocal, engine, init_db

        await init_db()
        factory = AsyncSessionLocal
    return Refinery(build_orchestrator(factory, cfg)), engine.dispose


def _drive(dry_run: bool, work):
    async def go():
        service, dispose = await _open(dry_run)
        try:
            return await work(service)
        finally:
            await dispose()

    return asyncio.run(go())


def _types(kind: MediaKind | None) -> set[str] | None:
    return {kind.value} if kind else None


def _print_plan(rows: list[dict]) -> None:
    table = Table(
        "item", "type", "state", "action", "source", "target", show_lines=False
    )
    table.columns[-1].overflow = "fold"
    for r in rows:
        table.add_row(
            r["id"][:8],
            r["type"],
            r["state"],
            r["action"],
            Path(r["source"]).name,
            r["target"],
        )
    console.print(table)
    for r in rows:
        if r["error"]:
            console.print(f"[red]{r['id'][:8]}[/red] {r['error']}")


def _stage(path: Path, until: FileState, kind: MediaKind | None, dry_run: bool):
    async def work(service: Refinery):
        ids = await service.ingest(path)
        await service.advance(ids, until, _types(kind))
        return await service.plan_rows(ids)

    _print_plan(_drive(dry_run, work))


@app.command()
def scan(path: PathArg, dry_run: DryRun = False, type: Kind = None) -> None:
    """Import files and classify/enrich them (no plan yet)."""
    _stage(path, FileState.enriched, type, dry_run)


@app.command()
def plan(path: PathArg, dry_run: DryRun = True, type: Kind = None) -> None:
    """Library-level report of what a run would do. Always a dry run: nothing is written
    outside work/dry-run/."""

    async def work(service: Refinery):
        ids = await service.ingest(path)
        await service.advance(ids, FileState.planned, _types(type))
        return await service.library_report(ids)

    r = _drive(True, work)  # `dry_run` is accepted for compatibility; plan never writes
    console.print(f"{r['total']} items")
    for outcome, n in r["outcomes"].items():
        console.print(f"  {outcome}: {n}")
    console.print(
        f"estimated disk {r['est_disk_bytes'] / 1e6:.1f} MB, "
        f"time {r['est_seconds'] / 60:.1f} min (rough, single worker)"
    )
    for label, key in (
        ("needs review", "needs_review"),
        ("not planned", "not_planned"),
    ):
        if r[key]:
            console.print(f"[yellow]{label} ({len(r[key])}):[/yellow]")
            for line in r[key]:
                console.print(f"  {line}")


@app.command()
def approve(
    path: PathArg,
    dry_run: DryRun = False,
    type: Kind = None,
    include_review: Annotated[
        bool, typer.Option(help="Also approve low-confidence (review-flagged) items")
    ] = False,
) -> None:
    """Plan, then approve every item under PATH except review-flagged ones (see --include-review)."""

    async def work(service: Refinery):
        ids = await service.ingest(path)
        await service.advance(ids, FileState.planned, _types(type))
        count = await service.approve(ids, _types(type), skip_review=not include_review)
        return count, await service.plan_rows(ids)

    count, rows = _drive(dry_run, work)
    _print_plan(rows)
    console.print(f"approved {count}")


@app.command()
def run(path: PathArg, dry_run: DryRun = False, type: Kind = None) -> None:
    """Full pipeline: scan, plan, approve (not review-flagged), execute, verify, publish."""

    async def work(service: Refinery):
        return await service.plan_rows(await service.run(path, _types(type)))

    _print_plan(_drive(dry_run, work))


@app.command()
def doctor() -> None:
    """Preflight: tools present, paths writable, keys set, servers reachable. Exit 1 on failure."""
    from app.core.config import settings
    from app.services.doctor import run_checks

    checks = asyncio.run(run_checks(settings))
    mark = {
        "ok": "[green]ok[/green]",
        "warn": "[yellow]warn[/yellow]",
        "fail": "[red]FAIL[/red]",
    }
    for c in checks:
        console.print(f"{mark[c.status]:>20}  {c.name}: {c.detail}")
    if any(c.status == "fail" for c in checks):
        raise typer.Exit(1)
    console.print("doctor: ready; next `refinery plan <library>`")


def _report(rows: list[dict]) -> None:
    for row in rows:
        console.print_json(json.dumps(row))
    if any(r.get("ok") is False for r in rows):
        raise typer.Exit(1)


@app.command()
def verify(path: PathArg) -> None:
    """Re-verify published files under PATH and report drift (exit 1 on drift)."""
    _report(_drive(False, lambda service: service.verify(path)))


@app.command()
def audit(path: PathArg) -> None:
    """Run the issue detector over published library items under PATH."""
    _report(_drive(False, lambda service: service.audit(path)))


if __name__ == "__main__":
    app()
