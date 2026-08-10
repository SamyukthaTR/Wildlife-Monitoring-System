from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class SpeciesBrief(BaseModel):
    """Taxonomy attached to a detection, when the label resolved to the catalog."""
    id: int
    scientific_name: str
    common_name: Optional[str] = None
    rank: str
    species_group: str
    taxon_class: Optional[str] = None
    iucn_status: Optional[str] = None
    is_endangered: bool

    model_config = ConfigDict(from_attributes=True)


class BoundingBox(BaseModel):
    """Pixel coordinates in the ORIGINAL image, not the rendered one."""
    x: int
    y: int
    w: int
    h: int


class ImageDetectionResponse(BaseModel):
    id: int
    detection_index: int
    # "unidentified animal" when the platform declines to name what it found.
    label_raw: str
    label_source: str
    confidence: float
    # The COCO class that localised the box -- a shape match, not an ID.
    detector_label: Optional[str] = None
    # Best classifier guess, kept even when it was too weak to assert.
    candidate_label: Optional[str] = None
    candidate_confidence: Optional[float] = None
    bbox: Optional[BoundingBox] = None
    posture_hint: Optional[str] = None
    is_unknown: bool
    species: Optional[SpeciesBrief] = None


class AudioClassificationResponse(BaseModel):
    id: int
    label_raw: str
    label_source: str
    confidence: float
    start_time_s: float
    end_time_s: float
    is_noise: bool
    species: Optional[SpeciesBrief] = None


class AnalysisRunResponse(BaseModel):
    id: int
    observation_id: int
    status: str
    models_used: Optional[str] = None
    latency_ms: Optional[int] = None
    animal_count: Optional[int] = None
    quality_score: Optional[float] = None
    quality_notes: Optional[str] = None
    error: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ObservationAnalysisResponse(BaseModel):
    observation_id: int
    file_type: str
    processing_status: str
    run: Optional[AnalysisRunResponse] = None
    image_detections: List[ImageDetectionResponse] = []
    audio_classifications: List[AudioClassificationResponse] = []
    # Stated on every response so consumers cannot mistake a coarse label for a
    # species identification.
    interpretation: dict


class AnalysisQueuedResponse(BaseModel):
    queued: int
    observation_ids: List[int]
    detail: str
