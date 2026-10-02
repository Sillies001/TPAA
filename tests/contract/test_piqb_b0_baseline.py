from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "testing" / "piqb_b0_review.py"

spec = importlib.util.spec_from_file_location("piqb_b0_review", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _review(**overrides: Any) -> dict[str, object]:
    values: dict[str, object] = {
        "expected_revision": "a" * 40,
        "checked_out_revision": "a" * 40,
        "event_name": "pull_request",
        "git_ref": "refs/pull/214/merge",
        "run_conclusion": "success",
        "required_jobs_success": 14,
        "required_jobs_total": 14,
    }
    values.update(overrides)
    return module.review(**values)


def test_piqb_b0_candidate_passes_but_cannot_formally_qualify() -> None:
    result = _review()
    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["formal_completion_blocked_by_protected_main"] is True
    assert result["product_topology_frozen"] is False
    assert result["qualification"] == "PIQB_B0_CANDIDATE"


def test_piqb_b0_exact_protected_main_push_qualifies() -> None:
    result = _review(event_name="push", git_ref="refs/heads/main")
    assert result["status"] == "PASS"
    assert result["decision"] == "GO"
    assert result["failed_acceptance"] == []
    assert result["product_topology_frozen"] is True
    assert result["qualification"] == "PIQB_B0_QUALIFIED"


def test_piqb_b0_source_revision_mismatch_fails() -> None:
    result = _review(checked_out_revision="b" * 40)
    assert result["status"] == "FAIL"
    assert result["decision"] == "NO_GO"
    assert "candidate_revision_exact" in result["failed_acceptance"]


def test_piqb_b0_required_job_count_is_exactly_fourteen() -> None:
    result = _review(required_jobs_success=13, required_jobs_total=14)
    assert result["status"] == "FAIL"
    assert "required_jobs_exact" in result["failed_acceptance"]


def test_piqb_b0_five_task_inventory_is_exact() -> None:
    result = _review()
    assert list(result["tasks"]) == [
        "PIQB-B0-001",
        "PIQB-B0-002",
        "PIQB-B0-003",
        "PIQB-B0-004",
        "PIQB-B0-005",
    ]


def test_piqb_b0_workflow_keeps_fourteen_job_topology() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "cross-platform-ci.yml"
    ).read_text(encoding="utf-8")
    assert "\n  piqb-b0-review:" not in workflow
    assert workflow.count("\n  m0-cross-platform:") == 1
    assert "Review PIQB B0 product topology baseline" in workflow
    assert "piqb_b0_review.py" in workflow
    assert "--required-jobs-success 14" in workflow
    assert "--required-jobs-total 14" in workflow
    assert "--output evidence/piqb-b0/review.json" in workflow
