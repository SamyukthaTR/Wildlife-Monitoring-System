"""Runs the analysis engines over an observation and persists what they found.

Called from a FastAPI BackgroundTask after upload, and from the manual
re-analysis endpoints. It opens its own database session: the request's session
is closed as soon as the response is sent, so a background task cannot borrow it.

Re-running an observation replaces its previous detections rather than adding to
them, so a re-analysis after a model or threshold change leaves one coherent set
of results instead of a pile of duplicates.
"""

import datetime
import logging
import os

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.analysis.models import (
    AnalysisRun,
    AudioClassification,
    ImageDetection,
    RunStatusEnum,
)
from app.modules.observations.models import FileTypeEnum, ObservationLog
from app.modules.species.catalog import resolve_label

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


def run_analysis(observation_id: int) -> None:
    """Analyse one observation. Never raises -- failures are recorded on the run."""
    db = SessionLocal()
    try:
        observation = db.query(ObservationLog).filter(
            ObservationLog.id == observation_id
        ).first()
        if observation is None:
            logger.warning("Analysis requested for missing observation %s", observation_id)
            return

        run = AnalysisRun(observation_id=observation.id, status=RunStatusEnum.RUNNING)
        db.add(run)
        observation.processing_status = STATUS_PROCESSING
        db.commit()
        db.refresh(run)

        try:
            if not os.path.exists(observation.storage_path):
                raise FileNotFoundError(f"file missing on disk: {observation.storage_path}")

            _clear_previous_results(db, observation.id)

            if observation.file_type == FileTypeEnum.IMAGE:
                result = _analyse_image(db, observation)
            else:
                result = _analyse_audio(db, observation)

            run.status = RunStatusEnum.COMPLETED
            run.models_used = result["models_used"]
            run.latency_ms = result["latency_ms"]
            run.animal_count = result.get("animal_count")
            quality = result.get("quality") or {}
            run.quality_score = quality.get("score")
            run.quality_notes = quality.get("notes")
            observation.processing_status = STATUS_COMPLETED

        except Exception as exc:  # noqa: BLE001 - record, do not propagate
            logger.exception("Analysis failed for observation %s", observation_id)
            db.rollback()
            run = db.query(AnalysisRun).filter(AnalysisRun.id == run.id).first()
            observation = db.query(ObservationLog).filter(
                ObservationLog.id == observation_id
            ).first()
            if run:
                run.status = RunStatusEnum.FAILED
                run.error = f"{type(exc).__name__}: {exc}"[:500]
                run.finished_at = datetime.datetime.now(datetime.timezone.utc)
            if observation:
                observation.processing_status = STATUS_FAILED
            db.commit()
            return

        run.finished_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()

    finally:
        db.close()


def _clear_previous_results(db: Session, observation_id: int) -> None:
    db.query(ImageDetection).filter(
        ImageDetection.observation_id == observation_id
    ).delete(synchronize_session=False)
    db.query(AudioClassification).filter(
        AudioClassification.observation_id == observation_id
    ).delete(synchronize_session=False)


def _analyse_image(db: Session, observation: ObservationLog) -> dict:
    from app.ml.image import analyse_image

    result = analyse_image(observation.storage_path)

    for detection in result["detections"]:
        species = resolve_label(db, detection["label_raw"], detection.get("species_group"))
        bbox = detection.get("bbox") or {}
        db.add(ImageDetection(
            observation_id=observation.id,
            species_id=species.id if species else None,
            label_raw=detection["label_raw"],
            label_source=detection["label_source"],
            confidence=detection["confidence"],
            detector_label=detection.get("detector_label"),
            candidate_label=detection.get("candidate_label"),
            candidate_confidence=detection.get("candidate_confidence"),
            bbox_x=bbox.get("x"),
            bbox_y=bbox.get("y"),
            bbox_w=bbox.get("w"),
            bbox_h=bbox.get("h"),
            detection_index=detection["detection_index"],
            posture_hint=detection.get("posture_hint"),
            is_unknown=detection["is_unknown"],
        ))
    return result


def _analyse_audio(db: Session, observation: ObservationLog) -> dict:
    from app.ml.audio import analyse_audio

    result = analyse_audio(observation.storage_path)

    for classification in result["classifications"]:
        species = None
        if not classification["is_noise"]:
            species = resolve_label(
                db, classification["label_raw"], classification.get("species_group")
            )
        db.add(AudioClassification(
            observation_id=observation.id,
            species_id=species.id if species else None,
            label_raw=classification["label_raw"],
            label_source=classification["label_source"],
            confidence=classification["confidence"],
            start_time_s=classification["start_time_s"],
            end_time_s=classification["end_time_s"],
            is_noise=classification["is_noise"],
        ))
    return result
