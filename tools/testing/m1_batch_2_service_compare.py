"""Exact Windows/Linux comparison for M1 Batch 2 service smoke evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

EXPECTED_SCHEMA = "TPAA_M1_BATCH_2_SERVICE_SMOKE_V1"


def _load(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema") != EXPECTED_SCHEMA:
        raise ValueError(f"invalid Batch 2 service evidence: {path}")
    return cast(dict[str, object], raw)


def run(windows: Path, linux: Path, evidence: Path) -> int:
    windows_payload = _load(windows)
    linux_payload = _load(linux)
    source_revision_equal = (
        windows_payload.get("source_revision") == linux_payload.get("source_revision")
    )
    both_pass = (
        windows_payload.get("status") == "PASS"
        and linux_payload.get("status") == "PASS"
    )
    logical_product_equal = (
        windows_payload.get("logical_product") == linux_payload.get("logical_product")
    )
    acceptance_equal = (
        windows_payload.get("acceptance") == linux_payload.get("acceptance")
    )
    exact = (
        source_revision_equal
        and both_pass
        and logical_product_equal
        and acceptance_equal
    )
    payload: dict[str, object] = {
        "schema": "TPAA_M1_BATCH_2_SERVICE_LOGICAL_EQUIVALENCE_V1",
        "tracking_issue": 87,
        "task_ids": ["M1-PLAT-003"],
        "source_revision": windows_payload.get("source_revision"),
        "status": "PASS" if exact else "FAIL",
        "exact_logical_equality": exact,
        "source_revision_equal": source_revision_equal,
        "both_platforms_pass": both_pass,
        "logical_product_equal": logical_product_equal,
        "acceptance_equal": acceptance_equal,
    }
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if exact else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--linux", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    return run(args.windows, args.linux, args.evidence)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
