"""Habitat signal classification and suitability scoring.

Both are transparent, formula-based heuristics over numbers this platform has
already computed elsewhere (the vegetation index from app/ml/vegetation.py,
and which species groups have actually been detected at a site) -- not a
trained classifier or a trained suitability model. There is no labelled
habitat-type or suitability dataset to train one on, so pretending otherwise
would overstate what this does. Thresholds are stated here so they can be
argued with, the same discipline app/ml/quality.py already applies.
"""

from typing import Optional

# (vegetation_index lower bound, label), checked highest threshold first.
VEGETATION_BANDS = [
    (0.55, "dense vegetation (forest/woodland signal)"),
    (0.35, "moderate vegetation (grassland/scrub signal)"),
    (0.0, "sparse vegetation (open ground/arid/water signal)"),
]

# Species groups whose presence corroborates a wetland/aquatic signal even
# when vegetation greenness alone would suggest otherwise.
WETLAND_INDICATOR_GROUPS = {"marine", "amphibian"}
WETLAND_SHARE_THRESHOLD = 0.4

SUITABILITY_WEIGHTS = {"vegetation": 0.5, "presence_history": 0.5}


def classify_habitat_signal(vegetation_index: float, species_group_counts: dict) -> str:
    """A short descriptive label from real, already-computed inputs."""
    signal = next(
        label for threshold, label in VEGETATION_BANDS if vegetation_index >= threshold
    )
    total = sum(species_group_counts.values())
    if total:
        wetland_share = sum(
            count for group, count in species_group_counts.items()
            if group in WETLAND_INDICATOR_GROUPS
        ) / total
        if wetland_share > WETLAND_SHARE_THRESHOLD:
            signal += "; species assemblage suggests wetland/aquatic habitat"
    return signal


def suitability_score(
    vegetation_index: Optional[float],
    group_detection_share: Optional[float],
) -> dict:
    """0-100 heuristic fit score for one species group at one site.

    Combines how green/vegetated the site reads (from real pixels) with how
    much of that site's own detection history already belongs to the
    requested group. A transparent weighted heuristic, not a trained
    habitat-suitability model.
    """
    components = {}
    if vegetation_index is not None:
        components["vegetation"] = vegetation_index
    if group_detection_share is not None:
        components["presence_history"] = group_detection_share

    if not components:
        return {
            "score": None,
            "computed_from": [],
            "note": "No vegetation assessment or detection history for this site.",
        }

    total_weight = sum(SUITABILITY_WEIGHTS[key] for key in components)
    score = sum(SUITABILITY_WEIGHTS[key] * value for key, value in components.items()) / total_weight

    return {
        "score": round(score * 100, 1),
        "computed_from": list(components.keys()),
        "note": (
            "Heuristic score from vegetation greenness and this site's own "
            f"detection history for the group, weighted {SUITABILITY_WEIGHTS} "
            "and renormalised over the components actually available. Not a "
            "trained suitability model."
        ),
    }
