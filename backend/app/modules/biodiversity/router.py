from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.modules.biodiversity import indices, queries
from app.modules.monitoring.models import MonitoringSite, Survey
from app.modules.users.models import User

router = APIRouter(prefix="/biodiversity", tags=["biodiversity"])

METHOD_NOTE = (
    "One detected animal in one frame is one observation of that species. "
    "Shannon H' = -sum(p ln p); Simpson D = sum(p^2); Pielou J' = H'/ln(S). "
    "Evenness is null for a single species and all indices are null when nothing "
    "has been detected -- zeros would misrepresent an unsurveyed scope."
)


def _scope_label(db: Session, site_id: Optional[int], survey_id: Optional[int]) -> dict:
    if survey_id is not None:
        survey = db.query(Survey).filter(Survey.id == survey_id).first()
        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")
        return {"type": "survey", "id": survey_id}
    if site_id is not None:
        site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
        if not site:
            raise HTTPException(status_code=404, detail="Monitoring site not found")
        return {"type": "site", "id": site_id, "name": site.location_name}
    return {"type": "all", "id": None}


@router.get("/indices")
def biodiversity_indices(
    site_id: Optional[int] = Query(None),
    survey_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Diversity indices for a survey, a site, or the whole platform."""
    scope = _scope_label(db, site_id, survey_id)
    abundances, excluded = queries.species_abundances(db, site_id, survey_id)

    result = indices.compute(abundances)
    result.update({
        "scope": scope,
        "excluded_from_indices": excluded,
        "observations": queries.observation_counts(db, site_id, survey_id),
        "method": METHOD_NOTE,
    })
    return result


@router.get("/composition")
def species_composition(
    site_id: Optional[int] = Query(None),
    survey_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Species list with relative abundance, most abundant first."""
    scope = _scope_label(db, site_id, survey_id)
    abundances, excluded = queries.species_abundances(db, site_id, survey_id)
    return {
        "scope": scope,
        "composition": indices.composition(abundances),
        "excluded_from_composition": excluded,
    }


@router.get("/acoustic")
def acoustic_activity(
    site_id: Optional[int] = Query(None),
    survey_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Acoustic detections by sound type, and how much was filtered as noise."""
    scope = _scope_label(db, site_id, survey_id)
    return {"scope": scope, **queries.acoustic_activity(db, site_id, survey_id)}


@router.get("/sites")
def per_site_indices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Indices for every site, for side-by-side comparison."""
    results = []
    for site in queries.sites_with_surveys(db):
        abundances, excluded = queries.species_abundances(db, site_id=site.id)
        computed = indices.compute(abundances)
        coordinates = db.query(
            func.ST_X(MonitoringSite.geom), func.ST_Y(MonitoringSite.geom)
        ).filter(MonitoringSite.id == site.id).first()
        results.append({
            "site_id": site.id,
            "location_name": site.location_name,
            "habitat_type": site.habitat_type,
            "longitude": coordinates[0] if coordinates else None,
            "latitude": coordinates[1] if coordinates else None,
            "observations": queries.observation_counts(db, site_id=site.id)["total"],
            **computed,
            "excluded_from_indices": excluded,
        })
    results.sort(key=lambda r: (r["species_richness"], r["total_detections"]), reverse=True)
    return {"sites": results, "method": METHOD_NOTE}
