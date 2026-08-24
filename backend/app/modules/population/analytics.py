"""Population intelligence calculations.

Pure functions over plain counts, so they can be tested without a database or
a model -- same discipline as biodiversity/indices.py.

This platform performs no cross-frame individual re-identification (stated
throughout docs/milestone2.md), so nothing here computes a population estimate
in the mark-recapture or distance-sampling sense. Two honestly-named
quantities instead:

  * peak_simultaneous_count -- the largest number of individuals of one
    species seen together in a single frame. A real, standard field-survey
    quantity, but a LOWER BOUND on population size: frames with fewer animals
    captured tell us nothing about how many were actually present nearby.
  * count_variability -- how much the observed peak count varies survey to
    survey, via bootstrap resampling of the median. This describes spread in
    what was observed, not a calibrated confidence interval for the true
    population, which would require a modelled detection probability this
    platform does not fit.
"""

import random
import statistics
from typing import Optional

# Bootstrapping the median of fewer than this many surveys is close to
# meaningless -- the resampled distribution is dominated by which few values
# happened to be drawn, not by real variability.
MIN_SURVEYS_FOR_VARIABILITY = 5

DEFAULT_BOOTSTRAP_SAMPLES = 2000
DEFAULT_SEED = 42


def peak_simultaneous_count(frame_counts: list[int]) -> dict:
    """The largest number of individuals of one species seen in a single frame.

    `frame_counts` is one count per frame/observation containing this species.
    """
    if not frame_counts:
        return {
            "peak_simultaneous_count": None,
            "frames_examined": 0,
            "note": "No frames with a species-level detection in scope.",
        }
    return {
        "peak_simultaneous_count": max(frame_counts),
        "frames_examined": len(frame_counts),
        "note": (
            "Largest number of individuals seen together in one frame -- a "
            "lower bound on population size, not an estimate of it. No "
            "individual is matched across frames, so animals photographed in "
            "different frames may or may not be the same individuals."
        ),
    }


def count_variability(
    survey_values: list[float],
    n_bootstrap: int = DEFAULT_BOOTSTRAP_SAMPLES,
    seed: int = DEFAULT_SEED,
) -> dict:
    """Spread of per-survey peak counts, via bootstrap resampling of the median.

    Gated at `MIN_SURVEYS_FOR_VARIABILITY` surveys. Deterministic (seeded) so
    the same input always reproduces the same interval.
    """
    n = len(survey_values)
    if n < MIN_SURVEYS_FOR_VARIABILITY:
        return {
            "n_surveys": n,
            "median": round(statistics.median(survey_values), 2) if survey_values else None,
            "low": None,
            "high": None,
            "note": (
                f"Need at least {MIN_SURVEYS_FOR_VARIABILITY} surveys to "
                f"characterise variability; only {n} available."
            ),
        }

    rng = random.Random(seed)
    resampled_medians = sorted(
        statistics.median(rng.choices(survey_values, k=n))
        for _ in range(n_bootstrap)
    )
    low = resampled_medians[int(0.025 * n_bootstrap)]
    high = resampled_medians[min(n_bootstrap - 1, int(0.975 * n_bootstrap))]

    return {
        "n_surveys": n,
        "median": round(statistics.median(survey_values), 2),
        "low": round(low, 2),
        "high": round(high, 2),
        "note": (
            "Variability in the observed peak counts across surveys "
            "(bootstrap 95% interval of the median) -- not a calibrated "
            "confidence interval for true population size."
        ),
    }
