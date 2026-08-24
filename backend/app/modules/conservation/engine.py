"""Conservation recommendation engine.

A deterministic, rule-based decision-support layer over numbers this platform
has already computed elsewhere (biodiversity indices, population trends,
habitat degradation, ecosystem health, IUCN status). It is explicitly NOT an
AI/ML recommender: there is no training data for "the right conservation
action" to learn from, and presenting rule-based logic as AI-generated would
overstate it, which is exactly what this platform avoids elsewhere (see
docs/milestone2.md). Every recommendation's rationale cites the actual number
that triggered it, so it can be checked against the data behind it.
"""

# Below this many observations, the trend/diversity figures for a site are too
# thin to trust -- flagged as a monitoring gap rather than acted on.
MIN_EFFORT_OBSERVATIONS = 10

# A site with this many species from fewer than this many observations reads
# as under-sampled relative to its apparent diversity.
UNDER_SAMPLED_RICHNESS_THRESHOLD = 5
UNDER_SAMPLED_EFFORT_THRESHOLD = 30

HEALTH_CRITICAL_THRESHOLD = 25
HEALTH_PRIORITY_THRESHOLD = 40


def recommend(inputs: dict) -> list[dict]:
    """Build recommendations from an assembled inputs dict.

    Expected keys (all optional / may be None or empty):
      location_name: str
      overall_health: float | None            -- 0-100, from ecosystem/scoring.py
      health_band: str | None
      health_computed_from: list[str]
      species_richness: int | None
      endangered_species: list[{scientific_name, common_name, iucn_status}]
      declining_species: list[{scientific_name}]  -- already filtered to
        statistically significant decliners (app/analytics/trend.py)
      habitat_degradation_significant: bool | None
      vegetation_trend: dict | None            -- app/analytics/trend.py output
      observation_effort: int | None

    Every branch below only fires when its trigger value is actually present;
    missing inputs produce no recommendation for that category rather than a
    guessed one.
    """
    recommendations = []
    location = inputs.get("location_name") or "This site"

    recommendations.extend(_conservation_priority(inputs, location))
    recommendations.extend(_wildlife_protection(inputs))
    recommendations.extend(_habitat_restoration(inputs))
    recommendations.extend(_monitoring_allocation(inputs))

    return recommendations


def _conservation_priority(inputs: dict, location: str) -> list[dict]:
    overall = inputs.get("overall_health")
    if overall is None or overall >= HEALTH_PRIORITY_THRESHOLD:
        return []
    return [{
        "category": "conservation_priority",
        "priority": "high" if overall < HEALTH_CRITICAL_THRESHOLD else "medium",
        "title": f"{location} needs prioritised conservation attention",
        "rationale": (
            f"Overall ecosystem health score is {overall}/100 "
            f"({inputs.get('health_band', 'unscored')}), computed from "
            f"{inputs.get('health_computed_from', [])}."
        ),
    }]


def _wildlife_protection(inputs: dict) -> list[dict]:
    recommendations = []
    endangered = inputs.get("endangered_species") or []
    if endangered:
        names = ", ".join(species.get("common_name") or species["scientific_name"]
                           for species in endangered[:5])
        recommendations.append({
            "category": "wildlife_protection",
            "priority": "high",
            "title": "IUCN-listed species detected -- protection measures warranted",
            "rationale": (
                f"{len(endangered)} species of conservation concern detected: "
                f"{names}. IUCN status is from a published source, never inferred."
            ),
        })

    declining = inputs.get("declining_species") or []
    endangered_names = {species["scientific_name"] for species in endangered}
    declining_endangered = [d for d in declining if d["scientific_name"] in endangered_names]
    if declining_endangered:
        names = ", ".join(d["scientific_name"] for d in declining_endangered[:5])
        recommendations.append({
            "category": "wildlife_protection",
            "priority": "high",
            "title": "Statistically significant decline in an IUCN-listed species",
            "rationale": (
                f"Declining detection trend for: {names}. Anti-poaching "
                "patrols and nest/den protection are the standard first "
                "response, but this platform detects the decline -- it does "
                "not diagnose the cause; field verification is needed before "
                "acting."
            ),
        })
    return recommendations


def _habitat_restoration(inputs: dict) -> list[dict]:
    if not inputs.get("habitat_degradation_significant"):
        return []
    trend = inputs.get("vegetation_trend") or {}
    return [{
        "category": "habitat_restoration",
        "priority": "medium",
        "title": "Vegetation index shows a significant decline",
        "rationale": (
            f"Vegetation index trend slope {trend.get('slope')} "
            f"(p={trend.get('p_value')}) across {trend.get('n_points')} "
            "assessments. Recommend a field vegetation/canopy survey before "
            "assuming the cause -- this platform detects the decline, it "
            "does not diagnose it."
        ),
    }]


def _monitoring_allocation(inputs: dict) -> list[dict]:
    effort = inputs.get("observation_effort")
    richness = inputs.get("species_richness")

    if effort is not None and effort < MIN_EFFORT_OBSERVATIONS:
        return [{
            "category": "monitoring_allocation",
            "priority": "low",
            "title": "Monitoring effort is too sparse to draw conclusions",
            "rationale": (
                f"Only {effort} observations recorded at this site -- below "
                f"the {MIN_EFFORT_OBSERVATIONS} needed for the trend and "
                "diversity figures above to be trustworthy. Recommend "
                "additional camera-trap/audio-sensor deployment here before "
                "reallocating effort elsewhere."
            ),
        }]

    if (
        richness is not None and richness >= UNDER_SAMPLED_RICHNESS_THRESHOLD
        and effort is not None and effort < UNDER_SAMPLED_EFFORT_THRESHOLD
    ):
        return [{
            "category": "monitoring_allocation",
            "priority": "medium",
            "title": "High species richness relative to monitoring effort",
            "rationale": (
                f"{richness} species detected from only {effort} observations "
                "-- this site is likely under-sampled relative to its "
                "apparent diversity. Recommend increasing monitoring "
                "frequency here."
            ),
        }]

    return []
