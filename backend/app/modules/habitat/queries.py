"""Queries feeding habitat intelligence.

Vegetation/degradation figures come from `habitat_assessments`, an append-only
table of real pixel-derived measurements (see app/ml/vegetation.py and
POST /habitat/assess-site/{id}). Environmental data comes from
`environmental_readings`, populated only by scripts/fetch_environment.py --
this module never calls the weather API itself, so a habitat page load never
depends on outbound network reachability.
"""

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.analysis.models import ImageDetection
from app.modules.habitat.models import EnvironmentalReading, HabitatAssessment
from app.modules.monitoring.models import MonitoringSite, Survey
from app.modules.observations.models import ObservationLog
from app.modules.species.models import Species


def assessment_history(db: Session, site_id: int) -> list[HabitatAssessment]:
    return (
        db.query(HabitatAssessment)
        .filter(HabitatAssessment.site_id == site_id)
        .order_by(HabitatAssessment.assessed_at)
        .all()
    )


def latest_assessment(db: Session, site_id: int) -> Optional[HabitatAssessment]:
    return (
        db.query(HabitatAssessment)
        .filter(HabitatAssessment.site_id == site_id)
        .order_by(HabitatAssessment.assessed_at.desc())
        .first()
    )


def sites_with_assessments(db: Session) -> list[MonitoringSite]:
    return (
        db.query(MonitoringSite)
        .join(HabitatAssessment, HabitatAssessment.site_id == MonitoringSite.id)
        .distinct()
        .order_by(MonitoringSite.id)
        .all()
    )


def environmental_readings(db: Session, site_id: int) -> list[EnvironmentalReading]:
    return (
        db.query(EnvironmentalReading)
        .filter(EnvironmentalReading.site_id == site_id)
        .order_by(EnvironmentalReading.recorded_date)
        .all()
    )


def environmental_summary(db: Session, site_id: int) -> dict:
    row = (
        db.query(
            func.avg(EnvironmentalReading.temperature_c),
            func.avg(EnvironmentalReading.humidity_pct),
            func.avg(EnvironmentalReading.precipitation_mm),
            func.avg(EnvironmentalReading.wind_speed_kmh),
            func.count(EnvironmentalReading.id),
        )
        .filter(EnvironmentalReading.site_id == site_id)
        .first()
    )
    avg_temp, avg_humidity, avg_precip, avg_wind, count = row
    if not count:
        return {
            "readings": 0,
            "mean_temperature_c": None,
            "mean_humidity_pct": None,
            "mean_precipitation_mm": None,
            "mean_wind_speed_kmh": None,
        }
    return {
        "readings": count,
        "mean_temperature_c": round(avg_temp, 1) if avg_temp is not None else None,
        "mean_humidity_pct": round(avg_humidity, 1) if avg_humidity is not None else None,
        "mean_precipitation_mm": round(avg_precip, 2) if avg_precip is not None else None,
        "mean_wind_speed_kmh": round(avg_wind, 1) if avg_wind is not None else None,
    }


def species_group_counts(db: Session, site_id: int) -> dict[str, int]:
    """Detections at this site grouped by species_group -- corroborates the
    vegetation-based habitat signal (e.g. a wetland presence signature)."""
    rows = (
        db.query(Species.species_group, func.count(ImageDetection.id))
        .join(ImageDetection, ImageDetection.species_id == Species.id)
        .join(ObservationLog, ImageDetection.observation_id == ObservationLog.id)
        .join(Survey, ObservationLog.survey_id == Survey.id)
        .filter(Survey.site_id == site_id, ImageDetection.is_unknown.is_(False))
        .group_by(Species.species_group)
        .all()
    )
    return {group.value: count for group, count in rows}
