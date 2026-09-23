from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"
VERIFY_MODULE = "tools.governance.verify_m1_entry_gate_state"
REVIEW = REPO_ROOT / "docs" / "reviews" / "M1_ENTRY_GATE_REVIEW.json"
ROLES = REPO_ROOT / "docs" / "governance" / "M1_ROLE_ASSIGNMENTS.json"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_m1_entry_gate_state_verifier_accepts_blocked_review_without_admission() -> None:
    result = _run("-m", VERIFY_MODULE)
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["schema"] == "TPAA_M1_ENTRY_GATE_STATE_VERIFICATION_V1"
    assert evidence["status"] == "PASS"
    assert evidence["decision"] == "M1_NOT_ADMITTED"
    assert evidence["implementation_authorized"] is False
    assert evidence["condition_8"] == "BLOCKED_UNASSIGNED"
    assert all(item["status"] == "PASS" for item in evidence["checks"])


def test_m1_entry_gate_review_is_exactly_9_of_10_with_only_condition_8_blocked() -> None:
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    conditions = {item["id"]: item["status"] for item in review["conditions"]}
    assert set(conditions) == set(range(1, 11))
    assert all(conditions[index] == "PASS" for index in (1,2,3,4,5,6,7,9,10))
    assert conditions[8] == "BLOCKED_UNASSIGNED"
    assert review["pass_count"] == 9
    assert review["condition_count"] == 10
    assert review["blocking_conditions"] == [8]
    assert review["decision"] == "M1_NOT_ADMITTED"
    assert review["implementation_authorized"] is False


def test_role_assignment_contract_remains_explicitly_unassigned() -> None:
    roles = json.loads(ROLES.read_text(encoding="utf-8"))
    assert roles["status"] == "UNASSIGNED"
    assert roles["primary_ws_owner"] is None
    assert roles["golden_independent_reviewer"] is None
    assert roles["m1_exit_reviewer"] is None
    assert roles["golden_independence_attestation"] is None


def test_m1_entry_gate_state_is_available_through_unified_cli() -> None:
    result = _run(str(DEV), "verify-m1-entry-gate-state")
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"
    assert evidence["decision"] == "M1_NOT_ADMITTED"
