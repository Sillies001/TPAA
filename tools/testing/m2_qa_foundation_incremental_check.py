#!/usr/bin/env python3
"""Formal executable evidence for M2-MET-002 QA foundation closure."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
BASELINE_LOCK = REPO_ROOT / "baseline" / "CB-1.4.0" / "BASELINE_LOCK.json"
C3_AUTHORITY = AUTHORITY_ROOT / "M2_QA_SNS_AUTHORITY.json"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m2"
REFERENCE = FIXTURE_ROOT / "RT_M2_NOMINAL_V1"
TIME = FIXTURE_ROOT / "TA_M2_NOMINAL_V1"
MISSION = FIXTURE_ROOT / "MSI_M2_RADAR_V1"
ALIGNMENT = FIXTURE_ROOT / "MA_M2_NOMINAL_V1"
REFERENCE_TIME_RELEASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1"
RADAR_RELEASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2"
ADOPTED_BASELINE_LOCK_SHA256 = (
    "d6ebab2b5402cf81a0b5f73a2da4ed2aaa2d530bc7445c7f6132dcf7fa72224d"
)
C3_AUTHORITY_SHA256 = (
    "1f0755836e7ea40b3b69c83dae1b2b636ff80e37d8630c5ce158d5dfccffd5d3"
)


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    value = completed.stdout.strip()
    return value if len(value) == 40 else "UNKNOWN"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be string-keyed object")
    return cast(dict[str, object], value)


def _instance(output: Mapping[str, object], index: int = 0) -> dict[str, object]:
    instances = output.get("instances")
    if not isinstance(instances, list) or index >= len(instances):
        raise ValueError(f"missing instances[{index}]")
    return _mapping(instances[index], field=f"instances[{index}]")


def _structured(output: Mapping[str, object], index: int = 0) -> dict[str, object]:
    return _mapping(
        _instance(output, index).get("value_structured"),
        field=f"instances[{index}].value_structured",
    )


def _float(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _close(actual: object, expected: object, *, field: str) -> bool:
    return math.isclose(
        _float(actual, field=field),
        _float(expected, field=f"{field}.expected"),
        rel_tol=0.0,
        abs_tol=1e-12,
    )


def _qa001_golden_payload(case: Mapping[str, object]) -> dict[str, object]:
    inp = _mapping(case.get("input"), field="qa_001.input")
    return {
        "samples": [
            {
                "own": {
                    "position_ecef_m": inp["own_position_ecef_m"],
                    "velocity_ecef_mps": inp["own_velocity_ecef_mps"],
                    "attitude_quat": inp["own_attitude_quat"],
                },
                "target": {
                    "position_ecef_m": inp["target_position_ecef_m"],
                    "velocity_ecef_mps": inp["target_velocity_ecef_mps"],
                },
                "sensor_boresight_quat": inp["sensor_boresight_quat"],
                "session_time_us": 0,
            }
        ]
    }


def _qa002_golden_payload(case: Mapping[str, object]) -> dict[str, object]:
    inp = _mapping(case.get("input"), field="qa_002.input")
    return {
        "samples": [
            {
                "target_position_uncertainty_ref": {
                    "representation": "COVARIANCE",
                    "unit": "m^2",
                    "frame_ref": "ECEF",
                    "value": inp["target_position_covariance_ecef_m2"],
                },
                "own_position_uncertainty_ref": {
                    "representation": "COVARIANCE",
                    "unit": "m^2",
                    "frame_ref": "ECEF",
                    "value": inp["own_position_covariance_ecef_m2"],
                },
                "own_attitude_uncertainty_ref": {
                    "representation": "SIGMA_1D",
                    "unit": "rad",
                    "frame_ref": "OWN_BODY_FRD",
                    "value": inp["own_attitude_sigma_rad"],
                },
                "target_attitude_uncertainty_ref": {
                    "representation": "SIGMA_1D",
                    "unit": "rad",
                    "frame_ref": "TARGET_BODY_FRD",
                    "value": inp["target_attitude_sigma_rad"],
                },
                "time_alignment_uncertainty_ref": {
                    "representation": "TWO_SIDED_HARD_BOUND",
                    "unit": "us",
                    "frame_ref": "SESSION_TIME",
                    "value": inp["time_alignment_two_sided_hard_bound_us"],
                },
                "relative_state_jacobian": inp["relative_state_jacobian"],
                "qa_001_basis": {
                    "target_velocity_ecef_mps": inp["target_velocity_ecef_mps"],
                    "own_velocity_ecef_mps": inp["own_velocity_ecef_mps"],
                    "own_attitude_quat": inp["own_attitude_quat"],
                    "r_rel_ecef_m": inp["r_rel_ecef_m"],
                },
            }
        ]
    }


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_metric.catalog_engine import (
        CatalogMetricEngine,
        M2MetricPluginRequest,
        MetricPluginRegistry,
        build_m2_metric_execution_plan,
    )
    from tpaa_metric.operators import M2_OPERATOR_IMPLEMENTATIONS
    from tpaa_metric.qa_foundation import (
        QA_AUTHORITY_BLOCKED_CODES,
        QA_EXECUTABLE_CODES,
        QA_FOUNDATION_CODES,
        build_m2_qa_inputs,
        register_m2_qa_plugins,
    )
    from tpaa_world import (
        project_m2_radar_sensor_world,
        project_m2_reference_time_world,
    )

    authority = _mapping(
        json.loads(C3_AUTHORITY.read_text(encoding="utf-8")),
        field="M2_QA_SNS_AUTHORITY",
    )
    vectors = _mapping(authority.get("golden_vectors"), field="golden_vectors")
    qa001_case = _mapping(vectors.get("qa_001"), field="golden_vectors.qa_001")
    qa002_case = _mapping(vectors.get("qa_002"), field="golden_vectors.qa_002")

    reference_time_world = project_m2_reference_time_world(
        REFERENCE,
        TIME,
        authority_root=AUTHORITY_ROOT,
        release_id=REFERENCE_TIME_RELEASE_ID,
    )
    radar_sensor_world = project_m2_radar_sensor_world(
        MISSION,
        ALIGNMENT,
        authority_root=AUTHORITY_ROOT,
        release_id=RADAR_RELEASE_ID,
    )
    plan = build_m2_metric_execution_plan(AUTHORITY_ROOT)
    registry = MetricPluginRegistry()
    register_m2_qa_plugins(plan, registry)
    inputs = build_m2_qa_inputs(reference_time_world, radar_sensor_world)

    def direct_output(
        metric_code: str,
        payload: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        definition = plan.definition(metric_code)
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
                    input_payload=inputs[metric_code] if payload is None else payload,
                    upstream_result_hashes=(),
                    operators=operators,
                )
            )
        )

    engine = CatalogMetricEngine(plan, registry)
    first = engine.execute(inputs, metric_codes=QA_FOUNDATION_CODES)
    replayed = engine.execute(inputs, metric_codes=QA_FOUNDATION_CODES)
    direct = {code: direct_output(code) for code in QA_FOUNDATION_CODES}
    record_by_code = {record.metric_code: record for record in first.records}

    qa001_c3 = direct_output("P1-QA-001", _qa001_golden_payload(qa001_case))
    qa002_c3 = direct_output("P1-QA-002", _qa002_golden_payload(qa002_case))
    qa001_expected = _mapping(qa001_case.get("expected"), field="qa001.expected")
    qa002_expected = _mapping(qa002_case.get("expected"), field="qa002.expected")
    qa001_value = _structured(qa001_c3)
    qa002_value = _structured(qa002_c3)

    qa001_fields = (
        "range_m",
        "range_rate_mps",
        "own_body_az_rad",
        "own_body_el_rad",
        "sensor_az_rad",
        "sensor_el_rad",
    )
    qa001_golden_exact = all(
        _close(qa001_value[field], qa001_expected[field], field=f"qa001.{field}")
        for field in qa001_fields
    ) and all(
        qa001_value[field] == qa001_expected[field]
        for field in (
            "r_rel_ecef_m",
            "v_rel_ecef_mps",
            "sensor_frame_status",
        )
    )
    qa002_golden_exact = all(
        _close(qa002_value[field], qa002_expected[field], field=f"qa002.{field}")
        for field in (
            "sigma_range_m",
            "sigma_az_rad",
            "sigma_el_rad",
            "sigma_position_3d_m",
        )
    )

    qa001_negative = _qa001_golden_payload(qa001_case)
    qa001_sample = _mapping(
        cast(list[object], qa001_negative["samples"])[0],
        field="qa001_negative.samples[0]",
    )
    qa001_own = _mapping(qa001_sample.get("own"), field="qa001_negative.own")
    qa001_own["attitude_quat"] = [0.0, 0.0, 0.0, 0.0]
    try:
        direct_output("P1-QA-001", qa001_negative)
    except ValueError as exc:
        qa001_zero_norm_fail_closed = "M2_QA_QUATERNION_ZERO_NORM" in str(exc)
    else:
        qa001_zero_norm_fail_closed = False

    qa002_negative = _qa002_golden_payload(qa002_case)
    qa002_sample = _mapping(
        cast(list[object], qa002_negative["samples"])[0],
        field="qa002_negative.samples[0]",
    )
    qa002_sample["relative_state_jacobian"] = [[1.0, 0.0, 0.0, -1.0, 0.0]]
    try:
        direct_output("P1-QA-002", qa002_negative)
    except ValueError as exc:
        qa002_wrong_jacobian_fail_closed = "M2_QA_INPUT_SHAPE_INVALID" in str(exc)
    else:
        qa002_wrong_jacobian_fail_closed = False

    qa003_instances = [_instance(direct["P1-QA-003"], index) for index in range(2)]
    qa003_values = [item.get("value_numeric") for item in qa003_instances]
    qa003_diagnostics = [
        _mapping(item.get("diagnostics"), field="P1-QA-003.diagnostics")
        for item in qa003_instances
    ]
    qa004_instance = _instance(direct["P1-QA-004"])
    qa004_diagnostics = _mapping(
        qa004_instance.get("diagnostics"),
        field="P1-QA-004.diagnostics",
    )
    qa005_instance = _instance(direct["P1-QA-005"])
    qa005_diagnostics = _mapping(
        qa005_instance.get("diagnostics"),
        field="P1-QA-005.diagnostics",
    )
    qa006_instances = [
        _structured(direct["P1-QA-006"], index) for index in range(3)
    ]
    qa007_instance = _instance(direct["P1-QA-007"])
    qa008_instance = _instance(direct["P1-QA-008"])

    expected_qa006 = 5.0 / math.sqrt(14.0)
    expected_qa007 = math.sqrt((500.0 / math.sqrt(3.0)) ** 2 + 100.0**2)
    expected_qa008 = math.sqrt((800.0 / math.sqrt(3.0)) ** 2 + 200.0**2)

    qa_codes = tuple(code for code in plan.metric_codes if code.startswith("P1-QA-"))
    qa_algorithms = {
        plan.definition(code).algorithm_id for code in QA_FOUNDATION_CODES
    }
    qa_algorithm_identities = {
        (
            plan.definition(code).algorithm_id,
            plan.definition(code).algorithm_version,
        )
        for code in QA_FOUNDATION_CODES
    }

    acceptance = {
        "catalog_qa_set_exact_8": (
            len(qa_codes) == 8 and set(qa_codes) == set(QA_FOUNDATION_CODES)
        ),
        "module_authority_blockers_empty": tuple(QA_AUTHORITY_BLOCKED_CODES) == (),
        "module_formula_plugins_exact_8": (
            tuple(QA_EXECUTABLE_CODES) == tuple(QA_FOUNDATION_CODES)
        ),
        "registry_uses_catalog_algorithm_ids": set(registry.plugin_ids) == qa_algorithms,
        "registry_uses_catalog_algorithm_identities_exact": (
            {
                (algorithm_id, algorithm_version)
                for algorithm_id, algorithm_version, _plugin_id
                in registry.plugin_identity_manifest
            }
            == qa_algorithm_identities
        ),
        "full_qa_set_executes_through_general_engine": (
            first.metric_codes == QA_FOUNDATION_CODES
            and first.dispatch_key == "algorithm_id+algorithm_version"
        ),
        "full_qa_set_replay_stable": first == replayed,
        "engine_outputs_match_direct_plugin_hashes": all(
            record_by_code[code].plugin_output_hash == _canonical_hash(direct[code])
            for code in QA_FOUNDATION_CODES
        ),
        "adopted_baseline_lock_exact": _sha256(BASELINE_LOCK)
        == ADOPTED_BASELINE_LOCK_SHA256,
        "c3_authority_artifact_exact": _sha256(C3_AUTHORITY) == C3_AUTHORITY_SHA256,
        "c3_authority_status_approved": (
            authority.get("status") == "APPROVED_BY_DELEGATED_OWNER_AUTHORITY"
        ),
        "qa_001_c3_nonidentity_golden_exact": qa001_golden_exact,
        "qa_001_zero_norm_fail_closed": qa001_zero_norm_fail_closed,
        "qa_002_c3_nondegenerate_golden_exact": qa002_golden_exact,
        "qa_002_wrong_jacobian_fail_closed": qa002_wrong_jacobian_fail_closed,
        "qa_003_segment_boundary_golden": (
            qa003_values == [2000.0, 2000.0]
            and all(item.get("rmse_us") == 2000.0 for item in qa003_diagnostics)
            and all(item.get("p95_us") == 2000.0 for item in qa003_diagnostics)
        ),
        "qa_004_latency_golden": (
            qa004_instance.get("value_numeric") == 40000.0
            and qa004_diagnostics.get("p95_us") == 49000.0
        ),
        "qa_005_interpolation_golden": (
            qa005_instance.get("value_numeric") == 50000.0
            and qa005_diagnostics.get("p95_us") == 50000.0
            and qa005_diagnostics.get("max_us") == 50000.0
        ),
        "qa_006_structured_formula_golden": all(
            item.get("error_domain") == "RANGE"
            and item.get("normalized_residual_status") == "VALID"
            and math.isclose(
                _float(
                    item.get("normalized_residual"),
                    field="P1-QA-006.normalized_residual",
                ),
                expected_qa006,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            for item in qa006_instances
        ),
        "qa_007_time_uncertainty_golden": math.isclose(
            _float(qa007_instance.get("value_numeric"), field="P1-QA-007"),
            expected_qa007,
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
        "qa_008_time_uncertainty_golden": math.isclose(
            _float(qa008_instance.get("value_numeric"), field="P1-QA-008"),
            expected_qa008,
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
        "world_inputs_bound": (
            len(reference_time_world.logical_hash) == 64
            and len(radar_sensor_world.logical_hash) == 64
        ),
    }
    failed_acceptance = sorted(key for key, passed in acceptance.items() if not passed)

    logical_product = {
        "plan_logical_hash": plan.logical_hash,
        "reference_time_world_logical_hash": reference_time_world.logical_hash,
        "radar_sensor_world_logical_hash": radar_sensor_world.logical_hash,
        "engine_metric_codes": list(first.metric_codes),
        "dispatch_key": first.dispatch_key,
        "engine_batch_logical_hash": first.logical_hash,
        "authority_artifact_sha256": _sha256(C3_AUTHORITY),
        "baseline_lock_sha256": _sha256(BASELINE_LOCK),
        "engine_records": [
            {
                "metric_code": record.metric_code,
                "algorithm_id": record.algorithm_id,
                "algorithm_version": record.algorithm_version,
                "plugin_id": record.plugin_id,
                "dependency_manifest_hash": record.dependency_manifest_hash,
                "plugin_output_hash": record.plugin_output_hash,
                "logical_hash": record.logical_hash,
            }
            for record in first.records
        ],
        "direct_outputs": direct,
        "c3_qa001_output": qa001_c3,
        "c3_qa002_output": qa002_c3,
    }

    return {
        "schema": "TPAA_M2_MET_002_INCREMENTAL_QA_EVIDENCE_V1",
        "task_id": "M2-MET-002",
        "tracking_issue": 97,
        "status": "PASS" if not failed_acceptance else "FAIL",
        "implementation_complete": True,
        "task_complete": not failed_acceptance,
        "formal_completion_blocked_by_authority": False,
        "authority_resolution_ready": True,
        "source_revision": _git_revision(),
        "authority": {
            "baseline_change_issue": 106,
            "authority_artifact_id": "M2_QA_SNS_AUTHORITY",
            "authority_version": "1.0.0",
            "authority_sha256": _sha256(C3_AUTHORITY),
            "baseline_lock_sha256": _sha256(BASELINE_LOCK),
        },
        "authority_gaps": {},
        "dependency_effects": {},
        "blocked_error_codes": {},
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed_acceptance,
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
            "schema": "TPAA_M2_MET_002_INCREMENTAL_QA_EVIDENCE_V1",
            "task_id": "M2-MET-002",
            "tracking_issue": 97,
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "formal_completion_blocked_by_authority": False,
            "authority_resolution_ready": True,
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
