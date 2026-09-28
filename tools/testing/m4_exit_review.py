#!/usr/bin/env python3
"""M4-TST-006 cold-start and protected-main M4 Exit review."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "docs" / "baseline" / "SDIB-1.3" / "M4_TASK_BASELINE.json"
LOCK = ROOT / "baseline" / "CB-1.4.0" / "BASELINE_LOCK.json"
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "M4_LONGITUDINAL_DEBRIEF_AUTHORITY.json"
TRACKING_ISSUE = 129
TASK_ID = "M4-TST-006"
EXPECTED_TASKS = (
    "M4-GOV-001","M4-GOV-002","M4-LONG-001","M4-LONG-002","M4-LONG-003","M4-TST-001",
    "M4-LONG-004","M4-LONG-005","M4-OBS-001","M4-OBS-002","M4-OBS-003","M4-TST-002",
    "M4-API-001","M4-API-002","M4-GUI-001","M4-GUI-002","M4-GUI-003","M4-TST-003",
    "M4-TST-004","M4-TST-005","M4-TST-006",
)


def _load(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: root must be object")
    return cast(dict[str, object], raw)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cold_start(
    payload: dict[str, object],
    *,
    platform: str,
    revision: str,
    postgres: bool,
) -> bool:
    base = (
        payload.get("schema") == "TPAA_M0_COLD_START_V2"
        and payload.get("status") == "PASS"
        and payload.get("source_revision") == revision
        and payload.get("platform") == platform
        and payload.get("clean_clone") is True
        and payload.get("uv_sync_locked") is True
        and payload.get("m0_gates") == "PASS"
        and payload.get("worktree_clean") is True
    )
    if not base:
        return False
    if postgres:
        return (
            payload.get("postgres_bootstrap") == "PASS"
            and payload.get("postgres_repository") == "PASS"
        )
    return True


def review(
    *,
    platform_root: Path,
    qualification_path: Path,
    postgres_cold_start_path: Path,
    c3_issue_path: Path,
    expected_revision: str,
    event_name: str,
    git_ref: str,
) -> dict[str, object]:
    if len(expected_revision) != 40:
        raise ValueError("expected_revision must be exact SHA")

    baseline = _load(BASELINE)
    tasks_raw = baseline.get("tasks")
    if not isinstance(tasks_raw, list):
        raise ValueError("M4 task baseline missing tasks")
    baseline_ids = tuple(str(cast(dict[str, object], row).get("task_id")) for row in tasks_raw)

    lock = _load(LOCK)
    artifacts = lock.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("Baseline Lock artifacts missing")
    authority_lock = next(
        (
            cast(dict[str, object], row)
            for row in artifacts
            if isinstance(row, dict)
            and row.get("file") == "M4_LONGITUDINAL_DEBRIEF_AUTHORITY.json"
        ),
        None,
    )
    authority = _load(AUTHORITY)
    scope = cast(dict[str, object], authority.get("scope", {}))
    c3_issue = _load(c3_issue_path)
    qualification = _load(qualification_path)
    product = cast(dict[str, object], qualification.get("logical_product", {}))
    qualified_ids = tuple(str(x) for x in cast(list[object], product.get("qualified_task_ids", [])))
    eligible = tuple(str(x) for x in cast(list[object], product.get("eligible_codes", [])))
    excluded = tuple(str(x) for x in cast(list[object], product.get("excluded_codes", [])))
    upstream_hashes = cast(dict[str, object], product.get("task_evidence_hashes", {}))

    windows = _load(platform_root / "devops" / "windows" / "cold-start.json")
    linux = _load(platform_root / "devops" / "linux" / "cold-start.json")
    postgres = _load(postgres_cold_start_path)

    qualification_complete = (
        qualification.get("schema") == "TPAA_M4_TST_005_STORAGE_QUALIFICATION_V1"
        and qualification.get("task_id") == "M4-TST-005"
        and qualification.get("status") == "PASS"
        and qualification.get("implementation_complete") is True
        and qualification.get("source_revision") == expected_revision
        and qualification.get("failed_acceptance") == []
        and isinstance(qualification.get("acceptance"), dict)
        and bool(cast(dict[str, object], qualification["acceptance"]))
        and all(v is True for v in cast(dict[str, object], qualification["acceptance"]).values())
    )

    expected_pre_tst006 = EXPECTED_TASKS[:-1]
    source_hash_keys = set(upstream_hashes)
    acceptance = {
        "baseline_task_count_exact_21": baseline.get("task_count") == 21 and len(baseline_ids) == 21,
        "baseline_task_ids_exact": baseline_ids == EXPECTED_TASKS,
        "c3_authority_locked_exact": (
            authority_lock is not None
            and authority_lock.get("sha256") == _sha(AUTHORITY)
            and authority.get("authority_id") == "M4_LONGITUDINAL_DEBRIEF_AUTHORITY"
        ),
        "c3_issue_122_closed": c3_issue.get("number") == 122 and c3_issue.get("state") == "closed",
        "p4_p5_inactive": scope.get("p4_p5_human_team_assessment_active") is False,
        "m5_formal_product_qualification_not_claimed": scope.get("m5_formal_product_qualification_claimed") is False,
        "tst005_exact_revision_complete": qualification_complete,
        "qualified_task_inventory_exact_20": qualified_ids == expected_pre_tst006,
        "upstream_task_evidence_hashes_exact_19": (
            source_hash_keys == set(EXPECTED_TASKS[:19])
            and all(isinstance(v, str) and len(v) == 64 for v in upstream_hashes.values())
        ),
        "eligible_exact_104": len(eligible) == 104 and len(set(eligible)) == 104,
        "excluded_exact_12": len(excluded) == 12 and len(set(excluded)) == 12,
        "eligible_excluded_disjoint": set(eligible).isdisjoint(excluded),
        "windows_clean_reconstruction_pass": _cold_start(
            windows, platform="windows", revision=expected_revision, postgres=False
        ),
        "linux_clean_reconstruction_pass": _cold_start(
            linux, platform="linux", revision=expected_revision, postgres=False
        ),
        "postgres_clean_reconstruction_pass": _cold_start(
            postgres, platform="linux", revision=expected_revision, postgres=True
        ),
        "upstream_failed_acceptance_empty": qualification.get("failed_acceptance") == [],
    }
    failed = sorted(k for k, v in acceptance.items() if v is not True)
    implementation_complete = not failed

    task_acceptance = {
        task: qualification_complete for task in EXPECTED_TASKS[:-1]
    }
    task_acceptance[TASK_ID] = implementation_complete
    qualification_hash = _sha(qualification_path)
    task_hashes = {
        task: str(upstream_hashes[task])
        for task in EXPECTED_TASKS[:19]
    }
    task_hashes["M4-TST-005"] = qualification_hash
    task_hashes[TASK_ID] = "SELF:TPAA_M4_EXIT_REVIEW_V1"

    acceptance["task_evidence_exact_21"] = (
        tuple(task_acceptance) == EXPECTED_TASKS
        and len(task_acceptance) == 21
        and all(task_acceptance.values())
        and tuple(task_hashes) == EXPECTED_TASKS
    )
    failed = sorted(k for k, v in acceptance.items() if v is not True)
    implementation_complete = not failed
    task_acceptance[TASK_ID] = implementation_complete

    protected_main = event_name == "push" and git_ref == "refs/heads/main"
    task_complete = implementation_complete and protected_main
    decision = (
        "GO" if task_complete
        else "PENDING_PROTECTED_MAIN" if implementation_complete
        else "NO_GO"
    )
    return {
        "schema": "TPAA_M4_EXIT_REVIEW_V1",
        "task_id": TASK_ID,
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if implementation_complete else "FAIL",
        "decision": decision,
        "implementation_complete": implementation_complete,
        "task_complete": task_complete,
        "formal_completion_blocked_by_protected_main": implementation_complete and not protected_main,
        "protected_main_exact": protected_main,
        "source_revision": expected_revision,
        "task_count": 21,
        "task_ids": list(EXPECTED_TASKS),
        "task_acceptance": task_acceptance,
        "task_evidence_hashes": task_hashes,
        "eligible_metric_codes": list(eligible),
        "excluded_metric_codes": list(excluded),
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "unresolved_risks": [] if not failed else [{"kind": "acceptance", "items": failed}],
        "scope": {
            "m4_exit_review_only": True,
            "clean_source_baseline_reconstruction_executed": True,
            "windows_linux_exact_revision_evidence_reviewed": True,
            "sqlite_postgresql_longitudinal_membership_parity_reused_from_tst005": True,
            "exact_104_12_qualified": True,
            "c3_issue_122_required_closed": True,
            "p4_p5_human_team_assessment_active": False,
            "m5_formal_product_qualification_claimed": False,
            "protected_main_required_for_go": True,
            "db_schema_version": "1.6.0",
            "shadow_schema_created": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-artifact-root", type=Path, required=True)
    parser.add_argument("--qualification", type=Path, required=True)
    parser.add_argument("--postgres-cold-start", type=Path, required=True)
    parser.add_argument("--c3-issue", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--git-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = review(
            platform_root=args.platform_artifact_root,
            qualification_path=args.qualification,
            postgres_cold_start_path=args.postgres_cold_start,
            c3_issue_path=args.c3_issue,
            expected_revision=args.expected_revision,
            event_name=args.event_name,
            git_ref=args.git_ref,
        )
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M4_EXIT_REVIEW_V1",
            "task_id": TASK_ID,
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "decision": "NO_GO",
            "implementation_complete": False,
            "task_complete": False,
            "source_revision": args.expected_revision,
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
