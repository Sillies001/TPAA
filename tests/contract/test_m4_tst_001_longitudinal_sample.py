from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tools" / "testing" / "m4_batch_1_longitudinal_sample_check.py"


def test_m4_batch_1_longitudinal_sample_evidence_passes(tmp_path: Path) -> None:
    evidence_path = tmp_path / "m4-batch-1.json"
    completed = subprocess.run(
        [sys.executable, str(CHECK), "--evidence", str(evidence_path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M4_BATCH_1_LONGITUDINAL_SAMPLE_EVIDENCE_V1"
    assert evidence["tracking_issue"] == 126
    assert evidence["status"] == "PASS"
    assert evidence["implementation_complete"] is True
    assert evidence["task_complete"] is False
    assert evidence["completion_gate"] == (
        "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED"
    )
    assert evidence["failed_acceptance"] == []
    assert all(evidence["acceptance"].values())
    assert len(evidence["logical_product"]["eligible_codes"]) == 104
    assert len(evidence["logical_product"]["excluded_codes"]) == 12
    assert evidence["logical_product"]["sample"]["value_numeric"] == 5.0
    assert evidence["logical_product"]["no_valid_sample"]["value_numeric"] is None
    assert len(evidence["logical_product_hash"]) == 64
    assert evidence["scope"] == {
        "p1_only": True,
        "p4_p5_human_team_assessment_active": False,
        "m5_formal_product_qualification_claimed": False,
        "db_schema_version": "1.6.0",
        "shadow_schema_created": False,
        "trend_engine_executed": False,
        "api_gui_implemented": False,
        "persistence_schema_changed": False,
    }
