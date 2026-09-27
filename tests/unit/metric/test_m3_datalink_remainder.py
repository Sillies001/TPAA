from __future__ import annotations

import math
from pathlib import Path

import pytest

from tpaa_metric.catalog_engine import (
    M2MetricPluginRequest,
    MetricPluginRegistry,
    validate_m2_runtime_output,
)
from tpaa_metric.m3_datalink import (
    M3_DL_ALLOWED_SYSTEM_TYPES,
    M3_DL_CODES,
    M3_DL_FAMILY,
    register_m3_datalink_plugins,
)
from tpaa_metric.m3_datalink_operators import M3_DATALINK_OPERATOR_IMPLEMENTATIONS
from tpaa_metric.m3_general_engine import build_m3_metric_execution_plan
from tpaa_metric.operators import M2_OPERATOR_IMPLEMENTATIONS

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
HASH_A = "a" * 64
HASH_B = "b" * 64


def _identity(prefix: str, digest: str = HASH_A) -> dict[str, object]:
    return {
        f"{prefix}_id": f"{prefix}-id",
        f"{prefix}_version": "1.0.0",
        f"{prefix}_hash": digest,
    }


def _domain() -> dict[str, int]:
    return {"minimum": 0, "maximum": 15, "modulus": 16}


def _quality_sample(
    *,
    domain: str,
    remote_field: str,
    remote: list[float],
    reference_field: str,
    reference: list[float],
    accepted: bool = True,
) -> dict[str, object]:
    return {
        "reference_match_accepted": accepted,
        "error_domain": domain,
        "remote_track_valid": True,
        "association_resolved": True,
        "link_endpoint_id": "link-1",
        remote_field: remote,
        reference_field: reference,
    }


def _inputs(system_type: str = "DATALINK") -> dict[str, dict[str, object]]:
    return {
        "P1-DL-001": {
            "system_type": system_type,
            "link_endpoint_id": "link-1",
            "message_send_time_us": 1_000_000,
            "message_receive_time_us": 2_500_000,
        },
        "P1-DL-002": {
            "system_type": system_type,
            "profile": {
                "min_message_count": 5,
                "max_gap_us": 1_000_000,
            },
            "message_latency_series": [
                {"session_time_us": 0, "message_latency_us": 100_000.0},
                {"session_time_us": 100_000, "message_latency_us": 110_000.0},
                {"session_time_us": 200_000, "message_latency_us": 130_000.0},
                {"session_time_us": 300_000, "message_latency_us": 120_000.0},
                {"session_time_us": 400_000, "message_latency_us": 500_000.0},
            ],
        },
        "P1-DL-003": {
            "system_type": system_type,
            "sequence_epochs": [
                {
                    "sequence_epoch_id": "epoch-1",
                    "link_endpoint_id": "link-1",
                    "expected_sequence_domain": _domain(),
                    "observed_sequence_positions": [14, 15, 1, 2],
                }
            ],
        },
        "P1-DL-004": {
            "system_type": system_type,
            "sequence_epochs": [
                {
                    "sequence_epoch_id": "epoch-1",
                    "link_endpoint_id": "link-1",
                    "expected_sequence_domain": _domain(),
                    "received_messages": [
                        {"receive_order": 1, "sequence_position": 10},
                        {"receive_order": 2, "sequence_position": 12},
                        {"receive_order": 3, "sequence_position": 11},
                        {"receive_order": 4, "sequence_position": 13},
                    ],
                }
            ],
        },
        "P1-DL-005": {
            "system_type": system_type,
            "link_endpoint_id": "link-1",
            "remote_track_valid": True,
            "remote_track_effective_time_us": 2_000_000,
            "local_use_time_us": 4_500_000,
        },
        "P1-DL-006": {
            "system_type": system_type,
            **_identity("reference_match_quality_profile"),
            "samples": [
                _quality_sample(
                    domain="POSITION_3D",
                    remote_field="remote_track_position_ecef_m",
                    remote=[3.0, 4.0, 0.0],
                    reference_field="reference_target_position_ecef_m",
                    reference=[0.0, 0.0, 0.0],
                ),
                _quality_sample(
                    domain="POSITION_3D",
                    remote_field="remote_track_position_ecef_m",
                    remote=[0.0, 0.0, 13.0],
                    reference_field="reference_target_position_ecef_m",
                    reference=[0.0, 0.0, 0.0],
                ),
            ],
        },
        "P1-DL-007": {
            "system_type": system_type,
            **_identity("reference_match_quality_profile", HASH_B),
            "samples": [
                _quality_sample(
                    domain="VELOCITY_3D",
                    remote_field="remote_track_velocity_ecef_mps",
                    remote=[1.0, 0.0, 0.0],
                    reference_field="reference_target_velocity_ecef_mps",
                    reference=[0.0, 0.0, 0.0],
                ),
                _quality_sample(
                    domain="VELOCITY_3D",
                    remote_field="remote_track_velocity_ecef_mps",
                    remote=[0.0, 3.0, 0.0],
                    reference_field="reference_target_velocity_ecef_mps",
                    reference=[0.0, 0.0, 0.0],
                ),
            ],
        },
        "P1-DL-008": {
            "system_type": system_type,
            **_identity("opportunity_profile"),
            "link_endpoint_id": "link-1",
            "remote_track_opportunity_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 10_000_000}
            ],
            "remote_track_valid_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 4_000_000},
                {"start_session_time_us": 6_000_000, "end_session_time_us": 10_000_000},
            ],
        },
    }


def _upstream(code: str) -> tuple[tuple[str, str], ...]:
    if code == "P1-DL-002":
        return (("P1-DL-001", "1" * 64),)
    if code in {"P1-DL-006", "P1-DL-007"}:
        return (("P1-QA-005", "5" * 64),)
    return ()


def _execute_direct(
    code: str,
    payload: dict[str, object],
) -> dict[str, object]:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    register_m3_datalink_plugins(plan, registry)
    definition = plan.definition(code)
    _plugin_id, plugin = registry.resolve(
        definition.algorithm_id,
        definition.algorithm_version,
    )
    request = M2MetricPluginRequest(
        definition=definition,
        input_payload=payload,
        upstream_result_hashes=_upstream(code),
        operators={
            operator_id: M3_DATALINK_OPERATOR_IMPLEMENTATIONS[operator_id]
            for operator_id in definition.operator_bindings
        },
    )
    output = dict(plugin(request))
    validate_m2_runtime_output(definition, payload, output)
    return output


def _instance(output: dict[str, object]) -> dict[str, object]:
    raw = output["instances"]
    assert isinstance(raw, list) and len(raw) == 1
    assert isinstance(raw[0], dict)
    return raw[0]


def test_m3_datalink_membership_and_applicability_are_exact() -> None:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    definitions = tuple(
        sorted(
            (
                definition
                for definition in plan.definitions
                if definition.metric_code in M3_DL_CODES
            ),
            key=lambda definition: definition.metric_code,
        )
    )
    assert tuple(item.metric_code for item in definitions) == M3_DL_CODES
    assert {item.family for item in definitions} == {M3_DL_FAMILY}
    assert all(
        item.applicability.applicability_mode == "SYSTEM_TYPE_EXACT"
        for item in definitions
    )
    assert all(
        item.applicability.allowed_system_types == M3_DL_ALLOWED_SYSTEM_TYPES
        for item in definitions
    )


def test_m3_datalink_golden_outputs() -> None:
    inputs = _inputs()
    outputs = {code: _execute_direct(code, inputs[code]) for code in M3_DL_CODES}

    assert _instance(outputs["P1-DL-001"])["value_numeric"] == 1.5
    assert _instance(outputs["P1-DL-002"])["value_numeric"] == 0.01
    assert _instance(outputs["P1-DL-003"])["value_numeric"] == 0.2
    assert _instance(outputs["P1-DL-004"])["value_numeric"] == 0.25
    assert _instance(outputs["P1-DL-005"])["value_numeric"] == 2.5
    assert _instance(outputs["P1-DL-006"])["value_numeric"] == pytest.approx(
        math.sqrt(97.0)
    )
    assert _instance(outputs["P1-DL-007"])["value_numeric"] == pytest.approx(
        math.sqrt(5.0)
    )
    assert _instance(outputs["P1-DL-008"])["value_numeric"] == 0.8


def test_m3_datalink_non_applicable_system_fails_closed() -> None:
    for code in M3_DL_CODES:
        output = _execute_direct(code, {"system_type": "RADAR"})
        assert output["applicable"] is False
        assert output["instances"] == []


def test_m3_datalink_jitter_gap_and_quality_rejection_are_na() -> None:
    jitter = _inputs()["P1-DL-002"]
    series = jitter["message_latency_series"]
    assert isinstance(series, list)
    assert isinstance(series[-1], dict)
    series[-1]["session_time_us"] = 2_000_000
    jitter_output = _execute_direct("P1-DL-002", jitter)
    assert _instance(jitter_output)["status"] == "N_A"

    position = _inputs()["P1-DL-006"]
    samples = position["samples"]
    assert isinstance(samples, list)
    for sample in samples:
        assert isinstance(sample, dict)
        sample["reference_match_accepted"] = False
    position_output = _execute_direct("P1-DL-006", position)
    assert _instance(position_output)["status"] == "N_A"
    assert _instance(position_output)["value_numeric"] is None


def test_m3_datalink_negative_latency_is_rejected() -> None:
    payload = _inputs()["P1-DL-001"]
    payload["message_receive_time_us"] = 999_999
    with pytest.raises(ValueError, match="M3_DL_NEGATIVE_MESSAGE_LATENCY"):
        _execute_direct("P1-DL-001", payload)


def test_mad_is_m3_overlay_only_and_deterministic() -> None:
    assert "MAD_V1" not in M2_OPERATOR_IMPLEMENTATIONS
    mad = M3_DATALINK_OPERATOR_IMPLEMENTATIONS["MAD_V1"]
    values = [100_000.0, 110_000.0, 130_000.0, 120_000.0, 500_000.0]
    assert mad(values) == 10_000.0
    assert mad(tuple(reversed(values))) == 10_000.0
