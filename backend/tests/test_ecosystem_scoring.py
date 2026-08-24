"""Tests for ecosystem health scoring.

Pure maths, no database and no models, so these run anywhere.
"""

from app.modules.ecosystem.scoring import (
    biodiversity_score,
    habitat_quality_score,
    overall_ecosystem_health_score,
    population_stability_score,
)


def test_biodiversity_score_null_with_no_inputs():
    assert biodiversity_score(None, None) is None


def test_biodiversity_score_uses_available_component_only():
    evenness_only = biodiversity_score(None, 1.0)
    assert evenness_only == 100.0


def test_biodiversity_score_in_range():
    score = biodiversity_score(3.0, 1.0)
    assert score == 100.0
    score = biodiversity_score(0.0, 0.0)
    assert score == 0.0


def test_habitat_quality_score_null_without_vegetation_index():
    assert habitat_quality_score(None, False) is None


def test_habitat_quality_score_discounted_for_significant_degradation():
    stable = habitat_quality_score(0.8, False)
    declining = habitat_quality_score(0.8, True)
    assert declining < stable
    assert stable == 80.0


def test_population_stability_excludes_insufficient_evidence():
    score = population_stability_score(
        ["increasing", "insufficient evidence", "insufficient evidence"]
    )
    # Only the one counted species is favourable -> 100%, not diluted by the
    # two "insufficient evidence" species being treated as failures.
    assert score == 100.0


def test_population_stability_null_when_nothing_countable():
    assert population_stability_score(["insufficient evidence"]) is None
    assert population_stability_score([]) is None


def test_population_stability_mixed_directions():
    score = population_stability_score(["increasing", "decreasing", "stable", "decreasing"])
    assert score == 50.0  # 2 of 4 favourable


def test_overall_score_null_below_minimum_components():
    result = overall_ecosystem_health_score(80.0, None, None)
    assert result["overall_ecosystem_health_score"] is None
    assert result["computed_from"] == ["biodiversity_score"]


def test_overall_score_computed_with_two_components_and_reports_which():
    result = overall_ecosystem_health_score(80.0, 60.0, None)
    assert result["overall_ecosystem_health_score"] is not None
    assert set(result["computed_from"]) == {"biodiversity_score", "habitat_quality_score"}
    assert result["band"] in {"Good", "Fair", "Poor", "Critical"}


def test_overall_score_full_inputs_in_sane_range():
    result = overall_ecosystem_health_score(90.0, 85.0, 95.0)
    assert 0.0 <= result["overall_ecosystem_health_score"] <= 100.0
    assert result["band"] == "Good"
    assert len(result["computed_from"]) == 3


def test_overall_score_all_none():
    result = overall_ecosystem_health_score(None, None, None)
    assert result["overall_ecosystem_health_score"] is None
    assert result["computed_from"] == []
