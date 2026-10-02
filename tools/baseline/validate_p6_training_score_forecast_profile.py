#!/usr/bin/env python3
"""Validate the adopted M9 P6 training-score forecast execution profile exactly."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
CANONICAL = BASELINE / "canonical"
PROFILE = CANONICAL / "P6_TRAINING_SCORE_OLS_MAD_FORECAST_PROFILE.json"
AUTHORITY = CANONICAL / "P6_PREDICTION_COUNTERFACTUAL_AUTHORITY.json"
P4_P5_AUTHORITY = CANONICAL / "P4_P5_TRAINING_ASSESSMENT_AUTHORITY.json"
DTO = CANONICAL / "CROSS_LAYER_DTO_CONTRACTS.json"
CORE = CANONICAL / "CORE_LOGICAL_MODEL.json"
EXTENSION = CANONICAL / "EXTENSION_CONTRACT_REGISTRY.json"
M4 = CANONICAL / "M4_LONGITUDINAL_DEBRIEF_AUTHORITY.json"
LOCK = BASELINE / "BASELINE_LOCK.json"

EXPECTED_PROFILE_SHA256 = "43bf6f3814d764de812c6ff478600959b3f7bd9c54e6b8bfec5297531271d038"
EXPECTED_ADOPTION_LOCK_SHA256 = "2852dc2904854fcd65e3207ddda4859795b003e839ff1d95e241b199879ddd1f"
EXPECTED_PARENT_LOCK_SHA256 = "ba4f152a09206bcbaf06a1882d08763b332e95068ada0404a969073a7dc13a08"
EXPECTED_AUTHORITY_SHA256 = "a138c97e6c9891f767ee25de8841e2bc9ca899ddf6d09b98b9e4bae73d9be79e"
EXPECTED_P4_P5_AUTHORITY_SHA256 = "749360544e3e403e3a81b4992797d5186c93d1f06a92e96f1352c4ab4ed4cb77"
EXPECTED_DTO_SHA256 = "28f7209e40709fb4eb53ceffdfee3542e867f060c4e63605cc1ad149a8e3819a"
EXPECTED_CORE_SHA256 = "cfde6638e6899167267375c899bff2f04a490ce12f32e0005be4e15dda956245"
EXPECTED_EXTENSION_SHA256 = "f987ea2801557befac44aaf3b47b3953a5cdbaaa662e39c2f3970526f3371f41"
EXPECTED_M4_SHA256 = "c1c073bce8870feceb90bdb6c28172c4c726de6b15fc70208e169336baa59dfa"

CONTRACT_SECTIONS = (
    "source_eligibility_contract",
    "feature_target_contract",
    "ordering_contract",
    "arithmetic_contract",
    "training_validation_contract",
    "uncertainty_calibration_contract",
    "applicability_contract",
    "forecast_contract",
    "managed_object_contract",
    "replay_supersession_contract",
    "identity_contract",
    "safety_boundary",
    "forbidden_fallbacks",
    "qualification_matrix",
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
    for row in rows:
        if isinstance(row, dict) and row.get("file") == filename:
            return row
    raise ValueError(f"{filename} missing from BASELINE_LOCK")


def verify() -> dict[str, object]:
    profile = _load(PROFILE)
    authority = _load(AUTHORITY)
    p4_p5 = _load(P4_P5_AUTHORITY)
    dto = _load(DTO)
    core = _load(CORE)
    extension = _load(EXTENSION)
    m4 = _load(M4)
    lock = _load(LOCK)
    current_lock_sha = _sha(LOCK)
    lineage = lock["baseline"]["lock_lineage_sha256"]

    adoption_chain_ok = (
        current_lock_sha == EXPECTED_ADOPTION_LOCK_SHA256
        and lineage
        and lineage[0] == EXPECTED_PARENT_LOCK_SHA256
    ) or (
        EXPECTED_ADOPTION_LOCK_SHA256 in lineage
        and EXPECTED_PARENT_LOCK_SHA256 in lineage
        and lineage.index(EXPECTED_ADOPTION_LOCK_SHA256)
        < lineage.index(EXPECTED_PARENT_LOCK_SHA256)
    )

    checks: dict[str, bool] = {
        "profile_sha": _sha(PROFILE) == EXPECTED_PROFILE_SHA256,
        "authority_immutable": _sha(AUTHORITY) == EXPECTED_AUTHORITY_SHA256,
        "p4_p5_authority_immutable": (
            _sha(P4_P5_AUTHORITY) == EXPECTED_P4_P5_AUTHORITY_SHA256
        ),
        "dto_immutable": _sha(DTO) == EXPECTED_DTO_SHA256,
        "core_immutable": _sha(CORE) == EXPECTED_CORE_SHA256,
        "extension_immutable": _sha(EXTENSION) == EXPECTED_EXTENSION_SHA256,
        "m4_immutable": _sha(M4) == EXPECTED_M4_SHA256,
        "adoption_lock_chain": adoption_chain_ok,
        "identity": (
            profile.get("profile_id") == "P6_TRAINING_SCORE_OLS_MAD_FORECAST"
            and profile.get("version") == "1.0.0"
            and profile.get("change_class") == "C3_EXECUTION_PROFILE"
            and profile.get("tracking_issue") == 196
        ),
        "source_bindings": (
            profile["source_bindings"]["p6_authority_sha256"]
            == EXPECTED_AUTHORITY_SHA256
            and profile["source_bindings"]["p4_p5_authority_sha256"]
            == EXPECTED_P4_P5_AUTHORITY_SHA256
            and profile["source_bindings"]["cross_layer_dto_sha256"]
            == EXPECTED_DTO_SHA256
            and profile["source_bindings"]["core_logical_model_sha256"]
            == EXPECTED_CORE_SHA256
            and profile["source_bindings"]["extension_contract_registry_sha256"]
            == EXPECTED_EXTENSION_SHA256
            and profile["source_bindings"]["m4_longitudinal_authority_sha256"]
            == EXPECTED_M4_SHA256
        ),
        "activation_is_adoption_not_admission": (
            profile["activation_rule"][
                "profile_effective_only_after_exact_head_ci_guarded_merge_and_protected_main_ci"
            ]
            is True
            and profile["activation_rule"]["profile_adoption_does_not_admit_p6"]
            is True
            and profile["activation_rule"][
                "p6_external_claim_requires_protected_main_m9_exit_go"
            ]
            is True
        ),
        "schema_unchanged": (
            profile["scope"]["db_schema_change"] is False
            and profile["scope"]["db_schema_version"] == "1.6.0"
            and profile["scope"]["shadow_schema_permitted"] is False
            and lock["baseline"]["db_schema"] == "1.6.0"
        ),
        "runtime_binding_exact": (
            profile["runtime_binding"]["model_spec_id"]
            == "P6_MODEL_SPEC:P6_TRAINING_SCORE_OLS_MAD_FORECAST"
            and profile["runtime_binding"]["model_spec_version"] == "1.0.0"
            and profile["runtime_binding"]["plugin_name"]
            == "TRAINING_SCORE_OLS_MAD_FORECAST"
            and profile["runtime_binding"]["plugin_version"] == "1.0.0"
            and profile["runtime_binding"]["exact_identity_only"] is True
            and profile["runtime_binding"]["current_latest_default_forbidden"]
            is True
        ),
        "training_evaluation_only": (
            profile["scope"]["domain"] == "TRAINING_EVALUATION"
            and profile["scope"]["allowed_target_kinds"]
            == ["P4_ASSESSMENT_SCORE", "P5_OVERALL_SCORE"]
            and profile["scope"]["operational_tactical_use_forbidden"] is True
            and profile["scope"]["weapon_employment_target_forbidden"] is True
            and profile["scope"]["command_or_control_output_forbidden"] is True
        ),
        "approved_numeric_sources_only": (
            profile["source_eligibility_contract"][
                "required_assessment_approval_state"
            ]
            == "APPROVED"
            and profile["source_eligibility_contract"]["finite_numeric_required"]
            is True
            and profile["source_eligibility_contract"][
                "p5_exact_aggregation_profile_ref_required_for_numeric_target"
            ]
            is True
            and profile["source_eligibility_contract"][
                "missing_numeric_score_policy"
            ]
            == "INSUFFICIENT_EVIDENCE_NO_IMPUTATION"
        ),
        "leakage_fail_closed": (
            profile["source_eligibility_contract"]["future_information_forbidden"]
            is True
            and profile["source_eligibility_contract"][
                "same_outcome_or_forecast_session_target_leakage_forbidden"
            ]
            is True
            and profile["training_validation_contract"][
                "training_validation_identity_overlap_forbidden"
            ]
            is True
        ),
        "deterministic_ols_no_rng": (
            profile["arithmetic_contract"]["estimator"]
            == "ORDINARY_LEAST_SQUARES"
            and profile["arithmetic_contract"]["residual_statistic"]
            == "UNSCALED_MEDIAN_ABSOLUTE_DEVIATION"
            and profile["arithmetic_contract"]["no_rng"] is True
            and profile["training_validation_contract"]["random_split_forbidden"]
            is True
        ),
        "temporal_validation_exact": (
            profile["training_validation_contract"]["strategy"]
            == "TEMPORAL_LAST_POINT_HOLDOUT_THEN_FINAL_REFIT"
            and profile["training_validation_contract"]["minimum_total_eligible_points"]
            == 4
            and profile["training_validation_contract"]["holdout_count"] == 1
            and profile["training_validation_contract"]["training_prefix_min_points"]
            == 3
            and profile["training_validation_contract"]["training_prefix_max_points"]
            == 5
            and profile["training_validation_contract"]["accuracy_threshold_or_multiplier"]
            is None
        ),
        "uncertainty_is_explicit_calibration": (
            profile["uncertainty_calibration_contract"]["calibration_evidence_required"]
            is True
            and profile["uncertainty_calibration_contract"]["half_width_rule"]
            == "max(holdout_component,final_refit_component)"
            and profile["uncertainty_calibration_contract"][
                "unquantified_uncertainty_fallback_forbidden"
            ]
            is True
            and profile["uncertainty_calibration_contract"][
                "threshold_probability_output_supported"
            ]
            is False
        ),
        "applicability_matches_authority": (
            profile["applicability_contract"]["states"]
            == authority["applicability_uncertainty_contract"]["applicability_states"]
            and profile["applicability_contract"][
                "numeric_forecast_allowed_only_when"
            ]
            == "APPLICABLE"
            and profile["applicability_contract"][
                "out_of_domain_zero_coercion_forbidden"
            ]
            is True
        ),
        "single_next_session_horizon": (
            profile["forecast_contract"]["horizon_type"] == "NEXT_SESSION_ORDER"
            and profile["forecast_contract"]["horizon_steps"] == 1
            and profile["forecast_contract"]["multi_step_recursive_forecast_forbidden"]
            is True
            and profile["forecast_contract"][
                "threshold_probabilities_forbidden_profile_v1"
            ]
            is True
        ),
        "managed_object_fail_closed": (
            profile["managed_object_contract"]["required_gc_state"] == "ACTIVE"
            and profile["managed_object_contract"]["required_sealed"] is True
            and profile["managed_object_contract"]["required_deleted_at"] is None
            and profile["managed_object_contract"][
                "model_artifact_hash_must_match_managed_object"
            ]
            is True
        ),
        "historical_replay_immutable": (
            profile["replay_supersession_contract"][
                "historical_current_latest_default_resolution_forbidden"
            ]
            is True
            and profile["replay_supersession_contract"][
                "later_observed_outcome_must_not_rewrite_prior_forecast"
            ]
            is True
            and profile["replay_supersession_contract"][
                "original_forecast_origin_and_as_of_preserved"
            ]
            is True
        ),
        "safety_boundary": (
            profile["safety_boundary"]["advisory_projection_only"] is True
            and profile["safety_boundary"][
                "operational_or_tactical_optimization_forbidden"
            ]
            is True
            and profile["safety_boundary"]["weapon_or_targeting_recommendation_forbidden"]
            is True
            and profile["safety_boundary"]["mission_command_generation_forbidden"]
            is True
            and profile["safety_boundary"]["p1_p5_fact_mutation_forbidden"] is True
        ),
        "p4_p5_numeric_aggregation_still_profile_bound": (
            p4_p5["aggregation_contract"]["default_aggregation_profile"] is None
            and p4_p5["aggregation_contract"][
                "exact_profile_formula_weight_threshold_required_for_numeric_aggregate"
            ]
            is True
        ),
        "p6_still_has_no_default_model": (
            authority["model_authority_contract"]["default_model_profile"] is None
            and authority["model_authority_contract"][
                "exact_adopted_model_profile_required_for_execution"
            ]
            is True
        ),
        "extension_safety_boundary_preserved": any(
            "Operational/tactical optimization remains outside" in rule
            for rule in extension["p_capability_contracts"]["P6"]["rules"]
        ),
        "m4_numeric_semantics_reused_without_m4_product_mutation": (
            m4["trend_profile"]["profile_hash"]
            == "87981c6e3c79f9587786d082d826a6393d15192f67b10c817612da8912982729"
            and profile["scope"]["p1_p5_historical_products_immutable"] is True
        ),
    }

    entry = _lock_entry(lock, PROFILE.name)
    checks["lock_profile_exact"] = (
        entry.get("sha256") == EXPECTED_PROFILE_SHA256
        and entry.get("bytes") == len(PROFILE.read_bytes())
    )
    checks["controlled_artifact_count"] = len(lock["artifacts"]) >= 33

    for section in CONTRACT_SECTIONS:
        checks[f"profile_hash:{section}"] = (
            profile["contract_hashes"][f"{section}_sha256"]
            == _canonical_hash(profile[section])
        )

    for table in (
        "registry.context_artifact",
        "registry.dataset_snapshot",
        "registry.object_reference",
        "capability.capability_model",
        "intelligence.forecast_run",
        "intelligence.forecast_result",
    ):
        checks[f"core:{table}"] = core["tables"][table]["schema_version"] == "1.6.0"

    dto_contracts = dto["contracts"]
    for name in (
        "P4AssessmentRevisionDTO",
        "P5AssessmentRevisionDTO",
        "P6InputSnapshotDTO",
        "P6ModelRevisionDTO",
        "P6ForecastRequestDTO",
        "P6ForecastResultDTO",
    ):
        checks[f"dto:{name}"] = name in dto_contracts

    failed = sorted(name for name, ok in checks.items() if not ok)
    return {
        "schema": "TPAA_M9_C3_P6_EXECUTION_PROFILE_EVIDENCE_V1",
        "task_id": "M9-MODEL-001",
        "subgate": "C3_EXECUTION_PROFILE_ADOPTION",
        "tracking_issue": 196,
        "status": "PASS" if not failed else "FAIL",
        "profile_sha256": EXPECTED_PROFILE_SHA256,
        "adoption_baseline_lock_sha256": EXPECTED_ADOPTION_LOCK_SHA256,
        "current_baseline_lock_sha256": current_lock_sha,
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
            "schema": "TPAA_M9_C3_P6_EXECUTION_PROFILE_EVIDENCE_V1",
            "task_id": "M9-MODEL-001",
            "subgate": "C3_EXECUTION_PROFILE_ADOPTION",
            "tracking_issue": 196,
            "status": "FAIL",
            "task_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
