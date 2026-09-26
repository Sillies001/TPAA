#!/usr/bin/env python3
"""Post-C3 incremental evidence for M2-MET-005 SNS accuracy.

All 17 frozen formulas and negative gates are executable. The task remains
formally incomplete while the approved C3 reference-match-quality profile has
not yet been integrated into the M2 SNS consumer path.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = str(REPO_ROOT / "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from tpaa_metric import (  # noqa: E402
    SNS_ACCURACY_CODES,
    CatalogMetricEngine,
    CatalogMetricEngineError,
    M2MetricPluginRequest,
    MetricPluginRegistry,
    build_m2_metric_execution_plan,
    register_m2_sns_accuracy_plugins,
    validate_m2_runtime_output,
)
from tpaa_metric.operators import M2_OPERATOR_IMPLEMENTATIONS  # noqa: E402
from tpaa_metric.qa_foundation import register_m2_qa_plugins  # noqa: E402

AUTHORITY = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    revision = completed.stdout.strip()
    return revision if len(revision) == 40 else "UNKNOWN"


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
            key: key
            for key in (
                "ASSOCIATION_INVALID",
                "MATCH_STATUS_INVALID",
                "INTERPOLATION_AGE_EXCEEDED",
                "REFERENCE_QUALITY_REJECTED",
                "UNCERTAINTY_COMPONENT_MISSING",
                "UNCERTAINTY_DOMAIN_CAP_EXCEEDED",
                "NO_VALID_MATCHED_SAMPLES",
            )
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


def _finite_number(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M2_SNS_ACCURACY_EVIDENCE_VALUE_INVALID:{field}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M2_SNS_ACCURACY_EVIDENCE_VALUE_NONFINITE:{field}")
    return result


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
        sample["measured_az_rad"] = _finite_number(
            sample["reference_az_rad"],
            field="reference_az_rad",
        ) + azimuth_errors[offset]
        sample["measured_el_rad"] = _finite_number(
            sample["reference_el_rad"],
            field="reference_el_rad",
        ) + elevation_errors[offset]
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


def _direct(
    plan: object,
    registry: MetricPluginRegistry,
    code: str,
    payload: Mapping[str, object],
) -> dict[str, object]:
    definition = plan.definition(code)  # type: ignore[attr-defined]
    _plugin_id, plugin = registry.resolve(
        definition.algorithm_id,
        definition.algorithm_version,
    )
    operators = MappingProxyType(
        {
            operator_id: M2_OPERATOR_IMPLEMENTATIONS[operator_id]
            for operator_id in definition.operator_bindings
        }
    )
    return dict(
        plugin(
            M2MetricPluginRequest(
                definition=definition,
                input_payload=payload,
                upstream_result_hashes=(),
                operators=operators,
            )
        )
    )


def _instance(output: Mapping[str, object]) -> dict[str, object]:
    instances = output.get("instances")
    if not isinstance(instances, list) or len(instances) != 1:
        raise ValueError("M2_SNS_ACCURACY_EVIDENCE_INSTANCE_INVALID")
    item = instances[0]
    if not isinstance(item, dict) or not all(isinstance(key, str) for key in item):
        raise ValueError("M2_SNS_ACCURACY_EVIDENCE_INSTANCE_INVALID")
    return item


def _value(output: Mapping[str, object]) -> float:
    value = _instance(output).get("value_numeric")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("M2_SNS_ACCURACY_EVIDENCE_VALUE_INVALID")
    return float(value)


def _evidence(output: Mapping[str, object]) -> dict[str, object]:
    value = _instance(output).get("evidence")
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("M2_SNS_ACCURACY_EVIDENCE_METADATA_INVALID")
    return value


def verify() -> dict[str, object]:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    register_m2_sns_accuracy_plugins(plan, registry)
    payload = _payload()
    outputs = {code: _direct(plan, registry, code, payload) for code in SNS_ACCURACY_CODES}

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

    discriminating_payload = _discriminating_payload()
    discriminating_outputs = {
        code: _direct(plan, registry, code, discriminating_payload)
        for code in SNS_ACCURACY_CODES
    }
    discriminating_expected = {
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

    wrap_payload = _payload()
    wrap_sample = _sample(1)
    wrap_sample["measured_az_rad"] = math.pi - 0.001
    wrap_sample["reference_az_rad"] = -math.pi + 0.001
    wrap_payload["samples"] = [wrap_sample]
    wrap_outputs = {
        code: _direct(plan, registry, code, wrap_payload)
        for code in ("P1-SNS-008", "P1-SNS-009", "P1-SNS-018")
    }

    rejected_payload = _payload()
    rejected_samples = [_sample(1), _sample(2), _sample(3)]
    rejected_samples[0]["association_valid"] = False
    rejected_samples[1]["reference_quality_status"] = "REJECTED"
    rejected_samples[2]["reference_time_us"] = 0
    rejected_payload["samples"] = rejected_samples
    rejected = {
        code: _direct(plan, registry, code, rejected_payload) for code in SNS_ACCURACY_CODES
    }

    full_rejection_payload = _payload()
    full_rejection_samples = [_sample(index) for index in range(1, 7)]
    full_rejection_samples[0]["association_valid"] = False
    full_rejection_samples[1]["match_status"] = "UNMATCHED"
    full_rejection_samples[2]["reference_time_us"] = 0
    full_rejection_samples[3]["reference_quality_status"] = "REJECTED"
    missing_uncertainty = full_rejection_samples[4]["uncertainty_components"]
    if not isinstance(missing_uncertainty, dict):
        raise ValueError("M2_SNS_ACCURACY_EVIDENCE_UNCERTAINTY_INVALID")
    del missing_uncertainty["alignment_uncertainty"]
    full_profile = full_rejection_payload["reference_match_quality_profile"]
    if not isinstance(full_profile, dict):
        raise ValueError("M2_SNS_ACCURACY_EVIDENCE_PROFILE_INVALID")
    full_caps = full_profile["max_sigma_by_error_domain"]
    if not isinstance(full_caps, dict):
        raise ValueError("M2_SNS_ACCURACY_EVIDENCE_PROFILE_CAP_INVALID")
    for domain in full_caps:
        full_caps[domain] = 2.5
    full_rejection_payload["samples"] = full_rejection_samples
    full_rejection_outputs = {
        code: _direct(plan, registry, code, full_rejection_payload)
        for code in SNS_ACCURACY_CODES
    }

    cap_payload = _payload()
    cap_profile = cap_payload["reference_match_quality_profile"]
    if not isinstance(cap_profile, dict):
        raise ValueError("M2_SNS_ACCURACY_EVIDENCE_PROFILE_INVALID")
    cap_values = cap_profile["max_sigma_by_error_domain"]
    if not isinstance(cap_values, dict):
        raise ValueError("M2_SNS_ACCURACY_EVIDENCE_PROFILE_CAP_INVALID")
    for domain in cap_values:
        cap_values[domain] = 3.0
    cap_outputs = {
        code: _direct(plan, registry, code, cap_payload)
        for code in SNS_ACCURACY_CODES
    }

    mixed_payload = _payload()
    accepted_sample = _sample(1)
    rejected_sample = _sample(2)
    rejected_sample["association_valid"] = False
    rejected_sample["measured_range_m"] = 100_000.0
    mixed_payload["samples"] = [accepted_sample, rejected_sample]
    mixed_output = _direct(plan, registry, "P1-SNS-005", mixed_payload)

    empty_payload = _payload()
    empty_payload["samples"] = []
    empty_output = _direct(plan, registry, "P1-SNS-005", empty_payload)

    segmented_payload = _payload()
    segmented_profile = segmented_payload["reference_match_quality_profile"]
    if not isinstance(segmented_profile, dict):
        raise ValueError("M2_SNS_ACCURACY_EVIDENCE_PROFILE_INVALID")
    segmented_profile["profile_id"] = "SYNTHETIC_COMPLETE_PROFILE_V2"
    segmented_profile["profile_version"] = "2.0.0"
    segmented_profile["profile_hash"] = "d" * 64
    segmented_output = _direct(plan, registry, "P1-SNS-005", segmented_payload)

    non_radar_payload = _payload()
    non_radar_payload["system_type"] = "IRST"
    non_radar = {
        code: _direct(plan, registry, code, non_radar_payload) for code in SNS_ACCURACY_CODES
    }

    register_m2_qa_plugins(plan, registry)
    engine_inputs = {code: payload for code in SNS_ACCURACY_CODES}
    engine_inputs.update(
        {
            "P1-QA-001": {"authority_gap": "FRAME_CONVENTION_UNRESOLVED"},
            "P1-QA-002": {"authority_gap": "UNCERTAINTY_MAPPING_UNRESOLVED"},
            "P1-QA-005": {"samples": []},
        }
    )
    dependency_error: str | None = None
    try:
        CatalogMetricEngine(plan, registry).execute(
            engine_inputs,
            metric_codes=SNS_ACCURACY_CODES,
        )
    except CatalogMetricEngineError as exc:
        dependency_error = exc.code

    runtime_transport_valid = True
    try:
        for code in SNS_ACCURACY_CODES:
            validate_m2_runtime_output(
                plan.definition(code),
                payload,
                outputs[code],
            )
            validate_m2_runtime_output(
                plan.definition(code),
                rejected_payload,
                rejected[code],
            )
            validate_m2_runtime_output(
                plan.definition(code),
                non_radar_payload,
                non_radar[code],
            )
    except CatalogMetricEngineError:
        runtime_transport_valid = False

    catalog_document = json.loads(
        (AUTHORITY / "P1_METRIC_CATALOG.json").read_text(encoding="utf-8")
    )
    catalog_profile = catalog_document[
        "reference_match_quality_profile_registry"
    ]["CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1"]
    required_profile_fields = set(catalog_profile["required_instance_fields"])
    fixture_profile = json.loads(
        (
            REPO_ROOT
            / "tests"
            / "fixtures"
            / "m2"
            / "MA_M2_NOMINAL_V1"
            / "source"
            / "measurement-alignment.json"
        ).read_text(encoding="utf-8")
    )["quality_profile"]
    fixture_profile_missing = sorted(required_profile_fields - set(fixture_profile))

    definitions = [plan.definition(code) for code in SNS_ACCURACY_CODES]
    rejection_reasons = [
        "ASSOCIATION_INVALID",
        "INTERPOLATION_AGE_EXCEEDED",
        "REFERENCE_QUALITY_REJECTED",
    ]
    full_rejection_reasons = [
        "ASSOCIATION_INVALID",
        "INTERPOLATION_AGE_EXCEEDED",
        "MATCH_STATUS_INVALID",
        "REFERENCE_QUALITY_REJECTED",
        "UNCERTAINTY_COMPONENT_MISSING",
        "UNCERTAINTY_DOMAIN_CAP_EXCEEDED",
    ]
    catalog_domain_map = catalog_profile["metric_error_domain_map"]
    profile_required_fields_exact = required_profile_fields == set(_profile())
    catalog_domain_map_exact = all(
        _evidence(outputs[code])["error_domain"] == catalog_domain_map[code]
        for code in SNS_ACCURACY_CODES
    )

    acceptance = {
        "catalog_membership_exact_17": tuple(item.metric_code for item in definitions)
        == SNS_ACCURACY_CODES,
        "catalog_semantics_exact": all(
            item.family == "SENSOR_ACCURACY"
            and item.subject_type == "MISSION_SYSTEM_INSTANCE"
            and item.value_kind == "NUMERIC"
            and item.structured_output_schema_id is None
            and item.publication_route == "SYSTEM_PERFORMANCE_OBSERVATION"
            and item.observation_lane == "SYSTEM_PERFORMANCE_OBSERVATION"
            for item in definitions
        ),
        "radar_applicability_exact": all(
            item.applicability.applicability_mode == "SYSTEM_TYPE_EXACT"
            and item.applicability.allowed_system_types == ("RADAR",)
            for item in definitions
        ),
        "version_qualified_plugin_identity_exact": (
            {
                (algorithm_id, algorithm_version)
                for algorithm_id, algorithm_version, _plugin_id
                in registry.plugin_identity_manifest
                if algorithm_id in {item.algorithm_id for item in definitions}
            }
            == {
                (item.algorithm_id, item.algorithm_version)
                for item in definitions
            }
        ),
        "constant_50m_and_vector_golden": all(
            math.isclose(_value(outputs[code]), value, rel_tol=0.0, abs_tol=1e-12)
            for code, value in expected.items()
        ),
        "discriminating_aggregation_golden_exact_17": all(
            math.isclose(
                _value(discriminating_outputs[code]),
                value,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            for code, value in discriminating_expected.items()
        ),
        "catalog_profile_required_fields_exact": profile_required_fields_exact,
        "catalog_error_domain_map_exact_17": catalog_domain_map_exact,
        "runtime_transport_validation_exact_17": runtime_transport_valid,
        "wrap_boundary_golden": (
            math.isclose(_value(wrap_outputs["P1-SNS-008"]), -0.002, abs_tol=1e-12)
            and math.isclose(_value(wrap_outputs["P1-SNS-009"]), 0.002, abs_tol=1e-12)
            and math.isclose(_value(wrap_outputs["P1-SNS-018"]), 0.002, abs_tol=1e-12)
        ),
        "quality_rejections_never_enter_statistics": all(
            _instance(output).get("status") == "N_A"
            and _instance(output).get("value_numeric") is None
            and _instance(output).get("reason_codes") == rejection_reasons
            for output in rejected.values()
        ),
        "full_profile_rejection_reason_surface_exact": all(
            _instance(output).get("status") == "N_A"
            and _instance(output).get("value_numeric") is None
            and _instance(output).get("reason_codes") == full_rejection_reasons
            for output in full_rejection_outputs.values()
        ),
        "profile_component_cap_rule_exact": all(
            _instance(output).get("status") == "VALID"
            for output in cap_outputs.values()
        ),
        "rejected_samples_excluded_from_statistics": (
            math.isclose(_value(mixed_output), 50.0, rel_tol=0.0, abs_tol=1e-12)
            and _evidence(mixed_output)["eligible_measurement_ids"]
            == ["measurement-1"]
            and _evidence(mixed_output)["rejected_sample_count"] == 1
        ),
        "empty_sample_set_uses_profile_reason": (
            _instance(empty_output).get("status") == "N_A"
            and _instance(empty_output).get("reason_codes")
            == ["NO_VALID_MATCHED_SAMPLES"]
        ),
        "profile_provenance_persisted_exact_17": all(
            _evidence(output)["reference_truth_profile_id"]
            == "SYNTHETIC_COMPLETE_PROFILE_V1"
            and _evidence(output)["reference_truth_profile_version"] == "1.0.0"
            and _evidence(output)["reference_truth_profile_hash"] == "c" * 64
            for output in outputs.values()
        ),
        "profile_identity_change_segments_evidence": (
            math.isclose(
                _value(segmented_output),
                _value(outputs["P1-SNS-005"]),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            and _evidence(segmented_output)["reference_truth_profile_id"]
            == "SYNTHETIC_COMPLETE_PROFILE_V2"
            and _evidence(segmented_output)["reference_truth_profile_version"]
            == "2.0.0"
            and _evidence(segmented_output)["reference_truth_profile_hash"]
            == "d" * 64
            and _evidence(segmented_output)
            != _evidence(outputs["P1-SNS-005"])
        ),
        "non_radar_emits_no_fake_observation": all(
            output.get("applicable") is False and output.get("instances") == []
            for output in non_radar.values()
        ),
        "invalid_qa_dependency_payload_fails_closed": (
            dependency_error == "M2_METRIC_PLUGIN_OUTPUT_INVALID"
        ),
        "frozen_fixture_profile_gap_detected": fixture_profile_missing
        == [
            "accepted_reference_quality_statuses",
            "max_interpolation_age_us",
            "max_sigma_by_error_domain",
            "na_reason_map",
            "required_uncertainty_components",
        ],
        "algorithm_replay_exact": outputs
        == {code: _direct(plan, registry, code, payload) for code in SNS_ACCURACY_CODES},
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    implementation_complete = not failed
    return {
        "schema": "TPAA_M2_MET_005_SNS_ACCURACY_INCREMENTAL_EVIDENCE_V1",
        "task_id": "M2-MET-005",
        "tracking_issue": 97,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": False,
        "implementation_complete": implementation_complete,
        "formal_completion_blocked_by_authority": False,
        "formal_completion_blocked_by_profile_integration": True,
        "source_revision": _git_revision(),
        "authority_gaps": {},
        "invalid_qa_payload_error_code": dependency_error,
        "fixture_profile_missing_fields": fixture_profile_missing,
        "scope": {
            "authority_independent_algorithms_executed": True,
            "synthetic_complete_profile_only": True,
            "approved_c3_authority_available": True,
            "approved_c3_profile_consumed": False,
            "adopted_qa_semantics_executed_by_this_check": False,
            "formal_task_completion_claimed": False,
        },
        "logical_product": {
            "delivery_membership": list(SNS_ACCURACY_CODES),
            "plan_logical_hash": plan.logical_hash,
            "definition_hashes": {item.metric_code: item.definition_hash for item in definitions},
            "plugin_identity_manifest": [
                list(item)
                for item in registry.plugin_identity_manifest
                if item[0] in {definition.algorithm_id for definition in definitions}
            ],
            "golden_outputs": outputs,
            "discriminating_outputs": discriminating_outputs,
            "wrap_outputs": wrap_outputs,
            "rejected_outputs": rejected,
            "full_rejection_outputs": full_rejection_outputs,
            "cap_outputs": cap_outputs,
            "mixed_rejection_output": mixed_output,
            "empty_output": empty_output,
            "segmented_profile_output": segmented_output,
            "catalog_profile_contract": {
                "required_instance_fields": catalog_profile["required_instance_fields"],
                "metric_error_domain_map": {
                    code: catalog_domain_map[code] for code in SNS_ACCURACY_CODES
                },
                "rules": catalog_profile["rules"],
            },
            "non_radar": non_radar,
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        payload = verify()
        return_code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M2_MET_005_SNS_ACCURACY_INCREMENTAL_EVIDENCE_V1",
            "task_id": "M2-MET-005",
            "tracking_issue": 97,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
            "formal_completion_blocked_by_authority": False,
            "formal_completion_blocked_by_profile_integration": True,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
