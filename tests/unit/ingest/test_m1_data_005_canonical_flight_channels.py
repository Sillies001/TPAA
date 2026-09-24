from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_ingest import load_synthetic_fixture_bundle
from tpaa_ingest.canonical_flight_channels import (
    CANONICAL_FLIGHT_CHANNELS,
    CanonicalFlightChannelError,
    project_canonical_flight_channels,
)
from tpaa_registry import build_session_time_projection, resolve_aircraft_identity

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "m1"


def _project(fixture_id: str):
    path = FIXTURE_ROOT / fixture_id
    bundle = load_synthetic_fixture_bundle(path)
    timed = build_session_time_projection(path)
    aircraft = resolve_aircraft_identity(path)
    return project_canonical_flight_channels(
        bundle,
        aircraft_id=aircraft.aircraft_id,
        session_time_us=tuple(row.session_time_us for row in timed.rows),
    )


def test_nominal_fixture_projects_exact_governed_canonical_channels() -> None:
    projection = _project("BF_M1_NOMINAL_V1")

    assert projection.authority_id == "CANONICAL_AIRCRAFT_STATE_V1"
    assert projection.channel_names == CANONICAL_FLIGHT_CHANNELS
    assert len(projection.rows) == 8
    first = projection.rows[0]
    assert first.source_stream_ordinal == 0
    assert first.session_time_us == 1_000_000
    assert first.body_p_rad_s == 0.1
    assert first.nz_g == 1.0
    assert first.heading_true_rad == 0.0
    assert first.tas_mps == 100.0
    assert first.mach == 0.3
    assert first.quality_mask == 0
    assert len(projection.logical_hash) == 64


def test_structured_partial_preserves_missing_tas_and_mach_as_null() -> None:
    projection = _project("BF_M1_STRUCTURED_PARTIAL_V1")

    assert sum(row.tas_mps is None for row in projection.rows) == 4
    assert sum(row.mach is None for row in projection.rows) == 4
    assert projection.rows[0].tas_mps == 100.0
    assert projection.rows[0].mach is None
    assert projection.rows[1].tas_mps is None
    assert projection.rows[1].mach == 0.31


def test_projection_replay_is_exact_and_has_no_downstream_execution() -> None:
    first = _project("BF_M1_CROSS_PLATFORM_V1")
    second = _project("BF_M1_CROSS_PLATFORM_V1")

    assert first == second
    assert first.database_persistence_executed is False
    assert first.evaluation_context_binding_executed is False
    assert first.stage_projection_executed is False
    assert first.world_projection_executed is False
    assert first.metric_logic_executed is False


def test_projection_fails_closed_when_session_time_count_does_not_match() -> None:
    path = FIXTURE_ROOT / "BF_M1_NOMINAL_V1"
    bundle = load_synthetic_fixture_bundle(path)
    aircraft = resolve_aircraft_identity(path)

    with pytest.raises(CanonicalFlightChannelError) as caught:
        project_canonical_flight_channels(
            bundle,
            aircraft_id=aircraft.aircraft_id,
            session_time_us=(0,),
        )

    assert caught.value.code == "M1_CANONICAL_SESSION_TIME_COUNT_MISMATCH"
