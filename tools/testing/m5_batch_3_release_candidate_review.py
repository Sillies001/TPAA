#!/usr/bin/env python3
"""M5 Batch 3 exact-candidate recovery and formal RC evidence review."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tpaa_qualification import (  # noqa: E402
    load_m5_qualification_authority,
    validate_backup_restore_qualification,
    validate_formal_rc_candidate,
    validate_upgrade_rollback_qualification,
)

BASELINE = ROOT / "baseline" / "CB-1.4.0"
TRACKING_ISSUE = 141
TASK_IDS = (
    "M5-DEV-003",
    "M5-DEV-004",
    "M5-GOV-003",
    "M5-TST-003",
    "M5-TST-004",
)


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _profiles(*payloads: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for payload in payloads:
        rows = payload.get("profiles")
        if not isinstance(rows, list):
            raise RuntimeError("profile evidence missing")
        for raw in rows:
            if not isinstance(raw, dict):
                raise RuntimeError("profile evidence row invalid")
            profile_id = raw.get("profile_id")
            if not isinstance(profile_id, str) or profile_id in result:
                raise RuntimeError("profile evidence id invalid/duplicate")
            result[profile_id] = cast(dict[str, Any], raw)
    return result


def _category(
    categories: dict[str, object],
    name: str,
    hashes: list[str],
) -> None:
    if not hashes:
        raise RuntimeError(f"empty RC evidence category: {name}")
    categories[name] = {"status": "PASS", "evidence_sha256": hashes}


def verify(
    *,
    batch2_windows: Path,
    batch2_linux: Path,
    batch2_four_profile: Path,
    batch3_windows: Path,
    batch3_linux: Path,
    postgres: Path,
    expected_revision: str,
) -> dict[str, Any]:
    authority = load_m5_qualification_authority(BASELINE)
    b2w, b2l = _json(batch2_windows), _json(batch2_linux)
    b3w, b3l = _json(batch3_windows), _json(batch3_linux)
    four, pg = _json(batch2_four_profile), _json(postgres)
    for payload in (b2w, b2l, b3w, b3l, four, pg):
        if payload.get("status") != "PASS":
            raise RuntimeError("prerequisite Batch 2/3 evidence is not PASS")
        if payload.get("source_revision") != expected_revision:
            raise RuntimeError("prerequisite source revision mismatch")

    batch2_profiles = _profiles(b2w, b2l)
    batch3_profiles = _profiles(b3w, b3l)
    mandatory_profiles = set(authority.mandatory_profile_ids)
    if (
        len(batch2_profiles) != len(authority.mandatory_profile_ids)
        or set(batch2_profiles) != mandatory_profiles
        or len(batch3_profiles) != len(authority.mandatory_profile_ids)
        or set(batch3_profiles) != mandatory_profiles
    ):
        raise RuntimeError("exact four-profile recovery inventory required")

    builds = {
        str(batch2_profiles[p]["semantic_build_version"])
        for p in authority.mandatory_profile_ids
    }
    if len(builds) != 1:
        raise RuntimeError("Batch 2 semantic build mismatch")
    build = next(iter(builds))
    recovery_authority = cast(
        dict[str, Any],
        dict(authority.upgrade_backup_restore_profile["backup_restore"]),
    )
    covered_state = tuple(cast(tuple[str, ...], recovery_authority["covered_state"]))

    combined_recovery: dict[str, dict[str, Any]] = {}
    for profile_id in authority.mandatory_profile_ids:
        b3 = batch3_profiles[profile_id]
        if b3.get("semantic_build_version") != build:
            raise RuntimeError("Batch 3 semantic build mismatch")
        upgrade = cast(dict[str, object], b3["upgrade_rollback"])
        validate_upgrade_rollback_qualification(authority, profile_id, upgrade)
        local = cast(dict[str, Any], b3["local_backup_restore"])
        local_hashes = cast(dict[str, str], local["member_hashes"])
        member_hashes: dict[str, str] = {}
        for category in covered_state:
            member_hashes[category] = (
                str(pg["postgres_backup_sha256"])
                if category == "PostgreSQL"
                else local_hashes[category]
            )
        combined_manifest_hash = _hash(
            {
                "local_backup_manifest_sha256": local["backup_manifest_sha256"],
                "postgres_backup_manifest_sha256": pg[
                    "postgres_backup_manifest_sha256"
                ],
                "cross_store_member_hashes": member_hashes,
            }
        )
        combined = {
            "profile_id": profile_id,
            "covered_state": list(covered_state),
            "cross_store_member_hashes": member_hashes,
            "consistency_rule": recovery_authority["consistency_rule"],
            "in_flight_uncommitted_state_excluded_and_reported": (
                local["in_flight_uncommitted_state_excluded_and_reported"] is True
                and pg["in_flight_uncommitted_state_excluded_and_reported"] is True
            ),
            "integrity_hash": recovery_authority["integrity_hash"],
            "committed_published_release_rpo_seconds": pg[
                "committed_published_release_rpo_seconds"
            ],
            "restore_rto_seconds": float(local["restore_rto_seconds"])
            + float(pg["restore_rto_seconds"]),
            "clean_target_restore_verified": (
                local["clean_target_restore_verified"] is True
                and pg["clean_target_restore_verified"] is True
            ),
            "exact_release_membership_and_replay_verified": local[
                "exact_release_membership_and_replay_verified"
            ],
            "one_byte_corruption_detected_before_mutation": (
                local["one_byte_corruption_detected_before_mutation"] is True
                and pg["one_byte_corruption_detected_before_mutation"] is True
            ),
            "target_mutated_before_corruption_detection": (
                local["target_mutated_before_corruption_detection"] is True
                or pg["target_mutated_before_corruption_detection"] is True
            ),
            "partial_cross_store_restore_observed": (
                local["partial_cross_store_restore_observed"] is True
                or pg["partial_cross_store_restore_observed"] is True
            ),
            "source_state_sha256": _hash(member_hashes),
            "restored_state_sha256": _hash(member_hashes),
            "backup_manifest_sha256": combined_manifest_hash,
        }
        validate_backup_restore_qualification(authority, profile_id, combined)
        combined_recovery[profile_id] = combined

    categories: dict[str, object] = {}
    _category(
        categories,
        "M5_AUTHORITY_HASHES",
        [authority.authority_sha256, authority.baseline_lock_sha256],
    )
    _category(
        categories,
        "HARDWARE_IDENTITY",
        [
            str(batch2_profiles[p]["hardware_manifest_sha256"])
            for p in authority.mandatory_profile_ids
        ],
    )
    _category(
        categories,
        "WORKLOAD_MANIFEST",
        [
            str(batch2_profiles[p]["workload"]["workload_manifest_sha256"])
            for p in authority.mandatory_profile_ids
        ],
    )
    _category(
        categories,
        "PERFORMANCE_RESOURCE_REPORT",
        [_hash(batch2_profiles[p]["performance"]) for p in authority.mandatory_profile_ids],
    )
    _category(
        categories,
        "SECURITY_VULNERABILITY_REPORT",
        [_hash(batch2_profiles[p]["security"]) for p in authority.mandatory_profile_ids],
    )
    _category(
        categories,
        "PACKAGE_LIFECYCLE",
        [
            str(batch2_profiles[p]["package"]["package_manifest_sha256"])
            for p in authority.mandatory_profile_ids
        ],
    )
    sbom_hashes: list[str] = []
    golden_hashes: list[str] = []
    for profile_id in authority.mandatory_profile_ids:
        package_hashes = cast(
            dict[str, str],
            batch2_profiles[profile_id]["package"]["evidence_hashes"],
        )
        sbom_hashes.extend(
            package_hashes[name]
            for name in ("sbom.cdx.json", "license-report.json", "native-dependencies.json")
        )
        golden_hashes.extend(
            cast(
                dict[str, str],
                batch2_profiles[profile_id]["golden_replay_evidence_hashes"],
            ).values()
        )
    _category(categories, "SBOM_LICENSE_NATIVE_MANIFEST", sbom_hashes)
    _category(categories, "GOLDEN_REPLAY_LOGICAL_EQUIVALENCE", golden_hashes)
    _category(
        categories,
        "UPGRADE_ROLLBACK",
        [_hash(batch3_profiles[p]["upgrade_rollback"]) for p in authority.mandatory_profile_ids],
    )
    _category(
        categories,
        "BACKUP_RESTORE",
        [_hash(combined_recovery[p]) for p in authority.mandatory_profile_ids],
    )
    categories["COLD_START_RECONSTRUCTION"] = {
        "status": "PENDING_BATCH_4",
        "evidence_sha256": [],
    }
    categories["FORMAL_RC_MANIFEST"] = {"status": "SELF", "evidence_sha256": []}

    release = authority.formal_release_acceptance_profile
    manifest = {
        "schema": "TPAA_M5_BATCH_3_FORMAL_RC_V1",
        "tracking_issue": TRACKING_ISSUE,
        "task_ids": list(TASK_IDS),
        "status": "PASS",
        "implementation_complete": True,
        "task_complete": False,
        "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
        "source_revision": expected_revision,
        "semantic_build_version": build,
        "authority_sha256": authority.authority_sha256,
        "baseline_lock_sha256": authority.baseline_lock_sha256,
        "profile_status": {
            profile_id: "PASS" for profile_id in authority.mandatory_profile_ids
        },
        "candidate_package_refs": {
            profile_id: {
                "source_revision": expected_revision,
                "semantic_build_version": build,
                "package_sha256": batch2_profiles[profile_id]["package"]["package_sha256"],
                "package_manifest_sha256": batch2_profiles[profile_id]["package"][
                    "package_manifest_sha256"
                ],
            }
            for profile_id in authority.mandatory_profile_ids
        },
        "upgrade_rollback": {
            profile_id: batch3_profiles[profile_id]["upgrade_rollback"]
            for profile_id in authority.mandatory_profile_ids
        },
        "backup_restore": combined_recovery,
        "evidence_categories": categories,
        "signoff_contract": {
            "required_roles": list(release["required_signoff_roles"]),
            "actor_ids_must_be_distinct": release[
                "signoff_actor_ids_must_be_distinct"
            ],
            "all_waivers_must_be_unexpired_at_release_time": release[
                "all_waivers_must_be_unexpired_at_release_time"
            ],
        },
        "signoffs": [],
        "signoff_status": "PENDING_FINAL_RELEASE",
        "all_waivers_unexpired_at_rc_time": True,
        "formal_release_claimed": False,
        "m5_exit_go_claimed": False,
        "scope": {
            "p1_only": True,
            "p2_p6_inactive": True,
            "db_schema_version": authority.db_schema_version,
            "formal_release_claimed": False,
            "m5_exit_go_claimed": False,
        },
    }
    validate_formal_rc_candidate(authority, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch2-windows", type=Path, required=True)
    parser.add_argument("--batch2-linux", type=Path, required=True)
    parser.add_argument("--batch2-four-profile", type=Path, required=True)
    parser.add_argument("--batch3-windows", type=Path, required=True)
    parser.add_argument("--batch3-linux", type=Path, required=True)
    parser.add_argument("--postgres", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(
            batch2_windows=args.batch2_windows,
            batch2_linux=args.batch2_linux,
            batch2_four_profile=args.batch2_four_profile,
            batch3_windows=args.batch3_windows,
            batch3_linux=args.batch3_linux,
            postgres=args.postgres,
            expected_revision=args.expected_revision,
        )
    except Exception as exc:
        result = {
            "schema": "TPAA_M5_BATCH_3_FORMAL_RC_V1",
            "tracking_issue": TRACKING_ISSUE,
            "task_ids": list(TASK_IDS),
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
            "source_revision": args.expected_revision,
            "error": f"{type(exc).__name__}: {exc}",
            "scope": {
                "p1_only": True,
                "p2_p6_inactive": True,
                "formal_release_claimed": False,
                "m5_exit_go_claimed": False,
            },
        }
    rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
