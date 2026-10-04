from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW_PATH = ROOT / "tools" / "testing" / "piqb_b4_review.py"
SPEC = importlib.util.spec_from_file_location("piqb_b4_review", REVIEW_PATH)
assert SPEC is not None and SPEC.loader is not None
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


def _qualification(revision: str = "a" * 40) -> dict[str, object]:
    acceptance = {
        "sqlite_db_1_9": True,
        "postgres_db_1_9": True,
        "sqlite_audit_restart_exact": True,
        "postgres_audit_restart_exact": True,
        "audit_semantic_parity": True,
        "actor_pseudonym_separation": True,
        "product_openapi_exact": True,
        "product_client_exact": True,
        "product_route_count_exact_10": True,
        "product_exact_id_only": True,
        "observability_exact": True,
        "no_shadow_schema": True,
        "required_job_topology_changed": False,
    }
    return {
        "schema": "TPAA_PIQB_B4_API_SECURITY_OBSERVABILITY_QUALIFICATION_V1",
        "source_revision": revision,
        "status": "PASS",
        "qualification_passed": True,
        "formal_b4_qualification_claimed": False,
        "completion_gate": "B4_CANDIDATE_REVIEW_PENDING",
        "failed_acceptance": [],
        "acceptance": acceptance,
        "scope": {
            "db_schema_version": "1.9.0",
            "audit_relation": "audit.audit_log",
            "real_sqlite_executed": True,
            "real_postgresql_executed": True,
            "shadow_schema_created": False,
            "required_job_topology_changed": False,
        },
    }


def _review(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "expected_revision": "a" * 40,
        "checked_out_revision": "a" * 40,
        "event_name": "pull_request",
        "git_ref": "refs/pull/224/merge",
        "run_conclusion": "success",
        "required_jobs_success": 14,
        "required_jobs_total": 14,
        "qualification": _qualification(),
    }
    values.update(overrides)
    return REVIEW.review(**values)


def test_b4_candidate_complete_pending_protected_main() -> None:
    result = _review()

    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["qualification"] == "PIQB_B4_CANDIDATE"
    assert result["implementation_complete"] is True
    assert result["api_security_observability_qualified"] is False
    assert result["formal_completion_blocked_by_protected_main"] is True
    acceptance = result["acceptance"]
    assert isinstance(acceptance, dict)
    assert acceptance["qualification_passed"] is True
    assert acceptance["all_tasks_complete_candidate"] is True
    assert acceptance["workflow_keeps_fourteen_job_topology"] is True


def test_b4_protected_main_qualifies() -> None:
    result = _review(event_name="push", git_ref="refs/heads/main")

    assert result["status"] == "PASS"
    assert result["decision"] == "GO"
    assert result["qualification"] == "PIQB_B4_QUALIFIED"
    assert result["api_security_observability_qualified"] is True
    assert result["formal_completion_blocked_by_protected_main"] is False


def test_b4_rejects_stale_head_failed_qualification_and_job_count() -> None:
    stale = _review(checked_out_revision="b" * 40)
    assert "candidate_revision_exact" in stale["failed_acceptance"]

    jobs = _review(required_jobs_success=13)
    assert "required_jobs_exact" in jobs["failed_acceptance"]

    failed = _qualification()
    failed["status"] = "FAIL"
    failed["qualification_passed"] = False
    failed["failed_acceptance"] = ["postgres_audit_restart_exact"]
    result = _review(qualification=failed)
    assert "qualification_passed" in result["failed_acceptance"]


def test_b4_workflow_keeps_exact_fourteen_job_topology() -> None:
    workflow = (ROOT / ".github" / "workflows" / "cross-platform-ci.yml").read_text(
        encoding="utf-8"
    )
    assert workflow.count("\n  m0-cross-platform:") == 1
    assert "\n  piqb-b4-review:" not in workflow
    assert "Execute PIQB B4 API security observability qualification" in workflow
    assert "Upload PIQB B4 PostgreSQL qualification evidence" in workflow
    assert "Download PIQB B4 PostgreSQL qualification evidence" in workflow
    assert "Review PIQB B4 unified API security and observability" in workflow
    assert "piqb_b4_api_security_observability.py" in workflow
    assert "piqb_b4_review.py" in workflow
    assert "--required-jobs-success 14" in workflow
    assert "--required-jobs-total 14" in workflow
