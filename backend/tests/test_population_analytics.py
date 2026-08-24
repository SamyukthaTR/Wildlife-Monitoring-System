"""Tests for population intelligence calculations.

Pure maths, no database and no models, so these run anywhere.
"""

import pytest

from app.modules.population.analytics import count_variability, peak_simultaneous_count


def test_peak_count_with_no_frames_is_null():
    result = peak_simultaneous_count([])
    assert result["peak_simultaneous_count"] is None
    assert result["frames_examined"] == 0


def test_peak_count_is_the_maximum_not_the_sum():
    result = peak_simultaneous_count([1, 3, 2, 1])
    assert result["peak_simultaneous_count"] == 3
    assert result["frames_examined"] == 4
    assert "lower bound" in result["note"]


def test_variability_undefined_below_minimum_surveys():
    result = count_variability([2, 3, 4])
    assert result["n_surveys"] == 3
    assert result["low"] is None
    assert result["high"] is None
    # The median is still reported even when the interval is not.
    assert result["median"] == 3


def test_variability_empty_series_has_no_median():
    result = count_variability([])
    assert result["median"] is None
    assert result["low"] is None


def test_variability_computed_and_bounds_are_sane_with_enough_surveys():
    values = [4, 5, 4, 6, 5, 4, 5]
    result = count_variability(values)

    assert result["n_surveys"] == 7
    assert result["low"] is not None
    assert result["high"] is not None
    assert result["low"] <= result["median"] <= result["high"]


def test_variability_is_deterministic_given_the_same_seed():
    values = [1, 5, 2, 8, 3, 9, 4]
    first = count_variability(values, seed=7)
    second = count_variability(values, seed=7)
    assert first == second
