#!/usr/bin/env python3
"""Cross-platform comparison for the M2 Batch 2 authority-gap sentinel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

SCHEMA = "TPAA_M2_BATCH_2_AUTHORITY_GAP_SENTINEL_V1"


def _load(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{path}: root must be string-keyed object")
    return cast(dict[str, object], value)


def compare(
    windows_path: Path,
    linux_path: Path,
    *,
    expected_revision: str,
) -> dict[str, object]:
    windows = _load(windows_path)
    linux = _load(linux_path)
    checks = {
        "schemas_exact": windows.get("schema") == linux.get("schema") == SCHEMA,
        "statuses_pass": windows.get("status") == linux.get("status") == "PASS",
        "revisions_exact": (
            windows.get("source_revision")
            == linux.get("source_revision")
            == expected_revision
        ),
        "resolution_stays_blocked": (
            windows.get("authority_resolution_ready") is False
            and linux.get("authority_resolution_ready") is False
        ),
        "tasks_stay_incomplete": (
            windows.get("task_complete") is False
            and linux.get("task_complete") is False
        ),
        "blocked_tasks_equal": windows.get("blocked_tasks") == linux.get("blocked_tasks"),
        "scope_equal": windows.get("scope") == linux.get("scope"),
        "logical_products_equal": (
            windows.get("logical_product") == linux.get("logical_product")
        ),
        "acceptance_equal": windows.get("acceptance") == linux.get("acceptance"),
        "failed_acceptance_empty": (
            windows.get("failed_acceptance") == []
            and linux.get("failed_acceptance") == []
        ),
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    return {
        "schema": "TPAA_M2_BATCH_2_AUTHORITY_GAP_SENTINEL_CROSS_PLATFORM_V1",
        "tracking_issue": 97,
        "baseline_change_issue": 106,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": expected_revision,
        "authority_resolution_ready": False,
        "task_complete": False,
        "logical_product": windows.get("logical_product"),
        "checks": checks,
        "failed_acceptance": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--linux", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = compare(
            args.windows,
            args.linux,
            expected_revision=args.expected_revision,
        )
        return_code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M2_BATCH_2_AUTHORITY_GAP_SENTINEL_CROSS_PLATFORM_V1",
            "tracking_issue": 97,
            "baseline_change_issue": 106,
            "status": "FAIL",
            "source_revision": args.expected_revision,
            "authority_resolution_ready": False,
            "task_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
