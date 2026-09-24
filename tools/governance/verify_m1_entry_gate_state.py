#!/usr/bin/env python3
"""Verify the SDIB-1.0.1 M1 Entry Gate review state.

The verifier validates review/evidence consistency. A PASS from this verifier
does not mean M1 is admitted; the admission decision is read from the review
record and is allowed to remain M1_NOT_ADMITTED while a condition is blocked.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW = REPO_ROOT / "docs" / "reviews" / "M1_ENTRY_GATE_REVIEW.json"
ROLES = REPO_ROOT / "docs" / "governance" / "M1_ROLE_ASSIGNMENTS.json"

EXPECTED_FROZEN = {
    "core_baseline": "CB-1.4.0",
    "db_schema_version": "1.6.0",
    "baseline_lock_sha256": "9d96a7eb0ba2b1fb13b11d76943171f773fd42497df74bf79c01928cfa26e7fa",
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


def _check(code: str, ok: bool, detail: str) -> dict[str, str]:
    return {"check": code, "status": "PASS" if ok else "FAIL", "detail": detail}


def _assigned(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def verify() -> dict[str, object]:
    checks: list[dict[str, str]] = []
    review = _load(REVIEW)
    roles = _load(ROLES)

    checks.append(
        _check(
            "review_schema",
            review.get("schema") == "TPAA_M1_ENTRY_GATE_REVIEW_V1",
            str(review.get("schema")),
        )
    )
    checks.append(
        _check(
            "roles_schema",
            roles.get("schema") == "TPAA_M1_ROLE_ASSIGNMENTS_V1",
            str(roles.get("schema")),
        )
    )

    conditions_obj = review.get("conditions")
    conditions = conditions_obj if isinstance(conditions_obj, list) else []
    by_id: dict[int, dict[str, object]] = {}
    for item in conditions:
        if isinstance(item, dict) and isinstance(item.get("id"), int):
            by_id[int(item["id"])] = item
    checks.append(_check("condition_count", set(by_id) == set(range(1, 11)), f"ids={sorted(by_id)}"))

    evidence_revision = review.get("evidence_revision")
    evidence_run = review.get("evidence_run")
    run = evidence_run if isinstance(evidence_run, dict) else {}
    checks.append(
        _check(
            "evidence_revision_consistent",
            isinstance(evidence_revision, str)
            and len(evidence_revision) == 40
            and run.get("source_revision") == evidence_revision
            and run.get("source_revision_consistent") is True
            and run.get("status") == "PASS",
            str(evidence_revision),
        )
    )
    checks.append(
        _check(
            "logical_equivalence",
            run.get("logical_equivalence_status") == "PASS"
            and run.get("logical_equivalence_mismatches") == [],
            f"{run.get('logical_equivalence_status')} / {run.get('logical_equivalence_mismatches')}",
        )
    )

    manifests_obj = review.get("m1_entry_manifests")
    manifests = manifests_obj if isinstance(manifests_obj, dict) else {}
    manifest_source_revisions: set[str] = set()
    manifest_profiles: set[str] = set()
    manifests_ok = set(manifests) == {"windows", "linux"}
    for item in manifests.values():
        if not isinstance(item, dict):
            manifests_ok = False
            continue
        source_revision = item.get("source_revision")
        profile = item.get("platform_profile")
        if isinstance(source_revision, str):
            manifest_source_revisions.add(source_revision)
        if isinstance(profile, str):
            manifest_profiles.add(profile)
        manifests_ok = (
            manifests_ok
            and item.get("status") == "FROZEN_ENTRY_CANDIDATE"
            and item.get("admission") == "M1_NOT_ADMITTED_BY_THIS_MANIFEST"
            and all(item.get(key) == value for key, value in EXPECTED_FROZEN.items())
        )
    checks.append(
        _check(
            "entry_manifests",
            manifests_ok
            and manifest_source_revisions == {evidence_revision}
            and manifest_profiles == {"WINDOWS_DESKTOP_X64", "LINUX_DESKTOP_X64"},
            f"revisions={sorted(manifest_source_revisions)} profiles={sorted(manifest_profiles)}",
        )
    )

    primary = roles.get("primary_ws_owner")
    golden = roles.get("golden_independent_reviewer")
    exit_reviewer = roles.get("m1_exit_reviewer")
    attestation = roles.get("golden_independence_attestation")
    all_roles_assigned = (
        _assigned(primary)
        and _assigned(golden)
        and _assigned(exit_reviewer)
        and isinstance(attestation, str)
        and bool(attestation.strip())
    )

    condition8 = by_id.get(8, {})
    decision = review.get("decision")
    blockers = review.get("blocking_conditions")

    if all_roles_assigned:
        role_state_ok = roles.get("status") == "ASSIGNED" and condition8.get("status") == "PASS"
        if decision == "M1_ADMISSION_CANDIDATE":
            decision_ok = (
                blockers == ["MERGED_MAIN_RUNTIME_EVIDENCE"]
                and by_id.get(6, {}).get("status") == "RUNTIME_VERIFY_REQUIRED"
                and all(
                    by_id.get(idx, {}).get("status") == "PASS"
                    for idx in (1, 2, 3, 4, 5, 7, 8, 9, 10)
                )
                and review.get("pass_count") == 9
                and review.get("implementation_authorized") is False
            )
        else:
            decision_ok = (
                decision == "M1_ADMITTED"
                and blockers == []
                and all(by_id.get(idx, {}).get("status") == "PASS" for idx in range(1, 11))
                and review.get("pass_count") == 10
                and review.get("implementation_authorized") is True
            )
    else:
        role_state_ok = (
            roles.get("status") == "UNASSIGNED"
            and condition8.get("status") == "BLOCKED_UNASSIGNED"
        )
        decision_ok = (
            decision == "M1_NOT_ADMITTED"
            and blockers == [8]
            and all(by_id.get(idx, {}).get("status") == "PASS" for idx in (1,2,3,4,5,6,7,9,10))
            and review.get("pass_count") == 9
            and review.get("implementation_authorized") is False
        )

    checks.append(_check("role_state", role_state_ok, str(roles.get("status"))))
    checks.append(_check("decision_consistency", decision_ok, str(decision)))

    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return {
        "schema": "TPAA_M1_ENTRY_GATE_STATE_VERIFICATION_V1",
        "status": status,
        "decision": decision,
        "implementation_authorized": review.get("implementation_authorized"),
        "condition_8": condition8.get("status"),
        "checks": checks,
    }


def main() -> int:
    result = verify()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
