from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tpaa_ingest import load_m2_reference_truth

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "m2" / "RT_M2_NOMINAL_V1"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_m2_data_001_projection_exposes_complete_provenance() -> None:
    projection = load_m2_reference_truth(FIXTURE)

    assert projection.source_time_basis == "REFERENCE_SOURCE_US"
    assert projection.time_transform_id == "55555555-5555-4555-8555-555555555555"
    assert projection.own_identity.identity_ref == "reference-identity:own:v1"
    assert projection.target_identity.identity_ref == "reference-identity:target:v1"
    assert projection.frame_provenance.position_frame == "ECEF"
    assert projection.frame_provenance.velocity_frame == "ECEF"
    assert len(projection.uncertainty_records) == 5
    assert len(projection.rows) == 3


def test_m2_data_001_evidence_command_is_exact_and_replay_stable(tmp_path: Path) -> None:
    evidence_path = tmp_path / "m2-data-001.json"
    result = _run(
        "m2-reference-truth-check",
        "--evidence",
        str(evidence_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M2_DATA_001_REFERENCE_TRUTH_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-DATA-001"
    assert evidence["status"] == "PASS"
    assert evidence["metric_codes"] == ["P1-QA-001", "P1-QA-002"]
    assert evidence["row_count"] == 3
    assert evidence["pair_identity_complete"] is True
    assert evidence["frame_provenance_complete"] is True
    assert evidence["time_provenance_complete"] is True
    assert evidence["uncertainty_provenance_complete"] is True
    assert evidence["replay_stable"] is True
    assert evidence["metric_logic_executed"] is False
    assert evidence["stage_projection_executed"] is False
    assert evidence["persistence_executed"] is False
