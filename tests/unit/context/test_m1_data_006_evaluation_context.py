from __future__ import annotations

from pathlib import Path

from tpaa_context import resolve_all_evaluation_contexts, resolve_evaluation_context

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m1"
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"


def test_nominal_context_binds_basic_rule_metric_and_stage_profiles() -> None:
    resolved = resolve_evaluation_context(
        FIXTURE_ROOT / "BF_M1_NOMINAL_V1",
        authority_root=AUTHORITY_ROOT,
    )

    assert resolved.basic_profile_id == "M1-BASIC-CONTEXT-1.0.0"
    assert resolved.rule_set_version == "CB-1.4.0"
    assert resolved.metric_profile_version == "M1_BASIC_AIR_PROFILE_V1"
    assert resolved.stage_profile_id == "BASIC_FLIGHT_V1"
    assert resolved.stage_profile_authority == "STAGE_REGISTRY:1.1.0"
    assert tuple(ref.binding_role for ref in resolved.artifact_refs) == (
        "METRIC_PROFILE",
        "RULE_SET",
    )
    assert resolved.stage_profile_persistence_binding_created is False
    assert resolved.current_latest_fallback_used is False
    assert resolved.database_persistence_executed is False
    assert resolved.stage_projection_executed is False
    assert resolved.metric_logic_executed is False


def test_replay_context_uses_frozen_refs_and_ignores_simulated_current_refs() -> None:
    resolved = resolve_evaluation_context(
        FIXTURE_ROOT / "BF_M1_REPLAY_V1",
        authority_root=AUTHORITY_ROOT,
    )

    assert resolved.frozen_refs_used is True
    assert resolved.current_refs_differ_from_frozen is True
    assert resolved.current_latest_fallback_used is False
    assert resolved.rule_set_version == "CB-1.4.0"
    assert resolved.metric_profile_version == "M1_BASIC_AIR_PROFILE_V1"
    assert resolved.stage_profile_id == "BASIC_FLIGHT_V1"


def test_all_governed_contexts_are_replay_stable() -> None:
    first = resolve_all_evaluation_contexts(
        FIXTURE_ROOT,
        authority_root=AUTHORITY_ROOT,
    )
    second = resolve_all_evaluation_contexts(
        FIXTURE_ROOT,
        authority_root=AUTHORITY_ROOT,
    )

    assert first == second
    assert len(first) == 8
    assert len({item.logical_hash for item in first}) == 8
    assert len({item.context_file_sha256 for item in first}) == 8
    assert sum(item.frozen_refs_used for item in first) == 1
    assert sum(item.current_refs_differ_from_frozen for item in first) == 1
