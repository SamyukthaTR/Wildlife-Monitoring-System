"""Conservation recommendation workflows -- see engine.py for the rule logic
and how each recommendation's rationale is tied to a real computed number.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analytics.trend import linear_trend
from app.core.deps import get_current_user, get_db
from app.modules.analysis.models import ImageDetection
from app.modules.biodiversity import queries as biodiversity_queries
from app.modules.conservation.engine import recommend
from app.modules.ecosystem.service import health_for_site
from app.modules.habitat import queries as habitat_queries
from app.modules.monitoring.models import MonitoringSite, Survey
from app.modules.observations.models import ObservationLog
from app.modules.population import queries as population_queries
from app.modules.species.models import Species
from app.modules.users.models import User

router = APIRouter(prefix="/conservation", tags=["conservation"])

NOTE = (
    "Deterministic rule-based recommendations, not AI-generated. Each "
    "rationale cites the number that triggered it -- check it against "
    "/ecosystem/health, /population/trends and /habitat/{id} for the "
    "underlying data."
)


def _endangered_species_at_site(db: Session, site_id: int) -> list[dict]:
    rows = (
        db.query(Species)
        .join(ImageDetection, ImageDetection.species_id == Species.id)
        .join(ObservationLog, ImageDetection.observation_id == ObservationLog.id)
        .join(Survey, ObservationLog.survey_id == Survey.id)
        .filter(Survey.site_id == site_id, Species.is_endangered.is_(True))
        .distinct()
        .all()
    )
    return [
        {"scientific_name": s.scientific_name, "common_name": s.common_name, "iucn_status": s.iucn_status}
        for s in rows
    ]


def _declining_species_at_site(db: Session, site_id: int) -> list[dict]:
    declining = []
    for species in population_queries.species_in_scope(db, site_id):
        series = population_queries.survey_series_by_species(db, site_id, species.id)
        points = [(survey_date.toordinal(), count) for survey_date, count in series]
        trend = linear_trend(points)
        if trend["direction"] == "decreasing":
            declining.append({"scientific_name": species.scientific_name})
    return declining


def _site_inputs(db: Session, site: MonitoringSite) -> dict:
    health = health_for_site(db, site.id)
    effort = biodiversity_queries.observation_counts(db, site_id=site.id)["total"]

    habitat_history = habitat_queries.assessment_history(db, site.id)
    vegetation_trend = None
    degradation_significant = None
    if habitat_history:
        vegetation_trend = linear_trend(
            [(a.assessed_at.timestamp(), a.vegetation_index) for a in habitat_history]
        )
        degradation_significant = vegetation_trend["direction"] == "decreasing"

    return {
        "site_id": site.id,
        "location_name": site.location_name,
        "overall_health": health["overall_ecosystem_health_score"],
        "health_band": health.get("band"),
        "health_computed_from": health.get("computed_from"),
        "species_richness": health["inputs"]["species_richness"],
        "endangered_species": _endangered_species_at_site(db, site.id),
        "declining_species": _declining_species_at_site(db, site.id),
        "habitat_degradation_significant": degradation_significant,
        "vegetation_trend": vegetation_trend,
        "observation_effort": effort,
    }


@router.get("/recommendations")
def recommendations(
    site_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rule-based recommendations for one site, or every site with any."""
    if site_id is not None:
        site = db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
        if not site:
            raise HTTPException(status_code=404, detail="Monitoring site not found")
        sites = [site]
    else:
        sites = db.query(MonitoringSite).order_by(MonitoringSite.id).all()

    results = []
    for site in sites:
        inputs = _site_inputs(db, site)
        site_recommendations = recommend(inputs)
        if site_recommendations:
            results.append({
                "site_id": site.id,
                "location_name": site.location_name,
                "recommendations": site_recommendations,
            })

    return {"sites": results, "note": NOTE}


@router.get("/priorities")
def priorities(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Every site ranked by how many high-priority flags it carries."""
    sites = db.query(MonitoringSite).order_by(MonitoringSite.id).all()
    ranked = []
    for site in sites:
        inputs = _site_inputs(db, site)
        site_recommendations = recommend(inputs)
        high_priority = sum(1 for r in site_recommendations if r["priority"] == "high")
        ranked.append({
            "site_id": site.id,
            "location_name": site.location_name,
            "overall_health": inputs["overall_health"],
            "high_priority_flags": high_priority,
            "total_recommendations": len(site_recommendations),
        })

    ranked.sort(
        key=lambda r: (
            -r["high_priority_flags"],
            r["overall_health"] if r["overall_health"] is not None else 1000,
        )
    )
    return {"sites": ranked, "note": NOTE}
