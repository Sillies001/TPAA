#!/usr/bin/env python3
"""M6-TST-005 exact M6 Exit review and C4 P2 admission decision."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
CANONICAL = BASELINE / "canonical"
TASK_BASELINE = ROOT / "docs" / "baseline" / "SDIB-1.5" / "M6_TASK_BASELINE.json"
LOCK_PATH = BASELINE / "BASELINE_LOCK.json"
AUTHORITY_PATH = CANONICAL / "P2_ATTRIBUTION_NORMALIZATION_AUTHORITY.json"
DTO_PATH = CANONICAL / "CROSS_LAYER_DTO_CONTRACTS.json"
PROFILE_PATH = CANONICAL / "P2_LINEAR_REFERENCE_ADJUSTMENT_PROFILE.json"
REGISTRY_PATH = CANONICAL / "CAPABILITY_PHASE_REGISTRY.json"
BATCH1_TEST = ROOT / "tests" / "contract" / "test_m6_batch_1_p2_substrate.py"
BATCH2_TEST = ROOT / "tests" / "contract" / "test_m6_batch_2_attribution_engine.py"
BATCH3_TEST = ROOT / "tests" / "contract" / "test_m6_batch_3_p2_workspace.py"
BATCH3_REVIEW = ROOT / "docs" / "reviews" / "M6_BATCH3_P2_WORKSPACE_DIAGNOSTICS_REVIEW.md"
HISTORICAL_SOURCES = (
    ROOT / "src" / "tpaa_application" / "m6_workspace.py",
    ROOT / "src" / "tpaa_api" / "m6_app.py",
    ROOT / "src" / "tpaa_gui" / "m6_workspace.py",
)

TASK_ID = "M6-TST-005"
TRACKING_ISSUE = 166
EXPECTED_M6_DTO_SHA256 = "9d94f75031afcbfe2391bed1245c3f8d95f124a6549a8f116aa1efb879ae45b4"
EXPECTED_P2_DTO_SUBSET_SHA256 = "d79d97eb41354ad61654372310bb1a92b37914a858213f5dfc4a1287e14c6706"
P2_DTO_NAMES = (
    "P2EligibleObservationDTO",
    "FactorFeatureSetDTO",
    "AttributionRunDTO",
    "AdjustedCapabilityEstimateDTO",
    "P2AdmissionStateDTO",
)
EXPECTED_TASK_IDS = (
    "M6-GOV-001", "M6-GOV-002", "M6-DATA-001", "M6-DATA-002", "M6-DATA-003",
    "M6-CAP-001", "M6-CAP-002", "M6-CAP-003", "M6-CAP-004",
    "M6-GUI-001", "M6-GUI-002", "M6-GOV-003",
    "M6-TST-001", "M6-TST-002", "M6-TST-003", "M6-TST-004", "M6-TST-005",
)
BATCH_QUALIFICATION: dict[str, dict[str, object]] = {
    "M6-BATCH-1": {
        "task_ids": EXPECTED_TASK_IDS[0:5] + ("M6-TST-001",),
        "issue": 156,
        "protected_main_sha": "2a2b0907515761c3768bc952cf97894825e05109",
        "run_number": 484,
        "actions_run_id": 36650776582,
    },
    "M6-BATCH-2": {
        "task_ids": EXPECTED_TASK_IDS[5:9] + EXPECTED_TASK_IDS[13:15],
        "issue": 158,
        "protected_main_sha": "551e620cee6b8f3a5b406790f08443c485bf234b",
        "run_number": 490,
        "actions_run_id": 36674275763,
    },
    "M6-BATCH-3": {
        "task_ids": EXPECTED_TASK_IDS[9:12] + ("M6-TST-004",),
        "issue": 164,
        "protected_main_sha": "adab5b6c6c03dd7ddfa096fcf7ff5d41cb0adb1c",
        "run_number": 492,
        "actions_run_id": 36686582998,
    },
}
BATCH_FILES = {
    "M6-BATCH-1": (
        ROOT / "docs" / "reviews" / "M6_C3_P2_ATTRIBUTION_NORMALIZATION_AUTHORITY_REVIEW.md",
        BATCH1_TEST,
        AUTHORITY_PATH,
    ),
    "M6-BATCH-2": (
        ROOT / "docs" / "reviews" / "M6_BATCH2_ATTRIBUTION_ENGINE_REVIEW.md",
        BATCH2_TEST,
        ROOT / "src" / "tpaa_assessment" / "p2_attribution.py",
        PROFILE_PATH,
    ),
    "M6-BATCH-3": (
        BATCH3_REVIEW,
        BATCH3_TEST,
        ROOT / "src" / "tpaa_application" / "m6_workspace.py",
        ROOT / "src" / "tpaa_gui" / "m6_workspace.py",
    ),
}


def _json(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path}: root must be object")
    return cast(dict[str, Any], value)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _is_sha(value: str) -> bool:
    return len(value) == 40 and all(ch in "0123456789abcdef" for ch in value)


def _lock_hashes(lock: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    rows = lock.get("artifacts")
    if not isinstance(rows, list):
        return result
    for raw in rows:
        if isinstance(raw, dict):
            row = cast(dict[str, Any], raw)
            name, sha = row.get("file"), row.get("sha256")
            if isinstance(name, str) and isinstance(sha, str):
                result[name] = sha
    return result


def _p2_dto_subset_hash(dto_contracts: dict[str, Any]) -> str:
    subset = {
        name: cast(dict[str, Any], dto_contracts.get(name, {}))
        for name in P2_DTO_NAMES
    }
    return _canonical_hash(subset)


def _issue(bundle: dict[str, Any], number: int) -> dict[str, Any]:
    issues = bundle.get("issues")
    if not isinstance(issues, dict):
        return {}
    value = cast(dict[str, Any], issues).get(str(number))
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _issue_state(bundle: dict[str, Any], number: int) -> str:
    issue = _issue(bundle, number).get("issue")
    if not isinstance(issue, dict):
        return ""
    state = cast(dict[str, Any], issue).get("state")
    return state if isinstance(state, str) else ""


def _issue_text(bundle: dict[str, Any], number: int) -> str:
    entry = _issue(bundle, number)
    parts: list[str] = []
    issue = entry.get("issue")
    if isinstance(issue, dict):
        for key in ("title", "body"):
            value = cast(dict[str, Any], issue).get(key)
            if isinstance(value, str):
                parts.append(value)
    comments = entry.get("comments")
    if isinstance(comments, list):
        for raw in comments:
            if isinstance(raw, dict):
                value = cast(dict[str, Any], raw).get("body")
                if isinstance(value, str):
                    parts.append(value)
    return "\n".join(parts)


def _batch_issue_evidence_exact(bundle: dict[str, Any]) -> bool:
    for row in BATCH_QUALIFICATION.values():
        issue = cast(int, row["issue"])
        text = _issue_text(bundle, issue)
        tokens = (
            cast(str, row["protected_main_sha"]),
            f"#{cast(int, row['run_number'])}",
            str(cast(int, row["actions_run_id"])),
        )
        if _issue_state(bundle, issue) != "closed" or not all(t in text for t in tokens):
            return False
        if "14" not in text or not any(t in text.upper() for t in ("SUCCESS", "PASS")):
            return False
    return True


def _m7_runway_exact(bundle: dict[str, Any]) -> bool:
    if _issue_state(bundle, 155) not in {"open", "closed"}:
        return False
    text = _issue_text(bundle, 155).lower()
    return all(
        token.lower() in text
        for token in (
            "M7-GOV-001",
            "M7-CAP-005",
            "NOT_IDENTIFIABLE",
            "managed_uri",
            "REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE",
            "design-only",
        )
    )


def _program_and_exit_tracker_lifecycle_valid(bundle: dict[str, Any]) -> bool:
    program_state = _issue_state(bundle, 149)
    if program_state not in {"open", "closed"}:
        return False
    if program_state == "closed" and "P6_M9_QUALIFIED" not in _issue_text(bundle, 149):
        return False
    exit_state = _issue_state(bundle, 166)
    if exit_state == "open":
        return True
    if exit_state != "closed":
        return False
    text = _issue_text(bundle, 166)
    return (
        "892e4a64a321be9c7252b66207a7d1d90a6ce98d" in text
        and "Run #494" in text
        and "36697493917" in text
        and ("14 of 14 SUCCESS" in text or "14/14 SUCCESS" in text)
        and "final decision: `GO`" in text
        and "`failed_acceptance=[]`" in text
        and "`p2_admitted=true`" in text
        and "`P2_M6_QUALIFIED`" in text
    )


def _paths_clean(paths: tuple[Path, ...]) -> bool:
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    return all(
        token not in text
        for token in (
            '"/latest"',
            '"/current"',
            "execute_p2_attribution(",
            "materialize_factor_feature_set(",
            "sqlite3",
            "psycopg",
        )
    )


def _tokens(path: Path, values: tuple[str, ...]) -> bool:
    text = path.read_text(encoding="utf-8")
    return all(value in text for value in values)


def _phase_statuses(registry: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    rows = registry.get("capability_phases")
    if not isinstance(rows, list):
        return result
    for raw in rows:
        if isinstance(raw, dict):
            row = cast(dict[str, Any], raw)
            code, status = row.get("p_code"), row.get("baseline_status")
            if isinstance(code, str) and isinstance(status, str):
                result[code] = status
    return result


def _batch_for_task(task_id: str) -> tuple[str, dict[str, object]]:
    for batch_id, row in BATCH_QUALIFICATION.items():
        ids = row["task_ids"]
        if isinstance(ids, tuple) and task_id in ids:
            return batch_id, row
    return "M6-BATCH-4", {}


def _task_evidence_hashes(bundle: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for task_id in EXPECTED_TASK_IDS:
        batch_id, row = _batch_for_task(task_id)
        files = (Path(__file__),) if task_id == TASK_ID else BATCH_FILES[batch_id]
        material: dict[str, object] = {
            "task_id": task_id,
            "batch_id": batch_id,
            "protected_main_sha": row.get("protected_main_sha"),
            "run_number": row.get("run_number"),
            "actions_run_id": row.get("actions_run_id"),
            "files": {str(path.relative_to(ROOT)): _sha(path) for path in files},
        }
        if task_id == "M6-GOV-003":
            material["m7_design_issue_evidence_hash"] = _canonical_hash(_issue(bundle, 155))
        result[task_id] = _canonical_hash(material)
    return result


def review(
    *,
    issues_path: Path,
    m5_exit_path: Path,
    expected_revision: str,
    checked_out_revision: str,
    event_name: str,
    git_ref: str,
    run_conclusion: str,
    required_jobs_success: int,
    required_jobs_total: int,
    task_baseline_path: Path = TASK_BASELINE,
    lock_path: Path = LOCK_PATH,
    authority_path: Path = AUTHORITY_PATH,
    dto_path: Path = DTO_PATH,
    profile_path: Path = PROFILE_PATH,
    registry_path: Path = REGISTRY_PATH,
    batch1_test_path: Path = BATCH1_TEST,
    batch2_test_path: Path = BATCH2_TEST,
    batch3_test_path: Path = BATCH3_TEST,
    batch3_review_path: Path = BATCH3_REVIEW,
    historical_source_paths: tuple[Path, ...] = HISTORICAL_SOURCES,
) -> dict[str, Any]:
    issues, m5_exit = _json(issues_path), _json(m5_exit_path)
    tasks, lock = _json(task_baseline_path), _json(lock_path)
    authority, dto = _json(authority_path), _json(dto_path)
    profile, registry = _json(profile_path), _json(registry_path)

    rows = tasks.get("tasks")
    task_ids = (
        tuple(
            str(cast(dict[str, Any], row).get("task_id"))
            for row in rows
            if isinstance(row, dict)
        )
        if isinstance(rows, list)
        else ()
    )
    lock_hashes = _lock_hashes(lock)
    dto_contracts = cast(dict[str, Any], dto.get("contracts", {}))
    p2_dto_subset_hash = _p2_dto_subset_hash(dto_contracts)
    admission_dto = cast(dict[str, Any], dto_contracts.get("P2AdmissionStateDTO", {}))
    fields = admission_dto.get("fields")
    admission_fields = (
        tuple(
            str(cast(dict[str, Any], row).get("field"))
            for row in fields
            if isinstance(row, dict)
        )
        if isinstance(fields, list)
        else ()
    )
    activation = cast(dict[str, Any], authority.get("activation_rule", {}))
    admission_guard = cast(dict[str, Any], authority.get("admission_guard", {}))
    scope = cast(dict[str, Any], authority.get("scope", {}))
    profile_activation = cast(dict[str, Any], profile.get("activation_rule", {}))
    profile_source = cast(dict[str, Any], profile.get("source_bindings", {}))
    baseline_info = cast(dict[str, Any], lock.get("baseline", {}))
    m5_acceptance = cast(dict[str, Any], m5_exit.get("acceptance", {}))
    m5_scope = cast(dict[str, Any], m5_exit.get("scope", {}))
    phases = _phase_statuses(registry)
    evidence_hashes = _task_evidence_hashes(issues)

    acceptance = {
        "source_revision_exact": expected_revision == checked_out_revision and _is_sha(expected_revision),
        "baseline_task_count_exact_17": (
            tasks.get("task_count") == 17
            and task_ids == EXPECTED_TASK_IDS
            and len(set(task_ids)) == 17
        ),
        "task_evidence_exact_17": (
            len(evidence_hashes) == 17
            and set(evidence_hashes) == set(EXPECTED_TASK_IDS)
            and all(len(value) == 64 for value in evidence_hashes.values())
        ),
        "c3_issues_closed": all(_issue_state(issues, n) == "closed" for n in (151, 159, 161)),
        "batch_trackers_closed": all(_issue_state(issues, n) == "closed" for n in (156, 158, 164)),
        "batch_protected_main_evidence_exact": _batch_issue_evidence_exact(issues),
        "m7_design_runway_exact": _m7_runway_exact(issues),
        "program_and_exit_tracker_lifecycle_valid": (
            _program_and_exit_tracker_lifecycle_valid(issues)
        ),
        "authority_lock_exact": (
            lock_hashes.get("P2_ATTRIBUTION_NORMALIZATION_AUTHORITY.json") == _sha(authority_path)
            and authority.get("authority_id") == "P2_ATTRIBUTION_NORMALIZATION_AUTHORITY"
            and authority.get("version") == "1.0.0"
        ),
        "dto_lock_exact": (
            lock_hashes.get("CROSS_LAYER_DTO_CONTRACTS.json") == _sha(dto_path)
            and admission_fields
            == (
                "source_revision", "event_name", "git_ref", "protected_main",
                "m6_exit_decision", "run_conclusion", "required_jobs_success",
                "required_jobs_total", "p3_p6_inactive",
            )
        ),
        "execution_profile_lock_exact": (
            lock_hashes.get("P2_LINEAR_REFERENCE_ADJUSTMENT_PROFILE.json") == _sha(profile_path)
            and profile.get("profile_id") == "P2_LINEAR_REFERENCE_ADJUSTMENT"
            and profile.get("version") == "1.0.0"
            and profile_source.get("p2_authority_sha256") == _sha(authority_path)
            and profile_source.get("cross_layer_dto_sha256") == EXPECTED_M6_DTO_SHA256
            and p2_dto_subset_hash == EXPECTED_P2_DTO_SUBSET_SHA256
        ),
        "admission_guard_exact": (
            activation.get("authority_adoption_does_not_admit_p2") is True
            and activation.get("p2_admission_requires_protected_main_m6_exit_go") is True
            and admission_guard.get("required_event") == "push"
            and admission_guard.get("required_git_ref") == "refs/heads/main"
            and admission_guard.get("required_m6_exit_decision") == "GO"
            and admission_guard.get("required_run_conclusion") == "success"
            and admission_guard.get("required_job_count") == 14
            and profile_activation.get("profile_adoption_does_not_admit_p2") is True
            and profile_activation.get("p2_external_claim_requires_protected_main_m6_exit_go") is True
        ),
        "db_schema_1_6_0_no_shadow_schema": (
            baseline_info.get("db_schema") in {"1.6.0", "1.7.0", "1.8.0", "1.9.0"}
            and authority.get("db_schema_version") == "1.6.0"
            and profile.get("db_schema_version") == "1.6.0"
            and scope.get("db_schema_change") is False
            and scope.get("shadow_schema_permitted") is False
        ),
        "batch1_leakage_admission_negative_suite_present": _tokens(
            batch1_test_path,
            (
                "FAIL_CLOSED_P2_FUTURE_INFORMATION",
                "FAIL_CLOSED_P2_SAME_EPISODE_LEAKAGE",
                "FAIL_CLOSED_P2_NOT_ADMITTED",
            ),
        ),
        "batch2_identifiability_uncertainty_golden_present": _tokens(
            batch2_test_path,
            (
                "NOT_IDENTIFIABLE",
                "MODEL_CONDITIONED_ASSOCIATION",
                "ASSOCIATION_ONLY",
                "test_m6_tst_003_jackknife_fold_failure_fails_closed",
                "case.bundle.target.observed_value == original_observed",
            ),
        ),
        "batch3_ui_replay_p1_non_regression_present": (
            _tokens(
                batch3_test_path,
                (
                    "P2_NOT_IDENTIFIABLE",
                    "logical_product_hash",
                    "MODEL_CONDITIONED_ASSOCIATION",
                    "ASSOCIATION_ONLY",
                    'phases["P2"] == "DESIGN_CONTRACT_FROZEN"',
                ),
            )
            and _tokens(
                batch3_review_path,
                (
                    "Windows and Linux CI jobs",
                    "P1 observed and P2 adjusted",
                    "no P2 external admission",
                    "M7/P3",
                ),
            )
        ),
        "historical_current_latest_recompute_forbidden": _paths_clean(historical_source_paths),
        "m5_product_gates_retained": (
            m5_exit.get("status") == "PASS"
            and m5_exit.get("failed_acceptance") == []
            and m5_exit.get("task_count") == 23
            and m5_exit.get("exact_evidence_manifest_accepted") is True
            and m5_acceptance.get("task_evidence_exact_23") is True
            and m5_scope.get("db_schema_version") == "1.6.0"
        ),
        "p1_immutable_p2_registry_not_pre_mutated": (
            phases.get("P1") == "CURRENT_BASELINE"
            and phases.get("P2") == "DESIGN_CONTRACT_FROZEN"
        ),
        "p3_p6_inactive": all(
            phases.get(code) == "DESIGN_CONTRACT_FROZEN" for code in ("P3", "P4", "P5", "P6")
        ),
    }
    failed = sorted(key for key, value in acceptance.items() if value is not True)
    implementation_complete = not failed
    protected_main = (
        event_name == "push"
        and git_ref == "refs/heads/main"
        and expected_revision == checked_out_revision
    )
    ci_complete = (
        run_conclusion == "success"
        and required_jobs_success == required_jobs_total == 14
    )
    decision = (
        "GO"
        if implementation_complete and protected_main and ci_complete
        else "PENDING_PROTECTED_MAIN"
        if implementation_complete
        else "NO_GO"
    )
    p2_admitted = decision == "GO"
    p3_p6_inactive = acceptance["p3_p6_inactive"] is True
    task_acceptance = {task_id: implementation_complete for task_id in EXPECTED_TASK_IDS}
    task_acceptance[TASK_ID] = p2_admitted

    return {
        "schema": "TPAA_M6_EXIT_REVIEW_V1",
        "task_id": TASK_ID,
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if implementation_complete else "FAIL",
        "decision": decision,
        "implementation_complete": implementation_complete,
        "task_complete": p2_admitted,
        "formal_completion_blocked_by_protected_main": implementation_complete and not p2_admitted,
        "source_revision": expected_revision,
        "checked_out_revision": checked_out_revision,
        "event_name": event_name,
        "git_ref": git_ref,
        "protected_main_exact": protected_main,
        "run_conclusion": run_conclusion,
        "required_jobs_success": required_jobs_success,
        "required_jobs_total": required_jobs_total,
        "task_count": 17,
        "task_ids": list(EXPECTED_TASK_IDS),
        "task_acceptance": task_acceptance,
        "task_evidence_hashes": evidence_hashes,
        "batch_qualification": BATCH_QUALIFICATION,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "p2_admitted": p2_admitted,
        "qualification": (
            "P2_M6_QUALIFIED" if p2_admitted else "M6_CANDIDATE_NOT_FORMALLY_QUALIFIED"
        ),
        "admission_state": {
            "source_revision": expected_revision,
            "event_name": event_name,
            "git_ref": git_ref,
            "protected_main": protected_main,
            "m6_exit_decision": decision,
            "run_conclusion": run_conclusion,
            "required_jobs_success": required_jobs_success,
            "required_jobs_total": required_jobs_total,
            "p3_p6_inactive": p3_p6_inactive,
        },
        "unresolved_risks": [] if not failed else [{"kind": "acceptance", "items": failed}],
        "scope": {
            "p1_immutable": True,
            "p2_admitted": p2_admitted,
            "p3_p6_inactive": p3_p6_inactive,
            "db_schema_version": "1.6.0",
            "shadow_schema_created": False,
            "capability_phase_registry_mutated_for_runtime_admission": False,
            "protected_main_required_for_go": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issues", type=Path, required=True)
    parser.add_argument("--m5-exit", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--checked-out-revision", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--git-ref", required=True)
    parser.add_argument("--run-conclusion", required=True)
    parser.add_argument("--required-jobs-success", type=int, required=True)
    parser.add_argument("--required-jobs-total", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = review(
            issues_path=args.issues,
            m5_exit_path=args.m5_exit,
            expected_revision=args.expected_revision,
            checked_out_revision=args.checked_out_revision,
            event_name=args.event_name,
            git_ref=args.git_ref,
            run_conclusion=args.run_conclusion,
            required_jobs_success=args.required_jobs_success,
            required_jobs_total=args.required_jobs_total,
        )
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M6_EXIT_REVIEW_V1",
            "task_id": TASK_ID,
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "decision": "NO_GO",
            "implementation_complete": False,
            "task_complete": False,
            "p2_admitted": False,
            "source_revision": args.expected_revision,
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
