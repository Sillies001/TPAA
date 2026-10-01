from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
AUTHORITY = BASELINE / "canonical" / "P4_P5_TRAINING_ASSESSMENT_AUTHORITY.json"
ROLE_PROFILE = BASELINE / "canonical" / "P4_P5_ROLE_PRIVACY_PROFILE.json"
VALIDATOR_PATH = ROOT / "tools" / "baseline" / "validate_p4_p5_training_assessment_authority.py"

EXPECTED_AUTHORITY_SHA256 = "749360544e3e403e3a81b4992797d5186c93d1f06a92e96f1352c4ab4ed4cb77"
EXPECTED_ROLE_PROFILE_SHA256 = "99a526cead816010373cdd81cd889d33fa359b5d0b74d87743e51d0f649f1113"

SPEC = importlib.util.spec_from_file_location("m8_c3_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def _payload(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_m8_c3_authority_and_role_profile_are_controlled_and_loadable() -> None:
    assert hashlib.sha256(AUTHORITY.read_bytes()).hexdigest() == EXPECTED_AUTHORITY_SHA256
    assert hashlib.sha256(ROLE_PROFILE.read_bytes()).hexdigest() == EXPECTED_ROLE_PROFILE_SHA256
    loader = CanonicalArtifactLoader(BASELINE)
    authority = loader.load(
        "P4_P5_TRAINING_ASSESSMENT_AUTHORITY",
        expectation=ArtifactExpectation(
            version="1.0.0",
            schema_version="1.6.0",
            required_top_level_keys=(
                "subject_context_contract",
                "composition_contract",
                "evidence_boundary_contract",
                "approval_workflow_contract",
                "role_privacy_contract",
                "aggregation_contract",
                "admission_guard",
                "dto_contracts",
            ),
        ),
    )
    role_profile = loader.load(
        "P4_P5_ROLE_PRIVACY_PROFILE",
        expectation=ArtifactExpectation(
            version="1.0.0",
            schema_version="1.6.0",
            required_top_level_keys=(
                "context_binding_contract",
                "pseudonymization_contract",
                "role_matrix",
                "projection_contract",
                "write_authorization_contract",
                "forbidden_fallbacks",
            ),
        ),
    )
    assert authority.sha256 == EXPECTED_AUTHORITY_SHA256
    assert role_profile.sha256 == EXPECTED_ROLE_PROFILE_SHA256


def test_m8_c3_validator_passes_without_claiming_completion() -> None:
    result = VALIDATOR.verify()
    assert result["status"] == "PASS"
    assert result["failed_checks"] == []
    assert result["task_complete"] is False
    assert all(result["checks"].values())


def test_m8_c3_has_no_default_scoring_or_aggregation_formula() -> None:
    authority = _payload(AUTHORITY)
    aggregation = authority["aggregation_contract"]
    assert aggregation["default_aggregation_profile"] is None
    assert aggregation["implementation_default_formula_forbidden"] is True
    assert aggregation["implementation_default_weight_forbidden"] is True
    assert aggregation["implementation_default_threshold_forbidden"] is True
    assert aggregation["no_profile_behavior"] == "EVIDENCE_ONLY_SCORE_AND_GRADE_NULL"


def test_m8_c3_machine_human_and_unavailable_semantics_are_distinct() -> None:
    authority = _payload(AUTHORITY)
    assert authority["evidence_boundary_contract"]["machine_and_human_evidence_distinct"] is True
    assert authority["status_contract"]["evidence_availability_states"] == [
        "AVAILABLE",
        "UNAVAILABLE",
        "OUT_OF_DOMAIN",
        "NOT_IDENTIFIABLE",
    ]
    assert authority["status_contract"]["unavailable_numeric_zero_substitution_forbidden"] is True


def test_m8_c3_role_profile_is_default_deny_and_least_privilege() -> None:
    role_profile = _payload(ROLE_PROFILE)
    roles = {row["role"]: row for row in role_profile["role_matrix"]}
    assert role_profile["scope"]["default_deny"] is True
    assert roles["ANALYST"]["direct_actor_id"] is False
    assert roles["TEAM_LEAD"]["direct_actor_id"] is False
    assert roles["ADMIN_AUDITOR"]["approval_write"] is False
    assert roles["INSTRUCTOR_EVALUATOR"]["approval_write"] is True
    assert role_profile["forbidden_fallbacks"]["admin_implies_evaluator"] is False


def test_m8_c3_adoption_does_not_admit_p4_p5_or_p6() -> None:
    authority = _payload(AUTHORITY)
    assert authority["activation_rule"]["authority_adoption_does_not_admit_p4_or_p5"] is True
    assert authority["scope"]["p4_p5_authority_frozen_not_admitted"] is True
    assert authority["scope"]["p6_active"] is False
