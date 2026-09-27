#!/usr/bin/env python3
"""M3-MET-001 integrated Catalog general-engine qualification evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
CATALOG_PATH = AUTHORITY_ROOT / "P1_METRIC_CATALOG.json"
TRACKING_ISSUE = 114

EXPECTED_REMAINDER_NAMESPACE_COUNTS = {
    "AIR": 36,
    "TRK": 7,
    "ID": 12,
    "PSV": 7,
    "ESM": 6,
    "DL": 8,
    "FUS": 8,
}


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


def _load(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{path}: root must be string-keyed object")
    return cast(dict[str, object], raw)


def _catalog_partition() -> tuple[
    dict[str, object],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    catalog = _load(CATALOG_PATH)
    raw_metrics = catalog.get("metrics")
    if not isinstance(raw_metrics, list) or not all(
        isinstance(item, dict) for item in raw_metrics
    ):
        raise ValueError("P1_METRIC_CATALOG.metrics must be object rows")
    metrics = cast(list[dict[str, object]], raw_metrics)
    all_codes = tuple(str(item.get("metric_code")) for item in metrics)
    foundation = tuple(
        str(item.get("metric_code"))
        for item in metrics
        if item.get("delivery_milestone") == "M2"
        and item.get("delivery_batch") == "P1_FOUNDATION_32"
    )
    remainder = tuple(
        str(item.get("metric_code"))
        for item in metrics
        if item.get("delivery_milestone") == "M3"
        and item.get("delivery_batch") == "P1_REMAINDER_84"
    )
    return catalog, foundation, remainder, all_codes


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_metric import (
        CatalogMetricEngine,
        M2MetricPluginRequest,
        MetricPluginRegistry,
        M3_CONTRACT_OPERATOR_IMPLEMENTATIONS,
        M3_DEFERRED_OPERATOR_IDS,
        M3_EXPECTED_FAMILY_COUNTS,
        build_m2_metric_execution_plan,
        build_m3_metric_execution_plan,
    )
    from tpaa_metric.operators import M2_OPERATOR_IMPLEMENTATIONS

    def contract_probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {
            "metric_code": request.definition.metric_code,
            "semantic_id": request.definition.semantic_id,
            "semantic_version": request.definition.semantic_version,
            "definition_hash": request.definition.definition_hash,
            "authority_lineage_hash": request.definition.authority_lineage_hash,
            "operator_ids": sorted(request.operators),
            "input_token": request.input_payload["input_token"],
            "upstream_result_hashes": list(request.upstream_result_hashes),
        }

    catalog, foundation_codes, remainder_codes, all_codes = _catalog_partition()
    foundation_plan = build_m2_metric_execution_plan(AUTHORITY_ROOT)
    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    replay_plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)

    registry = MetricPluginRegistry()
    identities = sorted(
        {
            (definition.algorithm_id, definition.algorithm_version)
            for definition in plan.definitions
        }
    )
    for algorithm_id, algorithm_version in identities:
        registry.register(
            algorithm_id,
            algorithm_version=algorithm_version,
            plugin_id="m3-met-001-contract-probe-v1",
            plugin=contract_probe,
        )

    inputs = {
        definition.metric_code: {
            "input_token": f"M3-MET-001::{definition.metric_code}",
        }
        for definition in plan.definitions
    }
    engine = CatalogMetricEngine(
        plan,
        registry,
        operator_implementations=M3_CONTRACT_OPERATOR_IMPLEMENTATIONS,
    )
    first = engine.execute(inputs, validate_runtime_contract=False)
    replay = engine.execute(inputs, validate_runtime_contract=False)

    foundation_set = set(foundation_codes)
    remainder_set = set(remainder_codes)
    all_set = set(all_codes)
    plan_set = set(plan.metric_codes)
    integrated_by_code = {
        definition.metric_code: definition for definition in plan.definitions
    }
    foundation_definition_hashes_unchanged = all(
        integrated_by_code[definition.metric_code].definition_hash
        == definition.definition_hash
        for definition in foundation_plan.definitions
    )

    positions = {
        definition.metric_code: index
        for index, definition in enumerate(plan.definitions)
    }
    dependency_order_exact = all(
        positions[dependency] < positions[definition.metric_code]
        for definition in plan.definitions
        for dependency in definition.metric_dependencies
    )
    cross_delivery_edges = sorted(
        (
            dependency,
            definition.metric_code,
        )
        for definition in plan.definitions
        if definition.metric_code in remainder_set
        for dependency in definition.metric_dependencies
        if dependency in foundation_set
    )

    remainder_namespace_counts = dict(
        sorted(
            Counter(code.split("-", 2)[1] for code in remainder_codes).items()
        )
    )
    family_counts = dict(
        sorted(Counter(definition.family for definition in plan.definitions).items())
    )
    structured_total = tuple(
        definition.metric_code
        for definition in plan.definitions
        if definition.value_kind == "STRUCTURED"
    )
    structured_remainder = tuple(
        code for code in structured_total if code in remainder_set
    )
    deferred_exact = (
        set(M3_CONTRACT_OPERATOR_IMPLEMENTATIONS)
        - set(M2_OPERATOR_IMPLEMENTATIONS)
        == set(M3_DEFERRED_OPERATOR_IDS)
    )
    record_by_code = {record.metric_code: record for record in first.records}

    acceptance = {
        "catalog_total_exact_116": (
            len(all_codes) == 116 and len(all_set) == 116
        ),
        "foundation_exact_32": (
            len(foundation_codes) == 32
            and len(foundation_set) == 32
        ),
        "remainder_exact_84": (
            len(remainder_codes) == 84
            and len(remainder_set) == 84
        ),
        "catalog_partition_exact_32_plus_84": (
            foundation_set.isdisjoint(remainder_set)
            and foundation_set | remainder_set == all_set
        ),
        "remainder_namespace_counts_exact": (
            remainder_namespace_counts == EXPECTED_REMAINDER_NAMESPACE_COUNTS
        ),
        "integrated_plan_exact_116": (
            len(plan.metric_codes) == 116
            and plan_set == all_set
            and set(plan.catalog_metric_codes) == all_set
        ),
        "integrated_execution_exact_116": (
            len(first.records) == 116
            and first.metric_codes == plan.metric_codes
            and set(first.metric_codes) == all_set
        ),
        "remainder_execution_membership_exact_84": (
            len([code for code in first.metric_codes if code in remainder_set]) == 84
            and remainder_set <= set(record_by_code)
        ),
        "foundation_plan_preserved": (
            set(foundation_plan.metric_codes) == foundation_set
            and foundation_definition_hashes_unchanged
        ),
        "cross_delivery_dependency_integration_present": bool(cross_delivery_edges),
        "dependency_order_exact": dependency_order_exact,
        "family_counts_exact_116": (
            family_counts == dict(sorted(M3_EXPECTED_FAMILY_COUNTS.items()))
        ),
        "all_nine_structured_schemas_compiled": len(structured_total) == 9,
        "m3_six_structured_schemas_compiled": len(structured_remainder) == 6,
        "all_required_operators_contract_bound": (
            set(plan.required_operator_ids)
            <= set(M3_CONTRACT_OPERATOR_IMPLEMENTATIONS)
        ),
        "deferred_m3_operator_set_exact": deferred_exact,
        "single_catalog_engine_dispatch": (
            first.dispatch_key == "algorithm_id+algorithm_version"
            and len(first.plugin_manifest_hash) == 64
            and {record.plugin_id for record in first.records}
            == {"m3-met-001-contract-probe-v1"}
        ),
        "catalog_plan_replay_stable": plan == replay_plan,
        "execution_replay_stable": first == replay,
        "authority_hashes_bound": all(
            len(value) == 64
            for value in (
                plan.catalog_sha256,
                plan.input_authority_matrix_sha256,
                plan.source_provenance_sha256,
                plan.world_capability_registry_sha256,
                plan.core_logical_model_sha256,
                plan.core_rules_sha256,
                plan.generated_metric_projection_sha256,
                plan.execution_identity_sha256,
                plan.logical_hash,
            )
        ),
        "catalog_file_hash_exact": (
            plan.catalog_sha256
            == hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest()
        ),
    }
    failed = sorted(key for key, passed in acceptance.items() if not bool(passed))

    logical_product = {
        "catalog_version": plan.catalog_version,
        "catalog_sha256": plan.catalog_sha256,
        "delivery_milestone": plan.delivery_milestone,
        "delivery_batch": plan.delivery_batch,
        "foundation_codes": list(foundation_codes),
        "remainder_codes": list(remainder_codes),
        "integrated_execution_codes": list(first.metric_codes),
        "remainder_namespace_counts": remainder_namespace_counts,
        "family_counts": family_counts,
        "cross_delivery_dependency_edges": [
            list(item) for item in cross_delivery_edges
        ],
        "structured_metric_codes": list(structured_total),
        "m3_structured_metric_codes": list(structured_remainder),
        "required_operator_ids": list(plan.required_operator_ids),
        "deferred_operator_ids": list(M3_DEFERRED_OPERATOR_IDS),
        "required_state_machine_ids": list(plan.required_state_machine_ids),
        "required_external_dependency_ids": list(
            plan.required_external_dependency_ids
        ),
        "plan_logical_hash": plan.logical_hash,
        "execution_logical_hash": first.logical_hash,
        "plugin_manifest_hash": first.plugin_manifest_hash,
        "definition_hashes": [
            [definition.metric_code, definition.definition_hash]
            for definition in plan.definitions
        ],
        "record_hashes": [
            [record.metric_code, record.logical_hash]
            for record in first.records
        ],
    }

    return {
        "schema": "TPAA_M3_MET_001_GENERAL_ENGINE_EVIDENCE_V1",
        "task_id": "M3-MET-001",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": _git_revision(),
        "task_complete": not failed,
        "implementation_complete": not failed,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "general_engine_membership_and_dispatch_only": True,
            "business_metric_semantics_executed": False,
            "deferred_m3_operator_business_semantics_executed": False,
            "family_specific_engine_created": False,
            "persistence_executed": False,
            "publication_executed": False,
        },
    }


def compare_evidence(
    windows_path: Path,
    linux_path: Path,
    *,
    expected_revision: str,
) -> dict[str, object]:
    windows = _load(windows_path)
    linux = _load(linux_path)
    checks = {
        "windows_status_pass": windows.get("status") == "PASS",
        "linux_status_pass": linux.get("status") == "PASS",
        "windows_task_complete": windows.get("task_complete") is True,
        "linux_task_complete": linux.get("task_complete") is True,
        "windows_revision_exact": (
            windows.get("source_revision") == expected_revision
        ),
        "linux_revision_exact": (
            linux.get("source_revision") == expected_revision
        ),
        "logical_product_equal": (
            windows.get("logical_product") == linux.get("logical_product")
        ),
        "acceptance_equal": (
            windows.get("acceptance") == linux.get("acceptance")
        ),
        "failed_acceptance_empty": (
            windows.get("failed_acceptance") == []
            and linux.get("failed_acceptance") == []
        ),
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    return {
        "schema": "TPAA_M3_MET_001_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": "M3-MET-001",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": expected_revision,
        "windows_source_revision": windows.get("source_revision"),
        "linux_source_revision": linux.get("source_revision"),
        "logical_product": windows.get("logical_product"),
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
            evidence = args.evidence
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
            "schema": "TPAA_M3_MET_001_GENERAL_ENGINE_EVIDENCE_V1",
            "task_id": "M3-MET-001",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "source_revision": _git_revision(),
            "task_complete": False,
            "implementation_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        evidence = getattr(args, "evidence", None)
        code = 2
    _write(payload, evidence)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
