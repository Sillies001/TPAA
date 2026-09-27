from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_metric.catalog_engine import (
    M2MetricPluginRequest,
    MetricPluginRegistry,
    validate_m2_runtime_output,
)
from tpaa_metric.m3_general_engine import build_m3_metric_execution_plan
from tpaa_metric.m3_track import (
    M3_TRK_CODES,
    M3_TRK_FAMILY,
    M3_TRK_REQUIRED_PRODUCT_SEMANTICS,
    register_m3_track_plugins,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"

PRODUCTS = [M3_TRK_REQUIRED_PRODUCT_SEMANTICS]
HASH_A = "a" * 64
HASH_B = "b" * 64


def _opportunity_identity() -> dict[str, object]:
    return {
        "detection_opportunity_id": "opp-001",
        "opportunity_profile_id": "opportunity-profile",
        "opportunity_profile_version": "1.0.0",
        "opportunity_profile_hash": HASH_A,
    }


def _request(
    code: str,
    payload: dict[str, object],
) -> tuple[M2MetricPluginRequest, object]:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    register_m3_track_plugins(plan, registry)
    definition = plan.definition(code)
    _plugin_id, plugin = registry.resolve(
        definition.algorithm_id,
        definition.algorithm_version,
    )
    upstream = (
        (("P1-QA-005", HASH_B),)
        if code in {"P1-TRK-002", "P1-TRK-003"}
        else ()
    )
    request = M2MetricPluginRequest(
        definition=definition,
        input_payload=payload,
        upstream_result_hashes=upstream,
        operators={
            operator_id: {
                "RMS_V1": lambda values: sum(value * value for value in values)
                ** 0.5
                / len(values) ** 0.5,
                "MEDIAN_V1": lambda values: sorted(values)[len(values) // 2]
                if len(values) % 2
                else (
                    sorted(values)[len(values) // 2 - 1]
                    + sorted(values)[len(values) // 2]
                )
                / 2.0,
                "QUANTILE_HF7_V1": lambda values, probability: (
                    sorted(values)[0]
                    + probability * (sorted(values)[-1] - sorted(values)[0])
                ),
            }[operator_id]
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


def test_m3_track_membership_and_product_applicability_are_exact() -> None:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    definitions = tuple(
        sorted(
            (
                definition
                for definition in plan.definitions
                if definition.metric_code in M3_TRK_CODES
            ),
            key=lambda definition: definition.metric_code,
        )
    )
    assert tuple(item.metric_code for item in definitions) == M3_TRK_CODES
    assert {item.family for item in definitions} == {M3_TRK_FAMILY}
    assert all(item.value_kind == "NUMERIC" for item in definitions)
    assert all(
        item.applicability.applicability_mode == "PRODUCT_CAPABILITY"
        and item.applicability.required_product_semantics
        == M3_TRK_REQUIRED_PRODUCT_SEMANTICS
        for item in definitions
    )

    registry = MetricPluginRegistry()
    register_m3_track_plugins(plan, registry)
    for definition in definitions:
        plugin_id, _plugin = registry.resolve(
            definition.algorithm_id,
            definition.algorithm_version,
        )
        assert plugin_id == f"m3-track-remainder:{definition.metric_code}:v1"


def test_track_initiation_golden_and_missing_product_fail_closed() -> None:
    payload = {
        "product_semantics": PRODUCTS,
        "first_confirmed_detection_time_us": 1_000_000,
        "stable_track_start_time_us": 2_500_000,
        "detection_confirmation_event_id": "confirm-001",
        "confirmation_profile_id": "confirm-profile",
        "confirmation_profile_version": "1.0.0",
        "confirmation_profile_hash": HASH_A,
        "profile": {
            "stable_track_persistence_s": 0.5,
            "max_gap_us": 500_000,
        },
    }
    request, plugin = _request("P1-TRK-001", payload)
    output = dict(plugin(request))
    validate_m2_runtime_output(request.definition, payload, output)
    assert _instance(output)["value_numeric"] == pytest.approx(1.5)

    negative = {"product_semantics": []}
    request, plugin = _request("P1-TRK-001", negative)
    output = dict(plugin(request))
    validate_m2_runtime_output(request.definition, negative, output)
    assert output["applicable"] is False
    assert output["instances"] == []


def test_track_error_continuity_drop_reacquisition_and_age_goldens() -> None:
    reference_profile = {
        "reference_match_quality_profile_id": "reference-profile",
        "reference_match_quality_profile_version": "1.0.0",
        "reference_match_quality_profile_hash": HASH_A,
    }
    request, plugin = _request(
        "P1-TRK-002",
        {
            "product_semantics": PRODUCTS,
            **reference_profile,
            "samples": [
                {
                    "track_position_ecef_m": [3.0, 4.0, 0.0],
                    "reference_target_position_ecef_m": [0.0, 0.0, 0.0],
                    "reference_match_accepted": True,
                    "error_domain": "POSITION_3D",
                },
                {
                    "track_position_ecef_m": [0.0, 3.0, 4.0],
                    "reference_target_position_ecef_m": [0.0, 0.0, 0.0],
                    "reference_match_accepted": True,
                    "error_domain": "POSITION_3D",
                },
            ],
        },
    )
    output = dict(plugin(request))
    validate_m2_runtime_output(request.definition, request.input_payload, output)
    assert _instance(output)["value_numeric"] == pytest.approx(5.0)

    request, plugin = _request(
        "P1-TRK-003",
        {
            "product_semantics": PRODUCTS,
            **reference_profile,
            "samples": [
                {
                    "track_velocity_ecef_mps": [2.0, 0.0, 0.0],
                    "reference_target_velocity_ecef_mps": [0.0, 0.0, 0.0],
                    "reference_match_accepted": True,
                    "error_domain": "VELOCITY_3D",
                },
                {
                    "track_velocity_ecef_mps": [0.0, 2.0, 0.0],
                    "reference_target_velocity_ecef_mps": [0.0, 0.0, 0.0],
                    "reference_match_accepted": True,
                    "error_domain": "VELOCITY_3D",
                },
            ],
        },
    )
    assert _instance(dict(plugin(request)))["value_numeric"] == pytest.approx(2.0)

    request, plugin = _request(
        "P1-TRK-004",
        {
            "product_semantics": PRODUCTS,
            **_opportunity_identity(),
            "evaluation_opportunity_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 10_000_000}
            ],
            "valid_track_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 4_000_000},
                {"start_session_time_us": 6_000_000, "end_session_time_us": 10_000_000},
            ],
        },
    )
    assert _instance(dict(plugin(request)))["value_numeric"] == pytest.approx(0.8)

    request, plugin = _request(
        "P1-TRK-005",
        {
            "product_semantics": PRODUCTS,
            **_opportunity_identity(),
            "opportunity_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 12_000_000}
            ],
            "valid_track_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 2_000_000},
                {
                    "start_session_time_us": 2_200_000,
                    "end_session_time_us": 4_000_000,
                },
                {"start_session_time_us": 6_000_000, "end_session_time_us": 8_000_000},
                {
                    "start_session_time_us": 10_000_000,
                    "end_session_time_us": 12_000_000,
                },
            ],
            "profile": {"drop_min_duration_s": 1.0},
        },
    )
    assert _instance(dict(plugin(request)))["value_numeric"] == pytest.approx(2.0)

    request, plugin = _request(
        "P1-TRK-006",
        {
            "product_semantics": PRODUCTS,
            **_opportunity_identity(),
            "profile": {
                "drop_min_duration_s": 1.0,
                "reacquisition_persistence_s": 0.5,
            },
            "reacquisition_events": [
                {
                    "detection_opportunity_id": "opp-001",
                    "track_drop_start_time_us": 0,
                    "reacquired_stable_track_time_us": 2_000_000,
                    "invalid_dwell_s": 1.5,
                    "stable_persistence_s": 0.5,
                },
                {
                    "detection_opportunity_id": "opp-001",
                    "track_drop_start_time_us": 10_000_000,
                    "reacquired_stable_track_time_us": 14_000_000,
                    "invalid_dwell_s": 3.0,
                    "stable_persistence_s": 0.5,
                },
            ],
        },
    )
    instance = _instance(dict(plugin(request)))
    assert instance["value_numeric"] == pytest.approx(3.0)
    evidence = instance["evidence"]
    assert isinstance(evidence, dict)
    assert evidence["p95_reacquisition_delay_s"] == pytest.approx(3.9)

    request, plugin = _request(
        "P1-TRK-007",
        {
            "product_semantics": PRODUCTS,
            "track_state_time_us": [2_000_000, 4_000_000, 6_000_000],
            "last_measurement_effective_time_us": [1_000_000, 2_000_000, 3_000_000],
        },
    )
    instance = _instance(dict(plugin(request)))
    assert instance["value_numeric"] == pytest.approx(2.0)
    evidence = instance["evidence"]
    assert isinstance(evidence, dict)
    assert evidence["p95_track_age_s"] == pytest.approx(2.9)
    assert evidence["max_track_age_s"] == pytest.approx(3.0)
