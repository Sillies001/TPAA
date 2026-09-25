"""Exact Windows/Linux comparison for M1 Batch 1 logical evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

EXPECTED_SCHEMA = "TPAA_M1_BATCH_1_CORE_EVIDENCE_V1"


def _load(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema") != EXPECTED_SCHEMA:
        raise ValueError(f"invalid Batch 1 evidence: {path}")
    return cast(dict[str, object], raw)


def run(windows: Path, linux: Path, expected_revision: str, evidence: Path) -> int:
    windows_payload = _load(windows)
    linux_payload = _load(linux)
    exact = windows_payload == linux_payload
    revisions_exact = windows_payload.get("source_revision") == linux_payload.get("source_revision") == expected_revision
    payload: dict[str, object] = {
        "schema": "TPAA_M1_BATCH_1_LOGICAL_EQUIVALENCE_V1",
        "batch_id": "M1-BATCH-1-CORE-PRODUCT",
        "source_revision": expected_revision,
        "status": "PASS" if exact and revisions_exact else "FAIL",
        "exact_logical_equality": exact,
        "world_hashes_equal": (
            windows_payload.get("world_logical_hashes") == linux_payload.get("world_logical_hashes")
        ),
        "metric_batch_hashes_equal": (
            windows_payload.get("metric_batch_hashes") == linux_payload.get("metric_batch_hashes")
        ),
        "acceptance_equal": windows_payload.get("acceptance") == linux_payload.get("acceptance"),
        "source_revisions_exact": revisions_exact,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if exact and revisions_exact else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--linux", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    return run(args.windows, args.linux, args.expected_revision, args.evidence)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
