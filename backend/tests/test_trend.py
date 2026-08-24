"""Tests for the shared trend-fitting helper.

Pure maths, no database and no models, so these run anywhere.
"""

import pytest

from app.analytics.trend import linear_trend


def test_empty_and_single_point_are_undefined():
    assert linear_trend([])["direction"] == "insufficient evidence"
    assert linear_trend([])["slope"] is None

    result = linear_trend([(0, 5)])
    assert result["n_points"] == 1
    assert result["direction"] == "insufficient evidence"
    assert result["slope"] is None


def test_clean_increasing_series_is_significant():
    points = [(x, 2 * x + 1) for x in range(6)]
    result = linear_trend(points)

    assert result["n_points"] == 6
    assert result["slope"] == pytest.approx(2.0, abs=1e-6)
    assert result["significant"] is True
    assert result["direction"] == "increasing"
    assert result["p_value"] < 0.05


def test_clean_decreasing_series_is_significant():
    points = [(x, 100 - 3 * x) for x in range(6)]
    result = linear_trend(points)

    assert result["slope"] < 0
    assert result["direction"] == "decreasing"
    assert result["significant"] is True


def test_flat_series_is_stable_not_insufficient_evidence():
    points = [(x, 10) for x in range(5)]
    result = linear_trend(points)

    assert result["slope"] == 0.0
    assert result["direction"] == "stable"
    assert result["percent_change_per_period"] == 0.0


def test_short_series_is_insufficient_evidence_even_with_a_steep_slope():
    # Only 2 points: a "perfect" fit by construction, but too few to trust.
    result = linear_trend([(0, 1), (1, 100)])

    assert result["n_points"] == 2
    assert result["direction"] == "insufficient evidence"
    # The numeric slope is still reported -- just not asserted as a direction.
    assert result["slope"] == pytest.approx(99.0, abs=1e-6)


def test_noisy_series_with_no_real_trend_is_insufficient_evidence():
    points = [(0, 5), (1, 1), (2, 6), (3, 2), (4, 5), (5, 3)]
    result = linear_trend(points)

    assert result["direction"] == "insufficient evidence"
    assert result["significant"] is False


def test_identical_x_values_cannot_be_fit():
    result = linear_trend([(1, 5), (1, 8), (1, 3)])

    assert result["direction"] == "insufficient evidence"
    assert result["slope"] is None
    assert "same x value" in result["note"]
