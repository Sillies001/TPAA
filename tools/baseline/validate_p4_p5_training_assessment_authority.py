#!/usr/bin/env python3
"""Validate the M8 P4/P5 training-assessment authority and role/privacy profile exactly."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = REPO_ROOT / "baseline" / "CB-1.4.0"
CANONICAL = BASELINE / "canonical"
AUTHORITY = CANONICAL / "P4_P5_TRAINING_ASSESSMENT_AUTHORITY.json"
ROLE_PROFILE = CANONICAL / "P4_P5_ROLE_PRIVACY_PROFILE.json"
DTO = CANONICAL / "CROSS_LAYER_DTO_CONTRACTS.json"
CORE = REPO_ROOT / "migrations" / "authority" / "CORE_LOGICAL_MODEL_DB_1_6_0.json"
EXTENSION = CANONICAL / "EXTENSION_CONTRACT_REGISTRY.json"
P3_AUTHORITY = CANONICAL / "P3_CAPABILITY_TWIN_AUTHORITY.json"
LOCK = BASELINE / "BASELINE_LOCK.json"

EXPECTED_AUTHORITY_SHA256 = "749360544e3e403e3a81b4992797d5186c93d1f06a92e96f1352c4ab4ed4cb77"
EXPECTED_ROLE_PROFILE_SHA256 = "99a526cead816010373cdd81cd889d33fa359b5d0b74d87743e51d0f649f1113"
EXPECTED_DTO_SHA256 = "2d5ff42aa3a8fee6ed7995be0e430dee18aa36bde6fc5144fd1484532d67ee47"
EXPECTED_LOCK_SHA256 = "d7073279fd5e8b1438fab3481f8654841b4e9445244d3b0369c5cad2cfe8111a"
PARENT_LOCK_SHA256 = "0d2f11dc5ee41038a1ef63b8b4157730bd1cd313c7a98faaa286132397b8de47"
EXPECTED_P3_AUTHORITY_SHA256 = "76726fc533cde7b0a183a1575cb50276e166081cc37ebe4857ed3324ab913e3b"
EXPECTED_P3_DTO_SUBSET_SHA256 = "90b2f51d0c9b81ed0b3d6ff4294a945c087578a41c01a9c11a5ac7571f6ad91f"
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


def _load(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} root must be object")
    return value


def _lock_entry(lock: dict[str, Any], filename: str) -> dict[str, Any]:
    rows = lock.get("artifacts")
    if not isinstance(rows, list):
        raise ValueError("BASELINE_LOCK artifacts invalid")
    for raw in rows:
        if isinstance(raw, dict) and raw.get("file") == filename:
            return raw
    raise ValueError(f"{filename} missing from BASELINE_LOCK")


def verify() -> dict[str, object]:
    authority = _load(AUTHORITY)
    role_profile = _load(ROLE_PROFILE)
    dto = _load(DTO)
    core = _load(CORE)
    lock = _load(LOCK)
    dto_contracts = dto["contracts"]
    p3_subset = {name: dto_contracts.get(name, {}) for name in P3_DTO_NAMES}
    m8_subset = {name: dto_contracts.get(name, {}) for name in M8_DTO_NAMES}
    lineage = lock["baseline"]["lock_lineage_sha256"]
    role_names = [row["role"] for row in role_profile["role_matrix"]]
    role_by_name = {row["role"]: row for row in role_profile["role_matrix"]}

    checks: dict[str, bool] = {
        "authority_sha": _sha(AUTHORITY) == EXPECTED_AUTHORITY_SHA256,
        "role_profile_sha": _sha(ROLE_PROFILE) == EXPECTED_ROLE_PROFILE_SHA256,
        "m8_dto_subset_preserved": (
            _canonical_hash(m8_subset) == EXPECTED_M8_DTO_SUBSET_SHA256
        ),
        "m8_lock_lineage_preserved": EXPECTED_LOCK_SHA256 in lineage,
        "p3_authority_immutable": _sha(P3_AUTHORITY) == EXPECTED_P3_AUTHORITY_SHA256,
        "identity": (
            authority.get("authority_id") == "P4_P5_TRAINING_ASSESSMENT_AUTHORITY"
            and authority.get("version") == "1.0.0"
            and role_profile.get("profile_id") == "P4_P5_ROLE_PRIVACY_PROFILE"
            and role_profile.get("version") == "1.0.0"
        ),
        "schema_unchanged": (
            authority["scope"]["db_schema_change"] is False
            and authority["scope"]["db_schema_version"] == "1.6.0"
            and authority["scope"]["shadow_schema_permitted"] is False
            and role_profile["scope"]["db_schema_change"] is False
            and role_profile["scope"]["shadow_schema_permitted"] is False
        ),
        "p1_p2_p3_immutable": (
            authority["scope"]["p1_observed_layer_immutable"] is True
            and authority["scope"]["p2_adjusted_layer_immutable"] is True
            and authority["scope"]["p3_capability_layer_immutable"] is True
        ),
        "p4_p5_not_admitted": authority["scope"][
            "p4_p5_authority_frozen_not_admitted"
        ]
        is True,
        "p6_inactive": (
            authority["scope"]["p6_active"] is False
            and role_profile["activation_rule"]["p6_active"] is False
        ),
        "subject_identity_exact": (
            authority["exact_identity_rules"]["p4_subject_context_identity_prefix"]
            == "P4_SUBJECT_CONTEXT_SHA256:"
            and authority["subject_context_contract"]["exact_role_model_binding_required"]
            is True
            and authority["subject_context_contract"]["exact_twin_revision_required"]
            is True
            and authority["subject_context_contract"][
                "current_latest_default_p3_resolution_forbidden"
            ]
            is True
        ),
        "composition_exact": (
            authority["exact_identity_rules"]["p5_composition_identity_prefix"]
            == "P5_COMPOSITION_SHA256:"
            and authority["composition_contract"]["stable_participant_order_required"]
            is True
            and authority["composition_contract"][
                "membership_or_role_or_aircraft_or_twin_or_p4_or_context_change_creates_new_identity"
            ]
            is True
        ),
        "evidence_separation": (
            authority["evidence_boundary_contract"]["machine_and_human_evidence_distinct"]
            is True
            and authority["evidence_boundary_contract"][
                "zero_fill_for_unavailable_ood_not_identifiable_forbidden"
            ]
            is True
        ),
        "annotation_revision": (
            authority["instructor_annotation_contract"]["revision_creates_new_annotation_id"]
            is True
            and authority["instructor_annotation_contract"][
                "machine_evidence_overwrite_forbidden"
            ]
            is True
            and authority["instructor_annotation_contract"]["physical_delete_forbidden"]
            is True
        ),
        "approval_audit": (
            authority["approval_workflow_contract"][
                "transition_creates_new_assessment_revision"
            ]
            is True
            and authority["approval_workflow_contract"]["audit_request_id_required"]
            is True
            and authority["approval_workflow_contract"][
                "admin_auditor_role_alone_does_not_grant_approval"
            ]
            is True
        ),
        "status_not_zero": (
            authority["status_contract"]["evidence_availability_states"]
            == ["AVAILABLE", "UNAVAILABLE", "OUT_OF_DOMAIN", "NOT_IDENTIFIABLE"]
            and authority["status_contract"][
                "unavailable_numeric_zero_substitution_forbidden"
            ]
            is True
        ),
        "aggregation_no_invented_formula": (
            authority["aggregation_contract"]["default_aggregation_profile"] is None
            and authority["aggregation_contract"]["implementation_default_formula_forbidden"]
            is True
            and authority["aggregation_contract"]["implementation_default_weight_forbidden"]
            is True
            and authority["aggregation_contract"][
                "implementation_default_threshold_forbidden"
            ]
            is True
            and authority["aggregation_contract"]["no_profile_behavior"]
            == "EVIDENCE_ONLY_SCORE_AND_GRADE_NULL"
        ),
        "role_matrix_exact": role_names
        == [
            "SUBJECT_SELF",
            "INSTRUCTOR_EVALUATOR",
            "TEAM_LEAD",
            "ANALYST",
            "ADMIN_AUDITOR",
        ],
        "least_privilege": (
            role_profile["scope"]["default_deny"] is True
            and role_by_name["ANALYST"]["direct_actor_id"] is False
            and role_by_name["TEAM_LEAD"]["direct_actor_id"] is False
            and role_by_name["ADMIN_AUDITOR"]["approval_write"] is False
            and role_by_name["INSTRUCTOR_EVALUATOR"]["approval_write"] is True
        ),
        "pseudonymization_exact": (
            role_profile["pseudonymization_contract"]["output_prefix"]
            == "SUBJECT_SHA256:"
            and role_profile["pseudonymization_contract"]["digest"] == "SHA256"
            and role_profile["pseudonymization_contract"]["stable_within_profile_version"]
            is True
        ),
        "role_model_carrier": (
            role_profile["context_binding_contract"]["carrier_table"]
            == "registry.context_artifact"
            and role_profile["context_binding_contract"]["binding_table"]
            == "context.context_artifact_binding"
            and role_profile["context_binding_contract"]["artifact_kind"] == "ROLE_MODEL"
            and role_profile["context_binding_contract"]["binding_role"] == "ROLE_MODEL"
        ),
        "admission_guard": (
            authority["admission_guard"]["required_event"] == "push"
            and authority["admission_guard"]["required_git_ref"] == "refs/heads/main"
            and authority["admission_guard"]["required_m8_exit_decision"] == "GO"
            and authority["admission_guard"]["required_job_count"] == 14
            and authority["activation_rule"]["authority_adoption_does_not_admit_p4_or_p5"]
            is True
        ),
        "role_profile_bindings": (
            role_profile["source_bindings"]["p4_p5_authority_sha256"]
            == EXPECTED_AUTHORITY_SHA256
            and role_profile["source_bindings"]["cross_layer_dto_sha256"]
            == EXPECTED_DTO_SHA256
            and role_profile["source_bindings"]["core_logical_model_sha256"]
            == _sha(CORE)
            and role_profile["source_bindings"]["extension_contract_registry_sha256"]
            == _sha(EXTENSION)
            and role_profile["source_bindings"]["p3_authority_sha256"]
            == EXPECTED_P3_AUTHORITY_SHA256
        ),
        "legacy_p3_dto_subset_preserved": (
            _canonical_hash(p3_subset) == EXPECTED_P3_DTO_SUBSET_SHA256
        ),
        "lock_lineage": (
            EXPECTED_LOCK_SHA256 in lineage
            and PARENT_LOCK_SHA256 in lineage
            and lineage.index(EXPECTED_LOCK_SHA256)
            < lineage.index(PARENT_LOCK_SHA256)
        ),
    }
    for filename, path, expected in (
        (
            "P4_P5_TRAINING_ASSESSMENT_AUTHORITY.json",
            AUTHORITY,
            EXPECTED_AUTHORITY_SHA256,
        ),
        ("P4_P5_ROLE_PRIVACY_PROFILE.json", ROLE_PROFILE, EXPECTED_ROLE_PROFILE_SHA256),
    ):
        entry = _lock_entry(lock, filename)
        checks[f"lock:{filename}"] = (
            entry.get("sha256") == expected and entry.get("bytes") == len(path.read_bytes())
        )
    dto_entry = _lock_entry(lock, "CROSS_LAYER_DTO_CONTRACTS.json")
    checks["lock:CROSS_LAYER_DTO_CONTRACTS.json"] = (
        dto_entry.get("sha256") == _sha(DTO)
        and dto_entry.get("bytes") == len(DTO.read_bytes())
    )
    for name in ["exact_identity_rules","subject_context_contract","composition_contract","evidence_boundary_contract","instructor_annotation_contract","approval_workflow_contract","status_contract","role_privacy_contract","aggregation_contract","knowledge_time_contract","release_replay_contract","admission_guard","dto_contracts"]:
        checks[f"authority_hash:{name}"] = (
            authority["contract_hashes"][f"{name}_sha256"]
            == _canonical_hash(authority[name])
        )
    for name in ["context_binding_contract","pseudonymization_contract","role_matrix","projection_contract","write_authorization_contract","export_audit_contract","forbidden_fallbacks"]:
        checks[f"role_hash:{name}"] = (
            role_profile["contract_hashes"][f"{name}_sha256"]
            == _canonical_hash(role_profile[name])
        )
    for name, expected in authority["dto_contracts"].items():
        fields = dto_contracts[name]["fields"]
        checks[f"dto:{name}"] = [field["field"] for field in fields] == expected["fields"]
    tables = core["tables"]
    for table in (
        "assessment.actor_assessment",
        "assessment.competency_observation",
        "assessment.mission_assessment",
        "assessment.objective_result",
        "debrief.annotation",
        "audit.audit_log",
        "metric.evidence_set",
        "world.world_relation",
        "registry.context_artifact",
        "context.context_artifact_binding",
        "registry.object_reference",
        "capability.aircraft_twin_revision",
        "capability.intrinsic_capability_estimate",
    ):
        checks[f"core:{table}"] = tables[table]["schema_version"] == "1.6.0"
    failed = sorted(name for name, ok in checks.items() if not ok)
    return {
        "schema": "TPAA_M8_C3_P4_P5_AUTHORITY_EVIDENCE_V1",
        "task_id": "M8-GOV-001",
        "tracking_issue": 181,
        "status": "PASS" if not failed else "FAIL",
        "authority_sha256": EXPECTED_AUTHORITY_SHA256,
        "role_profile_sha256": EXPECTED_ROLE_PROFILE_SHA256,
        "dto_sha256": _sha(DTO),
        "baseline_lock_sha256": _sha(LOCK),
        "checks": checks,
        "failed_checks": failed,
        "task_complete": False,
        "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
    }


def main() -> int:
    try:
        result = verify()
    except Exception as exc:
        result = {
            "schema": "TPAA_M8_C3_P4_P5_AUTHORITY_EVIDENCE_V1",
            "task_id": "M8-GOV-001",
            "tracking_issue": 181,
            "status": "FAIL",
            "task_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
