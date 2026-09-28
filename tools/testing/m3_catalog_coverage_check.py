#!/usr/bin/env python3
"""M3-TST-001 exact P1 Catalog coverage qualification evidence."""

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
BASELINE_PATH = REPO_ROOT / "docs" / "baseline" / "SDIB-1.2" / "M3_TASK_BASELINE.json"
TRACKING_ISSUE = 117

EXPECTED_REMAINDER_NAMESPACE_COUNTS = {
    "AIR": 36,
    "TRK": 7,
    "ID": 12,
    "PSV": 7,
    "ESM": 6,
    "DL": 8,
    "FUS": 8,
}
EXPECTED_M3_APPLICABILITY_KEYS = {
    "P1-AIR-*",
    "P1-TRK-*",
    "P1-ID-*",
    "P1-PSV-*",
    "P1-ESM-*",
    "P1-DL-*",
    "P1-FUS-*",
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
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ValueError(f"{path}: root must be string-keyed object")
    return cast(dict[str, object], value)


def _rows(value: object, *, field: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or not all(
        isinstance(item, dict) for item in value
    ):
        raise ValueError(f"{field} must be object rows")
    return cast(list[dict[str, object]], value)


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be a string-keyed object")
    return cast(dict[str, object], value)


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_metric import (
        M3_EXPECTED_FAMILY_COUNTS,
        M3_INTEGRATED_COUNT,
        M3_REMAINDER_COUNT,
        build_m2_metric_execution_plan,
        build_m3_metric_execution_plan,
    )

    catalog = _load(CATALOG_PATH)
    baseline = _load(BASELINE_PATH)
    metrics = _rows(catalog.get("metrics"), field="P1_METRIC_CATALOG.metrics")
    foundation_rows = [
        row
        for row in metrics
        if row.get("delivery_milestone") == "M2"
        and row.get("delivery_batch") == "P1_FOUNDATION_32"
    ]
    remainder_rows = [
        row
        for row in metrics
        if row.get("delivery_milestone") == "M3"
        and row.get("delivery_batch") == "P1_REMAINDER_84"
    ]
    all_codes = tuple(str(row.get("metric_code")) for row in metrics)
    foundation_codes = tuple(str(row.get("metric_code")) for row in foundation_rows)
    remainder_codes = tuple(str(row.get("metric_code")) for row in remainder_rows)

    baseline_delivery = _object(
        baseline.get("catalog_delivery"),
        field="M3_TASK_BASELINE.catalog_delivery",
    )
    baseline_integrated = _object(
        baseline.get("integrated_p1_delivery"),
        field="M3_TASK_BASELINE.integrated_p1_delivery",
    )
    baseline_family_counts = _object(
        baseline.get("family_counts"),
        field="M3_TASK_BASELINE.family_counts",
    )
    baseline_applicability = _object(
        baseline.get("family_applicability"),
        field="M3_TASK_BASELINE.family_applicability",
    )
    catalog_applicability = _object(
        catalog.get("family_applicability_contracts"),
        field="P1_METRIC_CATALOG.family_applicability_contracts",
    )

    baseline_remainder_codes_value = baseline_delivery.get("metric_codes")
    if not isinstance(baseline_remainder_codes_value, list) or not all(
        isinstance(code, str) for code in baseline_remainder_codes_value
    ):
        raise ValueError("M3_TASK_BASELINE.catalog_delivery.metric_codes invalid")
    baseline_remainder_codes = tuple(
        cast(list[str], baseline_remainder_codes_value)
    )

    m3_catalog_applicability = {
        key: catalog_applicability[key]
        for key in sorted(EXPECTED_M3_APPLICABILITY_KEYS)
        if key in catalog_applicability
    }
    baseline_applicability_sorted = {
        key: baseline_applicability[key]
        for key in sorted(baseline_applicability)
    }

    remainder_family_counts = dict(
        sorted(Counter(str(row.get("family")) for row in remainder_rows).items())
    )
    integrated_family_counts = dict(
        sorted(Counter(str(row.get("family")) for row in metrics).items())
    )
    remainder_namespace_counts = dict(
        sorted(Counter(code.split("-", 2)[1] for code in remainder_codes).items())
    )

    m2_plan = build_m2_metric_execution_plan(AUTHORITY_ROOT)
    m3_plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)

    all_set = set(all_codes)
    foundation_set = set(foundation_codes)
    remainder_set = set(remainder_codes)
    m3_plan_set = set(m3_plan.metric_codes)

    acceptance = {
        "catalog_total_exact_116_unique": (
            len(all_codes) == M3_INTEGRATED_COUNT == 116
            and len(all_set) == 116
        ),
        "foundation_exact_32_unique": (
            len(foundation_codes) == len(foundation_set) == 32
        ),
        "remainder_exact_84_unique": (
            len(remainder_codes) == len(remainder_set) == M3_REMAINDER_COUNT == 84
        ),
        "catalog_partition_exact_32_plus_84": (
            foundation_set.isdisjoint(remainder_set)
            and foundation_set | remainder_set == all_set
        ),
        "baseline_remainder_codes_exact": (
            baseline_remainder_codes == remainder_codes
            and baseline_delivery.get("delivery_milestone") == "M3"
            and baseline_delivery.get("delivery_batch") == "P1_REMAINDER_84"
            and baseline_delivery.get("count") == 84
        ),
        "baseline_integrated_counts_exact": (
            baseline_integrated.get("foundation_batch") == "P1_FOUNDATION_32"
            and baseline_integrated.get("foundation_count") == 32
            and baseline_integrated.get("remainder_batch") == "P1_REMAINDER_84"
            and baseline_integrated.get("remainder_count") == 84
            and baseline_integrated.get("total_count") == 116
        ),
        "remainder_namespace_counts_exact": (
            remainder_namespace_counts == EXPECTED_REMAINDER_NAMESPACE_COUNTS
        ),
        "remainder_family_counts_exact": (
            remainder_family_counts == baseline_family_counts
        ),
        "integrated_family_counts_exact": (
            integrated_family_counts
            == dict(sorted(M3_EXPECTED_FAMILY_COUNTS.items()))
        ),
        "m3_applicability_keyset_exact": (
            set(baseline_applicability) == EXPECTED_M3_APPLICABILITY_KEYS
            and set(m3_catalog_applicability) == EXPECTED_M3_APPLICABILITY_KEYS
        ),
        "m3_applicability_contracts_exact": (
            baseline_applicability_sorted == m3_catalog_applicability
        ),
        "m2_foundation_plan_exact": (
            m2_plan.catalog_metric_codes == foundation_codes
            and len(m2_plan.metric_codes) == 32
            and set(m2_plan.metric_codes) == foundation_set
        ),
        "m3_integrated_plan_exact_116": (
            m3_plan.catalog_metric_codes == all_codes
            and len(m3_plan.metric_codes) == 116
            and m3_plan_set == all_set
        ),
        "catalog_hash_exact": (
            m3_plan.catalog_sha256
            == hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest()
        ),
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    complete = not failed

    return {
        "schema": "TPAA_M3_TST_001_CATALOG_COVERAGE_EVIDENCE_V1",
        "task_id": "M3-TST-001",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": _git_revision(),
        "logical_product": {
            "catalog_version": m3_plan.catalog_version,
            "catalog_sha256": m3_plan.catalog_sha256,
            "baseline_sha256": hashlib.sha256(BASELINE_PATH.read_bytes()).hexdigest(),
            "catalog_total_count": len(all_codes),
            "foundation_count": len(foundation_codes),
            "remainder_count": len(remainder_codes),
            "foundation_codes": list(foundation_codes),
            "remainder_codes": list(remainder_codes),
            "integrated_catalog_codes": list(all_codes),
            "integrated_execution_codes": list(m3_plan.metric_codes),
            "remainder_namespace_counts": remainder_namespace_counts,
            "remainder_family_counts": remainder_family_counts,
            "integrated_family_counts": integrated_family_counts,
            "m3_applicability_contracts": baseline_applicability_sorted,
            "family_applicability_contracts_sha256": (
                m3_plan.family_applicability_contracts_sha256
            ),
            "delivery_milestone": m3_plan.delivery_milestone,
            "delivery_batch": m3_plan.delivery_batch,
            "plan_logical_hash": m3_plan.logical_hash,
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "catalog_coverage_contract_only": True,
            "p1_foundation_32_counted": True,
            "p1_remainder_84_counted": True,
            "business_metric_semantics_executed": False,
            "metric_values_recomputed": False,
            "publication_executed": False,
            "persistence_executed": False,
            "frozen_catalog_modified": False,
            "frozen_applicability_modified": False,
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
        "schemas_exact": (
            windows.get("schema")
            == linux.get("schema")
            == "TPAA_M3_TST_001_CATALOG_COVERAGE_EVIDENCE_V1"
        ),
        "tasks_exact": (
            windows.get("task_id") == linux.get("task_id") == "M3-TST-001"
        ),
        "statuses_pass": (
            windows.get("status") == linux.get("status") == "PASS"
        ),
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
        "acceptance_equal": (
            windows.get("acceptance") == linux.get("acceptance")
        ),
        "scope_equal": windows.get("scope") == linux.get("scope"),
        "failed_acceptance_empty": (
            windows.get("failed_acceptance") == []
            and linux.get("failed_acceptance") == []
        ),
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    complete = not failed
    return {
        "schema": "TPAA_M3_TST_001_CATALOG_COVERAGE_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": "M3-TST-001",
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
            "schema": "TPAA_M3_TST_001_CATALOG_COVERAGE_EVIDENCE_V1",
            "task_id": "M3-TST-001",
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
