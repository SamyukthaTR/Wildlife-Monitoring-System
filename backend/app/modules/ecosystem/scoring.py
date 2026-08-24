"""Ecosystem health scoring.

Four component scores, each 0-100, each derived from a documented formula over
numbers this platform has already computed elsewhere (biodiversity indices,
population trends, habitat vegetation index). None is a trained model. Each
component is null when its inputs are missing, and
`overall_ecosystem_health_score` requires at least
`MIN_COMPONENTS_FOR_OVERALL` of the three components before it computes
anything -- averaging whatever happens to be non-null would let a site with
one lucky component look as confidently scored as a site with full data,
which this platform's founding rule (never assert more than the data
supports) forbids. See biodiversity/indices.py's `_empty()` for the same
discipline applied at the community level.
"""

from typing import Optional

MIN_COMPONENTS_FOR_OVERALL = 2

# Reference Shannon diversity used to normalise onto 0-100. Not a hard
# ecological ceiling -- just a fixed denominator so the score is comparable
# across scopes. ln(20) ~= 3.0 covers a genuinely diverse assemblage without
# most real sites saturating the scale.
SHANNON_REFERENCE = 3.0

# Habitat quality is discounted, not zeroed, when degradation is significant:
# a declining-but-still-vegetated site is not the same as a bare one.
DEGRADATION_PENALTY_FACTOR = 0.7

OVERALL_WEIGHTS = {
    "biodiversity_score": 0.35,
    "habitat_quality_score": 0.30,
    "population_stability_score": 0.35,
}


def biodiversity_score(
    shannon_index: Optional[float], pielou_evenness: Optional[float]
) -> Optional[float]:
    """0-100 from Shannon diversity (normalised) and evenness, equally weighted."""
    parts = []
    if shannon_index is not None:
        parts.append(min(1.0, shannon_index / SHANNON_REFERENCE))
    if pielou_evenness is not None:
        parts.append(pielou_evenness)
    if not parts:
        return None
    return round(sum(parts) / len(parts) * 100, 1)


def habitat_quality_score(
    vegetation_index: Optional[float], degradation_significant: Optional[bool]
) -> Optional[float]:
    """0-100 from vegetation greenness, discounted for a significant decline."""
    if vegetation_index is None:
        return None
    score = vegetation_index * 100
    if degradation_significant:
        score *= DEGRADATION_PENALTY_FACTOR
    return round(max(0.0, min(100.0, score)), 1)


def population_stability_score(trend_directions: list[str]) -> Optional[float]:
    """0-100 from the share of species trending stable/increasing vs declining.

    `trend_directions` is one direction string per species
    (app/analytics/trend.py's output). Species with "insufficient evidence"
    are excluded from the denominator entirely rather than counted against
    stability -- absence of proof is not evidence of decline.
    """
    counted = [d for d in trend_directions if d != "insufficient evidence"]
    if not counted:
        return None
    favourable = sum(1 for d in counted if d in ("stable", "increasing"))
    return round(favourable / len(counted) * 100, 1)


def overall_ecosystem_health_score(
    biodiversity: Optional[float],
    habitat_quality: Optional[float],
    population_stability: Optional[float],
) -> dict:
    components = {
        "biodiversity_score": biodiversity,
        "habitat_quality_score": habitat_quality,
        "population_stability_score": population_stability,
    }
    available = {key: value for key, value in components.items() if value is not None}

    if len(available) < MIN_COMPONENTS_FOR_OVERALL:
        return {
            "overall_ecosystem_health_score": None,
            "band": None,
            "computed_from": list(available.keys()),
            "note": (
                f"Needs at least {MIN_COMPONENTS_FOR_OVERALL} of "
                f"{len(components)} component scores; only {len(available)} "
                "available."
            ),
        }

    total_weight = sum(OVERALL_WEIGHTS[key] for key in available)
    score = sum(OVERALL_WEIGHTS[key] * value for key, value in available.items()) / total_weight

    return {
        "overall_ecosystem_health_score": round(score, 1),
        "band": _band(score),
        "computed_from": list(available.keys()),
        "note": (
            f"Weighted mean of {list(available.keys())}, renormalised over the "
            "components actually available."
        ),
    }


def _band(score: float) -> str:
    if score >= 75:
        return "Good"
    if score >= 50:
        return "Fair"
    if score >= 25:
        return "Poor"
    return "Critical"
