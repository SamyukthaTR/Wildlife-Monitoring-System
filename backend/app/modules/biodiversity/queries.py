"""Abundance queries feeding the biodiversity indices.

The counting unit is one detected animal in one frame. Two exclusions, both
deliberate and both reported alongside the numbers:

  * unknown detections -- an animal was seen but not identified, so it cannot be
    attributed to a species
  * coarse-rank labels -- "bird", "Insect", "Bird vocalization" name a group or
    a sound type. Counting them as species would inflate richness with entries
    that are not species at all.
"""

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.analysis.models import AudioClassification, ImageDetection
from app.modules.monitoring.models import MonitoringSite, Survey
from app.modules.observations.models import ObservationLog
from app.modules.species.models import Species, TaxonRankEnum


def _scoped_detections(db: Session, site_id: Optional[int], survey_id: Optional[int]):
    """ImageDetection joined to Species, filtered to the requested scope."""
    query = (
        db.query(ImageDetection, Species)
        .join(Species, ImageDetection.species_id == Species.id)
        .join(ObservationLog, ImageDetection.observation_id == ObservationLog.id)
        .join(Survey, ObservationLog.survey_id == Survey.id)
    )
    if survey_id is not None:
        query = query.filter(Survey.id == survey_id)
    if site_id is not None:
        query = query.filter(Survey.site_id == site_id)
    return query


def species_abundances(
    db: Session, site_id: Optional[int] = None, survey_id: Optional[int] = None
) -> tuple[dict[str, int], dict]:
    """{species_name: count} for species-rank detections, plus what was excluded."""
    rows = (
        _scoped_detections(db, site_id, survey_id)
        .filter(
            ImageDetection.is_unknown.is_(False),
            Species.rank == TaxonRankEnum.SPECIES,
        )
        .with_entities(
            func.coalesce(Species.common_name, Species.scientific_name),
            func.count(ImageDetection.id),
        )
        .group_by(func.coalesce(Species.common_name, Species.scientific_name))
        .all()
    )
    abundances = {name: count for name, count in rows}

    coarse = (
        _scoped_detections(db, site_id, survey_id)
        .filter(
            ImageDetection.is_unknown.is_(False),
            Species.rank != TaxonRankEnum.SPECIES,
        )
        .count()
    )

    unknown_query = (
        db.query(ImageDetection)
        .join(ObservationLog, ImageDetection.observation_id == ObservationLog.id)
        .join(Survey, ObservationLog.survey_id == Survey.id)
        .filter(ImageDetection.is_unknown.is_(True))
    )
    if survey_id is not None:
        unknown_query = unknown_query.filter(Survey.id == survey_id)
    if site_id is not None:
        unknown_query = unknown_query.filter(Survey.site_id == site_id)

    excluded = {
        "coarse_rank_detections": coarse,
        "unidentified_detections": unknown_query.count(),
        "acoustic_detections": acoustic_activity(db, site_id, survey_id)["biological_events"],
        "reason": (
            "Coarse-rank labels name an animal group or sound type, not a "
            "species. Unidentified detections found an animal the classifier "
            "would not name. Acoustic detections are never species-level. All "
            "three are excluded from the indices and reported here instead."
        ),
    }
    return abundances, excluded


def acoustic_activity(
    db: Session, site_id: Optional[int] = None, survey_id: Optional[int] = None
) -> dict:
    """Acoustic detections summarised by sound type, kept apart from the indices."""
    query = (
        db.query(AudioClassification)
        .join(ObservationLog, AudioClassification.observation_id == ObservationLog.id)
        .join(Survey, ObservationLog.survey_id == Survey.id)
    )
    if survey_id is not None:
        query = query.filter(Survey.id == survey_id)
    if site_id is not None:
        query = query.filter(Survey.site_id == site_id)

    biological = query.filter(AudioClassification.is_noise.is_(False))
    rows = (
        biological.with_entities(
            AudioClassification.label_raw, func.count(AudioClassification.id)
        )
        .group_by(AudioClassification.label_raw)
        .order_by(func.count(AudioClassification.id).desc())
        .all()
    )
    return {
        "biological_events": biological.count(),
        "filtered_noise_events": query.filter(AudioClassification.is_noise.is_(True)).count(),
        "by_label": [{"label": label, "count": count} for label, count in rows],
        "note": (
            "AudioSet labels identify a sound type, not a species, so these are "
            "reported as acoustic activity rather than folded into diversity "
            "indices."
        ),
    }


def observation_counts(
    db: Session, site_id: Optional[int] = None, survey_id: Optional[int] = None
) -> dict:
    query = db.query(ObservationLog).join(Survey, ObservationLog.survey_id == Survey.id)
    if survey_id is not None:
        query = query.filter(Survey.id == survey_id)
    if site_id is not None:
        query = query.filter(Survey.site_id == site_id)

    by_status = dict(
        query.with_entities(ObservationLog.processing_status, func.count(ObservationLog.id))
        .group_by(ObservationLog.processing_status)
        .all()
    )
    return {"total": query.count(), "by_processing_status": by_status}


def sites_with_surveys(db: Session):
    """Sites that have at least one survey, for per-site comparisons."""
    return (
        db.query(MonitoringSite)
        .join(Survey, Survey.site_id == MonitoringSite.id)
        .distinct()
        .order_by(MonitoringSite.id)
        .all()
    )
