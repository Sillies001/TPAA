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
    validate_m2_runtime_output,
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


def _discriminating_payload() -> dict[str, object]:
    payload = _payload()
    range_errors = (-10.0, 0.0, 30.0, 80.0, -20.0)
    azimuth_errors = (0.1, -0.2, 0.3, -0.4, 0.5)
    elevation_errors = (-0.05, 0.1, -0.15, 0.2, 0.3)
    samples: list[dict[str, object]] = []
    for offset, index in enumerate(range(1, 6)):
        sample = _sample(index)
        reference_range = float(index * 1_000)
        measured_range = reference_range + range_errors[offset]
        sample["measured_range_m"] = measured_range
        sample["reference_range_m"] = reference_range
        sample["sensor_measurement"] = {"range_m": measured_range}
        sample["reference_relative_state"] = {"range_m": reference_range}
        sample["measured_az_rad"] = float(sample["reference_az_rad"]) + azimuth_errors[offset]
        sample["measured_el_rad"] = float(sample["reference_el_rad"]) + elevation_errors[offset]
        sample["measured_position_ecef_m"] = [float(index), 0.0, float(index)]
        sample["reference_target_position_ecef_m"] = [0.0, 0.0, float(index)]
        sample["measured_radial_velocity_mps"] = 10.0 + 2.0 * index
        sample["reference_range_rate_mps"] = 10.0
        sample["measured_position_sensor_frame"] = [
            10.0 + 5.0 * index,
            3.0 * index,
            0.0,
        ]
        sample["reference_position_sensor_frame"] = [10.0, 0.0, 0.0]
        sample["measured_position_local"] = [0.0, 0.0, 10.0 + 4.0 * index]
        sample["reference_position_local"] = [0.0, 0.0, 10.0]
        samples.append(sample)
    payload["samples"] = samples
    return payload


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
        _plugin_id, plugin = registry.resolve(
            definition.algorithm_id,
            definition.algorithm_version,
        )
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
    assert {
        (algorithm_id, algorithm_version)
        for algorithm_id, algorithm_version, _plugin_id in registry.plugin_identity_manifest
    } == {
        (plan.definition(code).algorithm_id, plan.definition(code).algorithm_version)
        for code in SNS_ACCURACY_CODES
    }
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


def test_sns_accuracy_discriminating_golden_distinguishes_all_aggregations() -> None:
    outputs = _direct_outputs(_discriminating_payload())
    expected = {
        "P1-SNS-005": 16.0,
        "P1-SNS-006": 39.496835316262995,
        "P1-SNS-007": 70.0,
        "P1-SNS-008": 0.06054936970668068,
        "P1-SNS-009": 0.33166247903554,
        "P1-SNS-010": 0.1816590212458495,
        "P1-SNS-011": 3.3166247903554,
        "P1-SNS-012": 6.6332495807108,
        "P1-SNS-013": 9.9498743710662,
        "P1-SNS-014": 13.2664991614216,
        "P1-SNS-015": 28.0,
        "P1-SNS-016": 20.0,
        "P1-SNS-017": 80.0,
        "P1-SNS-018": 0.48,
        "P1-SNS-019": 0.08,
        "P1-SNS-020": 0.28,
        "P1-SNS-021": 16.583123951777,
    }
    for code, value in expected.items():
        assert _value(outputs[code]) == pytest.approx(value, rel=0.0, abs=1e-12)


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


def test_profile_component_cap_is_applied_per_required_component() -> None:
    payload = _payload()
    profile = payload["reference_match_quality_profile"]
    assert isinstance(profile, dict)
    caps = profile["max_sigma_by_error_domain"]
    assert isinstance(caps, dict)
    for domain in caps:
        caps[domain] = 3.0

    outputs = _direct_outputs(payload)
    assert all(output["instances"][0]["status"] == "VALID" for output in outputs.values())


def test_full_profile_rejection_reason_surface_is_deterministic() -> None:
    payload = _payload()
    samples = [_sample(index) for index in range(1, 7)]
    samples[0]["association_valid"] = False
    samples[1]["match_status"] = "UNMATCHED"
    samples[2]["reference_time_us"] = 0
    samples[3]["reference_quality_status"] = "REJECTED"
    missing_uncertainty = samples[4]["uncertainty_components"]
    assert isinstance(missing_uncertainty, dict)
    del missing_uncertainty["alignment_uncertainty"]
    profile = payload["reference_match_quality_profile"]
    assert isinstance(profile, dict)
    caps = profile["max_sigma_by_error_domain"]
    assert isinstance(caps, dict)
    for domain in caps:
        caps[domain] = 2.5
    payload["samples"] = samples

    expected_reasons = [
        "ASSOCIATION_INVALID",
        "INTERPOLATION_AGE_EXCEEDED",
        "MATCH_STATUS_INVALID",
        "REFERENCE_QUALITY_REJECTED",
        "UNCERTAINTY_COMPONENT_MISSING",
        "UNCERTAINTY_DOMAIN_CAP_EXCEEDED",
    ]
    outputs = _direct_outputs(payload)
    for output in outputs.values():
        instance = output["instances"][0]
        assert instance["status"] == "N_A"
        assert instance["value_numeric"] is None
        assert instance["reason_codes"] == expected_reasons


def test_rejected_sample_cannot_bias_statistics_and_empty_uses_profile_reason() -> None:
    payload = _payload()
    accepted = _sample(1)
    rejected = _sample(2)
    rejected["association_valid"] = False
    rejected["measured_range_m"] = 100_000.0
    payload["samples"] = [accepted, rejected]
    output = _direct_outputs(payload)["P1-SNS-005"]
    assert _value(output) == pytest.approx(50.0)
    evidence = output["instances"][0]["evidence"]
    assert evidence["eligible_measurement_ids"] == ["measurement-1"]
    assert evidence["eligible_sample_count"] == 1
    assert evidence["rejected_sample_count"] == 1

    empty = _payload()
    empty["samples"] = []
    empty_output = _direct_outputs(empty)["P1-SNS-005"]
    instance = empty_output["instances"][0]
    assert instance["status"] == "N_A"
    assert instance["reason_codes"] == ["NO_VALID_MATCHED_SAMPLES"]


def test_profile_identity_is_persisted_and_segments_evidence() -> None:
    first_payload = _payload()
    second_payload = _payload()
    profile = second_payload["reference_match_quality_profile"]
    assert isinstance(profile, dict)
    profile["profile_id"] = "SYNTHETIC_COMPLETE_PROFILE_V2"
    profile["profile_version"] = "2.0.0"
    profile["profile_hash"] = "d" * 64

    first = _direct_outputs(first_payload)["P1-SNS-005"]
    second = _direct_outputs(second_payload)["P1-SNS-005"]
    assert _value(first) == _value(second)
    first_evidence = first["instances"][0]["evidence"]
    second_evidence = second["instances"][0]["evidence"]
    assert first_evidence["reference_truth_profile_id"] == "SYNTHETIC_COMPLETE_PROFILE_V1"
    assert first_evidence["reference_truth_profile_version"] == "1.0.0"
    assert first_evidence["reference_truth_profile_hash"] == "c" * 64
    assert second_evidence["reference_truth_profile_id"] == "SYNTHETIC_COMPLETE_PROFILE_V2"
    assert second_evidence["reference_truth_profile_version"] == "2.0.0"
    assert second_evidence["reference_truth_profile_hash"] == "d" * 64
    assert first_evidence != second_evidence


def test_direct_outputs_pass_shared_runtime_transport_validation() -> None:
    plan, _registry, inputs = _runtime()
    outputs = _direct_outputs()
    for code in SNS_ACCURACY_CODES:
        validate_m2_runtime_output(plan.definition(code), inputs[code], outputs[code])

    non_radar = _payload()
    non_radar["system_type"] = "IRST"
    non_radar_outputs = _direct_outputs(non_radar)
    for code in SNS_ACCURACY_CODES:
        validate_m2_runtime_output(
            plan.definition(code),
            {"system_type": "IRST"},
            non_radar_outputs[code],
        )


def test_shared_engine_rejects_invalid_qa_payload_after_c3_adoption() -> None:
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
    assert caught.value.code == "M2_METRIC_PLUGIN_OUTPUT_INVALID"


def test_world_adapter_requires_and_preserves_complete_external_contracts() -> None:
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

    associations = {
        row.measurement_id: {
            "association_id": f"assoc::{row.measurement_id}",
            "association_provenance": "unit-test:external-association:v1",
            "association_valid": True,
            "reference_quality_status": "ACCEPTED",
        }
        for row in stage_world.radar_sensor_world.measurement_alignment.rows
    }
    profile = _profile()
    inputs = build_m2_sns_accuracy_inputs(
        stage_world.radar_sensor_world,
        stage_world,
        reference_match_quality_profile=profile,
        associations=associations,
    )
    assert tuple(inputs) == SNS_ACCURACY_CODES
    for payload in inputs.values():
        assert payload["world_logical_hash"] == stage_world.radar_sensor_world.logical_hash
        assert payload["stage_world_logical_hash"] == stage_world.logical_hash
        assert payload["reference_match_quality_profile"] == profile
        assert payload["association_contract_supplied"] is True
        assert payload["quality_profile_contract_supplied"] is True
        assert payload["association_rebuilt_by_metric"] is False
        assert payload["quality_policy_defaulted_by_metric"] is False
        assert payload["frame_transform_executed_by_metric"] is False

    missing_associations = dict(associations)
    first_measurement_id = next(iter(missing_associations))
    del missing_associations[first_measurement_id]
    with pytest.raises(CatalogMetricEngineError) as missing:
        build_m2_sns_accuracy_inputs(
            stage_world.radar_sensor_world,
            stage_world,
            reference_match_quality_profile=profile,
            associations=missing_associations,
        )
    assert missing.value.code == "M2_SNS_ASSOCIATION_CONTRACT_MISSING"
