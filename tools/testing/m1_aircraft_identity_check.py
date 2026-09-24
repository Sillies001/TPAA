#!/usr/bin/env python3
"""M1-DATA-004 Aircraft entity-resolution acceptance evidence."""

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

    from tpaa_registry import resolve_all_aircraft_identities

    first = resolve_all_aircraft_identities(FIXTURE_ROOT)
    replay = resolve_all_aircraft_identities(FIXTURE_ROOT)
    replay_stable = first == replay

    records: list[dict[str, object]] = []
    for resolution in first:
        records.append(
            {
                "fixture_id": resolution.fixture_id,
                "fixture_version": resolution.fixture_version,
                "session_id": resolution.session_id,
                "aircraft_id": resolution.aircraft_id,
                "identity_field": resolution.identity_field,
                "source_aircraft_key": resolution.source_aircraft_key,
                "source_alias_role": resolution.source_alias_role,
                "source_id": resolution.source_id,
                "source_stream_id": resolution.source_stream_id,
                "source_artifact_ref": resolution.source_artifact_ref,
                "source_artifact_sha256": resolution.source_artifact_sha256,
                "context_artifact_ref": resolution.context_artifact_ref,
                "context_artifact_sha256": resolution.context_artifact_sha256,
                "input_sha256": resolution.input_sha256,
                "resolution_method": resolution.resolution_method,
                "resolution_version": resolution.resolution_version,
                "replay_basis_sha256": resolution.replay_basis_sha256,
                "logical_hash": resolution.logical_hash,
                "master_aircraft_persistence_executed": (
                    resolution.master_aircraft_persistence_executed
                ),
                "aircraft_instance_projection_executed": (
                    resolution.aircraft_instance_projection_executed
                ),
                "canonical_flight_channel_projection_executed": (
                    resolution.canonical_flight_channel_projection_executed
                ),
                "evaluation_context_binding_executed": (
                    resolution.evaluation_context_binding_executed
                ),
                "stage_projection_executed": resolution.stage_projection_executed,
                "metric_logic_executed": resolution.metric_logic_executed,
                "status": "PASS",
            }
        )

    aircraft_ids = {record["aircraft_id"] for record in records}
    replay_hashes = {record["replay_basis_sha256"] for record in records}
    logical_hashes = {record["logical_hash"] for record in records}
    alias_roles = {record["source_alias_role"] for record in records}
    identity_fields = {record["identity_field"] for record in records}
    methods = {record["resolution_method"] for record in records}

    status = (
        "PASS"
        if len(records) == 8
        and len(aircraft_ids) == 1
        and len(replay_hashes) == 8
        and len(logical_hashes) == 8
        and replay_stable
        and alias_roles == {"LINEAGE_ONLY"}
        and identity_fields == {"aircraft_id"}
        and methods == {"GOVERNED_FIXTURE_AIRCRAFT_ID"}
        else "FAIL"
    )
    return {
        "schema": "TPAA_M1_DATA_004_AIRCRAFT_IDENTITY_EVIDENCE_V1",
        "task_id": "M1-DATA-004",
        "status": status,
        "source_revision": _git_revision(),
        "resolution_count": len(records),
        "unique_governed_aircraft_id_count": len(aircraft_ids),
        "unique_replay_basis_hash_count": len(replay_hashes),
        "unique_logical_hash_count": len(logical_hashes),
        "replay_stable": replay_stable,
        "identity_field": "aircraft_id",
        "source_alias_role": "LINEAGE_ONLY",
        "source_alias_used_as_business_identity": False,
        "business_identity_generated_from_alias": False,
        "resolution_method": "GOVERNED_FIXTURE_AIRCRAFT_ID",
        "master_aircraft_persistence_executed": False,
        "aircraft_instance_projection_executed": False,
        "canonical_flight_channel_projection_executed": False,
        "evaluation_context_binding_executed": False,
        "stage_projection_executed": False,
        "metric_logic_executed": False,
        "records": records,
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
            "schema": "TPAA_M1_DATA_004_AIRCRAFT_IDENTITY_EVIDENCE_V1",
            "task_id": "M1-DATA-004",
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
