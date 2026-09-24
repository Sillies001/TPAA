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


def test_m1_data_003_acceptance_command_emits_machine_evidence(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "session-time.json"
    result = _run(
        "m1-session-time-check",
        "--evidence",
        str(evidence_path),
    )
    assert result.returncode == 0, result.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M1_DATA_003_SESSION_TIME_EVIDENCE_V1"
    assert evidence["task_id"] == "M1-DATA-003"
    assert evidence["status"] == "PASS"
    assert evidence["projection_count"] == 8
    assert evidence["unique_source_clock_segment_count"] == 8
    assert evidence["unique_time_transform_count"] == 8
    assert evidence["unique_logical_hash_count"] == 8
    assert evidence["transform_model"] == "ANCHORED_RATIONAL"
    assert evidence["timezone_input_used"] is False
    assert evidence["locale_input_used"] is False
    assert evidence["wall_clock_input_used"] is False
    assert evidence["implicit_rounding_used"] is False
    assert evidence["source_clock_rollback_unresolved"] is False
    assert evidence["database_persistence_executed"] is False
    assert evidence["canonical_flight_channel_projection_executed"] is False
    assert evidence["stage_projection_executed"] is False
    assert evidence["metric_logic_executed"] is False


def test_m1_data_003_nominal_evidence_uses_decimal_string_time_transport() -> None:
    result = _run("m1-session-time-check")
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)

    records = evidence["records"]
    assert isinstance(records, list)
    nominal = next(
        record
        for record in records
        if record["fixture_id"] == "BF_M1_NOMINAL_V1"
    )

    assert nominal["model"] == "ANCHORED_RATIONAL"
    assert nominal["anchor_segment_time_ns"] == "0"
    assert nominal["anchor_session_time_us"] == "1000000"
    assert nominal["rate_num"] == 1
    assert nominal["rate_den"] == 1000
    assert nominal["valid_segment_start_ns"] == "0"
    assert nominal["valid_segment_end_ns"] == "8000000000"
    assert nominal["start_session_time_us"] == "1000000"
    assert nominal["end_session_time_us"] == "9000000"
    assert nominal["first_row_session_time_us"] == "1000000"
    assert nominal["last_row_session_time_us"] == "8000000"
    assert len(nominal["transform_hash"]) == 64
    assert len(nominal["logical_hash"]) == 64
