from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tools" / "testing" / "m4_batch_3_api_gui_debrief_check.py"


def test_m4_batch_3_api_gui_debrief_evidence_passes(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "m4-batch-3.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(CHECK),
            "--evidence",
            str(evidence_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert completed.returncode == 0, (
        completed.stdout + completed.stderr
    )
    evidence = json.loads(
        evidence_path.read_text(encoding="utf-8")
    )
    assert evidence["schema"] == (
        "TPAA_M4_BATCH_3_API_GUI_DEBRIEF_EVIDENCE_V1"
    )
    assert evidence["tracking_issue"] == 128
    assert evidence["status"] == "PASS"
    assert evidence["implementation_complete"] is True
    assert evidence["task_complete"] is False
    assert evidence["failed_acceptance"] == []
    assert all(evidence["acceptance"].values())
    assert len(evidence["logical_product_hash"]) == 64
    assert evidence["scope"] == {
        "p1_only": True,
        "db_schema_version": "1.6.0",
        "shadow_schema_created": False,
        "api_business_recomputation": False,
        "gui_business_recomputation": False,
        "gui_persistence_access": False,
        "historical_current_latest_fallback": False,
        "p4_p5_human_team_assessment_active": False,
        "m5_formal_product_qualification_claimed": False,
    }
