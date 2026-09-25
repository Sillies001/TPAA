#!/usr/bin/env python3
"""M2-DATA-003 mission-system ingest/identity/applicability evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RADAR = REPO_ROOT / "tests" / "fixtures" / "m2" / "MSI_M2_RADAR_V1"
IRST = REPO_ROOT / "tests" / "fixtures" / "m2" / "MSI_M2_IRST_NEGATIVE_V1"
EXPECTED_NEGATIVE_CODE = "M2_MISSION_SYSTEM_NOT_APPLICABLE"


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

    from tpaa_ingest import M2MissionSystemError, load_m2_mission_system

    first = load_m2_mission_system(RADAR)
    second = load_m2_mission_system(RADAR)

    negative_error_code: str | None = None
    try:
        load_m2_mission_system(IRST)
    except M2MissionSystemError as exc:
        negative_error_code = exc.code

    core_identity_complete = bool(
        first.instance.mission_system_instance_id
        and first.instance.aircraft_id
        and first.instance.system_code
        and first.instance.configuration_hash
        and first.identity.identity_ref
        and first.identity.source_entity_key
    )
    applicability_exact = (
        first.subject_type == "MISSION_SYSTEM_INSTANCE"
        and first.metric_family == "P1-SNS-*"
        and first.applicability_mode == "SYSTEM_TYPE_EXACT"
        and first.allowed_system_types == ("RADAR",)
        and first.instance.system_type == "RADAR"
        and first.sns_applicable
    )
    negative_fixture_fail_closed = negative_error_code == EXPECTED_NEGATIVE_CODE
    replay_stable = first == second and first.logical_hash == second.logical_hash

    acceptance = {
        "core_identity_complete": core_identity_complete,
        "radar_applicability_exact": applicability_exact,
        "non_radar_fail_closed": negative_fixture_fail_closed,
        "replay_stable": replay_stable,
        "metric_logic_not_executed": not first.metric_logic_executed,
        "stage_projection_not_executed": not first.stage_projection_executed,
        "persistence_not_executed": not first.persistence_executed,
        "publication_not_executed": not first.publication_executed,
    }
    failed_acceptance = sorted(key for key, value in acceptance.items() if not value)
    return {
        "schema": "TPAA_M2_DATA_003_MISSION_SYSTEM_EVIDENCE_V1",
        "task_id": "M2-DATA-003",
        "tracking_issue": 96,
        "status": "PASS" if not failed_acceptance else "FAIL",
        "source_revision": _git_revision(),
        "fixture_id": first.fixture_id,
        "fixture_version": first.fixture_version,
        "input_sha256": first.input_sha256,
        "source_sha256": first.source_sha256,
        "logical_hash": first.logical_hash,
        "mission_system_instance_id": first.instance.mission_system_instance_id,
        "aircraft_id": first.instance.aircraft_id,
        "system_type": first.instance.system_type,
        "system_code": first.instance.system_code,
        "subject_type": first.subject_type,
        "metric_family": first.metric_family,
        "applicability_mode": first.applicability_mode,
        "allowed_system_types": list(first.allowed_system_types),
        "negative_fixture_id": IRST.name,
        "negative_error_code": negative_error_code,
        "negative_fixture_fail_closed": negative_fixture_fail_closed,
        "replay_stable": replay_stable,
        "metric_logic_executed": first.metric_logic_executed,
        "stage_projection_executed": first.stage_projection_executed,
        "persistence_executed": first.persistence_executed,
        "publication_executed": first.publication_executed,
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
            "schema": "TPAA_M2_DATA_003_MISSION_SYSTEM_EVIDENCE_V1",
            "task_id": "M2-DATA-003",
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
