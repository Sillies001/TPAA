from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tpaa_world import (
    M2StageWorldLineageError,
    build_m2_stage_world_lineage,
    project_m2_stage_world_lineage,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
M1_FIXTURES = ROOT / "tests" / "fixtures" / "m1"
M2_FIXTURES = ROOT / "tests" / "fixtures" / "m2"
STAGE = M1_FIXTURES / "BF_M1_NOMINAL_V1"
REFERENCE = M2_FIXTURES / "RT_M2_NOMINAL_V1"
TIME = M2_FIXTURES / "TA_M2_NOMINAL_V1"
MISSION = M2_FIXTURES / "MSI_M2_RADAR_V1"
ALIGNMENT = M2_FIXTURES / "MA_M2_NOMINAL_V1"
INSUFFICIENT = M2_FIXTURES / "MA_M2_INSUFFICIENT_V1"
RELEASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3"


def _project(alignment: Path = ALIGNMENT, release_id: str = RELEASE_ID):
    return project_m2_stage_world_lineage(
        STAGE,
        REFERENCE,
        TIME,
        MISSION,
        alignment,
        authority_root=AUTHORITY,
        release_id=release_id,
    )


def test_stage_world_lineage_is_complete_replay_stable_and_authority_preserving() -> None:
    first = _project()
    second = _project()

    assert first == second
    assert first.status == "READY"
    assert first.coverage == 1.0
    assert first.confidence == 1.0
    assert first.stage_profile_id == "BASIC_FLIGHT_V1"
    assert [stage.stage_type for stage in first.stage_projection.stages] == [
        "SETUP_ENTRY",
        "EXECUTION",
        "STABILIZATION_RECOVERY",
        "COMPLETION",
    ]
    assert all(stage.stage_status == "VALID" for stage in first.stage_projection.stages)
    assert all(stage.coverage == 1.0 for stage in first.stage_projection.stages)
    assert all(stage.confidence == 1.0 for stage in first.stage_projection.stages)
    assert [summary.world_role for summary in first.summaries] == [
        "REFERENCE_TRUTH_WORLD",
        "TIME_ALIGNMENT_WORLD",
        "RADAR_SENSOR_WORLD",
    ]
    assert all(summary.lineage_coverage == 1.0 for summary in first.summaries)
    assert all(summary.lineage_confidence == 1.0 for summary in first.summaries)
    assert first.stage_authority_rewritten is False
    assert first.world_manifest_rewritten is False
    assert first.persistence_executed is False
    assert first.metric_logic_executed is False
    assert first.observation_projection_executed is False
    assert first.release_publication_executed is False


def test_lineage_keeps_world_manifests_unscoped_when_world_spans_stages() -> None:
    product = _project()

    manifests = (
        product.reference_time_world.reference_manifest,
        product.reference_time_world.time_manifest,
        product.radar_sensor_world.manifest,
    )
    assert all(manifest.episode_id is None for manifest in manifests)
    assert all(manifest.stage_id is None for manifest in manifests)
    assert any(len(summary.stage_ids) > 1 for summary in product.summaries)
    assert all(record.episode_id == product.episode_id for record in product.records)


def test_release_changes_world_identity_not_logical_lineage() -> None:
    first = _project()
    second = _project(
        release_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb4",
    )

    assert first.logical_hash == second.logical_hash
    assert [summary.logical_hash for summary in first.summaries] == [
        summary.logical_hash for summary in second.summaries
    ]
    assert [summary.world_product_id for summary in first.summaries] != [
        summary.world_product_id for summary in second.summaries
    ]


def test_partial_radar_world_propagates_status_without_invalidating_stage_lineage() -> None:
    product = _project(INSUFFICIENT)
    summaries = {summary.world_role: summary for summary in product.summaries}

    assert product.status == "PARTIAL"
    assert product.coverage == 1.0
    assert summaries["RADAR_SENSOR_WORLD"].world_status == "PARTIAL"
    assert summaries["RADAR_SENSOR_WORLD"].lineage_coverage == 1.0
    assert all(stage.stage_status == "VALID" for stage in product.stage_projection.stages)


def test_session_drift_fails_closed() -> None:
    product = _project()
    reference = replace(
        product.reference_time_world.reference_manifest,
        session_id="99999999-9999-4999-8999-999999999999",
    )
    reference_world = replace(
        product.reference_time_world,
        reference_manifest=reference,
    )

    with pytest.raises(M2StageWorldLineageError) as caught:
        build_m2_stage_world_lineage(
            product.stage_projection,
            stage_session_id=product.session_id,
            reference_time_world=reference_world,
            radar_sensor_world=product.radar_sensor_world,
            authority_root=AUTHORITY,
        )

    assert caught.value.code == "M2_STAGE_WORLD_SESSION_DRIFT"
