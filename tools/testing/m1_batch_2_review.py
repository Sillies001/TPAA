"""Aggregate exact-revision evidence for M1 Batch 2 / Issue #87."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

BACKEND_SCHEMA = "TPAA_M1_BATCH_2_BACKEND_EVIDENCE_V1"
SERVICE_SCHEMA = "TPAA_M1_BATCH_2_SERVICE_SMOKE_V1"
SERVICE_EQ_SCHEMA = "TPAA_M1_BATCH_2_SERVICE_LOGICAL_EQUIVALENCE_V1"
STORAGE_SCHEMA = "TPAA_M1_BATCH_2_STORAGE_PARITY_V1"
REVIEW_SCHEMA = "TPAA_M1_BATCH_2_REVIEW_V1"

TASK_IDS = (
    "M1-OBS-001",
    "M1-OBS-002",
    "M1-OBS-003",
    "M1-OBS-004",
    "M1-OBS-005",
    "M1-STO-001",
    "M1-STO-002",
    "M1-STO-003",
    "M1-API-001",
    "M1-API-002",
    "M1-API-003",
    "M1-API-004",
    "M1-API-005",
    "M1-TST-004",
    "M1-TST-005",
    "M1-TST-006",
    "M1-TST-007",
    "M1-PLAT-003",
)


def _load(path: Path, schema: str) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema") != schema:
        raise ValueError(f"invalid evidence schema path={path} expected={schema}")
    return cast(dict[str, object], raw)


def _acceptance(payload: dict[str, object]) -> dict[str, bool]:
    raw = payload.get("acceptance")
    if not isinstance(raw, dict):
        raise ValueError("evidence acceptance must be an object")
    if not all(isinstance(key, str) and isinstance(value, bool) for key, value in raw.items()):
        raise ValueError("evidence acceptance must contain boolean values")
    return cast(dict[str, bool], raw)


def _revision(payload: dict[str, object], expected: str) -> bool:
    return payload.get("source_revision") == expected


def run(
    *,
    expected_revision: str,
    windows_backend: Path,
    linux_backend: Path,
    windows_service: Path,
    linux_service: Path,
    service_logical: Path,
    storage_parity: Path,
    output: Path,
) -> int:
    if len(expected_revision) != 40:
        raise ValueError("expected_revision must be an exact 40-character Git SHA")

    wb = _load(windows_backend, BACKEND_SCHEMA)
    lb = _load(linux_backend, BACKEND_SCHEMA)
    ws = _load(windows_service, SERVICE_SCHEMA)
    ls = _load(linux_service, SERVICE_SCHEMA)
    logical = _load(service_logical, SERVICE_EQ_SCHEMA)
    storage = _load(storage_parity, STORAGE_SCHEMA)

    revisions = {
        "windows_backend": _revision(wb, expected_revision),
        "linux_backend": _revision(lb, expected_revision),
        "windows_service": _revision(ws, expected_revision),
        "linux_service": _revision(ls, expected_revision),
        "service_logical": _revision(logical, expected_revision),
        "storage_parity": _revision(storage, expected_revision),
    }

    wb_acceptance = _acceptance(wb)
    lb_acceptance = _acceptance(lb)
    storage_acceptance = _acceptance(storage)

    backend_tasks = tuple(task for task in TASK_IDS if task not in {"M1-STO-003", "M1-PLAT-003"})
    acceptance: dict[str, bool] = {}
    for task_id in backend_tasks:
        acceptance[task_id] = (
            wb.get("status") == "PASS"
            and lb.get("status") == "PASS"
            and wb_acceptance.get(task_id) is True
            and lb_acceptance.get(task_id) is True
        )

    acceptance["M1-STO-001"] = (
        acceptance["M1-STO-001"]
        and storage.get("status") == "PASS"
        and storage_acceptance.get("core_schema_is_frozen_1_6_0") is True
        and storage_acceptance.get("sqlite_publish_pass") is True
        and storage_acceptance.get("postgres_publish_pass") is True
    )
    acceptance["M1-STO-003"] = (
        storage.get("status") == "PASS"
        and storage_acceptance.get("logical_release_membership_equal") is True
        and storage_acceptance.get("logical_membership_hash_equal") is True
        and storage_acceptance.get("receipt_identity_equal") is True
    )
    acceptance["M1-PLAT-003"] = (
        ws.get("status") == "PASS"
        and ls.get("status") == "PASS"
        and logical.get("status") == "PASS"
        and logical.get("exact_logical_equality") is True
        and logical.get("source_revision_equal") is True
        and logical.get("both_platforms_pass") is True
        and logical.get("logical_product_equal") is True
        and logical.get("acceptance_equal") is True
    )

    revisions_equal = all(revisions.values())
    backend_acceptance_equal = wb_acceptance == lb_acceptance
    all_rows_present = set(acceptance) == set(TASK_IDS)
    all_rows_pass = all(acceptance.get(task_id) is True for task_id in TASK_IDS)
    failed_acceptance = [
        task_id for task_id in TASK_IDS if acceptance.get(task_id) is not True
    ]

    review_checks = {
        "all_source_revisions_exact": revisions_equal,
        "windows_linux_backend_acceptance_equal": backend_acceptance_equal,
        "all_18_rows_present": all_rows_present,
        "all_18_rows_pass": all_rows_pass,
    }
    status = "PASS" if all(review_checks.values()) and not failed_acceptance else "FAIL"

    payload: dict[str, object] = {
        "schema": REVIEW_SCHEMA,
        "tracking_issue": 87,
        "source_revision": expected_revision,
        "status": status,
        "task_ids": list(TASK_IDS),
        "acceptance": {task_id: acceptance.get(task_id, False) for task_id in TASK_IDS},
        "failed_acceptance": failed_acceptance,
        "review_checks": review_checks,
        "revision_checks": revisions,
        "evidence": {
            "windows_backend": str(windows_backend),
            "linux_backend": str(linux_backend),
            "windows_service": str(windows_service),
            "linux_service": str(linux_service),
            "service_logical": str(service_logical),
            "storage_parity": str(storage_parity),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--windows-backend", type=Path, required=True)
    parser.add_argument("--linux-backend", type=Path, required=True)
    parser.add_argument("--windows-service", type=Path, required=True)
    parser.add_argument("--linux-service", type=Path, required=True)
    parser.add_argument("--service-logical", type=Path, required=True)
    parser.add_argument("--storage-parity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        return run(
            expected_revision=args.expected_revision,
            windows_backend=args.windows_backend,
            linux_backend=args.linux_backend,
            windows_service=args.windows_service,
            linux_service=args.linux_service,
            service_logical=args.service_logical,
            storage_parity=args.storage_parity,
            output=args.output,
        )
    except Exception as exc:  # noqa: BLE001 - review must fail closed
        print(f"M1_BATCH_2_REVIEW_FAIL {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
