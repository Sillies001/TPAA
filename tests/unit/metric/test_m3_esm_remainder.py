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
from tpaa_metric.m3_esm import (
    M3_ESM_ALLOWED_SYSTEM_TYPES,
    M3_ESM_CODES,
    M3_ESM_FAMILY,
    register_m3_esm_plugins,
)
from tpaa_metric.m3_general_engine import build_m3_metric_execution_plan

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
HASH_A = "a" * 64


def _identity(prefix: str) -> dict[str, object]:
    return {
        f"{prefix}_id": f"{prefix}-id",
        f"{prefix}_version": "1.0.0",
        f"{prefix}_hash": HASH_A,
    }


def _inputs(system_type: str = "RWR") -> dict[str, dict[str, object]]:
    taxonomy = {
        "taxonomy_id": "esm-taxonomy",
        "taxonomy_version": "1.0.0",
        "taxonomy_hash": HASH_A,
        "canonical_labels": ["FRIEND", "FOE", "UNKNOWN"],
        "alias_map": {"hostile": "FOE"},
        "unknown_label": "UNKNOWN",
    }
    return {
        "P1-ESM-001": {
            "system_type": system_type,
            **_identity("opportunity_profile"),
            **_identity("confirmation_profile"),
            "emitter_opportunity_intervals": [
                {
                    "detection_opportunity_id": "opp-1",
                    "reference_emitter_id": "emitter-1",
                    "start_session_time_us": 0,
                    "end_session_time_us": 2_000_000,
                },
                {
                    "detection_opportunity_id": "opp-2",
                    "reference_emitter_id": "emitter-2",
                    "start_session_time_us": 2_000_000,
                    "end_session_time_us": 4_000_000,
                },
                {
                    "detection_opportunity_id": "opp-3",
                    "reference_emitter_id": "emitter-3",
                    "start_session_time_us": 4_000_000,
                    "end_session_time_us": 6_000_000,
                },
            ],
            "confirmation_events": [
                {
                    "detection_confirmation_event_id": "confirm-1",
                    "detection_opportunity_id": "opp-1",
                    "reference_emitter_id": "emitter-1",
                },
                {
                    "detection_confirmation_event_id": "confirm-3",
                    "detection_opportunity_id": "opp-3",
                    "reference_emitter_id": "emitter-3",
                },
            ],
        },
        "P1-ESM-002": {
            "system_type": system_type,
            **_identity("reference_match_quality_profile"),
            "samples": [
                {
                    "reported_bearing_rad": math.pi - 0.1,
                    "reference_bearing_rad": -math.pi + 0.1,
                    "reference_match_accepted": True,
                    "error_domain": "BEARING",
                },
                {
                    "reported_bearing_rad": 0.1,
                    "reference_bearing_rad": 0.0,
                    "reference_match_accepted": True,
                    "error_domain": "BEARING",
                },
            ],
        },
        "P1-ESM-003": {
            "system_type": system_type,
            **_identity("opportunity_profile"),
            **_identity("confirmation_profile"),
            "detection_opportunity_id": "opp-latency",
            "detection_confirmation_event_id": "confirm-latency",
            "opportunity_start_time_us": 1_000_000,
            "first_confirmed_detection_time_us": 2_500_000,
        },
        "P1-ESM-004": {
            "system_type": system_type,
            "association_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 6_000_000,
                    "esm_emitter_track_id": "esm-1",
                    "reference_emitter_id": "emitter-1",
                    "association_state": "CORRECT",
                },
                {
                    "start_session_time_us": 6_000_000,
                    "end_session_time_us": 8_000_000,
                    "esm_emitter_track_id": "esm-1",
                    "reference_emitter_id": "emitter-2",
                    "association_state": "WRONG",
                },
            ],
        },
        "P1-ESM-005": {
            "system_type": system_type,
            "reference_classification_taxonomy_id": "esm-taxonomy",
            "reference_classification_taxonomy_version": "1.0.0",
            "reference_classification_taxonomy_hash": HASH_A,
            "taxonomy": taxonomy,
            "classification_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 4_000_000,
                    "reported_emitter_class": "FRIEND",
                    "reference_emitter_class": "FRIEND",
                    "association_resolved": True,
                    "reference_quality_status": "VALID",
                },
                {
                    "start_session_time_us": 4_000_000,
                    "end_session_time_us": 6_000_000,
                    "reported_emitter_class": "hostile",
                    "reference_emitter_class": "FRIEND",
                    "association_resolved": True,
                    "reference_quality_status": "VALID",
                },
                {
                    "start_session_time_us": 6_000_000,
                    "end_session_time_us": 7_000_000,
                    "reported_emitter_class": "UNKNOWN",
                    "reference_emitter_class": "FOE",
                    "association_resolved": True,
                    "reference_quality_status": "VALID",
                },
            ],
        },
        "P1-ESM-006": {
            "system_type": system_type,
            **_identity("opportunity_profile"),
            "emitter_opportunity_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 10_000_000}
            ],
            "esm_track_valid_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 4_000_000},
                {"start_session_time_us": 6_000_000, "end_session_time_us": 10_000_000},
            ],
        },
    }


def _execute_direct(
    code: str,
    payload: dict[str, object],
) -> dict[str, object]:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    register_m3_esm_plugins(plan, registry)
    definition = plan.definition(code)
    _plugin_id, plugin = registry.resolve(
        definition.algorithm_id,
        definition.algorithm_version,
    )
    request = M2MetricPluginRequest(
        definition=definition,
        input_payload=payload,
        upstream_result_hashes=(),
        operators={
            operator_id: M3_AIR_OPERATOR_IMPLEMENTATIONS[operator_id]
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


def test_m3_esm_membership_and_applicability_are_exact() -> None:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    definitions = tuple(
        sorted(
            (
                definition
                for definition in plan.definitions
                if definition.metric_code in M3_ESM_CODES
            ),
            key=lambda definition: definition.metric_code,
        )
    )
    assert tuple(item.metric_code for item in definitions) == M3_ESM_CODES
    assert {item.family for item in definitions} == {M3_ESM_FAMILY}
    assert all(item.applicability.applicability_mode == "SYSTEM_TYPE_SET" for item in definitions)
    assert all(
        item.applicability.allowed_system_types == M3_ESM_ALLOWED_SYSTEM_TYPES
        for item in definitions
    )


@pytest.mark.parametrize("system_type", M3_ESM_ALLOWED_SYSTEM_TYPES)
def test_m3_esm_golden_outputs_for_rwr_and_esm(system_type: str) -> None:
    inputs = _inputs(system_type)
    outputs = {code: _execute_direct(code, inputs[code]) for code in M3_ESM_CODES}

    assert _instance(outputs["P1-ESM-001"])["value_numeric"] == pytest.approx(2.0 / 3.0)
    assert _instance(outputs["P1-ESM-002"])["value_numeric"] == pytest.approx(
        math.sqrt(0.025)
    )
    assert _instance(outputs["P1-ESM-003"])["value_numeric"] == 1.5
    assert _instance(outputs["P1-ESM-004"])["value_numeric"] == 0.75
    assert _instance(outputs["P1-ESM-005"])["value_numeric"] == pytest.approx(2.0 / 3.0)
    assert _instance(outputs["P1-ESM-006"])["value_numeric"] == 0.8
    evidence = _instance(outputs["P1-ESM-005"])["evidence"]
    assert isinstance(evidence, dict)
    assert "canonical_confusion_matrix_dwell_us" in evidence


def test_m3_esm_non_applicable_system_fails_closed() -> None:
    for code in M3_ESM_CODES:
        output = _execute_direct(code, {"system_type": "RADAR"})
        assert output["applicable"] is False
        assert output["instances"] == []


def test_m3_esm_reference_quality_and_taxonomy_negatives_fail_closed() -> None:
    bearing = _inputs()["P1-ESM-002"]
    bearing["samples"] = [
        {
            "reference_match_accepted": False,
            "error_domain": "BEARING",
        }
    ]
    output = _execute_direct("P1-ESM-002", bearing)
    instance = _instance(output)
    assert instance["status"] == "N_A"
    assert instance["value_numeric"] is None

    classification = _inputs()["P1-ESM-005"]
    classification["reference_classification_taxonomy_hash"] = "b" * 64
    with pytest.raises(ValueError, match="M3_ESM_TAXONOMY_IDENTITY_MISMATCH"):
        _execute_direct("P1-ESM-005", classification)


def test_m3_esm_confirmation_association_mismatch_is_rejected() -> None:
    payload = _inputs()["P1-ESM-001"]
    confirmations = payload["confirmation_events"]
    assert isinstance(confirmations, list)
    assert isinstance(confirmations[0], dict)
    confirmations[0]["reference_emitter_id"] = "wrong-emitter"
    with pytest.raises(ValueError, match="M3_ESM_CONFIRMATION_ASSOCIATION_MISMATCH"):
        _execute_direct("P1-ESM-001", payload)
