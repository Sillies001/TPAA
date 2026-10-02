from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW_PATH = ROOT / "tools" / "testing" / "acp_216_adoption_readiness.py"
SPEC = importlib.util.spec_from_file_location("acp_216_adoption_readiness", REVIEW_PATH)
assert SPEC is not None and SPEC.loader is not None
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


def _review(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "expected_revision": "a" * 40,
        "checked_out_revision": "a" * 40,
        "run_conclusion": "success",
        "required_jobs_success": 14,
        "required_jobs_total": 14,
    }
    values.update(overrides)
    return REVIEW.review(**values)


def test_acp_216_is_ready_for_separate_adoption_without_mutating_authority() -> None:
    result = _review()
    assert result["status"] == "PASS"
    assert result["decision"] == "READY_FOR_ADOPTION"
    assert result["qualification"] == "ACP216_ADOPTION_READY"
    assert result["authority_changed"] is False
    assert result["adoption_performed"] is False
    assert result["formal_b2_unblocked"] is False
    assert result["next_gate"] == "SEPARATE_AUTHORITY_ADOPTION_CHANGE_REQUIRED"
    acceptance = result["acceptance"]
    assert isinstance(acceptance, dict)
    assert all(acceptance.values())


def test_acp_216_readiness_fails_exact_head_or_job_count_drift() -> None:
    revision = _review(checked_out_revision="b" * 40)
    assert revision["status"] == "FAIL"
    assert "candidate_revision_exact" in revision["failed_acceptance"]

    jobs = _review(required_jobs_total=15)
    assert jobs["status"] == "FAIL"
    assert "required_jobs_exact" in jobs["failed_acceptance"]


def test_acp_216_readiness_is_same_job_step_not_fifteenth_job() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "cross-platform-ci.yml"
    ).read_text(encoding="utf-8")
    assert "\n  acp-216-adoption-readiness:" not in workflow
    assert "Review ACP-216 adoption readiness without authority mutation" in workflow
    assert "acp_216_adoption_readiness.py" in workflow
    assert "--required-jobs-success 14" in workflow
    assert "--required-jobs-total 14" in workflow
    assert "--output evidence/piqb-b2/acp-216-adoption-readiness.json" in workflow
