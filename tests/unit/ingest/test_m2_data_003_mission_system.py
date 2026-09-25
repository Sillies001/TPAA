from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_ingest.m2_mission_system import (
    M2MissionSystemError,
    load_m2_mission_system,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
M2_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "m2"
RADAR = M2_FIXTURES / "MSI_M2_RADAR_V1"
IRST = M2_FIXTURES / "MSI_M2_IRST_NEGATIVE_V1"


def test_m2_data_003_radar_identity_and_applicability_are_exact() -> None:
    projection = load_m2_mission_system(RADAR)

    assert projection.subject_type == "MISSION_SYSTEM_INSTANCE"
    assert projection.metric_family == "P1-SNS-*"
    assert projection.applicability_mode == "SYSTEM_TYPE_EXACT"
    assert projection.allowed_system_types == ("RADAR",)
    assert projection.sns_applicable is True
    assert projection.instance.system_type == "RADAR"
    assert projection.instance.system_code == "RADAR-A"
    assert (
        projection.instance.mission_system_instance_id
        == "77777777-7777-4777-8777-777777777701"
    )
    assert projection.identity.identity_ref == "mission-system-identity:radar-a:v1"
    assert projection.identity.source_entity_key == "RADAR-A-01"
    assert len(projection.logical_hash) == 64


def test_m2_data_003_irst_fixture_fails_closed_for_sns_family() -> None:
    with pytest.raises(M2MissionSystemError) as exc_info:
        load_m2_mission_system(IRST)

    assert exc_info.value.code == "M2_MISSION_SYSTEM_NOT_APPLICABLE"
    assert "system_type=IRST" in exc_info.value.detail


def test_m2_data_003_projection_is_replay_stable() -> None:
    first = load_m2_mission_system(RADAR)
    second = load_m2_mission_system(RADAR)

    assert first == second
    assert first.logical_hash == second.logical_hash
    assert first.metric_logic_executed is False
    assert first.stage_projection_executed is False
    assert first.persistence_executed is False
    assert first.publication_executed is False
