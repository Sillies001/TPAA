#!/usr/bin/env python3
"""M3-TST-003 AIR remainder Golden and negative qualification."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
TRACKING_ISSUE = 117


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


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be a string-keyed object")
    return cast(dict[str, object], value)


def _strings(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a string list")
    return tuple(cast(list[str], value))


def _rows(value: object, *, field: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or not all(
        isinstance(item, dict) and all(isinstance(key, str) for key in item)
        for item in value
    ):
        raise ValueError(f"{field} must be string-keyed object rows")
    return cast(list[dict[str, object]], value)


def verify() -> dict[str, object]:
    repo_root = str(REPO_ROOT)
    src_root = str(REPO_ROOT / "src")
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tools.testing.m3_air_remainder_check import (
        _direct_outputs,
        _golden_inputs,
        _instance,
        verify as verify_air,
    )
    from tpaa_metric import (
        CatalogMetricEngine,
        MetricPluginRegistry,
        register_m2_air_plugins,
    )
    from tpaa_metric.catalog_engine import (
        CatalogMetricEngineError,
        validate_m2_runtime_output,
    )
    from tpaa_metric.m3_air import (
        M3_AIR_CODES,
        M3_AIR_STRUCTURED_CODES,
        register_m3_air_plugins,
    )
    from tpaa_metric.m3_air_operators import M3_AIR_OPERATOR_IMPLEMENTATIONS
    from tpaa_metric.m3_general_engine import build_m3_metric_execution_plan

    revision = _git_revision()
    source = verify_air()
    source_acceptance = _mapping(source.get("acceptance"), field="source.acceptance")
    source_product = _mapping(
        source.get("logical_product"),
        field="source.logical_product",
    )

    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    registry = MetricPluginRegistry()
    register_m2_air_plugins(plan, registry)
    register_m3_air_plugins(plan, registry)

    golden_inputs = _golden_inputs()
    golden_outputs = _direct_outputs(plan, registry, golden_inputs)

    numeric_codes = tuple(
        code for code in M3_AIR_CODES if code not in set(M3_AIR_STRUCTURED_CODES)
    )
    golden_statuses = {
        code: _instance(golden_outputs[code]).get("status")
        for code in M3_AIR_CODES
    }
    numeric_values_present = all(
        _instance(golden_outputs[code]).get("value_numeric") is not None
        for code in numeric_codes
    )
    structured_values_present = all(
        _instance(golden_outputs[code]).get("value_structured") is not None
        for code in M3_AIR_STRUCTURED_CODES
    )

    schema_ids: dict[str, str] = {}
    schema_hashes: dict[str, str] = {}
    schema_negative_codes: dict[str, str] = {}
    schema_positive_validated: list[str] = []
    for code in M3_AIR_STRUCTURED_CODES:
        definition = plan.definition(code)
        schema_id = definition.structured_output_schema_id
        schema_hash = definition.structured_output_schema_hash_sha256
        if schema_id is None or schema_hash is None:
            raise ValueError(f"{code}: structured schema identity missing")
        schema_ids[code] = schema_id
        schema_hashes[code] = schema_hash
        validate_m2_runtime_output(
            definition,
            golden_inputs[code],
            golden_outputs[code],
        )
        schema_positive_validated.append(code)

        mutated = copy.deepcopy(golden_outputs[code])
        mutated_instance = _instance(mutated)
        structured = mutated_instance.get("value_structured")
        if not isinstance(structured, dict):
            raise ValueError(f"{code}: structured Golden output missing")
        structured["__schema_drift__"] = True
        try:
            validate_m2_runtime_output(
                definition,
                golden_inputs[code],
                mutated,
            )
        except CatalogMetricEngineError as exc:
            schema_negative_codes[code] = exc.code
        else:
            schema_negative_codes[code] = "NOT_REJECTED"

    insufficient_inputs = copy.deepcopy(golden_inputs)
    insufficient_inputs["P1-AIR-004"][
        "P1-AIR-003.heading_rate_rad_s"
    ] = [{"session_time_us": 0, "value": 0.2}]
    insufficient_outputs = _direct_outputs(plan, registry, insufficient_inputs)
    insufficient_instance = _instance(insufficient_outputs["P1-AIR-004"])

    quality_inputs = copy.deepcopy(golden_inputs)
    quality_inputs["P1-AIR-019"].pop(
        "P1-AIR-017.specific_energy_rate",
        None,
    )
    quality_outputs = _direct_outputs(plan, registry, quality_inputs)
    quality_instance = _instance(quality_outputs["P1-AIR-019"])
    quality_structured = _mapping(
        quality_instance.get("value_structured"),
        field="quality.P1-AIR-019.value_structured",
    )

    invalid_inputs = copy.deepcopy(golden_inputs)
    invalid_rows = _rows(
        invalid_inputs["P1-AIR-024"].get("attitude_quat"),
        field="invalid.P1-AIR-024.attitude_quat",
    )
    if len(invalid_rows) < 2:
        raise ValueError("invalid P1-AIR-024 Golden requires at least two rows")
    invalid_rows[1]["session_time_us"] = invalid_rows[0]["session_time_us"]

    invalid_error_code = ""
    invalid_error_detail = ""
    engine = CatalogMetricEngine(
        plan,
        registry,
        operator_implementations=M3_AIR_OPERATOR_IMPLEMENTATIONS,
    )
    try:
        engine.execute(invalid_inputs, metric_codes=("P1-AIR-024",))
    except CatalogMetricEngineError as exc:
        invalid_error_code = exc.code
        invalid_error_detail = exc.detail

    acceptance = {
        "source_m3_met_002_exact_head_pass": (
            source.get("status") == "PASS"
            and source.get("task_complete") is True
            and source.get("implementation_complete") is True
            and source.get("source_revision") == revision
            and source.get("failed_acceptance") == []
            and all(value is True for value in source_acceptance.values())
        ),
        "air_remainder_membership_exact_36": (
            _strings(
                source_product.get("metric_codes"),
                field="source.logical_product.metric_codes",
            )
            == M3_AIR_CODES
            and len(golden_outputs) == 36
        ),
        "numeric_goldens_exact_30_valid": (
            len(numeric_codes) == 30
            and numeric_values_present
            and all(golden_statuses[code] == "VALID" for code in numeric_codes)
        ),
        "structured_goldens_exact_6_valid": (
            len(M3_AIR_STRUCTURED_CODES) == 6
            and structured_values_present
            and all(
                golden_statuses[code] == "VALID"
                for code in M3_AIR_STRUCTURED_CODES
            )
        ),
        "source_numeric_golden_vectors_pass": all(
            source_acceptance.get(name) is True
            for name in (
                "golden_turn_radius",
                "golden_acceleration_band_six_seconds",
                "golden_dive_acceleration_three",
                "golden_nose_pointing_rate",
                "golden_climb_energy_partition",
            )
        ),
        "six_structured_schemas_independently_validated": (
            tuple(schema_positive_validated) == M3_AIR_STRUCTURED_CODES
            and set(schema_ids) == set(M3_AIR_STRUCTURED_CODES)
            and all(len(value) == 64 for value in schema_hashes.values())
        ),
        "six_structured_schemas_reject_shape_drift": (
            set(schema_negative_codes) == set(M3_AIR_STRUCTURED_CODES)
            and set(schema_negative_codes.values())
            == {"M2_METRIC_STRUCTURED_OUTPUT_SCHEMA_VIOLATION"}
        ),
        "quality_partial_structured_golden_exact": (
            quality_instance.get("status") == "VALID"
            and quality_structured.get("median_energy_rate_w_per_kg") is None
            and quality_structured.get("median_energy_rate_status")
            == "INSUFFICIENT_RATE_SAMPLES"
            and quality_structured.get("retention_ratio") is not None
            and quality_structured.get("delta_E_s_j_per_kg") is not None
        ),
        "insufficient_golden_fails_closed": (
            insufficient_instance.get("status") == "INSUFFICIENT_DATA"
            and insufficient_instance.get("reason_codes")
            == ["INSUFFICIENT_CONTINUOUS_DURATION"]
            and insufficient_instance.get("value_numeric") is None
            and insufficient_instance.get("value_structured") is None
        ),
        "na_golden_fails_closed": (
            source_acceptance.get("negative_energy_denominator_fails_closed")
            is True
        ),
        "invalid_golden_fails_closed_through_shared_engine": (
            invalid_error_code == "M2_METRIC_PLUGIN_OUTPUT_INVALID"
            and "M3_AIR_QUATERNION_TIME_INVALID" in invalid_error_detail
        ),
        "shared_catalog_engine_preserved": (
            source_acceptance.get("single_catalog_engine_dispatch") is True
        ),
        "execution_replay_preserved": (
            source_acceptance.get("execution_replay_exact") is True
            and source_acceptance.get("plugin_replay_exact") is True
        ),
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    complete = not failed

    logical_product = {
        "metric_codes": list(M3_AIR_CODES),
        "numeric_metric_codes": list(numeric_codes),
        "structured_metric_codes": list(M3_AIR_STRUCTURED_CODES),
        "structured_schema_ids": schema_ids,
        "structured_schema_hashes": schema_hashes,
        "structured_schema_negative_codes": schema_negative_codes,
        "golden_statuses": golden_statuses,
        "source_execution_logical_hash": source_product.get(
            "execution_logical_hash"
        ),
        "source_plugin_manifest_hash": source_product.get("plugin_manifest_hash"),
        "quality_partial_case": {
            "metric_code": "P1-AIR-019",
            "status": quality_instance.get("status"),
            "value_structured": quality_structured,
        },
        "insufficient_case": {
            "metric_code": "P1-AIR-004",
            "status": insufficient_instance.get("status"),
            "reason_codes": insufficient_instance.get("reason_codes"),
        },
        "invalid_case": {
            "metric_code": "P1-AIR-024",
            "error_code": invalid_error_code,
            "error_detail": invalid_error_detail,
        },
    }

    return {
        "schema": "TPAA_M3_TST_003_AIR_GOLDEN_NEGATIVE_EVIDENCE_V1",
        "task_id": "M3-TST-003",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": revision,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "exact_air_remainder_36_executed": True,
            "business_metric_semantics_executed": True,
            "shared_catalog_metric_engine_only": True,
            "numeric_goldens_executed": True,
            "structured_goldens_executed": True,
            "quality_partial_golden_executed": True,
            "insufficient_golden_executed": True,
            "invalid_golden_executed": True,
            "six_structured_schemas_independently_checked": True,
            "catalog_formulas_modified": False,
            "applicability_modified": False,
            "publication_routes_modified": False,
            "persistence_executed": False,
        },
    }


def compare_evidence(
    windows_path: Path,
    linux_path: Path,
    *,
    expected_revision: str,
) -> dict[str, object]:
    windows = _mapping(
        json.loads(windows_path.read_text(encoding="utf-8")),
        field="windows",
    )
    linux = _mapping(
        json.loads(linux_path.read_text(encoding="utf-8")),
        field="linux",
    )
    checks = {
        "schemas_exact": (
            windows.get("schema")
            == linux.get("schema")
            == "TPAA_M3_TST_003_AIR_GOLDEN_NEGATIVE_EVIDENCE_V1"
        ),
        "tasks_exact": (
            windows.get("task_id") == linux.get("task_id") == "M3-TST-003"
        ),
        "statuses_pass": windows.get("status") == linux.get("status") == "PASS",
        "tasks_complete": (
            windows.get("task_complete") is True
            and linux.get("task_complete") is True
        ),
        "implementation_complete": (
            windows.get("implementation_complete") is True
            and linux.get("implementation_complete") is True
        ),
        "revisions_exact": (
            windows.get("source_revision")
            == linux.get("source_revision")
            == expected_revision
        ),
        "logical_product_equal": (
            windows.get("logical_product") == linux.get("logical_product")
        ),
        "acceptance_equal": windows.get("acceptance") == linux.get("acceptance"),
        "scope_equal": windows.get("scope") == linux.get("scope"),
        "failed_acceptance_empty": (
            windows.get("failed_acceptance") == []
            and linux.get("failed_acceptance") == []
        ),
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    complete = not failed
    return {
        "schema": (
            "TPAA_M3_TST_003_AIR_GOLDEN_NEGATIVE_"
            "CROSS_PLATFORM_EVIDENCE_V1"
        ),
        "task_id": "M3-TST-003",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": expected_revision,
        "windows_source_revision": windows.get("source_revision"),
        "linux_source_revision": linux.get("source_revision"),
        "logical_product": windows.get("logical_product"),
        "scope": windows.get("scope"),
        "checks": checks,
        "failed_acceptance": failed,
    }


def _write(payload: dict[str, object], path: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    check = sub.add_parser("check")
    check.add_argument("--evidence", type=Path)
    compare = sub.add_parser("compare")
    compare.add_argument("--windows", type=Path, required=True)
    compare.add_argument("--linux", type=Path, required=True)
    compare.add_argument("--expected-revision", required=True)
    compare.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.mode == "check":
            payload = verify()
        else:
            payload = compare_evidence(
                args.windows,
                args.linux,
                expected_revision=args.expected_revision,
            )
        evidence = args.evidence
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M3_TST_003_AIR_GOLDEN_NEGATIVE_EVIDENCE_V1",
            "task_id": "M3-TST-003",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        evidence = getattr(args, "evidence", None)
        code = 2
    _write(payload, evidence)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
