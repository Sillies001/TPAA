from __future__ import annotations

from tools.governance.m1_entry_activation import EXPECTED_FROZEN, evaluate


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
