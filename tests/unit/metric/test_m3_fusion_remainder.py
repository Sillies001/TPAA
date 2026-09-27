from __future__ import annotations

import math
from pathlib import Path

import pytest

from tpaa_metric.catalog_engine import (
    M2MetricPluginRequest,
    MetricPluginRegistry,
    validate_m2_runtime_output,
)
from tpaa_metric.m3_fusion import (
    M3_FUS_ALLOWED_SYSTEM_TYPES,
    M3_FUS_CODES,
    M3_FUS_FAMILY,
    register_m3_fusion_plugins,
)
from tpaa_metric.m3_fusion_operators import M3_FUSION_OPERATOR_IMPLEMENTATIONS
from tpaa_metric.m3_general_engine import build_m3_metric_execution_plan
from tpaa_metric.operators import M2_OPERATOR_IMPLEMENTATIONS

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
HASH_A = "a" * 64


def _identity(prefix: str) -> dict[str, object]:
    return {
        f"{prefix}_id": f"{prefix}-id",
        f"{prefix}_version": "1.0.0",
        f"{prefix}_hash": HASH_A,
    }


def _quality_sample(
    *,
    domain: str,
    fused_field: str,
    fused: list[float],
    reference_field: str,
    reference: list[float],
    accepted: bool = True,
) -> dict[str, object]:
    return {
        "reference_match_accepted": accepted,
        "error_domain": domain,
        "fused_track_valid": True,
        "fusion_provenance_resolved": True,
        "association_resolved": True,
        "source_member_ids": ["RADAR:track-1", "IRST:track-9"],
        fused_field: fused,
        reference_field: reference,
    }


def _handover_event(
    event_id: str,
    *,
    preserved: bool,
    qualified: bool = True,
) -> dict[str, object]:
    return {
        "handover_event_id": event_id,
        "reference_target_id": "target-1",
        "pre_fused_track_id": f"{event_id}-pre",
        "post_fused_track_id": f"{event_id}-post",
        "handover_time_us": 2_000_000,
        "identity_preserved": preserved,
        "handover_profile_id": "handover-profile",
        "handover_profile_version": "1.0.0",
        "handover_profile_hash": HASH_A,
        "qualification_status": "QUALIFIED" if qualified else "REJECTED",
        "association_resolved": True,
        "fusion_provenance_resolved": True,
    }


def _inputs(system_type: str = "FUSION") -> dict[str, dict[str, object]]:
    return {
        "P1-FUS-001": {
            "system_type": system_type,
            **_identity("reference_match_quality_profile"),
            "samples": [
                _quality_sample(
                    domain="POSITION_3D",
                    fused_field="fused_track_position_ecef_m",
                    fused=[3.0, 4.0, 0.0],
                    reference_field="reference_target_position_ecef_m",
                    reference=[0.0, 0.0, 0.0],
                ),
                _quality_sample(
                    domain="POSITION_3D",
                    fused_field="fused_track_position_ecef_m",
                    fused=[0.0, 0.0, 13.0],
                    reference_field="reference_target_position_ecef_m",
                    reference=[0.0, 0.0, 0.0],
                ),
            ],
        },
        "P1-FUS-002": {
            "system_type": system_type,
            **_identity("reference_match_quality_profile"),
            "samples": [
                _quality_sample(
                    domain="VELOCITY_3D",
                    fused_field="fused_track_velocity_ecef_mps",
                    fused=[1.0, 0.0, 0.0],
                    reference_field="reference_target_velocity_ecef_mps",
                    reference=[0.0, 0.0, 0.0],
                ),
                _quality_sample(
                    domain="VELOCITY_3D",
                    fused_field="fused_track_velocity_ecef_mps",
                    fused=[0.0, 3.0, 0.0],
                    reference_field="reference_target_velocity_ecef_mps",
                    reference=[0.0, 0.0, 0.0],
                ),
            ],
        },
        "P1-FUS-003": {
            "system_type": system_type,
            "fused_update_id": "fused-update-1",
            "fused_state_effective_time_us": 5_000_000,
            "provenance_source_updates": [
                {
                    "source_id": "RADAR",
                    "sequence": 10,
                    "source_update_id": "src-radar-10",
                    "source_update_effective_time_us": 3_000_000,
                },
                {
                    "source_id": "IRST",
                    "sequence": 20,
                    "source_update_id": "src-irst-20",
                    "source_update_effective_time_us": 4_000_000,
                },
                {
                    "source_id": "EO",
                    "sequence": 30,
                    "source_update_id": "src-future-30",
                    "source_update_effective_time_us": 6_000_000,
                },
            ],
        },
        "P1-FUS-004": {
            "system_type": system_type,
            **_identity("opportunity_profile"),
            "fusion_provenance_resolved": True,
            "association_resolved": True,
            "fused_opportunity_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 10_000_000}
            ],
            "fused_track_valid_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 4_000_000},
                {"start_session_time_us": 6_000_000, "end_session_time_us": 10_000_000},
            ],
        },
        "P1-FUS-005": {
            "system_type": system_type,
            "profile": {"duplicate_persistence_s": 1.0},
            "fusion_provenance_resolved": True,
            "association_resolved": True,
            "eligible_target_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 10_000_000}
            ],
            "duplicate_episode_intervals": [
                {"start_session_time_us": 2_000_000, "end_session_time_us": 5_000_000},
                {"start_session_time_us": 7_000_000, "end_session_time_us": 7_500_000},
            ],
        },
        "P1-FUS-006": {
            "system_type": system_type,
            "source_track_membership": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 6_000_000,
                    "fused_track_id": "fused-1",
                    "source_track_id": "radar-1",
                    "reference_target_id": "target-1",
                    "membership_correct": True,
                },
                {
                    "start_session_time_us": 6_000_000,
                    "end_session_time_us": 8_000_000,
                    "fused_track_id": "fused-1",
                    "source_track_id": "irst-wrong",
                    "reference_target_id": "target-1",
                    "membership_correct": False,
                },
            ],
        },
        "P1-FUS-007": {
            "system_type": system_type,
            "handover_events": [
                _handover_event("handover-1", preserved=True),
                _handover_event("handover-2", preserved=False),
                _handover_event("handover-rejected", preserved=False, qualified=False),
            ],
        },
        "P1-FUS-008": {
            "system_type": system_type,
            "handover_event_id": "handover-jump-1",
            "reference_target_id": "target-1",
            "pre_fused_track_id": "fused-pre",
            "post_fused_track_id": "fused-post",
            "handover_time_us": 2_000_000,
            "qualification_status": "QUALIFIED",
            **_identity("handover_profile"),
            "pre_handover_state_time_us": 1_000_000,
            "fused_position_before": [0.0, 0.0, 0.0],
            "fused_velocity_before": [10.0, 0.0, 0.0],
            "fused_position_after": [130.0, 0.0, 0.0],
            "profile": {"max_propagation_age_us": 2_000_000},
        },
    }


def _upstream(code: str) -> tuple[tuple[str, str], ...]:
    if code in {"P1-FUS-001", "P1-FUS-002"}:
        return (("P1-QA-005", "5" * 64),)
    return ()


def _execute_direct(code: str, payload: dict[str, object]) -> dict[str, object]:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    register_m3_fusion_plugins(plan, registry)
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
            operator_id: M3_FUSION_OPERATOR_IMPLEMENTATIONS[operator_id]
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


def test_m3_fusion_membership_and_applicability_are_exact() -> None:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    definitions = tuple(
        sorted(
            (
                definition
                for definition in plan.definitions
                if definition.metric_code in M3_FUS_CODES
            ),
            key=lambda definition: definition.metric_code,
        )
    )
    assert tuple(item.metric_code for item in definitions) == M3_FUS_CODES
    assert {item.family for item in definitions} == {M3_FUS_FAMILY}
    assert all(
        item.applicability.applicability_mode == "SYSTEM_TYPE_EXACT"
        for item in definitions
    )
    assert all(
        item.applicability.allowed_system_types == M3_FUS_ALLOWED_SYSTEM_TYPES
        for item in definitions
    )


def test_m3_fusion_golden_outputs() -> None:
    inputs = _inputs()
    outputs = {code: _execute_direct(code, inputs[code]) for code in M3_FUS_CODES}

    assert _instance(outputs["P1-FUS-001"])["value_numeric"] == pytest.approx(
        math.sqrt(97.0)
    )
    assert _instance(outputs["P1-FUS-002"])["value_numeric"] == pytest.approx(
        math.sqrt(5.0)
    )
    assert _instance(outputs["P1-FUS-003"])["value_numeric"] == 1.0
    assert _instance(outputs["P1-FUS-004"])["value_numeric"] == 0.8
    assert _instance(outputs["P1-FUS-005"])["value_numeric"] == 0.7
    assert _instance(outputs["P1-FUS-006"])["value_numeric"] == 0.75
    assert _instance(outputs["P1-FUS-007"])["value_numeric"] == 0.5
    assert _instance(outputs["P1-FUS-008"])["value_numeric"] == 120.0


def test_m3_fusion_non_applicable_system_fails_closed() -> None:
    for code in M3_FUS_CODES:
        output = _execute_direct(code, {"system_type": "RADAR"})
        assert output["applicable"] is False
        assert output["instances"] == []


def test_m3_fusion_quality_causal_and_propagation_negatives_are_na() -> None:
    position = _inputs()["P1-FUS-001"]
    samples = position["samples"]
    assert isinstance(samples, list)
    for sample in samples:
        assert isinstance(sample, dict)
        sample["reference_match_accepted"] = False
    assert _instance(_execute_direct("P1-FUS-001", position))["status"] == "N_A"

    latency = _inputs()["P1-FUS-003"]
    updates = latency["provenance_source_updates"]
    assert isinstance(updates, list)
    for update in updates:
        assert isinstance(update, dict)
        update["source_update_effective_time_us"] = 6_000_000
    assert _instance(_execute_direct("P1-FUS-003", latency))["status"] == "N_A"

    jump = _inputs()["P1-FUS-008"]
    jump["pre_handover_state_time_us"] = 0
    jump["profile"] = {"max_propagation_age_us": 1_000_000}
    assert _instance(_execute_direct("P1-FUS-008", jump))["status"] == "N_A"


def test_cv_propagation_is_m3_overlay_only() -> None:
    assert "CV_PROPAGATION_V1" not in M2_OPERATOR_IMPLEMENTATIONS
    operator = M3_FUSION_OPERATOR_IMPLEMENTATIONS["CV_PROPAGATION_V1"]
    result = operator(
        [0.0, 1.0, 2.0],
        [10.0, 20.0, 30.0],
        start_time_us=1_000_000,
        end_time_us=1_500_000,
        max_propagation_age_us=1_000_000,
    )
    assert result == (5.0, 11.0, 17.0)
