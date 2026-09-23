from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE = REPO_ROOT / "tools" / "storage" / "backup_restore_smoke.py"


def test_m0_sto_007_backup_restore_smoke_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(SMOKE)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"
    assert evidence["task"] == "M0-STO-007"
    assert all(evidence["checks"].values())
