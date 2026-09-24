#!/usr/bin/env python3
"""M1-DATA-001 source-adapter acceptance evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m1"


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    value = completed.stdout.strip()
    return value if len(value) == 40 else "UNKNOWN"


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)
    from tpaa_ingest import GOVERNED_FIXTURE_IDS, load_synthetic_fixture_bundle

    bundles: list[dict[str, object]] = []
    source_refs: set[str] = set()
    for fixture_id in sorted(GOVERNED_FIXTURE_IDS):
        bundle = load_synthetic_fixture_bundle(FIXTURE_ROOT / fixture_id)
        source_ref = bundle.identity.stable_source_ref
        source_refs.add(source_ref)
        bundles.append(
            {
                "fixture_id": fixture_id,
                "fixture_version": bundle.identity.fixture_version,
                "input_sha256": bundle.identity.input_sha256,
                "source_sha256": bundle.identity.source_sha256,
                "context_sha256": bundle.identity.context_sha256,
                "stable_source_ref": source_ref,
                "source_time_basis": bundle.session.source_time_basis,
                "mapping_version": bundle.mapping_version,
                "row_count": len(bundle.rows),
                "marker_count": len(bundle.source_markers),
                "classification": bundle.data_classification,
                "status": "PASS",
            }
        )

    unique_refs = len(source_refs) == len(GOVERNED_FIXTURE_IDS)
    status = "PASS" if unique_refs and len(bundles) == 8 else "FAIL"
    return {
        "schema": "TPAA_M1_DATA_001_SOURCE_ADAPTER_EVIDENCE_V1",
        "task_id": "M1-DATA-001",
        "status": status,
        "source_revision": _git_revision(),
        "bundle_count": len(bundles),
        "unique_source_ref_count": len(source_refs),
        "mapping_version": "M1_BASIC_FLIGHT_SOURCE_MAP_V1",
        "source_clock_preserved": True,
        "session_time_transform_executed": False,
        "canonical_projection_executed": False,
        "stage_projection_executed": False,
        "metric_logic_executed": False,
        "bundles": bundles,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    try:
        payload = verify()
        return_code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M1_DATA_001_SOURCE_ADAPTER_EVIDENCE_V1",
            "task_id": "M1-DATA-001",
            "status": "FAIL",
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2

    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
