"""PIQB B2 persistence/recovery state and qualification review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "baseline" / "PIQB-1.0"
TASK_BASELINE = BASE / "B2_TASK_BASELINE.json"
FIT_BASELINE = BASE / "B2_SCHEMA_PERSISTENCE_FIT.json"
STATE = BASE / "B2_IMPLEMENTATION_STATE.json"
SOURCE_B1_SHA = "1ae7fccd6b61f570e22b7622c74fe41a4a7fe6c8"
EXPECTED_TASKS = tuple(f"PIQB-B2-{index:03d}" for index in range(1, 9))
BLOCKED_STATES = frozenset({"PARTIAL_AUTHORITY_BLOCKED"})
COMPLETE_STATES = frozenset({"COMPLETE_CANDIDATE", "COMPLETE"})


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
) -> dict[str, object]:
    baseline = _json(TASK_BASELINE)
    fit = _json(FIT_BASELINE)
    state = _json(STATE)

    tasks = baseline.get("tasks")
    task_ids = tuple(
        item.get("task_id")
        for item in tasks
        if isinstance(tasks, list) and isinstance(item, dict)
    ) if isinstance(tasks, list) else ()

    task_state_raw = state.get("task_state")
    task_state = (
        cast(dict[str, Any], task_state_raw)
        if isinstance(task_state_raw, dict)
        else {}
    )
    recorded_task_ids = tuple(task_state)

    blocked_families = tuple(
        item.get("product_family")
        for item in fit.get("families", [])
        if isinstance(item, dict) and item.get("status") == "BLOCKED"
    )
    dependency_blocked_families = tuple(
        item.get("product_family")
        for item in fit.get("families", [])
        if isinstance(item, dict) and item.get("dependency_blockers")
    )
    authority_blocked = bool(blocked_families or dependency_blocked_families)

    ports = "\n".join(
        _text(path)
        for path in (
            "src/tpaa_application/m6_workspace.py",
            "src/tpaa_application/m7_workspace.py",
            "src/tpaa_application/m8_workspace.py",
            "src/tpaa_application/m9_workspace.py",
        )
    )
    publication = _text("src/tpaa_storage/product_publication.py")
    sqlite = _text("src/tpaa_storage/sqlite_product_repository.py")
    postgres = _text("src/tpaa_storage/postgres_product_repository.py")
    persistence = _text("src/tpaa_runtime/persistence.py")
    fit_gate = _text("src/tpaa_storage/persistence_fit.py")

    acceptance = {
        "b1_entry_exact": (
            baseline.get("source_b1_protected_main_sha") == SOURCE_B1_SHA
            and baseline.get("source_b1_qualification") == "PIQB_B1_QUALIFIED"
            and state.get("source_b1_protected_main_sha") == SOURCE_B1_SHA
        ),
        "task_inventory_exact_8": (
            baseline.get("task_count") == 8
            and task_ids == EXPECTED_TASKS
            and recorded_task_ids == EXPECTED_TASKS
        ),
        "db_schema_1_6_0_preserved": (
            baseline.get("db_schema_version") == "1.6.0"
            and fit.get("db_schema_version") == "1.6.0"
            and state.get("db_schema_version") == "1.6.0"
            and isinstance(baseline.get("scope"), dict)
            and baseline["scope"].get("no_db_schema_change") is True
            and baseline["scope"].get("no_shadow_schema") is True
        ),
        "authority_gap_truthfully_recorded": (
            authority_blocked
            and fit.get("authority_change_proposal_required") is True
            and fit.get("authority_change_proposal_issue") == 216
            and fit.get("authority_change_proposal_status")
            == "PROPOSED_NOT_ADOPTED"
            and state.get("authority_change_proposal_issue") == 216
            and state.get("authority_change_proposal_status")
            == "PROPOSED_NOT_ADOPTED"
            and state.get("b2_qualified") is False
        ),
        "repository_ports_engine_neutral": all(
            token in ports
            for token in (
                "class M6P2WorkspaceRepository(Protocol)",
                "class M7P3WorkspaceRepository(Protocol)",
                "class M8AssessmentRepository(Protocol)",
                "class M9P6Repository(Protocol)",
            )
        ),
        "durable_publication_protocol_present": all(
            token in publication
            for token in (
                "ProductPublicationCoordinator",
                "LocalSealedObjectFlow",
                "ProductPublicationLedger",
                "recover_registered_product_orphans",
                "recover_staging_orphans",
            )
        ),
        "sqlite_postgres_frozen_table_parity_present": all(
            token in sqlite and token in postgres
            for token in (
                "object_reference",
                "object_binding",
                "compute_job",
                "analysis_release",
                "release_scope_pointer",
                "exact_product",
                "referenced_object_uris",
            )
        ),
        "postgres_transaction_lock_present": (
            "pg_advisory_xact_lock" in postgres
        ),
        "production_fit_gate_precedes_publication": (
            "self.fit_gate.assert_production_allowed(request.product_family)"
            in persistence
            and "return self._publication.publish(request)" in persistence
            and "DEPENDENCY_BLOCKED" in fit_gate
        ),
        "recovery_contract_tests_present": (
            ROOT
            / "tests"
            / "unit"
            / "storage"
            / "test_piqb_b2_product_publication.py"
        ).is_file(),
        "restart_contract_tests_present": (
            ROOT
            / "tests"
            / "unit"
            / "storage"
            / "test_piqb_b2_sqlite_product_repository.py"
        ).is_file(),
        "parity_contract_tests_present": (
            ROOT
            / "tests"
            / "contract"
            / "test_piqb_b2_product_repository_parity.py"
        ).is_file(),
        "blocked_tasks_not_claimed_complete": all(
            not (
                isinstance(task_state.get(task), dict)
                and task_state[task].get("state") in COMPLETE_STATES
            )
            for task in ("PIQB-B2-002", "PIQB-B2-003", "PIQB-B2-008")
        ),
        "candidate_revision_exact": expected_revision == checked_out_revision,
        "required_jobs_exact": (
            required_jobs_success == 14 and required_jobs_total == 14
        ),
        "run_conclusion_success": run_conclusion == "success",
    }
    failed = sorted(key for key, ok in acceptance.items() if not ok)
    status = "PASS" if not failed else "FAIL"
    protected_main = event_name == "push" and git_ref == "refs/heads/main"

    all_tasks_complete = all(
        isinstance(task_state.get(task), dict)
        and task_state[task].get("state") in COMPLETE_STATES
        for task in EXPECTED_TASKS
    )
    implementation_complete = (
        status == "PASS" and all_tasks_complete and not authority_blocked
    )
    if status != "PASS":
        decision = "NO_GO"
    elif authority_blocked:
        decision = "BLOCKED_AUTHORITY_CHANGE"
    elif not all_tasks_complete:
        decision = "IN_PROGRESS"
    elif protected_main:
        decision = "GO"
    else:
        decision = "PENDING_PROTECTED_MAIN"

    task_projection = {
        task: (
            task_state[task].get("state")
            if isinstance(task_state.get(task), dict)
            else "MISSING"
        )
        for task in EXPECTED_TASKS
    }
    return {
        "schema": "TPAA_PIQB_B2_REVIEW_V1",
        "baseline": "PIQB-1.0",
        "source_b1_protected_main_sha": SOURCE_B1_SHA,
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
        "tasks": task_projection,
        "blocked_families": blocked_families,
        "dependency_blocked_families": dependency_blocked_families,
        "authority_change_proposal_issue": 216,
        "implementation_complete": implementation_complete,
        "formal_completion_blocked_by_authority_change": (
            status == "PASS" and authority_blocked
        ),
        "formal_completion_blocked_by_protected_main": (
            status == "PASS"
            and not authority_blocked
            and all_tasks_complete
            and not protected_main
        ),
        "persistence_recovery_qualified": (
            implementation_complete and protected_main
        ),
        "qualification": (
            "PIQB_B2_QUALIFIED"
            if implementation_complete and protected_main
            else "PIQB_B2_BLOCKED_AUTHORITY_CHANGE"
            if status == "PASS" and authority_blocked
            else "PIQB_B2_CANDIDATE"
            if status == "PASS" and all_tasks_complete
            else "PIQB_B2_IN_PROGRESS"
            if status == "PASS"
            else "PIQB_B2_NOT_QUALIFIED"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--checked-out-revision", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--git-ref", required=True)
    parser.add_argument("--run-conclusion", required=True)
    parser.add_argument("--required-jobs-success", required=True, type=int)
    parser.add_argument("--required-jobs-total", required=True, type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = review(
        expected_revision=args.expected_revision,
        checked_out_revision=args.checked_out_revision,
        event_name=args.event_name,
        git_ref=args.git_ref,
        run_conclusion=args.run_conclusion,
        required_jobs_success=args.required_jobs_success,
        required_jobs_total=args.required_jobs_total,
    )
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
