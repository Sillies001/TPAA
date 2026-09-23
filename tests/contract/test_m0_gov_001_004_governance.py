from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY = REPO_ROOT / "tools" / "governance" / "verify_governance.py"
DEV = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"


def test_m0_governance_verifier_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(VERIFY)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"
    assert evidence["task_ids"] == [
        "M0-GOV-001",
        "M0-GOV-002",
        "M0-GOV-003",
        "M0-GOV-004",
    ]
    assert all(item["status"] == "PASS" for item in evidence["checks"])


def test_governance_gate_is_available_through_unified_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(DEV), "verify-governance"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "PASS"


def test_issue_and_pr_templates_require_governance_identity() -> None:
    feature = (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature.yml").read_text(
        encoding="utf-8"
    )
    pr = (REPO_ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    baseline = (
        REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "baseline-change.yml"
    ).read_text(encoding="utf-8")

    for token in ("Milestone / Task ID", "Primary WS", "Authority refs", "Change class"):
        assert token in feature
    for token in ("Milestone / Task", "Primary WS", "Authority refs", "Change class"):
        assert token in pr
    assert "C2 Canonical non-semantic metadata" in baseline
    assert "C3 Semantic contract" in baseline
