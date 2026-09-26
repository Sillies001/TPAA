#!/usr/bin/env python3
"""Incremental executable evidence for M2-MET-002 QA foundation.

This evidence intentionally does not claim task completion. P1-QA-001 and
P1-QA-002 remain authority-blocked, and P1-QA-006 remains formally blocked
through the Catalog dependency closure because it depends on that unresolved
authority chain.
"""

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
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m2"
REFERENCE = FIXTURE_ROOT / "RT_M2_NOMINAL_V1"
TIME = FIXTURE_ROOT / "TA_M2_NOMINAL_V1"
MISSION = FIXTURE_ROOT / "MSI_M2_RADAR_V1"
ALIGNMENT = FIXTURE_ROOT / "MA_M2_NOMINAL_V1"
REFERENCE_TIME_RELEASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1"
RADAR_RELEASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2"

SAFE_ENGINE_CODES = (
    "P1-QA-003",
    "P1-QA-004",
    "P1-QA-005",
    "P1-QA-007",
    "P1-QA-008",
)
AUTHORITY_BLOCKED_CODES = ("P1-QA-001", "P1-QA-002")
DEPENDENCY_BLOCKED_CODES = ("P1-QA-006",)


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


def _float(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_metric.catalog_engine import (
        CatalogMetricEngine,
        CatalogMetricEngineError,
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

    def direct_output(metric_code: str) -> dict[str, object]:
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
                    input_payload=inputs[metric_code],
                    upstream_result_hashes=(),
                    operators=operators,
                )
            )
        )

    engine = CatalogMetricEngine(plan, registry)
    first = engine.execute(inputs, metric_codes=SAFE_ENGINE_CODES)
    replayed = engine.execute(inputs, metric_codes=SAFE_ENGINE_CODES)
    direct = {code: direct_output(code) for code in SAFE_ENGINE_CODES}
    qa006 = direct_output("P1-QA-006")
    record_by_code = {record.metric_code: record for record in first.records}

    def blocked(metric_code: str) -> tuple[bool, str | None]:
        try:
            engine.execute(inputs, metric_codes=(metric_code,))
        except CatalogMetricEngineError as exc:
            return exc.code == "M2_QA_AUTHORITY_GAP", exc.code
        return False, None

    qa001_blocked, qa001_error = blocked("P1-QA-001")
    qa002_blocked, qa002_error = blocked("P1-QA-002")
    qa006_blocked, qa006_error = blocked("P1-QA-006")

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
        _mapping(
            _instance(qa006, index).get("value_structured"),
            field=f"P1-QA-006.instances[{index}].value_structured",
        )
        for index in range(3)
    ]
    qa007_instance = _instance(direct["P1-QA-007"])
    qa008_instance = _instance(direct["P1-QA-008"])

    expected_qa006 = 5.0 / math.sqrt(14.0)
    expected_qa007 = math.sqrt((500.0 / math.sqrt(3.0)) ** 2 + 100.0**2)
    expected_qa008 = math.sqrt((800.0 / math.sqrt(3.0)) ** 2 + 200.0**2)

    qa_codes = tuple(code for code in plan.metric_codes if code.startswith("P1-QA-"))
    qa_algorithms = {
        plan.definition(code).algorithm_id
        for code in QA_FOUNDATION_CODES
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
        "module_authority_blockers_exact": (
            tuple(QA_AUTHORITY_BLOCKED_CODES) == AUTHORITY_BLOCKED_CODES
        ),
        "module_formula_plugins_exact_6": (
            tuple(QA_EXECUTABLE_CODES)
            == (
                "P1-QA-003",
                "P1-QA-004",
                "P1-QA-005",
                "P1-QA-006",
                "P1-QA-007",
                "P1-QA-008",
            )
        ),
        "registry_uses_catalog_algorithm_ids": (
            set(registry.plugin_ids) == qa_algorithms
        ),
        "registry_uses_catalog_algorithm_identities_exact": (
            {
                (algorithm_id, algorithm_version)
                for algorithm_id, algorithm_version, _plugin_id
                in registry.plugin_identity_manifest
            }
            == qa_algorithm_identities
        ),
        "safe_subset_executes_through_general_engine": (
            first.metric_codes == SAFE_ENGINE_CODES
            and first.dispatch_key == "algorithm_id+algorithm_version"
        ),
        "safe_subset_replay_stable": first == replayed,
        "safe_engine_outputs_match_direct_plugin_hashes": all(
            record_by_code[code].plugin_output_hash == _canonical_hash(direct[code])
            for code in SAFE_ENGINE_CODES
        ),
        "qa_001_authority_gap_fail_closed": qa001_blocked,
        "qa_002_authority_gap_fail_closed": qa002_blocked,
        "qa_006_dependency_closure_fail_closed": qa006_blocked,
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
            and item.get("residual_unit") == "m"
            and item.get("raw_residual") == 5.0
            and item.get("reference_uncertainty") == 3.0
            and item.get("alignment_uncertainty") == 1.0
            and item.get("sensor_reported_uncertainty") == 2.0
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
            _float(
                qa007_instance.get("value_numeric"),
                field="P1-QA-007.value_numeric",
            ),
            expected_qa007,
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
        "qa_008_time_uncertainty_golden": math.isclose(
            _float(
                qa008_instance.get("value_numeric"),
                field="P1-QA-008.value_numeric",
            ),
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
        "safe_engine_metric_codes": list(first.metric_codes),
        "dispatch_key": first.dispatch_key,
        "safe_engine_batch_logical_hash": first.logical_hash,
        "safe_engine_records": [
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
        "safe_direct_outputs": direct,
        "qa_006_formula_only_output": qa006,
        "authority_blocked_metric_codes": list(AUTHORITY_BLOCKED_CODES),
        "dependency_blocked_metric_codes": list(DEPENDENCY_BLOCKED_CODES),
    }

    return {
        "schema": "TPAA_M2_MET_002_INCREMENTAL_QA_EVIDENCE_V1",
        "task_id": "M2-MET-002",
        "tracking_issue": 97,
        "status": "PASS" if not failed_acceptance else "FAIL",
        "task_complete": False,
        "source_revision": _git_revision(),
        "authority_gaps": {
            "P1-QA-001": (
                "frozen quaternion ordering/rotation/body-axis/az-el convention unresolved"
            ),
            "P1-QA-002": (
                "frozen mapping from five uncertainty refs to the six-dimensional "
                "P_inputs consumed by relative_state_jacobian unresolved"
            ),
        },
        "dependency_effects": {
            "P1-QA-006": (
                "formula plugin is directly verifiable, but formal Catalog execution "
                "remains blocked by the unresolved P1-QA-002 -> P1-QA-001 authority chain"
            ),
        },
        "blocked_error_codes": {
            "P1-QA-001": qa001_error,
            "P1-QA-002": qa002_error,
            "P1-QA-006": qa006_error,
        },
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
