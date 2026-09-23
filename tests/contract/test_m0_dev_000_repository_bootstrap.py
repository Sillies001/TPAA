from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY = REPO_ROOT / "tools" / "governance" / "verify_repository_bootstrap.py"
DEV = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_m0_dev_000_repository_bootstrap_verifier_passes() -> None:
    result = _run(str(VERIFY))
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["schema"] == "TPAA_M0_DEV_000_REPOSITORY_BOOTSTRAP_EVIDENCE_V1"
    assert evidence["task_ids"] == ["M0-DEV-000"]
    assert evidence["status"] == "PASS"
    assert all(item["status"] == "PASS" for item in evidence["checks"])


def test_m0_dev_000_is_available_through_unified_cli() -> None:
    result = _run(str(DEV), "verify-repository-bootstrap")
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"
    assert evidence["task_ids"] == ["M0-DEV-000"]


def test_editorconfig_and_line_ending_contract_are_committed() -> None:
    editorconfig = (REPO_ROOT / ".editorconfig").read_text(encoding="utf-8")
    attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "root = true" in editorconfig
    assert "end_of_line = lf" in editorconfig
    assert "insert_final_newline = true" in editorconfig
    assert ".editorconfig text eol=lf" in attributes


def test_hosting_controls_are_explicitly_external_to_repo_verifier() -> None:
    result = _run(str(VERIFY))
    evidence = json.loads(result.stdout)
    external = evidence["external_controls"]
    assert "NOT_EVALUATED_BY_REPOSITORY_VERIFIER" in external["github_main_branch_protection"]
    assert "NOT_EVALUATED_BY_REPOSITORY_VERIFIER" in external["required_status_checks"]
