import enum
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class RunStatusEnum(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisRun(Base):
    """One execution of the analysis pipeline over one observation.

    Kept as its own table because the specification asks for image and audio
    inference latency as a performance metric, and because a failed model load
    or a corrupt file needs somewhere honest to land instead of disappearing.

    Re-running an observation replaces its detections (delete-then-insert), so
    detection rows point at the observation rather than at a specific run.
    """
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, index=True)
    observation_id = Column(Integer, ForeignKey("observation_log.id"), index=True, nullable=False)
    status = Column(Enum(RunStatusEnum), nullable=False, default=RunStatusEnum.RUNNING)
    models_used = Column(String, nullable=True)
    latency_ms = Column(Integer, nullable=True)

    # Image-only summary fields, null for audio observations.
    animal_count = Column(Integer, nullable=True)
    quality_score = Column(Float, nullable=True)
    quality_notes = Column(String, nullable=True)

    error = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)


class ImageDetection(Base):
    """One animal detected in one image.

    A row with a bounding box came from the detector; a row without one came
    from whole-image classification after the detector found nothing.
    """
    __tablename__ = "image_detections"

    id = Column(Integer, primary_key=True, index=True)
    observation_id = Column(Integer, ForeignKey("observation_log.id"), index=True, nullable=False)
    species_id = Column(Integer, ForeignKey("species.id"), nullable=True)

    # What the platform is willing to assert. When the classifier is not
    # confident this is the literal string "unidentified animal" -- never a
    # species name the platform does not stand behind.
    label_raw = Column(String, nullable=False)
    label_source = Column(String, nullable=False)  # yolov8n-coco | resnet50-imagenet
    confidence = Column(Float, nullable=False)

    # The COCO class that localised this box. Kept separately because it is a
    # coarse shape match, not an identification: YOLO calls a snapping turtle an
    # "elephant" often enough that presenting it as the finding would mislead.
    detector_label = Column(String, nullable=True)

    # The classifier's best animal guess and its score, retained even when it
    # fell below the assertion threshold. "Unidentified, closest match terrapin
    # at 18%" is more useful to a surveyor than "unidentified" alone.
    candidate_label = Column(String, nullable=True)
    candidate_confidence = Column(Float, nullable=True)

    # Bounding box in ORIGINAL image pixel coordinates. Null when the detection
    # came from whole-image classification rather than a localised box.
    bbox_x = Column(Integer, nullable=True)
    bbox_y = Column(Integer, nullable=True)
    bbox_w = Column(Integer, nullable=True)
    bbox_h = Column(Integer, nullable=True)

    # Stable index of this animal within this frame. This is what the platform
    # means by "individual identification": individual N *in this image*.
    # Matching an individual across images (stripe/spot re-ID) is not attempted
    # and is not claimed anywhere.
    detection_index = Column(Integer, nullable=False, default=0)

    # Coarse posture read from the box aspect ratio. A geometric heuristic, not
    # a trained behaviour classifier -- surfaced as such in the API and UI.
    posture_hint = Column(String, nullable=True)

    # True when classification confidence fell below the threshold: an animal
    # is present but the platform declines to name it.
    is_unknown = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AudioClassification(Base):
    """One acoustic event window with one AudioSet label.

    Non-biological labels (wind, rain, speech, vehicles) are kept with
    is_noise=True rather than discarded, so the noise filtering is auditable
    instead of invisible.
    """
    __tablename__ = "audio_classifications"

    id = Column(Integer, primary_key=True, index=True)
    observation_id = Column(Integer, ForeignKey("observation_log.id"), index=True, nullable=False)
    species_id = Column(Integer, ForeignKey("species.id"), nullable=True)

    label_raw = Column(String, nullable=False)
    label_source = Column(String, nullable=False)  # ast-audioset
    confidence = Column(Float, nullable=False)

    start_time_s = Column(Float, nullable=False)
    end_time_s = Column(Float, nullable=False)

    is_noise = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
