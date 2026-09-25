#!/usr/bin/env python3
"""Fail-closed ten-row review for M1 coarse Batch 3 / Issue #89."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "TPAA_M1_BATCH_3_REVIEW_V1"
TASK_IDS = (
    "M1-GUI-001",
    "M1-GUI-002",
    "M1-GUI-003",
    "M1-GUI-004",
    "M1-GUI-005",
    "M1-GUI-006",
    "M1-GUI-007",
    "M1-TST-008",
    "M1-PLAT-001",
    "M1-PLAT-002",
)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"evidence must be an object: {path}")
    return payload


def run(
    *,
    windows: Path,
    linux: Path,
    logical: Path,
    expected_revision: str,
    output: Path,
) -> int:
    win = _load(windows)
    lin = _load(linux)
    eq = _load(logical)
    win_rows = win.get("acceptance")
    lin_rows = lin.get("acceptance")
    win_rows = win_rows if isinstance(win_rows, dict) else {}
    lin_rows = lin_rows if isinstance(lin_rows, dict) else {}

    task_acceptance = {
        task: (
            win_rows.get(task) is True and lin_rows.get(task) is True
            if task in TASK_IDS[:8]
            else win_rows.get(task) is True
            if task == "M1-PLAT-001"
            else lin_rows.get(task) is True
        )
        for task in TASK_IDS
    }
    revision_checks = {
        "windows_revision_exact": win.get("source_revision") == expected_revision,
        "linux_revision_exact": lin.get("source_revision") == expected_revision,
        "logical_revision_exact": eq.get("source_revision") == expected_revision,
        "windows_status_pass": win.get("status") == "PASS",
        "linux_status_pass": lin.get("status") == "PASS",
        "logical_status_pass": eq.get("status") == "PASS",
    }
    failed_acceptance = sorted(task for task, passed in task_acceptance.items() if not passed)
    failed_revision_checks = sorted(
        name for name, passed in revision_checks.items() if not passed
    )
    status = "PASS" if not failed_acceptance and not failed_revision_checks else "FAIL"
    payload = {
        "schema": SCHEMA,
        "tracking_issue": 89,
        "source_revision": expected_revision,
        "status": status,
        "task_ids": list(TASK_IDS),
        "acceptance": task_acceptance,
        "failed_acceptance": failed_acceptance,
        "revision_checks": revision_checks,
        "failed_revision_checks": failed_revision_checks,
        "all_10_rows_present": set(task_acceptance) == set(TASK_IDS),
        "all_10_rows_pass": all(task_acceptance.values()),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--linux", type=Path, required=True)
    parser.add_argument("--logical", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    return run(
        windows=args.windows,
        linux=args.linux,
        logical=args.logical,
        expected_revision=args.expected_revision,
        output=args.output,
    )


if __name__ == "__main__":
    raise SystemExit(main())
