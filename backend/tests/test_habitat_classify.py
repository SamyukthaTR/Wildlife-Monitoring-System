"""Tests for habitat signal classification and suitability scoring.

Pure maths, no database and no models, so these run anywhere.
"""

from app.modules.habitat.classify import classify_habitat_signal, suitability_score


def test_high_vegetation_reads_as_dense():
    signal = classify_habitat_signal(0.8, {})
    assert "dense vegetation" in signal


def test_low_vegetation_reads_as_sparse():
    signal = classify_habitat_signal(0.05, {})
    assert "sparse vegetation" in signal


def test_wetland_species_assemblage_is_surfaced_even_at_low_vegetation():
    signal = classify_habitat_signal(0.1, {"marine": 8, "amphibian": 4, "mammal": 2})
    assert "wetland/aquatic" in signal


def test_wetland_signal_absent_when_species_assemblage_does_not_support_it():
    signal = classify_habitat_signal(0.1, {"mammal": 10, "bird": 5})
    assert "wetland" not in signal


def test_suitability_null_with_no_inputs():
    result = suitability_score(None, None)
    assert result["score"] is None
    assert result["computed_from"] == []


def test_suitability_uses_only_available_components():
    vegetation_only = suitability_score(0.8, None)
    assert vegetation_only["computed_from"] == ["vegetation"]
    assert vegetation_only["score"] == 80.0


def test_suitability_blends_both_components_when_available():
    result = suitability_score(0.8, 0.4)
    assert result["computed_from"] == ["vegetation", "presence_history"]
    assert result["score"] == 60.0  # (0.5*0.8 + 0.5*0.4) * 100


def test_suitability_score_is_bounded():
    result = suitability_score(1.0, 1.0)
    assert result["score"] == 100.0
