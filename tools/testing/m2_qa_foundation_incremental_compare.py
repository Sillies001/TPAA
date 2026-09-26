#!/usr/bin/env python3
"""Cross-platform comparison for formal M2-MET-002 QA evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

SCHEMA = "TPAA_M2_MET_002_INCREMENTAL_QA_EVIDENCE_V1"
TASK_ID = "M2-MET-002"
TRACKING_ISSUE = 97


def _load(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{path}: root must be string-keyed object")
    return cast(dict[str, object], raw)


def compare(
    windows_path: Path,
    linux_path: Path,
    *,
    expected_revision: str,
) -> dict[str, object]:
    windows = _load(windows_path)
    linux = _load(linux_path)
    checks = {
        "windows_schema_exact": windows.get("schema") == SCHEMA,
        "linux_schema_exact": linux.get("schema") == SCHEMA,
        "windows_task_exact": windows.get("task_id") == TASK_ID,
        "linux_task_exact": linux.get("task_id") == TASK_ID,
        "windows_tracking_issue_exact": windows.get("tracking_issue") == TRACKING_ISSUE,
        "linux_tracking_issue_exact": linux.get("tracking_issue") == TRACKING_ISSUE,
        "windows_pass": windows.get("status") == "PASS",
        "linux_pass": linux.get("status") == "PASS",
        "windows_implementation_complete": windows.get("implementation_complete") is True,
        "linux_implementation_complete": linux.get("implementation_complete") is True,
        "windows_task_complete": windows.get("task_complete") is True,
        "linux_task_complete": linux.get("task_complete") is True,
        "windows_authority_ready": windows.get("authority_resolution_ready") is True,
        "linux_authority_ready": linux.get("authority_resolution_ready") is True,
        "windows_authority_not_blocking": (
            windows.get("formal_completion_blocked_by_authority") is False
        ),
        "linux_authority_not_blocking": (
            linux.get("formal_completion_blocked_by_authority") is False
        ),
        "windows_revision_exact": windows.get("source_revision") == expected_revision,
        "linux_revision_exact": linux.get("source_revision") == expected_revision,
        "authority_equal": windows.get("authority") == linux.get("authority"),
        "logical_product_equal": windows.get("logical_product") == linux.get("logical_product"),
        "acceptance_equal": windows.get("acceptance") == linux.get("acceptance"),
        "authority_gaps_empty": (
            windows.get("authority_gaps") == {}
            and linux.get("authority_gaps") == {}
        ),
        "dependency_effects_empty": (
            windows.get("dependency_effects") == {}
            and linux.get("dependency_effects") == {}
        ),
        "blocked_error_codes_empty": (
            windows.get("blocked_error_codes") == {}
            and linux.get("blocked_error_codes") == {}
        ),
        "failed_acceptance_empty": (
            windows.get("failed_acceptance") == []
            and linux.get("failed_acceptance") == []
        ),
    }
    failed_acceptance = sorted(key for key, passed in checks.items() if not passed)
    return {
        "schema": "TPAA_M2_MET_002_INCREMENTAL_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": TASK_ID,
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed_acceptance else "FAIL",
        "implementation_complete": not failed_acceptance,
        "task_complete": not failed_acceptance,
        "formal_completion_blocked_by_authority": False,
        "authority_resolution_ready": True,
        "source_revision": expected_revision,
        "windows_source_revision": windows.get("source_revision"),
        "linux_source_revision": linux.get("source_revision"),
        "authority": windows.get("authority"),
        "logical_product": windows.get("logical_product"),
        "checks": checks,
        "failed_acceptance": failed_acceptance,
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
            "schema": "TPAA_M2_MET_002_INCREMENTAL_CROSS_PLATFORM_EVIDENCE_V1",
            "task_id": TASK_ID,
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "formal_completion_blocked_by_authority": False,
            "authority_resolution_ready": True,
            "source_revision": args.expected_revision,
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
