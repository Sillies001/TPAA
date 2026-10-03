#!/usr/bin/env python3
"""M2-TST-005 cross-platform and frozen-Core storage qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import cast

REQUIRED_LOGICAL_EVIDENCE = (
    "m2-data-005-logical-equivalence.json",
    "m2-world-001-logical-equivalence.json",
    "m2-world-002-logical-equivalence.json",
    "m2-world-003-logical-equivalence.json",
    "m2-met-001-logical-equivalence.json",
    "m2-met-002-incremental-logical-equivalence.json",
    "m2-met-003-logical-equivalence.json",
    "m2-met-004-logical-equivalence.json",
    "m2-met-005-incremental-logical-equivalence.json",
    "m2-met-006-incremental-logical-equivalence.json",
    "m2-met-007-incremental-logical-equivalence.json",
    "m2-authority-gap-sentinel.json",
    "m2-obs-001-logical-equivalence.json",
    "m2-obs-002-logical-equivalence.json",
    "m2-obs-003-logical-equivalence.json",
    "m2-gui-001-logical-equivalence.json",
    "m2-gui-002-logical-equivalence.json",
    "m2-gui-003-logical-equivalence.json",
    "m2-tst-001-logical-equivalence.json",
    "m2-tst-002-logical-equivalence.json",
    "m2-tst-003-logical-equivalence.json",
    "m2-tst-004-logical-equivalence.json",
)
STORAGE_SCHEMA = "TPAA_M1_BATCH_2_STORAGE_PARITY_V1"


def _load(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ValueError(f"{path}: root must be string-keyed object")
    return cast(dict[str, object], value)


def _hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _evidence_revision(payload: dict[str, object]) -> object:
    revision = payload.get("source_revision")
    if revision is not None:
        return revision
    return payload.get("expected_revision")


def qualify(
    logical_root: Path,
    storage_parity_path: Path,
    *,
    expected_revision: str,
) -> dict[str, object]:
    if len(expected_revision) != 40:
        raise ValueError("expected_revision must be an exact 40-character Git SHA")

    logical_products: dict[str, dict[str, object]] = {}
    logical_checks: dict[str, bool] = {}
    logical_hashes: dict[str, str] = {}
    for name in REQUIRED_LOGICAL_EVIDENCE:
        payload = _load(logical_root / name)
        logical_products[name] = payload
        complete = payload.get("task_complete")
        logical_checks[name] = (
            payload.get("status") == "PASS"
            and _evidence_revision(payload) == expected_revision
            and payload.get("failed_acceptance") == []
            and (complete is None or complete is True)
        )
        logical_hashes[name] = _hash(payload)

    storage = _load(storage_parity_path)
    storage_acceptance = storage.get("acceptance")
    if not isinstance(storage_acceptance, dict) or not all(
        isinstance(key, str) for key in storage_acceptance
    ):
        raise ValueError("storage acceptance must be a string-keyed object")
    storage_acceptance = cast(dict[str, object], storage_acceptance)

    acceptance = {
        "all_required_m2_logical_products_present": (
            set(logical_products) == set(REQUIRED_LOGICAL_EVIDENCE)
        ),
        "windows_linux_logical_equivalence_pass": all(logical_checks.values()),
        "logical_products_exact_candidate_revision": all(
            _evidence_revision(payload) == expected_revision
            for payload in logical_products.values()
        ),
        "upstream_tst_001_004_equivalence_present": all(
            f"m2-tst-{index:03d}-logical-equivalence.json" in logical_products
            for index in range(1, 5)
        ),
        "storage_schema_exact": storage.get("schema") == STORAGE_SCHEMA,
        "storage_exact_candidate_revision": (
            storage.get("source_revision") == expected_revision
        ),
        "storage_status_pass": storage.get("status") == "PASS",
        "storage_failed_acceptance_empty": (
            storage.get("failed_acceptance") == []
        ),
        "storage_acceptance_all_pass": all(
            value is True for value in storage_acceptance.values()
        ),
        "current_core_schema_1_7_0": (
            storage_acceptance.get("current_core_schema_is_1_8_0") is True
        ),
        "sqlite_publish_pass": (
            storage_acceptance.get("sqlite_publish_pass") is True
        ),
        "postgres_publish_pass": (
            storage_acceptance.get("postgres_publish_pass") is True
        ),
        "sqlite_postgres_receipt_identity_equal": (
            storage_acceptance.get("receipt_identity_equal") is True
        ),
        "sqlite_postgres_logical_release_membership_parity": (
            storage_acceptance.get("logical_release_membership_equal") is True
        ),
        "sqlite_postgres_logical_membership_hash_equal": (
            storage_acceptance.get("logical_membership_hash_equal") is True
            and storage.get("sqlite_membership_hash")
            == storage.get("postgres_membership_hash")
        ),
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    complete = not failed

    return {
        "schema": "TPAA_M2_TST_005_CROSS_PLATFORM_STORAGE_QUALIFICATION_V1",
        "task_id": "M2-TST-005",
        "tracking_issue": 99,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": expected_revision,
        "logical_product": {
            "required_logical_product_count": len(REQUIRED_LOGICAL_EVIDENCE),
            "required_logical_products": list(REQUIRED_LOGICAL_EVIDENCE),
            "logical_product_hashes": logical_hashes,
            "storage_schema": storage.get("schema"),
            "storage_fixture_id": storage.get("fixture_id"),
            "storage_release_id": storage.get("release_id"),
            "storage_manifest_hash": storage.get("manifest_hash"),
            "sqlite_membership_hash": storage.get("sqlite_membership_hash"),
            "postgres_membership_hash": storage.get("postgres_membership_hash"),
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "cross_platform_qualification_only": True,
            "windows_linux_m2_logical_evidence_aggregated": True,
            "sqlite_postgres_frozen_core_adapter_parity_executed": True,
            "storage_adapter_parity_reuses_frozen_core_release_fixture": True,
            "storage_schema_version": "1.8.0",
            "m2_business_metric_semantics_recomputed": False,
            "p1_remainder_84_executed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--logical-root", type=Path, required=True)
    parser.add_argument("--storage-parity", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = qualify(
            args.logical_root,
            args.storage_parity,
            expected_revision=args.expected_revision,
        )
        return_code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": (
                "TPAA_M2_TST_005_CROSS_PLATFORM_STORAGE_QUALIFICATION_V1"
            ),
            "task_id": "M2-TST-005",
            "tracking_issue": 99,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
            "source_revision": args.expected_revision,
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
