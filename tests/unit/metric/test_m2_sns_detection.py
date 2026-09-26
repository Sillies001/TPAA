from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from tpaa_metric import (
    SNS_DETECTION_CODES,
    CatalogMetricEngine,
    CatalogMetricEngineError,
    M2MetricPluginRequest,
    MetricPluginRegistry,
    build_m2_metric_execution_plan,
    build_m2_sns_detection_inputs,
    register_m2_sns_detection_plugins,
)
from tpaa_metric.operators import M2_OPERATOR_IMPLEMENTATIONS
from tpaa_metric.qa_foundation import register_m2_qa_plugins
from tpaa_world import project_m2_stage_world_lineage

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
M1_FIXTURES = ROOT / "tests" / "fixtures" / "m1"
M2_FIXTURES = ROOT / "tests" / "fixtures" / "m2"


def _opportunity(
    opportunity_id: str,
    start: int,
    end: int,
    *,
    status: str = "VALID",
    system_id: str = "radar-1",
) -> dict[str, object]:
    return {
        "opportunity_id": opportunity_id,
        "reference_entity_id": "target-1",
        "evaluated_system_instance_id": system_id,
        "start_session_time_us": start,
        "end_session_time_us": end,
        "validity_status": status,
        "opportunity_profile_id": "SNS_OPPORTUNITY_V1",
        "opportunity_profile_version": "1.0.0",
        "opportunity_profile_hash": "a" * 64,
        "eligibility_reason": "FROZEN_PROFILE_ELIGIBLE",
        "eligibility_provenance": "wre:synthetic-contract:v1",
    }


def _confirmation(
    opportunity_id: str,
    timestamp: int,
) -> dict[str, object]:
    return {
        "confirmation_event_id": f"confirmation-{opportunity_id}",
        "opportunity_id": opportunity_id,
        "reference_entity_id": "target-1",
        "first_confirmed_detection_time_us": timestamp,
        "confirmation_profile_id": "SNS_CONFIRMATION_V1",
        "confirmation_profile_version": "1.0.0",
        "confirmation_profile_hash": "b" * 64,
        "confirmation_persistence_s": 0.5,
        "association_provenance": "association:synthetic:v1",
    }


def _payload() -> dict[str, object]:
    return {
        "system_type": "RADAR",
        "mission_system_instance_id": "radar-1",
        "opportunities": [
            _opportunity("opp-1", 0, 4_000_000),
            _opportunity("opp-invalid", 4_000_000, 6_000_000, status="INVALID"),
            _opportunity("opp-2", 6_000_000, 10_000_000),
        ],
        "confirmations": [
            _confirmation("opp-1", 3_200_000),
            _confirmation("opp-2", 7_000_000),
        ],
        "target_presence_intervals": [
            {
                "evaluated_system_instance_id": "radar-1",
                "reference_entity_id": "target-1",
                "start_session_time_us": 0,
                "end_session_time_us": 10_000_000,
                "presence_provenance": "reference:synthetic:v1",
            }
        ],
        "reference_range_samples": [
            {
                "reference_state_id": "range-1-left",
                "reference_entity_id": "target-1",
                "session_time_us": 3_180_000,
                "reference_range_m": 6_820.0,
            },
            {
                "reference_state_id": "range-1-right",
                "reference_entity_id": "target-1",
                "session_time_us": 3_220_000,
                "reference_range_m": 6_780.0,
            },
            {
                "reference_state_id": "range-2-left",
                "reference_entity_id": "target-1",
                "session_time_us": 6_980_000,
                "reference_range_m": 3_020.0,
            },
            {
                "reference_state_id": "range-2-right",
                "reference_entity_id": "target-1",
                "session_time_us": 7_020_000,
                "reference_range_m": 2_980.0,
            },
        ],
        "interpolation_max_gap_us": 50_000,
    }


def _runtime(payload: Mapping[str, object] | None = None):
    plan = build_m2_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    register_m2_qa_plugins(plan, registry)
    register_m2_sns_detection_plugins(plan, registry)
    inputs = {code: dict(payload or _payload()) for code in SNS_DETECTION_CODES}
    inputs["P1-QA-005"] = {
        "samples": [
            {
                "measurement_time_us": 1_000_000,
                "left_truth_time_us": 980_000,
                "right_truth_time_us": 1_020_000,
                "profile.max_gap_us": 50_000,
            }
        ]
    }
    return plan, registry, inputs, CatalogMetricEngine(plan, registry)


def _direct_outputs(payload: Mapping[str, object] | None = None) -> dict[str, object]:
    plan, registry, inputs, _engine = _runtime(payload)
    result: dict[str, object] = {}
    for code in SNS_DETECTION_CODES:
        definition = plan.definition(code)
        _plugin_id, plugin = registry.resolve(
            definition.algorithm_id,
            definition.algorithm_version,
        )
        result[code] = plugin(
            M2MetricPluginRequest(
                definition=definition,
                input_payload=inputs[code],
                upstream_result_hashes=(),
                operators={
                    operator_id: M2_OPERATOR_IMPLEMENTATIONS[operator_id]
                    for operator_id in definition.operator_bindings
                },
            )
        )
    return result


def test_sns_detection_exact_catalog_and_golden_outputs() -> None:
    plan, registry, inputs, engine = _runtime()
    batch = engine.execute(inputs, metric_codes=SNS_DETECTION_CODES)
    outputs = _direct_outputs()

    assert batch.metric_codes == ("P1-QA-005", *SNS_DETECTION_CODES)
    assert {plan.definition(code).algorithm_id for code in SNS_DETECTION_CODES} <= set(
        registry.plugin_ids
    )
    assert {
        (algorithm_id, algorithm_version)
        for algorithm_id, algorithm_version, _plugin_id in registry.plugin_identity_manifest
        if algorithm_id in {plan.definition(code).algorithm_id for code in SNS_DETECTION_CODES}
    } == {
        (plan.definition(code).algorithm_id, plan.definition(code).algorithm_version)
        for code in SNS_DETECTION_CODES
    }
    assert outputs["P1-SNS-001"]["instances"][0]["value_numeric"] == 0.8
    assert outputs["P1-SNS-002"]["instances"][0]["value_numeric"] == 1.0
    assert [item["value_numeric"] for item in outputs["P1-SNS-003"]["instances"]] == [
        3.2,
        1.0,
    ]
    assert [item["value_numeric"] for item in outputs["P1-SNS-004"]["instances"]] == [
        6_800.0,
        3_000.0,
    ]


def test_sns_002_known_ten_opportunities_eight_detections_excludes_invalid() -> None:
    payload = _payload()
    payload["opportunities"] = [
        *[_opportunity(f"opp-{index}", index * 10, index * 10 + 9) for index in range(10)],
        _opportunity("invalid", 200, 210, status="INVALID"),
    ]
    payload["confirmations"] = [_confirmation(f"opp-{index}", index * 10 + 3) for index in range(8)]
    output = _direct_outputs(payload)["P1-SNS-002"]
    assert output["instances"][0]["value_numeric"] == 0.8
    assert output["instances"][0]["evidence"]["invalid_opportunity_count"] == 1


def test_sns_missing_detection_and_range_gap_fail_closed_to_na() -> None:
    payload = _payload()
    payload["confirmations"] = [_confirmation("opp-1", 3_200_000)]
    payload["interpolation_max_gap_us"] = 10_000
    outputs = _direct_outputs(payload)
    assert outputs["P1-SNS-003"]["instances"][1]["status"] == "N_A"
    assert outputs["P1-SNS-003"]["instances"][1]["reason_codes"] == ["NO_CONFIRMED_DETECTION"]
    assert outputs["P1-SNS-004"]["instances"][0]["status"] == "N_A"
    assert outputs["P1-SNS-004"]["instances"][0]["reason_codes"] == [
        "REFERENCE_RANGE_MATCH_UNAVAILABLE"
    ]


def test_non_radar_applicability_emits_no_fake_instances() -> None:
    payload = _payload()
    payload["system_type"] = "IRST"
    outputs = _direct_outputs(payload)
    assert all(output["applicable"] is False for output in outputs.values())
    assert all(output["instances"] == [] for output in outputs.values())


def test_confirmation_association_mismatch_fails_closed() -> None:
    payload = _payload()
    payload["confirmations"][0]["reference_entity_id"] = "wrong-target"
    _plan, _registry, inputs, engine = _runtime(payload)
    with pytest.raises(CatalogMetricEngineError, match="M2_SNS_CONFIRMATION_ASSOCIATION_MISMATCH"):
        engine.execute(inputs, metric_codes=("P1-SNS-002",))


def test_world_adapter_binds_identity_without_rebuilding_contracts() -> None:
    stage_world = project_m2_stage_world_lineage(
        M1_FIXTURES / "BF_M1_NOMINAL_V1",
        M2_FIXTURES / "RT_M2_NOMINAL_V1",
        M2_FIXTURES / "TA_M2_NOMINAL_V1",
        M2_FIXTURES / "MSI_M2_RADAR_V1",
        M2_FIXTURES / "MA_M2_NOMINAL_V1",
        authority_root=AUTHORITY,
        release_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa7",
    )
    payload = _payload()
    system_id = stage_world.radar_sensor_world.mission_system_instance_id
    for opportunity in payload["opportunities"]:
        opportunity["evaluated_system_instance_id"] = system_id
    for interval in payload["target_presence_intervals"]:
        interval["evaluated_system_instance_id"] = system_id
    inputs = build_m2_sns_detection_inputs(
        stage_world.radar_sensor_world,
        stage_world,
        opportunities=payload["opportunities"],
        confirmations=payload["confirmations"],
        target_presence_intervals=payload["target_presence_intervals"],
        reference_range_samples=payload["reference_range_samples"],
    )
    assert all(item["upstream_contracts_supplied"] is True for item in inputs.values())
    assert all(item["opportunity_rebuilt_by_metric"] is False for item in inputs.values())
    assert all(item["confirmation_rebuilt_by_metric"] is False for item in inputs.values())
