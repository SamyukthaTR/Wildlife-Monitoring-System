"""Population Intelligence Engine.

Every number here is derived from detections and survey dates already in the
database. There is no cross-frame individual re-identification anywhere in
this platform (see docs/milestone2.md), so "population estimate" language is
deliberately avoided in favour of what is actually measured: peak counts (a
lower bound, app/modules/population/analytics.py), encounter rates
(effort-normalised, not per unit area), and presence patterns (not confirmed
tracked migration). See queries.py for the survey_date-based time axis and the
same species-rank/unknown exclusions biodiversity/queries.py already applies.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analytics.trend import linear_trend
from app.core.deps import get_current_user, get_db
from app.modules.monitoring.models import MonitoringSite
from app.modules.population import analytics, queries
from app.modules.species.models import Species
from app.modules.users.models import User

router = APIRouter(prefix="/population", tags=["population"])

METHOD_NOTE = (
    "Counting unit is one species-level detection in one frame, bucketed by "
    "Survey.survey_date (the real observation date), not upload time. No "
    "individual animal is tracked across frames, so figures here are peak "
    "counts and encounter rates, never population estimates in the "
    "mark-recapture sense."
)


def _require_site(db: Session, site_id: Optional[int]) -> Optional[MonitoringSite]:
    if site_id is None:
        return None
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Monitoring site not found")
    return site


def _species_scope(
    db: Session, site_id: Optional[int], species_id: Optional[int]
) -> list[Species]:
    if species_id is not None:
        species = db.query(Species).filter(Species.id == species_id).first()
        if not species:
            raise HTTPException(status_code=404, detail="Species not found")
        return [species]
    return queries.species_in_scope(db, site_id)


def _brief(species: Species) -> dict:
    return {
        "species_id": species.id,
        "scientific_name": species.scientific_name,
        "common_name": species.common_name,
        "species_group": species.species_group.value,
    }


@router.get("/estimates")
def population_estimates(
    site_id: Optional[int] = Query(None),
    species_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Peak simultaneous count and observed variability per species."""
    _require_site(db, site_id)
    results = []
    for species in _species_scope(db, site_id, species_id):
        frame_counts = queries.frame_counts_by_species(db, site_id, species.id)
        peak = analytics.peak_simultaneous_count(frame_counts)
        survey_peaks = queries.survey_peak_counts_by_species(db, site_id, species.id)
        variability = analytics.count_variability(survey_peaks)
        results.append({**_brief(species), **peak, "variability": variability})

    results.sort(key=lambda r: r["peak_simultaneous_count"] or 0, reverse=True)
    return {"site_id": site_id, "species": results, "method": METHOD_NOTE}


@router.get("/trends")
def population_trends(
    site_id: Optional[int] = Query(None),
    species_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detection-count trend over survey dates per species."""
    _require_site(db, site_id)
    results = []
    for species in _species_scope(db, site_id, species_id):
        series = queries.survey_series_by_species(db, site_id, species.id)
        points = [(survey_date.toordinal(), count) for survey_date, count in series]
        trend = linear_trend(points)
        results.append({
            **_brief(species),
            "data_points": [
                {"survey_date": survey_date.isoformat(), "count": count}
                for survey_date, count in series
            ],
            "trend": trend,
        })
    return {
        "site_id": site_id,
        "species": results,
        "method": METHOD_NOTE + (
            " Trend slope is fit in detections per day; percent_change_per_period "
            "is normalised by the series mean so it is comparable across species "
            "with different baseline abundances."
        ),
    }


@router.get("/density")
def population_density(
    site_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Effort-normalised encounter rate per species -- not a true area density."""
    _require_site(db, site_id)
    effort = queries.observation_effort(db, site_id)
    results = []
    for species in queries.species_in_scope(db, site_id):
        detections = queries.species_detection_count(db, site_id, species.id)
        rate = round(detections / effort * 100, 3) if effort else None
        results.append({**_brief(species), "detections": detections,
                         "encounter_rate_per_100_observations": rate})

    results.sort(key=lambda r: r["encounter_rate_per_100_observations"] or 0, reverse=True)
    return {
        "site_id": site_id,
        "observation_effort": effort,
        "species": results,
        "is_true_density": False,
        "note": (
            "This is an effort-normalised encounter rate (detections per 100 "
            "observations), not a true area-based density: no monitoring site "
            "in this system records its surveyed area, so a per-km2 figure "
            "cannot be honestly computed."
        ),
    }


@router.get("/distribution")
def population_distribution(
    site_id: Optional[int] = Query(None),
    species_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Species x site x month presence -- the honest version of "migration patterns"."""
    _require_site(db, site_id)
    records = queries.distribution_by_month(db, site_id)
    if species_id is not None:
        records = [r for r in records if r["species_id"] == species_id]

    return {
        "site_id": site_id,
        "records": records,
        "note": (
            "Presence pattern by species, site and month, built from detection "
            "dates. This is NOT confirmed migration tracking: no individual "
            "animal is identified across frames or locations, so an apparent "
            "seasonal shift may reflect survey timing or effort rather than "
            "animal movement."
        ),
    }
