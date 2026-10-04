from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW_PATH = ROOT / "tools" / "testing" / "piqb_b3_review.py"
SPEC = importlib.util.spec_from_file_location("piqb_b3_review", REVIEW_PATH)
assert SPEC is not None and SPEC.loader is not None
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


def _qualification(revision: str = "a" * 40) -> dict[str, object]:
    acceptance = {
        "sqlite_db_1_9": True,
        "postgres_db_1_9": True,
        "sqlite_full_pipeline_exact": True,
        "postgres_full_pipeline_exact": True,
        "sqlite_postgres_logical_parity": True,
        "source_byte_identity_exact": True,
        "restart_release_exact_both": True,
        "replay_exact_both": True,
        "parquet_restart_scan_exact_both": True,
        "terminal_job_succeeded_both": True,
        "no_shadow_schema": True,
    }
    return {
        "schema": "TPAA_PIQB_B3_PRODUCTION_PIPELINE_QUALIFICATION_V1",
        "source_revision": revision,
        "status": "PASS",
        "pipeline_qualification_passed": True,
        "failed_acceptance": [],
        "acceptance": acceptance,
        "scope": {
            "db_schema_version": "1.9.0",
            "real_sqlite_executed": True,
            "real_postgresql_executed": True,
            "real_spawn_worker_executed": True,
            "polars_parquet_executed": True,
            "canonical_world_metric_release_executed": True,
            "shadow_schema_created": False,
            "required_job_topology_changed": False,
        },
    }


def _review(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "expected_revision": "a" * 40,
        "checked_out_revision": "a" * 40,
        "event_name": "pull_request",
        "git_ref": "refs/pull/223/merge",
        "run_conclusion": "success",
        "required_jobs_success": 14,
        "required_jobs_total": 14,
        "production_qualification": _qualification(),
    }
    values.update(overrides)
    return REVIEW.review(**values)


def test_b3_candidate_complete_pending_protected_main() -> None:
    result = _review()

    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["qualification"] == "PIQB_B3_CANDIDATE"
    assert result["implementation_complete"] is True
    assert result["production_pipeline_qualified"] is True
    assert result["data_compute_plane_qualified"] is False
    assert result["formal_completion_blocked_by_protected_main"] is True
    acceptance = result["acceptance"]
    assert isinstance(acceptance, dict)
    assert acceptance["production_pipeline_qualification_passed"] is True
    assert acceptance["all_tasks_complete_candidate"] is True
    assert acceptance["workflow_keeps_fourteen_job_topology"] is True


def test_b3_protected_main_qualifies() -> None:
    result = _review(event_name="push", git_ref="refs/heads/main")

    assert result["status"] == "PASS"
    assert result["decision"] == "GO"
    assert result["qualification"] == "PIQB_B3_QUALIFIED"
    assert result["data_compute_plane_qualified"] is True
    assert result["formal_completion_blocked_by_protected_main"] is False


def test_b3_rejects_stale_head_jobs_and_failed_pipeline() -> None:
    stale = _review(checked_out_revision="b" * 40)
    assert "candidate_revision_exact" in stale["failed_acceptance"]

    jobs = _review(required_jobs_success=13)
    assert "required_jobs_exact" in jobs["failed_acceptance"]

    failed_qualification = _qualification()
    failed_qualification["status"] = "FAIL"
    failed_qualification["pipeline_qualification_passed"] = False
    pipeline = _review(production_qualification=failed_qualification)
    assert "production_pipeline_qualification_passed" in pipeline["failed_acceptance"]


def test_b3_workflow_keeps_exact_fourteen_job_topology() -> None:
    workflow = (ROOT / ".github" / "workflows" / "cross-platform-ci.yml").read_text(
        encoding="utf-8"
    )

    assert "\n  piqb-b3-review:" not in workflow
    assert workflow.count("\n  m0-cross-platform:") == 1
    assert "Execute PIQB B3 production import to persistent release qualification" in workflow
    assert "Review PIQB B3 production data and compute plane qualification" in workflow
    assert "piqb_b3_production_pipeline.py" in workflow
    assert "piqb_b3_review.py" in workflow
    assert "--required-jobs-success 14" in workflow
    assert "--required-jobs-total 14" in workflow



def test_b3_governance_scripts_are_python_syntax_valid() -> None:
    for relative in (
        "tools/testing/piqb_b3_production_pipeline.py",
        "tools/testing/piqb_b3_review.py",
    ):
        path = ROOT / relative
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))