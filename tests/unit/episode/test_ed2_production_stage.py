from __future__ import annotations

import copy
from pathlib import Path

import pytest

from tpaa_episode import (
    PRODUCTION_STAGE_DETECTION_METHOD,
    PRODUCTION_STAGE_ORDER,
    PRODUCTION_STAGE_PRECEDENCE_SOURCE,
    PRODUCTION_STAGE_PROFILE_ID,
    ProductionStageError,
    project_production_basic_stages,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
EPISODE_ID = "c2000000-0000-4000-8000-000000000010"


def _scenario_payload() -> dict[str, object]:
    boundaries = [0, 25, 50, 75, 100]
    markers: list[dict[str, object]] = [
        {
            "marker": stage_type,
            "session_time_us": boundaries[index],
        }
        for index, stage_type in enumerate(PRODUCTION_STAGE_ORDER)
    ]
    markers.append({"marker": "END", "session_time_us": boundaries[-1]})
    return {
        "stage_projection": {
            "stage_profile_id": PRODUCTION_STAGE_PROFILE_ID,
            "precedence_source": PRODUCTION_STAGE_PRECEDENCE_SOURCE,
            "detection_method": PRODUCTION_STAGE_DETECTION_METHOD,
            "markers": markers,
        }
    }


def _markers(payload: dict[str, object]) -> list[object]:
    projection = payload["stage_projection"]
    assert isinstance(projection, dict)
    markers = projection["markers"]
    assert isinstance(markers, list)
    return markers


def test_production_stage_projection_uses_frozen_basic_flight_authority() -> None:
    projection = project_production_basic_stages(
        _scenario_payload(),
        episode_id=EPISODE_ID,
        start_session_time_us=0,
        end_session_time_us=100,
        authority_root=AUTHORITY,
    )

    assert projection.status == "READY"
    assert projection.reason_codes == ()
    assert projection.stage_profile_id == "BASIC_FLIGHT_V1"
    assert projection.precedence_source == "CONTEXT_OFFICIAL_MARKER"
    assert projection.detection_method == "CONTEXT"
    assert len(projection.stage_registry_sha256) == 64
    assert len(projection.logical_hash) == 64
    assert [stage.stage_type for stage in projection.stages] == list(
        PRODUCTION_STAGE_ORDER
    )
    assert [stage.stage_order for stage in projection.stages] == [0, 1, 2, 3]
    assert [
        (stage.start_session_time_us, stage.end_session_time_us)
        for stage in projection.stages
    ] == [(0, 25), (25, 50), (50, 75), (75, 100)]
    assert all(stage.stage_status == "VALID" for stage in projection.stages)
    assert len({stage.stage_id for stage in projection.stages}) == 4


def test_production_stage_projection_missing_scenario_is_business_insufficiency() -> None:
    projection = project_production_basic_stages(
        None,
        episode_id=EPISODE_ID,
        start_session_time_us=0,
        end_session_time_us=100,
        authority_root=AUTHORITY,
    )

    assert projection.status == "INSUFFICIENT_DATA"
    assert projection.stages == ()
    assert projection.reason_codes == (
        "ED2_SOURCE_FAMILY_MISSING_SCENARIO",
    )
    assert len(projection.logical_hash) == 64


def test_production_stage_projection_rejects_missing_markers() -> None:
    payload = copy.deepcopy(_scenario_payload())
    projection = payload["stage_projection"]
    assert isinstance(projection, dict)
    projection["markers"] = []

    with pytest.raises(
        ProductionStageError,
        match="ED2_STAGE_MARKER_COUNT_INVALID",
    ):
        project_production_basic_stages(
            payload,
            episode_id=EPISODE_ID,
            start_session_time_us=0,
            end_session_time_us=100,
            authority_root=AUTHORITY,
        )


def test_production_stage_projection_rejects_stage_order_drift() -> None:
    payload = copy.deepcopy(_scenario_payload())
    markers = _markers(payload)
    markers[1] = {"marker": "COMPLETION", "session_time_us": 25}

    with pytest.raises(
        ProductionStageError,
        match="ED2_STAGE_MARKER_ORDER_INVALID",
    ):
        project_production_basic_stages(
            payload,
            episode_id=EPISODE_ID,
            start_session_time_us=0,
            end_session_time_us=100,
            authority_root=AUTHORITY,
        )


def test_production_stage_projection_rejects_episode_boundary_drift() -> None:
    payload = copy.deepcopy(_scenario_payload())
    markers = _markers(payload)
    markers[4] = {"marker": "END", "session_time_us": 99}

    with pytest.raises(
        ProductionStageError,
        match="ED2_STAGE_MARKER_INTERVAL_INVALID",
    ):
        project_production_basic_stages(
            payload,
            episode_id=EPISODE_ID,
            start_session_time_us=0,
            end_session_time_us=100,
            authority_root=AUTHORITY,
        )
