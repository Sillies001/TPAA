#!/usr/bin/env python3
"""Verify the published SDIB-1.0.1 M0 48-task closure review.

This verifier checks repository-local integrity of the closure record. External
GitHub hosting controls and historical Actions artifacts are evidence recorded
by the review and are not re-fetched by this offline gate.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW = REPO_ROOT / "docs" / "reviews" / "M0_SDIB-1.0.1_DELTA_CLOSURE.json"

EXPECTED_TASK_IDS = (
    "M0-CORE-001",
    "M0-CORE-002",
    "M0-CORE-003",
    "M0-CORE-004",
    "M0-CORE-005",
    "M0-CORE-006",
    "M0-STO-001",
    "M0-STO-002",
    "M0-STO-003",
    "M0-STO-004",
    "M0-STO-005",
    "M0-STO-006",
    "M0-STO-007",
    "M0-API-001",
    "M0-API-002",
    "M0-API-003",
    "M0-API-004",
    "M0-API-005",
    "M0-GUI-001",
    "M0-GUI-002",
    "M0-GUI-003",
    "M0-GUI-004",
    "M0-TST-001",
    "M0-TST-002",
    "M0-TST-003",
    "M0-TST-004",
    "M0-TST-005",
    "M0-TST-006",
    "M0-PLAT-001",
    "M0-PLAT-002",
    "M0-PLAT-003",
    "M0-PLAT-004",
    "M0-PLAT-005",
    "M0-SEC-001",
    "M0-SEC-002",
    "M0-SEC-003",
    "M0-SEC-004",
    "M0-DEV-000",
    "M0-DEV-001",
    "M0-DEV-002",
    "M0-DEV-003",
    "M0-DEV-004",
    "M0-DEV-005",
    "M0-DEV-006",
    "M0-GOV-001",
    "M0-GOV-002",
    "M0-GOV-003",
    "M0-GOV-004",
)

EXPECTED_REQUIRED_CHECKS = {
    "M0 windows",
    "M0 linux",
    "M0 Exit PostgreSQL",
    "M0 logical equivalence",
    "M0 Exit Review",
}

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")


def _check(code: str, ok: bool, detail: str) -> dict[str, str]:
    return {"check": code, "status": "PASS" if ok else "FAIL", "detail": detail}


def verify() -> dict[str, object]:
    checks: list[dict[str, str]] = []
    try:
        payload = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "schema": "TPAA_M0_DELTA_CLOSURE_VERIFICATION_V1",
            "status": "FAIL",
            "checks": [_check("review_load", False, str(exc))],
        }

    checks.append(
        _check(
            "schema",
            payload.get("schema") == "TPAA_M0_SDIB_1_0_1_DELTA_CLOSURE_REVIEW_V1",
            str(payload.get("schema")),
        )
    )
    checks.append(_check("sdib", payload.get("sdib") == "SDIB-1.0.1", str(payload.get("sdib"))))
    checks.append(_check("decision", payload.get("decision") == "GO", str(payload.get("decision"))))

    tasks = payload.get("tasks")
    task_records = tasks if isinstance(tasks, list) else []
    task_ids = [item.get("task_id") for item in task_records if isinstance(item, dict)]
    checks.append(_check("task_count", len(task_records) == 48, f"count={len(task_records)}"))
    checks.append(_check("task_ids_unique", len(set(task_ids)) == 48, f"unique={len(set(task_ids))}"))
    checks.append(
        _check(
            "task_ids_exact",
            set(task_ids) == set(EXPECTED_TASK_IDS),
            f"expected={len(EXPECTED_TASK_IDS)} actual={len(set(task_ids))}",
        )
    )
    checks.append(
        _check(
            "all_tasks_closed",
            all(
                isinstance(item, dict)
                and item.get("status") == "CLOSED"
                and isinstance(item.get("evidence"), str)
                and bool(item["evidence"].strip())
                for item in task_records
            ),
            "every task must be CLOSED with non-empty evidence",
        )
    )
    checks.append(_check("declared_task_count", payload.get("task_count") == 48, str(payload.get("task_count"))))
    checks.append(
        _check(
            "declared_closed_count",
            payload.get("closed_task_count") == 48,
            str(payload.get("closed_task_count")),
        )
    )

    evidence_revision = payload.get("evidence_revision")
    checks.append(
        _check(
            "evidence_revision",
            isinstance(evidence_revision, str) and bool(SHA40.fullmatch(evidence_revision)),
            str(evidence_revision),
        )
    )

    historical = payload.get("historical_m0_baseline")
    historical_ok = (
        isinstance(historical, dict)
        and historical.get("tag") == "M0_IMPLEMENTATION_BASELINE"
        and historical.get("target_revision") == "ee54e8500381e62a53e1f2352d485ed11892c9d6"
        and historical.get("tag_compare_status") == "identical"
        and historical.get("original_exit_decision") == "GO"
    )
    checks.append(_check("historical_baseline", historical_ok, "historical tag/Exit identity"))

    run = payload.get("sdib_1_0_1_merged_main_evidence")
    run_ok = (
        isinstance(run, dict)
        and run.get("run_number") == 37
        and run.get("status") == "PASS"
        and run.get("source_revision") == evidence_revision
        and run.get("source_revision_consistent") is True
        and run.get("exit_gate_pass_count") == 14
        and run.get("exit_gate_count") == 14
        and run.get("logical_equivalence_status") == "PASS"
        and run.get("logical_equivalence_mismatches") == []
    )
    checks.append(_check("run37_summary", run_ok, "Run #37 merged-main evidence"))

    artifacts = run.get("artifacts") if isinstance(run, dict) else None
    artifact_ok = isinstance(artifacts, dict) and len(artifacts) == 5
    if artifact_ok:
        for item in artifacts.values():
            artifact_ok = (
                artifact_ok
                and isinstance(item, dict)
                and isinstance(item.get("id"), int)
                and isinstance(item.get("sha256"), str)
                and bool(SHA64.fullmatch(item["sha256"]))
            )
    checks.append(_check("artifact_identities", artifact_ok, "five artifacts with SHA-256 identities"))

    hosting = payload.get("m0_dev_000_external_hosting_evidence")
    required_checks = hosting.get("required_checks") if isinstance(hosting, dict) else None
    hosting_ok = (
        isinstance(hosting, dict)
        and hosting.get("repository_visibility") == "public"
        and hosting.get("main_protected") is True
        and isinstance(required_checks, list)
        and set(required_checks) == EXPECTED_REQUIRED_CHECKS
        and hosting.get("closure_pr") == 9
        and hosting.get("closure_pr_run") == 36
        and hosting.get("merged_main_run") == 37
    )
    checks.append(_check("m0_dev_000_hosting_record", hosting_ok, "protected main + required checks + PR evidence"))

    transition = payload.get("transition")
    transition_ok = (
        isinstance(transition, dict)
        and transition.get("m0_48_work_packages") == "CLOSED"
        and transition.get("m1_entry") == "NOT_EVALUATED_BY_THIS_REVIEW"
        and transition.get("m1_implementation") == "NOT_STARTED"
    )
    checks.append(_check("transition_boundary", transition_ok, "M0 closure does not imply M1 admission"))

    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return {
        "schema": "TPAA_M0_DELTA_CLOSURE_VERIFICATION_V1",
        "status": status,
        "task_count": len(task_records),
        "checks": checks,
    }


def main() -> int:
    evidence = verify()
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
