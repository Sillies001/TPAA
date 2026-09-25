from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tpaa_ingest import M2MissionSystemError, load_m2_mission_system

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"
RADAR = REPO_ROOT / "tests" / "fixtures" / "m2" / "MSI_M2_RADAR_V1"
IRST = REPO_ROOT / "tests" / "fixtures" / "m2" / "MSI_M2_IRST_NEGATIVE_V1"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_m2_data_003_projection_matches_frozen_sns_contract() -> None:
    projection = load_m2_mission_system(RADAR)

    assert projection.subject_type == "MISSION_SYSTEM_INSTANCE"
    assert projection.metric_family == "P1-SNS-*"
    assert projection.applicability_mode == "SYSTEM_TYPE_EXACT"
    assert projection.allowed_system_types == ("RADAR",)
    assert projection.instance.system_type == "RADAR"

    try:
        load_m2_mission_system(IRST)
    except M2MissionSystemError as exc:
        assert exc.code == "M2_MISSION_SYSTEM_NOT_APPLICABLE"
    else:
        raise AssertionError("IRST must fail closed for P1-SNS-* applicability")


def test_m2_data_003_evidence_command_covers_positive_and_negative(tmp_path: Path) -> None:
    evidence_path = tmp_path / "m2-data-003.json"
    result = _run(
        "m2-mission-system-check",
        "--evidence",
        str(evidence_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M2_DATA_003_MISSION_SYSTEM_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-DATA-003"
    assert evidence["status"] == "PASS"
    assert evidence["subject_type"] == "MISSION_SYSTEM_INSTANCE"
    assert evidence["metric_family"] == "P1-SNS-*"
    assert evidence["applicability_mode"] == "SYSTEM_TYPE_EXACT"
    assert evidence["allowed_system_types"] == ["RADAR"]
    assert evidence["system_type"] == "RADAR"
    assert evidence["negative_fixture_id"] == "MSI_M2_IRST_NEGATIVE_V1"
    assert evidence["negative_error_code"] == "M2_MISSION_SYSTEM_NOT_APPLICABLE"
    assert evidence["negative_fixture_fail_closed"] is True
    assert evidence["replay_stable"] is True
    assert evidence["failed_acceptance"] == []
    assert evidence["metric_logic_executed"] is False
    assert evidence["persistence_executed"] is False
