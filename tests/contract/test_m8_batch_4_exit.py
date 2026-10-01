from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXIT_PATH = ROOT / "tools" / "testing" / "m8_exit_review.py"

SPEC = importlib.util.spec_from_file_location("m8_exit_review", EXIT_PATH)
assert SPEC is not None and SPEC.loader is not None
EXIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXIT)

REV = "a" * 40


def _write(path: Path, value: object) -> Path:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _valid_issues() -> dict[str, object]:
    issues: dict[str, object] = {}
    for number, state in (
        (149, "open"),
        (181, "closed"),
        (182, "closed"),
        (183, "closed"),
        (184, "closed"),
        (185, "open"),
        (186, "open"),
    ):
        issues[str(number)] = {
            "issue": {
                "number": number,
                "state": state,
                "title": f"issue {number}",
                "body": "",
            },
            "comments": [],
        }

    qualifications = {
        181: (
            "0a704735a3e5ecb847d7ed4194aa6649280d351a "
            "Run #516 36822713745 14/14 SUCCESS"
        ),
        182: (
            "b212761dd57ab7abbd5c48b1fefb19a65fd5c71c "
            "Run #518 36829110420 14/14 SUCCESS"
        ),
        183: (
            "68881758cddca2f39b3d6f7801f2766755b8bc2f "
            "Run #520 36838469146 14/14 SUCCESS"
        ),
        184: (
            "eaa1a9a0f3374410cf59e82e97bef70ac18840b0 "
            "Run #525 36855927899 14/14 SUCCESS"
        ),
    }
    for number, body in qualifications.items():
        entry = issues[str(number)]
        assert isinstance(entry, dict)
        entry["comments"] = [{"body": body}]

    runway = issues["186"]
    assert isinstance(runway, dict)
    runway["comments"] = [
        {"body": "M9/P6 runway DESIGN ONLY docs/reviews/M9_P6_DESIGN_RUNWAY_REVIEW.md"}
    ]
    return {"issues": issues}


def _review(
    tmp_path: Path,
    *,
    event_name: str = "pull_request",
    git_ref: str = "refs/pull/192/merge",
    expected_revision: str = REV,
    checked_out_revision: str = REV,
    issues: dict[str, object] | None = None,
    required_jobs_success: int = 14,
    required_jobs_total: int = 14,
    **overrides: object,
) -> dict[str, object]:
    issue_path = _write(tmp_path / "issues.json", issues or _valid_issues())
    return EXIT.review(
        issues_path=issue_path,
        expected_revision=expected_revision,
        checked_out_revision=checked_out_revision,
        event_name=event_name,
        git_ref=git_ref,
        run_conclusion="success",
        required_jobs_success=required_jobs_success,
        required_jobs_total=required_jobs_total,
        **overrides,
    )


def _close_exit_with_go_evidence(bundle: dict[str, object]) -> None:
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    entry = issues["185"]
    assert isinstance(entry, dict)
    issue = entry["issue"]
    assert isinstance(issue, dict)
    issue["state"] = "closed"
    entry["comments"] = [
        {
            "body": (
                "M8 Exit decision=GO failed_acceptance=[] "
                "p4_admitted=true p5_admitted=true p6_inactive=true "
                "P4_P5_M8_QUALIFIED 14/14 SUCCESS"
            )
        }
    ]


def test_m8_batch_4_pr_candidate_passes_but_cannot_admit_p4_p5(
    tmp_path: Path,
) -> None:
    result = _review(tmp_path)
    assert result["schema"] == "TPAA_M8_EXIT_REVIEW_V1"
    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["p4_admitted"] is False
    assert result["p5_admitted"] is False
    assert result["p6_inactive"] is True
    assert result["task_complete"] is False
    assert result["failed_acceptance"] == []


def test_m8_batch_4_exact_protected_main_all_pass_admits_p4_p5(
    tmp_path: Path,
) -> None:
    result = _review(
        tmp_path,
        event_name="push",
        git_ref="refs/heads/main",
    )
    assert result["status"] == "PASS"
    assert result["decision"] == "GO"
    assert result["p4_admitted"] is True
    assert result["p5_admitted"] is True
    assert result["p6_inactive"] is True
    assert result["qualification"] == "P4_P5_M8_QUALIFIED"


def test_m8_batch_4_non_main_never_returns_go(tmp_path: Path) -> None:
    result = _review(
        tmp_path,
        event_name="push",
        git_ref="refs/heads/m8/batch-4-exit-admission",
    )
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["p4_admitted"] is False
    assert result["p5_admitted"] is False


def test_m8_batch_4_source_revision_mismatch_is_no_go(tmp_path: Path) -> None:
    result = _review(tmp_path, checked_out_revision="b" * 40)
    assert result["decision"] == "NO_GO"
    assert "source_revision_exact" in result["failed_acceptance"]


def test_m8_batch_4_twenty_two_tasks_is_no_go(tmp_path: Path) -> None:
    baseline = json.loads(EXIT.TASK_BASELINE.read_text(encoding="utf-8"))
    baseline["tasks"] = baseline["tasks"][:-1]
    baseline["task_count"] = 22
    path = _write(tmp_path / "baseline22.json", baseline)
    result = _review(tmp_path, task_baseline_path=path)
    assert result["decision"] == "NO_GO"
    assert "baseline_task_count_exact_23" in result["failed_acceptance"]


def test_m8_batch_4_extra_unknown_task_is_no_go(tmp_path: Path) -> None:
    baseline = json.loads(EXIT.TASK_BASELINE.read_text(encoding="utf-8"))
    baseline["tasks"].append(
        {
            "task_id": "M8-UNKNOWN-999",
            "workstream": "WS-TEST",
            "deliverable": "invalid",
            "dependencies": [],
            "minimum_acceptance": "invalid",
        }
    )
    baseline["task_count"] = 24
    path = _write(tmp_path / "baseline24.json", baseline)
    result = _review(tmp_path, task_baseline_path=path)
    assert result["decision"] == "NO_GO"
    assert "baseline_task_count_exact_23" in result["failed_acceptance"]


def test_m8_batch_4_open_batch3_issue_is_no_go(tmp_path: Path) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    entry = issues["184"]
    assert isinstance(entry, dict)
    issue = entry["issue"]
    assert isinstance(issue, dict)
    issue["state"] = "open"
    result = _review(tmp_path, issues=bundle)
    assert result["decision"] == "NO_GO"
    assert "c3_and_batch_trackers_closed" in result["failed_acceptance"]


def test_m8_batch_4_missing_batch3_qualification_is_no_go(
    tmp_path: Path,
) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    entry = issues["184"]
    assert isinstance(entry, dict)
    entry["comments"] = []
    result = _review(tmp_path, issues=bundle)
    assert result["decision"] == "NO_GO"
    assert "batch_protected_main_evidence_exact" in result["failed_acceptance"]


def test_m8_batch_4_authority_drift_is_no_go(tmp_path: Path) -> None:
    authority = json.loads(EXIT.AUTHORITY_PATH.read_text(encoding="utf-8"))
    authority["version"] = "9.9.9"
    path = _write(tmp_path / "authority.json", authority)
    result = _review(tmp_path, authority_path=path)
    assert result["decision"] == "NO_GO"
    assert "authority_role_dto_lock_exact" in result["failed_acceptance"]


def test_m8_batch_4_shadow_schema_authorization_is_no_go(
    tmp_path: Path,
) -> None:
    authority = json.loads(EXIT.AUTHORITY_PATH.read_text(encoding="utf-8"))
    authority["scope"]["shadow_schema_permitted"] = True
    path = _write(tmp_path / "authority.json", authority)
    result = _review(tmp_path, authority_path=path)
    assert result["decision"] == "NO_GO"
    assert "db_schema_1_6_0_no_shadow_schema" in result["failed_acceptance"]


def test_m8_batch_4_numeric_default_aggregation_is_no_go(
    tmp_path: Path,
) -> None:
    authority = json.loads(EXIT.AUTHORITY_PATH.read_text(encoding="utf-8"))
    authority["aggregation_contract"]["default_aggregation_profile"] = "bad"
    path = _write(tmp_path / "authority.json", authority)
    result = _review(tmp_path, authority_path=path)
    assert result["decision"] == "NO_GO"
    assert (
        "batch3_p5_aggregation_replay_api_gui_security_gates"
        in result["failed_acceptance"]
    )


def test_m8_batch_4_p6_activation_is_no_go(tmp_path: Path) -> None:
    authority = json.loads(EXIT.AUTHORITY_PATH.read_text(encoding="utf-8"))
    authority["scope"]["p6_active"] = True
    path = _write(tmp_path / "authority.json", authority)
    result = _review(tmp_path, authority_path=path)
    assert result["decision"] == "NO_GO"
    assert "p6_inactive_and_m9_runway_exact" in result["failed_acceptance"]


def test_m8_batch_4_wrong_required_job_count_is_no_go(tmp_path: Path) -> None:
    result = _review(
        tmp_path,
        required_jobs_success=13,
        required_jobs_total=14,
    )
    assert result["decision"] == "NO_GO"
    assert "required_ci_exact_14" in result["failed_acceptance"]


def test_m8_batch_4_closed_tracker_without_go_evidence_is_no_go(
    tmp_path: Path,
) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    entry = issues["185"]
    assert isinstance(entry, dict)
    issue = entry["issue"]
    assert isinstance(issue, dict)
    issue["state"] = "closed"
    result = _review(tmp_path, issues=bundle)
    assert result["decision"] == "NO_GO"
    assert (
        "program_exit_and_m9_runway_lifecycle_valid"
        in result["failed_acceptance"]
    )


def test_m8_batch_4_closed_tracker_with_go_evidence_remains_valid(
    tmp_path: Path,
) -> None:
    bundle = _valid_issues()
    _close_exit_with_go_evidence(bundle)
    result = _review(tmp_path, issues=bundle)
    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["failed_acceptance"] == []


def test_m8_batch_4_workflow_keeps_fourteen_job_topology_and_final_sink() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "cross-platform-ci.yml"
    ).read_text(encoding="utf-8")
    assert "\n  m8-exit-review:" not in workflow
    assert workflow.count("\n  m0-cross-platform:") == 1
    assert "Review exact M8 task inventory and C4 P4/P5 admission" in workflow
    assert "m8_exit_review.py" in workflow
    assert "--required-jobs-success 14" in workflow
    assert "--required-jobs-total 14" in workflow
    assert "numbers = (149, 181, 182, 183, 184, 185, 186)" in workflow
    assert workflow.rstrip().endswith("--output evidence/m8-exit/review.json")
