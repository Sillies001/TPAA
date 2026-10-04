from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW_PATH = ROOT / "tools/testing/piqb_b2_review.py"
SPEC = importlib.util.spec_from_file_location("piqb_b2_review", REVIEW_PATH)
assert SPEC is not None and SPEC.loader is not None
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


def _review(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "expected_revision": "a" * 40,
        "checked_out_revision": "a" * 40,
        "event_name": "pull_request",
        "git_ref": "refs/pull/217/merge",
        "run_conclusion": "success",
        "required_jobs_success": 14,
        "required_jobs_total": 14,
    }
    values.update(overrides)
    return REVIEW.review(**values)


def test_b2_candidate_complete_pending_protected_main() -> None:
    result = _review()
    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["qualification"] == "PIQB_B2_CANDIDATE"
    assert result["authority_change_resolved"] is True
    assert result["implementation_complete"] is True
    assert result["formal_completion_blocked_by_authority_change"] is False
    assert result["formal_completion_blocked_by_protected_main"] is True
    acceptance = result["acceptance"]
    assert isinstance(acceptance, dict)
    assert acceptance["db_schema_1_9_authority_adopted"] is True
    assert acceptance["historical_db_1_7_adoption_preserved"] is True
    assert acceptance["historical_db_1_8_adoption_preserved"] is True
    assert acceptance["real_postgres_restart_parity_gate_present"] is True
    assert acceptance["p4_p5_exact_adapter_present"] is True
    assert acceptance["real_postgres_p4_p5_gate_present"] is True
    assert acceptance["p3_durable_adapter_and_postgres_gate_present"] is True
    assert acceptance["p6_durable_substrate_present"] is True
    assert acceptance["p6_result_adapter_present"] is True
    assert acceptance["p6_durable_resolver_postgres_gate_present"] is True
    assert acceptance["adapter_tasks_complete_candidate"] is True


def test_b2_protected_main_qualifies_complete_candidate() -> None:
    result = _review(event_name="push", git_ref="refs/heads/main")
    assert result["status"] == "PASS"
    assert result["decision"] == "GO"
    assert result["qualification"] == "PIQB_B2_QUALIFIED"
    assert result["implementation_complete"] is True


def test_b2_review_fails_exact_head_or_job_count_drift() -> None:
    failed_head = _review(checked_out_revision="b" * 40)["failed_acceptance"]
    failed_jobs = _review(required_jobs_success=13)["failed_acceptance"]
    assert "candidate_revision_exact" in failed_head
    assert "required_jobs_exact" in failed_jobs


def test_b2_workflow_keeps_exact_fourteen_job_topology() -> None:
    workflow = (ROOT / ".github/workflows/cross-platform-ci.yml").read_text(
        encoding="utf-8"
    )
    assert "\n  piqb-b2-review:" not in workflow
    assert workflow.count("\n  m0-cross-platform:") == 1
    assert "Review PIQB B2 persistence and recovery state" in workflow
    assert "Execute PIQB B2 PostgreSQL restart/parity qualification" in workflow
    assert "Execute PIQB B2 P4/P5 real PostgreSQL exact persistence qualification" in workflow
    assert "Review ACP-221 DB 1.9.0 authority adoption gate" in workflow
    assert "run_platform_parallel_lanes.py" in workflow
    runner = (ROOT / "tools/ci/run_platform_parallel_lanes.py").read_text(
        encoding="utf-8"
    )
    assert 'EXPECTED_LANES = ("m1", "m2", "m3", "m4", "m5")' in runner
    assert "ThreadPoolExecutor" in runner
    assert "PARALLEL_LANE_FAIL" in runner
    assert "Review ACP-216 DB 1.7.0 authority adoption gate" not in workflow
