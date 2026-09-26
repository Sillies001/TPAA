#!/usr/bin/env python3
"""Cross-platform comparison for incremental M2-MET-005 evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

SCHEMA = "TPAA_M2_MET_005_SNS_ACCURACY_INCREMENTAL_EVIDENCE_V1"


def _load(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{path}: root must be string-keyed object")
    return cast(dict[str, object], value)


def compare(windows_path: Path, linux_path: Path, *, expected_revision: str) -> dict[str, object]:
    windows = _load(windows_path)
    linux = _load(linux_path)
    checks = {
        "schemas_exact": windows.get("schema") == linux.get("schema") == SCHEMA,
        "tasks_exact": windows.get("task_id") == linux.get("task_id") == "M2-MET-005",
        "statuses_pass": windows.get("status") == linux.get("status") == "PASS",
        "tasks_remain_incomplete": windows.get("task_complete") is False
        and linux.get("task_complete") is False,
        "implementation_complete": windows.get("implementation_complete") is True
        and linux.get("implementation_complete") is True,
        "formal_completion_not_blocked_by_authority": (
            windows.get("formal_completion_blocked_by_authority") is False
            and linux.get("formal_completion_blocked_by_authority") is False
        ),
        "formal_completion_blocked_by_profile_integration": (
            windows.get("formal_completion_blocked_by_profile_integration") is True
            and linux.get("formal_completion_blocked_by_profile_integration") is True
        ),
        "revisions_exact": windows.get("source_revision")
        == linux.get("source_revision")
        == expected_revision,
        "logical_products_equal": windows.get("logical_product") == linux.get("logical_product"),
        "acceptance_equal": windows.get("acceptance") == linux.get("acceptance"),
        "authority_gaps_empty": (
            windows.get("authority_gaps") == {}
            and linux.get("authority_gaps") == {}
        ),
        "invalid_qa_payload_error_codes_equal": (
            windows.get("invalid_qa_payload_error_code")
            == linux.get("invalid_qa_payload_error_code")
        ),
        "fixture_profile_missing_fields_equal": (
            windows.get("fixture_profile_missing_fields")
            == linux.get("fixture_profile_missing_fields")
        ),
        "scope_equal": windows.get("scope") == linux.get("scope"),
        "failed_acceptance_empty": windows.get("failed_acceptance") == []
        and linux.get("failed_acceptance") == [],
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    return {
        "schema": "TPAA_M2_MET_005_SNS_ACCURACY_INCREMENTAL_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": "M2-MET-005",
        "tracking_issue": 97,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": False,
        "implementation_complete": not failed,
        "formal_completion_blocked_by_authority": False,
        "formal_completion_blocked_by_profile_integration": True,
        "source_revision": expected_revision,
        "authority_gaps": windows.get("authority_gaps"),
        "invalid_qa_payload_error_code": windows.get("invalid_qa_payload_error_code"),
        "fixture_profile_missing_fields": windows.get("fixture_profile_missing_fields"),
        "scope": windows.get("scope"),
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
        payload = compare(args.windows, args.linux, expected_revision=args.expected_revision)
        return_code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M2_MET_005_SNS_ACCURACY_INCREMENTAL_CROSS_PLATFORM_EVIDENCE_V1",
            "task_id": "M2-MET-005",
            "tracking_issue": 97,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
            "formal_completion_blocked_by_authority": False,
            "formal_completion_blocked_by_profile_integration": True,
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
