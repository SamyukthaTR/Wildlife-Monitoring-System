"""Database queries feeding the population intelligence engine.

Time axis is `Survey.survey_date`, not `ObservationLog.uploaded_at`:
`uploaded_at` is when a file entered this platform, which can lag the actual
fieldwork by years for the seeded historical corpus (see
scripts/seed_dataset.py). `survey_date` is when the animal was actually
observed, so every query here buckets by it.

Counting unit is one detected animal in one frame, the same unit
biodiversity/queries.py uses, with the same exclusions: unknown detections and
coarse-rank labels are dropped because neither can be attributed to a species.
Audio classifications are excluded entirely -- an acoustic event carries no
simultaneous-individual-count signal the way a frame full of animals does.
"""

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.analysis.models import ImageDetection
from app.modules.monitoring.models import MonitoringSite, Survey
from app.modules.observations.models import ObservationLog
from app.modules.species.models import Species, TaxonRankEnum


def _scoped_species_detections(db: Session, site_id: Optional[int], species_id: Optional[int]):
    query = (
        db.query(ImageDetection, Species, Survey)
        .join(Species, ImageDetection.species_id == Species.id)
        .join(ObservationLog, ImageDetection.observation_id == ObservationLog.id)
        .join(Survey, ObservationLog.survey_id == Survey.id)
        .filter(ImageDetection.is_unknown.is_(False), Species.rank == TaxonRankEnum.SPECIES)
    )
    if site_id is not None:
        query = query.filter(Survey.site_id == site_id)
    if species_id is not None:
        query = query.filter(Species.id == species_id)
    return query


def species_in_scope(db: Session, site_id: Optional[int] = None) -> list[Species]:
    """Species with at least one species-level detection in scope."""
    ids = {
        row[0] for row in
        _scoped_species_detections(db, site_id, None).with_entities(Species.id).distinct()
    }
    if not ids:
        return []
    return (
        db.query(Species)
        .filter(Species.id.in_(ids))
        .order_by(Species.scientific_name)
        .all()
    )


def frame_counts_by_species(db: Session, site_id: Optional[int], species_id: int) -> list[int]:
    """Per-frame detection counts for one species -- one count per observation."""
    rows = (
        _scoped_species_detections(db, site_id, species_id)
        .with_entities(ImageDetection.observation_id, func.count(ImageDetection.id))
        .group_by(ImageDetection.observation_id)
        .all()
    )
    return [count for _obs_id, count in rows]


def survey_series_by_species(
    db: Session, site_id: Optional[int], species_id: int
) -> list[tuple]:
    """(survey_date, detection_count) pairs for one species, ordered by date."""
    rows = (
        _scoped_species_detections(db, site_id, species_id)
        .with_entities(Survey.survey_date, func.count(ImageDetection.id))
        .group_by(Survey.survey_date)
        .order_by(Survey.survey_date)
        .all()
    )
    return [(survey_date, count) for survey_date, count in rows]


def survey_peak_counts_by_species(
    db: Session, site_id: Optional[int], species_id: int
) -> list[int]:
    """Per-survey peak simultaneous count: the max single-frame count within that survey."""
    rows = (
        _scoped_species_detections(db, site_id, species_id)
        .with_entities(Survey.id, ImageDetection.observation_id, func.count(ImageDetection.id))
        .group_by(Survey.id, ImageDetection.observation_id)
        .all()
    )
    per_survey: dict[int, int] = {}
    for survey_id, _obs_id, count in rows:
        per_survey[survey_id] = max(per_survey.get(survey_id, 0), count)
    return list(per_survey.values())


def species_detection_count(db: Session, site_id: Optional[int], species_id: int) -> int:
    return _scoped_species_detections(db, site_id, species_id).count()


def observation_effort(db: Session, site_id: Optional[int]) -> int:
    """Total observations in scope -- the effort denominator for encounter rate."""
    query = db.query(ObservationLog).join(Survey, ObservationLog.survey_id == Survey.id)
    if site_id is not None:
        query = query.filter(Survey.site_id == site_id)
    return query.count()


def distribution_by_month(db: Session, site_id: Optional[int]) -> list[dict]:
    """species x site x month presence, for the distribution/migration view."""
    query = (
        db.query(
            Species.id, Species.scientific_name, Species.common_name,
            MonitoringSite.id, MonitoringSite.location_name,
            func.extract('year', Survey.survey_date),
            func.extract('month', Survey.survey_date),
            func.count(ImageDetection.id),
        )
        .join(ImageDetection, ImageDetection.species_id == Species.id)
        .join(ObservationLog, ImageDetection.observation_id == ObservationLog.id)
        .join(Survey, ObservationLog.survey_id == Survey.id)
        .join(MonitoringSite, Survey.site_id == MonitoringSite.id)
        .filter(ImageDetection.is_unknown.is_(False), Species.rank == TaxonRankEnum.SPECIES)
    )
    if site_id is not None:
        query = query.filter(MonitoringSite.id == site_id)
    rows = query.group_by(
        Species.id, Species.scientific_name, Species.common_name,
        MonitoringSite.id, MonitoringSite.location_name,
        func.extract('year', Survey.survey_date), func.extract('month', Survey.survey_date),
    ).all()

    return [
        {
            "species_id": species_id_,
            "scientific_name": scientific_name,
            "common_name": common_name,
            "site_id": site_id_,
            "location_name": location_name,
            "year": int(year),
            "month": int(month),
            "detections": count,
        }
        for species_id_, scientific_name, common_name, site_id_, location_name, year, month, count
        in rows
    ]
