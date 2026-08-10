"""Biodiversity index calculations.

Pure functions over an abundance mapping, so they can be tested without a
database or a model. Standard community-ecology definitions:

    p_i = n_i / N   (proportional abundance of species i)

    Species richness      S  = number of species with n_i > 0
    Shannon index         H' = -sum p_i * ln(p_i)
    Simpson's index       D  = sum p_i^2                  (dominance)
    Gini-Simpson          1 - D                           (diversity)
    Inverse Simpson       1 / D                           (effective species)
    Pielou's evenness     J' = H' / ln(S)

Two deliberate choices about what "undefined" means:

  * With one species, evenness is 0/0. It is reported as null, not 0 -- a
    single-species community is not "perfectly uneven", the measure simply does
    not apply.
  * With no detections at all, every index is null with an explanatory note.
    Reporting zeros would make an unsurveyed site look like a dead one.

The counting unit is one detected animal in one frame. Acoustic detections are
excluded, because AudioSet labels identify a sound type rather than a species
and would otherwise inflate richness with entries like "Bird".
"""

import math


def compute(abundances: dict[str, int]) -> dict:
    """Compute all indices for a {species_name: count} mapping."""
    positive = {name: count for name, count in abundances.items() if count and count > 0}
    total = sum(positive.values())
    richness = len(positive)

    if total == 0:
        return _empty("no species-rank detections in scope")

    proportions = [count / total for count in positive.values()]

    shannon = -sum(p * math.log(p) for p in proportions)
    simpson_d = sum(p * p for p in proportions)

    # Guard against floating-point drift making a single-species H' slightly
    # negative (e.g. -1e-17), which would look like a bug in the UI.
    shannon = max(0.0, shannon)

    evenness = None
    if richness > 1:
        evenness = shannon / math.log(richness)

    return {
        "species_richness": richness,
        "total_detections": total,
        "shannon_index": round(shannon, 4),
        "simpson_index": round(simpson_d, 4),
        "gini_simpson_index": round(1 - simpson_d, 4),
        "inverse_simpson_index": round(1 / simpson_d, 4) if simpson_d > 0 else None,
        "pielou_evenness": round(evenness, 4) if evenness is not None else None,
        "note": (
            "Evenness is undefined for a single species and reported as null."
            if richness == 1 else None
        ),
    }


def _empty(reason: str) -> dict:
    return {
        "species_richness": 0,
        "total_detections": 0,
        "shannon_index": None,
        "simpson_index": None,
        "gini_simpson_index": None,
        "inverse_simpson_index": None,
        "pielou_evenness": None,
        "note": f"Indices undefined: {reason}.",
    }


def composition(abundances: dict[str, int]) -> list[dict]:
    """Species list with relative abundance, most abundant first."""
    positive = {name: count for name, count in abundances.items() if count and count > 0}
    total = sum(positive.values())
    if total == 0:
        return []
    return [
        {
            "species": name,
            "count": count,
            "relative_abundance": round(count / total, 4),
        }
        for name, count in sorted(positive.items(), key=lambda kv: kv[1], reverse=True)
    ]
