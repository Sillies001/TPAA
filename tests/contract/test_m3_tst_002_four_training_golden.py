from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tools" / "testing" / "m3_four_training_golden_check.py"

EXPECTED_STAGE_PROFILES = {
    "BASIC": "BASIC_FLIGHT_V1",
    "WVR": "WVR_ENGAGEMENT_V1",
    "BVR": "BVR_KILL_CHAIN_V1",
    "STRIKE": "STRIKE_MISSION_V1",
}
EXPECTED_STAGE_ORDERS = {
    "BASIC": [
        "SETUP_ENTRY",
        "EXECUTION",
        "STABILIZATION_RECOVERY",
        "COMPLETION",
    ],
    "WVR": [
        "MERGE",
        "POSITION_ADVANTAGE",
        "MANEUVER",
        "WEAPON_ENVELOPE",
        "LAUNCH",
        "KILL_ASSESSMENT",
    ],
    "BVR": [
        "DETECTION",
        "TRACK",
        "IDENTIFICATION",
        "DECISION",
        "WEAPON_EMPLOYMENT",
        "ASSESSMENT",
    ],
    "STRIKE": [
        "MISSION_SETUP",
        "ROUTE_TASK_EXECUTION",
        "TARGET_INFORMATION_AVAILABLE",
        "TARGET_ASSOCIATION",
        "DESIGNATION_TRACK",
        "TRAINING_ATTACK_EVENT",
        "RANGE_SIM_ADJUDICATION",
        "POST_EVENT_TASK_TRANSITION",
        "RECOVERY",
    ],
}


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECK), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=240,
    )


def test_m3_tst_002_four_training_golden_contract() -> None:
    checked = _run("check")
    assert checked.returncode == 0, checked.stdout + checked.stderr

    payload = json.loads(checked.stdout)
    assert payload["schema"] == "TPAA_M3_TST_002_FOUR_TRAINING_GOLDEN_EVIDENCE_V1"
    assert payload["task_id"] == "M3-TST-002"
    assert payload["tracking_issue"] == 117
    assert payload["status"] == "PASS"
    assert payload["task_complete"] is True
    assert payload["implementation_complete"] is True
    assert payload["failed_acceptance"] == []
    assert all(payload["acceptance"].values())

    logical = payload["logical_product"]
    assert logical["stage_profiles"] == EXPECTED_STAGE_PROFILES
    assert logical["stage_orders"] == EXPECTED_STAGE_ORDERS
    assert logical["fixture_category_counts"] == {
        "APPLICABILITY": 4,
        "BOUNDARY": 4,
        "GAP": 4,
        "INSUFFICIENT": 4,
        "INVALID": 4,
        "NOMINAL": 4,
    }
    assert logical["fixture_training_counts"] == {
        "BASIC_FLIGHT": 6,
        "BVR": 6,
        "STRIKE": 6,
        "WVR": 6,
    }
    assert len(logical["fixture_family"]["cases"]) == 24

    assert payload["scope"]["basic_regression_included"] is True
    assert payload["scope"]["boundary_gap_insufficient_invalid_included"] is True
    assert payload["scope"]["business_metric_values_executed"] is False
    assert payload["scope"]["metric_engine_executed"] is False
    assert payload["scope"]["persistence_executed"] is False
    assert payload["scope"]["shadow_stage_schema_created"] is False
    assert payload["scope"]["event_persistence_schema_created"] is False


def test_m3_tst_002_cross_platform_evidence_contract(tmp_path: Path) -> None:
    source = tmp_path / "four-training-golden.json"
    checked = _run("check", "--evidence", str(source))
    assert checked.returncode == 0, checked.stdout + checked.stderr

    payload = json.loads(source.read_text(encoding="utf-8"))
    revision = payload["source_revision"]

    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"

    result = _run(
        "compare",
        "--windows",
        str(windows),
        "--linux",
        str(linux),
        "--expected-revision",
        revision,
        "--evidence",
        str(compared),
    )
    assert result.returncode == 0, result.stdout + result.stderr

    evidence = json.loads(compared.read_text(encoding="utf-8"))
    assert evidence["schema"] == (
        "TPAA_M3_TST_002_FOUR_TRAINING_GOLDEN_"
        "CROSS_PLATFORM_EVIDENCE_V1"
    )
    assert evidence["task_id"] == "M3-TST-002"
    assert evidence["tracking_issue"] == 117
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is True
    assert evidence["implementation_complete"] is True
    assert evidence["source_revision"] == revision
    assert evidence["windows_source_revision"] == revision
    assert evidence["linux_source_revision"] == revision
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
