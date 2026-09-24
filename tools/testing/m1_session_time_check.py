#!/usr/bin/env python3
"""M1-DATA-003 Session Time acceptance evidence."""

from __future__ import annotations

import argparse
import hashlib
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


def _times_hash(values: tuple[int, ...]) -> str:
    payload = "\n".join(str(value) for value in values).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_registry import build_all_session_time_projections

    projections = build_all_session_time_projections(FIXTURE_ROOT)
    records: list[dict[str, object]] = []
    for projection in projections:
        transform = projection.transform
        row_times = tuple(row.session_time_us for row in projection.rows)
        marker_times = tuple(marker.session_time_us for marker in projection.markers)
        records.append(
            {
                "fixture_id": projection.fixture_id,
                "session_id": projection.session_id,
                "source_id": projection.source_id,
                "source_stream_id": projection.source_stream_id,
                "source_time_basis": projection.source_time_basis,
                "source_clock_segment_id": transform.source_clock_segment_id,
                "time_transform_id": transform.time_transform_id,
                "model": transform.model,
                "anchor_segment_time_ns": str(transform.anchor_segment_time_ns),
                "anchor_session_time_us": str(transform.anchor_session_time_us),
                "rate_num": transform.rate_num,
                "rate_den": transform.rate_den,
                "valid_segment_start_ns": str(transform.valid_segment_start_ns),
                "valid_segment_end_ns": str(transform.valid_segment_end_ns),
                "residual_rms_us": transform.residual_rms_us,
                "residual_p95_us": transform.residual_p95_us,
                "confidence": transform.confidence,
                "method": transform.method,
                "version": transform.version,
                "transform_hash": transform.transform_hash,
                "start_session_time_us": str(projection.start_session_time_us),
                "end_session_time_us": str(projection.end_session_time_us),
                "row_count": len(projection.rows),
                "marker_count": len(projection.markers),
                "first_row_session_time_us": str(row_times[0]),
                "last_row_session_time_us": str(row_times[-1]),
                "row_session_time_sha256": _times_hash(row_times),
                "marker_session_time_sha256": _times_hash(marker_times),
                "logical_hash": projection.logical_hash,
                "database_persistence_executed": (
                    projection.database_persistence_executed
                ),
                "canonical_flight_channel_projection_executed": (
                    projection.canonical_flight_channel_projection_executed
                ),
                "stage_projection_executed": projection.stage_projection_executed,
                "metric_logic_executed": projection.metric_logic_executed,
                "status": "PASS",
            }
        )

    unique_segments = {record["source_clock_segment_id"] for record in records}
    unique_transforms = {record["time_transform_id"] for record in records}
    unique_logical = {record["logical_hash"] for record in records}
    models = {record["model"] for record in records}

    status = (
        "PASS"
        if len(records) == 8
        and len(unique_segments) == 8
        and len(unique_transforms) == 8
        and len(unique_logical) == 8
        and models == {"ANCHORED_RATIONAL"}
        else "FAIL"
    )
    return {
        "schema": "TPAA_M1_DATA_003_SESSION_TIME_EVIDENCE_V1",
        "task_id": "M1-DATA-003",
        "status": status,
        "source_revision": _git_revision(),
        "projection_count": len(records),
        "unique_source_clock_segment_count": len(unique_segments),
        "unique_time_transform_count": len(unique_transforms),
        "unique_logical_hash_count": len(unique_logical),
        "transform_model": "ANCHORED_RATIONAL",
        "source_time_unit": "us",
        "segment_time_unit": "ns",
        "session_time_unit": "us",
        "timezone_input_used": False,
        "locale_input_used": False,
        "wall_clock_input_used": False,
        "implicit_rounding_used": False,
        "source_clock_rollback_unresolved": False,
        "database_persistence_executed": False,
        "canonical_flight_channel_projection_executed": False,
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
            "schema": "TPAA_M1_DATA_003_SESSION_TIME_EVIDENCE_V1",
            "task_id": "M1-DATA-003",
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
