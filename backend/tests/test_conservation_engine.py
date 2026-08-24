"""Tests for the conservation recommendation engine.

Pure maths/logic, no database and no models, so these run anywhere.
"""

from app.modules.conservation.engine import recommend


def test_no_inputs_produces_no_recommendations():
    assert recommend({}) == []


def test_low_health_score_triggers_conservation_priority():
    result = recommend({"location_name": "Site A", "overall_health": 20.0, "health_band": "Critical"})
    categories = [r["category"] for r in result]
    assert "conservation_priority" in categories
    priority_rec = next(r for r in result if r["category"] == "conservation_priority")
    assert priority_rec["priority"] == "high"
    assert "20.0" in priority_rec["rationale"]


def test_healthy_site_does_not_trigger_conservation_priority():
    result = recommend({"overall_health": 85.0})
    assert all(r["category"] != "conservation_priority" for r in result)


def test_missing_health_score_produces_no_priority_guess():
    result = recommend({"overall_health": None})
    assert all(r["category"] != "conservation_priority" for r in result)


def test_endangered_species_triggers_wildlife_protection():
    result = recommend({
        "endangered_species": [
            {"scientific_name": "Panthera tigris", "common_name": "Tiger", "iucn_status": "EN"},
        ],
    })
    rec = next(r for r in result if r["category"] == "wildlife_protection")
    assert rec["priority"] == "high"
    assert "Tiger" in rec["rationale"]


def test_declining_endangered_species_adds_a_second_stronger_recommendation():
    inputs = {
        "endangered_species": [
            {"scientific_name": "Panthera tigris", "common_name": "Tiger", "iucn_status": "EN"},
        ],
        "declining_species": [{"scientific_name": "Panthera tigris"}],
    }
    result = recommend(inputs)
    protection_recs = [r for r in result if r["category"] == "wildlife_protection"]
    assert len(protection_recs) == 2


def test_declining_non_endangered_species_does_not_trigger_protection_escalation():
    inputs = {"declining_species": [{"scientific_name": "Some Common Species"}]}
    result = recommend(inputs)
    assert all(r["category"] != "wildlife_protection" for r in result)


def test_habitat_degradation_triggers_restoration_recommendation():
    inputs = {
        "habitat_degradation_significant": True,
        "vegetation_trend": {"slope": -0.05, "p_value": 0.02, "n_points": 5},
    }
    result = recommend(inputs)
    rec = next(r for r in result if r["category"] == "habitat_restoration")
    assert "-0.05" in rec["rationale"]


def test_no_degradation_flag_produces_no_restoration_recommendation():
    result = recommend({"habitat_degradation_significant": False})
    assert all(r["category"] != "habitat_restoration" for r in result)
    result = recommend({"habitat_degradation_significant": None})
    assert all(r["category"] != "habitat_restoration" for r in result)


def test_low_effort_triggers_monitoring_allocation_low_priority():
    result = recommend({"observation_effort": 3})
    rec = next(r for r in result if r["category"] == "monitoring_allocation")
    assert rec["priority"] == "low"


def test_high_richness_low_effort_triggers_under_sampled_recommendation():
    result = recommend({"species_richness": 8, "observation_effort": 20})
    rec = next(r for r in result if r["category"] == "monitoring_allocation")
    assert rec["priority"] == "medium"


def test_well_sampled_site_has_no_monitoring_allocation_recommendation():
    result = recommend({"species_richness": 8, "observation_effort": 200})
    assert all(r["category"] != "monitoring_allocation" for r in result)


def test_missing_effort_data_does_not_fabricate_a_monitoring_recommendation():
    result = recommend({"species_richness": 8, "observation_effort": None})
    assert all(r["category"] != "monitoring_allocation" for r in result)
