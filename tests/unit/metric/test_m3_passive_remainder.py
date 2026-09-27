from __future__ import annotations

import math
from pathlib import Path

import pytest

from tpaa_metric.catalog_engine import (
    M2MetricPluginRequest,
    MetricPluginRegistry,
    validate_m2_runtime_output,
)
from tpaa_metric.m3_air_operators import M3_AIR_OPERATOR_IMPLEMENTATIONS
from tpaa_metric.m3_general_engine import build_m3_metric_execution_plan
from tpaa_metric.m3_passive import (
    M3_PSV_ALLOWED_SYSTEM_TYPES,
    M3_PSV_CODES,
    register_m3_passive_plugins,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def _quality(system_type: str = "IRST") -> dict[str, object]:
    return {
        "system_type": system_type,
        "reference_match_quality_profile_id": "Q-PROFILE",
        "reference_match_quality_profile_version": "1.0.0",
        "reference_match_quality_profile_hash": HASH_A,
    }


def _opportunity_identity() -> dict[str, object]:
    return {
        "opportunity_profile_id": "OPP",
        "opportunity_profile_version": "1.0.0",
        "opportunity_profile_hash": HASH_B,
    }


def _coverage_identity() -> dict[str, object]:
    return {
        "reference_target_coverage_id": "COVERAGE",
        "reference_target_coverage_version": "1.0.0",
        "reference_target_coverage_hash": HASH_C,
    }


def _golden_inputs(system_type: str = "IRST") -> dict[str, dict[str, object]]:
    angle_a = 0.1
    angle_b = 0.2
    base_quality = _quality(system_type)
    opportunity = _opportunity_identity()
    tracks = [
        {
            "track_id": f"T{index}",
            "stable_start_time_us": 0,
            "stable_end_time_us": 2_000_000,
            "association_status": "NO_MATCH" if index >= 8 else "MATCHED",
        }
        for index in range(10)
    ]
    tracks.append(
        {
            "track_id": "TA",
            "stable_start_time_us": 0,
            "stable_end_time_us": 2_000_000,
            "association_status": "AMBIGUOUS",
        }
    )
    return {
        "P1-PSV-001": {
            **base_quality,
            "samples": [
                {
                    "reference_match_accepted": True,
                    "error_domain": "LOS_ANGLE",
                    "measured_los_unit": [math.cos(angle_a), math.sin(angle_a), 0.0],
                    "reference_los_unit": [1.0, 0.0, 0.0],
                },
                {
                    "reference_match_accepted": True,
                    "error_domain": "LOS_ANGLE",
                    "measured_los_unit": [math.cos(angle_b), math.sin(angle_b), 0.0],
                    "reference_los_unit": [1.0, 0.0, 0.0],
                },
            ],
        },
        "P1-PSV-002": {
            **base_quality,
            "samples": [
                {
                    "reference_match_accepted": True,
                    "error_domain": "LOS_RATE",
                    "measured_los_rate_rad_s": 2.0,
                    "reference_los_rate_rad_s": 1.0,
                },
                {
                    "reference_match_accepted": True,
                    "error_domain": "LOS_RATE",
                    "measured_los_rate_rad_s": 1.0,
                    "reference_los_rate_rad_s": 2.0,
                },
            ],
        },
        "P1-PSV-003": {
            **base_quality,
            "samples": [
                {
                    "reference_match_accepted": True,
                    "error_domain": "RANGE",
                    "passive_range_estimate_m": 1100.0,
                    "reference_range_m": 1000.0,
                },
                {
                    "reference_match_accepted": True,
                    "error_domain": "RANGE",
                    "passive_range_estimate_m": 900.0,
                    "reference_range_m": 1000.0,
                },
            ],
        },
        "P1-PSV-004": {
            "system_type": system_type,
            **opportunity,
            "confirmation_profile_id": "CONF",
            "confirmation_profile_version": "1.0.0",
            "confirmation_profile_hash": HASH_C,
            "evaluation_opportunity_intervals": [
                {
                    "detection_opportunity_id": f"O{index}",
                    "reference_target_id": f"R{index}",
                    "start_session_time_us": index * 2_000_000,
                    "end_session_time_us": (index + 1) * 2_000_000,
                }
                for index in range(3)
            ],
            "confirmation_events": [
                {
                    "detection_confirmation_event_id": f"C{index}",
                    "detection_opportunity_id": f"O{index}",
                    "reference_target_id": f"R{index}",
                }
                for index in range(2)
            ],
        },
        "P1-PSV-005": {
            "system_type": system_type,
            **opportunity,
            "evaluation_opportunity_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 10_000_000}
            ],
            "passive_track_valid_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 4_000_000},
                {"start_session_time_us": 6_000_000, "end_session_time_us": 10_000_000},
            ],
        },
        "P1-PSV-006": {
            "system_type": system_type,
            "profile": {
                "drop_min_duration_s": 1.0,
                "reacquisition_persistence_s": 1.0,
                "max_gap_us": 500_000,
            },
            "reacquisition_events": [
                {
                    "passive_drop_time_us": 0,
                    "passive_reacquired_time_us": delay * 1_000_000,
                    "invalid_dwell_s": 1.5,
                    "stable_persistence_s": 1.5,
                    "same_reference_association": True,
                }
                for delay in (2, 4, 6)
            ],
        },
        "P1-PSV-007": {
            "system_type": system_type,
            **_coverage_identity(),
            "reference_target_coverage_status": "COMPLETE",
            "evaluation_start_time_us": 0,
            "evaluation_end_time_us": 10_000_000,
            "coverage_start_time_us": 0,
            "coverage_end_time_us": 10_000_000,
            "profile": {
                "stable_track_persistence_s": 1.0,
                "max_gap_us": 500_000,
            },
            "passive_tracks": tracks,
        },
    }


def _plugin_request(
    code: str,
    payload: dict[str, object],
) -> tuple[M2MetricPluginRequest, object]:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    register_m3_passive_plugins(plan, registry)
    definition = plan.definition(code)
    _plugin_id, plugin = registry.resolve(
        definition.algorithm_id,
        definition.algorithm_version,
    )
    request = M2MetricPluginRequest(
        definition=definition,
        input_payload=payload,
        upstream_result_hashes=(
            ("P1-QA-001", "1" * 64),
            ("P1-QA-002", "2" * 64),
            ("P1-QA-005", "5" * 64),
        ),
        operators={
            operator_id: M3_AIR_OPERATOR_IMPLEMENTATIONS[operator_id]
            for operator_id in definition.operator_bindings
        },
    )
    return request, plugin


def _instance(output: object) -> dict[str, object]:
    assert isinstance(output, dict)
    raw = output["instances"]
    assert isinstance(raw, list) and len(raw) == 1
    assert isinstance(raw[0], dict)
    return raw[0]


def test_m3_passive_membership_and_system_type_set_are_exact() -> None:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    definitions = tuple(
        sorted(
            (
                definition
                for definition in plan.definitions
                if definition.metric_code in M3_PSV_CODES
            ),
            key=lambda definition: definition.metric_code,
        )
    )
    assert tuple(item.metric_code for item in definitions) == M3_PSV_CODES
    assert {item.family for item in definitions} == {"PASSIVE_SENSOR"}
    assert all(
        item.applicability.applicability_mode == "SYSTEM_TYPE_SET"
        and item.applicability.allowed_system_types == M3_PSV_ALLOWED_SYSTEM_TYPES
        for item in definitions
    )


@pytest.mark.parametrize("system_type", M3_PSV_ALLOWED_SYSTEM_TYPES)
@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("P1-PSV-001", math.sqrt((0.1**2 + 0.2**2) / 2.0)),
        ("P1-PSV-002", 1.0),
        ("P1-PSV-003", 100.0),
        ("P1-PSV-004", 2.0 / 3.0),
        ("P1-PSV-005", 0.8),
        ("P1-PSV-006", 4.0),
        ("P1-PSV-007", 0.2),
    ],
)
def test_m3_passive_golden_values(
    system_type: str,
    code: str,
    expected: float,
) -> None:
    payload = _golden_inputs(system_type)[code]
    request, plugin = _plugin_request(code, payload)
    output = plugin(request)
    validate_m2_runtime_output(request.definition, payload, output)
    assert _instance(output)["value_numeric"] == pytest.approx(expected)


@pytest.mark.parametrize("code", M3_PSV_CODES)
def test_m3_passive_non_applicable_system_fails_closed(code: str) -> None:
    payload: dict[str, object] = {"system_type": "RADAR"}
    request, plugin = _plugin_request(code, payload)
    output = plugin(request)
    validate_m2_runtime_output(request.definition, payload, output)
    assert output["applicable"] is False
    assert output["instances"] == []


def test_m3_passive_reference_quality_rejects_all_without_zero() -> None:
    payload = _golden_inputs()["P1-PSV-003"]
    rows = payload["samples"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        row["reference_match_accepted"] = False
    request, plugin = _plugin_request("P1-PSV-003", payload)
    output = plugin(request)
    assert _instance(output)["status"] == "N_A"
    assert _instance(output)["reason_codes"] == [
        "REFERENCE_MATCH_QUALITY_REJECTED_ALL"
    ]


def test_m3_passive_false_track_requires_complete_reference_coverage() -> None:
    payload = _golden_inputs()["P1-PSV-007"]
    payload["reference_target_coverage_status"] = "PARTIAL"
    request, plugin = _plugin_request("P1-PSV-007", payload)
    output = plugin(request)
    assert _instance(output)["status"] == "N_A"
    assert _instance(output)["reason_codes"] == [
        "REFERENCE_TARGET_SET_COVERAGE_INCOMPLETE"
    ]
