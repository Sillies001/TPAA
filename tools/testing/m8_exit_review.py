#!/usr/bin/env python3
"""M8-TST-005 exact M8 Exit review and C4 P4/P5 admission decision."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
CANONICAL = BASELINE / "canonical"
TASK_BASELINE = ROOT / "docs" / "baseline" / "SDIB-1.7" / "M8_TASK_BASELINE.json"
LOCK_PATH = BASELINE / "BASELINE_LOCK.json"
AUTHORITY_PATH = CANONICAL / "P4_P5_TRAINING_ASSESSMENT_AUTHORITY.json"
ROLE_PROFILE_PATH = CANONICAL / "P4_P5_ROLE_PRIVACY_PROFILE.json"
DTO_PATH = CANONICAL / "CROSS_LAYER_DTO_CONTRACTS.json"
REGISTRY_PATH = CANONICAL / "CAPABILITY_PHASE_REGISTRY.json"

BATCH1_TEST = ROOT / "tests" / "contract" / "test_m8_batch_1_subject_composition_privacy.py"
BATCH2_TEST = ROOT / "tests" / "contract" / "test_m8_batch_2_p4_assessment_replay.py"
BATCH3_TEST = ROOT / "tests" / "contract" / "test_m8_batch_3_p5_api_gui_security.py"
BATCH1_REVIEW = ROOT / "docs" / "reviews" / "M8_BATCH1_SUBJECT_COMPOSITION_PRIVACY_REVIEW.md"
BATCH2_REVIEW = ROOT / "docs" / "reviews" / "M8_BATCH2_P4_ASSESSMENT_REPLAY_REVIEW.md"
BATCH3_REVIEW = ROOT / "docs" / "reviews" / "M8_BATCH3_P5_API_GUI_SECURITY_REVIEW.md"
M9_RUNWAY = ROOT / "docs" / "reviews" / "M9_P6_DESIGN_RUNWAY_REVIEW.md"
EXIT_REVIEW = ROOT / "docs" / "reviews" / "M8_BATCH4_EXIT_ADMISSION_REVIEW.md"

CONTEXT_SOURCE = ROOT / "src" / "tpaa_context" / "m8_p4_p5.py"
P4_SUBJECT_SOURCE = ROOT / "src" / "tpaa_assessment" / "p4_subject.py"
P4_EVIDENCE_SOURCE = ROOT / "src" / "tpaa_assessment" / "p4_evidence.py"
P4_REVISION_SOURCE = ROOT / "src" / "tpaa_assessment" / "p4_revision.py"
P5_SOURCE = ROOT / "src" / "tpaa_assessment" / "p5_assessment.py"
WORLD_SOURCE = ROOT / "src" / "tpaa_world" / "p4_p5_scope.py"
P4_REPLAY_SOURCE = ROOT / "src" / "tpaa_longitudinal" / "p4_replay.py"
P5_REPLAY_SOURCE = ROOT / "src" / "tpaa_longitudinal" / "p5_replay.py"
APPLICATION_SOURCE = ROOT / "src" / "tpaa_application" / "m8_workspace.py"
API_SOURCE = ROOT / "src" / "tpaa_api" / "m8_app.py"
GUI_SOURCE = ROOT / "src" / "tpaa_gui" / "m8_workspace.py"

TASK_ID = "M8-TST-005"
TRACKING_ISSUE = 185

EXPECTED_AUTHORITY_SHA256 = "749360544e3e403e3a81b4992797d5186c93d1f06a92e96f1352c4ab4ed4cb77"
EXPECTED_ROLE_PROFILE_SHA256 = "99a526cead816010373cdd81cd889d33fa359b5d0b74d87743e51d0f649f1113"
EXPECTED_DTO_SHA256 = "2d5ff42aa3a8fee6ed7995be0e430dee18aa36bde6fc5144fd1484532d67ee47"
EXPECTED_M8_BASELINE_LOCK_SHA256 = "d7073279fd5e8b1438fab3481f8654841b4e9445244d3b0369c5cad2cfe8111a"
EXPECTED_M8_DTO_SUBSET_SHA256 = "34c11b2c7e2bc2a1e26dacb83676f1919331e88520e634b527eef30cacd6341a"
M8_DTO_NAMES = (
    "P4SubjectContextDTO",
    "HumanMachineEvidenceDTO",
    "InstructorAnnotationDTO",
    "ApprovalStateDTO",
    "P4AssessmentRevisionDTO",
    "P5CompositionSnapshotDTO",
    "TeamMissionEvidenceDTO",
    "P5AssessmentRevisionDTO",
    "P4P5AdmissionStateDTO",
)

EXPECTED_TASK_IDS = (
    "M8-GOV-001",
    "M8-GOV-002",
    "M8-DATA-001",
    "M8-WORLD-001",
    "M8-WORLD-002",
    "M8-SEC-001",
    "M8-TST-001",
    "M8-ASSESS-001",
    "M8-ASSESS-002",
    "M8-ASSESS-003",
    "M8-LONG-001",
    "M8-TST-002",
    "M8-ASSESS-004",
    "M8-ASSESS-005",
    "M8-ASSESS-006",
    "M8-LONG-002",
    "M8-API-001",
    "M8-GUI-001",
    "M8-SEC-002",
    "M8-GOV-003",
    "M8-TST-003",
    "M8-TST-004",
    "M8-TST-005",
)

QUALIFICATION: dict[int, dict[str, object]] = {
    181: {
        "label": "M8-C3",
        "protected_main_sha": "0a704735a3e5ecb847d7ed4194aa6649280d351a",
        "run_number": 516,
        "actions_run_id": 36822713745,
    },
    182: {
        "label": "M8-BATCH-1",
        "protected_main_sha": "b212761dd57ab7abbd5c48b1fefb19a65fd5c71c",
        "run_number": 518,
        "actions_run_id": 36829110420,
    },
    183: {
        "label": "M8-BATCH-2",
        "protected_main_sha": "68881758cddca2f39b3d6f7801f2766755b8bc2f",
        "run_number": 520,
        "actions_run_id": 36838469146,
    },
    184: {
        "label": "M8-BATCH-3",
        "protected_main_sha": "eaa1a9a0f3374410cf59e82e97bef70ac18840b0",
        "run_number": 525,
        "actions_run_id": 36855927899,
    },
}

BATCH_FILES: dict[str, tuple[Path, ...]] = {
    "M8-BATCH-1": (
        BATCH1_REVIEW,
        BATCH1_TEST,
        CONTEXT_SOURCE,
        P4_SUBJECT_SOURCE,
        WORLD_SOURCE,
    ),
    "M8-BATCH-2": (
        BATCH2_REVIEW,
        BATCH2_TEST,
        P4_EVIDENCE_SOURCE,
        P4_REVISION_SOURCE,
        P4_REPLAY_SOURCE,
    ),
    "M8-BATCH-3": (
        BATCH3_REVIEW,
        BATCH3_TEST,
        P5_SOURCE,
        P5_REPLAY_SOURCE,
        APPLICATION_SOURCE,
        API_SOURCE,
        GUI_SOURCE,
        M9_RUNWAY,
    ),
}

BATCH_FOR_TASK = {
    **{task_id: "M8-BATCH-1" for task_id in EXPECTED_TASK_IDS[0:7]},
    **{task_id: "M8-BATCH-2" for task_id in EXPECTED_TASK_IDS[7:12]},
    **{task_id: "M8-BATCH-3" for task_id in EXPECTED_TASK_IDS[12:22]},
}

ADMISSION_FIELDS = (
    "source_revision",
    "event_name",
    "git_ref",
    "protected_main",
    "m8_exit_decision",
    "run_conclusion",
    "required_jobs_success",
    "required_jobs_total",
    "p4_admitted",
    "p5_admitted",
    "p6_inactive",
)


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
            name, sha = row.get("file"), row.get("sha256")
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
            code, status = row.get("p_code"), row.get("baseline_status")
            if isinstance(code, str) and isinstance(status, str):
                result[code] = status
    return result


def _batch_qualification_exact(bundle: dict[str, Any]) -> bool:
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


def _entry_qualification_exact(tasks: dict[str, Any]) -> bool:
    entry = tasks.get("entry_evidence")
    if not isinstance(entry, dict):
        return False
    value = cast(dict[str, Any], entry)
    return (
        value.get("predecessor_milestone") == "M7"
        and value.get("protected_main_sha")
        == "c78604ade0aeffdbf7395fccfc0951751beae751"
        and value.get("protected_main_run_number") == 510
        and value.get("protected_main_actions_run_id") == 36807335564
        and value.get("p3_qualification") == "P3_M7_QUALIFIED"
        and value.get("m7_exit_decision") == "GO"
        and value.get("p3_admitted") is True
        and value.get("protected_main_exact") is True
        and value.get("hosted_ci_required_jobs") == 14
        and value.get("hosted_ci_result") == "PASS"
    )


def _program_exit_runway_lifecycle_valid(bundle: dict[str, Any]) -> bool:
    if _issue_state(bundle, 149) != "open":
        return False
    runway_state = _issue_state(bundle, 186)
    if runway_state not in ("open", "closed"):
        return False
    if runway_state == "closed":
        runway_text = _issue_text(bundle, 186)
        if not all(
            token in runway_text
            for token in (
                "SDIB-1.8",
                "ffbd5e5f0561ce39d8736de765dd6be240edfae1",
                "Run #529",
                "15 tasks",
            )
        ):
            return False
    exit_state = _issue_state(bundle, 185)
    if exit_state == "open":
        return True
    if exit_state != "closed":
        return False
    exit_text = _issue_text(bundle, 185)
    return (
        "P4_P5_M8_QUALIFIED" in exit_text
        and "p4_admitted=true" in exit_text
        and "p5_admitted=true" in exit_text
        and "p6_inactive=true" in exit_text
        and "failed_acceptance=[]" in exit_text
        and "decision=GO" in exit_text
        and ("14/14 SUCCESS" in exit_text or "14 of 14 SUCCESS" in exit_text)
    )


def _task_evidence_hashes(issues: dict[str, Any]) -> dict[str, str]:
    issue_for_batch = {
        "M8-BATCH-1": 182,
        "M8-BATCH-2": 183,
        "M8-BATCH-3": 184,
    }
    result: dict[str, str] = {}
    for task_id in EXPECTED_TASK_IDS:
        if task_id == TASK_ID:
            material: dict[str, object] = {
                "task_id": task_id,
                "batch_id": "M8-BATCH-4",
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
            "execute_capability_model(",
            "evaluate_twin_capability_estimate(",
            "sqlite3",
            "psycopg",
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
    dto_path: Path = DTO_PATH,
    registry_path: Path = REGISTRY_PATH,
    batch1_test_path: Path = BATCH1_TEST,
    batch2_test_path: Path = BATCH2_TEST,
    batch3_test_path: Path = BATCH3_TEST,
    context_source_path: Path = CONTEXT_SOURCE,
    p5_source_path: Path = P5_SOURCE,
    application_source_path: Path = APPLICATION_SOURCE,
    api_source_path: Path = API_SOURCE,
    gui_source_path: Path = GUI_SOURCE,
    m9_runway_path: Path = M9_RUNWAY,
) -> dict[str, Any]:
    issues = _json(issues_path)
    tasks = _json(task_baseline_path)
    lock = _json(lock_path)
    authority = _json(authority_path)
    role_profile = _json(role_profile_path)
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
    authority_scope = cast(dict[str, Any], authority.get("scope", {}))
    authority_activation = cast(
        dict[str, Any],
        authority.get("activation_rule", {}),
    )
    admission_guard = cast(dict[str, Any], authority.get("admission_guard", {}))
    aggregation = cast(dict[str, Any], authority.get("aggregation_contract", {}))
    role_activation = cast(
        dict[str, Any],
        role_profile.get("activation_rule", {}),
    )
    role_scope = cast(dict[str, Any], role_profile.get("scope", {}))
    role_projection = cast(
        dict[str, Any],
        role_profile.get("projection_contract", {}),
    )
    dto_contracts = cast(dict[str, Any], dto.get("contracts", {}))
    m8_dto_subset = {name: dto_contracts.get(name, {}) for name in M8_DTO_NAMES}
    lineage = cast(list[Any], baseline_info.get("lock_lineage_sha256", []))
    admission = cast(
        dict[str, Any],
        dto_contracts.get("P4P5AdmissionStateDTO", {}),
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
        "baseline_task_count_exact_23": (
            tasks.get("task_count") == 23
            and task_ids == EXPECTED_TASK_IDS
            and len(set(task_ids)) == 23
        ),
        "task_evidence_exact_23": (
            len(evidence_hashes) == 23
            and set(evidence_hashes) == set(EXPECTED_TASK_IDS)
            and all(len(value) == 64 for value in evidence_hashes.values())
        ),
        "m7_entry_qualification_exact": _entry_qualification_exact(tasks),
        "c3_and_batch_trackers_closed": all(
            _issue_state(issues, number) == "closed"
            for number in (181, 182, 183, 184)
        ),
        "batch_protected_main_evidence_exact": _batch_qualification_exact(issues),
        "program_exit_and_m9_runway_lifecycle_valid": (
            _program_exit_runway_lifecycle_valid(issues)
        ),
        "authority_role_dto_lock_exact": (
            _sha(authority_path) == EXPECTED_AUTHORITY_SHA256
            and _sha(role_profile_path) == EXPECTED_ROLE_PROFILE_SHA256
            and lock_hashes.get("P4_P5_TRAINING_ASSESSMENT_AUTHORITY.json")
            == EXPECTED_AUTHORITY_SHA256
            and lock_hashes.get("P4_P5_ROLE_PRIVACY_PROFILE.json")
            == EXPECTED_ROLE_PROFILE_SHA256
            and lock_hashes.get("CROSS_LAYER_DTO_CONTRACTS.json")
            == _sha(dto_path)
            and _canonical_hash(m8_dto_subset) == EXPECTED_M8_DTO_SUBSET_SHA256
            and EXPECTED_M8_BASELINE_LOCK_SHA256 in lineage
            and authority.get("authority_id")
            == "P4_P5_TRAINING_ASSESSMENT_AUTHORITY"
            and authority.get("version") == "1.0.0"
            and role_profile.get("profile_id") == "P4_P5_ROLE_PRIVACY_PROFILE"
            and role_profile.get("version") == "1.0.0"
        ),
        "db_schema_1_6_0_no_shadow_schema": (
            baseline_info.get("db_schema") == "1.6.0"
            and authority.get("db_schema_version") == "1.6.0"
            and role_profile.get("db_schema_version") == "1.6.0"
            and authority_scope.get("db_schema_change") is False
            and authority_scope.get("shadow_schema_permitted") is False
            and role_scope.get("db_schema_change") is False
            and role_scope.get("shadow_schema_permitted") is False
        ),
        "admission_dto_and_guard_exact": (
            admission_fields == ADMISSION_FIELDS
            and authority_activation.get("authority_adoption_does_not_admit_p4_or_p5")
            is True
            and authority_activation.get(
                "p4_p5_admission_requires_protected_main_m8_exit_go"
            )
            is True
            and authority_activation.get("p6_remains_inactive") is True
            and role_activation.get("profile_adoption_does_not_admit_p4_or_p5")
            is True
            and role_activation.get(
                "p4_p5_external_claim_requires_protected_main_m8_exit_go"
            )
            is True
            and admission_guard.get("required_event") == "push"
            and admission_guard.get("required_git_ref") == "refs/heads/main"
            and admission_guard.get("required_m8_exit_decision") == "GO"
            and admission_guard.get("required_run_conclusion") == "success"
            and admission_guard.get("required_job_count") == 14
        ),
        "batch1_subject_composition_privacy_gates": (
            _tokens(
                batch1_test_path,
                (
                    "test_m8_batch1_p4_subject_context_is_exact_and_deterministic",
                    "test_m8_batch1_p4_alias_future_and_same_episode_fail_closed",
                    "test_m8_batch1_privacy_projection_is_least_privilege",
                    "test_m8_batch1_world_leakage_conflation_and_zero_coercion_fail_closed",
                    "test_m8_batch1_p5_composition_is_deterministic_and_drift_sensitive",
                ),
            )
            and _tokens(
                context_source_path,
                (
                    "FAIL_CLOSED_P4_P5_NOT_ADMITTED",
                    "FAIL_CLOSED_P6_NOT_ADMITTED",
                    "FAIL_CLOSED_P4_P5_TEAM_TO_INDIVIDUAL_COPY",
                ),
            )
        ),
        "batch2_instructor_p4_replay_gates": _tokens(
            batch2_test_path,
            (
                "test_m8_batch2_machine_evidence_is_exact_deterministic_and_unscored",
                "test_m8_batch2_annotation_revision_is_immutable_and_idempotent",
                "test_m8_batch2_p4_assessment_revision_and_approval_chain",
                "test_m8_batch2_longitudinal_replay_is_exact_and_as_of_bounded",
                "test_m8_batch2_longitudinal_configuration_drift_is_not_pooled",
            ),
        ),
        "batch3_p5_aggregation_replay_api_gui_security_gates": (
            _tokens(
                batch3_test_path,
                (
                    "test_m8_batch3_p5_evidence_and_no_profile_aggregation",
                    "test_m8_batch3_missing_member_is_explicit",
                    "test_m8_batch3_p5_replay_separates_changed_composition",
                    "test_m8_batch3_application_role_projection_and_export_denial",
                    "test_m8_batch3_api_exact_ids_role_privacy_and_idempotent_write",
                    "test_m8_batch3_gui_preserves_aircraft_p4_p5_separation",
                    "test_m8_batch3_pre_exit_api_fails_closed",
                ),
            )
            and aggregation.get("default_aggregation_profile") is None
            and aggregation.get("implementation_default_formula_forbidden") is True
            and aggregation.get("implementation_default_weight_forbidden") is True
            and aggregation.get("implementation_default_threshold_forbidden") is True
            and aggregation.get("no_profile_behavior")
            == "EVIDENCE_ONLY_SCORE_AND_GRADE_NULL"
            and _tokens(
                p5_source_path,
                (
                    "FAIL_CLOSED_P4_P5_AGGREGATION_PROFILE_REQUIRED",
                    "TEAM_MISSION_EVIDENCE_ONLY",
                    "overall_score=None",
                    "grade=None",
                ),
            )
        ),
        "api_exact_ids_no_alias_recompute": (
            _tokens(
                api_source_path,
                (
                    "/m8/p4/assessments/{actor_assessment_id}",
                    "/m8/p5/assessments/{mission_assessment_id}",
                    "principal_resolver",
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
        "gui_p1_p5_separation_no_business_recompute": (
            _tokens(
                gui_source_path,
                (
                    "P1_OBSERVED",
                    "P2_ADJUSTED",
                    "P3_REFERENCE_CONDITION_LONGITUDINAL",
                    "P4 INDIVIDUAL",
                    "P5 TEAM/MISSION",
                ),
            )
            and "tpaa_assessment"
            not in gui_source_path.read_text(encoding="utf-8")
            and "tpaa_application"
            not in gui_source_path.read_text(encoding="utf-8")
        ),
        "role_privacy_runtime_exact": (
            role_scope.get("default_deny") is True
            and role_scope.get("direct_identity_default") is False
            and role_projection.get("default_subject_projection") == "subject_key"
            and role_projection.get("p5_team_lead_and_analyst_participant_identity")
            == "subject_key_only"
            and role_projection.get("not_authorized_transport_behavior")
            == "FAIL_CLOSED_NOT_AUTHORIZED_NO_BUSINESS_VALUE"
            and _tokens(
                application_source_path,
                (
                    "privileged_identity_authorized",
                    "export_authorized",
                    "M8_EXPORT",
                    "principal_key",
                ),
            )
        ),
        "p1_p3_retained_and_p4_p5_candidate_registry": (
            phases.get("P1") == "CURRENT_BASELINE"
            and all(
                phases.get(code) == "DESIGN_CONTRACT_FROZEN"
                for code in ("P2", "P3", "P4", "P5")
            )
        ),
        "p6_inactive_and_m9_runway_exact": (
            phases.get("P6") == "DESIGN_CONTRACT_FROZEN"
            and authority_scope.get("p6_active") is False
            and role_activation.get("p6_active") is False
            and admission_guard.get("p6_claim_before_m9_exit_forbidden") is True
            and _tokens(
                m9_runway_path,
                (
                    "P6 implementation status: **DESIGN ONLY**",
                    "P6 admission status: **NOT ADMITTED**",
                    "P6ForecastRequestDTO",
                    "P6CounterfactualRequestDTO",
                    "M9-GOV-001",
                    "M9-EXIT-001",
                ),
            )
            and "DESIGN ONLY" in _issue_text(issues, 186)
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
    p4_admitted = decision == "GO"
    p5_admitted = decision == "GO"
    p6_inactive = acceptance["p6_inactive_and_m9_runway_exact"] is True
    task_acceptance = {
        task_id: implementation_complete
        for task_id in EXPECTED_TASK_IDS
    }
    task_acceptance[TASK_ID] = p4_admitted and p5_admitted

    return {
        "schema": "TPAA_M8_EXIT_REVIEW_V1",
        "milestone": "M8",
        "capability": "P4_P5",
        "task_id": TASK_ID,
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if implementation_complete else "FAIL",
        "decision": decision,
        "implementation_complete": implementation_complete,
        "task_complete": p4_admitted and p5_admitted,
        "formal_completion_blocked_by_protected_main": (
            implementation_complete and not (p4_admitted and p5_admitted)
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
        "task_count": 23,
        "task_ids": list(EXPECTED_TASK_IDS),
        "task_acceptance": task_acceptance,
        "task_evidence_hashes": evidence_hashes,
        "qualification_chain": QUALIFICATION,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "p4_admitted": p4_admitted,
        "p5_admitted": p5_admitted,
        "p6_inactive": p6_inactive,
        "qualification": (
            "P4_P5_M8_QUALIFIED"
            if p4_admitted and p5_admitted
            else "M8_CANDIDATE_NOT_FORMALLY_QUALIFIED"
        ),
        "admission_state": {
            "source_revision": expected_revision,
            "event_name": event_name,
            "git_ref": git_ref,
            "protected_main": protected_main,
            "m8_exit_decision": decision,
            "run_conclusion": run_conclusion,
            "required_jobs_success": required_jobs_success,
            "required_jobs_total": required_jobs_total,
            "p4_admitted": p4_admitted,
            "p5_admitted": p5_admitted,
            "p6_inactive": p6_inactive,
        },
        "unresolved_risks": (
            []
            if not failed
            else [{"kind": "acceptance", "items": failed}]
        ),
        "scope": {
            "p1_p3_immutable_upstream": True,
            "p4_admitted": p4_admitted,
            "p5_admitted": p5_admitted,
            "p6_inactive": p6_inactive,
            "db_schema_version": "1.6.0",
            "shadow_schema_created": False,
            "capability_phase_registry_mutated_for_runtime_admission": False,
            "protected_main_required_for_go": True,
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
            "schema": "TPAA_M8_EXIT_REVIEW_V1",
            "milestone": "M8",
            "capability": "P4_P5",
            "task_id": TASK_ID,
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "decision": "NO_GO",
            "implementation_complete": False,
            "task_complete": False,
            "p4_admitted": False,
            "p5_admitted": False,
            "p6_inactive": True,
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
