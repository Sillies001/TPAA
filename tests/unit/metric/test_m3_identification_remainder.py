from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_metric.catalog_engine import (
    M2MetricPluginRequest,
    MetricPluginRegistry,
    validate_m2_runtime_output,
)
from tpaa_metric.m3_general_engine import build_m3_metric_execution_plan
from tpaa_metric.m3_identification import (
    M3_ID_CODES,
    M3_ID_FAMILY,
    M3_ID_REQUIRED_PRODUCT_SEMANTICS,
    register_m3_identification_plugins,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"

PRODUCTS = [M3_ID_REQUIRED_PRODUCT_SEMANTICS]
HASH_A = "a" * 64
HASH_B = "b" * 64


def _taxonomy_fields() -> dict[str, object]:
    return {
        "reference_classification_taxonomy_id": "tax-v1",
        "reference_classification_taxonomy_version": "1.0.0",
        "reference_classification_taxonomy_hash": HASH_A,
        "taxonomy": {
            "taxonomy_id": "tax-v1",
            "taxonomy_version": "1.0.0",
            "taxonomy_hash": HASH_A,
            "canonical_labels": ["FRIEND", "HOSTILE", "UNKNOWN"],
            "alias_map": {"F": "FRIEND", "H": "HOSTILE"},
            "unknown_label": "UNKNOWN",
        },
    }


def _class_intervals() -> list[dict[str, object]]:
    return [
        {
            "start_session_time_us": 0,
            "end_session_time_us": 6_000_000,
            "track_id": "T1",
            "reference_target_id": "R1",
            "reported_classification": "F",
            "reference_classification": "FRIEND",
            "association_resolved": True,
            "reference_quality_status": "VALID",
        },
        {
            "start_session_time_us": 6_000_000,
            "end_session_time_us": 8_000_000,
            "track_id": "T1",
            "reference_target_id": "R1",
            "reported_classification": "HOSTILE",
            "reference_classification": "FRIEND",
            "association_resolved": True,
            "reference_quality_status": "VALID",
        },
        {
            "start_session_time_us": 8_000_000,
            "end_session_time_us": 10_000_000,
            "track_id": "T1",
            "reference_target_id": "R1",
            "reported_classification": "UNKNOWN",
            "reference_classification": "FRIEND",
            "association_resolved": True,
            "reference_quality_status": "VALID",
        },
    ]


def _golden_payloads(
    products: list[str] | None = None,
) -> dict[str, dict[str, object]]:
    product_semantics = PRODUCTS if products is None else products
    taxonomy = _taxonomy_fields()
    return {
        "P1-ID-001": {
            "product_semantics": product_semantics,
            "association_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 8_000_000,
                    "track_id": "T1",
                    "reference_target_id": "R1",
                    "association_state": "CORRECT",
                },
                {
                    "start_session_time_us": 8_000_000,
                    "end_session_time_us": 10_000_000,
                    "track_id": "T1",
                    "reference_target_id": "R2",
                    "association_state": "WRONG",
                },
            ],
        },
        "P1-ID-002": {
            "product_semantics": product_semantics,
            "association_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 2_000_000,
                    "track_id": "T1",
                    "reference_target_id": "R2",
                    "association_state": "WRONG",
                },
                {
                    "start_session_time_us": 2_000_000,
                    "end_session_time_us": 3_000_000,
                    "track_id": "T1",
                    "reference_target_id": "R1",
                    "association_state": "CORRECT",
                },
                {
                    "start_session_time_us": 3_000_000,
                    "end_session_time_us": 5_000_000,
                    "track_id": "T1",
                    "reference_target_id": "R2",
                    "association_state": "WRONG",
                },
            ],
        },
        "P1-ID-003": {
            "product_semantics": product_semantics,
            "profile": {"swap_persistence_s": 2.0},
            "association_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 1_000_000,
                    "track_id": "A",
                    "reference_target_id": "R1",
                },
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 1_000_000,
                    "track_id": "B",
                    "reference_target_id": "R2",
                },
                {
                    "start_session_time_us": 1_000_000,
                    "end_session_time_us": 4_000_000,
                    "track_id": "A",
                    "reference_target_id": "R2",
                },
                {
                    "start_session_time_us": 1_000_000,
                    "end_session_time_us": 4_000_000,
                    "track_id": "B",
                    "reference_target_id": "R1",
                },
            ],
        },
        "P1-ID-004": {
            "product_semantics": product_semantics,
            "profile": {"split_persistence_s": 2.0},
            "association_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 5_000_000,
                    "track_id": "A",
                    "reference_target_id": "R1",
                },
                {
                    "start_session_time_us": 1_000_000,
                    "end_session_time_us": 4_000_000,
                    "track_id": "B",
                    "reference_target_id": "R1",
                },
            ],
        },
        "P1-ID-005": {
            "product_semantics": product_semantics,
            "profile": {"merge_persistence_s": 2.0},
            "association_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 5_000_000,
                    "track_id": "A",
                    "reference_target_id": "R1",
                },
                {
                    "start_session_time_us": 1_000_000,
                    "end_session_time_us": 4_000_000,
                    "track_id": "A",
                    "reference_target_id": "R2",
                },
            ],
        },
        "P1-ID-006": {
            "product_semantics": product_semantics,
            "profile": {"duplicate_persistence_s": 2.0},
            "association_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 10_000_000,
                    "track_id": "A",
                    "reference_target_id": "R1",
                },
                {
                    "start_session_time_us": 2_000_000,
                    "end_session_time_us": 6_000_000,
                    "track_id": "B",
                    "reference_target_id": "R1",
                },
            ],
        },
        "P1-ID-007": {
            "product_semantics": product_semantics,
            "profile": {
                "identity_persistence_s": 2.0,
                "max_gap_us": 0,
            },
            "association_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 6_000_000,
                    "track_id": "A",
                    "reference_target_id": "R1",
                },
                {
                    "start_session_time_us": 6_000_000,
                    "end_session_time_us": 10_000_000,
                    "track_id": "B",
                    "reference_target_id": "R1",
                },
            ],
        },
        "P1-ID-008": {
            "product_semantics": product_semantics,
            **taxonomy,
            "classification_intervals": _class_intervals(),
        },
        "P1-ID-009": {
            "product_semantics": product_semantics,
            **taxonomy,
            "classification_intervals": _class_intervals(),
        },
        "P1-ID-010": {
            "product_semantics": product_semantics,
            "reported_classification_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 6_000_000,
                    "reported_classification": "FRIEND",
                    "association_resolved": True,
                },
                {
                    "start_session_time_us": 6_000_000,
                    "end_session_time_us": 8_000_000,
                    "reported_classification": "HOSTILE",
                    "association_resolved": True,
                },
                {
                    "start_session_time_us": 8_000_000,
                    "end_session_time_us": 10_000_000,
                    "reported_classification": "UNKNOWN",
                    "association_resolved": True,
                },
            ],
        },
        "P1-ID-011": {
            "product_semantics": product_semantics,
            **taxonomy,
            "stable_track_start_time_us": 1_000_000,
            "first_stable_non_unknown_correct_id_time_us": 3_500_000,
            "profile": {
                "stable_track_persistence_s": 1.0,
                "id_stability_persistence_s": 1.0,
                "max_gap_us": 100_000,
            },
        },
        "P1-ID-012": {
            "product_semantics": product_semantics,
            **taxonomy,
            "profile": {
                "id_stability_persistence_s": 1.0,
                "max_gap_us": 0,
            },
            "classification_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 2_000_000,
                    "track_id": "T1",
                    "reference_target_id": "R1",
                    "reported_classification": "F",
                    "reference_classification": "FRIEND",
                    "association_resolved": True,
                    "reference_quality_status": "VALID",
                },
                {
                    "start_session_time_us": 2_000_000,
                    "end_session_time_us": 4_000_000,
                    "track_id": "T1",
                    "reference_target_id": "R1",
                    "reported_classification": "HOSTILE",
                    "reference_classification": "FRIEND",
                    "association_resolved": True,
                    "reference_quality_status": "VALID",
                },
                {
                    "start_session_time_us": 4_000_000,
                    "end_session_time_us": 6_000_000,
                    "track_id": "T1",
                    "reference_target_id": "R1",
                    "reported_classification": "FRIEND",
                    "reference_classification": "FRIEND",
                    "association_resolved": True,
                    "reference_quality_status": "VALID",
                },
            ],
        },
    }


def _request(
    code: str,
    payload: dict[str, object],
) -> tuple[M2MetricPluginRequest, object]:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    register_m3_identification_plugins(plan, registry)
    definition = plan.definition(code)
    _plugin_id, plugin = registry.resolve(
        definition.algorithm_id,
        definition.algorithm_version,
    )
    request = M2MetricPluginRequest(
        definition=definition,
        input_payload=payload,
        upstream_result_hashes=(),
        operators={},
    )
    return request, plugin


def _instance(output: object) -> dict[str, object]:
    assert isinstance(output, dict)
    raw = output["instances"]
    assert isinstance(raw, list) and len(raw) == 1
    assert isinstance(raw[0], dict)
    return raw[0]


def test_m3_identification_membership_and_product_applicability_are_exact() -> None:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    definitions = tuple(
        sorted(
            (
                definition
                for definition in plan.definitions
                if definition.metric_code in M3_ID_CODES
            ),
            key=lambda definition: definition.metric_code,
        )
    )
    assert tuple(item.metric_code for item in definitions) == M3_ID_CODES
    assert {item.family for item in definitions} == {M3_ID_FAMILY}
    assert all(item.operator_bindings == () for item in definitions)
    assert all(
        item.applicability.applicability_mode == "PRODUCT_CAPABILITY"
        and item.applicability.required_product_semantics
        == M3_ID_REQUIRED_PRODUCT_SEMANTICS
        for item in definitions
    )


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("P1-ID-001", 0.8),
        ("P1-ID-002", 2.0),
        ("P1-ID-003", 1.0),
        ("P1-ID-004", 1.0),
        ("P1-ID-005", 1.0),
        ("P1-ID-006", 0.4),
        ("P1-ID-007", 0.6),
        ("P1-ID-008", 0.75),
        ("P1-ID-009", 0.25),
        ("P1-ID-010", 0.2),
        ("P1-ID-011", 2.5),
        ("P1-ID-012", 0.4),
    ],
)
def test_m3_identification_golden_values(code: str, expected: float) -> None:
    payload = _golden_payloads()[code]
    request, plugin = _request(code, payload)
    output = plugin(request)
    validate_m2_runtime_output(request.definition, payload, output)
    assert _instance(output)["value_numeric"] == pytest.approx(expected)


@pytest.mark.parametrize("code", M3_ID_CODES)
def test_m3_identification_non_capable_product_fails_closed(code: str) -> None:
    payload: dict[str, object] = {"product_semantics": []}
    request, plugin = _request(code, payload)
    output = plugin(request)
    validate_m2_runtime_output(request.definition, payload, output)
    assert output["applicable"] is False
    assert output["instances"] == []


def test_m3_identification_taxonomy_identity_mismatch_fails_closed() -> None:
    payload = _golden_payloads()["P1-ID-008"]
    payload["reference_classification_taxonomy_hash"] = HASH_B
    request, plugin = _request("P1-ID-008", payload)
    with pytest.raises(ValueError, match="M3_ID_TAXONOMY_IDENTITY_MISMATCH"):
        plugin(request)


def test_m3_identification_stability_requires_stable_correct_episode() -> None:
    payload = _golden_payloads()["P1-ID-012"]
    rows = payload["classification_intervals"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        row["reported_classification"] = "UNKNOWN"
    request, plugin = _request("P1-ID-012", payload)
    output = plugin(request)
    assert _instance(output)["status"] == "N_A"
    assert _instance(output)["reason_codes"] == ["NO_STABLE_CORRECT_IDENTIFICATION"]
