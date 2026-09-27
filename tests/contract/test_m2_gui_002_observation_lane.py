from __future__ import annotations

from copy import deepcopy

import pytest

from tpaa_gui.m2_workspace import (
    M2FoundationNavigationError,
    build_m2_foundation_navigation_model,
)

from tests.contract.test_m2_gui_001_foundation_navigation import _projection


def test_m2_gui_002_model_projects_exact_observation_lanes() -> None:
    model = build_m2_foundation_navigation_model(_projection())
    assert {
        lane: len(model.by_observation_lane(lane))
        for lane in (
            "AIRCRAFT_CAP_L1_OBSERVATION",
            "SYSTEM_PERFORMANCE_OBSERVATION",
            "QUALITY_EVIDENCE_ONLY",
        )
    } == {
        "AIRCRAFT_CAP_L1_OBSERVATION": 3,
        "SYSTEM_PERFORMANCE_OBSERVATION": 24,
        "QUALITY_EVIDENCE_ONLY": 5,
    }
    assert {
        item.metric_code
        for item in model.by_observation_lane("AIRCRAFT_CAP_L1_OBSERVATION")
    } == {"P1-AIR-001", "P1-AIR-002", "P1-AIR-003"}
    assert {
        item.metric_code
        for item in model.by_observation_lane("QUALITY_EVIDENCE_ONLY")
    } == {
        "P1-QA-001",
        "P1-QA-002",
        "P1-QA-005",
        "P1-QA-007",
        "P1-QA-008",
    }


def test_m2_gui_002_presentation_preserves_route_lane_meaning() -> None:
    model = build_m2_foundation_navigation_model(_projection())
    capability = model.item("P1-AIR-001")
    evidence_only = model.item("P1-QA-001")
    system = model.item("P1-SNS-001")

    assert capability.publication_route == "CAPABILITY_OBSERVATION"
    assert capability.observation_record_expected is True
    assert capability.lane_presentation_label == "Aircraft capability observation"

    assert system.publication_route == "SYSTEM_PERFORMANCE_OBSERVATION"
    assert system.observation_record_expected is True
    assert system.lane_presentation_label == "Mission-system performance observation"

    assert evidence_only.publication_route == "METRIC_INSTANCE_EVIDENCE_ONLY"
    assert evidence_only.observation_record_expected is False
    assert evidence_only.lane_presentation_label == "Quality evidence only"


def test_m2_gui_002_rejects_route_lane_mismatch() -> None:
    projection = deepcopy(_projection())
    definitions = projection["definitions"]
    assert isinstance(definitions, list)
    first = definitions[0]
    assert isinstance(first, dict)
    first["publication_route"] = "SYSTEM_PERFORMANCE_OBSERVATION"
    with pytest.raises(M2FoundationNavigationError) as error:
        build_m2_foundation_navigation_model(projection)
    assert str(error.value).startswith("M2_GUI_OBSERVATION_ROUTE_LANE_MISMATCH:")


def test_m2_gui_002_unknown_lane_filter_fails_closed() -> None:
    model = build_m2_foundation_navigation_model(_projection())
    with pytest.raises(M2FoundationNavigationError) as error:
        model.by_observation_lane("UNKNOWN")
    assert str(error.value) == "M2_GUI_OBSERVATION_LANE_UNKNOWN:UNKNOWN"
