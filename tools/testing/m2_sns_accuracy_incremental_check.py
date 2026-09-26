#!/usr/bin/env python3
"""Authority-safe incremental evidence for M2-MET-005 SNS accuracy.

All 17 frozen formulas and negative gates are executable.  The task is not
declared complete while QA-001/002 and the repository's incomplete reference
match-quality profile authority keep the shared-engine closure blocked.
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

    catalog_profile = json.loads(
        (AUTHORITY / "P1_METRIC_CATALOG.json").read_text(encoding="utf-8")
    )["reference_match_quality_profile_registry"]["CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1"]
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
        "non_radar_emits_no_fake_observation": all(
            output.get("applicable") is False and output.get("instances") == []
            for output in non_radar.values()
        ),
        "shared_engine_qa_dependency_fails_closed": dependency_error == "M2_QA_AUTHORITY_GAP",
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
    return {
        "schema": "TPAA_M2_MET_005_SNS_ACCURACY_INCREMENTAL_EVIDENCE_V1",
        "task_id": "M2-MET-005",
        "tracking_issue": 97,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": False,
        "source_revision": _git_revision(),
        "authority_gaps": {
            "P1-QA-001": "frame convention authority unresolved",
            "P1-QA-002": "six-dimensional uncertainty mapping authority unresolved",
            "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1": (
                "frozen M2 alignment fixture omits five required profile fields"
            ),
        },
        "dependency_error_code": dependency_error,
        "fixture_profile_missing_fields": fixture_profile_missing,
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
            "wrap_outputs": wrap_outputs,
            "rejected_outputs": rejected,
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
