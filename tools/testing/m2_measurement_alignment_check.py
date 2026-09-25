#!/usr/bin/env python3
"""M2-DATA-004 measurement/reference alignment and quality evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m2"
NOMINAL = FIXTURE_ROOT / "MA_M2_NOMINAL_V1"
GAP = FIXTURE_ROOT / "MA_M2_GAP_V1"


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

    from tpaa_ingest import load_m2_measurement_alignment

    nominal = load_m2_measurement_alignment(NOMINAL)
    replayed = load_m2_measurement_alignment(NOMINAL)
    gap = load_m2_measurement_alignment(GAP)

    complete_uncertainty = all(
        row.reference_uncertainty >= 0
        and row.alignment_uncertainty >= 0
        and row.sensor_measurement_uncertainty >= 0
        and row.reference_truth_uncertainty >= 0
        and set(row.uncertainty_provenance)
        == {
            "alignment_uncertainty_ref",
            "reference_uncertainty_ref",
            "sensor_measurement_uncertainty_ref",
        }
        for row in nominal.rows
    )
    sns_fields_complete = all(
        bool(row.sensor_measurement)
        and bool(row.reference_relative_state)
        and len(row.measured_position_ecef_m) == 3
        and len(row.reference_target_position_ecef_m) == 3
        and len(row.measured_position_sensor_frame) == 3
        and len(row.reference_position_sensor_frame) == 3
        and len(row.measured_position_local) == 3
        and len(row.reference_position_local) == 3
        for row in nominal.rows
    )
    acceptance = {
        "pairing_identity_exact": all(
            row.mission_system_instance_id == nominal.mission_system_instance_id
            and row.target_pair_id == nominal.target_pair_id
            for row in nominal.rows
        ),
        "qa_006_residual_and_uncertainty_inputs_present": all(
            row.residual_unit
            and row.error_domain
            and row.measurement_error == 5.0
            and row.reference_uncertainty == 3.0
            and row.alignment_uncertainty == 1.0
            and row.sensor_measurement_uncertainty == 2.0
            for row in nominal.rows
        ),
        "sns_accuracy_input_family_present": sns_fields_complete,
        "uncertainty_provenance_complete": complete_uncertainty,
        "nominal_coverage_and_gap_pass": (
            nominal.status == "READY"
            and nominal.coverage == 1.0
            and nominal.max_observed_gap_us == 5000
        ),
        "gap_fixture_preserved_fail_closed": (
            gap.status == "INSUFFICIENT"
            and gap.reason_codes == ("MAX_GAP_EXCEEDED", "MIN_COVERAGE_NOT_MET")
            and gap.max_observed_gap_us == 200000
            and [row.match_status for row in gap.rows]
            == ["MATCHED", "REJECTED_QUALITY", "MATCHED"]
        ),
        "replay_stable": nominal == replayed and nominal.logical_hash == replayed.logical_hash,
        "metric_logic_not_executed": not nominal.metric_logic_executed,
        "stage_projection_not_executed": not nominal.stage_projection_executed,
        "persistence_not_executed": not nominal.persistence_executed,
        "publication_not_executed": not nominal.publication_executed,
    }
    failed_acceptance = sorted(key for key, passed in acceptance.items() if not passed)
    return {
        "schema": "TPAA_M2_DATA_004_MEASUREMENT_ALIGNMENT_EVIDENCE_V1",
        "task_id": "M2-DATA-004",
        "tracking_issue": 96,
        "status": "PASS" if not failed_acceptance else "FAIL",
        "source_revision": _git_revision(),
        "nominal_fixture_id": nominal.fixture_id,
        "nominal_input_sha256": nominal.input_sha256,
        "nominal_source_sha256": nominal.source_sha256,
        "nominal_logical_hash": nominal.logical_hash,
        "gap_fixture_id": gap.fixture_id,
        "gap_input_sha256": gap.input_sha256,
        "gap_source_sha256": gap.source_sha256,
        "gap_logical_hash": gap.logical_hash,
        "metric_codes": list(nominal.metric_codes),
        "mission_system_instance_id": nominal.mission_system_instance_id,
        "target_pair_id": nominal.target_pair_id,
        "quality_profile_id": nominal.quality_profile.profile_id,
        "quality_profile_version": nominal.quality_profile.profile_version,
        "quality_profile_hash": nominal.quality_profile.profile_hash,
        "coverage": nominal.coverage,
        "max_observed_gap_us": nominal.max_observed_gap_us,
        "gap_coverage": gap.coverage,
        "gap_max_observed_gap_us": gap.max_observed_gap_us,
        "gap_reason_codes": list(gap.reason_codes),
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
            "schema": "TPAA_M2_DATA_004_MEASUREMENT_ALIGNMENT_EVIDENCE_V1",
            "task_id": "M2-DATA-004",
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
