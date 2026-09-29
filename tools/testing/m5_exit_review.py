#!/usr/bin/env python3
"""M5-TST-007 protected-main M5 Exit review and formal P1 release decision."""

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
    validate_m5_formal_claim_prerequisites,
    validate_release_signoffs,
)

BASELINE = ROOT / "baseline" / "CB-1.4.0"
TASK_BASELINE = ROOT / "docs" / "baseline" / "SDIB-1.4" / "M5_TASK_BASELINE.json"
TRACKING_ISSUE = 142
TASK_ID = "M5-TST-007"

SIGNOFF_PRINCIPALS = (
    {
        "role": "RELEASE_MANAGER",
        "actor_id": "TPAA_M5_FORMAL_RC_REVIEW_V1",
        "actor_kind": "GOVERNED_EVIDENCE_PRINCIPAL",
    },
    {
        "role": "INDEPENDENT_QA",
        "actor_id": "TPAA_M5_TST_005_PARITY_REVIEW_V1",
        "actor_kind": "GOVERNED_EVIDENCE_PRINCIPAL",
    },
    {
        "role": "SECURITY_APPROVER",
        "actor_id": "TPAA_M5_SECURITY_QUALIFICATION_V1",
        "actor_kind": "GOVERNED_EVIDENCE_PRINCIPAL",
    },
)


def _json(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path}: root must be object")
    return cast(dict[str, Any], value)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review(
    *,
    tst006_path: Path,
    formal_rc_path: Path,
    c3_issue_path: Path,
    expected_revision: str,
    event_name: str,
    git_ref: str,
) -> dict[str, Any]:
    authority = load_m5_qualification_authority(BASELINE)
    task_baseline = _json(TASK_BASELINE)
    rows = task_baseline.get("tasks")
    if not isinstance(rows, list) or task_baseline.get("task_count") != 23:
        raise RuntimeError("M5 task baseline is not exact 23")
    task_ids = tuple(str(cast(dict[str, object], row).get("task_id")) for row in rows)

    tst006 = _json(tst006_path)
    formal_rc = _json(formal_rc_path)
    c3_issue = _json(c3_issue_path)
    if tst006.get("status") != "PASS" or tst006.get("failed_acceptance") != []:
        raise RuntimeError("M5-TST-006 is not accepted")
    if (
        tst006.get("source_revision") != expected_revision
        or formal_rc.get("source_revision") != expected_revision
    ):
        raise RuntimeError("M5 Exit source revision mismatch")
    if c3_issue.get("number") != 136 or c3_issue.get("state") != "closed":
        raise RuntimeError("C3 issue #136 must remain closed")

    manifest = tst006.get("completed_rc_manifest")
    if not isinstance(manifest, dict):
        raise RuntimeError("completed RC manifest missing")
    required_categories = tuple(
        authority.formal_release_acceptance_profile["required_evidence_categories"]
    )
    categories = manifest.get("evidence_categories")
    if (
        not isinstance(categories, dict)
        or len(categories) != len(required_categories)
        or set(categories) != set(required_categories)
    ):
        raise RuntimeError("completed RC category inventory mismatch")
    if any(
        not isinstance(categories[name], dict)
        or cast(dict[str, Any], categories[name]).get("status") != "PASS"
        for name in required_categories
    ):
        raise RuntimeError("completed RC category is not PASS")

    upstream = tst006.get("upstream_task_evidence_hashes")
    if (
        not isinstance(upstream, dict)
        or len(upstream) != len(task_ids[:21])
        or set(upstream) != set(task_ids[:21])
    ):
        raise RuntimeError("M5-TST-006 task evidence inventory drift")
    if tuple(tst006.get("qualified_task_ids", ())) != task_ids[:22]:
        raise RuntimeError("M5-TST-006 qualified task inventory drift")

    signoffs = [dict(item) for item in SIGNOFF_PRINCIPALS]
    signoffs[0]["evidence_sha256"] = _sha(formal_rc_path)
    signoffs[1]["evidence_sha256"] = str(upstream["M5-TST-005"])
    security_category = cast(dict[str, Any], categories["SECURITY_VULNERABILITY_REPORT"])
    signoffs[2]["evidence_sha256"] = hashlib.sha256(
        json.dumps(
            security_category,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    validate_release_signoffs(authority, signoffs)

    protected_main = event_name == "push" and git_ref == "refs/heads/main"
    exact_manifest_accepted = (
        manifest.get("source_revision") == expected_revision
        and manifest.get("authority_sha256") == authority.authority_sha256
        and manifest.get("baseline_lock_sha256") == authority.baseline_lock_sha256
        and manifest.get("all_waivers_unexpired_at_release_time") is True
        and len(cast(dict[str, Any], manifest.get("profile_status", {})))
        == len(authority.mandatory_profile_ids)
        and set(cast(dict[str, Any], manifest.get("profile_status", {})))
        == set(authority.mandatory_profile_ids)
    )
    acceptance = {
        "baseline_task_count_exact_23": len(task_ids) == 23,
        "exact_21_upstream_task_hashes": (
            len(upstream) == len(task_ids[:21])
            and set(upstream) == set(task_ids[:21])
        ),
        "tst006_exact_revision_pass": tst006.get("source_revision") == expected_revision,
        "formal_rc_exact_revision_pass": formal_rc.get("source_revision")
        == expected_revision,
        "completed_rc_manifest_exact": exact_manifest_accepted,
        "all_evidence_categories_pass": all(
            cast(dict[str, Any], categories[name]).get("status") == "PASS"
            for name in required_categories
        ),
        "exact_four_profiles_pass": all(
            cast(dict[str, Any], manifest["profile_status"]).get(profile_id) == "PASS"
            for profile_id in authority.mandatory_profile_ids
        ),
        "three_distinct_governed_signoffs": len({row["actor_id"] for row in signoffs})
        == 3,
        "required_signoff_roles_exact": tuple(row["role"] for row in signoffs)
        == tuple(authority.formal_release_acceptance_profile["required_signoff_roles"]),
        "all_waivers_unexpired": manifest.get(
            "all_waivers_unexpired_at_release_time"
        )
        is True,
        "c3_issue_136_closed": True,
        "db_schema_1_6_0": authority.db_schema_version == "1.6.0",
        "p1_only": authority.admitted_phases == ("P1",),
        "p2_p6_inactive": authority.excluded_phases
        == ("P2", "P3", "P4", "P5", "P6"),
    }
    failed = sorted(key for key, value in acceptance.items() if value is not True)
    implementation_complete = not failed

    decision = (
        "GO"
        if implementation_complete and protected_main
        else "PENDING_PROTECTED_MAIN"
        if implementation_complete
        else "NO_GO"
    )
    formal_release_claimed = decision == "GO"
    if formal_release_claimed:
        validate_m5_formal_claim_prerequisites(
            authority,
            capability_phase="P1",
            m5_exit_decision=decision,
            exact_evidence_manifest_accepted=exact_manifest_accepted,
            candidate_source_revision=expected_revision,
            exit_source_revision=expected_revision,
        )

    task_hashes = {str(key): str(value) for key, value in upstream.items()}
    task_hashes["M5-TST-006"] = _sha(tst006_path)
    task_hashes["M5-TST-007"] = "SELF:TPAA_M5_EXIT_REVIEW_V1"
    acceptance["task_evidence_exact_23"] = (
        len(task_hashes) == len(task_ids) and set(task_hashes) == set(task_ids)
    )
    failed = sorted(key for key, value in acceptance.items() if value is not True)
    implementation_complete = not failed
    if not implementation_complete:
        decision = "NO_GO"
        formal_release_claimed = False

    task_acceptance = {task_id: implementation_complete for task_id in task_ids}
    task_complete = implementation_complete and protected_main
    return {
        "schema": "TPAA_M5_EXIT_REVIEW_V1",
        "task_id": TASK_ID,
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if implementation_complete else "FAIL",
        "decision": decision,
        "implementation_complete": implementation_complete,
        "task_complete": task_complete,
        "formal_completion_blocked_by_protected_main": (
            implementation_complete and not protected_main
        ),
        "protected_main_exact": protected_main,
        "source_revision": expected_revision,
        "task_count": 23,
        "task_ids": list(task_ids),
        "task_acceptance": task_acceptance,
        "task_evidence_hashes": task_hashes,
        "signoffs": signoffs,
        "signoff_mode": "GOVERNED_EVIDENCE_PRINCIPALS",
        "human_identity_claimed": False,
        "exact_evidence_manifest_accepted": exact_manifest_accepted,
        "formal_release_claimed": formal_release_claimed,
        "qualification": (
            "P1_M5_QUALIFIED"
            if formal_release_claimed
            else "M5_CANDIDATE_NOT_FORMALLY_QUALIFIED"
        ),
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "unresolved_risks": [] if not failed else [{"kind": "acceptance", "items": failed}],
        "scope": {
            "p1_only": True,
            "p2_p6_inactive": True,
            "db_schema_version": authority.db_schema_version,
            "shadow_schema_created": False,
            "protected_main_required_for_go": True,
            "formal_release_claimed": formal_release_claimed,
            "m5_exit_go_claimed": decision == "GO",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tst006", type=Path, required=True)
    parser.add_argument("--formal-rc", type=Path, required=True)
    parser.add_argument("--c3-issue", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--git-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = review(
            tst006_path=args.tst006,
            formal_rc_path=args.formal_rc,
            c3_issue_path=args.c3_issue,
            expected_revision=args.expected_revision,
            event_name=args.event_name,
            git_ref=args.git_ref,
        )
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M5_EXIT_REVIEW_V1",
            "task_id": TASK_ID,
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "decision": "NO_GO",
            "implementation_complete": False,
            "task_complete": False,
            "formal_release_claimed": False,
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
