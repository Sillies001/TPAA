from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW_PATH = ROOT / "tools" / "testing" / "piqb_b5_review.py"
SPEC = importlib.util.spec_from_file_location("piqb_b5_review", REVIEW_PATH)
assert SPEC is not None and SPEC.loader is not None
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


def _qualification(platform: str, revision: str = "a" * 40) -> dict[str, object]:
    acceptance = {
        "real_qt_product_workspace_created": True,
        "navigation_exact_13": True,
        "product_spine_visible": True,
        "semantic_layers_visible": True,
        "existing_surfaces_composed": True,
        "debrief_trajectory_tabs_composed": True,
        "trajectory_exact_release": True,
        "trajectory_2d_projection_exact": True,
        "cesium_relative_time_guard": True,
        "presentation_has_no_business_authority": True,
    }
    return {
        "schema": "TPAA_PIQB_B5_DESKTOP_REPLAY_VISUALIZATION_QUALIFICATION_V1",
        "platform": platform,
        "source_revision": revision,
        "status": "PASS",
        "qualification_passed": True,
        "failed_acceptance": [],
        "acceptance": acceptance,
        "logical_fingerprint": "f" * 64,
    }


def _review(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "expected_revision": "a" * 40,
        "checked_out_revision": "a" * 40,
        "event_name": "pull_request",
        "git_ref": "refs/pull/999/merge",
        "run_conclusion": "success",
        "required_jobs_success": 14,
        "required_jobs_total": 14,
        "windows_qualification": _qualification("windows"),
        "linux_qualification": _qualification("linux"),
    }
    values.update(overrides)
    return REVIEW.review(**values)


def test_b5_candidate_complete_pending_protected_main() -> None:
    result = _review()

    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["qualification"] == "PIQB_B5_CANDIDATE"
    assert result["implementation_complete"] is True
    assert result["desktop_replay_visualization_qualified"] is False
    assert result["formal_completion_blocked_by_protected_main"] is True
    acceptance = result["acceptance"]
    assert isinstance(acceptance, dict)
    assert acceptance["windows_real_qt_qualification_passed"] is True
    assert acceptance["linux_real_qt_qualification_passed"] is True
    assert acceptance["cross_platform_logical_fingerprint_equal"] is True
    assert acceptance["workflow_keeps_fourteen_job_topology"] is True


def test_b5_protected_main_qualifies() -> None:
    result = _review(event_name="push", git_ref="refs/heads/main")

    assert result["status"] == "PASS"
    assert result["decision"] == "GO"
    assert result["qualification"] == "PIQB_B5_QUALIFIED"
    assert result["desktop_replay_visualization_qualified"] is True
    assert result["formal_completion_blocked_by_protected_main"] is False


def test_b5_rejects_stale_head_platform_failure_fingerprint_and_job_count() -> None:
    stale = _review(checked_out_revision="b" * 40)
    assert "candidate_revision_exact" in stale["failed_acceptance"]

    jobs = _review(required_jobs_success=13)
    assert "required_jobs_exact" in jobs["failed_acceptance"]

    failed_windows = _qualification("windows")
    failed_windows["status"] = "FAIL"
    failed_windows["qualification_passed"] = False
    failed_windows["failed_acceptance"] = ["navigation_exact_13"]
    platform = _review(windows_qualification=failed_windows)
    assert "windows_real_qt_qualification_passed" in platform["failed_acceptance"]

    linux = _qualification("linux")
    linux["logical_fingerprint"] = "e" * 64
    mismatch = _review(linux_qualification=linux)
    assert "cross_platform_logical_fingerprint_equal" in mismatch["failed_acceptance"]


def test_b5_workflow_keeps_exact_fourteen_job_topology() -> None:
    workflow = (ROOT / ".github" / "workflows" / "cross-platform-ci.yml").read_text(
        encoding="utf-8"
    )
    assert workflow.count("\n  m0-cross-platform:") == 1
    assert "\n  piqb-b5-review:" not in workflow
    assert "Execute PIQB B5 Desktop replay visualization qualification" in workflow
    assert "Review PIQB B5 Desktop replay and visualization" in workflow
    assert "piqb_b5_desktop_replay_visualization.py" in workflow
    assert "piqb_b5_review.py" in workflow
    assert "--required-jobs-success 14" in workflow
    assert "--required-jobs-total 14" in workflow
