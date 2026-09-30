from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
AUTHORITY = BASELINE / "canonical" / "P2_ATTRIBUTION_NORMALIZATION_AUTHORITY.json"
VALIDATOR_PATH = ROOT / "tools" / "baseline" / "validate_p2_attribution_authority.py"
CORE = BASELINE / "canonical" / "CORE_LOGICAL_MODEL.json"
EXPECTED_SHA256 = "1bfc6c9eb8e2142249c327af5698bc6a8925f983fd8363b1d2bd835966eea5fa"

SPEC = importlib.util.spec_from_file_location("p2_c3_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def _payload() -> dict[str, object]:
    value = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_m6_c3_authority_is_controlled_and_loadable() -> None:
    raw = AUTHORITY.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA256
    artifact = CanonicalArtifactLoader(BASELINE).load(
        "P2_ATTRIBUTION_NORMALIZATION_AUTHORITY",
        expectation=ArtifactExpectation(
            version="1.0.0",
            schema_version="1.6.0",
            required_top_level_keys=(
                "p1_eligibility_contract",
                "feature_spec_contract",
                "reference_condition_contract",
                "cohort_specification_contract",
                "attribution_spec_contract",
                "identifiability_contract",
                "uncertainty_contract",
                "factor_effect_contract",
                "knowledge_time_contract",
                "release_replay_contract",
                "admission_guard",
                "dto_contracts",
            ),
        ),
    )
    assert artifact.sha256 == EXPECTED_SHA256


def test_m6_c3_validator_passes() -> None:
    result = VALIDATOR.verify()
    assert result["status"] == "PASS"
    assert result["failed_checks"] == []
    assert result["task_complete"] is False
    assert all(result["checks"].values())


def test_m6_c3_preserves_schema_and_p1_boundary() -> None:
    p = _payload()
    scope = p["scope"]
    assert scope["db_schema_change"] is False
    assert scope["db_schema_version"] == "1.6.0"
    assert scope["shadow_schema_permitted"] is False
    assert scope["p1_observed_layer_immutable"] is True
    assert scope["p2_authority_frozen_not_admitted"] is True
    assert scope["p3_p6_active"] is False


def test_m6_c3_exact_identifiability_and_leakage_semantics() -> None:
    p = _payload()
    ident = p["identifiability_contract"]
    assert ident["statuses"] == ["IDENTIFIABLE", "NOT_IDENTIFIABLE"]
    assert ident["not_identifiable_is_valid_product"] is True
    assert ident["not_identifiable_requires_adjusted_value_null"] is True
    knowledge = p["knowledge_time_contract"]
    assert knowledge["future_information_forbidden"] is True
    assert knowledge["same_episode_leakage_forbidden"] is True
    assert knowledge["historical_current_latest_fallback_forbidden"] is True


def test_m6_c3_uses_existing_1_6_0_carriers() -> None:
    p = _payload()
    assert p["feature_spec_contract"]["carrier_table"] == "registry.context_artifact"
    assert p["reference_condition_contract"]["carrier_table"] == "registry.context_artifact"
    assert p["cohort_specification_contract"]["carrier_table"] == "registry.dataset_snapshot"
    assert p["release_replay_contract"]["p2_release_binding"].startswith(
        "adjusted estimate evidence_set_id"
    )


def test_m6_c3_p2_subtypes_use_existing_core_artifact_kinds() -> None:
    p = _payload()
    core = json.loads(CORE.read_text(encoding="utf-8"))
    table = core["tables"]["registry.context_artifact"]
    artifact_kind = next(
        field for field in table["fields"] if field["name"] == "artifact_kind"
    )
    sql = artifact_kind["sql"]
    for contract in (
        p["feature_spec_contract"],
        p["reference_condition_contract"],
        p["attribution_spec_contract"],
    ):
        assert f"'{contract['artifact_kind']}'" in sql
        assert contract["logical_key_prefix"].startswith("P2_")
        assert contract["artifact_schema_version"].startswith("TPAA_P2_")


def test_m6_c3_lock_lineage_preserves_protected_main_parent() -> None:
    lock = json.loads((BASELINE / "BASELINE_LOCK.json").read_text(encoding="utf-8"))
    assert lock["baseline"]["lock_lineage_sha256"][0] == (
        "be54a16d2f33aca73f0686ffe09414045611fa4ad4c452e0e57ca96e460736d8"
    )
