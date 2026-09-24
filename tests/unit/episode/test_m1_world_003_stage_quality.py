from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tpaa_episode import (
    StageQualityError,
    project_basic_flight_stage_quality,
    project_basic_flight_stages,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
NOMINAL = FIXTURES / "BF_M1_NOMINAL_V1"
AUTHORITY_ROOT = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def test_stage_quality_is_exact_replay_stable_and_preserves_world_002() -> None:
    base = project_basic_flight_stages(NOMINAL, authority_root=AUTHORITY_ROOT)
    first = project_basic_flight_stage_quality(NOMINAL, authority_root=AUTHORITY_ROOT)
    second = project_basic_flight_stage_quality(NOMINAL, authority_root=AUTHORITY_ROOT)

    assert first == second
    assert first.stage_quality_projection_executed is True
    assert first.database_persistence_executed is False
    assert first.revision_supersede_executed is False
    assert first.logical_hash_executed is False
    assert first.evidence_refs_projected is False
    assert first.world_projection_executed is False
    assert first.metric_logic_executed is False
    assert len(first.stages) == len(base.stages) == 4

    for source, qualified in zip(base.stages, first.stages, strict=True):
        assert qualified.episode_id == source.episode_id
        assert qualified.stage_id == source.stage_id
        assert qualified.stage_profile_id == source.stage_profile_id
        assert qualified.stage_type == source.stage_type
        assert qualified.stage_order == source.stage_order
        assert qualified.start_session_time_us == source.start_session_time_us
        assert qualified.end_session_time_us == source.end_session_time_us
        assert qualified.precedence_source == source.precedence_source
        assert qualified.detection_method == source.detection_method
        assert qualified.stage_status == "VALID"
        assert qualified.coverage == 1.0
        assert qualified.confidence == 1.0
        assert qualified.detector_version == "M1_BASIC_FLIGHT_STAGE_PROJECTOR_V1"


@pytest.mark.parametrize("bundle", sorted(path for path in FIXTURES.iterdir() if path.is_dir()))
def test_every_governed_fixture_publishes_complete_stage_quality(bundle: Path) -> None:
    projection = project_basic_flight_stage_quality(bundle, authority_root=AUTHORITY_ROOT)

    assert len(projection.stages) == 4
    assert all(stage.stage_status == "VALID" for stage in projection.stages)
    assert all(stage.coverage == 1.0 for stage in projection.stages)
    assert all(stage.confidence == 1.0 for stage in projection.stages)
    assert all(
        stage.detector_version == "M1_BASIC_FLIGHT_STAGE_PROJECTOR_V1"
        for stage in projection.stages
    )


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("coverage", -0.01, "M1_STAGE_QUALITY_RANGE_INVALID"),
        ("coverage", 1.01, "M1_STAGE_QUALITY_RANGE_INVALID"),
        ("confidence", float("nan"), "M1_STAGE_QUALITY_RANGE_INVALID"),
        ("confidence", "1.0", "M1_STAGE_QUALITY_VALUE_INVALID"),
        ("stage_status", "", "M1_STAGE_STATUS_INVALID"),
        ("stage_status", None, "M1_STAGE_STATUS_INVALID"),
        ("detector_version", " ", "M1_STAGE_DETECTOR_VERSION_INVALID"),
        ("detector_version", None, "M1_STAGE_DETECTOR_VERSION_INVALID"),
    ],
)
def test_stage_quality_contract_fails_closed(field: str, value: object, code: str) -> None:
    stage = project_basic_flight_stage_quality(
        NOMINAL,
        authority_root=AUTHORITY_ROOT,
    ).stages[0]

    with pytest.raises(StageQualityError) as caught:
        replace(stage, **{field: value})

    assert caught.value.code == code
