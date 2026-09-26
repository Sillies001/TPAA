from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path

import pytest

from tpaa_metric import (
    SNS_ACCURACY_CODES,
    CatalogMetricEngine,
    CatalogMetricEngineError,
    M2MetricPluginRequest,
    MetricPluginRegistry,
    build_m2_metric_execution_plan,
    build_m2_sns_accuracy_inputs,
    register_m2_sns_accuracy_plugins,
)
from tpaa_metric.operators import M2_OPERATOR_IMPLEMENTATIONS
from tpaa_metric.qa_foundation import register_m2_qa_plugins
from tpaa_world import project_m2_stage_world_lineage

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
M1_FIXTURES = ROOT / "tests" / "fixtures" / "m1"
M2_FIXTURES = ROOT / "tests" / "fixtures" / "m2"


def _profile() -> dict[str, object]:
    domains = {
        "RANGE",
        "AZIMUTH",
        "ELEVATION",
        "POSITION_3D",
        "RADIAL_VELOCITY",
        "CROSS_RANGE",
        "VERTICAL_POSITION",
        "RADIAL_POSITION",
    }
    return {
        "profile_id": "SYNTHETIC_COMPLETE_PROFILE_V1",
        "profile_version": "1.0.0",
        "profile_hash": "c" * 64,
        "max_interpolation_age_us": 100,
        "accepted_reference_quality_statuses": ["ACCEPTED"],
        "max_sigma_by_error_domain": {domain: None for domain in sorted(domains)},
        "required_uncertainty_components": [
            "reference_truth_uncertainty",
            "alignment_uncertainty",
            "sensor_measurement_uncertainty",
        ],
        "na_reason_map": {
            "ASSOCIATION_INVALID": "ASSOCIATION_INVALID",
            "MATCH_STATUS_INVALID": "MATCH_STATUS_INVALID",
            "INTERPOLATION_AGE_EXCEEDED": "INTERPOLATION_AGE_EXCEEDED",
            "REFERENCE_QUALITY_REJECTED": "REFERENCE_QUALITY_REJECTED",
            "UNCERTAINTY_COMPONENT_MISSING": "UNCERTAINTY_COMPONENT_MISSING",
            "UNCERTAINTY_DOMAIN_CAP_EXCEEDED": "UNCERTAINTY_DOMAIN_CAP_EXCEEDED",
            "NO_VALID_MATCHED_SAMPLES": "NO_VALID_MATCHED_SAMPLES",
        },
    }


def _sample(index: int) -> dict[str, object]:
    reference_range = float(index * 1_000)
    return {
        "measurement_id": f"measurement-{index}",
        "reference_state_id": f"reference-{index}",
        "association_id": f"association-{index}",
        "association_provenance": "synthetic:association:v1",
        "association_valid": True,
        "reference_quality_status": "ACCEPTED",
        "measurement_time_us": index * 1_000,
        "reference_time_us": index * 1_000 - 50,
        "match_status": "MATCHED",
        "measured_range_m": reference_range + 50.0,
        "reference_range_m": reference_range,
        "measured_az_rad": 0.11 + index * 0.1,
        "reference_az_rad": 0.10 + index * 0.1,
        "measured_el_rad": 0.12 + index * 0.1,
        "reference_el_rad": 0.10 + index * 0.1,
        "measured_position_ecef_m": [3.0, 4.0, float(index)],
        "reference_target_position_ecef_m": [0.0, 0.0, float(index)],
        "measured_radial_velocity_mps": 12.0,
        "reference_range_rate_mps": 10.0,
        "measured_position_sensor_frame": [13.0, 4.0, 0.0],
        "reference_position_sensor_frame": [10.0, 0.0, 0.0],
        "measured_position_local": [0.0, 0.0, 16.0],
        "reference_position_local": [0.0, 0.0, 10.0],
        "sensor_measurement": {"range_m": reference_range + 50.0},
        "reference_relative_state": {"range_m": reference_range},
        "reference_truth_uncertainty": 3.0,
        "uncertainty_components": {
            "reference_truth_uncertainty": 3.0,
            "alignment_uncertainty": 1.0,
            "sensor_measurement_uncertainty": 2.0,
        },
    }


def _payload() -> dict[str, object]:
    return {
        "system_type": "RADAR",
        "mission_system_instance_id": "radar-1",
        "reference_match_quality_profile": _profile(),
        "samples": [_sample(1), _sample(2), _sample(3)],
    }


def _runtime(payload: Mapping[str, object] | None = None):
    plan = build_m2_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    register_m2_sns_accuracy_plugins(plan, registry)
    inputs = {code: dict(payload or _payload()) for code in SNS_ACCURACY_CODES}
    return plan, registry, inputs


def _direct_outputs(payload: Mapping[str, object] | None = None) -> dict[str, object]:
    plan, registry, inputs = _runtime(payload)
    outputs: dict[str, object] = {}
    for code in SNS_ACCURACY_CODES:
        definition = plan.definition(code)
        _plugin_id, plugin = registry.resolve(definition.algorithm_id)
        outputs[code] = plugin(
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
    return outputs


def _value(output: object) -> float:
    assert isinstance(output, dict)
    instances = output["instances"]
    assert isinstance(instances, list)
    value = instances[0]["value_numeric"]
    assert isinstance(value, float)
    return value


def test_sns_accuracy_exact_17_catalog_algorithms_and_golden_values() -> None:
    plan, registry, _inputs = _runtime()
    outputs = _direct_outputs()
    assert (
        tuple(code for code in plan.metric_codes if code in SNS_ACCURACY_CODES)
        == SNS_ACCURACY_CODES
    )
    assert {plan.definition(code).algorithm_id for code in SNS_ACCURACY_CODES} == set(
        registry.plugin_ids
    )
    expected = {
        "P1-SNS-005": 50.0,
        "P1-SNS-006": 50.0,
        "P1-SNS-007": 50.0,
        "P1-SNS-008": 0.01,
        "P1-SNS-009": 0.01,
        "P1-SNS-010": 0.02,
        "P1-SNS-011": 5.0,
        "P1-SNS-012": 2.0,
        "P1-SNS-013": 4.0,
        "P1-SNS-014": 6.0,
        "P1-SNS-015": 50.0,
        "P1-SNS-016": 50.0,
        "P1-SNS-017": 50.0,
        "P1-SNS-018": 0.01,
        "P1-SNS-019": 0.02,
        "P1-SNS-020": 0.02,
        "P1-SNS-021": 3.0,
    }
    for code, value in expected.items():
        assert _value(outputs[code]) == pytest.approx(value)


def test_azimuth_wrap_boundary_uses_frozen_wrap_operator() -> None:
    payload = _payload()
    sample = payload["samples"][0]
    sample["measured_az_rad"] = math.pi - 0.001
    sample["reference_az_rad"] = -math.pi + 0.001
    payload["samples"] = [sample]
    outputs = _direct_outputs(payload)
    assert _value(outputs["P1-SNS-008"]) == pytest.approx(-0.002)
    assert _value(outputs["P1-SNS-009"]) == pytest.approx(0.002)
    assert _value(outputs["P1-SNS-018"]) == pytest.approx(0.002)


def test_quality_profile_rejections_are_deterministic_and_never_enter_statistics() -> None:
    payload = _payload()
    payload["samples"][0]["association_valid"] = False
    payload["samples"][1]["reference_quality_status"] = "REJECTED"
    payload["samples"][2]["reference_time_us"] = 0
    outputs = _direct_outputs(payload)
    for output in outputs.values():
        assert output["instances"][0]["status"] == "N_A"
        assert output["instances"][0]["value_numeric"] is None
        assert output["instances"][0]["reason_codes"] == [
            "ASSOCIATION_INVALID",
            "INTERPOLATION_AGE_EXCEEDED",
            "REFERENCE_QUALITY_REJECTED",
        ]


def test_non_radar_applicability_emits_no_fake_observation() -> None:
    payload = _payload()
    payload["system_type"] = "IRST"
    outputs = _direct_outputs(payload)
    assert all(output["applicable"] is False for output in outputs.values())
    assert all(output["instances"] == [] for output in outputs.values())


def test_shared_engine_dependency_closure_remains_blocked_by_qa_authority() -> None:
    plan, registry, inputs = _runtime()
    register_m2_qa_plugins(plan, registry)
    inputs.update(
        {
            "P1-QA-001": {"authority_gap": "FRAME_CONVENTION_UNRESOLVED"},
            "P1-QA-002": {"authority_gap": "UNCERTAINTY_MAPPING_UNRESOLVED"},
            "P1-QA-005": {"samples": []},
        }
    )
    with pytest.raises(CatalogMetricEngineError) as caught:
        CatalogMetricEngine(plan, registry).execute(inputs, metric_codes=SNS_ACCURACY_CODES)
    assert caught.value.code == "M2_QA_AUTHORITY_GAP"


def test_world_adapter_requires_complete_external_profile_and_associations() -> None:
    stage_world = project_m2_stage_world_lineage(
        M1_FIXTURES / "BF_M1_NOMINAL_V1",
        M2_FIXTURES / "RT_M2_NOMINAL_V1",
        M2_FIXTURES / "TA_M2_NOMINAL_V1",
        M2_FIXTURES / "MSI_M2_RADAR_V1",
        M2_FIXTURES / "MA_M2_NOMINAL_V1",
        authority_root=AUTHORITY,
        release_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa9",
    )
    partial = {
        "profile_id": stage_world.radar_sensor_world.measurement_alignment.quality_profile.profile_id,
        "profile_version": stage_world.radar_sensor_world.measurement_alignment.quality_profile.profile_version,
        "profile_hash": stage_world.radar_sensor_world.measurement_alignment.quality_profile.profile_hash,
        "max_gap_us": 50_000,
        "min_coverage": 0.8,
    }
    with pytest.raises(CatalogMetricEngineError) as caught:
        build_m2_sns_accuracy_inputs(
            stage_world.radar_sensor_world,
            stage_world,
            reference_match_quality_profile=partial,
            associations={},
        )
    assert caught.value.code == "M2_SNS_MATCH_QUALITY_PROFILE_INCOMPLETE"
