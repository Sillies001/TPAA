from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_registry import (
    AircraftIdentityError,
    parse_governed_aircraft_id,
    resolve_aircraft_identity,
    resolve_all_aircraft_identities,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "m1"
EXPECTED_AIRCRAFT_ID = "22222222-2222-4222-8222-222222222222"


def test_nominal_fixture_resolves_governed_aircraft_id_not_source_alias() -> None:
    resolution = resolve_aircraft_identity(FIXTURE_ROOT / "BF_M1_NOMINAL_V1")

    assert resolution.aircraft_id == EXPECTED_AIRCRAFT_ID
    assert resolution.identity_field == "aircraft_id"
    assert resolution.source_aircraft_key == "SYNTH-ACFT-01"
    assert resolution.source_alias_role == "LINEAGE_ONLY"
    assert resolution.aircraft_id != resolution.source_aircraft_key
    assert resolution.resolution_method == "GOVERNED_FIXTURE_AIRCRAFT_ID"
    assert resolution.resolution_version == "1.0.0"
    assert len(resolution.replay_basis_sha256) == 64
    assert len(resolution.logical_hash) == 64
    assert resolution.master_aircraft_persistence_executed is False
    assert resolution.aircraft_instance_projection_executed is False
    assert resolution.canonical_flight_channel_projection_executed is False
    assert resolution.evaluation_context_binding_executed is False
    assert resolution.stage_projection_executed is False
    assert resolution.metric_logic_executed is False


def test_all_governed_fixtures_replay_to_one_stable_aircraft_identity() -> None:
    first = resolve_all_aircraft_identities(FIXTURE_ROOT)
    second = resolve_all_aircraft_identities(FIXTURE_ROOT)

    assert first == second
    assert len(first) == 8
    assert {item.aircraft_id for item in first} == {EXPECTED_AIRCRAFT_ID}
    assert {item.source_alias_role for item in first} == {"LINEAGE_ONLY"}
    assert len({item.replay_basis_sha256 for item in first}) == 8
    assert len({item.logical_hash for item in first}) == 8


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-a-uuid",
        "22222222222242228222222222222222",
        "22222222-2222-4222-8222-22222222222",
        "22222222-2222-4222-8222-222222222222 ",
        "22222222-2222-4222-8222-22222222222A",
        "00000000-0000-0000-0000-000000000000",
    ],
)
def test_governed_aircraft_id_parser_fails_closed_on_noncanonical_uuid(
    value: str,
) -> None:
    with pytest.raises(AircraftIdentityError) as caught:
        parse_governed_aircraft_id(value)

    assert caught.value.code == "M1_AIRCRAFT_IDENTITY_UUID_INVALID"


def test_governed_aircraft_id_parser_preserves_canonical_uuid() -> None:
    assert parse_governed_aircraft_id(EXPECTED_AIRCRAFT_ID) == EXPECTED_AIRCRAFT_ID
