"""Assembles the inputs ecosystem/scoring.py's formulas need, from the
biodiversity, habitat and population modules -- the composition step, kept
separate from the pure formulas so both ecosystem/router.py and
conservation/router.py can reuse it without importing each other's routers.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.analytics.trend import linear_trend
from app.modules.biodiversity import indices as biodiversity_indices
from app.modules.biodiversity import queries as biodiversity_queries
from app.modules.ecosystem import scoring
from app.modules.habitat import queries as habitat_queries
from app.modules.population import queries as population_queries


def health_for_site(db: Session, site_id: Optional[int]) -> dict:
    abundances, _excluded = biodiversity_queries.species_abundances(db, site_id=site_id)
    diversity = biodiversity_indices.compute(abundances)
    bio_score = scoring.biodiversity_score(diversity["shannon_index"], diversity["pielou_evenness"])

    habitat_score = None
    if site_id is not None:
        history = habitat_queries.assessment_history(db, site_id)
        if history:
            latest = history[-1]
            trend = linear_trend([(a.assessed_at.timestamp(), a.vegetation_index) for a in history])
            degradation_significant = trend["direction"] == "decreasing"
            habitat_score = scoring.habitat_quality_score(latest.vegetation_index, degradation_significant)

    directions = [
        linear_trend([
            (survey_date.toordinal(), count)
            for survey_date, count in population_queries.survey_series_by_species(db, site_id, species.id)
        ])["direction"]
        for species in population_queries.species_in_scope(db, site_id)
    ]
    pop_score = scoring.population_stability_score(directions)

    overall = scoring.overall_ecosystem_health_score(bio_score, habitat_score, pop_score)

    return {
        "site_id": site_id,
        "biodiversity_score": bio_score,
        "habitat_quality_score": habitat_score,
        "population_stability_score": pop_score,
        **overall,
        "inputs": {
            "species_richness": diversity["species_richness"],
            "shannon_index": diversity["shannon_index"],
            "pielou_evenness": diversity["pielou_evenness"],
            "species_with_trend_data": len(directions),
        },
    }
