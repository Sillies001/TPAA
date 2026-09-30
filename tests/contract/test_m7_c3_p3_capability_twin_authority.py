from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
AUTHORITY = BASELINE / "canonical" / "P3_CAPABILITY_TWIN_AUTHORITY.json"
PROFILE = BASELINE / "canonical" / "P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL_PROFILE.json"
VALIDATOR_PATH = ROOT / "tools" / "baseline" / "validate_p3_capability_twin_authority.py"

EXPECTED_AUTHORITY_SHA256 = "76726fc533cde7b0a183a1575cb50276e166081cc37ebe4857ed3324ab913e3b"
EXPECTED_PROFILE_SHA256 = "d66aa780d1c2e31ec664d173a0cdbc355f98c9ff3f751a6949e84f74cdf93876"

SPEC = importlib.util.spec_from_file_location("p3_c3_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def _payload(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_m7_c3_authority_and_profile_are_controlled_and_loadable() -> None:
    assert hashlib.sha256(AUTHORITY.read_bytes()).hexdigest() == EXPECTED_AUTHORITY_SHA256
    assert hashlib.sha256(PROFILE.read_bytes()).hexdigest() == EXPECTED_PROFILE_SHA256
    loader = CanonicalArtifactLoader(BASELINE)
    authority = loader.load(
        "P3_CAPABILITY_TWIN_AUTHORITY",
        expectation=ArtifactExpectation(
            version="1.0.0",
            schema_version="1.6.0",
            required_top_level_keys=(
                "p2_eligibility_contract",
                "lifecycle_segment_contract",
                "validation_snapshot_contract",
                "managed_object_contract",
                "claim_contract",
                "admission_guard",
                "dto_contracts",
            ),
        ),
    )
    profile = loader.load(
        "P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL_PROFILE",
        expectation=ArtifactExpectation(
            version="1.0.0",
            schema_version="1.6.0",
            required_top_level_keys=(
                "source_bindings",
                "segmentation_contract",
                "longitudinal_core",
                "validation_contract",
                "validity_domain_contract",
            ),
        ),
    )
    assert authority.sha256 == EXPECTED_AUTHORITY_SHA256
    assert profile.sha256 == EXPECTED_PROFILE_SHA256


def test_m7_c3_validator_passes() -> None:
    result = VALIDATOR.verify()
    assert result["status"] == "PASS"
    assert result["failed_checks"] == []
    assert result["task_complete"] is False
    assert all(result["checks"].values())


def test_m7_c3_reuses_m4_numeric_semantics_but_not_p1_product_semantics() -> None:
    profile = _payload(PROFILE)
    core = profile["longitudinal_core"]
    assert core["x_axis_semantics"] == "SESSION_ORDER"
    assert core["slope"]["estimator"] == "ORDINARY_LEAST_SQUARES"
    assert core["slope"]["min_valid_points"] == 3
    assert core["slope"]["max_valid_points"] == 5
    assert core["stability"]["statistic"] == "UNSCALED_MEDIAN_ABSOLUTE_DEVIATION"
    assert core["current_value_rule"] == "LAST_ELIGIBLE_P2_ESTIMATE_BY_SESSION_ORDER"
    assert profile["scope"]["numeric_p2_identifiable_only"] is True


def test_m7_c3_configuration_key_and_lifecycle_boundary_are_explicit() -> None:
    authority = _payload(AUTHORITY)
    eligibility = authority["p2_eligibility_contract"]
    segment = authority["lifecycle_segment_contract"]
    assert eligibility["configuration_key_rule"].startswith("AIRCRAFT_CONFIG_SHA256:")
    assert "configuration_key" in segment["profile_v1_segment_dimensions"]
    assert "configuration_snapshot_id" not in segment["profile_v1_segment_dimensions"]
    assert segment["configuration_snapshot_ids_preserved_as_provenance"] is True
    assert (
        segment["lifecycle_event_inside_selected_session_interval_forces_new_segment"]
        is True
    )


def test_m7_c3_profile_v1_claim_and_scope_are_conservative() -> None:
    authority = _payload(AUTHORITY)
    profile = _payload(PROFILE)
    assert profile["scope"]["subject_type"] == "AIRCRAFT"
    assert profile["scope"]["aircraft_model_level_supported"] is False
    assert profile["scope"]["stronger_intrinsic_claim_supported"] is False
    assert authority["claim_contract"]["profile_v1_allowed_claim_levels"] == [
        "REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE"
    ]
    assert authority["scope"]["p4_p6_active"] is False


def test_m7_c3_validation_has_no_free_accuracy_multiplier() -> None:
    profile = _payload(PROFILE)
    validation = profile["validation_contract"]
    assert validation["minimum_total_eligible_points"] == 4
    assert validation["training_prefix_min_points"] == 3
    assert validation["training_prefix_max_points"] == 5
    assert validation["acceptance"] == (
        "abs(predicted-heldout_adjusted_value) <= "
        "training_prefix_MAD + heldout_input_half_width"
    )
    assert validation["implementation_selected_tolerance_or_multiplier_forbidden"] is True
