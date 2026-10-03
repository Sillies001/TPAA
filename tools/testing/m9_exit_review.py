#!/usr/bin/env python3
"""M9-EXIT-001 exact M9 Exit review and C4 P6 admission decision."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
CANONICAL = BASELINE / "canonical"
TASK_BASELINE = ROOT / "docs" / "baseline" / "SDIB-1.8" / "M9_TASK_BASELINE.json"
LOCK_PATH = BASELINE / "BASELINE_LOCK.json"
AUTHORITY_PATH = CANONICAL / "P6_PREDICTION_COUNTERFACTUAL_AUTHORITY.json"
ROLE_PROFILE_PATH = CANONICAL / "P6_ROLE_PRIVACY_RELEASE_PROFILE.json"
EXECUTION_PROFILE_PATH = (
    CANONICAL / "P6_P3_CAPABILITY_OLS_MAD_FORECAST_PROFILE.json"
)
DTO_PATH = CANONICAL / "CROSS_LAYER_DTO_CONTRACTS.json"
REGISTRY_PATH = CANONICAL / "CAPABILITY_PHASE_REGISTRY.json"

C3_REVIEW = (
    ROOT
    / "docs"
    / "reviews"
    / "M9_C3_P6_PREDICTION_COUNTERFACTUAL_AUTHORITY_REVIEW.md"
)
BATCH1_REVIEW = ROOT / "docs" / "reviews" / "M9_BATCH1_INPUT_INTEROP_REVIEW.md"
BATCH2_REVIEW = ROOT / "docs" / "reviews" / "M9_BATCH2_MODEL_FORECAST_REVIEW.md"
PROFILE_REVIEW = (
    ROOT
    / "docs"
    / "reviews"
    / "M9_BATCH2_P6_EXECUTION_PROFILE_ADOPTION_REVIEW.md"
)
BATCH3_REVIEW = (
    ROOT
    / "docs"
    / "reviews"
    / "M9_BATCH3_COUNTERFACTUAL_ADVISORY_API_GUI_SECURITY_REVIEW.md"
)
EXIT_REVIEW = ROOT / "docs" / "reviews" / "M9_BATCH4_EXIT_ADMISSION_REVIEW.md"

BATCH1_TEST = ROOT / "tests" / "contract" / "test_m9_batch_1_input_interop.py"
BATCH2_TEST = ROOT / "tests" / "contract" / "test_m9_batch_2_model_forecast.py"
BATCH3_TEST = (
    ROOT
    / "tests"
    / "contract"
    / "test_m9_batch_3_counterfactual_advisory_api_gui_security.py"
)

GOVERNANCE_SOURCE = ROOT / "src" / "tpaa_context" / "p6_governance.py"
INPUT_SOURCE = ROOT / "src" / "tpaa_capability" / "p6_input.py"
INTEROP_SOURCE = ROOT / "src" / "tpaa_ingest" / "p6_interop.py"
FORECAST_SOURCE = ROOT / "src" / "tpaa_capability" / "p6_forecast.py"
REPLAY_SOURCE = ROOT / "src" / "tpaa_longitudinal" / "p6_replay.py"
GOLDEN_PATH = ROOT / "tests" / "fixtures" / "m9" / "p6_model_forecast_golden.json"
COUNTERFACTUAL_SOURCE = ROOT / "src" / "tpaa_capability" / "p6_counterfactual.py"
RECOMMENDATION_SOURCE = ROOT / "src" / "tpaa_assessment" / "p6_recommendation.py"
APPLICATION_SOURCE = ROOT / "src" / "tpaa_application" / "m9_workspace.py"
API_SOURCE = ROOT / "src" / "tpaa_api" / "m9_app.py"
GUI_SOURCE = ROOT / "src" / "tpaa_gui" / "m9_workspace.py"
SECURITY_SOURCE = ROOT / "src" / "tpaa_context" / "p6_runtime_security.py"

TASK_ID = "M9-EXIT-001"
TRACKING_ISSUE = 198

EXPECTED_AUTHORITY_SHA256 = (
    "a138c97e6c9891f767ee25de8841e2bc9ca899ddf6d09b98b9e4bae73d9be79e"
)
EXPECTED_ROLE_PROFILE_SHA256 = (
    "d5eff80dbfa912955ae7b09bc3e4a2868650466560cb1a5b1f558434e8076713"
)
EXPECTED_EXECUTION_PROFILE_SHA256 = (
    "6a064762b4edde3448b25e5b74384708745793acc863a8adfbfad40fc7651394"
)
EXPECTED_DTO_SHA256 = (
    "28f7209e40709fb4eb53ceffdfee3542e867f060c4e63605cc1ad149a8e3819a"
)
EXPECTED_LOCK_SHA256 = (
    "9920b59601d8441f883879e813164f33ee5c02db81aa5e1b759e3a1772469e51"
)
EXPECTED_PARENT_C3_LOCK_SHA256 = (
    "ba4f152a09206bcbaf06a1882d08763b332e95068ada0404a969073a7dc13a08"
)

P6_DTO_NAMES = (
    "P6InputSnapshotDTO",
    "P6ModelRevisionDTO",
    "P6ForecastRequestDTO",
    "P6ForecastResultDTO",
    "P6CounterfactualRequestDTO",
    "P6CounterfactualResultDTO",
    "P6RecommendationDTO",
    "P6InteropSnapshotDTO",
    "P6AdmissionStateDTO",
)

ADMISSION_FIELDS = (
    "source_revision",
    "event_name",
    "git_ref",
    "protected_main",
    "m9_exit_decision",
    "run_conclusion",
    "required_jobs_success",
    "required_jobs_total",
    "p6_admitted",
)

EXPECTED_TASK_IDS = (
    "M9-GOV-001",
    "M9-DATA-001",
    "M9-INTEROP-001",
    "M9-MODEL-001",
    "M9-MODEL-002",
    "M9-PROJ-001",
    "M9-LONG-001",
    "M9-TST-001",
    "M9-CF-001",
    "M9-ASSESS-001",
    "M9-API-001",
    "M9-GUI-001",
    "M9-SEC-001",
    "M9-TST-002",
    "M9-EXIT-001",
)

QUALIFICATION: dict[int, dict[str, object]] = {
    193: {
        "label": "M9-BASELINE",
        "protected_main_sha": "ffbd5e5f0561ce39d8736de765dd6be240edfae1",
        "run_number": 529,
        "actions_run_id": 36876431677,
    },
    194: {
        "label": "M9-C3",
        "protected_main_sha": "7628e6caad30f76179d7fbfcf8e600ef80ccc314",
        "run_number": 531,
        "actions_run_id": 36952909234,
    },
    195: {
        "label": "M9-BATCH-1",
        "protected_main_sha": "47858360a8409fa9370a4e622f3dc3b308593fdc",
        "run_number": 535,
        "actions_run_id": 36960346928,
    },
    196: {
        "label": "M9-BATCH-2",
        "protected_main_sha": "d37a994d6efbaeec2d10022ec083015771c40152",
        "run_number": 542,
        "actions_run_id": 36981630238,
    },
    197: {
        "label": "M9-BATCH-3",
        "protected_main_sha": "87e99b4ea3e55b60ef29a45adfc5e6ad7946bc0e",
        "run_number": 546,
        "actions_run_id": 36993939363,
    },
}

PROFILE_QUALIFICATION = {
    "profile_id": "P6_P3_CAPABILITY_OLS_MAD_FORECAST",
    "profile_version": "1.0.0",
    "profile_sha256": EXPECTED_EXECUTION_PROFILE_SHA256,
    "protected_main_sha": "9d6c70133e1994c5823bbe6efb499001b5aa697c",
    "run_number": 540,
    "actions_run_id": 36968525803,
}

BATCH_FILES: dict[str, tuple[Path, ...]] = {
    "M9-BATCH-1": (
        C3_REVIEW,
        BATCH1_REVIEW,
        BATCH1_TEST,
        GOVERNANCE_SOURCE,
        INPUT_SOURCE,
        INTEROP_SOURCE,
    ),
    "M9-BATCH-2": (
        PROFILE_REVIEW,
        BATCH2_REVIEW,
        BATCH2_TEST,
        EXECUTION_PROFILE_PATH,
        FORECAST_SOURCE,
        REPLAY_SOURCE,
        GOLDEN_PATH,
    ),
    "M9-BATCH-3": (
        BATCH3_REVIEW,
        BATCH3_TEST,
        COUNTERFACTUAL_SOURCE,
        RECOMMENDATION_SOURCE,
        APPLICATION_SOURCE,
        API_SOURCE,
        GUI_SOURCE,
        SECURITY_SOURCE,
    ),
}

BATCH_FOR_TASK = {
    **{task_id: "M9-BATCH-1" for task_id in EXPECTED_TASK_IDS[0:3]},
    **{task_id: "M9-BATCH-2" for task_id in EXPECTED_TASK_IDS[3:8]},
    **{task_id: "M9-BATCH-3" for task_id in EXPECTED_TASK_IDS[8:14]},
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
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
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
            name = row.get("file")
            sha = row.get("sha256")
            if isinstance(name, str) and isinstance(sha, str):
                result[name] = sha
    return result


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
            code = row.get("p_code")
            status = row.get("baseline_status")
            if isinstance(code, str) and isinstance(status, str):
                result[code] = status
    return result


def _entry_qualification_exact(tasks: dict[str, Any]) -> bool:
    entry = tasks.get("entry_evidence")
    if not isinstance(entry, dict):
        return False
    value = cast(dict[str, Any], entry)
    return (
        value.get("predecessor_milestone") == "M8"
        and value.get("protected_main_sha")
        == "06b9f0c55dda803765fc265b8d5ca0353620476f"
        and value.get("protected_main_run_number") == 527
        and value.get("protected_main_actions_run_id") == 36869057230
        and value.get("p4_p5_qualification") == "P4_P5_M8_QUALIFIED"
        and value.get("m8_exit_decision") == "GO"
        and value.get("p4_admitted") is True
        and value.get("p5_admitted") is True
        and value.get("p6_inactive") is True
        and value.get("protected_main_exact") is True
        and value.get("hosted_ci_required_jobs") == 14
        and value.get("hosted_ci_result") == "PASS"
    )


def _qualification_chain_exact(bundle: dict[str, Any]) -> bool:
    for issue_number, row in QUALIFICATION.items():
        if _issue_state(bundle, issue_number) != "closed":
            return False
        issue_text = _issue_text(bundle, issue_number)
        tokens = (
            cast(str, row["protected_main_sha"]),
            f"Run #{cast(int, row['run_number'])}",
            str(cast(int, row["actions_run_id"])),
        )
        if not all(token in issue_text for token in tokens):
            return False
        if "14/14 SUCCESS" not in issue_text and "14 of 14 SUCCESS" not in issue_text:
            return False
    return True


def _profile_qualification_exact(bundle: dict[str, Any]) -> bool:
    issue_text = _issue_text(bundle, 196)
    tokens = (
        cast(str, PROFILE_QUALIFICATION["profile_id"]),
        cast(str, PROFILE_QUALIFICATION["profile_version"]),
        cast(str, PROFILE_QUALIFICATION["profile_sha256"]),
        cast(str, PROFILE_QUALIFICATION["protected_main_sha"]),
        f"Run #{cast(int, PROFILE_QUALIFICATION['run_number'])}",
        str(cast(int, PROFILE_QUALIFICATION["actions_run_id"])),
    )
    return all(token in issue_text for token in tokens) and (
        "14/14 SUCCESS" in issue_text or "14 of 14 SUCCESS" in issue_text
    )


def _program_exit_lifecycle_valid(bundle: dict[str, Any]) -> bool:
    program_state = _issue_state(bundle, 149)
    if program_state not in ("open", "closed"):
        return False
    if program_state == "closed":
        if "P6_M9_QUALIFIED" not in _issue_text(bundle, 149):
            return False

    exit_state = _issue_state(bundle, TRACKING_ISSUE)
    if exit_state == "open":
        return True
    if exit_state != "closed":
        return False
    exit_text = _issue_text(bundle, TRACKING_ISSUE)
    return all(
        token in exit_text
        for token in (
            "P6_M9_QUALIFIED",
            "p6_admitted=true",
            "failed_acceptance=[]",
            "decision=GO",
            "14/14 SUCCESS",
        )
    )


def _task_evidence_hashes(issues: dict[str, Any]) -> dict[str, str]:
    issue_for_batch = {
        "M9-BATCH-1": 195,
        "M9-BATCH-2": 196,
        "M9-BATCH-3": 197,
    }
    result: dict[str, str] = {}
    for task_id in EXPECTED_TASK_IDS:
        if task_id == TASK_ID:
            material: dict[str, object] = {
                "task_id": task_id,
                "batch_id": "M9-BATCH-4",
                "tracking_issue": TRACKING_ISSUE,
                "files": {
                    str(path.relative_to(ROOT)): _sha(path)
                    for path in (Path(__file__), EXIT_REVIEW)
                },
                "issue_evidence_hash": _canonical_hash(
                    _issue(issues, TRACKING_ISSUE)
                ),
            }
        else:
            batch_id = BATCH_FOR_TASK[task_id]
            issue_number = issue_for_batch[batch_id]
            qualification = QUALIFICATION[issue_number]
            material = {
                "task_id": task_id,
                "batch_id": batch_id,
                "tracking_issue": issue_number,
                "protected_main_sha": qualification["protected_main_sha"],
                "run_number": qualification["run_number"],
                "actions_run_id": qualification["actions_run_id"],
                "files": {
                    str(path.relative_to(ROOT)): _sha(path)
                    for path in BATCH_FILES[batch_id]
                },
                "issue_evidence_hash": _canonical_hash(
                    _issue(issues, issue_number)
                ),
            }
        result[task_id] = _canonical_hash(material)
    return result


def _paths_clean(paths: tuple[Path, ...]) -> bool:
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    return all(
        token not in source
        for token in (
            '"/latest"',
            '"/current"',
            '"/default"',
            "sqlite3",
            "psycopg",
            "tpaa_storage",
        )
    )


def review(
    *,
    issues_path: Path,
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
    role_profile_path: Path = ROLE_PROFILE_PATH,
    execution_profile_path: Path = EXECUTION_PROFILE_PATH,
    dto_path: Path = DTO_PATH,
    registry_path: Path = REGISTRY_PATH,
    batch1_test_path: Path = BATCH1_TEST,
    batch2_test_path: Path = BATCH2_TEST,
    batch3_test_path: Path = BATCH3_TEST,
    input_source_path: Path = INPUT_SOURCE,
    interop_source_path: Path = INTEROP_SOURCE,
    forecast_source_path: Path = FORECAST_SOURCE,
    replay_source_path: Path = REPLAY_SOURCE,
    counterfactual_source_path: Path = COUNTERFACTUAL_SOURCE,
    recommendation_source_path: Path = RECOMMENDATION_SOURCE,
    application_source_path: Path = APPLICATION_SOURCE,
    api_source_path: Path = API_SOURCE,
    gui_source_path: Path = GUI_SOURCE,
    security_source_path: Path = SECURITY_SOURCE,
) -> dict[str, Any]:
    issues = _json(issues_path)
    tasks = _json(task_baseline_path)
    lock = _json(lock_path)
    authority = _json(authority_path)
    role_profile = _json(role_profile_path)
    execution_profile = _json(execution_profile_path)
    dto = _json(dto_path)
    registry = _json(registry_path)

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
    baseline_info = cast(dict[str, Any], lock.get("baseline", {}))
    lineage = cast(list[Any], baseline_info.get("lock_lineage_sha256", []))
    authority_scope = cast(dict[str, Any], authority.get("scope", {}))
    authority_activation = cast(
        dict[str, Any],
        authority.get("activation_rule", {}),
    )
    admission_guard = cast(dict[str, Any], authority.get("admission_guard", {}))
    role_scope = cast(dict[str, Any], role_profile.get("scope", {}))
    role_activation = cast(
        dict[str, Any],
        role_profile.get("activation_rule", {}),
    )
    role_projection = cast(
        dict[str, Any],
        role_profile.get("projection_contract", {}),
    )
    profile_scope = cast(dict[str, Any], execution_profile.get("scope", {}))
    profile_activation = cast(
        dict[str, Any],
        execution_profile.get("activation_rule", {}),
    )
    dto_contracts = cast(dict[str, Any], dto.get("contracts", {}))
    admission = cast(
        dict[str, Any],
        dto_contracts.get("P6AdmissionStateDTO", {}),
    )
    admission_rows = admission.get("fields")
    admission_fields = (
        tuple(
            str(cast(dict[str, Any], row).get("field"))
            for row in admission_rows
            if isinstance(row, dict)
        )
        if isinstance(admission_rows, list)
        else ()
    )
    phases = _phase_statuses(registry)
    evidence_hashes = _task_evidence_hashes(issues)

    acceptance = {
        "source_revision_exact": (
            expected_revision == checked_out_revision
            and _is_sha(expected_revision)
        ),
        "baseline_task_count_exact_15": (
            tasks.get("task_count") == 15
            and task_ids == EXPECTED_TASK_IDS
            and len(set(task_ids)) == 15
        ),
        "task_evidence_exact_15": (
            len(evidence_hashes) == 15
            and set(evidence_hashes) == set(EXPECTED_TASK_IDS)
            and all(len(value) == 64 for value in evidence_hashes.values())
        ),
        "m8_entry_qualification_exact": _entry_qualification_exact(tasks),
        "baseline_c3_and_batches_closed": all(
            _issue_state(issues, number) == "closed"
            for number in (193, 194, 195, 196, 197)
        ),
        "qualification_chain_exact": _qualification_chain_exact(issues),
        "execution_profile_qualification_exact": _profile_qualification_exact(
            issues
        ),
        "program_exit_lifecycle_valid": _program_exit_lifecycle_valid(issues),
        "authority_role_profile_dto_lock_exact": (
            _sha(authority_path) == EXPECTED_AUTHORITY_SHA256
            and _sha(role_profile_path) == EXPECTED_ROLE_PROFILE_SHA256
            and _sha(execution_profile_path)
            == EXPECTED_EXECUTION_PROFILE_SHA256
            and _sha(dto_path) == EXPECTED_DTO_SHA256
            and (
                _sha(lock_path) == EXPECTED_LOCK_SHA256
                or EXPECTED_LOCK_SHA256 in lineage
            )
            and lock_hashes.get("P6_PREDICTION_COUNTERFACTUAL_AUTHORITY.json")
            == EXPECTED_AUTHORITY_SHA256
            and lock_hashes.get("P6_ROLE_PRIVACY_RELEASE_PROFILE.json")
            == EXPECTED_ROLE_PROFILE_SHA256
            and lock_hashes.get(
                "P6_P3_CAPABILITY_OLS_MAD_FORECAST_PROFILE.json"
            )
            == EXPECTED_EXECUTION_PROFILE_SHA256
            and lock_hashes.get("CROSS_LAYER_DTO_CONTRACTS.json")
            == EXPECTED_DTO_SHA256
            and EXPECTED_PARENT_C3_LOCK_SHA256 in lineage
            and authority.get("authority_id")
            == "P6_PREDICTION_COUNTERFACTUAL_AUTHORITY"
            and authority.get("version") == "1.0.0"
            and role_profile.get("profile_id")
            == "P6_ROLE_PRIVACY_RELEASE_PROFILE"
            and role_profile.get("version") == "1.0.0"
            and execution_profile.get("profile_id")
            == "P6_P3_CAPABILITY_OLS_MAD_FORECAST"
            and execution_profile.get("version") == "1.0.0"
        ),
        "db_schema_1_6_0_no_shadow_schema": (
            baseline_info.get("db_schema") in {"1.6.0", "1.7.0", "1.8.0"}
            and authority.get("db_schema_version") == "1.6.0"
            and role_profile.get("db_schema_version") == "1.6.0"
            and execution_profile.get("db_schema_version") == "1.6.0"
            and authority_scope.get("db_schema_change") is False
            and authority_scope.get("shadow_schema_permitted") is False
            and role_scope.get("db_schema_change") is False
            and role_scope.get("shadow_schema_permitted") is False
            and profile_scope.get("db_schema_change") is False
            and profile_scope.get("shadow_schema_permitted") is False
        ),
        "admission_dto_and_guard_exact": (
            all(name in dto_contracts for name in P6_DTO_NAMES)
            and admission_fields == ADMISSION_FIELDS
            and authority_activation.get("authority_adoption_does_not_admit_p6")
            is True
            and authority_activation.get(
                "p6_admission_requires_protected_main_m9_exit_go"
            )
            is True
            and role_activation.get("profile_adoption_does_not_admit_p6")
            is True
            and role_activation.get(
                "p6_external_claim_requires_protected_main_m9_exit_go"
            )
            is True
            and profile_activation.get("profile_adoption_does_not_admit_p6")
            is True
            and profile_activation.get(
                "p6_external_claim_requires_protected_main_m9_exit_go"
            )
            is True
            and admission_guard.get("required_event") == "push"
            and admission_guard.get("required_git_ref") == "refs/heads/main"
            and admission_guard.get("required_m9_exit_decision") == "GO"
            and admission_guard.get("required_run_conclusion") == "success"
            and admission_guard.get("required_job_count") == 14
            and admission_guard.get("p6_external_claim_before_gate_forbidden")
            is True
        ),
        "batch1_input_interop_gates": (
            _tokens(
                batch1_test_path,
                (
                    "test_m9_batch1_policy_and_input_identity_are_exact",
                    "test_m9_batch1_alias_future_same_outcome_and_overlap_fail_closed",
                    "test_m9_batch1_unavailable_and_ood_zero_coercion_fail_closed",
                    "test_m9_batch1_interop_alias_lossy_conflation_and_future_fail_closed",
                    "test_m9_batch1_p6_release_and_p1_p5_mutation_remain_fail_closed",
                ),
            )
            and _tokens(
                input_source_path,
                (
                    "P6_INPUT_SHA256:",
                    "FAIL_CLOSED_P6_SAME_OUTCOME_LEAKAGE",
                    "FAIL_CLOSED_P6_TRAINING_VALIDATION_LEAKAGE",
                ),
            )
            and _tokens(
                interop_source_path,
                (
                    "P6_INTEROP_SHA256:",
                    "FAIL_CLOSED_P6_INTEROP_LOSSY_MAPPING",
                    "FAIL_CLOSED_P6_FACT_PROJECTION_CONFLATION",
                ),
            )
        ),
        "batch2_model_forecast_replay_gates": (
            _tokens(
                batch2_test_path,
                (
                    "test_m9_batch2_profile_and_linear_case_match_static_golden",
                    "test_m9_batch2_training_and_validation_snapshots_are_exact_and_disjoint",
                    "test_m9_batch2_out_of_domain_row_is_excluded_never_zero_filled",
                    "test_m9_batch2_missing_uncertainty_and_future_context_fail_closed",
                    "test_m9_batch2_replay_validation_never_rewrites_original_forecast",
                ),
            )
            and _tokens(
                forecast_source_path,
                (
                    "P6_P3_CAPABILITY_OLS_MAD_FORECAST",
                    "NEXT_SESSION_ORDER",
                    "FAIL_CLOSED_P6_TRAINING_VALIDATION_LEAKAGE",
                    "FAIL_CLOSED_P6_UNCERTAINTY_REQUIRED",
                ),
            )
            and _tokens(
                replay_source_path,
                (
                    "Exact-ID immutable replay registry",
                    "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
                ),
            )
        ),
        "batch3_counterfactual_advisory_security_gates": (
            _tokens(
                batch3_test_path,
                (
                    "test_m9_batch3_exact_projection_graph_is_deterministic_and_non_causal",
                    "test_m9_batch3_recommendation_is_advisory_and_approval_is_separated",
                    "test_m9_batch3_command_and_causal_upgrades_fail_closed",
                    "test_m9_batch3_pre_exit_export_and_admin_business_approval_fail_closed",
                    "test_m9_batch3_security_audit_excludes_sensitive_payloads",
                    "test_m9_batch3_p1_p5_authority_hashes_and_db_schema_remain_immutable",
                ),
            )
            and _tokens(
                counterfactual_source_path,
                (
                    "SCENARIO_PROJECTION_NON_CAUSAL",
                    "SCENARIO_ONLY_NON_CAUSAL",
                    "FAIL_CLOSED_P6_CAUSAL_CLAIM_NOT_AUTHORIZED",
                ),
            )
            and _tokens(
                recommendation_source_path,
                (
                    "FAIL_CLOSED_P6_RECOMMENDATION_COMMAND_UPGRADE",
                    "FAIL_CLOSED_P6_APPLICABILITY_REQUIRED",
                ),
            )
        ),
        "api_gui_exact_ids_no_alias_recompute": (
            _tokens(
                api_source_path,
                (
                    "/m9/models/{capability_model_id}",
                    "/m9/forecasts/{forecast_result_id}",
                    "/m9/counterfactuals/{counterfactual_run_id}",
                    "/m9/recommendations/{recommendation_id}",
                    "/m9/models/{capability_model_id}/release",
                ),
            )
            and _tokens(
                gui_source_path,
                (
                    "P1_P5_FACTUAL_HISTORY",
                    "P6_FORECAST_PROJECTION",
                    "P6_COUNTERFACTUAL_PROJECTION",
                    "P6_TRAINING_ADVISORY",
                    "business_recompute=False",
                    "persistence_access=False",
                    "projection_to_fact_upgrade=False",
                ),
            )
            and _paths_clean(
                (
                    application_source_path,
                    api_source_path,
                    gui_source_path,
                )
            )
        ),
        "role_privacy_release_boundary_exact": (
            role_scope.get("default_deny") is True
            and role_scope.get("direct_identity_default") is False
            and role_scope.get("separation_of_model_release_and_business_approval")
            is True
            and role_projection.get("default_subject_projection") == "subject_key"
            and _tokens(
                security_source_path,
                (
                    "INSTRUCTOR_EVALUATOR",
                    "MODEL_REVIEWER",
                    "export_authorized",
                    "FAIL_CLOSED_P6_AUTHORITY_REQUIRED",
                ),
            )
        ),
        "p1_p5_immutable_p6_candidate_registry": (
            phases.get("P1") == "CURRENT_BASELINE"
            and all(
                phases.get(code) == "DESIGN_CONTRACT_FROZEN"
                for code in ("P2", "P3", "P4", "P5", "P6")
            )
            and authority_scope.get("p1_p5_historical_products_immutable") is True
            and authority_scope.get("p6_authority_frozen_not_admitted") is True
            and profile_scope.get("p1_p5_historical_products_immutable") is True
        ),
        "required_ci_exact_14": (
            run_conclusion == "success"
            and required_jobs_success == required_jobs_total == 14
        ),
    }

    failed = sorted(key for key, value in acceptance.items() if value is not True)
    implementation_complete = not failed
    protected_main = (
        event_name == "push"
        and git_ref == "refs/heads/main"
        and expected_revision == checked_out_revision
        and _is_sha(expected_revision)
    )
    decision = (
        "GO"
        if implementation_complete and protected_main
        else "PENDING_PROTECTED_MAIN"
        if implementation_complete
        else "NO_GO"
    )
    p6_admitted = decision == "GO"
    task_acceptance = {
        task_id: implementation_complete
        for task_id in EXPECTED_TASK_IDS
    }
    task_acceptance[TASK_ID] = p6_admitted

    return {
        "schema": "TPAA_M9_EXIT_REVIEW_V1",
        "milestone": "M9",
        "capability": "P6",
        "task_id": TASK_ID,
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if implementation_complete else "FAIL",
        "decision": decision,
        "implementation_complete": implementation_complete,
        "task_complete": p6_admitted,
        "formal_completion_blocked_by_protected_main": (
            implementation_complete and not p6_admitted
        ),
        "source_revision": expected_revision,
        "checked_out_revision": checked_out_revision,
        "event": event_name,
        "event_name": event_name,
        "git_ref": git_ref,
        "protected_main_exact": protected_main,
        "run_conclusion": run_conclusion,
        "required_jobs_success": required_jobs_success,
        "required_jobs_total": required_jobs_total,
        "task_count": 15,
        "task_ids": list(EXPECTED_TASK_IDS),
        "task_acceptance": task_acceptance,
        "task_evidence_hashes": evidence_hashes,
        "qualification_chain": QUALIFICATION,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "p6_admitted": p6_admitted,
        "qualification": (
            "P6_M9_QUALIFIED"
            if p6_admitted
            else "M9_CANDIDATE_NOT_FORMALLY_QUALIFIED"
        ),
        "admission_state": {
            "source_revision": expected_revision,
            "event_name": event_name,
            "git_ref": git_ref,
            "protected_main": protected_main,
            "m9_exit_decision": decision,
            "run_conclusion": run_conclusion,
            "required_jobs_success": required_jobs_success,
            "required_jobs_total": required_jobs_total,
            "p6_admitted": p6_admitted,
        },
        "unresolved_risks": (
            []
            if not failed
            else [{"kind": "acceptance", "items": failed}]
        ),
        "scope": {
            "p1_p5_immutable_upstream": True,
            "p6_admitted": p6_admitted,
            "db_schema_version": "1.6.0",
            "shadow_schema_created": False,
            "capability_phase_registry_mutated_for_runtime_admission": False,
            "protected_main_required_for_go": True,
            "roadmap_ends_at_m9_under_current_registry": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issues", type=Path, required=True)
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
            "schema": "TPAA_M9_EXIT_REVIEW_V1",
            "milestone": "M9",
            "capability": "P6",
            "task_id": TASK_ID,
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "decision": "NO_GO",
            "implementation_complete": False,
            "task_complete": False,
            "p6_admitted": False,
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
