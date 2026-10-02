from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW_PATH = ROOT / "tools" / "testing" / "piqb_b2_review.py"
SPEC = importlib.util.spec_from_file_location("piqb_b2_review", REVIEW_PATH)
assert SPEC is not None and SPEC.loader is not None
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


def _review(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "expected_revision": "a" * 40,
        "checked_out_revision": "a" * 40,
        "event_name": "pull_request",
        "git_ref": "refs/pull/999/merge",
        "run_conclusion": "success",
        "required_jobs_success": 14,
        "required_jobs_total": 14,
    }
    values.update(overrides)
    return REVIEW.review(**values)


def test_b2_truthful_candidate_passes_ci_but_remains_authority_blocked() -> None:
    result = _review()
    assert result["status"] == "PASS"
    assert result["decision"] == "BLOCKED_AUTHORITY_CHANGE"
    assert result["qualification"] == "PIQB_B2_BLOCKED_AUTHORITY_CHANGE"
    assert result["implementation_complete"] is False
    assert result["persistence_recovery_qualified"] is False
    assert result["formal_completion_blocked_by_authority_change"] is True
    assert result["authority_change_proposal_issue"] == 216
    acceptance = result["acceptance"]
    assert isinstance(acceptance, dict)
    assert acceptance["real_postgres_restart_parity_gate_present"] is True
    assert result["blocked_families"] == (
        "P2_ATTRIBUTION",
        "P4_P5_ASSESSMENT",
        "P6_MODEL_PROJECTION_ADVISORY",
    )
    assert result["dependency_blocked_families"] == ("P3_TWIN_CAPABILITY",)


def test_b2_protected_main_cannot_qualify_while_authority_gap_exists() -> None:
    result = _review(event_name="push", git_ref="refs/heads/main")
    assert result["status"] == "PASS"
    assert result["decision"] == "BLOCKED_AUTHORITY_CHANGE"
    assert result["qualification"] != "PIQB_B2_QUALIFIED"
    assert result["persistence_recovery_qualified"] is False


def test_b2_review_fails_exact_head_or_job_count_drift() -> None:
    revision = _review(checked_out_revision="b" * 40)
    assert revision["status"] == "FAIL"
    assert "candidate_revision_exact" in revision["failed_acceptance"]

    jobs = _review(required_jobs_success=13)
    assert jobs["status"] == "FAIL"
    assert "required_jobs_exact" in jobs["failed_acceptance"]


def test_b2_workflow_keeps_exact_fourteen_job_topology() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "cross-platform-ci.yml"
    ).read_text(encoding="utf-8")
    assert "\n  piqb-b2-review:" not in workflow
    assert workflow.count("\n  m0-cross-platform:") == 1
    assert "Review PIQB B2 persistence and recovery state" in workflow
    assert "Execute PIQB B2 PostgreSQL restart/parity qualification" in workflow
    assert "piqb_b2_postgres_product_persistence.py" in workflow
    assert "evidence/piqb-b2/postgres-product-persistence.json" in workflow
    assert "piqb_b2_review.py" in workflow
    assert "--required-jobs-success 14" in workflow
    assert "--required-jobs-total 14" in workflow
    assert "--output evidence/piqb-b2/review.json" in workflow
