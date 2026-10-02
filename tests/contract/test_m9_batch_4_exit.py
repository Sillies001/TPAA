from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXIT_PATH = ROOT / "tools" / "testing" / "m9_exit_review.py"

SPEC = importlib.util.spec_from_file_location("m9_exit_review", EXIT_PATH)
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
        (193, "closed"),
        (194, "closed"),
        (195, "closed"),
        (196, "closed"),
        (197, "closed"),
        (198, "open"),
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
        193: (
            "ffbd5e5f0561ce39d8736de765dd6be240edfae1 "
            "Run #529 36876431677 14/14 SUCCESS"
        ),
        194: (
            "7628e6caad30f76179d7fbfcf8e600ef80ccc314 "
            "Run #531 36952909234 14/14 SUCCESS"
        ),
        195: (
            "47858360a8409fa9370a4e622f3dc3b308593fdc "
            "Run #535 36960346928 14/14 SUCCESS"
        ),
        196: (
            "d37a994d6efbaeec2d10022ec083015771c40152 "
            "Run #542 36981630238 14/14 SUCCESS "
            "P6_P3_CAPABILITY_OLS_MAD_FORECAST 1.0.0 "
            "6a064762b4edde3448b25e5b74384708745793acc863a8adfbfad40fc7651394 "
            "9d6c70133e1994c5823bbe6efb499001b5aa697c "
            "Run #540 36968525803"
        ),
        197: (
            "87e99b4ea3e55b60ef29a45adfc5e6ad7946bc0e "
            "Run #546 36993939363 14/14 SUCCESS"
        ),
    }
    for number, body in qualifications.items():
        entry = issues[str(number)]
        assert isinstance(entry, dict)
        entry["comments"] = [{"body": body}]
    return {"issues": issues}


def _review(
    tmp_path: Path,
    *,
    event_name: str = "pull_request",
    git_ref: str = "refs/pull/205/merge",
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
    entry = issues["198"]
    assert isinstance(entry, dict)
    issue = entry["issue"]
    assert isinstance(issue, dict)
    issue["state"] = "closed"
    entry["comments"] = [
        {
            "body": (
                "M9 Exit decision=GO failed_acceptance=[] "
                "p6_admitted=true P6_M9_QUALIFIED 14/14 SUCCESS"
            )
        }
    ]


def test_m9_batch_4_pr_candidate_passes_but_cannot_admit_p6(
    tmp_path: Path,
) -> None:
    result = _review(tmp_path)
    assert result["schema"] == "TPAA_M9_EXIT_REVIEW_V1"
    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["p6_admitted"] is False
    assert result["task_complete"] is False
    assert result["failed_acceptance"] == []


def test_m9_batch_4_exact_protected_main_all_pass_admits_p6(
    tmp_path: Path,
) -> None:
    result = _review(
        tmp_path,
        event_name="push",
        git_ref="refs/heads/main",
    )
    assert result["status"] == "PASS"
    assert result["decision"] == "GO"
    assert result["p6_admitted"] is True
    assert result["task_complete"] is True
    assert result["qualification"] == "P6_M9_QUALIFIED"


def test_m9_batch_4_non_main_never_returns_go(tmp_path: Path) -> None:
    result = _review(
        tmp_path,
        event_name="push",
        git_ref="refs/heads/m9/batch4-exit-admission",
    )
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["p6_admitted"] is False


def test_m9_batch_4_source_revision_mismatch_is_no_go(tmp_path: Path) -> None:
    result = _review(tmp_path, checked_out_revision="b" * 40)
    assert result["decision"] == "NO_GO"
    assert "source_revision_exact" in result["failed_acceptance"]


def test_m9_batch_4_fourteen_tasks_is_no_go(tmp_path: Path) -> None:
    baseline = json.loads(EXIT.TASK_BASELINE.read_text(encoding="utf-8"))
    baseline["tasks"] = baseline["tasks"][:-1]
    baseline["task_count"] = 14
    path = _write(tmp_path / "baseline14.json", baseline)
    result = _review(tmp_path, task_baseline_path=path)
    assert result["decision"] == "NO_GO"
    assert "baseline_task_count_exact_15" in result["failed_acceptance"]


def test_m9_batch_4_extra_unknown_task_is_no_go(tmp_path: Path) -> None:
    baseline = json.loads(EXIT.TASK_BASELINE.read_text(encoding="utf-8"))
    baseline["tasks"].append(
        {
            "task_id": "M9-UNKNOWN-999",
            "workstream": "WS-TEST",
            "deliverable": "invalid",
            "dependencies": [],
            "minimum_acceptance": "invalid",
        }
    )
    baseline["task_count"] = 16
    path = _write(tmp_path / "baseline16.json", baseline)
    result = _review(tmp_path, task_baseline_path=path)
    assert result["decision"] == "NO_GO"
    assert "baseline_task_count_exact_15" in result["failed_acceptance"]


def test_m9_batch_4_open_batch3_issue_is_no_go(tmp_path: Path) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    entry = issues["197"]
    assert isinstance(entry, dict)
    issue = entry["issue"]
    assert isinstance(issue, dict)
    issue["state"] = "open"
    result = _review(tmp_path, issues=bundle)
    assert result["decision"] == "NO_GO"
    assert "baseline_c3_and_batches_closed" in result["failed_acceptance"]


def test_m9_batch_4_missing_batch3_qualification_is_no_go(
    tmp_path: Path,
) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    entry = issues["197"]
    assert isinstance(entry, dict)
    entry["comments"] = []
    result = _review(tmp_path, issues=bundle)
    assert result["decision"] == "NO_GO"
    assert "qualification_chain_exact" in result["failed_acceptance"]


def test_m9_batch_4_missing_profile_qualification_is_no_go(
    tmp_path: Path,
) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    entry = issues["196"]
    assert isinstance(entry, dict)
    entry["comments"] = [
        {
            "body": (
                "d37a994d6efbaeec2d10022ec083015771c40152 "
                "Run #542 36981630238 14/14 SUCCESS"
            )
        }
    ]
    result = _review(tmp_path, issues=bundle)
    assert result["decision"] == "NO_GO"
    assert (
        "execution_profile_qualification_exact"
        in result["failed_acceptance"]
    )


def test_m9_batch_4_authority_drift_is_no_go(tmp_path: Path) -> None:
    authority = json.loads(EXIT.AUTHORITY_PATH.read_text(encoding="utf-8"))
    authority["version"] = "9.9.9"
    path = _write(tmp_path / "authority.json", authority)
    result = _review(tmp_path, authority_path=path)
    assert result["decision"] == "NO_GO"
    assert (
        "authority_role_profile_dto_lock_exact"
        in result["failed_acceptance"]
    )


def test_m9_batch_4_shadow_schema_authorization_is_no_go(
    tmp_path: Path,
) -> None:
    authority = json.loads(EXIT.AUTHORITY_PATH.read_text(encoding="utf-8"))
    authority["scope"]["shadow_schema_permitted"] = True
    path = _write(tmp_path / "authority.json", authority)
    result = _review(tmp_path, authority_path=path)
    assert result["decision"] == "NO_GO"
    assert "db_schema_1_6_0_no_shadow_schema" in result["failed_acceptance"]


def test_m9_batch_4_execution_profile_drift_is_no_go(
    tmp_path: Path,
) -> None:
    profile = json.loads(EXIT.EXECUTION_PROFILE_PATH.read_text(encoding="utf-8"))
    profile["version"] = "9.9.9"
    path = _write(tmp_path / "profile.json", profile)
    result = _review(tmp_path, execution_profile_path=path)
    assert result["decision"] == "NO_GO"
    assert (
        "authority_role_profile_dto_lock_exact"
        in result["failed_acceptance"]
    )


def test_m9_batch_4_wrong_required_job_count_is_no_go(tmp_path: Path) -> None:
    result = _review(
        tmp_path,
        required_jobs_success=13,
        required_jobs_total=14,
    )
    assert result["decision"] == "NO_GO"
    assert "required_ci_exact_14" in result["failed_acceptance"]


def test_m9_batch_4_closed_tracker_without_go_evidence_is_no_go(
    tmp_path: Path,
) -> None:
    bundle = _valid_issues()
    issues = bundle["issues"]
    assert isinstance(issues, dict)
    entry = issues["198"]
    assert isinstance(entry, dict)
    issue = entry["issue"]
    assert isinstance(issue, dict)
    issue["state"] = "closed"
    result = _review(tmp_path, issues=bundle)
    assert result["decision"] == "NO_GO"
    assert "program_exit_lifecycle_valid" in result["failed_acceptance"]


def test_m9_batch_4_closed_tracker_with_go_evidence_remains_valid(
    tmp_path: Path,
) -> None:
    bundle = _valid_issues()
    _close_exit_with_go_evidence(bundle)
    result = _review(tmp_path, issues=bundle)
    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["failed_acceptance"] == []


def test_m9_batch_4_workflow_keeps_fourteen_job_topology_and_final_sink() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "cross-platform-ci.yml"
    ).read_text(encoding="utf-8")
    assert "\n  m9-exit-review:" not in workflow
    assert workflow.count("\n  m0-cross-platform:") == 1
    assert "Review exact M9 task inventory and C4 P6 admission" in workflow
    assert "m9_exit_review.py" in workflow
    assert "--required-jobs-success 14" in workflow
    assert "--required-jobs-total 14" in workflow
    assert "numbers = (149, 193, 194, 195, 196, 197, 198)" in workflow
    assert workflow.rstrip().endswith("--output evidence/m9-exit/review.json")
