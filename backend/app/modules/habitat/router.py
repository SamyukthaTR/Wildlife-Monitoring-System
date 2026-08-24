"""Habitat Intelligence.

Vegetation and canopy metrics come from real pixels of already-uploaded
camera-trap images (app/ml/vegetation.py) via POST /habitat/assess-site,
stored append-only in habitat_assessments so repeated runs build a real trend.
Environmental readings come only from scripts/fetch_environment.py -- this
router never calls the weather API itself. Classification and suitability are
transparent heuristics (app/modules/habitat/classify.py), not trained models.
"""

import os
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from PIL import Image
from sqlalchemy.orm import Session

from app.analytics.trend import linear_trend
from app.core.deps import RoleChecker, get_current_user, get_db
from app.ml import vegetation
from app.modules.habitat import queries
from app.modules.habitat.classify import classify_habitat_signal, suitability_score
from app.modules.habitat.models import HabitatAssessment
from app.modules.monitoring.models import MonitoringSite, Survey
from app.modules.observations.models import FileTypeEnum, ObservationLog
from app.modules.users.models import User

router = APIRouter(prefix="/habitat", tags=["habitat"])

assess_roles = RoleChecker(['Wildlife Researcher', 'Conservation Officer', 'Administrator'])

ENV_NOTE = (
    "Environmental readings are modelled ERA5 historical reanalysis for this "
    "site's coordinates (Open-Meteo archive), not a field sensor -- populated "
    "only by scripts/fetch_environment.py."
)
DEGRADATION_NOTE = (
    "Flagged only when the vegetation index shows a statistically significant "
    "decline across assessments -- a single assessment cannot show "
    "degradation, only a repeated one can."
)


def _get_site(db: Session, site_id: int) -> MonitoringSite:
    site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Monitoring site not found")
    return site


def _serialize_assessment(assessment: HabitatAssessment) -> dict:
    return {
        "id": assessment.id,
        "site_id": assessment.site_id,
        "assessed_at": assessment.assessed_at.isoformat(),
        "images_sampled": assessment.images_sampled,
        "vegetation_index": assessment.vegetation_index,
        "green_pixel_fraction": assessment.green_pixel_fraction,
        "canopy_texture_index": assessment.canopy_texture_index,
        "declared_habitat_type": assessment.declared_habitat_type,
        "inferred_habitat_signal": assessment.inferred_habitat_signal,
    }


def _vegetation_trend(history: list[HabitatAssessment]) -> dict:
    return linear_trend([(a.assessed_at.timestamp(), a.vegetation_index) for a in history])


@router.post("/assess-site/{site_id}")
def assess_site(
    site_id: int,
    limit: int = Query(50, ge=1, le=200, description="Most recent image observations to sample"),
    db: Session = Depends(get_db),
    current_user: User = Depends(assess_roles),
):
    """Compute vegetation metrics from this site's real uploaded images.

    Samples up to `limit` image observations (most recent first), averages the
    per-image vegetation metrics, and appends one new assessment row -- it
    never overwrites a previous one, so degradation trend detection has real
    history to work with.
    """
    site = _get_site(db, site_id)

    observations = (
        db.query(ObservationLog)
        .join(Survey, ObservationLog.survey_id == Survey.id)
        .filter(Survey.site_id == site_id, ObservationLog.file_type == FileTypeEnum.IMAGE)
        .order_by(ObservationLog.uploaded_at.desc())
        .limit(limit)
        .all()
    )
    if not observations:
        raise HTTPException(status_code=400, detail="No image observations at this site to assess.")

    metrics = []
    for observation in observations:
        if not os.path.exists(observation.storage_path):
            continue
        try:
            image = Image.open(observation.storage_path).convert("RGB")
        except Exception:  # noqa: BLE001 - a corrupt/unreadable file is skipped, not fatal
            continue
        metrics.append(vegetation.assess(np.array(image)))

    if not metrics:
        raise HTTPException(
            status_code=400,
            detail="None of this site's image files could be read from disk.",
        )

    avg_vegetation = sum(m["vegetation_index"] for m in metrics) / len(metrics)
    avg_green = sum(m["green_pixel_fraction"] for m in metrics) / len(metrics)
    avg_texture = sum(m["canopy_texture_index"] for m in metrics) / len(metrics)

    group_counts = queries.species_group_counts(db, site_id)
    signal = classify_habitat_signal(avg_vegetation, group_counts)

    assessment = HabitatAssessment(
        site_id=site_id,
        images_sampled=len(metrics),
        vegetation_index=round(avg_vegetation, 4),
        green_pixel_fraction=round(avg_green, 4),
        canopy_texture_index=round(avg_texture, 4),
        declared_habitat_type=site.habitat_type,
        inferred_habitat_signal=signal,
        created_by=current_user.id,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    return {
        **_serialize_assessment(assessment),
        "images_at_site": len(observations),
        "images_unreadable": len(observations) - len(metrics),
    }


@router.get("/sites")
def habitat_sites(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Latest habitat assessment for every assessed site, with degradation trend."""
    results = []
    for site in queries.sites_with_assessments(db):
        history = queries.assessment_history(db, site.id)
        latest = history[-1]
        trend = _vegetation_trend(history)
        results.append({
            "site_id": site.id,
            "location_name": site.location_name,
            "assessments": len(history),
            **_serialize_assessment(latest),
            "vegetation_trend": trend,
            "degradation_flag": trend["direction"] == "decreasing",
        })
    return {"sites": results, "note": DEGRADATION_NOTE}


@router.get("/environment")
def environment(
    site_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    site = _get_site(db, site_id)
    readings = queries.environmental_readings(db, site_id)
    summary = queries.environmental_summary(db, site_id)

    if not readings:
        return {
            "site_id": site_id,
            "location_name": site.location_name,
            "readings": [],
            **summary,
            "note": (
                "No environmental readings recorded for this site. Run "
                "`python -m scripts.fetch_environment` after seeding real "
                "site coordinates and surveys. " + ENV_NOTE
            ),
        }

    return {
        "site_id": site_id,
        "location_name": site.location_name,
        "readings": [
            {
                "recorded_date": reading.recorded_date.isoformat(),
                "temperature_c": reading.temperature_c,
                "humidity_pct": reading.humidity_pct,
                "precipitation_mm": reading.precipitation_mm,
                "wind_speed_kmh": reading.wind_speed_kmh,
            }
            for reading in readings
        ],
        **summary,
        "note": ENV_NOTE,
    }


@router.get("/suitability")
def suitability(
    site_id: int = Query(...),
    species_group: str = Query(..., description="mammal|bird|reptile|amphibian|insect|marine|other"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    site = _get_site(db, site_id)
    latest = queries.latest_assessment(db, site_id)
    vegetation_index = latest.vegetation_index if latest else None

    group_counts = queries.species_group_counts(db, site_id)
    total = sum(group_counts.values())
    group_share = (group_counts.get(species_group, 0) / total) if total else None

    result = suitability_score(vegetation_index, group_share)
    return {
        "site_id": site_id,
        "location_name": site.location_name,
        "species_group": species_group,
        **result,
    }


@router.get("/{site_id}")
def habitat_detail(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    site = _get_site(db, site_id)
    history = queries.assessment_history(db, site_id)
    if not history:
        return {
            "site_id": site_id,
            "location_name": site.location_name,
            "declared_habitat_type": site.habitat_type,
            "assessments": [],
            "note": "No habitat assessment yet. POST /habitat/assess-site/{id} to compute one.",
        }

    trend = _vegetation_trend(history)
    return {
        "site_id": site_id,
        "location_name": site.location_name,
        "declared_habitat_type": site.habitat_type,
        "assessments": [_serialize_assessment(a) for a in history],
        "vegetation_trend": trend,
        "degradation_flag": trend["direction"] == "decreasing",
        "note": DEGRADATION_NOTE,
    }
