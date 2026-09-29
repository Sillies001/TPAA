#!/usr/bin/env python3
"""M5-TST-005 same-candidate four-profile parity review."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tpaa_qualification import load_m5_qualification_authority  # noqa: E402

BASELINE = ROOT / "baseline" / "CB-1.4.0"
TASK_BASELINE = ROOT / "docs" / "baseline" / "SDIB-1.4" / "M5_TASK_BASELINE.json"
TRACKING_ISSUE = 142
TASK_ID = "M5-TST-005"


def _json(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path}: root must be object")
    return cast(dict[str, Any], value)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _combined_hash(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _profiles(*payloads: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for payload in payloads:
        rows = payload.get("profiles")
        if not isinstance(rows, list):
            raise RuntimeError("Batch 2 profile evidence missing")
        for raw in rows:
            if not isinstance(raw, dict):
                raise RuntimeError("Batch 2 profile row invalid")
            profile_id = raw.get("profile_id")
            if not isinstance(profile_id, str) or profile_id in result:
                raise RuntimeError("Batch 2 profile id invalid/duplicate")
            result[profile_id] = cast(dict[str, Any], raw)
    return result


def _logical_pass(payload: dict[str, Any], expected_revision: str) -> bool:
    return (
        payload.get("status") == "PASS"
        and payload.get("source_revision") == expected_revision
        and payload.get("failed_acceptance", []) == []
    )


def _waivers_current(
    profiles: dict[str, dict[str, Any]],
    *,
    reviewed_at: datetime,
) -> bool:
    for report in profiles.values():
        security = report.get("security")
        if not isinstance(security, dict):
            return False
        waivers = security.get("waivers", [])
        if not isinstance(waivers, list):
            return False
        for raw in waivers:
            if not isinstance(raw, dict):
                return False
            expires_raw = raw.get("expires_at_utc")
            if not isinstance(expires_raw, str):
                return False
            expires = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
            if expires <= reviewed_at:
                return False
    return True


def review(
    *,
    batch1_windows: Path,
    batch1_linux: Path,
    batch2_windows: Path,
    batch2_linux: Path,
    batch2_four_profile: Path,
    batch3_formal_rc: Path,
    logical_equivalence: Path,
    immutable_release_logical: Path,
    replay_logical: Path,
    expected_revision: str,
) -> dict[str, Any]:
    authority = load_m5_qualification_authority(BASELINE)
    task_baseline = _json(TASK_BASELINE)
    task_rows = task_baseline.get("tasks")
    if not isinstance(task_rows, list) or task_baseline.get("task_count") != 23:
        raise RuntimeError("M5 task baseline is not exact 23")
    task_ids = tuple(str(cast(dict[str, object], row).get("task_id")) for row in task_rows)
    prior_ids = task_ids[:20]
    if task_ids[-3:] != ("M5-TST-005", "M5-TST-006", "M5-TST-007"):
        raise RuntimeError("M5 Batch 4 task order drift")

    b1w, b1l = _json(batch1_windows), _json(batch1_linux)
    b2w, b2l = _json(batch2_windows), _json(batch2_linux)
    four = _json(batch2_four_profile)
    rc = _json(batch3_formal_rc)
    logical = _json(logical_equivalence)
    immutable = _json(immutable_release_logical)
    replay = _json(replay_logical)

    for payload in (b1w, b1l, b2w, b2l, four, rc):
        if payload.get("status") != "PASS":
            raise RuntimeError("M5 prerequisite evidence is not PASS")
        if payload.get("source_revision") != expected_revision:
            raise RuntimeError("M5 prerequisite revision mismatch")

    expected_b1 = tuple(str(x) for x in b1w.get("task_ids", ()))
    if expected_b1 != task_ids[:6] or tuple(b1l.get("task_ids", ())) != expected_b1:
        raise RuntimeError("Batch 1 task inventory drift")
    if tuple(four.get("task_ids", ())) != task_ids[6:15]:
        raise RuntimeError("Batch 2 task inventory drift")
    if tuple(rc.get("task_ids", ())) != task_ids[15:20]:
        raise RuntimeError("Batch 3 task inventory drift")

    profiles = _profiles(b2w, b2l)
    mandatory = authority.mandatory_profile_ids
    if len(profiles) != len(mandatory) or set(profiles) != set(mandatory):
        raise RuntimeError("exact four-profile inventory required")
    ordered = [profiles[profile_id] for profile_id in mandatory]

    rc_refs = rc.get("candidate_package_refs")
    rc_status = rc.get("profile_status")
    if not isinstance(rc_refs, dict) or not isinstance(rc_status, dict):
        raise RuntimeError("formal RC profile/package evidence missing")

    package_refs_exact = True
    all_performance = True
    all_security = True
    all_package_lifecycle = True
    same_build = {str(report.get("semantic_build_version")) for report in ordered}
    for report in ordered:
        profile_id = str(report["profile_id"])
        package = cast(dict[str, Any], report.get("package", {}))
        rc_ref = rc_refs.get(profile_id)
        if not isinstance(rc_ref, dict):
            package_refs_exact = False
        else:
            package_refs_exact = package_refs_exact and (
                rc_ref.get("source_revision") == expected_revision
                and rc_ref.get("semantic_build_version")
                == report.get("semantic_build_version")
                and rc_ref.get("package_sha256") == package.get("package_sha256")
                and rc_ref.get("package_manifest_sha256")
                == package.get("package_manifest_sha256")
            )
        lifecycle = package.get("lifecycle", {})
        all_package_lifecycle = all_package_lifecycle and (
            isinstance(lifecycle, dict)
            and all(
                lifecycle.get(key) is True
                for key in (
                    "clean_install_pass",
                    "ready_start_pass",
                    "component_smoke_pass",
                    "graceful_stop_pass",
                    "uninstall_pass",
                    "no_residual_product_state",
                )
            )
        )
        performance = report.get("performance", {})
        security = report.get("security", {})
        all_performance = all_performance and (
            isinstance(performance, dict) and performance.get("status") == "PASS"
        )
        all_security = all_security and (
            isinstance(security, dict) and security.get("status") == "PASS"
        )

    categories = rc.get("evidence_categories")
    if not isinstance(categories, dict):
        raise RuntimeError("formal RC evidence categories missing")
    recovery_pass = all(
        isinstance(categories.get(name), dict)
        and cast(dict[str, Any], categories[name]).get("status") == "PASS"
        for name in ("UPGRADE_ROLLBACK", "BACKUP_RESTORE")
    )

    reviewed_at = datetime.now(UTC)
    acceptance = {
        "baseline_task_count_exact_23": len(task_ids) == 23,
        "prior_task_inventory_exact_20": prior_ids == task_ids[:20],
        "batch1_windows_linux_pass": b1w["status"] == b1l["status"] == "PASS",
        "batch2_four_profile_pass": four.get("failed_acceptance") == [],
        "batch3_formal_rc_pass": rc.get("status") == "PASS",
        "windows_linux_logical_equivalence_pass": _logical_pass(
            logical, expected_revision
        ),
        "immutable_release_logical_equivalence_pass": _logical_pass(
            immutable, expected_revision
        ),
        "replay_logical_equivalence_pass": _logical_pass(replay, expected_revision),
        "exact_four_profiles": (
            len(rc_status) == len(mandatory)
            and set(rc_status) == set(mandatory)
            and all(rc_status.get(profile_id) == "PASS" for profile_id in mandatory)
        ),
        "same_candidate_source_revision": all(
            report.get("source_revision") == expected_revision for report in ordered
        ),
        "same_semantic_build_version": len(same_build) == 1,
        "package_refs_exact": package_refs_exact,
        "all_package_lifecycle_pass": all_package_lifecycle,
        "all_performance_pass": all_performance,
        "all_security_pass": all_security,
        "upgrade_recovery_pass": recovery_pass,
        "all_waivers_unexpired_at_review_time": _waivers_current(
            profiles, reviewed_at=reviewed_at
        ),
        "db_schema_1_6_0": authority.db_schema_version == "1.6.0",
        "p1_only": authority.admitted_phases == ("P1",),
        "p2_p6_inactive": authority.excluded_phases
        == ("P2", "P3", "P4", "P5", "P6"),
        "formal_release_not_claimed": rc.get("formal_release_claimed") is False
        and rc.get("m5_exit_go_claimed") is False,
    }
    failed = sorted(key for key, value in acceptance.items() if value is not True)

    b1_hash = _combined_hash(batch1_windows, batch1_linux)
    b2_hash = _combined_hash(batch2_windows, batch2_linux, batch2_four_profile)
    b3_hash = _sha(batch3_formal_rc)
    task_hashes = {
        task_id: (
            b1_hash
            if index < 6
            else b2_hash
            if index < 15
            else b3_hash
        )
        for index, task_id in enumerate(prior_ids)
    }
    return {
        "schema": "TPAA_M5_TST_005_PARITY_V1",
        "task_id": TASK_ID,
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "implementation_complete": not failed,
        "task_complete": False,
        "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
        "source_revision": expected_revision,
        "semantic_build_version": next(iter(same_build)) if len(same_build) == 1 else None,
        "authority_sha256": authority.authority_sha256,
        "baseline_lock_sha256": authority.baseline_lock_sha256,
        "qualified_task_ids": list(task_ids[:21]),
        "upstream_task_evidence_hashes": task_hashes,
        "mandatory_profiles": list(mandatory),
        "profile_status": {profile_id: rc_status.get(profile_id) for profile_id in mandatory},
        "candidate_package_refs": rc_refs,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "reviewed_at_utc": reviewed_at.isoformat().replace("+00:00", "Z"),
        "scope": {
            "p1_only": True,
            "p2_p6_inactive": True,
            "db_schema_version": authority.db_schema_version,
            "shadow_schema_created": False,
            "formal_release_claimed": False,
            "m5_exit_go_claimed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch1-windows", type=Path, required=True)
    parser.add_argument("--batch1-linux", type=Path, required=True)
    parser.add_argument("--batch2-windows", type=Path, required=True)
    parser.add_argument("--batch2-linux", type=Path, required=True)
    parser.add_argument("--batch2-four-profile", type=Path, required=True)
    parser.add_argument("--batch3-formal-rc", type=Path, required=True)
    parser.add_argument("--logical-equivalence", type=Path, required=True)
    parser.add_argument("--immutable-release-logical", type=Path, required=True)
    parser.add_argument("--replay-logical", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = review(
            batch1_windows=args.batch1_windows,
            batch1_linux=args.batch1_linux,
            batch2_windows=args.batch2_windows,
            batch2_linux=args.batch2_linux,
            batch2_four_profile=args.batch2_four_profile,
            batch3_formal_rc=args.batch3_formal_rc,
            logical_equivalence=args.logical_equivalence,
            immutable_release_logical=args.immutable_release_logical,
            replay_logical=args.replay_logical,
            expected_revision=args.expected_revision,
        )
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M5_TST_005_PARITY_V1",
            "task_id": TASK_ID,
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "source_revision": args.expected_revision,
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
