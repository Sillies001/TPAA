#!/usr/bin/env python3
"""Windows/Linux integrated logical-equivalence for M1 Batch 4 / Issue #88."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "TPAA_M1_BATCH_4_LOGICAL_EQUIVALENCE_V1"
FORBIDDEN_KEYS = {"path", "pid", "native_bytes", "native_byte_hash", "timestamp"}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"evidence must be an object: {path}")
    return payload


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key in FORBIDDEN_KEYS or _contains_forbidden(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden(child) for child in value)
    return False


def run(*, windows: Path, linux: Path, expected_revision: str, evidence: Path) -> int:
    win = _load(windows)
    lin = _load(linux)
    logical_equal = win.get("logical_product") == lin.get("logical_product")
    noise_free = not _contains_forbidden(win.get("logical_product")) and not _contains_forbidden(
        lin.get("logical_product")
    )
    checks = {
        "windows_schema_exact": win.get("schema") == "TPAA_M1_BATCH_4_PLATFORM_V1",
        "linux_schema_exact": lin.get("schema") == "TPAA_M1_BATCH_4_PLATFORM_V1",
        "windows_status_pass": win.get("status") == "PASS",
        "linux_status_pass": lin.get("status") == "PASS",
        "windows_revision_exact": win.get("source_revision") == expected_revision,
        "linux_revision_exact": lin.get("source_revision") == expected_revision,
        "logical_product_equal": logical_equal,
        "logical_product_noise_free": noise_free,
    }
    acceptance = {
        "M1-TST-009": all(checks.values()),
        "M1-PLAT-004": logical_equal and noise_free and all(
            checks[name]
            for name in (
                "windows_schema_exact",
                "linux_schema_exact",
                "windows_status_pass",
                "linux_status_pass",
                "windows_revision_exact",
                "linux_revision_exact",
            )
        ),
    }
    failed_checks = sorted(name for name, passed in checks.items() if not passed)
    failed_acceptance = sorted(name for name, passed in acceptance.items() if not passed)
    payload = {
        "schema": SCHEMA,
        "tracking_issue": 88,
        "source_revision": expected_revision,
        "windows_source_revision": win.get("source_revision"),
        "linux_source_revision": lin.get("source_revision"),
        "status": "PASS" if not failed_checks and not failed_acceptance else "FAIL",
        "acceptance": acceptance,
        "failed_acceptance": failed_acceptance,
        "checks": checks,
        "failed_checks": failed_checks,
        "logical_product": win.get("logical_product") if logical_equal else None,
        "noise_policy": {
            "forbidden_keys": sorted(FORBIDDEN_KEYS),
            "business_results_compared": True,
        },
    }
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 2


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
