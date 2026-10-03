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
AUTHORITY_REBASE = BASE / "B2_AUTHORITY_REBASE.json"
CURRENT_ADOPTION = BASE / "ACP_219_DB_1_8_0_ADOPTION.json"
HISTORICAL_ADOPTION = BASE / "ACP_216_DB_1_7_0_ADOPTION.json"
LOCK = ROOT / "baseline" / "CB-1.4.0" / "BASELINE_LOCK.json"
SOURCE_B1_SHA = "1ae7fccd6b61f570e22b7622c74fe41a4a7fe6c8"
ADOPTED_MAIN_SHA = "a17eb1e5a0b961c7c555c6d900839df47165e245"
ADOPTION_RUN = 583
EXPECTED_TASKS = tuple(f"PIQB-B2-{index:03d}" for index in range(1, 9))
COMPLETE_STATES = frozenset({"COMPLETE_CANDIDATE", "COMPLETE"})
IN_PROGRESS_STATES = frozenset({"IN_PROGRESS_DB_1_8_ADAPTERS"})


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
    rebase = _json(AUTHORITY_REBASE)
    current_adoption = _json(CURRENT_ADOPTION)
    historical_adoption = _json(HISTORICAL_ADOPTION)
    lock = _json(LOCK)
    tasks = baseline.get("tasks")
    task_ids = (
        tuple(item.get("task_id") for item in tasks if isinstance(item, dict))
        if isinstance(tasks, list)
        else ()
    )
    raw_state = state.get("task_state")
    task_state = cast(dict[str, Any], raw_state) if isinstance(raw_state, dict) else {}
    historical_blocked = tuple(
        item.get("product_family")
        for item in fit.get("families", [])
        if isinstance(item, dict) and item.get("status") == "BLOCKED"
    )
    historical_dependency = tuple(
        item.get("product_family")
        for item in fit.get("families", [])
        if isinstance(item, dict) and item.get("dependency_blockers")
    )
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
    workflow = _text(".github/workflows/cross-platform-ci.yml")
    live_postgres = _text("tools/testing/piqb_b2_postgres_product_persistence.py")
    p4_p5_adapter = _text("src/tpaa_application/p4_p5_persistence.py")
    p6_adapter = _text("src/tpaa_application/p6_persistence.py")
    live_p4_p5 = _text("tools/testing/piqb_b2_postgres_p4_p5_persistence.py")
    lock_baseline = lock.get("baseline")
    adopted = rebase.get("adopted_authority")
    lineage = rebase.get("authority_lineage")
    historical_fit = rebase.get("historical_fit_audit")
    state_adoption = state.get("authority_adoption")

    historical_1_7 = (
        isinstance(lineage, list)
        and any(
            isinstance(item, dict)
            and item.get("proposal_id") == "ACP-216"
            and item.get("db_schema_version") == "1.7.0"
            and item.get("protected_main_sha")
            == "d5be58189d7fbd81f7fb3e49506eb0a61544db46"
            and item.get("qualification") == "ACP216_DB_1_7_0_ADOPTED"
            and item.get("historical") is True
            for item in lineage
        )
        and historical_adoption.get("target_db_schema_version") == "1.7.0"
    )

    acceptance = {
        "b1_entry_exact": (
            baseline.get("source_b1_protected_main_sha") == SOURCE_B1_SHA
            and baseline.get("source_b1_qualification") == "PIQB_B1_QUALIFIED"
            and state.get("source_b1_protected_main_sha") == SOURCE_B1_SHA
        ),
        "task_inventory_exact_8": (
            baseline.get("task_count") == 8
            and task_ids == EXPECTED_TASKS
            and tuple(task_state) == EXPECTED_TASKS
        ),
        "pre_adoption_fit_audit_preserved": (
            baseline.get("db_schema_version") == "1.6.0"
            and fit.get("db_schema_version") == "1.6.0"
            and fit.get("authority_change_proposal_status") == "PROPOSED_NOT_ADOPTED"
            and isinstance(historical_fit, dict)
            and historical_fit.get("preserved_as_pre_adoption_evidence") is True
        ),
        "historical_db_1_7_adoption_preserved": historical_1_7,
        "db_schema_1_8_authority_adopted": (
            state.get("db_schema_version") == "1.8.0"
            and state.get("authority_change_proposal_issue") == 219
            and state.get("authority_change_proposal_status") == "ADOPTED_PROTECTED_MAIN"
            and isinstance(state_adoption, dict)
            and state_adoption.get("protected_main_sha") == ADOPTED_MAIN_SHA
            and state_adoption.get("run_number") == ADOPTION_RUN
            and state_adoption.get("qualification") == "ACP219_DB_1_8_0_ADOPTED"
            and isinstance(adopted, dict)
            and adopted.get("proposal_id") == "ACP-219"
            and adopted.get("db_schema_version") == "1.8.0"
            and adopted.get("protected_main_sha") == ADOPTED_MAIN_SHA
            and adopted.get("run_number") == ADOPTION_RUN
            and adopted.get("qualification") == "ACP219_DB_1_8_0_ADOPTED"
            and current_adoption.get("target_db_schema_version") == "1.8.0"
            and isinstance(lock_baseline, dict)
            and lock_baseline.get("db_schema") == "1.8.0"
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
        "sqlite_postgres_canonical_table_parity_present": all(
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
        "postgres_transaction_lock_present": "pg_advisory_xact_lock" in postgres,
        "production_fit_gate_precedes_publication": (
            "self.fit_gate.assert_production_allowed(request.product_family)"
            in persistence
            and "return self._publication.publish(request)" in persistence
            and "DEPENDENCY_BLOCKED" in fit_gate
        ),
        "recovery_contract_tests_present": (
            ROOT / "tests/unit/storage/test_piqb_b2_product_publication.py"
        ).is_file(),
        "restart_contract_tests_present": (
            ROOT / "tests/unit/storage/test_piqb_b2_sqlite_product_repository.py"
        ).is_file(),
        "parity_contract_tests_present": (
            ROOT / "tests/contract/test_piqb_b2_product_repository_parity.py"
        ).is_file(),
        "real_postgres_restart_parity_gate_present": (
            isinstance(task_state.get("PIQB-B2-006"), dict)
            and task_state["PIQB-B2-006"].get("state") in IN_PROGRESS_STATES
            and isinstance(task_state.get("PIQB-B2-008"), dict)
            and task_state["PIQB-B2-008"].get("state") in IN_PROGRESS_STATES
            and all(
                token in workflow
                for token in (
                    "Execute PIQB B2 PostgreSQL restart/parity qualification",
                    "piqb_b2_postgres_product_persistence.py",
                    "evidence/piqb-b2/postgres-product-persistence.json",
                )
            )
            and all(
                token in live_postgres
                for token in (
                    "build_desktop_persistence",
                    "build_service_persistence",
                    "PUBLISH_CAS_CONFLICT",
                    "ADOPTED_PROTECTED_MAIN",
                    "current_db_1_8",
                    "shadow_schema_created",
                )
            )
        ),
        "p4_p5_exact_adapter_present": all(
            token in p4_p5_adapter
            for token in (
                "P4P5PersistenceRepository",
                "assessment.actor_assessment_machine_evidence_ref",
                "assessment.mission_assessment_objective_ref",
                "P4_P5_IMMUTABLE_CONFLICT",
            )
        ),
        "real_postgres_p4_p5_gate_present": (
            "Execute PIQB B2 P4/P5 real PostgreSQL exact persistence qualification"
            in workflow
            and "piqb_b2_postgres_p4_p5_persistence.py" in workflow
            and all(
                token in live_p4_p5
                for token in (
                    "PostgreSQLServiceUnitOfWork",
                    "SQLiteDesktopUnitOfWork",
                    "ordered_machine_evidence_refs_preserved",
                    "ordered_objective_refs_preserved",
                    "P4_P5_IMMUTABLE_CONFLICT",
                )
            )
        ),
        "p6_durable_substrate_present": all(
            token in p6_adapter
            for token in (
                "P6PersistenceRepository",
                "register_input",
                "register_model_build",
                "register_forecast_request",
                "register_counterfactual_request",
                "P6_MODEL_BUILD_DEPENDENCY_BLOCKED",
                "registry.dataset_snapshot",
                "capability.p6_model_revision",
                "intelligence.forecast_request",
                "intelligence.counterfactual_request",
            )
        ),
        "adapter_tasks_not_prematurely_complete": all(
            isinstance(task_state.get(task), dict)
            and task_state[task].get("state") in IN_PROGRESS_STATES
            for task in ("PIQB-B2-002", "PIQB-B2-003", "PIQB-B2-006", "PIQB-B2-008")
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
    implementation_complete = status == "PASS" and all_tasks_complete
    if status != "PASS":
        decision = "NO_GO"
    elif not all_tasks_complete:
        decision = "IN_PROGRESS"
    elif protected_main:
        decision = "GO"
    else:
        decision = "PENDING_PROTECTED_MAIN"
    if implementation_complete and protected_main:
        qualification = "PIQB_B2_QUALIFIED"
    elif status == "PASS" and all_tasks_complete:
        qualification = "PIQB_B2_CANDIDATE"
    elif status == "PASS":
        qualification = "PIQB_B2_IN_PROGRESS"
    else:
        qualification = "PIQB_B2_NOT_QUALIFIED"
    return {
        "schema": "TPAA_PIQB_B2_REVIEW_V1",
        "baseline": "PIQB-1.0",
        "source_b1_protected_main_sha": SOURCE_B1_SHA,
        "adopted_db_authority_protected_main_sha": ADOPTED_MAIN_SHA,
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
        "tasks": {
            task: (
                task_state[task].get("state")
                if isinstance(task_state.get(task), dict)
                else "MISSING"
            )
            for task in EXPECTED_TASKS
        },
        "historical_blocked_families": historical_blocked,
        "historical_dependency_blocked_families": historical_dependency,
        "authority_change_proposal_issue": 219,
        "authority_change_resolved": True,
        "implementation_complete": implementation_complete,
        "formal_completion_blocked_by_authority_change": False,
        "formal_completion_blocked_by_protected_main": (
            status == "PASS" and all_tasks_complete and not protected_main
        ),
        "persistence_recovery_qualified": implementation_complete and protected_main,
        "qualification": qualification,
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
