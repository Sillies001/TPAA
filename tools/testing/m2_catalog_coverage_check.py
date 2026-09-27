#!/usr/bin/env python3
"""Formal M2-TST-001 exact Catalog coverage evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
CATALOG_PATH = AUTHORITY_ROOT / "P1_METRIC_CATALOG.json"


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


def _load_catalog() -> tuple[dict[str, object], bytes]:
    raw = CATALOG_PATH.read_bytes()
    value: object = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("P1_METRIC_CATALOG root must be an object")
    return value, raw


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_metric import build_m2_metric_execution_plan
    from tpaa_metric.catalog_engine import (
        M2_DELIVERY_BATCH,
        M2_DELIVERY_MILESTONE,
        M2_EXPECTED_FAMILY_COUNTS,
        M2_FOUNDATION_COUNT,
    )

    catalog, catalog_bytes = _load_catalog()
    raw_metrics = catalog.get("metrics")
    if not isinstance(raw_metrics, list) or not all(
        isinstance(item, dict) for item in raw_metrics
    ):
        raise ValueError("P1_METRIC_CATALOG metrics must be object rows")
    metrics = raw_metrics

    foundation = [
        item
        for item in metrics
        if item.get("delivery_milestone") == M2_DELIVERY_MILESTONE
        and item.get("delivery_batch") == M2_DELIVERY_BATCH
    ]
    remainder = [
        item
        for item in metrics
        if item.get("delivery_milestone") == "M3"
        and item.get("delivery_batch") == "P1_REMAINDER_84"
    ]
    foundation_codes = tuple(str(item.get("metric_code")) for item in foundation)
    remainder_codes = tuple(str(item.get("metric_code")) for item in remainder)
    all_codes = tuple(str(item.get("metric_code")) for item in metrics)

    plan = build_m2_metric_execution_plan(AUTHORITY_ROOT)
    family_counts = dict(
        sorted(Counter(str(item.get("family")) for item in foundation).items())
    )
    namespace_counts = dict(
        sorted(
            Counter(code.split("-", 2)[1] for code in foundation_codes).items()
        )
    )
    expected_family_counts = dict(sorted(M2_EXPECTED_FAMILY_COUNTS.items()))

    acceptance = {
        "catalog_total_exact_116": len(metrics) == 116,
        "catalog_codes_unique_116": (
            len(all_codes) == 116 and len(set(all_codes)) == 116
        ),
        "foundation_exact_32": len(foundation) == M2_FOUNDATION_COUNT == 32,
        "remainder_exact_84": len(remainder) == 84,
        "catalog_partition_exact_32_plus_84": (
            len(foundation) + len(remainder) == len(metrics) == 116
            and set(foundation_codes).isdisjoint(remainder_codes)
            and set(foundation_codes) | set(remainder_codes) == set(all_codes)
        ),
        "foundation_codes_unique": (
            len(foundation_codes) == len(set(foundation_codes)) == 32
        ),
        "remainder_codes_unique": (
            len(remainder_codes) == len(set(remainder_codes)) == 84
        ),
        "foundation_family_counts_exact": (
            family_counts == expected_family_counts
        ),
        "foundation_namespace_counts_exact": (
            namespace_counts == {"AIR": 3, "QA": 8, "SNS": 21}
        ),
        "plan_catalog_membership_exact": (
            plan.catalog_metric_codes == foundation_codes
        ),
        "plan_execution_membership_exact": (
            len(plan.metric_codes) == 32
            and set(plan.metric_codes) == set(foundation_codes)
        ),
        "remainder_excluded_from_m2_plan": (
            set(plan.metric_codes).isdisjoint(remainder_codes)
        ),
        "delivery_identity_exact": (
            plan.delivery_milestone == M2_DELIVERY_MILESTONE == "M2"
            and plan.delivery_batch == M2_DELIVERY_BATCH == "P1_FOUNDATION_32"
        ),
        "catalog_hash_exact": (
            plan.catalog_sha256 == hashlib.sha256(catalog_bytes).hexdigest()
        ),
        "catalog_version_bound": (
            plan.catalog_version == catalog.get("catalog_version")
        ),
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    complete = not failed
    return {
        "schema": "TPAA_M2_TST_001_CATALOG_COVERAGE_EVIDENCE_V1",
        "task_id": "M2-TST-001",
        "tracking_issue": 99,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": _git_revision(),
        "logical_product": {
            "catalog_version": plan.catalog_version,
            "catalog_hash": plan.catalog_sha256,
            "catalog_total_count": len(metrics),
            "foundation_count": len(foundation),
            "remainder_count": len(remainder),
            "foundation_codes": list(foundation_codes),
            "remainder_codes": list(remainder_codes),
            "execution_metric_codes": list(plan.metric_codes),
            "family_counts": family_counts,
            "namespace_counts": namespace_counts,
            "delivery_milestone": plan.delivery_milestone,
            "delivery_batch": plan.delivery_batch,
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "catalog_coverage_contract_only": True,
            "p1_foundation_32_counted": True,
            "p1_remainder_84_counted_as_m2": False,
            "p1_remainder_84_executed": False,
            "business_metric_semantics_executed": False,
            "golden_metric_values_executed": False,
            "release_persistence_executed": False,
        },
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
            "schema": "TPAA_M2_TST_001_CATALOG_COVERAGE_EVIDENCE_V1",
            "task_id": "M2-TST-001",
            "tracking_issue": 99,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
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
