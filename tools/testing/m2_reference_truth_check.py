#!/usr/bin/env python3
"""M2-DATA-001 reference-relative truth acceptance evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "m2" / "RT_M2_NOMINAL_V1"


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

    from tpaa_ingest import load_m2_reference_truth

    first = load_m2_reference_truth(FIXTURE)
    second = load_m2_reference_truth(FIXTURE)
    required_uncertainty_refs = {
        "own_attitude_uncertainty_ref",
        "own_position_uncertainty_ref",
        "target_attitude_uncertainty_ref",
        "target_position_uncertainty_ref",
        "time_alignment_uncertainty_ref",
    }
    pair_identity_complete = all(
        (
            first.own_identity.aircraft_id,
            first.own_identity.identity_ref,
            first.own_identity.source_entity_key,
            first.target_identity.aircraft_id,
            first.target_identity.identity_ref,
            first.target_identity.source_entity_key,
        )
    )
    frame_provenance_complete = all(
        (
            first.frame_provenance.position_frame,
            first.frame_provenance.velocity_frame,
            first.frame_provenance.own_attitude_frame_ref,
        )
    )
    time_provenance_complete = bool(
        first.time_transform_id
        and first.time_transform_hash
        and first.source_time_basis
        and all(row.session_time_us > 0 for row in first.rows)
    )
    uncertainty_provenance_complete = all(
        required_uncertainty_refs <= set(row.uncertainty_refs)
        and set(row.uncertainty_refs.values()) <= set(first.uncertainty_records)
        for row in first.rows
    )
    replay_stable = first == second and first.logical_hash == second.logical_hash
    acceptance = {
        "pair_identity_complete": pair_identity_complete,
        "frame_provenance_complete": frame_provenance_complete,
        "time_provenance_complete": time_provenance_complete,
        "uncertainty_provenance_complete": uncertainty_provenance_complete,
        "replay_stable": replay_stable,
        "metric_logic_not_executed": not first.metric_logic_executed,
        "stage_projection_not_executed": not first.stage_projection_executed,
        "persistence_not_executed": not first.persistence_executed,
    }
    failed_acceptance = sorted(key for key, value in acceptance.items() if not value)
    status = "PASS" if not failed_acceptance else "FAIL"
    return {
        "schema": "TPAA_M2_DATA_001_REFERENCE_TRUTH_EVIDENCE_V1",
        "task_id": "M2-DATA-001",
        "tracking_issue": 96,
        "status": status,
        "source_revision": _git_revision(),
        "fixture_id": first.fixture_id,
        "fixture_version": first.fixture_version,
        "input_sha256": first.input_sha256,
        "source_sha256": first.source_sha256,
        "logical_hash": first.logical_hash,
        "metric_codes": ["P1-QA-001", "P1-QA-002"],
        "row_count": len(first.rows),
        "pair_identity_complete": pair_identity_complete,
        "frame_provenance_complete": frame_provenance_complete,
        "time_provenance_complete": time_provenance_complete,
        "uncertainty_provenance_complete": uncertainty_provenance_complete,
        "replay_stable": replay_stable,
        "metric_logic_executed": first.metric_logic_executed,
        "stage_projection_executed": first.stage_projection_executed,
        "persistence_executed": first.persistence_executed,
        "acceptance": acceptance,
        "failed_acceptance": failed_acceptance,
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
            "schema": "TPAA_M2_DATA_001_REFERENCE_TRUTH_EVIDENCE_V1",
            "task_id": "M2-DATA-001",
            "tracking_issue": 96,
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
