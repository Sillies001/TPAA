#!/usr/bin/env python3
"""Verify/activate the SDIB-1.0.1 M1 Entry candidate.

The static repository review may remain an admission candidate so the exact
post-merge main revision can be verified without a second governance-only
merge. A merged-main activation artifact is the machine evidence that changes
the runtime decision to M1_ADMITTED.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REVIEW = REPO_ROOT / "docs" / "reviews" / "M1_ENTRY_GATE_REVIEW.json"
DEFAULT_ROLES = REPO_ROOT / "docs" / "governance" / "M1_ROLE_ASSIGNMENTS.json"

EXPECTED_FROZEN = {
    "core_baseline": "CB-1.4.0",
    "db_schema_version": "1.6.0",
    "baseline_lock_sha256": "d6ebab2b5402cf81a0b5f73a2da4ed2aaa2d530bc7445c7f6132dcf7fa72224d",
    "dependency_lock_sha256": "302ab51a013c713af6ece61113526eb411f6edf302b70c7a924224701387257e",
    "p1_metric_catalog_sha256": "24ab6d06ced0b768ff16e4c945e778cc8fd2d3838be3ca30051ec8f8e0d7277d",
    "stage_authority_sha256": "52377c097342fd52ad7b10e771a85420f3dca24f0446d171ff285306b8245691",
    "dto_authority_sha256": "be9e83d18427c0a71d80df6ba2a56f7f611a059c749e1e163d9b5c0140b90e1c",
}


def _load(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError(f"JSON root must be object: {path}")
    return raw


def _assigned(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _conditions(review: dict[str, object]) -> dict[int, dict[str, object]]:
    raw = review.get("conditions")
    items = raw if isinstance(raw, list) else []
    result: dict[int, dict[str, object]] = {}
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("id"), int):
            result[int(item["id"])] = item
    return result


def _manifest_ok(
    payload: dict[str, object],
    *,
    source_revision: str,
    platform_profile: str,
) -> bool:
    return (
        payload.get("schema") == "TPAA_M1_ENTRY_BUILD_MANIFEST_V1"
        and payload.get("status") == "FROZEN_ENTRY_CANDIDATE"
        and payload.get("admission") == "M1_NOT_ADMITTED_BY_THIS_MANIFEST"
        and payload.get("source_revision") == source_revision
        and payload.get("platform_profile") == platform_profile
        and all(payload.get(key) == value for key, value in EXPECTED_FROZEN.items())
    )


def evaluate(
    *,
    mode: str,
    source_revision: str,
    review: dict[str, object],
    roles: dict[str, object],
    windows_manifest: dict[str, object],
    linux_manifest: dict[str, object],
) -> dict[str, object]:
    if mode not in {"blocked", "candidate", "activate"}:
        raise ValueError(f"unsupported mode: {mode}")
    if len(source_revision) != 40:
        raise ValueError("source revision must be a 40-character Git commit SHA")

    conditions = _conditions(review)
    assigned_roles_ok = (
        roles.get("schema") == "TPAA_M1_ROLE_ASSIGNMENTS_V1"
        and roles.get("status") == "ASSIGNED"
        and _assigned(roles.get("primary_ws_owner"))
        and _assigned(roles.get("golden_independent_reviewer"))
        and _assigned(roles.get("m1_exit_reviewer"))
        and _assigned(roles.get("golden_independence_attestation"))
    )
    unassigned_roles_ok = (
        roles.get("schema") == "TPAA_M1_ROLE_ASSIGNMENTS_V1"
        and roles.get("status") == "UNASSIGNED"
        and not _assigned(roles.get("primary_ws_owner"))
        and not _assigned(roles.get("golden_independent_reviewer"))
        and not _assigned(roles.get("m1_exit_reviewer"))
        and not _assigned(roles.get("golden_independence_attestation"))
    )

    if mode == "blocked":
        static_ok = (
            set(conditions) == set(range(1, 11))
            and all(
                conditions.get(index, {}).get("status") == "PASS"
                for index in (1, 2, 3, 4, 5, 6, 7, 9, 10)
            )
            and conditions.get(8, {}).get("status") == "BLOCKED_UNASSIGNED"
            and review.get("decision") == "M1_NOT_ADMITTED"
            and review.get("implementation_authorized") is False
        )
        roles_ok = unassigned_roles_ok
    else:
        static_ok = (
            set(conditions) == set(range(1, 11))
            and all(
                conditions.get(index, {}).get("status") == "PASS"
                for index in (1, 2, 3, 4, 5, 7, 8, 9, 10)
            )
            and conditions.get(6, {}).get("status") == "RUNTIME_VERIFY_REQUIRED"
            and review.get("decision") == "M1_ADMISSION_CANDIDATE"
            and review.get("implementation_authorized") is False
        )
        roles_ok = assigned_roles_ok

    windows_ok = _manifest_ok(
        windows_manifest,
        source_revision=source_revision,
        platform_profile="WINDOWS_DESKTOP_X64",
    )
    linux_ok = _manifest_ok(
        linux_manifest,
        source_revision=source_revision,
        platform_profile="LINUX_DESKTOP_X64",
    )

    checks = [
        {"check": "static_candidate", "status": "PASS" if static_ok else "FAIL"},
        {"check": "role_assignments", "status": "PASS" if roles_ok else "FAIL"},
        {"check": "windows_manifest", "status": "PASS" if windows_ok else "FAIL"},
        {"check": "linux_manifest", "status": "PASS" if linux_ok else "FAIL"},
    ]
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"

    if status == "PASS" and mode == "activate":
        decision = "M1_ADMITTED"
        implementation_authorized = True
        condition_6 = "PASS"
    elif status == "PASS" and mode == "candidate":
        decision = "M1_ADMISSION_CANDIDATE_VERIFIED"
        implementation_authorized = False
        condition_6 = "CANDIDATE_PASS"
    elif status == "PASS":
        decision = "M1_NOT_ADMITTED"
        implementation_authorized = False
        condition_6 = "PASS"
    else:
        decision = "M1_NOT_ADMITTED"
        implementation_authorized = False
        condition_6 = "FAIL"

    return {
        "schema": "TPAA_M1_ENTRY_ACTIVATION_V1",
        "status": status,
        "mode": mode,
        "source_revision": source_revision,
        "decision": decision,
        "implementation_authorized": implementation_authorized,
        "condition_6_runtime": condition_6,
        "conditions_passed_after_runtime_verification": (9 if mode == "blocked" else 10) if status == "PASS" else 9,
        "checks": checks,
        "roles": {
            "primary_ws_owner": roles.get("primary_ws_owner"),
            "golden_independent_reviewer": roles.get("golden_independent_reviewer"),
            "m1_exit_reviewer": roles.get("m1_exit_reviewer"),
            "golden_independence_attestation": roles.get("golden_independence_attestation"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("auto", "blocked", "candidate", "activate"), required=True)
    parser.add_argument("--event-name")
    parser.add_argument("--git-ref")
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--windows-manifest", type=Path, required=True)
    parser.add_argument("--linux-manifest", type=Path, required=True)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--roles", type=Path, default=DEFAULT_ROLES)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    mode = args.mode
    if mode == "auto":
        roles = _load(args.roles)
        roles_status = roles.get("status")
        if roles_status == "UNASSIGNED":
            mode = "blocked"
        elif roles_status == "ASSIGNED" and args.event_name == "push" and args.git_ref == "refs/heads/main":
            mode = "activate"
        elif roles_status == "ASSIGNED":
            mode = "candidate"
        else:
            mode = "blocked"
    else:
        roles = _load(args.roles)

    result = evaluate(
        mode=mode,
        source_revision=args.source_revision,
        review=_load(args.review),
        roles=roles,
        windows_manifest=_load(args.windows_manifest),
        linux_manifest=_load(args.linux_manifest),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
