from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.governance.m1_entry_activation import EXPECTED_FROZEN, evaluate
from tools.manifest.m1_entry_manifest import build_manifest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"
ROLES = REPO_ROOT / "docs" / "governance" / "M1_ROLE_ASSIGNMENTS.json"


def _blocked_review() -> dict[str, object]:
    return {
        "schema": "TPAA_M1_ENTRY_GATE_REVIEW_V1",
        "decision": "M1_NOT_ADMITTED",
        "implementation_authorized": False,
        "conditions": [
            {
                "id": index,
                "status": "BLOCKED_UNASSIGNED" if index == 8 else "PASS",
            }
            for index in range(1, 11)
        ],
    }


def _unassigned_roles() -> dict[str, object]:
    return {
        "schema": "TPAA_M1_ROLE_ASSIGNMENTS_V1",
        "status": "UNASSIGNED",
        "primary_ws_owner": None,
        "golden_independent_reviewer": None,
        "m1_exit_reviewer": None,
        "golden_independence_attestation": None,
    }


def _candidate_review() -> dict[str, object]:
    return {
        "schema": "TPAA_M1_ENTRY_GATE_REVIEW_V1",
        "decision": "M1_ADMISSION_CANDIDATE",
        "implementation_authorized": False,
        "conditions": [
            {
                "id": index,
                "status": "RUNTIME_VERIFY_REQUIRED" if index == 6 else "PASS",
            }
            for index in range(1, 11)
        ],
    }


def _assigned_roles() -> dict[str, object]:
    return {
        "schema": "TPAA_M1_ROLE_ASSIGNMENTS_V1",
        "status": "ASSIGNED",
        "primary_ws_owner": "primary-owner",
        "golden_independent_reviewer": "golden-reviewer",
        "m1_exit_reviewer": "exit-reviewer",
        "golden_independence_attestation": (
            "Golden reviewer is independent of the implementation and expected-result author."
        ),
    }


def _manifest(source_revision: str, platform_profile: str) -> dict[str, object]:
    return {
        "schema": "TPAA_M1_ENTRY_BUILD_MANIFEST_V1",
        "status": "FROZEN_ENTRY_CANDIDATE",
        "admission": "M1_NOT_ADMITTED_BY_THIS_MANIFEST",
        "source_revision": source_revision,
        "platform_profile": platform_profile,
        **EXPECTED_FROZEN,
    }


def test_blocked_mode_verifies_consistent_9_of_10_state() -> None:
    revision = "9" * 40
    result = evaluate(
        mode="blocked",
        source_revision=revision,
        review=_blocked_review(),
        roles=_unassigned_roles(),
        windows_manifest=_manifest(revision, "WINDOWS_DESKTOP_X64"),
        linux_manifest=_manifest(revision, "LINUX_DESKTOP_X64"),
    )
    assert result["status"] == "PASS"
    assert result["decision"] == "M1_NOT_ADMITTED"
    assert result["implementation_authorized"] is False
    assert result["conditions_passed_after_runtime_verification"] == 9


def test_candidate_mode_verifies_without_authorizing_implementation() -> None:
    revision = "a" * 40
    result = evaluate(
        mode="candidate",
        source_revision=revision,
        review=_candidate_review(),
        roles=_assigned_roles(),
        windows_manifest=_manifest(revision, "WINDOWS_DESKTOP_X64"),
        linux_manifest=_manifest(revision, "LINUX_DESKTOP_X64"),
    )
    assert result["status"] == "PASS"
    assert result["decision"] == "M1_ADMISSION_CANDIDATE_VERIFIED"
    assert result["implementation_authorized"] is False
    assert result["condition_6_runtime"] == "CANDIDATE_PASS"
    assert result["conditions_passed_after_runtime_verification"] == 10


def test_activate_mode_emits_admission_only_after_runtime_manifest_match() -> None:
    revision = "b" * 40
    result = evaluate(
        mode="activate",
        source_revision=revision,
        review=_candidate_review(),
        roles=_assigned_roles(),
        windows_manifest=_manifest(revision, "WINDOWS_DESKTOP_X64"),
        linux_manifest=_manifest(revision, "LINUX_DESKTOP_X64"),
    )
    assert result["status"] == "PASS"
    assert result["decision"] == "M1_ADMITTED"
    assert result["implementation_authorized"] is True
    assert result["condition_6_runtime"] == "PASS"


def test_activation_fails_closed_when_role_assignment_is_incomplete() -> None:
    revision = "c" * 40
    roles = _assigned_roles()
    roles["golden_independence_attestation"] = None
    result = evaluate(
        mode="activate",
        source_revision=revision,
        review=_candidate_review(),
        roles=roles,
        windows_manifest=_manifest(revision, "WINDOWS_DESKTOP_X64"),
        linux_manifest=_manifest(revision, "LINUX_DESKTOP_X64"),
    )
    assert result["status"] == "FAIL"
    assert result["decision"] == "M1_NOT_ADMITTED"
    assert result["implementation_authorized"] is False


def test_activation_fails_closed_on_cross_platform_source_revision_drift() -> None:
    revision = "d" * 40
    result = evaluate(
        mode="activate",
        source_revision=revision,
        review=_candidate_review(),
        roles=_assigned_roles(),
        windows_manifest=_manifest(revision, "WINDOWS_DESKTOP_X64"),
        linux_manifest=_manifest("e" * 40, "LINUX_DESKTOP_X64"),
    )
    assert result["status"] == "FAIL"
    assert result["implementation_authorized"] is False

def test_auto_mode_tracks_current_role_state_without_early_admission(tmp_path: Path) -> None:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(
        json.dumps(build_manifest("WINDOWS_DESKTOP_X64"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    linux.write_text(
        json.dumps(build_manifest("LINUX_DESKTOP_X64"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "activation.json"
    result = subprocess.run(
        [
            sys.executable,
            str(DEV),
            "m1-entry-activation",
            "--mode",
            "auto",
            "--event-name",
            "pull_request",
            "--git-ref",
            "refs/pull/entry/merge",
            "--source-revision",
            revision,
            "--windows-manifest",
            str(windows),
            "--linux-manifest",
            str(linux),
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(output.read_text(encoding="utf-8"))
    roles = json.loads(ROLES.read_text(encoding="utf-8"))
    assert evidence["status"] == "PASS"
    assert evidence["implementation_authorized"] is False
    if roles["status"] == "UNASSIGNED":
        assert evidence["mode"] == "blocked"
        assert evidence["decision"] == "M1_NOT_ADMITTED"
    else:
        assert roles["status"] == "ASSIGNED"
        assert evidence["mode"] == "candidate"
        assert evidence["decision"] == "M1_ADMISSION_CANDIDATE_VERIFIED"

