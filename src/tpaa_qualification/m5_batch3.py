"""M5 Batch 3 authority-driven upgrade, recovery and RC contract checks."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .m5_profiles import M5QualificationAuthority, M5QualificationError

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def _fail(authority: M5QualificationAuthority, code_key: str, detail: str) -> None:
    raise M5QualificationError(authority.error_code(code_key), detail)


def _mapping(
    authority: M5QualificationAuthority,
    value: object,
    *,
    field: str,
    code_key: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(authority, code_key, f"{field} must be an object")
    return value


def _sequence(
    authority: M5QualificationAuthority,
    value: object,
    *,
    field: str,
    code_key: str,
) -> tuple[object, ...]:
    if not isinstance(value, (list, tuple)):
        _fail(authority, code_key, f"{field} must be a sequence")
    return tuple(value)


def _sha256(
    authority: M5QualificationAuthority,
    value: object,
    *,
    field: str,
    code_key: str,
) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        _fail(authority, code_key, f"{field} must be lowercase SHA-256")
    return value


def _source_revision(value: object, *, authority: M5QualificationAuthority) -> str:
    if not isinstance(value, str) or _COMMIT_RE.fullmatch(value) is None:
        _fail(authority, "release_evidence_incomplete", "source_revision")
    return value


def validate_upgrade_rollback_qualification(
    authority: M5QualificationAuthority,
    profile_id: str,
    report: Mapping[str, object],
) -> None:
    """Validate first/subsequent release upgrade and failed-install rollback evidence."""

    authority.certification_profile(profile_id)
    recovery = authority.upgrade_backup_restore_profile
    upgrade = _mapping(
        authority,
        recovery.get("upgrade"),
        field="upgrade",
        code_key="upgrade_rollback",
    )
    if report.get("profile_id") != profile_id:
        _fail(authority, "upgrade_rollback", f"{profile_id}: profile binding mismatch")
    _source_revision(report.get("source_revision"), authority=authority)
    semantic = report.get("semantic_build_version")
    if not isinstance(semantic, str) or not semantic:
        _fail(authority, "upgrade_rollback", f"{profile_id}: semantic build version")

    prior_exists = report.get("prior_accepted_m5_release_exists")
    if not isinstance(prior_exists, bool):
        _fail(
            authority,
            "upgrade_rollback",
            f"{profile_id}: prior-release existence must be explicit",
        )
    if prior_exists:
        if report.get("upgrade_result") != "PASS":
            _fail(authority, "upgrade_rollback", f"{profile_id}: subsequent upgrade")
        prior = _mapping(
            authority,
            report.get("prior_release"),
            field="prior_release",
            code_key="upgrade_rollback",
        )
        if (
            prior.get("profile_id") != profile_id
            or prior.get("source_kind") != upgrade.get("subsequent_supported_source")
        ):
            _fail(
                authority,
                "upgrade_rollback",
                f"{profile_id}: immediate prior same-profile release required",
            )
        _sha256(
            authority,
            prior.get("package_sha256"),
            field="prior_release.package_sha256",
            code_key="upgrade_rollback",
        )
        _sha256(
            authority,
            prior.get("package_manifest_sha256"),
            field="prior_release.package_manifest_sha256",
            code_key="upgrade_rollback",
        )
        if report.get("rollback_target") != upgrade.get("rollback_target"):
            _fail(authority, "upgrade_rollback", f"{profile_id}: rollback target drift")
    else:
        if report.get("upgrade_result") != "NOT_APPLICABLE_FIRST_M5_RELEASE":
            _fail(authority, "upgrade_rollback", f"{profile_id}: first-release N/A rule")
        if report.get("prior_release") is not None:
            _fail(authority, "upgrade_rollback", f"{profile_id}: invented prior release")

    requirements = {
        "db_schema_compatibility_verified": upgrade.get("db_schema_compatibility_required"),
        "immutable_release_replay_preserved": upgrade.get(
            "immutable_release_replay_preservation_required"
        ),
        "failed_install_rollback_verified": upgrade.get(
            "failed_upgrade_rollback_required"
        ),
    }
    for key, governed in requirements.items():
        if governed is not True or report.get(key) is not True:
            _fail(authority, "upgrade_rollback", f"{profile_id}: {key}")

    before = _sha256(
        authority,
        report.get("pre_install_state_sha256"),
        field="pre_install_state_sha256",
        code_key="upgrade_rollback",
    )
    after = _sha256(
        authority,
        report.get("post_rollback_state_sha256"),
        field="post_rollback_state_sha256",
        code_key="upgrade_rollback",
    )
    if before != after:
        _fail(authority, "upgrade_rollback", f"{profile_id}: rollback changed state")
    if (
        upgrade.get("current_pointer_corruption_permitted") is not False
        or report.get("current_pointer_integrity_preserved") is not True
    ):
        _fail(authority, "upgrade_rollback", f"{profile_id}: current pointer integrity")


def validate_backup_restore_qualification(
    authority: M5QualificationAuthority,
    profile_id: str,
    report: Mapping[str, object],
) -> None:
    """Validate the governed cross-store backup/restore qualification envelope."""

    authority.certification_profile(profile_id)
    governed = _mapping(
        authority,
        authority.upgrade_backup_restore_profile.get("backup_restore"),
        field="backup_restore",
        code_key="backup_restore",
    )
    expected_state = tuple(governed.get("covered_state", ()))
    actual_state = _sequence(
        authority,
        report.get("covered_state"),
        field="covered_state",
        code_key="backup_restore",
    )
    if actual_state != expected_state:
        _fail(authority, "backup_restore", f"{profile_id}: covered state mismatch")

    hashes = _mapping(
        authority,
        report.get("cross_store_member_hashes"),
        field="cross_store_member_hashes",
        code_key="backup_restore",
    )
    if tuple(hashes) != expected_state:
        _fail(authority, "backup_restore", f"{profile_id}: hash inventory mismatch")
    for category, digest in hashes.items():
        _sha256(
            authority,
            digest,
            field=f"cross_store_member_hashes.{category}",
            code_key="backup_restore",
        )

    if report.get("integrity_hash") != governed.get("integrity_hash"):
        _fail(authority, "backup_restore", f"{profile_id}: integrity hash")
    if report.get("committed_published_release_rpo_seconds") != governed.get(
        "committed_published_release_rpo_seconds"
    ):
        _fail(authority, "backup_restore", f"{profile_id}: RPO")
    rto = report.get("restore_rto_seconds")
    max_rto = governed.get("restore_rto_seconds_max")
    if (
        isinstance(rto, bool)
        or not isinstance(rto, (int, float))
        or isinstance(max_rto, bool)
        or not isinstance(max_rto, (int, float))
        or float(rto) > float(max_rto)
    ):
        _fail(authority, "backup_restore", f"{profile_id}: RTO")

    requirements = {
        "clean_target_restore_verified": governed.get("clean_target_restore_required"),
        "exact_release_membership_and_replay_verified": governed.get(
            "exact_release_membership_and_replay_required"
        ),
        "one_byte_corruption_detected_before_mutation": governed.get(
            "one_byte_corruption_must_fail_before_target_mutation"
        ),
    }
    for key, required in requirements.items():
        if required is not True or report.get(key) is not True:
            _fail(authority, "backup_restore", f"{profile_id}: {key}")
    if report.get("target_mutated_before_corruption_detection") is not False:
        _fail(authority, "backup_restore", f"{profile_id}: corruption mutated target")
    if (
        governed.get("partial_cross_store_restore_permitted") is not False
        or report.get("partial_cross_store_restore_observed") is not False
    ):
        _fail(authority, "backup_restore", f"{profile_id}: partial restore")

    source_state = _sha256(
        authority,
        report.get("source_state_sha256"),
        field="source_state_sha256",
        code_key="backup_restore",
    )
    restored_state = _sha256(
        authority,
        report.get("restored_state_sha256"),
        field="restored_state_sha256",
        code_key="backup_restore",
    )
    _sha256(
        authority,
        report.get("backup_manifest_sha256"),
        field="backup_manifest_sha256",
        code_key="backup_restore",
    )
    if source_state != restored_state:
        _fail(authority, "backup_restore", f"{profile_id}: restored state mismatch")


def validate_signoff_contract(
    authority: M5QualificationAuthority,
    contract: Mapping[str, object],
) -> None:
    """Validate the pre-signoff RC contract without claiming final approvals."""

    release = authority.formal_release_acceptance_profile
    roles = _sequence(
        authority,
        contract.get("required_roles"),
        field="required_roles",
        code_key="signoff_missing_or_not_distinct",
    )
    expected_roles = tuple(release.get("required_signoff_roles", ()))
    if roles != expected_roles:
        _fail(authority, "signoff_missing_or_not_distinct", "signoff role inventory")
    if (
        release.get("signoff_actor_ids_must_be_distinct") is not True
        or contract.get("actor_ids_must_be_distinct") is not True
        or release.get("all_waivers_must_be_unexpired_at_release_time") is not True
        or contract.get("all_waivers_must_be_unexpired_at_release_time") is not True
    ):
        _fail(authority, "signoff_missing_or_not_distinct", "signoff contract drift")


def validate_release_signoffs(
    authority: M5QualificationAuthority,
    signoffs: Sequence[Mapping[str, object]],
) -> None:
    """Validate the final three-role distinct-actor signoff set for Batch 4 use."""

    expected_roles = tuple(
        authority.formal_release_acceptance_profile.get("required_signoff_roles", ())
    )
    roles: list[str] = []
    actors: list[str] = []
    for signoff in signoffs:
        role = signoff.get("role")
        actor = signoff.get("actor_id")
        if not isinstance(role, str) or not isinstance(actor, str) or not actor:
            _fail(authority, "signoff_missing_or_not_distinct", "signoff role/actor")
        roles.append(role)
        actors.append(actor)
    if tuple(roles) != expected_roles or len(set(actors)) != len(expected_roles):
        _fail(authority, "signoff_missing_or_not_distinct", "required distinct signoffs")


def validate_formal_rc_candidate(
    authority: M5QualificationAuthority,
    manifest: Mapping[str, object],
) -> None:
    """Validate a Batch 3 RC evidence contract without authorizing formal release."""

    revision = _source_revision(manifest.get("source_revision"), authority=authority)
    semantic = manifest.get("semantic_build_version")
    if not isinstance(semantic, str) or not semantic:
        _fail(authority, "release_evidence_incomplete", "semantic build version")
    if manifest.get("authority_sha256") != authority.authority_sha256:
        _fail(authority, "release_evidence_incomplete", "authority hash")
    if manifest.get("baseline_lock_sha256") != authority.baseline_lock_sha256:
        _fail(authority, "release_evidence_incomplete", "baseline lock")

    profile_status = _mapping(
        authority,
        manifest.get("profile_status"),
        field="profile_status",
        code_key="release_evidence_incomplete",
    )
    if tuple(profile_status) != authority.mandatory_profile_ids or any(
        profile_status[profile_id] != "PASS"
        for profile_id in authority.mandatory_profile_ids
    ):
        _fail(authority, "release_evidence_incomplete", "mandatory profile status")

    release = authority.formal_release_acceptance_profile
    categories = _mapping(
        authority,
        manifest.get("evidence_categories"),
        field="evidence_categories",
        code_key="release_evidence_incomplete",
    )
    required_categories = tuple(release.get("required_evidence_categories", ()))
    if tuple(categories) != required_categories:
        _fail(authority, "release_evidence_incomplete", "RC evidence inventory")
    for category, raw in categories.items():
        row = _mapping(
            authority,
            raw,
            field=f"evidence_categories.{category}",
            code_key="release_evidence_incomplete",
        )
        status = row.get("status")
        if category == "COLD_START_RECONSTRUCTION":
            if status != "PENDING_BATCH_4":
                _fail(authority, "release_evidence_incomplete", "cold-start status")
        elif category == "FORMAL_RC_MANIFEST":
            if status != "SELF":
                _fail(authority, "release_evidence_incomplete", "RC self category")
        elif status != "PASS":
            _fail(authority, "release_evidence_incomplete", f"category {category}")
        if status == "PASS":
            items = _sequence(
                authority,
                row.get("evidence_sha256"),
                field=f"{category}.evidence_sha256",
                code_key="release_evidence_incomplete",
            )
            if not items:
                _fail(authority, "release_evidence_incomplete", f"{category} hash")
            for index, digest in enumerate(items):
                _sha256(
                    authority,
                    digest,
                    field=f"{category}.evidence_sha256[{index}]",
                    code_key="release_evidence_incomplete",
                )

    signoff_contract = _mapping(
        authority,
        manifest.get("signoff_contract"),
        field="signoff_contract",
        code_key="signoff_missing_or_not_distinct",
    )
    validate_signoff_contract(authority, signoff_contract)
    signoffs = _sequence(
        authority,
        manifest.get("signoffs"),
        field="signoffs",
        code_key="release_evidence_incomplete",
    )
    if signoffs:
        _fail(authority, "release_evidence_incomplete", "Batch 3 final signoffs")
    if (
        manifest.get("formal_release_claimed") is not False
        or manifest.get("m5_exit_go_claimed") is not False
        or manifest.get("signoff_status") != "PENDING_FINAL_RELEASE"
        or manifest.get("source_revision") != revision
    ):
        _fail(authority, "release_evidence_incomplete", "Batch 3 formal-claim guard")
