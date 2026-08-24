import json
import os
import statistics
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import RoleChecker, get_current_user, get_db
from app.ml import registry
from app.modules.analysis.models import (
    AnalysisRun,
    AudioClassification,
    ImageDetection,
    RunStatusEnum,
)
from app.modules.analysis.pipeline import STATUS_PENDING, run_analysis
from app.modules.analysis.schemas import (
    AnalysisQueuedResponse,
    AnalysisRunResponse,
    AudioClassificationResponse,
    BoundingBox,
    ImageDetectionResponse,
    ObservationAnalysisResponse,
    SpeciesBrief,
)
from app.modules.observations.models import FileTypeEnum, ObservationLog
from app.modules.species.models import Species, TaxonRankEnum
from app.modules.users.models import User

router = APIRouter(prefix="/analysis", tags=["analysis"])

analyse_roles = RoleChecker(['Wildlife Researcher', 'Conservation Officer', 'Administrator'])
admin_only = RoleChecker(['Administrator'])

MANIFEST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    "scripts", "sample_data", "manifest.json",
)

INTERPRETATION = {
    "detection": (
        "Bounding boxes come from YOLOv8n and locate an animal; the species name "
        "comes from ResNet-50 classifying that crop."
    ),
    "unknown": (
        "is_unknown means an animal was found but classification confidence was "
        "below threshold, so label_raw reads 'unidentified animal'. "
        "detector_label is the COCO class that located the box -- a shape match "
        "against ten classes, not an identification -- and candidate_label is "
        "the classifier's best guess with its actual score. Neither is asserted "
        "as the species."
    ),
    "individual_id": (
        "detection_index identifies an individual within this frame only. "
        "Matching individuals across frames is not attempted."
    ),
    "posture": (
        "posture_hint is derived from bounding-box aspect ratio. It is a "
        "geometric heuristic, not a trained behaviour classifier."
    ),
    "audio": (
        "AudioSet labels name a sound type (bird, insect, frog), never a species. "
        "Acoustic detections are stored at coarse rank and excluded from "
        "species-level diversity indices."
    ),
    "noise": (
        "is_noise marks non-biological sound kept for auditability of the "
        "environmental noise filtering."
    ),
}


def _visible_observation(db: Session, obs_id: int, user: User) -> ObservationLog:
    observation = db.query(ObservationLog).filter(ObservationLog.id == obs_id).first()
    if not observation:
        raise HTTPException(status_code=404, detail="Observation not found")
    if user.role == "Wildlife Researcher" and observation.uploaded_by != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this observation")
    return observation


def _species_brief(species: Optional[Species]) -> Optional[SpeciesBrief]:
    if species is None:
        return None
    return SpeciesBrief(
        id=species.id,
        scientific_name=species.scientific_name,
        common_name=species.common_name,
        rank=species.rank.value,
        species_group=species.species_group.value,
        taxon_class=species.taxon_class,
        iucn_status=species.iucn_status,
        is_endangered=species.is_endangered,
    )


@router.post("/observations/{obs_id}/analyze", response_model=AnalysisQueuedResponse,
             status_code=status.HTTP_202_ACCEPTED)
def analyze_observation(
    obs_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(analyse_roles),
):
    """Queue (or re-queue) one observation for analysis.

    Re-running replaces the previous detections for that observation.
    """
    observation = _visible_observation(db, obs_id, current_user)
    observation.processing_status = STATUS_PENDING
    db.commit()

    background_tasks.add_task(run_analysis, observation.id)
    return AnalysisQueuedResponse(
        queued=1,
        observation_ids=[observation.id],
        detail="Analysis queued. Poll GET /analysis/observations/{id} for the result.",
    )


@router.post("/run-pending", response_model=AnalysisQueuedResponse,
             status_code=status.HTTP_202_ACCEPTED)
def run_pending(
    background_tasks: BackgroundTasks,
    include_failed: bool = Query(True, description="Also retry previously failed runs"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    """Analyse everything not yet processed. Used to process the seeded corpus."""
    statuses = ["pending", "processing"]
    if include_failed:
        statuses.append("failed")

    observations = (
        db.query(ObservationLog)
        .filter(ObservationLog.processing_status.in_(statuses))
        .order_by(ObservationLog.id)
        .limit(limit)
        .all()
    )
    for observation in observations:
        background_tasks.add_task(run_analysis, observation.id)

    return AnalysisQueuedResponse(
        queued=len(observations),
        observation_ids=[o.id for o in observations],
        detail=(
            f"{len(observations)} observation(s) queued. Inference runs on CPU, "
            "so expect a few seconds each."
        ),
    )


@router.get("/observations/{obs_id}", response_model=ObservationAnalysisResponse)
def get_observation_analysis(
    obs_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Everything the engines found for one observation."""
    observation = _visible_observation(db, obs_id, current_user)

    run = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.observation_id == obs_id)
        .order_by(AnalysisRun.id.desc())
        .first()
    )

    image_detections = []
    audio_classifications = []

    if observation.file_type == FileTypeEnum.IMAGE:
        rows = (
            db.query(ImageDetection, Species)
            .outerjoin(Species, ImageDetection.species_id == Species.id)
            .filter(ImageDetection.observation_id == obs_id)
            .order_by(ImageDetection.detection_index)
            .all()
        )
        for detection, species in rows:
            bbox = None
            if detection.bbox_x is not None:
                bbox = BoundingBox(
                    x=detection.bbox_x, y=detection.bbox_y,
                    w=detection.bbox_w, h=detection.bbox_h,
                )
            image_detections.append(ImageDetectionResponse(
                id=detection.id,
                detection_index=detection.detection_index,
                label_raw=detection.label_raw,
                label_source=detection.label_source,
                confidence=detection.confidence,
                detector_label=detection.detector_label,
                candidate_label=detection.candidate_label,
                candidate_confidence=detection.candidate_confidence,
                bbox=bbox,
                posture_hint=detection.posture_hint,
                is_unknown=detection.is_unknown,
                species=_species_brief(species),
            ))
    else:
        rows = (
            db.query(AudioClassification, Species)
            .outerjoin(Species, AudioClassification.species_id == Species.id)
            .filter(AudioClassification.observation_id == obs_id)
            .order_by(AudioClassification.start_time_s, AudioClassification.confidence.desc())
            .all()
        )
        for classification, species in rows:
            audio_classifications.append(AudioClassificationResponse(
                id=classification.id,
                label_raw=classification.label_raw,
                label_source=classification.label_source,
                confidence=classification.confidence,
                start_time_s=classification.start_time_s,
                end_time_s=classification.end_time_s,
                is_noise=classification.is_noise,
                species=_species_brief(species),
            ))

    return ObservationAnalysisResponse(
        observation_id=observation.id,
        file_type=observation.file_type.value,
        processing_status=observation.processing_status,
        run=AnalysisRunResponse.model_validate(run) if run else None,
        image_detections=image_detections,
        audio_classifications=audio_classifications,
        interpretation=INTERPRETATION,
    )


@router.get("/runs", response_model=List[AnalysisRunResponse])
def list_runs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recent analysis runs, newest first."""
    return (
        db.query(AnalysisRun)
        .order_by(AnalysisRun.id.desc())
        .limit(limit)
        .all()
    )


@router.get("/models")
def model_status(current_user: User = Depends(get_current_user)):
    """Which models are loaded in this process, and why any failed.

    Reports only what has already been loaded; it does not trigger a load.
    """
    return registry.status()


@router.get("/metrics")
def recognition_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Measured performance of the recognition engines.

    Accuracy is computed against the seeded corpus's ground truth -- the
    identifications the source databases published, not labels we assigned. It
    is reported at two ranks, separately and honestly:

      * species agreement  -- the classifier named the exact species
      * class agreement    -- the prediction resolved to the right taxonomic
                              class (Mammalia, Aves, ...), which is the most
                              a coarse model can be expected to get right

    Files with no published label (the Snapshot Serengeti frames) and non-animal
    files are excluded from accuracy and counted separately.
    """
    latencies = _latency_metrics(db)
    accuracy = _accuracy_metrics(db)
    return {"latency": latencies, "accuracy": accuracy}


def _latency_metrics(db: Session) -> dict:
    def summarise(file_type: FileTypeEnum) -> dict:
        values = [
            run.latency_ms
            for run in db.query(AnalysisRun)
            .join(ObservationLog, AnalysisRun.observation_id == ObservationLog.id)
            .filter(
                AnalysisRun.status == RunStatusEnum.COMPLETED,
                AnalysisRun.latency_ms.isnot(None),
                ObservationLog.file_type == file_type,
            )
            .with_entities(AnalysisRun)
            .all()
        ]
        if not values:
            return {"samples": 0, "median_ms": None, "p95_ms": None,
                    "min_ms": None, "max_ms": None}
        ordered = sorted(values)
        p95_index = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
        return {
            "samples": len(ordered),
            "median_ms": int(statistics.median(ordered)),
            "p95_ms": ordered[p95_index],
            "min_ms": ordered[0],
            "max_ms": ordered[-1],
        }

    return {
        "image_inference": summarise(FileTypeEnum.IMAGE),
        "audio_processing": summarise(FileTypeEnum.AUDIO),
        "note": "Wall-clock time for the full pipeline per file, CPU inference.",
    }


def _load_ground_truth() -> dict:
    """source_id -> ground truth, from the corpus manifest."""
    if not os.path.exists(MANIFEST_PATH):
        return {}
    try:
        with open(MANIFEST_PATH, encoding="utf-8") as fh:
            records = json.load(fh).get("records", [])
    except (OSError, json.JSONDecodeError):
        return {}
    truths = {}
    for record in records:
        truth = record.get("ground_truth") or {}
        if truth.get("scientific_name"):
            truths[str(record["source_id"])] = truth
    return truths


def _accuracy_metrics(db: Session) -> dict:
    truths = _load_ground_truth()
    if not truths:
        return {
            "evaluated": 0,
            "note": "No corpus manifest available; accuracy cannot be measured.",
        }

    observations = (
        db.query(ObservationLog)
        .filter(ObservationLog.processing_status == "completed")
        .all()
    )

    species_hits = class_hits = evaluated = no_prediction = 0
    unlabelled = 0
    examples = []

    for observation in observations:
        truth = None
        for source_id, candidate in truths.items():
            if source_id in os.path.basename(observation.storage_path):
                truth = candidate
                break
        if truth is None:
            unlabelled += 1
            continue

        predicted = _best_prediction(db, observation)
        evaluated += 1
        if predicted is None:
            no_prediction += 1
            continue

        species_match = bool(
            predicted.get("scientific_name")
            and predicted["scientific_name"].strip().lower()
            == (truth.get("scientific_name") or "").strip().lower()
        )
        class_match = bool(
            predicted.get("taxon_class")
            and truth.get("taxon_class")
            and predicted["taxon_class"].strip().lower()
            == truth["taxon_class"].strip().lower()
        )
        species_hits += species_match
        class_hits += class_match

        if len(examples) < 15:
            examples.append({
                "observation_id": observation.id,
                "expected": truth.get("scientific_name"),
                "expected_class": truth.get("taxon_class"),
                "predicted_label": predicted.get("label_raw"),
                "predicted_species": predicted.get("scientific_name"),
                "predicted_class": predicted.get("taxon_class"),
                "confidence": predicted.get("confidence"),
                "species_match": species_match,
                "class_match": class_match,
            })

    def rate(hits: int) -> Optional[float]:
        return round(hits / evaluated, 4) if evaluated else None

    return {
        "evaluated": evaluated,
        "species_level_agreement": rate(species_hits),
        "class_level_agreement": rate(class_hits),
        "no_prediction": no_prediction,
        "excluded_unlabelled": unlabelled,
        "examples": examples,
        "note": (
            "Ground truth is the source database's own identification. "
            "Species-level agreement is expected to be low: ImageNet-1k contains "
            "about 400 animal classes against millions of real species, and "
            "AudioSet contains none. Class-level agreement is the fair measure "
            "of these models on this task."
        ),
    }


def _best_prediction(db: Session, observation: ObservationLog) -> Optional[dict]:
    """Highest-confidence identification for an observation."""
    if observation.file_type == FileTypeEnum.IMAGE:
        row = (
            db.query(ImageDetection, Species)
            .outerjoin(Species, ImageDetection.species_id == Species.id)
            .filter(
                ImageDetection.observation_id == observation.id,
                ImageDetection.is_unknown.is_(False),
            )
            .order_by(ImageDetection.confidence.desc())
            .first()
        )
    else:
        row = (
            db.query(AudioClassification, Species)
            .outerjoin(Species, AudioClassification.species_id == Species.id)
            .filter(
                AudioClassification.observation_id == observation.id,
                AudioClassification.is_noise.is_(False),
            )
            .order_by(AudioClassification.confidence.desc())
            .first()
        )
    if row is None:
        return None

    detection, species = row
    return {
        "label_raw": detection.label_raw,
        "confidence": detection.confidence,
        "scientific_name": species.scientific_name if species and
        species.rank == TaxonRankEnum.SPECIES else None,
        "taxon_class": species.taxon_class if species else None,
    }
