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


def test_m1_data_005_acceptance_command_emits_machine_evidence(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "canonical-flight-channels.json"
    result = _run(
        "m1-canonical-flight-channels-check",
        "--evidence",
        str(evidence_path),
    )
    assert result.returncode == 0, result.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M1_DATA_005_CANONICAL_FLIGHT_CHANNEL_EVIDENCE_V1"
    assert evidence["task_id"] == "M1-DATA-005"
    assert evidence["status"] == "PASS"
    assert evidence["authority_id"] == "CANONICAL_AIRCRAFT_STATE_V1"
    assert evidence["projection_count"] == 8
    assert evidence["total_row_count"] == 62
    assert evidence["canonical_channels"] == [
        "body_p_rad_s",
        "nz_g",
        "heading_true_rad",
        "tas_mps",
        "mach",
        "session_time_us",
        "quality_mask",
    ]
    assert evidence["unique_logical_hash_count"] == 8
    assert evidence["replay_stable"] is True
    assert evidence["missing_value_count"] == 8
    assert evidence["missing_preserved_as_null"] is True
    assert evidence["zero_fill_of_missing_executed"] is False
    assert evidence["database_persistence_executed"] is False
    assert evidence["evaluation_context_binding_executed"] is False
    assert evidence["stage_projection_executed"] is False
    assert evidence["world_projection_executed"] is False
    assert evidence["metric_logic_executed"] is False


def test_m1_data_005_structured_partial_keeps_missing_values_missing() -> None:
    result = _run("m1-canonical-flight-channels-check")
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)

    structured = next(
        record
        for record in evidence["records"]
        if record["fixture_id"] == "BF_M1_STRUCTURED_PARTIAL_V1"
    )
    assert structured["missing_by_channel"]["tas_mps"] == 4
    assert structured["missing_by_channel"]["mach"] == 4
    assert structured["missing_value_count"] == 8
    assert structured["missing_preserved_as_null"] is True
