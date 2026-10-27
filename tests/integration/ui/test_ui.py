"""G10: Review->approve reaches validated; axe finds no serious/critical issues."""

from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from app.models.media import (
    FileState,
    MediaItem,
    MediaType,
    NormalizationPlan,
    VerificationRecord,
)
from tests.pipeline_helpers import import_input, make_mp3

pytestmark = [pytest.mark.integration]
AXE = (Path(__file__).parent / "axe.min.js").read_text()
AXE_RUN = """axe.run().then(r => ({passes: r.passes.length,
  bad: r.violations.filter(v => ['serious','critical'].includes(v.impact))
    .map(v => v.id + ': ' + v.nodes.map(n => n.target).join(' | '))}))"""
VIEWS = ["queue", "review", "quarantine", "summary", "items/a.mp3"]


@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser.new_page()
        browser.close()


async def _real_item(cfg, factory):
    make_mp3(
        cfg.input_dir / "song.mp3",
        artist="The Artist",
        album="The Album",
        title="Song",
        date="2020",
        track="1",
    )
    await import_input(cfg, factory)


async def _seed(cfg, factory):
    async with factory() as s:
        for name, state in (
            ("a.mp3", FileState.planned),
            ("b.mp3", FileState.quarantined),
        ):
            s.add(
                MediaItem(
                    id=name,
                    source_path=f"/in/{name}",
                    state=state,
                    media_type=MediaType.music,
                    error_log="rejected: declined at review"
                    if state == FileState.quarantined
                    else None,
                )
            )
            s.add(
                NormalizationPlan(
                    media_item_id=name,
                    target_path=f"/lib/{name}",
                    original_hash=name,
                    ffmpeg_args=["-c", "copy"],
                )
            )
        s.add(
            VerificationRecord(
                media_item_id="a.mp3",
                passed=True,
                checks=[{"name": "duration", "passed": True, "detail": "2.0s ≥ 1.9s"}],
            )
        )
        await s.commit()


def test_approve_from_review_reaches_validated(live, page):
    base = live(_real_item, run_pipeline=True)
    row = page.get_by_role("row", name="song.mp3")
    for _ in range(
        60
    ):  # Review is a snapshot (no auto-refresh): wait for the plan to land
        page.goto(f"{base}/ui/review")
        if row.count():
            break
        page.wait_for_timeout(500)
    expect(row).to_be_visible()
    expect(page.get_by_text("The Artist")).to_be_visible()  # target path in the diff
    row.get_by_role("button", name="Approve").click()
    expect(row).to_have_count(0)  # htmx removed it from the review list
    page.goto(f"{base}/ui/queue")
    for _ in range(60):
        if page.get_by_role("row", name="song.mp3").get_by_text("validated").count():
            break
        page.wait_for_timeout(500)
        page.reload()
    expect(
        page.get_by_role("row", name="song.mp3").get_by_text("validated")
    ).to_be_visible()


@pytest.mark.parametrize("view", VIEWS)
def test_axe_serious_or_critical_is_zero(live, page, view):
    base = live(_seed)
    page.goto(f"{base}/ui/{view}")
    page.add_script_tag(content=AXE)
    found = page.evaluate(AXE_RUN)
    assert found["passes"] > 10, "axe evaluated almost nothing"
    assert found["bad"] == [], found["bad"]


def test_axe_harness_detects_a_violation(page):
    page.set_content(
        '<html lang="en"><title>t</title><main><img src="x.png"></main></html>'
    )
    page.add_script_tag(content=AXE)
    assert page.evaluate(AXE_RUN)["bad"], "axe should flag the image with no alt text"


def test_reject_asks_for_confirmation_in_a_styled_dialog(live, page):
    base = live(_seed)
    page.goto(f"{base}/ui/review")
    page.get_by_role("row", name="a.mp3").get_by_role("button", name="Reject").click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_contain_text("Reject and quarantine")
    dialog.get_by_role("button", name="Cancel").click()
    expect(page.get_by_role("row", name="a.mp3")).to_have_count(1)  # nothing happened
    page.get_by_role("row", name="a.mp3").get_by_role("button", name="Reject").click()
    page.get_by_role("dialog").get_by_role("button", name="Reject").click()
    expect(page.get_by_role("row", name="a.mp3")).to_have_count(0)
