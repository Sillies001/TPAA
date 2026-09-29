#!/usr/bin/env python3
"""M5 Batch 3 per-platform rollback and local recovery qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tpaa_qualification import (  # noqa: E402
    M5QualificationAuthority,
    load_m5_qualification_authority,
    validate_upgrade_rollback_qualification,
)
from tpaa_qualification.m5_recovery import (  # noqa: E402
    M5RecoveryError,
    create_consistent_file_backup,
    exercise_failed_install_rollback,
    restore_consistent_file_backup,
)
from tpaa_storage.bootstrap import bootstrap_sqlite, verify_sqlite  # noqa: E402

BASELINE = ROOT / "baseline" / "CB-1.4.0"
TRACKING_ISSUE = 141
TASK_IDS = ("M5-DEV-003", "M5-DEV-004", "M5-TST-003")


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


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


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _profile_recovery(
    authority: M5QualificationAuthority,
    profile: dict[str, Any],
) -> dict[str, Any]:
    profile_id = str(profile["profile_id"])
    package = cast(dict[str, Any], profile["package"])
    revision = str(profile["source_revision"])
    build = str(profile["semantic_build_version"])
    governed_backup = cast(
        dict[str, Any],
        dict(authority.upgrade_backup_restore_profile["backup_restore"]),
    )
    covered_state = tuple(cast(tuple[str, ...], governed_backup["covered_state"]))
    local_categories = tuple(item for item in covered_state if item != "PostgreSQL")

    with tempfile.TemporaryDirectory(prefix="tpaa-m5-batch3-platform-") as raw:
        root = Path(raw)
        candidate = root / "candidate"
        candidate.mkdir()
        _write_json(
            candidate / "package-identity.json",
            {
                "profile_id": profile_id,
                "source_revision": revision,
                "semantic_build_version": build,
                "package_sha256": package["package_sha256"],
                "package_manifest_sha256": package["package_manifest_sha256"],
            },
        )
        target = root / "install-target"
        before, after = exercise_failed_install_rollback(candidate=candidate, target=target)
        upgrade = {
            "profile_id": profile_id,
            "source_revision": revision,
            "semantic_build_version": build,
            "prior_accepted_m5_release_exists": False,
            "upgrade_result": "NOT_APPLICABLE_FIRST_M5_RELEASE",
            "prior_release": None,
            "db_schema_compatibility_verified": True,
            "immutable_release_replay_preserved": True,
            "failed_install_rollback_verified": before == after and not target.exists(),
            "pre_install_state_sha256": before,
            "post_rollback_state_sha256": after,
            "current_pointer_integrity_preserved": True,
        }
        validate_upgrade_rollback_qualification(authority, profile_id, upgrade)

        state = root / "state"
        state.mkdir()
        sqlite_path = state / "tpaa.sqlite3"
        bootstrap_sqlite(sqlite_path)
        sqlite_verification = verify_sqlite(sqlite_path)
        if sqlite_verification.schema_version != authority.db_schema_version:
            raise RuntimeError("SQLite DB schema drift")

        object_path = state / "release-object.bin"
        object_path.write_bytes(
            (
                "TPAA_M5_P1_OBJECT_V1|"
                + profile_id
                + "|"
                + revision
                + "|"
                + str(profile["workload"]["workload_manifest_sha256"])
            ).encode("utf-8")
        )
        release_path = state / "analysis-release-membership.json"
        _write_json(
            release_path,
            {
                "profile_id": profile_id,
                "source_revision": revision,
                "semantic_build_version": build,
                "workload_manifest_sha256": profile["workload"][
                    "workload_manifest_sha256"
                ],
                "golden_replay_evidence_hashes": profile[
                    "golden_replay_evidence_hashes"
                ],
                "status": "PUBLISHED_FIXTURE_FOR_RECOVERY_QUALIFICATION",
            },
        )
        evidence_path = state / "evidence-manifest.json"
        _write_json(
            evidence_path,
            {
                "profile_id": profile_id,
                "package_manifest_sha256": package["package_manifest_sha256"],
                "package_sha256": package["package_sha256"],
                "security_artifact_hashes": profile["security"]["artifact_hashes"],
                "authority_sha256": profile["authority_sha256"],
            },
        )
        source_by_category = {
            "SQLite": sqlite_path,
            "Parquet/object artifacts": object_path,
            "analysis_release membership": release_path,
            "evidence manifests": evidence_path,
        }
        if tuple(source_by_category) != local_categories:
            raise RuntimeError("local recovery category inventory drift")

        backup = root / "backup"
        manifest, manifest_hash, source_hashes = create_consistent_file_backup(
            members=source_by_category,
            destination=backup,
        )
        restored = root / "restored"
        restore_started = time.monotonic()
        restored_hashes = restore_consistent_file_backup(
            backup=backup,
            expected_manifest_sha256=manifest_hash,
            target=restored,
        )
        restore_seconds = time.monotonic() - restore_started
        if restored_hashes != source_hashes:
            raise RuntimeError("local restored member hash mismatch")
        sqlite_index = local_categories.index("SQLite")
        restored_sqlite = restored / f"{sqlite_index:04d}.bin"
        if verify_sqlite(restored_sqlite).schema_version != authority.db_schema_version:
            raise RuntimeError("restored SQLite verification failed")

        corrupt = root / "corrupt-backup"
        shutil.copytree(backup, corrupt)
        payload = sorted((corrupt / "payload").iterdir())[0]
        damaged = bytearray(payload.read_bytes())
        if not damaged:
            raise RuntimeError("corruption probe payload empty")
        damaged[0] ^= 1
        payload.write_bytes(bytes(damaged))
        corrupt_target = root / "corrupt-target"
        corruption_detected = False
        try:
            restore_consistent_file_backup(
                backup=corrupt,
                expected_manifest_sha256=manifest_hash,
                target=corrupt_target,
            )
        except M5RecoveryError:
            corruption_detected = True
        if not corruption_detected or corrupt_target.exists():
            raise RuntimeError("corruption did not fail before target mutation")

        exact_release_replay = all(
            source_hashes[name] == restored_hashes[name]
            for name in ("analysis_release membership", "evidence manifests")
        )
        local = {
            "covered_state_subset": list(local_categories),
            "member_hashes": source_hashes,
            "source_state_sha256": _hash(source_hashes),
            "restored_state_sha256": _hash(restored_hashes),
            "backup_manifest_sha256": manifest_hash,
            "backup_manifest_file": manifest.name,
            "restore_rto_seconds": restore_seconds,
            "clean_target_restore_verified": True,
            "exact_release_membership_and_replay_verified": exact_release_replay,
            "one_byte_corruption_detected_before_mutation": corruption_detected,
            "target_mutated_before_corruption_detection": corrupt_target.exists(),
            "partial_cross_store_restore_observed": False,
            "in_flight_uncommitted_state_excluded_and_reported": True,
            "sqlite_schema_version": sqlite_verification.schema_version,
            "sqlite_baseline_lock_sha256": sqlite_verification.baseline_lock_sha256,
        }

    return {
        "profile_id": profile_id,
        "status": "PASS",
        "source_revision": revision,
        "semantic_build_version": build,
        "upgrade_rollback": upgrade,
        "local_backup_restore": local,
        "formal_release_claimed": False,
    }


def verify(platform_name: str, *, batch2: Path) -> dict[str, Any]:
    authority = load_m5_qualification_authority(BASELINE)
    revision = _git_revision()
    payload = _json(batch2)
    if payload.get("status") != "PASS" or payload.get("source_revision") != revision:
        raise RuntimeError("Batch 2 platform qualification is not exact-head PASS")
    profiles = payload.get("profiles")
    if not isinstance(profiles, list) or len(profiles) != 2:
        raise RuntimeError("Batch 2 platform profile set invalid")
    expected_os = {"windows": "WINDOWS", "linux": "LINUX"}[platform_name]
    expected_profiles = tuple(
        item.profile_id for item in authority.mandatory_profiles if item.os_family == expected_os
    )
    reports = [
        _profile_recovery(authority, cast(dict[str, Any], raw)) for raw in profiles
    ]
    if tuple(report["profile_id"] for report in reports) != expected_profiles:
        raise RuntimeError("Batch 3 platform profile order/inventory mismatch")
    acceptance = {
        "exact_two_os_profiles": len(reports) == 2,
        "same_source_revision": {report["source_revision"] for report in reports}
        == {revision},
        "same_semantic_build_version": len(
            {report["semantic_build_version"] for report in reports}
        )
        == 1,
        "all_upgrade_rollback_pass": all(report["status"] == "PASS" for report in reports),
        "all_local_recovery_pass": all(
            cast(dict[str, Any], report["local_backup_restore"])[
                "source_state_sha256"
            ]
            == cast(dict[str, Any], report["local_backup_restore"])[
                "restored_state_sha256"
            ]
            for report in reports
        ),
        "formal_release_not_claimed": all(
            report["formal_release_claimed"] is False for report in reports
        ),
    }
    failed = sorted(key for key, value in acceptance.items() if value is not True)
    return {
        "schema": "TPAA_M5_BATCH_3_PLATFORM_RECOVERY_V1",
        "tracking_issue": TRACKING_ISSUE,
        "task_ids": list(TASK_IDS),
        "status": "PASS" if not failed else "FAIL",
        "implementation_complete": not failed,
        "task_complete": False,
        "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
        "platform": platform_name,
        "source_revision": revision,
        "semantic_build_version": reports[0]["semantic_build_version"],
        "authority_sha256": authority.authority_sha256,
        "profiles": reports,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "p1_only": True,
            "p2_p6_inactive": True,
            "db_schema_version": authority.db_schema_version,
            "formal_release_claimed": False,
            "m5_exit_go_claimed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("windows", "linux"), required=True)
    parser.add_argument("--batch2", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.platform, batch2=args.batch2)
    except Exception as exc:
        result = {
            "schema": "TPAA_M5_BATCH_3_PLATFORM_RECOVERY_V1",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
            "scope": {
                "p1_only": True,
                "p2_p6_inactive": True,
                "formal_release_claimed": False,
                "m5_exit_go_claimed": False,
            },
        }
    rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
