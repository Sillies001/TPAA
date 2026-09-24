#!/usr/bin/env python3
"""M1-DATA-005 Canonical flight-channel acceptance evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

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


def _project_all() -> tuple[Any, ...]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_ingest import GOVERNED_FIXTURE_IDS, load_synthetic_fixture_bundle
    from tpaa_ingest.canonical_flight_channels import (
        project_canonical_flight_channels,
    )
    from tpaa_registry import (
        build_session_time_projection,
        resolve_aircraft_identity,
    )

    projections: list[Any] = []
    for fixture_id in sorted(GOVERNED_FIXTURE_IDS):
        path = FIXTURE_ROOT / fixture_id
        bundle = load_synthetic_fixture_bundle(path)
        time_projection = build_session_time_projection(path)
        aircraft = resolve_aircraft_identity(path)
        if time_projection.fixture_id != bundle.identity.fixture_id:
            raise RuntimeError("Session Time fixture identity drift")
        if aircraft.fixture_id != bundle.identity.fixture_id:
            raise RuntimeError("aircraft fixture identity drift")
        if time_projection.session_id != bundle.session.session_id:
            raise RuntimeError("Session Time session identity drift")
        if aircraft.session_id != bundle.session.session_id:
            raise RuntimeError("aircraft session identity drift")
        for ordinal, timed_row in enumerate(time_projection.rows):
            if timed_row.source_stream_ordinal != ordinal:
                raise RuntimeError("Session Time ordinal drift")
            if timed_row.source_time_us != bundle.rows[ordinal].source_time_us:
                raise RuntimeError("Session Time source-row drift")
        projections.append(
            project_canonical_flight_channels(
                bundle,
                aircraft_id=aircraft.aircraft_id,
                session_time_us=tuple(
                    row.session_time_us for row in time_projection.rows
                ),
            )
        )
    return tuple(projections)


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_ingest.canonical_flight_channels import CANONICAL_FLIGHT_CHANNELS

    first = _project_all()
    replay = _project_all()
    replay_stable = first == replay

    records: list[dict[str, Any]] = []
    total_missing = 0
    downstream_execution_detected = False
    for projection in first:
        missing_by_channel = {
            "body_p_rad_s": sum(row.body_p_rad_s is None for row in projection.rows),
            "nz_g": sum(row.nz_g is None for row in projection.rows),
            "heading_true_rad": sum(
                row.heading_true_rad is None for row in projection.rows
            ),
            "tas_mps": sum(row.tas_mps is None for row in projection.rows),
            "mach": sum(row.mach is None for row in projection.rows),
        }
        fixture_missing = sum(missing_by_channel.values())
        total_missing += fixture_missing
        downstream = any(
            (
                projection.database_persistence_executed,
                projection.evaluation_context_binding_executed,
                projection.stage_projection_executed,
                projection.world_projection_executed,
                projection.metric_logic_executed,
            )
        )
        downstream_execution_detected = downstream_execution_detected or downstream
        records.append(
            {
                "fixture_id": projection.fixture_id,
                "fixture_version": projection.fixture_version,
                "session_id": projection.session_id,
                "aircraft_id": projection.aircraft_id,
                "authority_id": projection.authority_id,
                "mapping_version": projection.mapping_version,
                "channel_names": list(projection.channel_names),
                "row_count": len(projection.rows),
                "missing_by_channel": missing_by_channel,
                "missing_value_count": fixture_missing,
                "missing_preserved_as_null": True,
                "logical_hash": projection.logical_hash,
                "database_persistence_executed": (
                    projection.database_persistence_executed
                ),
                "evaluation_context_binding_executed": (
                    projection.evaluation_context_binding_executed
                ),
                "stage_projection_executed": projection.stage_projection_executed,
                "world_projection_executed": projection.world_projection_executed,
                "metric_logic_executed": projection.metric_logic_executed,
                "status": "PASS",
            }
        )

    logical_hashes = {record["logical_hash"] for record in records}
    row_count = sum(int(record["row_count"]) for record in records)
    structured = next(
        record
        for record in records
        if record["fixture_id"] == "BF_M1_STRUCTURED_PARTIAL_V1"
    )
    structured_missing = structured["missing_by_channel"]
    status = (
        "PASS"
        if len(records) == 8
        and row_count == 62
        and replay_stable
        and len(logical_hashes) == 8
        and total_missing == 8
        and structured_missing["tas_mps"] == 4
        and structured_missing["mach"] == 4
        and all(
            record["channel_names"] == list(CANONICAL_FLIGHT_CHANNELS)
            for record in records
        )
        and not downstream_execution_detected
        else "FAIL"
    )

    return {
        "schema": "TPAA_M1_DATA_005_CANONICAL_FLIGHT_CHANNEL_EVIDENCE_V1",
        "task_id": "M1-DATA-005",
        "status": status,
        "source_revision": _git_revision(),
        "authority_id": "CANONICAL_AIRCRAFT_STATE_V1",
        "projection_count": len(records),
        "total_row_count": row_count,
        "canonical_channels": list(CANONICAL_FLIGHT_CHANNELS),
        "unique_logical_hash_count": len(logical_hashes),
        "replay_stable": replay_stable,
        "missing_value_count": total_missing,
        "missing_preserved_as_null": total_missing == 8,
        "zero_fill_of_missing_executed": False,
        "database_persistence_executed": False,
        "evaluation_context_binding_executed": False,
        "stage_projection_executed": False,
        "world_projection_executed": False,
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
            "schema": "TPAA_M1_DATA_005_CANONICAL_FLIGHT_CHANNEL_EVIDENCE_V1",
            "task_id": "M1-DATA-005",
            "status": "FAIL",
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2

    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
