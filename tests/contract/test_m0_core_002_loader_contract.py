from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_LOADER = REPO_ROOT / "tools" / "canonical" / "verify_loader.py"
DEV_CLI = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"


def test_machine_readable_loader_acceptance_verifier_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(VERIFY_LOADER)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"
    assert evidence["task_id"] == "M0-CORE-002"
    assert evidence["controlled_artifact_count"] == 21
    assert len(evidence["artifacts"]) == 21
    assert all(check["status"] == "PASS" for check in evidence["checks"])


def test_loader_verification_is_available_through_unified_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(DEV_CLI), "verify-canonical"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"
    assert evidence["gate_id"] == "M0-CORE-002.CANONICAL_ARTIFACT_LOADER"
