from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS = REPO_ROOT / "tools" / "storage" / "migration_harness.py"


def test_m0_sto_005_migration_harness_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(HARNESS)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"
    assert evidence["schema_target"] == "1.6.0"
    assert evidence["schema_transition"] == "NONE_CURRENT_BASELINE"
    assert all(evidence["checks"].values())
