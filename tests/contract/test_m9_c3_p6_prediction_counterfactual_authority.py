from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
CANONICAL = BASELINE / "canonical"
AUTHORITY = CANONICAL / "P6_PREDICTION_COUNTERFACTUAL_AUTHORITY.json"
ROLE_PROFILE = CANONICAL / "P6_ROLE_PRIVACY_RELEASE_PROFILE.json"
DTO = CANONICAL / "CROSS_LAYER_DTO_CONTRACTS.json"
GENERATED_DTO = ROOT / "src" / "tpaa_generated" / "dto.py"
VALIDATOR_PATH = (
    ROOT
    / "tools"
    / "baseline"
    / "validate_p6_prediction_counterfactual_authority.py"
)

EXPECTED_AUTHORITY_SHA256 = "a138c97e6c9891f767ee25de8841e2bc9ca899ddf6d09b98b9e4bae73d9be79e"
EXPECTED_ROLE_PROFILE_SHA256 = "d5eff80dbfa912955ae7b09bc3e4a2868650466560cb1a5b1f558434e8076713"

SPEC = importlib.util.spec_from_file_location("m9_c3_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_m9_c3_authority_and_release_profile_are_controlled_and_loadable() -> None:
    assert hashlib.sha256(AUTHORITY.read_bytes()).hexdigest() == EXPECTED_AUTHORITY_SHA256
    assert (
        hashlib.sha256(ROLE_PROFILE.read_bytes()).hexdigest()
        == EXPECTED_ROLE_PROFILE_SHA256
    )
    loader = CanonicalArtifactLoader(BASELINE)
    authority = loader.load(
        "P6_PREDICTION_COUNTERFACTUAL_AUTHORITY",
        expectation=ArtifactExpectation(
            version="1.0.0",
            schema_version="1.6.0",
            required_top_level_keys=(
                "input_snapshot_contract",
                "model_authority_contract",
                "forecast_contract",
                "counterfactual_contract",
                "recommendation_contract",
                "interoperability_contract",
                "admission_guard",
                "dto_contracts",
            ),
        ),
    )
    profile = loader.load(
        "P6_ROLE_PRIVACY_RELEASE_PROFILE",
        expectation=ArtifactExpectation(
            version="1.0.0",
            schema_version="1.6.0",
            required_top_level_keys=(
                "identity_privacy_contract",
                "role_matrix",
                "projection_contract",
                "write_authorization_contract",
                "release_approval_contract",
                "forbidden_fallbacks",
            ),
        ),
    )
    assert authority.sha256 == EXPECTED_AUTHORITY_SHA256
    assert profile.sha256 == EXPECTED_ROLE_PROFILE_SHA256


def test_m9_c3_validator_passes_without_claiming_completion() -> None:
    result = VALIDATOR.verify()
    assert result["status"] == "PASS"
    assert result["failed_checks"] == []
    assert result["task_complete"] is False
    assert all(result["checks"].values())


def test_m9_c3_has_no_implementation_default_model_or_threshold() -> None:
    authority = _json(AUTHORITY)
    model = authority["model_authority_contract"]
    assert isinstance(model, dict)
    assert model["default_model_profile"] is None
    assert model["implementation_default_model_family_forbidden"] is True
    assert model["implementation_default_threshold_forbidden"] is True


def test_m9_c3_counterfactual_and_recommendation_boundaries_fail_closed() -> None:
    authority = _json(AUTHORITY)
    counterfactual = authority["counterfactual_contract"]
    recommendation = authority["recommendation_contract"]
    assert isinstance(counterfactual, dict)
    assert isinstance(recommendation, dict)
    assert (
        counterfactual["default_causal_claim_level"]
        == "SCENARIO_PROJECTION_NON_CAUSAL"
    )
    assert counterfactual["association_to_causal_upgrade_forbidden"] is True
    assert recommendation["advisory_only"] is True
    assert recommendation["automatic_command_forbidden"] is True


def test_m9_c3_role_profile_separates_release_and_business_approval() -> None:
    profile = _json(ROLE_PROFILE)
    rows = profile["role_matrix"]
    assert isinstance(rows, list)
    roles = {row["role"]: row for row in rows}
    assert roles["MODEL_REVIEWER"]["model_release"] is True
    assert roles["MODEL_REVIEWER"]["recommendation_approval"] is False
    assert roles["INSTRUCTOR_EVALUATOR"]["model_release"] is False
    assert roles["INSTRUCTOR_EVALUATOR"]["recommendation_approval"] is True
    assert roles["ADMIN_AUDITOR"]["model_release"] is False


def test_m9_c3_central_and_generated_dto_family_is_exact() -> None:
    dto = _json(DTO)
    contracts = dto["contracts"]
    assert isinstance(contracts, dict)
    names = (
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
    source = GENERATED_DTO.read_text(encoding="utf-8")
    for name in names:
        assert name in contracts
        assert f"class {name}(TypedDict, total=False):" in source

    admission = contracts["P6AdmissionStateDTO"]
    assert isinstance(admission, dict)
    fields = admission["fields"]
    assert isinstance(fields, list)
    assert [row["field"] for row in fields] == [
        "source_revision",
        "event_name",
        "git_ref",
        "protected_main",
        "m9_exit_decision",
        "run_conclusion",
        "required_jobs_success",
        "required_jobs_total",
        "p6_admitted",
    ]


def test_m9_c3_adoption_does_not_admit_p6() -> None:
    authority = _json(AUTHORITY)
    activation = authority["activation_rule"]
    scope = authority["scope"]
    assert isinstance(activation, dict)
    assert isinstance(scope, dict)
    assert activation["authority_adoption_does_not_admit_p6"] is True
    assert scope["p6_authority_frozen_not_admitted"] is True
