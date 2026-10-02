from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXIT_PATH = ROOT / "tools" / "testing" / "m6_exit_review.py"

SPEC = importlib.util.spec_from_file_location("m6_exit_review", EXIT_PATH)
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
        (151, "closed"),
        (155, "open"),
        (156, "closed"),
        (158, "closed"),
        (159, "closed"),
        (161, "closed"),
        (164, "closed"),
        (166, "open"),
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

    qualification = {
        156: (
            "2a2b0907515761c3768bc952cf97894825e05109 "
            "Run #484 36650776582 14 of 14 SUCCESS"
        ),
        158: (
            "551e620cee6b8f3a5b406790f08443c485bf234b "
            "Run #490 36674275763 14 of 14 SUCCESS"
        ),
        164: (
            "adab5b6c6c03dd7ddfa096fcf7ff5d41cb0adb1c "
            "Run #492 36686582998 all 14 required jobs completed SUCCESS"
        ),
    }
    for number, body in qualification.items():
        entry = issues[str(number)]
        assert isinstance(entry, dict)
        entry["comments"] = [{"body": body}]

    m7 = issues["155"]
    assert isinstance(m7, dict)
    m7["comments"] = [
        {
            "body": (
                "design-only M7-GOV-001 through M7-CAP-005; "
                "NOT_IDENTIFIABLE is not a numeric target; use sealed managed_uri; "
                "default wording REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE."
            )
        }
    ]
    return {"issues": issues}


def _valid_m5_exit() -> dict[str, object]:
    return {
        "status": "PASS",
        "failed_acceptance": [],
        "task_count": 23,
        "exact_evidence_manifest_accepted": True,
        "acceptance": {"task_evidence_exact_23": True},
        "scope": {"db_schema_version": "1.6.0"},
    }


def _review(
    tmp_path: Path,
    *,
    event_name: str = "pull_request",
    git_ref: str = "refs/pull/167/merge",
    expected_revision: str = REV,
    checked_out_revision: str = REV,
    issues: dict[str, object] | None = None,
    m5_exit: dict[str, object] | None = None,
    **overrides: object,
) -> dict[str, object]:
    issue_path = _write(tmp_path / "issues.json", issues or _valid_issues())
    m5_path = _write(tmp_path / "m5.json", m5_exit or _valid_m5_exit())
    return EXIT.review(
        issues_path=issue_path,
        m5_exit_path=m5_path,
        expected_revision=expected_revision,
        checked_out_revision=checked_out_revision,
        event_name=event_name,
        git_ref=git_ref,
        run_conclusion="success",
        required_jobs_success=14,
        required_jobs_total=14,
        **overrides,
    )


def _close_m6_exit_with_exact_go_evidence(bundle: dict[str, object]) -> None:
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    entry = issues["166"]
    assert isinstance(entry, dict)
    issue = entry["issue"]
    assert isinstance(issue, dict)
    issue["state"] = "closed"
    entry["comments"] = [
        {
            "body": (
                "M6 protected-main Exit is formally qualified. "
                "actual M6 merge SHA: 892e4a64a321be9c7252b66207a7d1d90a6ce98d "
                "protected-main Run #494 / 36697493917: push / main / exact merge SHA / "
                "14 of 14 SUCCESS; final decision: `GO`; "
                "`failed_acceptance=[]`; `p2_admitted=true`; "
                "qualification: `P2_M6_QUALIFIED`."
            )
        }
    ]


def test_m6_batch_4_closed_exit_tracker_with_exact_go_evidence_remains_valid(
    tmp_path: Path,
) -> None:
    bundle = _valid_issues()
    _close_m6_exit_with_exact_go_evidence(bundle)
    result = _review(tmp_path, issues=bundle)
    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["failed_acceptance"] == []


def test_m6_batch_4_closed_m7_design_runway_remains_valid_historical_evidence(
    tmp_path: Path,
) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    entry = issues["155"]
    assert isinstance(entry, dict)
    issue = entry["issue"]
    assert isinstance(issue, dict)
    issue["state"] = "closed"
    result = _review(tmp_path, issues=bundle)
    assert result["status"] == "PASS"
    assert result["failed_acceptance"] == []


def test_m6_batch_4_closed_exit_tracker_without_go_evidence_is_no_go(
    tmp_path: Path,
) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    entry = issues["166"]
    assert isinstance(entry, dict)
    issue = entry["issue"]
    assert isinstance(issue, dict)
    issue["state"] = "closed"
    entry["comments"] = []
    result = _review(tmp_path, issues=bundle)
    assert result["decision"] == "NO_GO"
    assert "program_and_exit_tracker_lifecycle_valid" in result["failed_acceptance"]


def test_m6_batch_4_pr_candidate_passes_but_cannot_admit_p2(tmp_path: Path) -> None:
    result = _review(tmp_path)
    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["p2_admitted"] is False
    assert result["task_complete"] is False
    assert result["failed_acceptance"] == []


def test_m6_batch_4_exact_protected_main_all_pass_admits_p2(tmp_path: Path) -> None:
    result = _review(
        tmp_path,
        event_name="push",
        git_ref="refs/heads/main",
    )
    assert result["status"] == "PASS"
    assert result["decision"] == "GO"
    assert result["p2_admitted"] is True
    assert result["qualification"] == "P2_M6_QUALIFIED"
    state = result["admission_state"]
    assert isinstance(state, dict)
    assert state["required_jobs_success"] == 14
    assert state["required_jobs_total"] == 14
    assert state["p3_p6_inactive"] is True


def test_m6_batch_4_pr_event_and_non_main_ref_never_return_go(tmp_path: Path) -> None:
    pr_result = _review(tmp_path)
    non_main = _review(
        tmp_path,
        event_name="push",
        git_ref="refs/heads/m6/batch-4-exit-admission",
    )
    assert pr_result["decision"] == "PENDING_PROTECTED_MAIN"
    assert non_main["decision"] == "PENDING_PROTECTED_MAIN"
    assert pr_result["p2_admitted"] is False
    assert non_main["p2_admitted"] is False


def test_m6_batch_4_source_revision_mismatch_is_no_go(tmp_path: Path) -> None:
    result = _review(tmp_path, checked_out_revision="b" * 40)
    assert result["decision"] == "NO_GO"
    assert "source_revision_exact" in result["failed_acceptance"]


def test_m6_batch_4_sixteen_of_seventeen_tasks_is_no_go(tmp_path: Path) -> None:
    baseline = json.loads(EXIT.TASK_BASELINE.read_text(encoding="utf-8"))
    baseline["tasks"] = baseline["tasks"][:-1]
    baseline["task_count"] = 16
    path = _write(tmp_path / "baseline16.json", baseline)
    result = _review(tmp_path, task_baseline_path=path)
    assert result["decision"] == "NO_GO"
    assert "baseline_task_count_exact_17" in result["failed_acceptance"]


def test_m6_batch_4_extra_unknown_task_is_no_go(tmp_path: Path) -> None:
    baseline = json.loads(EXIT.TASK_BASELINE.read_text(encoding="utf-8"))
    baseline["tasks"].append(
        {
            "task_id": "M6-UNKNOWN-999",
            "workstream": "WS-TEST",
            "deliverable": "invalid",
            "dependencies": [],
            "minimum_acceptance": "invalid",
        }
    )
    baseline["task_count"] = 18
    path = _write(tmp_path / "baseline18.json", baseline)
    result = _review(tmp_path, task_baseline_path=path)
    assert result["decision"] == "NO_GO"
    assert "baseline_task_count_exact_17" in result["failed_acceptance"]


def test_m6_batch_4_failed_retained_m5_gate_is_no_go(tmp_path: Path) -> None:
    m5 = _valid_m5_exit()
    m5["status"] = "FAIL"
    m5["failed_acceptance"] = ["security"]
    result = _review(tmp_path, m5_exit=m5)
    assert result["decision"] == "NO_GO"
    assert "m5_product_gates_retained" in result["failed_acceptance"]


def test_m6_batch_4_stale_execution_profile_hash_is_no_go(tmp_path: Path) -> None:
    profile = json.loads(EXIT.PROFILE_PATH.read_text(encoding="utf-8"))
    profile["version"] = "9.9.9"
    path = _write(tmp_path / "profile.json", profile)
    result = _review(tmp_path, profile_path=path)
    assert result["decision"] == "NO_GO"
    assert "execution_profile_lock_exact" in result["failed_acceptance"]


def test_m6_batch_4_open_c3_issue_is_no_go(tmp_path: Path) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    issue = issues["151"]
    assert isinstance(issue, dict)
    issue_payload = issue["issue"]
    assert isinstance(issue_payload, dict)
    issue_payload["state"] = "open"
    result = _review(tmp_path, issues=bundle)
    assert result["decision"] == "NO_GO"
    assert "c3_issues_closed" in result["failed_acceptance"]


def test_m6_batch_4_current_latest_fallback_evidence_is_no_go(tmp_path: Path) -> None:
    bad = tmp_path / "bad_history.py"
    bad.write_text('PATH = "/latest"\n', encoding="utf-8")
    result = _review(tmp_path, historical_source_paths=(bad,))
    assert result["decision"] == "NO_GO"
    assert "historical_current_latest_recompute_forbidden" in result["failed_acceptance"]


def test_m6_batch_4_p1_non_regression_evidence_missing_is_no_go(tmp_path: Path) -> None:
    text = EXIT.BATCH3_TEST.read_text(encoding="utf-8")
    text = text.replace(
        'phases["P2"] == "DESIGN_CONTRACT_FROZEN"',
        'phases["P2"] == "BROKEN"',
    )
    path = tmp_path / "batch3.py"
    path.write_text(text, encoding="utf-8")
    result = _review(tmp_path, batch3_test_path=path)
    assert result["decision"] == "NO_GO"
    assert "batch3_ui_replay_p1_non_regression_present" in result["failed_acceptance"]


def test_m6_batch_4_db_schema_drift_is_no_go(tmp_path: Path) -> None:
    lock = json.loads(EXIT.LOCK_PATH.read_text(encoding="utf-8"))
    lock["baseline"]["db_schema"] = "1.7.0"
    path = _write(tmp_path / "lock.json", lock)
    result = _review(tmp_path, lock_path=path)
    assert result["decision"] == "NO_GO"
    assert "db_schema_1_6_0_no_shadow_schema" in result["failed_acceptance"]


def test_m6_batch_4_p3_activation_before_m6_go_is_no_go(tmp_path: Path) -> None:
    registry = json.loads(EXIT.REGISTRY_PATH.read_text(encoding="utf-8"))
    for row in registry["capability_phases"]:
        if row["p_code"] == "P3":
            row["baseline_status"] = "CURRENT_BASELINE"
    path = _write(tmp_path / "registry.json", registry)
    result = _review(tmp_path, registry_path=path)
    assert result["decision"] == "NO_GO"
    assert "p3_p6_inactive" in result["failed_acceptance"]


def test_m6_batch_4_batch3_ui_replay_evidence_missing_is_no_go(tmp_path: Path) -> None:
    path = tmp_path / "batch3_review.md"
    path.write_text("incomplete\n", encoding="utf-8")
    result = _review(tmp_path, batch3_review_path=path)
    assert result["decision"] == "NO_GO"
    assert "batch3_ui_replay_p1_non_regression_present" in result["failed_acceptance"]


def test_m6_batch_4_m7_runway_evidence_missing_is_no_go(tmp_path: Path) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    entry = issues["155"]
    assert isinstance(entry, dict)
    entry["comments"] = []
    result = _review(tmp_path, issues=bundle)
    assert result["decision"] == "NO_GO"
    assert "m7_design_runway_exact" in result["failed_acceptance"]


def test_m6_batch_4_workflow_keeps_fourteen_job_topology_and_final_sink() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "cross-platform-ci.yml"
    ).read_text(encoding="utf-8")
    assert "\n  m6-exit-review:" not in workflow
    assert workflow.count("\n  m0-cross-platform:") == 1
    assert "Review exact M6 task inventory and C4 P2 admission" in workflow
    assert "tpaa-m5-exit-review-" in workflow
    assert "m6_exit_review.py" in workflow
    assert "--required-jobs-success 14" in workflow
    assert "--required-jobs-total 14" in workflow
    m0_exit = workflow.split("\n  m0-exit-review:", 1)[1]
    for job_id in (
        "m0-cross-platform",
        "m0-logical-equivalence",
        "m0-exit-postgres",
        "m2-tst-005-review",
        "m3-tst-005-review",
        "m4-tst-005-review",
        "m4-exit-review",
        "m3-exit-review",
        "m2-exit-review",
        "m1-batch-2-review",
        "m1-batch-3-review",
        "m1-exit-review",
    ):
        assert f"      - {job_id}" in m0_exit

def test_m6_historical_review_accepts_program_closed_after_m9_qualification(
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
    _close_m6_exit_with_exact_go_evidence(bundle)
    result = _review(tmp_path, issues=bundle)
    assert result["status"] == "PASS"
    assert result["failed_acceptance"] == []


def test_m6_historical_review_rejects_unqualified_program_closure(
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
