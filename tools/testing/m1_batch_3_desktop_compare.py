#!/usr/bin/env python3
"""Compare Windows/Linux M1 Batch 3 Desktop logical products."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "TPAA_M1_BATCH_3_DESKTOP_LOGICAL_EQUIVALENCE_V1"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"evidence must be an object: {path}")
    return payload


def run(*, windows: Path, linux: Path, expected_revision: str, evidence: Path) -> int:
    win = _load(windows)
    lin = _load(linux)
    acceptance = {
        "windows_status_pass": win.get("status") == "PASS",
        "linux_status_pass": lin.get("status") == "PASS",
        "windows_revision_exact": win.get("source_revision") == expected_revision,
        "linux_revision_exact": lin.get("source_revision") == expected_revision,
        "same_fixture": win.get("fixture_id") == lin.get("fixture_id") == "BF_M1_NOMINAL_V1",
        "logical_product_equal": win.get("logical_product") == lin.get("logical_product"),
        "windows_platform_row": (
            isinstance(win.get("acceptance"), dict)
            and win["acceptance"].get("M1-PLAT-001") is True
        ),
        "linux_platform_row": (
            isinstance(lin.get("acceptance"), dict)
            and lin["acceptance"].get("M1-PLAT-002") is True
        ),
    }
    failed = sorted(name for name, passed in acceptance.items() if not passed)
    payload = {
        "schema": SCHEMA,
        "tracking_issue": 89,
        "source_revision": expected_revision,
        "windows_source_revision": win.get("source_revision"),
        "linux_source_revision": lin.get("source_revision"),
        "status": "PASS" if not failed else "FAIL",
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "logical_product": win.get("logical_product") if not failed else None,
    }
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not failed else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--linux", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    return run(
        windows=args.windows,
        linux=args.linux,
        expected_revision=args.expected_revision,
        evidence=args.evidence,
    )


if __name__ == "__main__":
    raise SystemExit(main())
