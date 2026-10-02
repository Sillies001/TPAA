from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
PROFILE = (
    BASELINE
    / "canonical"
    / "P6_TRAINING_SCORE_OLS_MAD_FORECAST_PROFILE.json"
)
VALIDATOR_PATH = (
    ROOT
    / "tools"
    / "baseline"
    / "validate_p6_training_score_forecast_profile.py"
)

EXPECTED_PROFILE_SHA256 = "43bf6f3814d764de812c6ff478600959b3f7bd9c54e6b8bfec5297531271d038"

SPEC = importlib.util.spec_from_file_location("p6_profile_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def _profile() -> dict[str, object]:
    value = json.loads(PROFILE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_p6_execution_profile_is_controlled_and_loadable() -> None:
    assert hashlib.sha256(PROFILE.read_bytes()).hexdigest() == EXPECTED_PROFILE_SHA256
    loader = CanonicalArtifactLoader(BASELINE)
    artifact = loader.load(
        "P6_TRAINING_SCORE_OLS_MAD_FORECAST_PROFILE",
        expectation=ArtifactExpectation(
            version="1.0.0",
            schema_version="1.6.0",
            required_top_level_keys=(
                "source_bindings",
                "runtime_binding",
                "source_eligibility_contract",
                "training_validation_contract",
                "uncertainty_calibration_contract",
                "applicability_contract",
                "forecast_contract",
                "safety_boundary",
            ),
        ),
    )
    assert artifact.sha256 == EXPECTED_PROFILE_SHA256


def test_p6_execution_profile_validator_passes_without_claiming_task_completion() -> None:
    result = VALIDATOR.verify()
    assert result["status"] == "PASS"
    assert result["failed_checks"] == []
    assert result["task_complete"] is False
    assert all(result["checks"].values())


def test_p6_profile_uses_only_approved_governed_training_scores() -> None:
    profile = _profile()
    eligibility = profile["source_eligibility_contract"]
    scope = profile["scope"]
    assert isinstance(eligibility, dict)
    assert isinstance(scope, dict)
    assert scope["allowed_target_kinds"] == [
        "P4_ASSESSMENT_SCORE",
        "P5_OVERALL_SCORE",
    ]
    assert eligibility["required_assessment_approval_state"] == "APPROVED"
    assert eligibility["finite_numeric_required"] is True
    assert eligibility[
        "p5_exact_aggregation_profile_ref_required_for_numeric_target"
    ] is True
    assert eligibility["missing_numeric_score_policy"] == (
        "INSUFFICIENT_EVIDENCE_NO_IMPUTATION"
    )


def test_p6_profile_is_deterministic_and_leakage_safe() -> None:
    profile = _profile()
    arithmetic = profile["arithmetic_contract"]
    validation = profile["training_validation_contract"]
    eligibility = profile["source_eligibility_contract"]
    assert isinstance(arithmetic, dict)
    assert isinstance(validation, dict)
    assert isinstance(eligibility, dict)
    assert arithmetic["estimator"] == "ORDINARY_LEAST_SQUARES"
    assert arithmetic["residual_statistic"] == "UNSCALED_MEDIAN_ABSOLUTE_DEVIATION"
    assert arithmetic["no_rng"] is True
    assert validation["random_split_forbidden"] is True
    assert validation["training_validation_identity_overlap_forbidden"] is True
    assert eligibility["future_information_forbidden"] is True
    assert eligibility["same_outcome_or_forecast_session_target_leakage_forbidden"] is True


def test_p6_profile_has_exact_temporal_validation_and_single_step_horizon() -> None:
    profile = _profile()
    validation = profile["training_validation_contract"]
    forecast = profile["forecast_contract"]
    assert isinstance(validation, dict)
    assert isinstance(forecast, dict)
    assert validation["strategy"] == "TEMPORAL_LAST_POINT_HOLDOUT_THEN_FINAL_REFIT"
    assert validation["minimum_total_eligible_points"] == 4
    assert validation["training_prefix_min_points"] == 3
    assert validation["training_prefix_max_points"] == 5
    assert validation["accuracy_threshold_or_multiplier"] is None
    assert forecast["horizon_type"] == "NEXT_SESSION_ORDER"
    assert forecast["horizon_steps"] == 1
    assert forecast["multi_step_recursive_forecast_forbidden"] is True
    assert forecast["threshold_probabilities_forbidden_profile_v1"] is True


def test_p6_profile_requires_explicit_uncertainty_and_applicability() -> None:
    profile = _profile()
    uncertainty = profile["uncertainty_calibration_contract"]
    applicability = profile["applicability_contract"]
    assert isinstance(uncertainty, dict)
    assert isinstance(applicability, dict)
    assert uncertainty["calibration_evidence_required"] is True
    assert uncertainty["half_width_rule"] == (
        "max(holdout_component,final_refit_component)"
    )
    assert uncertainty["unquantified_uncertainty_fallback_forbidden"] is True
    assert applicability["numeric_forecast_allowed_only_when"] == "APPLICABLE"
    assert applicability["out_of_domain_zero_coercion_forbidden"] is True


def test_p6_profile_keeps_training_projection_outside_operational_tactical_use() -> None:
    profile = _profile()
    safety = profile["safety_boundary"]
    activation = profile["activation_rule"]
    assert isinstance(safety, dict)
    assert isinstance(activation, dict)
    assert safety["advisory_projection_only"] is True
    assert safety["operational_or_tactical_optimization_forbidden"] is True
    assert safety["weapon_or_targeting_recommendation_forbidden"] is True
    assert safety["mission_command_generation_forbidden"] is True
    assert safety["p1_p5_fact_mutation_forbidden"] is True
    assert activation["profile_adoption_does_not_admit_p6"] is True
