from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tpaa_ingest import (
    M2MissionSystemError,
    load_m2_measurement_alignment,
    load_m2_mission_system,
)
from tpaa_world import (
    M2RadarSensorWorldError,
    build_m2_radar_sensor_world,
    project_m2_radar_sensor_world,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
FIXTURES = ROOT / "tests" / "fixtures" / "m2"
MISSION = FIXTURES / "MSI_M2_RADAR_V1"
NON_RADAR = FIXTURES / "MSI_M2_IRST_NEGATIVE_V1"
ALIGNMENT = FIXTURES / "MA_M2_NOMINAL_V1"
INSUFFICIENT = FIXTURES / "MA_M2_INSUFFICIENT_V1"
RELEASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2"


def _project(release_id: str = RELEASE_ID):
    return project_m2_radar_sensor_world(
        MISSION,
        ALIGNMENT,
        authority_root=AUTHORITY,
        release_id=release_id,
    )


def test_radar_sensor_world_is_replay_stable_and_preserves_subject_identity() -> None:
    first = _project()
    second = _project()

    assert first == second
    assert first.manifest.world_kind == "MACHINE"
    assert first.manifest.world_version == "M2_RADAR_SENSOR_WORLD_V1"
    assert first.manifest.status == "READY"
    assert first.subject_type == "MISSION_SYSTEM_INSTANCE"
    assert first.applicability_mode == "SYSTEM_TYPE_EXACT"
    assert first.allowed_system_types == ("RADAR",)
    assert first.mission_system.instance.system_type == "RADAR"
    assert first.mission_system.sns_applicable is True
    assert first.mission_system_instance_id == (
        first.mission_system.instance.mission_system_instance_id
    )
    assert first.mission_system_instance_id == (
        first.measurement_alignment.mission_system_instance_id
    )
    assert first.manifest.aircraft_id == first.mission_system.instance.aircraft_id
    assert first.manifest.subject_id is None
    assert first.manifest.logical_content_hash == first.manifest.artifact_sha256
    assert first.manifest.coverage == first.measurement_alignment.coverage
    assert len(first.logical_hash) == 64
    assert first.shadow_schema_created is False
    assert first.metric_logic_executed is False
    assert first.stage_projection_executed is False
    assert first.persistence_executed is False
    assert first.observation_projection_executed is False
    assert first.release_publication_executed is False


def test_radar_sensor_world_preserves_governed_measurement_alignment() -> None:
    world = _project()
    mission = load_m2_mission_system(MISSION)
    alignment = load_m2_measurement_alignment(ALIGNMENT)

    assert world.mission_system == mission
    assert world.measurement_alignment == alignment
    assert alignment.mission_system_logical_hash == mission.logical_hash
    assert world.manifest.start_session_time_us == min(
        min(row.measurement_time_us, row.reference_time_us)
        for row in alignment.rows
    )
    assert world.manifest.end_session_time_us == max(
        max(row.measurement_time_us, row.reference_time_us)
        for row in alignment.rows
    )


def test_release_changes_world_identity_not_logical_content() -> None:
    first = _project()
    second = _project("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb3")

    assert first.logical_hash == second.logical_hash
    assert first.manifest.logical_content_hash == second.manifest.logical_content_hash
    assert first.manifest.world_product_id != second.manifest.world_product_id
    assert first.manifest.request_hash != second.manifest.request_hash


def test_insufficient_alignment_maps_to_partial_without_dropping_subject() -> None:
    world = project_m2_radar_sensor_world(
        MISSION,
        INSUFFICIENT,
        authority_root=AUTHORITY,
        release_id=RELEASE_ID,
    )

    assert world.measurement_alignment.status == "INSUFFICIENT"
    assert world.manifest.status == "PARTIAL"
    assert world.manifest.reason_codes
    assert world.mission_system_instance_id == (
        world.measurement_alignment.mission_system_instance_id
    )


def test_non_radar_mission_system_fails_closed_before_world_projection() -> None:
    with pytest.raises(M2MissionSystemError) as caught:
        project_m2_radar_sensor_world(
            NON_RADAR,
            ALIGNMENT,
            authority_root=AUTHORITY,
            release_id=RELEASE_ID,
        )

    assert caught.value.code == "M2_MISSION_SYSTEM_NOT_APPLICABLE"


def test_world_fails_closed_on_subject_provenance_drift() -> None:
    mission = load_m2_mission_system(MISSION)
    alignment = replace(
        load_m2_measurement_alignment(ALIGNMENT),
        mission_system_logical_hash="0" * 64,
    )

    with pytest.raises(M2RadarSensorWorldError) as caught:
        build_m2_radar_sensor_world(
            mission,
            alignment,
            authority_root=AUTHORITY,
            release_id=RELEASE_ID,
        )

    assert caught.value.code == "M2_RADAR_WORLD_MISSION_PROVENANCE_DRIFT"
