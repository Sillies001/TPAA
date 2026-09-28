from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tools" / "testing" / "m4_longitudinal_coverage_check.py"


def test_m4_tst_004_exact_104_12_coverage(tmp_path: Path) -> None:
    evidence = tmp_path / "coverage.json"
    completed = subprocess.run(
        [sys.executable, str(CHECK), "--evidence", str(evidence)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["schema"] == "TPAA_M4_TST_004_LONGITUDINAL_COVERAGE_V1"
    assert payload["task_id"] == "M4-TST-004"
    assert payload["status"] == "PASS"
    assert payload["implementation_complete"] is True
    assert payload["task_complete"] is False
    assert payload["failed_acceptance"] == []
    assert all(payload["acceptance"].values())
    assert len(payload["logical_product"]["eligible"]) == 104
    assert len(payload["logical_product"]["excluded"]) == 12
