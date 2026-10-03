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
        timeout=90,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"
    assert evidence["schema_target"] == "1.7.0"
    assert evidence["schema_transition"] == "1.6.0->1.7.0"
    assert evidence["proposal_id"] == "ACP-216"
    assert evidence["checks"]["historical_1_6_bootstrap"] is True
    assert evidence["checks"]["upgrade_1_6_to_1_7"] is True
    assert evidence["checks"]["nonempty_downgrade_fail_closed"] is True
    assert evidence["checks"]["empty_downgrade_to_1_6"] is True
    assert evidence["checks"]["forward_reupgrade_to_1_7"] is True
    assert all(evidence["checks"].values())
