"""PIQB B4 unified API/security/observability qualification review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "baseline" / "PIQB-1.0"
TASK_BASELINE = BASE / "B4_TASK_BASELINE.json"
IMPLEMENTATION_STATE = BASE / "B4_IMPLEMENTATION_STATE.json"
PRODUCT_CONTRACT = BASE / "B4_PRODUCT_API_V1_CONTRACT.json"
SOURCE_B3_SHA = "08e223c8137eb261b43ed7c2ca3612e22770d8ba"
EXPECTED_TASKS = tuple(f"PIQB-B4-{index:03d}" for index in range(1, 9))


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be object")
    return cast(dict[str, Any], value)


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def review(
    *,
    expected_revision: str,
    checked_out_revision: str,
    event_name: str,
    git_ref: str,
    run_conclusion: str,
    required_jobs_success: int,
    required_jobs_total: int,
    qualification: dict[str, Any],
) -> dict[str, object]:
    baseline = _json(TASK_BASELINE)
    state = _json(IMPLEMENTATION_STATE)
    product = _json(PRODUCT_CONTRACT)
    tasks = baseline.get("tasks")
    task_ids = tuple(
        item.get("task_id")
        for item in tasks
        if isinstance(tasks, list) and isinstance(item, dict)
    ) if isinstance(tasks, list) else ()

    task_state = state.get("task_state")
    states = (
        tuple(task_state.get(task, {}).get("state") for task in EXPECTED_TASKS)
        if isinstance(task_state, dict)
        else ()
    )
    scope = baseline.get("scope")
    workflow = _text(".github/workflows/cross-platform-ci.yml")
    product_api = _text("src/tpaa_api/product_v1.py")
    unified = _text("src/tpaa_api/unified.py")
    audit_ledger = _text("src/tpaa_storage/audit_ledger.py")
    runtime_audit = _text("src/tpaa_runtime/security_audit.py")
    observability = _text("src/tpaa_runtime/observability.py")
    runtime_api = _text("src/tpaa_api/runtime.py")

    qualification_acceptance = qualification.get("acceptance")
    qualification_all_pass = (
        isinstance(qualification_acceptance, dict)
        and bool(qualification_acceptance)
        and all(value is True for value in qualification_acceptance.values())
    )
    routes = product.get("routes")
    invariants = product.get("invariants")

    acceptance = {
        "b3_entry_exact": (
            baseline.get("source_b3_protected_main_sha") == SOURCE_B3_SHA
            and baseline.get("source_b3_qualification") == "PIQB_B3_QUALIFIED"
            and baseline.get("source_b3_run_number") == 618
        ),
        "task_inventory_exact_8": (
            baseline.get("task_count") == 8
            and task_ids == EXPECTED_TASKS
        ),
        "all_tasks_complete_candidate": (
            len(states) == 8
            and all(item in {"COMPLETE_CANDIDATE", "COMPLETE"} for item in states)
            and state.get("candidate_complete") is True
        ),
        "formal_state_consistent": (
            (
                state.get("b4_qualified") is False
                and state.get("b5_blocked") is True
            )
            or (
                state.get("b4_qualified") is True
                and state.get("b5_blocked") is False
                and isinstance(state.get("protected_main_qualification"), dict)
                and state["protected_main_qualification"].get("protected_main_sha")
                == "7130978fc14c2714a9135de285a2c74aeaa33804"
                and state["protected_main_qualification"].get("run_number") == 624
                and state["protected_main_qualification"].get("required_jobs_success") == 14
                and state["protected_main_qualification"].get("qualification")
                == "PIQB_B4_QUALIFIED"
            )
        ),
        "db_1_9_no_authority_change": (
            baseline.get("db_schema_version") == "1.9.0"
            and isinstance(scope, dict)
            and scope.get("no_db_schema_change") is True
            and scope.get("no_shadow_schema") is True
            and scope.get("existing_audit_relation_required") == "audit.audit_log"
        ),
        "product_api_exact_contract": (
            product.get("schema") == "TPAA_PRODUCT_API_V1_CONTRACT_V1"
            and product.get("api_version") == "v1"
            and isinstance(routes, list)
            and len(routes) == 10
            and isinstance(invariants, dict)
            and invariants.get("exact_ids_only") is True
            and invariants.get("mutable_latest_routes_forbidden") is True
            and invariants.get("aliases_forbidden") is True
            and invariants.get("hidden_recomputation_forbidden") is True
            and "register_product_v1_routes" in unified
            and "UUID" in product_api
        ),
        "persistent_audit_db19_present": all(
            token in audit_ledger
            for token in (
                '"audit.audit_log"',
                "PersistentAuditLedger",
                "principal_key",
                "request_id",
                "actor_id",
            )
        ) and all(
            token in runtime_audit
            for token in (
                "SQLiteSecurityAuditSink",
                "PostgreSQLSecurityAuditSink",
                "AuditLogWrite",
            )
        ),
        "observability_explicit_and_secret_safe": (
            "ProductQualificationStatus" in observability
            and "ProductOperationalStatus" in observability
            and "structured_record(" in observability
            and '@app.get("/runtime/qualification")' in runtime_api
            and '@app.get("/runtime/observability")' in runtime_api
        ),
        "qualification_passed": (
            qualification.get("schema")
            == "TPAA_PIQB_B4_API_SECURITY_OBSERVABILITY_QUALIFICATION_V1"
            and qualification.get("source_revision") == expected_revision
            and qualification.get("status") == "PASS"
            and qualification.get("qualification_passed") is True
            and qualification.get("failed_acceptance") == []
            and qualification_all_pass
        ),
        "qualification_scope_exact": (
            isinstance(qualification.get("scope"), dict)
            and qualification["scope"].get("db_schema_version") == "1.9.0"
            and qualification["scope"].get("audit_relation") == "audit.audit_log"
            and qualification["scope"].get("real_sqlite_executed") is True
            and qualification["scope"].get("real_postgresql_executed") is True
            and qualification["scope"].get("shadow_schema_created") is False
            and qualification["scope"].get("required_job_topology_changed") is False
        ),
        "workflow_keeps_fourteen_job_topology": (
            "Execute PIQB B4 API security observability qualification" in workflow
            and "Review PIQB B4 unified API security and observability" in workflow
            and "\n  piqb-b4-review:" not in workflow
        ),
        "candidate_revision_exact": expected_revision == checked_out_revision,
        "required_jobs_exact": (
            required_jobs_success == 14 and required_jobs_total == 14
        ),
        "run_conclusion_success": run_conclusion == "success",
    }

    failed = sorted(key for key, ok in acceptance.items() if not ok)
    protected_main = event_name == "push" and git_ref == "refs/heads/main"
    status = "PASS" if not failed else "FAIL"
    decision = (
        "GO"
        if status == "PASS" and protected_main
        else "PENDING_PROTECTED_MAIN"
        if status == "PASS"
        else "NO_GO"
    )
    qualified = status == "PASS" and protected_main
    return {
        "schema": "TPAA_PIQB_B4_REVIEW_V1",
        "baseline": "PIQB-1.0",
        "source_b3_protected_main_sha": SOURCE_B3_SHA,
        "expected_revision": expected_revision,
        "checked_out_revision": checked_out_revision,
        "event_name": event_name,
        "git_ref": git_ref,
        "required_jobs_success": required_jobs_success,
        "required_jobs_total": required_jobs_total,
        "status": status,
        "decision": decision,
        "failed_acceptance": failed,
        "acceptance": acceptance,
        "tasks": {task: status == "PASS" for task in EXPECTED_TASKS},
        "implementation_complete": status == "PASS",
        "formal_completion_blocked_by_protected_main": not qualified,
        "api_security_observability_qualified": qualified,
        "qualification": (
            "PIQB_B4_QUALIFIED"
            if qualified
            else "PIQB_B4_CANDIDATE"
            if status == "PASS"
            else "PIQB_B4_NOT_QUALIFIED"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qualification", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--checked-out-revision", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--git-ref", required=True)
    parser.add_argument("--run-conclusion", required=True)
    parser.add_argument("--required-jobs-success", required=True, type=int)
    parser.add_argument("--required-jobs-total", required=True, type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = review(
        expected_revision=args.expected_revision,
        checked_out_revision=args.checked_out_revision,
        event_name=args.event_name,
        git_ref=args.git_ref,
        run_conclusion=args.run_conclusion,
        required_jobs_success=args.required_jobs_success,
        required_jobs_total=args.required_jobs_total,
        qualification=_json(args.qualification),
    )
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
