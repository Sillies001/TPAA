#!/usr/bin/env python3
"""Validate the M9 P6 prediction/counterfactual authority exactly."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
CANONICAL = BASELINE / "canonical"
AUTHORITY = CANONICAL / "P6_PREDICTION_COUNTERFACTUAL_AUTHORITY.json"
ROLE_PROFILE = CANONICAL / "P6_ROLE_PRIVACY_RELEASE_PROFILE.json"
DTO = CANONICAL / "CROSS_LAYER_DTO_CONTRACTS.json"
CORE = CANONICAL / "CORE_LOGICAL_MODEL.json"
EXTENSION = CANONICAL / "EXTENSION_CONTRACT_REGISTRY.json"
M8_AUTHORITY = CANONICAL / "P4_P5_TRAINING_ASSESSMENT_AUTHORITY.json"
M8_ROLE_PROFILE = CANONICAL / "P4_P5_ROLE_PRIVACY_PROFILE.json"
LOCK = BASELINE / "BASELINE_LOCK.json"

EXPECTED_AUTHORITY_SHA256 = "a138c97e6c9891f767ee25de8841e2bc9ca899ddf6d09b98b9e4bae73d9be79e"
EXPECTED_ROLE_PROFILE_SHA256 = "d5eff80dbfa912955ae7b09bc3e4a2868650466560cb1a5b1f558434e8076713"
EXPECTED_DTO_SHA256 = "28f7209e40709fb4eb53ceffdfee3542e867f060c4e63605cc1ad149a8e3819a"
EXPECTED_LOCK_SHA256 = "ba4f152a09206bcbaf06a1882d08763b332e95068ada0404a969073a7dc13a08"
EXPECTED_M8_LOCK_SHA256 = "d7073279fd5e8b1438fab3481f8654841b4e9445244d3b0369c5cad2cfe8111a"
EXPECTED_M8_AUTHORITY_SHA256 = "749360544e3e403e3a81b4992797d5186c93d1f06a92e96f1352c4ab4ed4cb77"
EXPECTED_M8_ROLE_PROFILE_SHA256 = "99a526cead816010373cdd81cd889d33fa359b5d0b74d87743e51d0f649f1113"
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
    extension = _load(EXTENSION)
    lock = _load(LOCK)

    dto_contracts = dto["contracts"]
    m8_subset = {name: dto_contracts.get(name, {}) for name in M8_DTO_NAMES}
    p6_fields = {
        name: [row["field"] for row in dto_contracts[name]["fields"]]
        for name in P6_DTO_NAMES
    }
    roles = {row["role"]: row for row in role_profile["role_matrix"]}
    lineage = lock["baseline"]["lock_lineage_sha256"]

    checks: dict[str, bool] = {
        "authority_sha": _sha(AUTHORITY) == EXPECTED_AUTHORITY_SHA256,
        "role_profile_sha": _sha(ROLE_PROFILE) == EXPECTED_ROLE_PROFILE_SHA256,
        "dto_sha": _sha(DTO) == EXPECTED_DTO_SHA256,
        "m9_c3_lock_lineage_preserved": EXPECTED_LOCK_SHA256 in lineage,
        "m8_authority_immutable": (
            _sha(M8_AUTHORITY) == EXPECTED_M8_AUTHORITY_SHA256
        ),
        "m8_role_profile_immutable": (
            _sha(M8_ROLE_PROFILE) == EXPECTED_M8_ROLE_PROFILE_SHA256
        ),
        "m8_dto_subset_preserved": (
            _canonical_hash(m8_subset) == EXPECTED_M8_DTO_SUBSET_SHA256
        ),
        "m8_lock_lineage_preserved": (
            EXPECTED_M8_LOCK_SHA256 in lineage
            and EXPECTED_LOCK_SHA256 in lineage
            and lineage.index(EXPECTED_LOCK_SHA256)
            < lineage.index(EXPECTED_M8_LOCK_SHA256)
        ),
        "identity": (
            authority.get("authority_id")
            == "P6_PREDICTION_COUNTERFACTUAL_AUTHORITY"
            and authority.get("version") == "1.0.0"
            and role_profile.get("profile_id")
            == "P6_ROLE_PRIVACY_RELEASE_PROFILE"
            and role_profile.get("version") == "1.0.0"
        ),
        "schema_unchanged": (
            authority["scope"]["db_schema_change"] is False
            and authority["scope"]["db_schema_version"] == "1.6.0"
            and authority["scope"]["shadow_schema_permitted"] is False
            and role_profile["scope"]["db_schema_change"] is False
            and role_profile["scope"]["shadow_schema_permitted"] is False
            and lock["baseline"]["db_schema"] == "1.6.0"
        ),
        "p1_p5_immutable_p6_not_admitted": (
            authority["scope"]["p1_p5_historical_products_immutable"] is True
            and authority["scope"]["p6_authority_frozen_not_admitted"] is True
            and authority["activation_rule"][
                "authority_adoption_does_not_admit_p6"
            ]
            is True
        ),
        "no_default_model_or_threshold": (
            authority["model_authority_contract"]["default_model_profile"] is None
            and authority["model_authority_contract"][
                "implementation_default_model_family_forbidden"
            ]
            is True
            and authority["model_authority_contract"][
                "implementation_default_threshold_forbidden"
            ]
            is True
        ),
        "fact_projection_and_leakage_guards": (
            authority["scope"][
                "fact_projection_physical_and_semantic_separation_required"
            ]
            is True
            and authority["input_snapshot_contract"][
                "future_information_forbidden"
            ]
            is True
            and authority["input_snapshot_contract"][
                "same_outcome_information_forbidden"
            ]
            is True
            and authority["forecast_contract"][
                "projection_to_fact_upgrade_forbidden"
            ]
            is True
        ),
        "applicability_uncertainty_fail_closed": (
            authority["applicability_uncertainty_contract"][
                "numeric_projection_allowed_only_when_applicable"
            ]
            is True
            and authority["applicability_uncertainty_contract"][
                "explicit_uncertainty_required_for_numeric_projection"
            ]
            is True
            and authority["applicability_uncertainty_contract"][
                "out_of_domain_zero_coercion_forbidden"
            ]
            is True
        ),
        "counterfactual_causal_boundary": (
            authority["counterfactual_contract"]["default_causal_claim_level"]
            == "SCENARIO_PROJECTION_NON_CAUSAL"
            and authority["counterfactual_contract"][
                "stronger_causal_claim_requires_separately_adopted_authority"
            ]
            is True
            and authority["counterfactual_contract"][
                "association_to_causal_upgrade_forbidden"
            ]
            is True
        ),
        "recommendation_advisory_boundary": (
            authority["recommendation_contract"]["advisory_only"] is True
            and authority["recommendation_contract"][
                "automatic_command_forbidden"
            ]
            is True
            and authority["recommendation_contract"][
                "p1_p5_mutation_forbidden"
            ]
            is True
        ),
        "interop_exact_and_lossless": (
            authority["interoperability_contract"][
                "exact_external_profile_id_and_version_required"
            ]
            is True
            and authority["interoperability_contract"][
                "unversioned_external_alias_forbidden"
            ]
            is True
            and authority["interoperability_contract"][
                "lossy_phase_conversion_forbidden"
            ]
            is True
            and authority["interoperability_contract"][
                "second_fact_model_forbidden"
            ]
            is True
        ),
        "role_separation": (
            role_profile["scope"]["default_deny"] is True
            and roles["MODEL_REVIEWER"]["model_release"] is True
            and roles["MODEL_REVIEWER"]["recommendation_approval"] is False
            and roles["INSTRUCTOR_EVALUATOR"]["model_release"] is False
            and roles["INSTRUCTOR_EVALUATOR"]["recommendation_approval"] is True
            and roles["ADMIN_AUDITOR"]["model_release"] is False
        ),
        "admission_guard": (
            authority["admission_guard"]["required_event"] == "push"
            and authority["admission_guard"]["required_git_ref"]
            == "refs/heads/main"
            and authority["admission_guard"]["required_m9_exit_decision"] == "GO"
            and authority["admission_guard"]["required_job_count"] == 14
            and authority["admission_guard"][
                "p6_external_claim_before_gate_forbidden"
            ]
            is True
        ),
        "role_profile_bindings": (
            role_profile["source_bindings"]["p6_authority_sha256"]
            == EXPECTED_AUTHORITY_SHA256
            and role_profile["source_bindings"]["cross_layer_dto_sha256"]
            == EXPECTED_DTO_SHA256
            and role_profile["source_bindings"]["core_logical_model_sha256"]
            == _sha(CORE)
            and role_profile["source_bindings"][
                "extension_contract_registry_sha256"
            ]
            == _sha(EXTENSION)
            and role_profile["source_bindings"]["p4_p5_authority_sha256"]
            == EXPECTED_M8_AUTHORITY_SHA256
            and role_profile["source_bindings"][
                "p4_p5_role_privacy_profile_sha256"
            ]
            == EXPECTED_M8_ROLE_PROFILE_SHA256
        ),
        "post_c3_rebaseline_compatible": (
            EXPECTED_LOCK_SHA256 in lineage
            and len(lock["artifacts"]) >= 32
            and lock["baseline"]["db_schema"] == "1.6.0"
        ),
    }

    for filename, path, expected in (
        (
            "P6_PREDICTION_COUNTERFACTUAL_AUTHORITY.json",
            AUTHORITY,
            EXPECTED_AUTHORITY_SHA256,
        ),
        (
            "P6_ROLE_PRIVACY_RELEASE_PROFILE.json",
            ROLE_PROFILE,
            EXPECTED_ROLE_PROFILE_SHA256,
        ),
        ("CROSS_LAYER_DTO_CONTRACTS.json", DTO, EXPECTED_DTO_SHA256),
    ):
        entry = _lock_entry(lock, filename)
        checks[f"lock:{filename}"] = (
            entry.get("sha256") == expected
            and entry.get("bytes") == len(path.read_bytes())
        )

    for name in (
        "exact_identity_rules",
        "input_snapshot_contract",
        "model_authority_contract",
        "applicability_uncertainty_contract",
        "forecast_contract",
        "counterfactual_contract",
        "recommendation_contract",
        "interoperability_contract",
        "knowledge_time_contract",
        "release_replay_contract",
        "admission_guard",
        "dto_contracts",
    ):
        checks[f"authority_hash:{name}"] = (
            authority["contract_hashes"][f"{name}_sha256"]
            == _canonical_hash(authority[name])
        )

    for name in (
        "identity_privacy_contract",
        "role_matrix",
        "projection_contract",
        "write_authorization_contract",
        "release_approval_contract",
        "export_audit_contract",
        "forbidden_fallbacks",
    ):
        checks[f"role_hash:{name}"] = (
            role_profile["contract_hashes"][f"{name}_sha256"]
            == _canonical_hash(role_profile[name])
        )

    for name, frozen in authority["dto_contracts"].items():
        checks[f"dto:{name}"] = p6_fields[name] == frozen["fields"]

    for table in (
        "registry.dataset_snapshot",
        "capability.capability_model",
        "registry.object_reference",
        "intelligence.forecast_run",
        "intelligence.forecast_result",
        "intelligence.counterfactual_run",
        "intelligence.training_recommendation",
        "intelligence.intervention_outcome",
        "registry.training_session",
        "registry.data_source",
        "registry.source_stream",
        "registry.source_artifact",
        "audit.audit_log",
    ):
        checks[f"core:{table}"] = (
            core["tables"][table]["schema_version"] == "1.6.0"
        )

    p6_extension = extension["p_capability_contracts"]["P6"]
    checks["extension_p6_boundary"] = (
        "intelligence.forecast_run" in p6_extension["products"]
        and "intelligence.counterfactual_run" in p6_extension["products"]
        and "intelligence.training_recommendation" in p6_extension["products"]
        and any(
            "Operational/tactical optimization remains outside" in rule
            for rule in p6_extension["rules"]
        )
    )

    failed = sorted(name for name, ok in checks.items() if not ok)
    return {
        "schema": "TPAA_M9_C3_P6_AUTHORITY_EVIDENCE_V1",
        "task_id": "M9-GOV-001",
        "tracking_issue": 194,
        "status": "PASS" if not failed else "FAIL",
        "authority_sha256": EXPECTED_AUTHORITY_SHA256,
        "role_profile_sha256": EXPECTED_ROLE_PROFILE_SHA256,
        "dto_sha256": EXPECTED_DTO_SHA256,
        "baseline_lock_sha256": EXPECTED_LOCK_SHA256,
        "current_baseline_lock_sha256": _sha(LOCK),
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
            "schema": "TPAA_M9_C3_P6_AUTHORITY_EVIDENCE_V1",
            "task_id": "M9-GOV-001",
            "tracking_issue": 194,
            "status": "FAIL",
            "task_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
