from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_m1_data_006_acceptance_command_emits_machine_evidence(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "evaluation-context.json"
    result = _run(
        "m1-evaluation-context-check",
        "--evidence",
        str(evidence_path),
    )
    assert result.returncode == 0, result.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M1_DATA_006_EVALUATION_CONTEXT_EVIDENCE_V1"
    assert evidence["task_id"] == "M1-DATA-006"
    assert evidence["status"] == "PASS"
    assert evidence["context_count"] == 8
    assert evidence["artifact_ref_count"] == 16
    assert evidence["required_binding_roles"] == ["METRIC_PROFILE", "RULE_SET"]
    assert evidence["artifact_refs_stable_sorted"] is True
    assert evidence["basic_profile_id"] == "M1-BASIC-CONTEXT-1.0.0"
    assert evidence["stage_profile_id"] == "BASIC_FLIGHT_V1"
    assert evidence["metric_profile_id"] == "M1_BASIC_AIR_PROFILE_V1"
    assert evidence["unique_logical_hash_count"] == 8
    assert evidence["unique_context_file_hash_count"] == 8
    assert evidence["replay_stable"] is True
    assert evidence["frozen_refs_resolution_count"] == 1
    assert evidence["current_ref_drift_fixture_count"] == 1
    assert evidence["current_latest_fallback_used"] is False
    assert evidence["stage_profile_persistence_binding_created"] is False
    assert evidence["database_persistence_executed"] is False
    assert evidence["stage_projection_executed"] is False
    assert evidence["world_projection_executed"] is False
    assert evidence["metric_logic_executed"] is False


def test_replay_fixture_proves_no_current_latest_context_fallback() -> None:
    result = _run("m1-evaluation-context-check")
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)

    replay = next(
        record
        for record in evidence["records"]
        if record["fixture_id"] == "BF_M1_REPLAY_V1"
    )
    assert replay["frozen_refs_used"] is True
    assert replay["current_refs_differ_from_frozen"] is True
    assert replay["current_latest_fallback_used"] is False
    assert replay["rule_set_version"] == "CB-1.4.0"
    assert replay["metric_profile_version"] == "M1_BASIC_AIR_PROFILE_V1"
