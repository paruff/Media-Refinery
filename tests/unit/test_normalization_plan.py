import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
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


def test_create_normalization_plan(db_session):
    media = MediaItem(id=str(uuid.uuid4()), source_path="/input/test.mp4")
    db_session.add(media)
    db_session.commit()

    plan = NormalizationPlan(
        media_item_id=media.id,
        needs_transcode=True,
        needs_rename=True,
        needs_subtitle_conversion=False,
        target_path="/output/test_canonical.mp4",
        ffmpeg_args=["-c:a", "aac"],
        original_hash="abc123",
        plan_status=PlanStatus.draft,
        execution_log="",
    )
    db_session.add(plan)
    db_session.commit()

    fetched = (
        db_session.query(NormalizationPlan).filter_by(media_item_id=media.id).first()
    )
    assert fetched is not None
    assert fetched.media_item_id == media.id
    assert fetched.target_path == "/output/test_canonical.mp4"
    assert fetched.needs_transcode is True
    assert fetched.ffmpeg_args == ["-c:a", "aac"]
    assert fetched.plan_status == PlanStatus.draft
    assert fetched.is_ready


def test_unique_target_path_constraint(db_session):
    media1 = MediaItem(id=str(uuid.uuid4()), source_path="/input/1.mp4")
    media2 = MediaItem(id=str(uuid.uuid4()), source_path="/input/2.mp4")
    db_session.add_all([media1, media2])
    db_session.commit()

    plan1 = NormalizationPlan(
        media_item_id=media1.id,
        needs_transcode=True,
        needs_rename=False,
        needs_subtitle_conversion=False,
        target_path="/output/unique.mp4",
        ffmpeg_args=["-c:a", "aac"],
        original_hash="hash1",
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
        target_path="/output/unique.mp4",  # duplicate path
        ffmpeg_args=["-c:v", "h264"],
        original_hash="hash2",
        plan_status=PlanStatus.draft,
        execution_log="",
    )
    db_session.add(plan2)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_plan_status_lifecycle(db_session):
    media = MediaItem(id=str(uuid.uuid4()), source_path="/input/lifecycle.mp4")
    db_session.add(media)
    db_session.commit()

    plan = NormalizationPlan(
        media_item_id=media.id,
        needs_transcode=True,
        needs_rename=True,
        needs_subtitle_conversion=True,
        target_path="/output/lifecycle.mp4",
        ffmpeg_args=["-c:a", "aac"],
        original_hash="hashlifecycle",
        plan_status=PlanStatus.draft,
        execution_log="",
    )
    db_session.add(plan)
    db_session.commit()

    plan.plan_status = PlanStatus.approved
    db_session.commit()
    assert plan.plan_status == PlanStatus.approved
    plan.plan_status = PlanStatus.executing
    db_session.commit()
    assert plan.plan_status == PlanStatus.executing
    plan.plan_status = PlanStatus.completed
    db_session.commit()
    assert plan.plan_status == PlanStatus.completed
    plan.plan_status = PlanStatus.failed
    db_session.commit()
    assert plan.plan_status == PlanStatus.failed


def test_is_ready_property(db_session):
    media = MediaItem(id=str(uuid.uuid4()), source_path="/input/ready.mp4")
    db_session.add(media)
    db_session.commit()

    plan = NormalizationPlan(
        media_item_id=media.id,
        needs_transcode=True,
        needs_rename=True,
        needs_subtitle_conversion=False,
        target_path="/output/ready.mp4",
        ffmpeg_args=["-c:a", "aac"],
        original_hash="hashready",
        plan_status=PlanStatus.draft,
        execution_log="",
    )
    db_session.add(plan)
    db_session.commit()
    assert plan.is_ready

    # Remove ffmpeg_args to make it not ready
    plan.ffmpeg_args = None
    db_session.commit()
    assert not plan.is_ready


def test_plan_association_with_media_item(db_session):
    media = MediaItem(id=str(uuid.uuid4()), source_path="/input/assoc.mp4")
    db_session.add(media)
    db_session.commit()

    plan = NormalizationPlan(
        media_item_id=media.id,
        needs_transcode=False,
        needs_rename=True,
        needs_subtitle_conversion=False,
        target_path="/output/assoc.mp4",
        ffmpeg_args=["-c:v", "h264"],
        original_hash="hashassoc",
        plan_status=PlanStatus.draft,
        execution_log="",
    )
    db_session.add(plan)
    db_session.commit()

    fetched_media = db_session.query(MediaItem).filter_by(id=media.id).first()
    assert fetched_media.normalization_plan is not None
    assert fetched_media.normalization_plan.target_path == "/output/assoc.mp4"
