"""Linear trend estimation with an honesty gate.

A regression line always has *some* slope, even fit to pure noise. Reporting a
confident "increasing" or "decreasing" from a couple of noisy points would be
exactly the kind of overstated precision this platform avoids everywhere else
(see biodiversity/indices.py's null-vs-zero discipline). This module gates the
categorical `direction` on both sample size and statistical significance, while
still returning the numeric slope for anyone who wants it.

Used by population trends (detections over survey dates) and habitat
degradation trends (vegetation index over assessment dates) -- one
implementation, reused, rather than two copies that could drift apart.
"""

from typing import Optional

MIN_POINTS_FOR_SIGNIFICANCE = 3
SIGNIFICANCE_LEVEL = 0.05


def linear_trend(points: list[tuple[float, float]]) -> dict:
    """Fit y = a*x + b over (x, y) pairs and return a hedged trend summary.

    `x` is a numeric axis (e.g. an ordinal date or a timestamp); `y` is a count
    or index value. `direction` is only ever "increasing" or "decreasing" when
    there are at least `MIN_POINTS_FOR_SIGNIFICANCE` points AND the fit is
    statistically significant (p < 0.05); otherwise it is "insufficient
    evidence", even though `slope` may still be a real (just untrustworthy)
    number. A perfectly flat series is reported as "stable" rather than run
    through a regression that would divide by zero variance.
    """
    n = len(points)
    if n == 0:
        return _empty(0, "no data points")
    if n == 1:
        return _empty(1, "a single data point has no trend")

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    if len(set(xs)) == 1:
        return _empty(n, "all data points share the same x value")

    if max(ys) == min(ys):
        return {
            "n_points": n,
            "slope": 0.0,
            "r_value": None,
            "p_value": None,
            "significant": True,
            "direction": "stable",
            "percent_change_per_period": 0.0,
            "note": "All observed values are identical across the series.",
        }

    from scipy import stats

    fit = stats.linregress(xs, ys)
    slope, r_value, p_value = fit.slope, fit.rvalue, fit.pvalue

    mean_y = sum(ys) / n
    percent_change = round((slope / mean_y) * 100, 2) if mean_y else None

    # bool(...) matters: scipy's p_value is a numpy scalar, and a bare
    # `n >= k and p_value < level` would return a numpy.bool_ that fails
    # `is True` comparisons downstream.
    significant = bool(n >= MIN_POINTS_FOR_SIGNIFICANCE and p_value < SIGNIFICANCE_LEVEL)
    if significant:
        direction = "increasing" if slope > 0 else "decreasing"
    else:
        direction = "insufficient evidence"

    if n < MIN_POINTS_FOR_SIGNIFICANCE:
        note = (
            f"Need at least {MIN_POINTS_FOR_SIGNIFICANCE} points to test "
            f"significance; only {n} available."
        )
    elif not significant:
        note = f"Fit over {n} points is not statistically significant (p={p_value:.3f})."
    else:
        note = None

    return {
        "n_points": n,
        "slope": round(slope, 6),
        "r_value": round(r_value, 4),
        "p_value": round(p_value, 4),
        "significant": significant,
        "direction": direction,
        "percent_change_per_period": percent_change,
        "note": note,
    }


def _empty(n: int, reason: str) -> dict:
    return {
        "n_points": n,
        "slope": None,
        "r_value": None,
        "p_value": None,
        "significant": False,
        "direction": "insufficient evidence",
        "percent_change_per_period": None,
        "note": f"Trend undefined: {reason}.",
    }
