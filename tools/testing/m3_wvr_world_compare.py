#!/usr/bin/env python3
"""Cross-platform logical comparison for M3-WORLD-001."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

EXPECTED_SCHEMA = "TPAA_M3_WORLD_001_WVR_STAGE_WORLD_EVENT_EVIDENCE_V1"
EXPECTED_TASK_ID = "M3-WORLD-001"
TRACKING_ISSUE = 112


def _load(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(
        isinstance(key, str) for key in raw
    ):
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
        "windows_schema_exact": windows.get("schema") == EXPECTED_SCHEMA,
        "linux_schema_exact": linux.get("schema") == EXPECTED_SCHEMA,
        "windows_task_exact": windows.get("task_id") == EXPECTED_TASK_ID,
        "linux_task_exact": linux.get("task_id") == EXPECTED_TASK_ID,
        "windows_tracking_issue_exact": (
            windows.get("tracking_issue") == TRACKING_ISSUE
        ),
        "linux_tracking_issue_exact": (
            linux.get("tracking_issue") == TRACKING_ISSUE
        ),
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
        "schema": "TPAA_M3_WORLD_001_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": EXPECTED_TASK_ID,
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": expected_revision,
        "windows_source_revision": windows.get("source_revision"),
        "linux_source_revision": linux.get("source_revision"),
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
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M3_WORLD_001_CROSS_PLATFORM_EVIDENCE_V1",
            "task_id": EXPECTED_TASK_ID,
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "source_revision": args.expected_revision,
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(
        rendered,
        encoding="utf-8",
        newline="\n",
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
