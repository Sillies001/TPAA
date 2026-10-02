from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXIT_PATH = ROOT / "tools" / "testing" / "m7_exit_review.py"

SPEC = importlib.util.spec_from_file_location("m7_exit_review", EXIT_PATH)
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
        (166, "closed"),
        (169, "closed"),
        (170, "open"),
        (172, "closed"),
        (174, "closed"),
        (176, "closed"),
        (177, "open"),
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

    issue166 = issues["166"]
    assert isinstance(issue166, dict)
    issue166["comments"] = [
        {
            "body": (
                "892e4a64a321be9c7252b66207a7d1d90a6ce98d "
                "Run #494 36697493917 14 of 14 SUCCESS "
                "p2_admitted=true P2_M6_QUALIFIED"
            )
        }
    ]

    qualifications = {
        172: (
            "ebfb99afbb86cf1fc857d03d746afa6e774a4626 "
            "Run #501 36726742843 14/14 SUCCESS"
        ),
        174: (
            "df32b081747e3526e13d974f818cc58125c16fd3 "
            "Run #504 36739428626 14/14 SUCCESS"
        ),
        176: (
            "a56acc6014daf68d5a0207fb78297777e575341b "
            "Run #508 36801435432 14/14 SUCCESS"
        ),
    }
    for number, body in qualifications.items():
        entry = issues[str(number)]
        assert isinstance(entry, dict)
        entry["comments"] = [{"body": body}]

    runway = issues["170"]
    assert isinstance(runway, dict)
    runway["comments"] = [
        {
            "body": (
                "M7-GOV-003 a56acc6014daf68d5a0207fb78297777e575341b "
                "Run #508 36801435432 DESIGN ONLY"
            )
        }
    ]
    return {"issues": issues}


def _review(
    tmp_path: Path,
    *,
    event_name: str = "pull_request",
    git_ref: str = "refs/pull/179/merge",
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
    entry = issues["177"]
    assert isinstance(entry, dict)
    issue = entry["issue"]
    assert isinstance(issue, dict)
    issue["state"] = "closed"
    entry["comments"] = [
        {
            "body": (
                "M7 Exit decision=GO failed_acceptance=[] "
                "p3_admitted=true P3_M7_QUALIFIED 14/14 SUCCESS"
            )
        }
    ]


def test_m7_batch_4_pr_candidate_passes_but_cannot_admit_p3(
    tmp_path: Path,
) -> None:
    result = _review(tmp_path)
    assert result["schema"] == "TPAA_M7_EXIT_REVIEW_V1"
    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["p3_admitted"] is False
    assert result["task_complete"] is False
    assert result["failed_acceptance"] == []


def test_m7_batch_4_exact_protected_main_all_pass_admits_p3(
    tmp_path: Path,
) -> None:
    result = _review(
        tmp_path,
        event_name="push",
        git_ref="refs/heads/main",
    )
    assert result["status"] == "PASS"
    assert result["decision"] == "GO"
    assert result["p3_admitted"] is True
    assert result["qualification"] == "P3_M7_QUALIFIED"
    state = result["admission_state"]
    assert isinstance(state, dict)
    assert state["required_jobs_success"] == 14
    assert state["required_jobs_total"] == 14
    assert state["p4_p6_inactive"] is True


def test_m7_batch_4_pr_event_and_non_main_ref_never_return_go(
    tmp_path: Path,
) -> None:
    pr_result = _review(tmp_path)
    non_main = _review(
        tmp_path,
        event_name="push",
        git_ref="refs/heads/m7/batch-4-exit-admission",
    )
    assert pr_result["decision"] == "PENDING_PROTECTED_MAIN"
    assert non_main["decision"] == "PENDING_PROTECTED_MAIN"
    assert pr_result["p3_admitted"] is False
    assert non_main["p3_admitted"] is False


def test_m7_batch_4_source_revision_mismatch_is_no_go(tmp_path: Path) -> None:
    result = _review(tmp_path, checked_out_revision="b" * 40)
    assert result["decision"] == "NO_GO"
    assert "source_revision_exact" in result["failed_acceptance"]


def test_m7_batch_4_seventeen_of_eighteen_tasks_is_no_go(
    tmp_path: Path,
) -> None:
    baseline = json.loads(EXIT.TASK_BASELINE.read_text(encoding="utf-8"))
    baseline["tasks"] = baseline["tasks"][:-1]
    baseline["task_count"] = 17
    path = _write(tmp_path / "baseline17.json", baseline)
    result = _review(tmp_path, task_baseline_path=path)
    assert result["decision"] == "NO_GO"
    assert "baseline_task_count_exact_18" in result["failed_acceptance"]


def test_m7_batch_4_extra_unknown_task_is_no_go(tmp_path: Path) -> None:
    baseline = json.loads(EXIT.TASK_BASELINE.read_text(encoding="utf-8"))
    baseline["tasks"].append(
        {
            "task_id": "M7-UNKNOWN-999",
            "workstream": "WS-TEST",
            "deliverable": "invalid",
            "dependencies": [],
            "minimum_acceptance": "invalid",
        }
    )
    baseline["task_count"] = 19
    path = _write(tmp_path / "baseline19.json", baseline)
    result = _review(tmp_path, task_baseline_path=path)
    assert result["decision"] == "NO_GO"
    assert "baseline_task_count_exact_18" in result["failed_acceptance"]


def test_m7_batch_4_open_c3_issue_is_no_go(tmp_path: Path) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    entry = issues["169"]
    assert isinstance(entry, dict)
    issue = entry["issue"]
    assert isinstance(issue, dict)
    issue["state"] = "open"
    result = _review(tmp_path, issues=bundle)
    assert result["decision"] == "NO_GO"
    assert "c3_issue_closed" in result["failed_acceptance"]


def test_m7_batch_4_missing_batch3_completion_evidence_is_no_go(
    tmp_path: Path,
) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    entry = issues["176"]
    assert isinstance(entry, dict)
    entry["comments"] = []
    result = _review(tmp_path, issues=bundle)
    assert result["decision"] == "NO_GO"
    assert "batch_protected_main_evidence_exact" in result["failed_acceptance"]


def test_m7_batch_4_missing_m8_runway_evidence_is_no_go(
    tmp_path: Path,
) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    entry = issues["170"]
    assert isinstance(entry, dict)
    entry["comments"] = []
    result = _review(tmp_path, issues=bundle)
    assert result["decision"] == "NO_GO"
    assert "m8_design_runway_exact" in result["failed_acceptance"]


def test_m7_batch_4_stale_profile_is_no_go(tmp_path: Path) -> None:
    profile = json.loads(EXIT.PROFILE_PATH.read_text(encoding="utf-8"))
    profile["version"] = "9.9.9"
    path = _write(tmp_path / "profile.json", profile)
    result = _review(tmp_path, profile_path=path)
    assert result["decision"] == "NO_GO"
    assert "profile_lock_exact" in result["failed_acceptance"]


def test_m7_batch_4_db_schema_drift_is_no_go(tmp_path: Path) -> None:
    authority = json.loads(EXIT.AUTHORITY_PATH.read_text(encoding="utf-8"))
    authority["db_schema_version"] = "1.7.0"
    path = _write(tmp_path / "authority.json", authority)
    result = _review(tmp_path, authority_path=path)
    assert result["decision"] == "NO_GO"
    assert "authority_lock_exact" in result["failed_acceptance"]
    assert "db_schema_1_6_0_no_shadow_schema" in result["failed_acceptance"]


def test_m7_batch_4_stronger_intrinsic_claim_authorization_is_no_go(
    tmp_path: Path,
) -> None:
    authority = json.loads(EXIT.AUTHORITY_PATH.read_text(encoding="utf-8"))
    authority["scope"]["stronger_intrinsic_claim_profile_v1_supported"] = True
    path = _write(tmp_path / "authority.json", authority)
    result = _review(tmp_path, authority_path=path)
    assert result["decision"] == "NO_GO"
    assert "claim_boundary_exact" in result["failed_acceptance"]


def test_m7_batch_4_current_latest_fallback_is_no_go(tmp_path: Path) -> None:
    bad = tmp_path / "bad_api.py"
    bad.write_text('PATH = "/latest"\n', encoding="utf-8")
    result = _review(
        tmp_path,
        application_source_path=bad,
        api_source_path=EXIT.API_SOURCE,
        gui_source_path=EXIT.GUI_SOURCE,
    )
    assert result["decision"] == "NO_GO"
    assert "api_exact_id_no_alias_or_recompute" in result["failed_acceptance"]


def test_m7_batch_4_p4_activation_is_no_go(tmp_path: Path) -> None:
    registry = json.loads(EXIT.REGISTRY_PATH.read_text(encoding="utf-8"))
    for row in registry["capability_phases"]:
        if row["p_code"] == "P4":
            row["baseline_status"] = "CURRENT_BASELINE"
    path = _write(tmp_path / "registry.json", registry)
    result = _review(tmp_path, registry_path=path)
    assert result["decision"] == "NO_GO"
    assert "p4_p6_inactive" in result["failed_acceptance"]


def test_m7_batch_4_wrong_required_job_count_is_no_go(tmp_path: Path) -> None:
    result = _review(
        tmp_path,
        required_jobs_success=13,
        required_jobs_total=14,
    )
    assert result["decision"] == "NO_GO"
    assert "required_ci_exact_14" in result["failed_acceptance"]


def test_m7_batch_4_closed_tracker_without_go_evidence_is_no_go(
    tmp_path: Path,
) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    entry = issues["177"]
    assert isinstance(entry, dict)
    issue = entry["issue"]
    assert isinstance(issue, dict)
    issue["state"] = "closed"
    result = _review(tmp_path, issues=bundle)
    assert result["decision"] == "NO_GO"
    assert (
        "program_and_exit_tracker_lifecycle_valid"
        in result["failed_acceptance"]
    )


def test_m7_batch_4_closed_tracker_with_go_evidence_remains_valid(
    tmp_path: Path,
) -> None:
    bundle = _valid_issues()
    _close_exit_with_go_evidence(bundle)
    result = _review(tmp_path, issues=bundle)
    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["failed_acceptance"] == []


def test_m7_batch_4_workflow_keeps_fourteen_job_topology_and_final_sink() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "cross-platform-ci.yml"
    ).read_text(encoding="utf-8")
    assert "\n  m7-exit-review:" not in workflow
    assert workflow.count("\n  m0-cross-platform:") == 1
    assert "Review exact M7 task inventory and C4 P3 admission" in workflow
    assert "m7_exit_review.py" in workflow
    assert "--required-jobs-success 14" in workflow
    assert "--required-jobs-total 14" in workflow
    assert "numbers = (149, 166, 169, 170, 172, 174, 176, 177)" in workflow
    m7_review = workflow.index(
        "Review exact M7 task inventory and C4 P3 admission"
    )
    assert m7_review >= 0

def test_m7_historical_review_accepts_program_closed_after_m9_qualification(
    tmp_path: Path,
) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    program = issues["149"]
    assert isinstance(program, dict)
    issue = program["issue"]
    assert isinstance(issue, dict)
    issue["state"] = "closed"
    program["comments"] = [{"body": "Program closure P6_M9_QUALIFIED"}]
    _close_exit_with_go_evidence(bundle)
    result = _review(tmp_path, issues=bundle)
    assert result["status"] == "PASS"
    assert result["failed_acceptance"] == []


def test_m7_historical_review_rejects_unqualified_program_closure(
    tmp_path: Path,
) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    program = issues["149"]
    assert isinstance(program, dict)
    issue = program["issue"]
    assert isinstance(issue, dict)
    issue["state"] = "closed"
    program["comments"] = [{"body": "closed without final qualification"}]
    result = _review(tmp_path, issues=bundle)
    assert result["decision"] == "NO_GO"
    assert "program_and_exit_tracker_lifecycle_valid" in result["failed_acceptance"]
