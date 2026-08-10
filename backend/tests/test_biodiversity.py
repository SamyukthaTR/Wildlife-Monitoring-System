"""Tests for the biodiversity index calculations.

Pure maths, no database and no models, so these run anywhere.
"""

import math

import pytest

from app.modules.biodiversity import indices


def test_even_community_maximises_shannon():
    """Four species in equal numbers: H' should equal ln(4) exactly."""
    result = indices.compute({"a": 5, "b": 5, "c": 5, "d": 5})

    assert result["species_richness"] == 4
    assert result["total_detections"] == 20
    assert result["shannon_index"] == pytest.approx(math.log(4), abs=1e-4)
    # Every p_i = 0.25, so D = 4 * 0.0625 = 0.25
    assert result["simpson_index"] == pytest.approx(0.25, abs=1e-4)
    assert result["inverse_simpson_index"] == pytest.approx(4.0, abs=1e-4)
    # A perfectly even community has evenness 1.
    assert result["pielou_evenness"] == pytest.approx(1.0, abs=1e-4)


def test_uneven_community_lowers_shannon_and_evenness():
    even = indices.compute({"a": 10, "b": 10})
    skewed = indices.compute({"a": 19, "b": 1})

    assert skewed["species_richness"] == even["species_richness"]
    assert skewed["shannon_index"] < even["shannon_index"]
    assert skewed["pielou_evenness"] < even["pielou_evenness"]
    # Dominance rises as the community becomes more skewed.
    assert skewed["simpson_index"] > even["simpson_index"]


def test_known_values_for_a_hand_computed_case():
    """H' and D for {8, 1, 1}, computed by hand."""
    result = indices.compute({"zebra": 8, "impala": 1, "lion": 1})

    p = [0.8, 0.1, 0.1]
    expected_shannon = -sum(x * math.log(x) for x in p)
    expected_simpson = sum(x * x for x in p)

    assert result["shannon_index"] == pytest.approx(expected_shannon, abs=1e-4)
    assert result["simpson_index"] == pytest.approx(expected_simpson, abs=1e-4)
    assert result["gini_simpson_index"] == pytest.approx(1 - expected_simpson, abs=1e-4)


def test_single_species_has_zero_diversity_and_undefined_evenness():
    result = indices.compute({"zebra": 12})

    assert result["species_richness"] == 1
    assert result["shannon_index"] == 0.0
    assert result["simpson_index"] == pytest.approx(1.0, abs=1e-6)
    assert result["gini_simpson_index"] == pytest.approx(0.0, abs=1e-6)
    # Undefined, not zero: 0/0 is not "perfectly uneven".
    assert result["pielou_evenness"] is None
    assert "undefined" in result["note"].lower()


def test_no_detections_reports_null_indices_not_zeros():
    result = indices.compute({})

    assert result["species_richness"] == 0
    assert result["total_detections"] == 0
    assert result["shannon_index"] is None
    assert result["simpson_index"] is None
    assert result["pielou_evenness"] is None
    assert "undefined" in result["note"].lower()


def test_zero_and_negative_counts_are_ignored():
    result = indices.compute({"a": 5, "b": 0, "c": 5})

    assert result["species_richness"] == 2
    assert result["total_detections"] == 10


def test_composition_is_sorted_and_sums_to_one():
    rows = indices.composition({"a": 1, "b": 7, "c": 2})

    assert [row["species"] for row in rows] == ["b", "c", "a"]
    assert sum(row["relative_abundance"] for row in rows) == pytest.approx(1.0, abs=1e-4)
    assert rows[0]["count"] == 7


def test_composition_of_empty_scope_is_empty():
    assert indices.composition({}) == []
