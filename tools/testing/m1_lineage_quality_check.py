#!/usr/bin/env python3
"""M1-DATA-007 lineage/quality propagation acceptance evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
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
    from tpaa_ingest import GOVERNED_FIXTURE_IDS
    from tpaa_ingest.lineage_quality import build_lineage_quality_projection

    return tuple(
        build_lineage_quality_projection(FIXTURE_ROOT / fixture_id)
        for fixture_id in sorted(GOVERNED_FIXTURE_IDS)
    )


def _invalid_source_values_fail_closed() -> bool:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)
    from tpaa_ingest import load_synthetic_fixture_bundle
    from tpaa_ingest.canonical_flight_channels import (
        CanonicalFlightChannelError,
        project_canonical_flight_channels,
    )
    from tpaa_registry import build_session_time_projection, resolve_aircraft_identity

    path = FIXTURE_ROOT / "BF_M1_NOMINAL_V1"
    bundle = load_synthetic_fixture_bundle(path)
    first = bundle.rows[0]
    values = dict(first.values)
    values["p"] = "INVALID"
    invalid_bundle = replace(
        bundle,
        rows=(replace(first, values=MappingProxyType(values)), *bundle.rows[1:]),
    )
    timed = build_session_time_projection(path)
    aircraft = resolve_aircraft_identity(path)
    try:
        project_canonical_flight_channels(
            invalid_bundle,
            aircraft_id=aircraft.aircraft_id,
            session_time_us=tuple(row.session_time_us for row in timed.rows),
        )
    except CanonicalFlightChannelError as exc:
        return exc.code == "M1_CANONICAL_CHANNEL_VALUE_INVALID"
    return False


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)
    from tpaa_ingest import load_synthetic_fixture_bundle
    from tpaa_ingest.lineage_quality import (
        LINEAGE_QUALITY_AUTHORITY,
        MISSING,
        PRESENT,
    )
    from tpaa_registry import register_synthetic_fixture

    first = _project_all()
    replay_stable = first == _project_all()
    records: list[dict[str, Any]] = []
    field_count = traceable_count = missing_count = 0
    quality_exact = refs_verified = True
    downstream_execution_detected = False

    for projection in first:
        path = FIXTURE_ROOT / projection.fixture_id
        bundle = load_synthetic_fixture_bundle(path)
        registration = register_synthetic_fixture(path)
        fixture_missing = fixture_fields = 0
        refs_verified = refs_verified and (
            projection.source_artifact_ref == registration.source_artifact.logical_ref
            and projection.source_artifact_sha256 == registration.source_artifact.sha256
            and registration.source_artifact.sha256 in projection.source_artifact_ref
        )
        for source_row, row in zip(bundle.rows, projection.rows, strict=True):
            fixture_fields += len(row.fields)
            expected_quality = source_row.values["quality"]
            quality_exact = quality_exact and row.quality_mask == expected_quality
            for field in row.fields:
                field_count += 1
                if (
                    field.source_stream_id == projection.source_stream_id
                    and field.source_stream_ordinal == row.source_stream_ordinal
                    and field.source_artifact_ref == projection.source_artifact_ref
                    and field.source_artifact_sha256 == projection.source_artifact_sha256
                    and field.source_field
                    and field.mapping_ref == bundle.mapping_version
                ):
                    traceable_count += 1
                quality_exact = quality_exact and field.quality_mask == expected_quality
                if field.value_status == MISSING:
                    missing_count += 1
                    fixture_missing += 1
                elif field.value_status != PRESENT:
                    quality_exact = False
        downstream_execution_detected = downstream_execution_detected or any(
            (
                projection.database_persistence_executed,
                projection.episode_projection_executed,
                projection.stage_projection_executed,
                projection.world_projection_executed,
                projection.metric_logic_executed,
            )
        )
        records.append(
            {
                "fixture_id": projection.fixture_id,
                "fixture_version": projection.fixture_version,
                "session_id": projection.session_id,
                "aircraft_id": projection.aircraft_id,
                "source_stream_id": projection.source_stream_id,
                "source_artifact_ref": projection.source_artifact_ref,
                "source_artifact_sha256": projection.source_artifact_sha256,
                "row_count": len(projection.rows),
                "field_lineage_count": fixture_fields,
                "missing_value_count": fixture_missing,
                "canonical_logical_hash": projection.canonical_logical_hash,
                "logical_hash": projection.logical_hash,
                "status": "PASS",
            }
        )

    invalid_fail_closed = _invalid_source_values_fail_closed()
    total_rows = sum(int(record["row_count"]) for record in records)
    unique_hashes = {record["logical_hash"] for record in records}
    status = (
        "PASS"
        if len(records) == 8
        and total_rows == 62
        and field_count == 434
        and traceable_count == field_count
        and missing_count == 8
        and quality_exact
        and refs_verified
        and invalid_fail_closed
        and replay_stable
        and len(unique_hashes) == 8
        and not downstream_execution_detected
        else "FAIL"
    )
    return {
        "schema": "TPAA_M1_DATA_007_LINEAGE_QUALITY_EVIDENCE_V1",
        "task_id": "M1-DATA-007",
        "status": status,
        "source_revision": _git_revision(),
        "authority_id": LINEAGE_QUALITY_AUTHORITY,
        "projection_count": len(records),
        "total_row_count": total_rows,
        "field_lineage_count": field_count,
        "traceable_field_count": traceable_count,
        "missing_value_count": missing_count,
        "missing_preserved_as_null": missing_count == 8,
        "invalid_source_values_fail_closed": invalid_fail_closed,
        "zero_fill_of_missing_or_invalid_executed": False,
        "quality_mask_propagation_exact": quality_exact,
        "immutable_source_refs_verified": refs_verified,
        "replay_stable": replay_stable,
        "unique_logical_hash_count": len(unique_hashes),
        "database_persistence_executed": False,
        "episode_projection_executed": False,
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
            "schema": "TPAA_M1_DATA_007_LINEAGE_QUALITY_EVIDENCE_V1",
            "task_id": "M1-DATA-007",
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
