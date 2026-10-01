from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
PROFILE = BASELINE / "canonical" / "P2_LINEAR_REFERENCE_ADJUSTMENT_PROFILE.json"
DTO = BASELINE / "canonical" / "CROSS_LAYER_DTO_CONTRACTS.json"
AUTHORITY = BASELINE / "canonical" / "P2_ATTRIBUTION_NORMALIZATION_AUTHORITY.json"
GENERATED_DTO = ROOT / "src" / "tpaa_generated" / "dto.py"
VALIDATOR_PATH = ROOT / "tools" / "baseline" / "validate_p2_dto_execution_profile.py"

SPEC = importlib.util.spec_from_file_location("p2_dto_profile_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_m6_c3_p2_dto_profile_validator_passes() -> None:
    result = VALIDATOR.verify()
    assert result["status"] == "PASS"
    assert result["dto_sha256"] == "9d94f75031afcbfe2391bed1245c3f8d95f124a6549a8f116aa1efb879ae45b4"
    assert result["current_dto_sha256"] == "28f7209e40709fb4eb53ceffdfee3542e867f060c4e63605cc1ad149a8e3819a"
    assert result["p2_dto_subset_sha256"] == "d79d97eb41354ad61654372310bb1a92b37914a858213f5dfc4a1287e14c6706"
    assert result["failed_checks"] == []
    assert result["task_complete"] is False
    assert all(result["checks"].values())


def test_m6_c3_execution_profile_is_controlled_and_loadable() -> None:
    artifact = CanonicalArtifactLoader(BASELINE).load(
        "P2_LINEAR_REFERENCE_ADJUSTMENT_PROFILE",
        expectation=ArtifactExpectation(
            version="1.0.0",
            schema_version="1.6.0",
            required_top_level_keys=(
                "runtime_binding",
                "eligibility_contract",
                "arithmetic_contract",
                "solver_contract",
                "uncertainty_contract",
                "identity_contract",
                "contract_hashes",
            ),
        ),
    )
    assert artifact.sha256 == (
        "202e255bd09349407e0e7cc4d77d8b848df99d84dc00e50e46871eb4f82f0d68"
    )


def test_m6_c3_central_dto_fields_equal_p2_authority() -> None:
    dto = _json(DTO)
    authority = _json(AUTHORITY)
    contracts = dto["contracts"]
    authority_contracts = authority["dto_contracts"]
    assert isinstance(contracts, dict)
    assert isinstance(authority_contracts, dict)
    names = (
        "P2EligibleObservationDTO",
        "FactorFeatureSetDTO",
        "AttributionRunDTO",
        "AdjustedCapabilityEstimateDTO",
        "P2AdmissionStateDTO",
    )
    for name in names:
        central = contracts[name]
        frozen = authority_contracts[name]
        assert isinstance(central, dict)
        assert isinstance(frozen, dict)
        fields = central["fields"]
        frozen_fields = frozen["fields"]
        assert isinstance(fields, list)
        assert isinstance(frozen_fields, list)
        assert [field["field"] for field in fields] == frozen_fields


def test_m6_c3_generated_dto_preserves_nullable_adjusted_numbers() -> None:
    source = GENERATED_DTO.read_text(encoding="utf-8")
    assert "class AdjustedCapabilityEstimateDTO(TypedDict, total=False):" in source
    assert "adjusted_value: Required[int | float | None]" in source
    assert "residual: Required[int | float | None]" in source
    assert "class P2EligibleObservationDTO(TypedDict, total=False):" in source
    assert "metric_semantic_version: Required[int]" in source


def test_m6_c3_profile_uuid_namespaces_are_derivable() -> None:
    profile = _json(PROFILE)
    identity = profile["identity_contract"]
    assert isinstance(identity, dict)
    for name in ("factor_feature_set", "attribution_run", "adjusted_estimate"):
        section = identity[name]
        assert isinstance(section, dict)
        assert str(uuid5(NAMESPACE_URL, section["urn"])) == section["namespace_uuid"]


def test_m6_c3_profile_is_not_p2_admission() -> None:
    profile = _json(PROFILE)
    activation = profile["activation_rule"]
    scope = profile["scope"]
    assert isinstance(activation, dict)
    assert isinstance(scope, dict)
    assert activation["profile_adoption_does_not_admit_p2"] is True
    assert activation["p3_p6_active"] is False
    assert scope["db_schema_change"] is False
    assert scope["db_schema_version"] == "1.6.0"
