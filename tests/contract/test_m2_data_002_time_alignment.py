from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tpaa_ingest import load_m2_time_alignment

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"
NOMINAL = REPO_ROOT / "tests" / "fixtures" / "m2" / "TA_M2_NOMINAL_V1"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_m2_data_002_projection_exposes_frozen_time_inputs() -> None:
    projection = load_m2_time_alignment(NOMINAL)

    assert len(projection.clock_segments) == 2
    assert sum(len(segment.records) for segment in projection.clock_segments) == 4
    assert len(projection.latency_records) == 3
    assert len(projection.interpolation_records) == 3
    assert len(projection.uncertainty_records) == 2
    assert projection.max_gap_us == 60_000


def test_m2_data_002_evidence_command_includes_negative_fixture(tmp_path: Path) -> None:
    evidence_path = tmp_path / "m2-data-002.json"
    result = _run(
        "m2-time-alignment-check",
        "--evidence",
        str(evidence_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M2_DATA_002_TIME_ALIGNMENT_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-DATA-002"
    assert evidence["status"] == "PASS"
    assert evidence["metric_codes"] == [
        "P1-QA-003",
        "P1-QA-004",
        "P1-QA-005",
        "P1-QA-007",
        "P1-QA-008",
    ]
    assert evidence["clock_segment_count"] == 2
    assert evidence["clock_record_count"] == 4
    assert evidence["latency_record_count"] == 3
    assert evidence["interpolation_record_count"] == 3
    assert evidence["negative_fixture_fail_closed"] is True
    assert evidence["negative_error_code"] == "M2_TIME_ALIGNMENT_TIME_TRANSFORM_UNRESOLVED"
    assert evidence["replay_stable"] is True
    assert evidence["metric_logic_executed"] is False
