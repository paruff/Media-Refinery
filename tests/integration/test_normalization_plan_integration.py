import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.media import Base, MediaItem, NormalizationPlan, PlanStatus
import uuid


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_create_and_query_plan(db_session):
    media = MediaItem(id=str(uuid.uuid4()), source_path="/input/integration.mp4")
    db_session.add(media)
    db_session.commit()

    plan = NormalizationPlan(
        media_item_id=media.id,
        needs_transcode=True,
        needs_rename=True,
        needs_subtitle_conversion=True,
        target_path="/output/integration.mp4",
        ffmpeg_args=["-c:a", "aac", "-b:a", "192k"],
        original_hash="hashintegration",
        plan_status=PlanStatus.draft,
        execution_log="Plan created",
    )
    db_session.add(plan)
    db_session.commit()

    # Simulate GET /media/{id}/plan
    fetched = (
        db_session.query(NormalizationPlan).filter_by(media_item_id=media.id).first()
    )
    assert fetched is not None
    assert fetched.target_path == "/output/integration.mp4"
    assert fetched.ffmpeg_args == ["-c:a", "aac", "-b:a", "192k"]
    assert fetched.plan_status == PlanStatus.draft
    assert fetched.media_item.source_path == "/input/integration.mp4"
    assert fetched.is_ready


def test_unique_target_path_integration(db_session):
    media1 = MediaItem(id=str(uuid.uuid4()), source_path="/input/int1.mp4")
    media2 = MediaItem(id=str(uuid.uuid4()), source_path="/input/int2.mp4")
    db_session.add_all([media1, media2])
    db_session.commit()

    plan1 = NormalizationPlan(
        media_item_id=media1.id,
        needs_transcode=True,
        needs_rename=False,
        needs_subtitle_conversion=False,
        target_path="/output/integration_unique.mp4",
        ffmpeg_args=["-c:a", "aac"],
        original_hash="hashint1",
        plan_status=PlanStatus.draft,
        execution_log="",
    )
    db_session.add(plan1)
    db_session.commit()

    plan2 = NormalizationPlan(
        media_item_id=media2.id,
        needs_transcode=False,
        needs_rename=True,
        needs_subtitle_conversion=False,
        target_path="/output/integration_unique.mp4",  # duplicate path
        ffmpeg_args=["-c:v", "h264"],
        original_hash="hashint2",
        plan_status=PlanStatus.draft,
        execution_log="",
    )
    db_session.add(plan2)
    with pytest.raises(Exception):
        db_session.commit()


def test_plan_status_lifecycle_integration(db_session):
    media = MediaItem(id=str(uuid.uuid4()), source_path="/input/int_lifecycle.mp4")
    db_session.add(media)
    db_session.commit()

    plan = NormalizationPlan(
        media_item_id=media.id,
        needs_transcode=True,
        needs_rename=True,
        needs_subtitle_conversion=True,
        target_path="/output/int_lifecycle.mp4",
        ffmpeg_args=["-c:a", "aac"],
        original_hash="hashintcycle",
        plan_status=PlanStatus.draft,
        execution_log="",
    )
    db_session.add(plan)
    db_session.commit()

    for status in [
        PlanStatus.approved,
        PlanStatus.executing,
        PlanStatus.completed,
        PlanStatus.failed,
    ]:
        plan.plan_status = status
        db_session.commit()
        assert plan.plan_status == status


def test_plan_json_projection(db_session):
    media = MediaItem(id=str(uuid.uuid4()), source_path="/input/json.mp4")
    db_session.add(media)
    db_session.commit()

    plan = NormalizationPlan(
        media_item_id=media.id,
        needs_transcode=True,
        needs_rename=True,
        needs_subtitle_conversion=False,
        target_path="/output/json.mp4",
        ffmpeg_args=["-c:a", "aac"],
        original_hash="hashjson",
        plan_status=PlanStatus.draft,
        execution_log="",
    )
    db_session.add(plan)
    db_session.commit()

    # Simulate API serialization
    plan_dict = {
        "id": plan.id,
        "media_item_id": plan.media_item_id,
        "needs_transcode": plan.needs_transcode,
        "needs_rename": plan.needs_rename,
        "needs_subtitle_conversion": plan.needs_subtitle_conversion,
        "target_path": plan.target_path,
        "ffmpeg_args": plan.ffmpeg_args,
        "original_hash": plan.original_hash,
        "plan_status": plan.plan_status.value,
        "execution_log": plan.execution_log,
        "created_at": str(plan.created_at),
        "is_ready": plan.is_ready,
    }
    assert plan_dict["target_path"] == "/output/json.mp4"
    assert "-c:a" in plan_dict["ffmpeg_args"]
    assert plan_dict["is_ready"] is True
