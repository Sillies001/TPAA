"""PIQB B3 production data and compute-plane qualification review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "baseline" / "PIQB-1.0"
TASK_BASELINE = BASE / "B3_TASK_BASELINE.json"
IMPLEMENTATION_STATE = BASE / "B3_IMPLEMENTATION_STATE.json"
SOURCE_B2_SHA = "4b6e7c1e40d857b859b7fd322af9943706e79354"
EXPECTED_TASKS = tuple(f"PIQB-B3-{index:03d}" for index in range(1, 9))


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
    production_qualification: dict[str, Any],
) -> dict[str, object]:
    baseline = _json(TASK_BASELINE)
    state = _json(IMPLEMENTATION_STATE)
    tasks = baseline.get("tasks")
    task_ids = tuple(
        item.get("task_id")
        for item in tasks
        if isinstance(tasks, list) and isinstance(item, dict)
    ) if isinstance(tasks, list) else ()

    task_state = state.get("task_state")
    state_items = (
        tuple(task_state.get(task, {}).get("state") for task in EXPECTED_TASKS)
        if isinstance(task_state, dict)
        else ()
    )
    scope = baseline.get("scope")
    workflow = _text(".github/workflows/cross-platform-ci.yml")
    source = _text("src/tpaa_ingest/production_source.py")
    import_boundary = _text("src/tpaa_application/source_import.py")
    polars_runtime = _text("src/tpaa_platform/polars_runtime.py")
    parquet = _text("src/tpaa_storage/parquet_plane.py")
    jobs = _text("src/tpaa_storage/compute_job.py")
    durable = _text("src/tpaa_application/durable_job_control.py")
    worker = _text("src/tpaa_platform/worker.py")
    recovery = _text("src/tpaa_storage/product_publication.py")
    pyproject = _text("pyproject.toml")

    qualification_acceptance = production_qualification.get("acceptance")
    qualification_all_pass = (
        isinstance(qualification_acceptance, dict)
        and bool(qualification_acceptance)
        and all(value is True for value in qualification_acceptance.values())
    )

    foundation = state.get("foundation_qualification")
    data_plane = state.get("data_plane_qualification")
    runtime_safety = state.get("runtime_safety_qualification")

    acceptance = {
        "b2_entry_exact": (
            baseline.get("source_b2_protected_main_sha") == SOURCE_B2_SHA
            and baseline.get("source_b2_qualification") == "PIQB_B2_QUALIFIED"
            and baseline.get("source_b2_run_number") == 611
        ),
        "task_inventory_exact_8": (
            baseline.get("task_count") == 8
            and task_ids == EXPECTED_TASKS
        ),
        "db_1_9_no_authority_change": (
            baseline.get("db_schema_version") == "1.9.0"
            and isinstance(scope, dict)
            and scope.get("no_db_schema_change") is True
            and scope.get("no_shadow_schema") is True
            and scope.get("no_canonical_mutation") is True
        ),
        "prior_exact_head_gates_preserved": (
            isinstance(foundation, dict)
            and foundation.get("run_number") == 612
            and foundation.get("required_jobs_success") == 14
            and isinstance(data_plane, dict)
            and data_plane.get("run_number") == 614
            and data_plane.get("required_jobs_success") == 14
            and isinstance(runtime_safety, dict)
            and runtime_safety.get("run_number") == 615
            and runtime_safety.get("required_jobs_success") == 14
        ),
        "all_tasks_complete_candidate": (
            len(state_items) == 8
            and all(
                item in {"COMPLETE_CANDIDATE", "COMPLETE"}
                for item in state_items
            )
        ),
        "six_family_source_registry_present": all(
            token in source
            for token in (
                'FLIGHT = "FLIGHT"',
                'MISSION_AVIONICS = "MISSION_AVIONICS"',
                'TDL = "TDL"',
                'RANGE_ACMI = "RANGE_ACMI"',
                'SCENARIO = "SCENARIO"',
                'AUDIO_VIDEO = "AUDIO_VIDEO"',
                "SourceAdapterRegistry",
            )
        ),
        "production_import_provenance_present": all(
            token in import_boundary
            for token in (
                "ProductionImportService",
                "SourceProvenanceRepository",
                '"registry.data_source"',
                '"registry.source_stream"',
                '"registry.source_artifact"',
            )
        ),
        "polars_and_parquet_governed": (
            '"polars==1.44.2"' in pyproject
            and 'EXPECTED_POLARS_VERSION = "1.44.2"' in polars_runtime
            and 'collect(engine="streaming")' in polars_runtime
            and "tpaa-parquet://" in parquet
            and "logical_content_hash" in parquet
            and "artifact_sha256" in parquet
        ),
        "durable_job_lifecycle_present": all(
            token in jobs
            for token in (
                'SUBMITTED = "SUBMITTED"',
                'QUEUED = "QUEUED"',
                'RUNNING = "RUNNING"',
                'SUCCEEDED = "SUCCEEDED"',
                'FAILED = "FAILED"',
                'CANCELLED = "CANCELLED"',
                "cas_update",
            )
        ) and all(
            token in durable
            for token in (
                "DurableJobControl",
                "B3_JOB_IDEMPOTENCY_CONFLICT",
                "B3_JOB_TRANSITION_INVALID",
                "B3_JOB_PROGRESS_INVALID",
            )
        ),
        "worker_and_resource_safety_present": (
            "SpawnWorkerDispatcher" in worker
            and "WorkerAdmissionController" in worker
            and "WorkerBackpressureError" in worker
            and "WorkerTimeoutError" in worker
            and "subprocess" not in worker
            and "shell=True" not in worker
            and "recover_staging_orphans" in recovery
            and "active_operation_ids" in recovery
        ),
        "production_pipeline_qualification_passed": (
            production_qualification.get("schema")
            == "TPAA_PIQB_B3_PRODUCTION_PIPELINE_QUALIFICATION_V1"
            and production_qualification.get("source_revision") == expected_revision
            and production_qualification.get("status") == "PASS"
            and production_qualification.get("pipeline_qualification_passed") is True
            and production_qualification.get("failed_acceptance") == []
            and qualification_all_pass
        ),
        "qualification_scope_exact": (
            isinstance(production_qualification.get("scope"), dict)
            and production_qualification["scope"].get("db_schema_version") == "1.9.0"
            and production_qualification["scope"].get("real_sqlite_executed") is True
            and production_qualification["scope"].get("real_postgresql_executed") is True
            and production_qualification["scope"].get("real_spawn_worker_executed") is True
            and production_qualification["scope"].get("polars_parquet_executed") is True
            and production_qualification["scope"].get(
                "canonical_world_metric_release_executed"
            ) is True
            and production_qualification["scope"].get("shadow_schema_created") is False
            and production_qualification["scope"].get(
                "required_job_topology_changed"
            ) is False
        ),
        "workflow_keeps_fourteen_job_topology": (
            "Execute PIQB B3 production import to persistent release qualification"
            in workflow
            and "Review PIQB B3 production data and compute plane qualification"
            in workflow
            and "\n  piqb-b3-review:" not in workflow
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
        "schema": "TPAA_PIQB_B3_REVIEW_V1",
        "baseline": "PIQB-1.0",
        "source_b2_protected_main_sha": SOURCE_B2_SHA,
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
        "production_pipeline_qualified": status == "PASS",
        "data_compute_plane_qualified": qualified,
        "qualification": (
            "PIQB_B3_QUALIFIED"
            if qualified
            else "PIQB_B3_CANDIDATE"
            if status == "PASS"
            else "PIQB_B3_NOT_QUALIFIED"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-qualification", type=Path, required=True)
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
        production_qualification=_json(args.production_qualification),
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
