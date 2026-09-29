from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_qualification import (
    M5QualificationError,
    load_m5_qualification_authority,
    validate_backup_restore_qualification,
    validate_formal_rc_candidate,
    validate_release_signoffs,
    validate_signoff_contract,
    validate_upgrade_rollback_qualification,
)
from tpaa_qualification.m5_recovery import (
    M5RecoveryError,
    create_consistent_file_backup,
    restore_consistent_file_backup,
)

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
REVISION = "a" * 40
BUILD = "0.0.0+m5.batch3-test"
H = "b" * 64


def _upgrade(profile_id: str) -> dict[str, object]:
    return {
        "profile_id": profile_id,
        "source_revision": REVISION,
        "semantic_build_version": BUILD,
        "prior_accepted_m5_release_exists": False,
        "upgrade_result": "NOT_APPLICABLE_FIRST_M5_RELEASE",
        "prior_release": None,
        "db_schema_compatibility_verified": True,
        "immutable_release_replay_preserved": True,
        "failed_install_rollback_verified": True,
        "pre_install_state_sha256": H,
        "post_rollback_state_sha256": H,
        "current_pointer_integrity_preserved": True,
    }


def _backup(authority, profile_id: str) -> dict[str, object]:
    covered = list(authority.upgrade_backup_restore_profile["backup_restore"]["covered_state"])
    return {
        "profile_id": profile_id,
        "covered_state": covered,
        "cross_store_member_hashes": {name: H for name in covered},
        "consistency_rule": authority.upgrade_backup_restore_profile["backup_restore"][
            "consistency_rule"
        ],
        "in_flight_uncommitted_state_excluded_and_reported": True,
        "integrity_hash": "SHA-256",
        "committed_published_release_rpo_seconds": 0,
        "restore_rto_seconds": 1.0,
        "clean_target_restore_verified": True,
        "exact_release_membership_and_replay_verified": True,
        "one_byte_corruption_detected_before_mutation": True,
        "target_mutated_before_corruption_detection": False,
        "partial_cross_store_restore_observed": False,
        "source_state_sha256": H,
        "restored_state_sha256": H,
        "backup_manifest_sha256": H,
    }


def _signoff_contract(authority) -> dict[str, object]:
    release = authority.formal_release_acceptance_profile
    return {
        "required_roles": list(release["required_signoff_roles"]),
        "actor_ids_must_be_distinct": True,
        "all_waivers_must_be_unexpired_at_release_time": True,
    }


def _rc(authority) -> dict[str, object]:
    categories: dict[str, object] = {}
    for category in authority.formal_release_acceptance_profile[
        "required_evidence_categories"
    ]:
        if category == "COLD_START_RECONSTRUCTION":
            categories[category] = {"status": "PENDING_BATCH_4", "evidence_sha256": []}
        elif category == "FORMAL_RC_MANIFEST":
            categories[category] = {"status": "SELF", "evidence_sha256": []}
        else:
            categories[category] = {"status": "PASS", "evidence_sha256": [H]}
    return {
        "source_revision": REVISION,
        "semantic_build_version": BUILD,
        "authority_sha256": authority.authority_sha256,
        "baseline_lock_sha256": authority.baseline_lock_sha256,
        "profile_status": {
            profile_id: "PASS" for profile_id in authority.mandatory_profile_ids
        },
        "candidate_package_refs": {
            profile_id: {
                "source_revision": REVISION,
                "semantic_build_version": BUILD,
                "package_sha256": H,
                "package_manifest_sha256": H,
            }
            for profile_id in authority.mandatory_profile_ids
        },
        "evidence_categories": categories,
        "signoff_contract": _signoff_contract(authority),
        "signoffs": [],
        "signoff_status": "PENDING_FINAL_RELEASE",
        "all_waivers_unexpired_at_rc_time": True,
        "formal_release_claimed": False,
        "m5_exit_go_claimed": False,
    }


def test_m5_batch_3_authority_projection_and_first_release_upgrade() -> None:
    authority = load_m5_qualification_authority(BASELINE)
    assert authority.upgrade_backup_restore_profile["profile_id"] == "M5_UPGRADE_RECOVERY_V1"
    for code in ("upgrade_rollback", "backup_restore", "signoff_missing_or_not_distinct"):
        assert authority.error_code(code).startswith("FAIL_CLOSED_M5_")

    profile_id = authority.mandatory_profile_ids[0]
    report = _upgrade(profile_id)
    validate_upgrade_rollback_qualification(authority, profile_id, report)
    subsequent = dict(report)
    subsequent.update(
        {
            "prior_accepted_m5_release_exists": True,
            "upgrade_result": "PASS",
            "prior_release": {
                "profile_id": profile_id,
                "source_kind": authority.upgrade_backup_restore_profile["upgrade"][
                    "subsequent_supported_source"
                ],
                "package_sha256": H,
                "package_manifest_sha256": H,
            },
            "supported_prior_release_count": 1,
            "rollback_target": authority.upgrade_backup_restore_profile["upgrade"][
                "rollback_target"
            ],
        }
    )
    validate_upgrade_rollback_qualification(authority, profile_id, subsequent)

    bad = dict(report)
    bad["failed_install_rollback_verified"] = False
    with pytest.raises(M5QualificationError) as exc:
        validate_upgrade_rollback_qualification(authority, profile_id, bad)
    assert exc.value.code == authority.error_code("upgrade_rollback")


def test_m5_batch_3_backup_restore_and_corruption_fail_closed(tmp_path: Path) -> None:
    authority = load_m5_qualification_authority(BASELINE)
    profile_id = authority.mandatory_profile_ids[0]
    validate_backup_restore_qualification(authority, profile_id, _backup(authority, profile_id))

    source = tmp_path / "source.bin"
    source.write_bytes(b"m5-recovery-source")
    backup = tmp_path / "backup"
    _, manifest_hash, _ = create_consistent_file_backup(
        members={"evidence manifests": source},
        destination=backup,
    )
    payload = next((backup / "payload").iterdir())
    raw = bytearray(payload.read_bytes())
    raw[0] ^= 1
    payload.write_bytes(bytes(raw))
    target = tmp_path / "target"
    with pytest.raises(M5RecoveryError):
        restore_consistent_file_backup(
            backup=backup,
            expected_manifest_sha256=manifest_hash,
            target=target,
        )
    assert not target.exists()


def test_m5_batch_3_rc_contract_and_distinct_signoff_guard() -> None:
    authority = load_m5_qualification_authority(BASELINE)
    contract = _signoff_contract(authority)
    validate_signoff_contract(authority, contract)
    validate_formal_rc_candidate(authority, _rc(authority))

    with pytest.raises(M5QualificationError) as exc:
        validate_release_signoffs(
            authority,
            [
                {"role": "RELEASE_MANAGER", "actor_id": "actor-a"},
                {"role": "INDEPENDENT_QA", "actor_id": "actor-a"},
                {"role": "SECURITY_APPROVER", "actor_id": "actor-c"},
            ],
        )
    assert exc.value.code == authority.error_code("signoff_missing_or_not_distinct")

    missing_profile = _rc(authority)
    statuses = dict(missing_profile["profile_status"])
    statuses.pop(authority.mandatory_profile_ids[-1])
    missing_profile["profile_status"] = statuses
    with pytest.raises(M5QualificationError) as exc:
        validate_formal_rc_candidate(authority, missing_profile)
    assert exc.value.code == authority.error_code("release_evidence_incomplete")
