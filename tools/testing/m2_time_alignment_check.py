#!/usr/bin/env python3
"""M2-DATA-002 sensor/INS time-alignment acceptance evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NOMINAL = REPO_ROOT / "tests" / "fixtures" / "m2" / "TA_M2_NOMINAL_V1"
INVALID = REPO_ROOT / "tests" / "fixtures" / "m2" / "TA_M2_INVALID_UNRESOLVED_V1"
EXPECTED_NEGATIVE_CODE = "M2_TIME_ALIGNMENT_TIME_TRANSFORM_UNRESOLVED"


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

    from tpaa_ingest import M2TimeAlignmentError, load_m2_time_alignment

    first = load_m2_time_alignment(NOMINAL)
    second = load_m2_time_alignment(NOMINAL)

    negative_error_code: str | None = None
    try:
        load_m2_time_alignment(INVALID)
    except M2TimeAlignmentError as exc:
        negative_error_code = exc.code

    clock_record_count = sum(len(segment.records) for segment in first.clock_segments)
    clock_contract_complete = bool(
        first.clock_segments
        and all(
            segment.time_transform_id
            and segment.sensor_system_instance_id
            and segment.records
            and all(
                row.sensor_timestamp_mapped_to_session_time_us >= 0
                and row.aligned_session_time_us >= 0
                for row in segment.records
            )
            for segment in first.clock_segments
        )
    )
    latency_contract_complete = bool(
        first.latency_records
        and all(
            row.sensor_system_instance_id
            and row.sensor_measurement_effective_time_us >= 0
            and row.referenced_ownship_state_effective_time_us >= 0
            for row in first.latency_records
        )
    )
    interpolation_contract_complete = bool(
        first.interpolation_records
        and first.max_gap_us > 0
        and all(
            row.left_truth_time_us <= row.measurement_time_us <= row.right_truth_time_us
            for row in first.interpolation_records
        )
    )
    uncertainty_contract_complete = bool(
        len(first.uncertainty_records) == 2
        and all(
            row.representation == "TWO_SIDED_HARD_BOUND"
            and row.bound_us > 0
            and row.provenance_ref
            for row in first.uncertainty_records
        )
        and first.ownship_clock_transform_residual_sigma_us >= 0
        and first.target_clock_transform_residual_sigma_us >= 0
    )
    replay_stable = first == second and first.logical_hash == second.logical_hash
    negative_fixture_fail_closed = negative_error_code == EXPECTED_NEGATIVE_CODE

    acceptance = {
        "clock_contract_complete": clock_contract_complete,
        "latency_contract_complete": latency_contract_complete,
        "interpolation_contract_complete": interpolation_contract_complete,
        "uncertainty_contract_complete": uncertainty_contract_complete,
        "negative_fixture_fail_closed": negative_fixture_fail_closed,
        "replay_stable": replay_stable,
        "metric_logic_not_executed": not first.metric_logic_executed,
        "stage_projection_not_executed": not first.stage_projection_executed,
        "persistence_not_executed": not first.persistence_executed,
    }
    failed_acceptance = sorted(key for key, value in acceptance.items() if not value)
    return {
        "schema": "TPAA_M2_DATA_002_TIME_ALIGNMENT_EVIDENCE_V1",
        "task_id": "M2-DATA-002",
        "tracking_issue": 96,
        "status": "PASS" if not failed_acceptance else "FAIL",
        "source_revision": _git_revision(),
        "fixture_id": first.fixture_id,
        "fixture_version": first.fixture_version,
        "source_sha256": first.source_sha256,
        "logical_hash": first.logical_hash,
        "metric_codes": [
            "P1-QA-003",
            "P1-QA-004",
            "P1-QA-005",
            "P1-QA-007",
            "P1-QA-008",
        ],
        "clock_segment_count": len(first.clock_segments),
        "clock_record_count": clock_record_count,
        "latency_record_count": len(first.latency_records),
        "interpolation_record_count": len(first.interpolation_records),
        "uncertainty_record_count": len(first.uncertainty_records),
        "max_gap_us": first.max_gap_us,
        "negative_fixture_id": INVALID.name,
        "negative_error_code": negative_error_code,
        "negative_fixture_fail_closed": negative_fixture_fail_closed,
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
            "schema": "TPAA_M2_DATA_002_TIME_ALIGNMENT_EVIDENCE_V1",
            "task_id": "M2-DATA-002",
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
