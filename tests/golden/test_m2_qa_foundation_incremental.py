from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"


def test_m2_met_002_formal_golden_evidence(tmp_path: Path) -> None:
    evidence_path = tmp_path / "qa.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(DEV),
            "m2-qa-foundation-incremental-check",
            "--evidence",
            str(evidence_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["status"] == "PASS"
    assert evidence["implementation_complete"] is True
    assert evidence["task_complete"] is True
    assert evidence["formal_completion_blocked_by_authority"] is False
    assert evidence["authority_resolution_ready"] is True
    assert evidence["failed_acceptance"] == []
    assert evidence["logical_product"]["engine_metric_codes"] == [
        "P1-QA-001",
        "P1-QA-003",
        "P1-QA-004",
        "P1-QA-005",
        "P1-QA-007",
        "P1-QA-008",
        "P1-QA-002",
        "P1-QA-006",
    ]
    assert evidence["acceptance"]["qa_001_c3_nonidentity_golden_exact"]
    assert evidence["acceptance"]["qa_002_c3_nondegenerate_golden_exact"]
