from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from tools.testing.prcb_c5_exit_review import MANDATORY_PROFILES, review

REVISION = "a" * 40


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _equivalence() -> dict[str, object]:
    package_hashes = {
        "LINUX_DESKTOP_X64": "1" * 64,
        "LINUX_SERVICE_X64": "2" * 64,
        "WINDOWS_DESKTOP_X64": "3" * 64,
        "WINDOWS_SERVICE_X64": "4" * 64,
    }
    evidence_hashes = {
        "LINUX_DESKTOP_X64": "5" * 64,
        "LINUX_SERVICE_X64": "6" * 64,
        "WINDOWS_DESKTOP_X64": "7" * 64,
        "WINDOWS_SERVICE_X64": "8" * 64,
    }
    shared = {
        "release_id": "11111111-1111-4111-8111-111111111111",
        "p3_estimate_id": "22222222-2222-4222-8222-222222222222",
        "p4_revision_id": "33333333-3333-4333-8333-333333333333",
        "p5_revision_id": "44444444-4444-4444-8444-444444444444",
        "p6_forecast_result_id": "55555555-5555-4555-8555-555555555555",
        "p6_counterfactual_run_id": "66666666-6666-4666-8666-666666666666",
    }
    return {
        "schema": "TPAA_PRCB_C5_FOUR_PROFILE_LOGICAL_EQUIVALENCE_V1",
        "status": "PASS",
        "qualification": "TPAA_1_0_1_CANDIDATE_NOT_QUALIFIED",
        "formal_release_claimed": False,
        "source_revision": REVISION,
        "mandatory_profiles": list(MANDATORY_PROFILES),
        "package_sha256_by_profile": package_hashes,
        "installed_evidence_sha256_by_profile": evidence_hashes,
        "postgres_server_version_by_service_profile": {
            "LINUX_SERVICE_X64": "16.15",
            "WINDOWS_SERVICE_X64": "17.11",
        },
        "p2_runtime_provenance_by_profile": {
            profile: {
                "estimate_id": f"estimate-{index}",
                "knowledge_time_utc": f"2026-10-07T00:00:0{index}Z",
            }
            for index, profile in enumerate(MANDATORY_PROFILES)
        },
        "p2_identity_interpretation": (
            "Exact P2 identity is profile-local and semantic equivalence is cross-OS."
        ),
        "shared_exact_projection_by_profile": {
            profile: shared for profile in MANDATORY_PROFILES
        },
        "acceptance": {
            "exact_four_profiles": True,
            "same_candidate_source_revision": True,
            "immutable_package_sha256_all_profiles": True,
            "desktop_windows_linux_p2_semantic_equivalence": True,
            "service_windows_linux_p2_semantic_equivalence": True,
            "shared_p1_p3_p6_exact_identity_all_profiles": True,
            "desktop_installed_discovery_auth_replay_all_os": True,
            "service_real_postgres_rbac_recovery_all_os": True,
            "restart_backup_restore_exact_all_profiles": True,
            "formal_release_not_claimed": True,
        },
        "failed_acceptance": [],
    }


def _review(
    tmp_path: Path,
    *,
    event_name: str = "pull_request",
    git_ref: str = "refs/pull/243/merge",
) -> tuple[dict[str, object], dict[str, object]]:
    equivalence = _write(tmp_path / "equivalence.json", _equivalence())
    return review(
        logical_equivalence=equivalence,
        expected_revision=REVISION,
        checked_out_revision=REVISION,
        event_name=event_name,
        git_ref=git_ref,
        run_conclusion="success",
        required_jobs_success=14,
        required_jobs_total=14,
    )


def test_prcb_c5_candidate_review_waits_for_protected_main(
    tmp_path: Path,
) -> None:
    result, attestation = _review(tmp_path)
    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["qualification"] == "TPAA_1_0_1_CANDIDATE_NOT_QUALIFIED"
    assert result["formal_release_claimed"] is False
    assert result["formal_completion_blocked_by_protected_main"] is True
    assert result["failed_acceptance"] == []
    assert attestation["formal_release_claimed"] is False
    assert len(cast(str, attestation["attestation_payload_sha256"])) == 64


def test_prcb_c5_protected_main_attestation_qualifies_release(
    tmp_path: Path,
) -> None:
    result, attestation = _review(
        tmp_path,
        event_name="push",
        git_ref="refs/heads/main",
    )
    assert result["status"] == "PASS"
    assert result["decision"] == "GO"
    assert result["qualification"] == "TPAA_1_0_1_QUALIFIED"
    assert result["formal_release_claimed"] is True
    assert result["protected_main_exact"] is True
    assert attestation["qualification"] == "TPAA_1_0_1_QUALIFIED"
    assert attestation["formal_release_claimed"] is True


def test_prcb_c5_review_rejects_package_hash_inventory_drift(
    tmp_path: Path,
) -> None:
    payload = _equivalence()
    hashes = cast(dict[str, str], payload["package_sha256_by_profile"])
    hashes["WINDOWS_SERVICE_X64"] = hashes["LINUX_SERVICE_X64"]
    equivalence = _write(tmp_path / "equivalence.json", payload)
    result, _ = review(
        logical_equivalence=equivalence,
        expected_revision=REVISION,
        checked_out_revision=REVISION,
        event_name="pull_request",
        git_ref="refs/pull/243/merge",
        run_conclusion="success",
        required_jobs_success=14,
        required_jobs_total=14,
    )
    assert result["status"] == "FAIL"
    assert result["decision"] == "NO_GO"
    assert "immutable_package_sha256_all_profiles" in result["failed_acceptance"]


def test_prcb_c5_review_rejects_missing_installed_evidence_hash(
    tmp_path: Path,
) -> None:
    payload = _equivalence()
    evidence = cast(
        dict[str, str],
        payload["installed_evidence_sha256_by_profile"],
    )
    evidence.pop("WINDOWS_SERVICE_X64")
    equivalence = _write(tmp_path / "equivalence.json", payload)
    result, _ = review(
        logical_equivalence=equivalence,
        expected_revision=REVISION,
        checked_out_revision=REVISION,
        event_name="pull_request",
        git_ref="refs/pull/243/merge",
        run_conclusion="success",
        required_jobs_success=14,
        required_jobs_total=14,
    )
    assert result["status"] == "FAIL"
    assert "installed_evidence_sha256_all_profiles" in result["failed_acceptance"]
