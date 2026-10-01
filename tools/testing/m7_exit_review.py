#!/usr/bin/env python3
"""M7-TST-005 exact M7 Exit review and C4 P3 admission decision."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
CANONICAL = BASELINE / "canonical"
TASK_BASELINE = ROOT / "docs" / "baseline" / "SDIB-1.6" / "M7_TASK_BASELINE.json"
LOCK_PATH = BASELINE / "BASELINE_LOCK.json"
AUTHORITY_PATH = CANONICAL / "P3_CAPABILITY_TWIN_AUTHORITY.json"
DTO_PATH = CANONICAL / "CROSS_LAYER_DTO_CONTRACTS.json"
PROFILE_PATH = CANONICAL / "P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL_PROFILE.json"
REGISTRY_PATH = CANONICAL / "CAPABILITY_PHASE_REGISTRY.json"
BATCH1_TEST = ROOT / "tests" / "contract" / "test_m7_batch_1_p3_substrate.py"
BATCH2_TEST = ROOT / "tests" / "contract" / "test_m7_batch_2_capability_model.py"
BATCH3_TEST = ROOT / "tests" / "contract" / "test_m7_batch_3_twin_api_gui.py"
BATCH1_REVIEW = ROOT / "docs" / "reviews" / "M7_C3_P3_CAPABILITY_TWIN_AUTHORITY_REVIEW.md"
BATCH2_REVIEW = ROOT / "docs" / "reviews" / "M7_BATCH2_CAPABILITY_MODEL_SURFACE_REVIEW.md"
BATCH3_REVIEW = ROOT / "docs" / "reviews" / "M7_BATCH3_TWIN_API_GUI_REVIEW.md"
M8_RUNWAY = ROOT / "docs" / "reviews" / "M8_P4_P5_DESIGN_RUNWAY_REVIEW.md"
EXIT_REVIEW = ROOT / "docs" / "reviews" / "M7_BATCH4_EXIT_ADMISSION_REVIEW.md"
MODEL_SOURCE = ROOT / "src" / "tpaa_capability" / "p3_model.py"
APPLICATION_SOURCE = ROOT / "src" / "tpaa_application" / "m7_workspace.py"
API_SOURCE = ROOT / "src" / "tpaa_api" / "m7_app.py"
GUI_SOURCE = ROOT / "src" / "tpaa_gui" / "m7_workspace.py"

TASK_ID = "M7-TST-005"
TRACKING_ISSUE = 177

EXPECTED_AUTHORITY_SHA256 = "76726fc533cde7b0a183a1575cb50276e166081cc37ebe4857ed3324ab913e3b"
EXPECTED_PROFILE_SHA256 = "d66aa780d1c2e31ec664d173a0cdbc355f98c9ff3f751a6949e84f74cdf93876"
EXPECTED_M7_DTO_SHA256 = "644370d40e42960144102e6f404b6ee31af9753686b67bb27e47690515898c41"
EXPECTED_M7_BASELINE_LOCK_SHA256 = "0d2f11dc5ee41038a1ef63b8b4157730bd1cd313c7a98faaa286132397b8de47"
EXPECTED_P3_DTO_SUBSET_SHA256 = "90b2f51d0c9b81ed0b3d6ff4294a945c087578a41c01a9c11a5ac7571f6ad91f"

P3_DTO_NAMES = (
    "P3EligibleAdjustedEstimateDTO",
    "P3LifecycleSegmentDTO",
    "P3ModelValidationSnapshotDTO",
    "CapabilityModelDTO",
    "CapabilitySurfaceDTO",
    "AircraftTwinRevisionDTO",
    "IntrinsicCapabilityEstimateDTO",
    "P3AdmissionStateDTO",
)

EXPECTED_TASK_IDS = (
    "M7-GOV-001",
    "M7-GOV-002",
    "M7-DATA-001",
    "M7-DATA-002",
    "M7-DATA-003",
    "M7-CAP-001",
    "M7-CAP-002",
    "M7-CAP-003",
    "M7-CAP-004",
    "M7-CAP-005",
    "M7-API-001",
    "M7-GUI-001",
    "M7-GOV-003",
    "M7-TST-001",
    "M7-TST-002",
    "M7-TST-003",
    "M7-TST-004",
    "M7-TST-005",
)

BATCH_QUALIFICATION: dict[str, dict[str, object]] = {
    "M7-BATCH-1": {
        "task_ids": EXPECTED_TASK_IDS[0:5] + ("M7-TST-001",),
        "issue": 172,
        "protected_main_sha": "ebfb99afbb86cf1fc857d03d746afa6e774a4626",
        "run_number": 501,
        "actions_run_id": 36726742843,
    },
    "M7-BATCH-2": {
        "task_ids": EXPECTED_TASK_IDS[5:8] + EXPECTED_TASK_IDS[14:16],
        "issue": 174,
        "protected_main_sha": "df32b081747e3526e13d974f818cc58125c16fd3",
        "run_number": 504,
        "actions_run_id": 36739428626,
    },
    "M7-BATCH-3": {
        "task_ids": EXPECTED_TASK_IDS[8:13] + ("M7-TST-004",),
        "issue": 176,
        "protected_main_sha": "a56acc6014daf68d5a0207fb78297777e575341b",
        "run_number": 508,
        "actions_run_id": 36801435432,
    },
}

BATCH_FILES = {
    "M7-BATCH-1": (
        BATCH1_REVIEW,
        BATCH1_TEST,
        AUTHORITY_PATH,
        PROFILE_PATH,
    ),
    "M7-BATCH-2": (
        BATCH2_REVIEW,
        BATCH2_TEST,
        MODEL_SOURCE,
        ROOT / "tests" / "fixtures" / "m7" / "p3_capability_model_golden.json",
    ),
    "M7-BATCH-3": (
        BATCH3_REVIEW,
        BATCH3_TEST,
        APPLICATION_SOURCE,
        API_SOURCE,
        GUI_SOURCE,
        M8_RUNWAY,
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


def _p3_dto_subset_hash(dto_contracts: dict[str, Any]) -> str:
    subset = {
        name: cast(dict[str, Any], dto_contracts.get(name, {}))
        for name in P3_DTO_NAMES
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
        if _issue_state(bundle, issue) != "closed":
            return False
        if not all(token in text for token in tokens):
            return False
        if "14/14 SUCCESS" not in text and "14 of 14 SUCCESS" not in text:
            return False
    return True


def _m6_entry_qualification_exact(
    bundle: dict[str, Any],
    tasks: dict[str, Any],
) -> bool:
    entry = tasks.get("entry_evidence")
    if not isinstance(entry, dict):
        return False
    evidence = cast(dict[str, Any], entry)
    text = _issue_text(bundle, 166)
    return (
        _issue_state(bundle, 166) == "closed"
        and evidence.get("protected_main_sha")
        == "892e4a64a321be9c7252b66207a7d1d90a6ce98d"
        and evidence.get("protected_main_run_number") == 494
        and evidence.get("protected_main_actions_run_id") == 36697493917
        and evidence.get("p2_qualification") == "P2_M6_QUALIFIED"
        and evidence.get("m6_exit_decision") == "GO"
        and evidence.get("p2_admitted") is True
        and evidence.get("hosted_ci_required_jobs") == 14
        and evidence.get("hosted_ci_result") == "PASS"
        and "892e4a64a321be9c7252b66207a7d1d90a6ce98d" in text
        and "Run #494" in text
        and "36697493917" in text
        and "P2_M6_QUALIFIED" in text
        and "p2_admitted=true" in text
    )


def _m8_design_runway_exact(bundle: dict[str, Any]) -> bool:
    if _issue_state(bundle, 170) not in {"open", "closed"}:
        return False
    issue_text = _issue_text(bundle, 170)
    runway_text = M8_RUNWAY.read_text(encoding="utf-8")
    issue_tokens = (
        "M7-GOV-003",
        "a56acc6014daf68d5a0207fb78297777e575341b",
        "Run #508",
        "36801435432",
        "DESIGN ONLY",
    )
    runway_tokens = (
        "P3 -> P4/P5 interface contract",
        "twin_revision_id",
        "privacy",
        "Golden",
        "negative",
        "replay",
        "M8 implementation must not start",
    )
    return all(token in issue_text for token in issue_tokens) and all(
        token in runway_text for token in runway_tokens
    )


def _program_and_exit_tracker_lifecycle_valid(bundle: dict[str, Any]) -> bool:
    if _issue_state(bundle, 149) != "open":
        return False
    exit_state = _issue_state(bundle, 177)
    if exit_state == "open":
        return True
    if exit_state != "closed":
        return False
    text = _issue_text(bundle, 177)
    return (
        "P3_M7_QUALIFIED" in text
        and "p3_admitted=true" in text
        and ("14/14 SUCCESS" in text or "14 of 14 SUCCESS" in text)
        and "failed_acceptance=[]" in text
        and ("decision=GO" in text or "decision: `GO`" in text)
    )


def _paths_clean(paths: tuple[Path, ...]) -> bool:
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    return all(
        token not in text
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
    return "M7-BATCH-4", {}


def _task_evidence_hashes(bundle: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for task_id in EXPECTED_TASK_IDS:
        batch_id, row = _batch_for_task(task_id)
        files = (
            (Path(__file__), EXIT_REVIEW)
            if task_id == TASK_ID
            else BATCH_FILES[batch_id]
        )
        material: dict[str, object] = {
            "task_id": task_id,
            "batch_id": batch_id,
            "protected_main_sha": row.get("protected_main_sha"),
            "run_number": row.get("run_number"),
            "actions_run_id": row.get("actions_run_id"),
            "files": {
                str(path.relative_to(ROOT)): _sha(path)
                for path in files
            },
        }
        if task_id == "M7-GOV-003":
            material["m8_design_issue_evidence_hash"] = _canonical_hash(
                _issue(bundle, 170)
            )
        result[task_id] = _canonical_hash(material)
    return result


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
    dto_path: Path = DTO_PATH,
    profile_path: Path = PROFILE_PATH,
    registry_path: Path = REGISTRY_PATH,
    batch1_test_path: Path = BATCH1_TEST,
    batch2_test_path: Path = BATCH2_TEST,
    batch3_test_path: Path = BATCH3_TEST,
    application_source_path: Path = APPLICATION_SOURCE,
    api_source_path: Path = API_SOURCE,
    gui_source_path: Path = GUI_SOURCE,
) -> dict[str, Any]:
    issues = _json(issues_path)
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
    p3_dto_subset_hash = _p3_dto_subset_hash(dto_contracts)
    lineage = cast(
        list[Any],
        cast(dict[str, Any], lock.get("baseline", {})).get("lock_lineage_sha256", []),
    )
    admission_dto = cast(dict[str, Any], dto_contracts.get("P3AdmissionStateDTO", {}))
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

    auth_scope = cast(dict[str, Any], authority.get("scope", {}))
    activation = cast(dict[str, Any], authority.get("activation_rule", {}))
    admission_guard = cast(dict[str, Any], authority.get("admission_guard", {}))
    claim_contract = cast(dict[str, Any], authority.get("claim_contract", {}))
    profile_activation = cast(dict[str, Any], profile.get("activation_rule", {}))
    profile_scope = cast(dict[str, Any], profile.get("scope", {}))
    profile_source = cast(dict[str, Any], profile.get("source_bindings", {}))
    profile_output = cast(dict[str, Any], profile.get("output_contract", {}))
    profile_managed = cast(dict[str, Any], profile.get("managed_object_contract", {}))
    segmentation = cast(dict[str, Any], profile.get("segmentation_contract", {}))
    validation = cast(dict[str, Any], profile.get("validation_contract", {}))
    validity = cast(dict[str, Any], profile.get("validity_domain_contract", {}))
    baseline_info = cast(dict[str, Any], lock.get("baseline", {}))
    phases = _phase_statuses(registry)
    evidence_hashes = _task_evidence_hashes(issues)

    acceptance = {
        "source_revision_exact": (
            expected_revision == checked_out_revision
            and _is_sha(expected_revision)
        ),
        "baseline_task_count_exact_18": (
            tasks.get("task_count") == 18
            and task_ids == EXPECTED_TASK_IDS
            and len(set(task_ids)) == 18
        ),
        "task_evidence_exact_18": (
            len(evidence_hashes) == 18
            and set(evidence_hashes) == set(EXPECTED_TASK_IDS)
            and all(len(value) == 64 for value in evidence_hashes.values())
        ),
        "m6_entry_qualification_exact": _m6_entry_qualification_exact(
            issues,
            tasks,
        ),
        "c3_issue_closed": _issue_state(issues, 169) == "closed",
        "batch_trackers_closed": all(
            _issue_state(issues, number) == "closed"
            for number in (172, 174, 176)
        ),
        "batch_protected_main_evidence_exact": _batch_issue_evidence_exact(issues),
        "m8_design_runway_exact": _m8_design_runway_exact(issues),
        "program_and_exit_tracker_lifecycle_valid": (
            _program_and_exit_tracker_lifecycle_valid(issues)
        ),
        "authority_lock_exact": (
            _sha(authority_path) == EXPECTED_AUTHORITY_SHA256
            and lock_hashes.get("P3_CAPABILITY_TWIN_AUTHORITY.json")
            == EXPECTED_AUTHORITY_SHA256
            and authority.get("authority_id") == "P3_CAPABILITY_TWIN_AUTHORITY"
            and authority.get("version") == "1.0.0"
        ),
        "profile_lock_exact": (
            _sha(profile_path) == EXPECTED_PROFILE_SHA256
            and lock_hashes.get(
                "P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL_PROFILE.json"
            )
            == EXPECTED_PROFILE_SHA256
            and profile.get("profile_id")
            == "P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL"
            and profile.get("version") == "1.0.0"
            and profile_source.get("p3_authority_sha256")
            == EXPECTED_AUTHORITY_SHA256
            and profile_source.get("cross_layer_dto_sha256")
            == EXPECTED_M7_DTO_SHA256
        ),
        "dto_and_baseline_lock_exact": (
            lock_hashes.get("CROSS_LAYER_DTO_CONTRACTS.json") == _sha(dto_path)
            and p3_dto_subset_hash == EXPECTED_P3_DTO_SUBSET_SHA256
            and EXPECTED_M7_BASELINE_LOCK_SHA256 in lineage
            and admission_fields
            == (
                "source_revision",
                "event_name",
                "git_ref",
                "protected_main",
                "m7_exit_decision",
                "run_conclusion",
                "required_jobs_success",
                "required_jobs_total",
                "p4_p6_inactive",
            )
        ),
        "p3_admission_guard_exact": (
            activation.get("authority_adoption_does_not_admit_p3") is True
            and activation.get(
                "p3_admission_requires_protected_main_m7_exit_go"
            )
            is True
            and admission_guard.get("required_event") == "push"
            and admission_guard.get("required_git_ref") == "refs/heads/main"
            and admission_guard.get("required_m7_exit_decision") == "GO"
            and admission_guard.get("required_run_conclusion") == "success"
            and admission_guard.get("required_job_count") == 14
            and profile_activation.get("profile_adoption_does_not_admit_p3")
            is True
            and profile_activation.get(
                "p3_external_claim_requires_protected_main_m7_exit_go"
            )
            is True
        ),
        "db_schema_1_6_0_no_shadow_schema": (
            baseline_info.get("db_schema") == "1.6.0"
            and authority.get("db_schema_version") == "1.6.0"
            and profile.get("db_schema_version") == "1.6.0"
            and auth_scope.get("db_schema_change") is False
            and auth_scope.get("shadow_schema_permitted") is False
            and profile_scope.get("db_schema_change") is False
            and profile_scope.get("shadow_schema_permitted") is False
        ),
        "lifecycle_configuration_knowledge_time_exact": (
            segmentation.get("per_session_configuration_snapshot_ids_preserved")
            is True
            and segmentation.get("any_dimension_change_starts_new_segment") is True
            and segmentation.get(
                "any_lifecycle_event_inside_selected_session_interval_starts_new_segment"
            )
            is True
            and segmentation.get("lifecycle_marker_set_bound_into_segment_hash")
            is True
            and _tokens(
                batch1_test_path,
                (
                    "FAIL_CLOSED_P3_CONFIGURATION_SEGMENT_REQUIRED",
                    "FAIL_CLOSED_P3_LIFECYCLE_FUTURE_INFORMATION",
                    "test_m7_batch1_estimate_creation_after_as_of_fails_closed",
                ),
            )
        ),
        "managed_object_binding_exact": (
            profile_managed.get("model_artifact_requires_sealed_active_object")
            is True
            and profile_managed.get("surface_dataset_requires_sealed_active_object")
            is True
            and profile_managed.get("managed_uri_exact_match") is True
            and profile_managed.get("artifact_sha256_exact_match") is True
            and _tokens(
                batch1_test_path,
                (
                    "FAIL_CLOSED_P3_MANAGED_OBJECT_REQUIRED",
                    "FAIL_CLOSED_P3_MANAGED_OBJECT_HASH_MISMATCH",
                ),
            )
            and _tokens(
                batch2_test_path,
                (
                    "test_m7_batch2_model_and_surface_bytes_are_physically_sealed_and_hash_bound",
                    "test_m7_batch2_managed_object_hash_mismatch_remains_fail_closed",
                ),
            )
        ),
        "validation_and_validity_domain_exact": (
            validation.get("strategy")
            == "TEMPORAL_LAST_POINT_HOLDOUT_THEN_FINAL_REFIT"
            and validation.get("minimum_total_eligible_points") == 4
            and validation.get("pass_status") == "VALIDATED"
            and validity.get("out_of_domain_status") == "OUT_OF_DOMAIN"
            and validity.get("in_domain_status") == "IN_DOMAIN"
            and validity.get(
                "extrapolation_beyond_observed_session_order_forbidden"
            )
            is True
            and _tokens(
                batch2_test_path,
                (
                    "test_m7_batch2_training_model_surface_match_static_golden",
                    "test_m7_batch2_input_order_replay_is_logically_identical",
                    "test_m7_batch2_validation_failure_blocks_model_publication",
                    "test_m7_batch2_surface_is_observed_domain_only",
                ),
            )
        ),
        "claim_boundary_exact": (
            auth_scope.get("profile_v1_subject_type") == "AIRCRAFT"
            and auth_scope.get("aircraft_model_level_profile_v1_supported")
            is False
            and auth_scope.get("stronger_intrinsic_claim_profile_v1_supported")
            is False
            and profile_scope.get("subject_type") == "AIRCRAFT"
            and profile_scope.get("aircraft_model_level_supported") is False
            and profile_scope.get("stronger_intrinsic_claim_supported") is False
            and profile_output.get("estimate_claim_level")
            == "REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE"
            and claim_contract.get("profile_v1_allowed_claim_levels")
            == ["REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE"]
            and _tokens(
                batch3_test_path,
                (
                    "FAIL_CLOSED_P3_CLAIM_EVIDENCE_REQUIRED",
                    "INTRINSIC_CAPABILITY_ESTIMATE",
                    "REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE",
                ),
            )
        ),
        "p1_p2_historical_products_immutable": (
            auth_scope.get("p1_observed_layer_immutable") is True
            and auth_scope.get("p2_adjusted_layer_immutable") is True
            and profile_scope.get("p1_p2_overwrite_forbidden") is True
            and phases.get("P1") == "CURRENT_BASELINE"
            and phases.get("P2") == "DESIGN_CONTRACT_FROZEN"
            and _tokens(
                batch3_test_path,
                (
                    "test_m7_tst_004_p1_p2_hashes_are_nonregressing_and_repository_is_immutable",
                    "logical_product_hash",
                ),
            )
        ),
        "p3_substrate_model_surface_twin_estimate_replay_present": (
            _tokens(
                batch1_test_path,
                (
                    "test_m7_batch1_exact_segment_and_validation_snapshot_are_deterministic",
                    "test_m7_batch1_p1_p2_products_cannot_be_overwritten",
                ),
            )
            and _tokens(
                batch2_test_path,
                (
                    "test_m7_batch2_training_model_surface_match_static_golden",
                    "test_m7_batch2_input_order_replay_is_logically_identical",
                ),
            )
            and _tokens(
                batch3_test_path,
                (
                    "test_m7_cap_004_twin_identity_is_ordered_immutable_and_exact",
                    "test_m7_cap_004_supersession_is_new_revision_without_mutating_history",
                    "test_m7_cap_005_estimate_is_exact_claim_bound_and_ood_is_null",
                    "test_m7_api_001_exact_revision_reads_and_replay",
                ),
            )
        ),
        "api_exact_id_no_alias_or_recompute": (
            _tokens(
                api_source_path,
                (
                    "/m7/p3/twins/{twin_revision_id}",
                    "/estimates/{estimate_id}",
                    "M7_P3_NOT_ADMITTED",
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
        "gui_no_persistence_recompute_or_claim_upgrade": (
            _tokens(
                gui_source_path,
                (
                    "P1_OBSERVED",
                    "P2_ADJUSTED",
                    "P3_REFERENCE_CONDITION_LONGITUDINAL",
                    "REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE",
                ),
            )
            and "tpaa_capability"
            not in gui_source_path.read_text(encoding="utf-8")
            and "tpaa_application"
            not in gui_source_path.read_text(encoding="utf-8")
            and _tokens(
                batch3_test_path,
                (
                    "test_m7_tst_004_gui_rejects_transport_hash_and_claim_drift",
                    "test_m7_tst_004_gui_and_api_respect_architecture_boundary",
                ),
            )
        ),
        "p4_p6_inactive": (
            auth_scope.get("p4_p6_active") is False
            and profile_activation.get("p4_p6_active") is False
            and all(
                phases.get(code) == "DESIGN_CONTRACT_FROZEN"
                for code in ("P3", "P4", "P5", "P6")
            )
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
    p3_admitted = decision == "GO"
    p4_p6_inactive = acceptance["p4_p6_inactive"] is True
    task_acceptance = {
        task_id: implementation_complete
        for task_id in EXPECTED_TASK_IDS
    }
    task_acceptance[TASK_ID] = p3_admitted

    return {
        "schema": "TPAA_M7_EXIT_REVIEW_V1",
        "milestone": "M7",
        "capability": "P3",
        "task_id": TASK_ID,
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if implementation_complete else "FAIL",
        "decision": decision,
        "implementation_complete": implementation_complete,
        "task_complete": p3_admitted,
        "formal_completion_blocked_by_protected_main": (
            implementation_complete and not p3_admitted
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
        "task_count": 18,
        "task_ids": list(EXPECTED_TASK_IDS),
        "task_acceptance": task_acceptance,
        "task_evidence_hashes": evidence_hashes,
        "batch_qualification": BATCH_QUALIFICATION,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "p3_admitted": p3_admitted,
        "qualification": (
            "P3_M7_QUALIFIED"
            if p3_admitted
            else "M7_CANDIDATE_NOT_FORMALLY_QUALIFIED"
        ),
        "admission_state": {
            "source_revision": expected_revision,
            "event_name": event_name,
            "git_ref": git_ref,
            "protected_main": protected_main,
            "m7_exit_decision": decision,
            "run_conclusion": run_conclusion,
            "required_jobs_success": required_jobs_success,
            "required_jobs_total": required_jobs_total,
            "p4_p6_inactive": p4_p6_inactive,
        },
        "unresolved_risks": (
            []
            if not failed
            else [{"kind": "acceptance", "items": failed}]
        ),
        "scope": {
            "p1_immutable": True,
            "p2_immutable": True,
            "p3_admitted": p3_admitted,
            "p4_p6_inactive": p4_p6_inactive,
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
            "schema": "TPAA_M7_EXIT_REVIEW_V1",
            "milestone": "M7",
            "capability": "P3",
            "task_id": TASK_ID,
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "decision": "NO_GO",
            "implementation_complete": False,
            "task_complete": False,
            "p3_admitted": False,
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
