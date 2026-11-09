from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tpaa_canonical.loader import (
    F1_CANDIDATE_CORE_BASELINE,
    G12_LOCAL_CORE_BASELINE,
    trusted_loader_for_baseline,
)

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_ROOT = ROOT / "baseline" / F1_CANDIDATE_CORE_BASELINE
PARENT_ROOT = ROOT / "baseline" / G12_LOCAL_CORE_BASELINE
METRIC_IDS = ("KILL_RATIO", "EXCHANGE_RATIO", "MISSION_COMPLETION_RATE")


def _definition_hash(definition: dict[str, object]) -> str:
    payload = dict(definition)
    payload.pop("definition_sha256", None)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def test_candidate_baseline_loads_all_77_locked_artifacts() -> None:
    loader = trusted_loader_for_baseline(CANDIDATE_ROOT)
    artifacts = loader.load_all()
    assert len(artifacts) == 77
    assert loader.baseline_metadata["core"] == F1_CANDIDATE_CORE_BASELINE
    assert loader.baseline_metadata["db_schema"] == "1.11.0"


def test_three_task_metric_definitions_are_self_hashed_candidates() -> None:
    loader = trusted_loader_for_baseline(CANDIDATE_ROOT)
    for metric_id in METRIC_IDS:
        definition = dict(loader.load(metric_id).payload)
        assert definition["semantic_id"] == metric_id
        assert definition["definition_version"] == "1.0.0"
        assert definition["admission_status"] == "CANDIDATE_TEST_ONLY"
        assert definition["definition_sha256"] == _definition_hash(definition)


def test_kill_ratio_uses_engagement_denominator_not_launch_count() -> None:
    loader = trusted_loader_for_baseline(CANDIDATE_ROOT)
    definition = dict(loader.load("KILL_RATIO").payload)
    assert definition["numerator_rule"]["count"] == "unique loss_id"
    assert definition["denominator_rule"]["source"] == "assessment.engagement_episode"
    assert definition["denominator_rule"]["count"] == "unique engagement_id"
    assert definition["deduplication_rule"]["launch_count_as_denominator"] == "FORBIDDEN"


def test_exchange_ratio_zero_denominator_is_na() -> None:
    loader = trusted_loader_for_baseline(CANDIDATE_ROOT)
    definition = dict(loader.load("EXCHANGE_RATIO").payload)
    assert definition["zero_denominator_rule"]["status"] == "N_A"
    assert definition["zero_denominator_rule"]["value"] is None
    assert definition["zero_denominator_rule"]["reason_code"] == (
        "ZERO_EVALUATED_SIDE_CONFIRMED_LOSS"
    )


def test_mission_completion_uses_frozen_required_objective_plan() -> None:
    loader = trusted_loader_for_baseline(CANDIDATE_ROOT)
    definition = dict(loader.load("MISSION_COMPLETION_RATE").payload)
    assert definition["denominator_rule"]["source"] == "assessment.mission_objective_plan"
    assert "required=true" in definition["denominator_rule"]["where"]
    assert definition["deduplication_rule"]["optional_objectives"] == "EXCLUDE"
    assert definition["deduplication_rule"]["weighting"] == "NOT_USED_IN_VERSION_1_0_0"


def test_cross_batch_comparability_forbids_simple_ratio_average() -> None:
    loader = trusted_loader_for_baseline(CANDIDATE_ROOT)
    authority = dict(loader.load("TASK_METRIC_COMPARABILITY_AUTHORITY").payload)
    assert authority["aggregate_rule"] == "SUM_NUMERATOR_AND_DENOMINATOR_THEN_DIVIDE"
    assert authority["simple_average"] == "FORBIDDEN"


def test_world_relation_authority_keeps_passive_semantics_distinct() -> None:
    loader = trusted_loader_for_baseline(CANDIDATE_ROOT)
    authority = dict(loader.load("WORLD_RELATION_TYPE_AUTHORITY").payload)
    types = {item["relation_type"] for item in authority["relation_types"]}
    assert "MANEUVER_SEGMENT" in types
    assert "BASIC_FLIGHT_DEVIATION" in types
    assert "ATTACK_SUPPORT_RELATION" in types
    assert "WEAPON_EVENT_SUPERSESSION" in types
    assert "COOPERATIVE_PASSIVE_LOCALIZATION" in authority["semantic_distinctions"]
    assert "PASSIVE_DETECTION_DATA_LINK_SHARE" in authority["semantic_distinctions"]


def test_task_metric_dtos_are_separate_from_p1_catalog() -> None:
    candidate = trusted_loader_for_baseline(CANDIDATE_ROOT)
    parent = trusted_loader_for_baseline(PARENT_ROOT)
    assert candidate.load("P1_METRIC_CATALOG").sha256 == parent.load("P1_METRIC_CATALOG").sha256
    contracts = dict(candidate.load("CROSS_LAYER_DTO_CONTRACTS").payload)["contracts"]
    assert "TaskMetricDefinitionDTO" in contracts
    assert "TaskMetricResultDTO" in contracts
    assert "TaskMetricCompareRequestDTO" in contracts
    assert "TaskMetricEvidenceDTO" in contracts
    transport = dict(candidate.load("CROSS_LAYER_DTO_CONTRACTS").payload)["transport_rules"]
    assert transport["task_metric"]["decimal"] == "decimal-string; never IEEE-754 number"


def test_algorithm_vectors_cover_pending_zero_dedup_and_aggregation() -> None:
    loader = trusted_loader_for_baseline(CANDIDATE_ROOT)
    vectors = dict(loader.load("TASK_METRIC_ALGORITHM_TEST_VECTORS").payload)["vectors"]
    ids = {item["id"] for item in vectors}
    assert len(vectors) >= 10
    assert "KILL_RATIO_DEDUP_MULTIPLE_WE" in ids
    assert "KILL_RATIO_ZERO_DENOMINATOR" in ids
    assert "KILL_RATIO_PENDING_J" in ids
    assert "EXCHANGE_RATIO_ZERO_DENOMINATOR" in ids
    assert "MISSION_COMPLETION_PENDING" in ids
    assert "CROSS_BATCH_WEIGHTED_AGGREGATION" in ids


def test_no_candidate_metric_is_admitted_by_automation() -> None:
    loader = trusted_loader_for_baseline(CANDIDATE_ROOT)
    authority = dict(loader.load("GUI_TASK_METRIC_ADMISSION_AUTHORITY").payload)
    assert authority["approval_status"] == "CANDIDATE_TEST_ONLY"
    assert all(
        item["admission_status"] == "CANDIDATE_TEST_ONLY"
        for item in authority["candidates"]
    )
    assert authority["rules"]["automated_test_pass_is_business_approval"] is False
