from __future__ import annotations

import json
from pathlib import Path

import pytest

from tpaa_world.m3_mission_product_applicability import (
    M3MissionProductApplicabilityError,
    load_m3_mission_product_inputs,
    project_m3_family_applicability,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "m3"
    / "M3_WORLD_004_MISSION_SYSTEMS_V1.json"
)

TRACK_ID = "61111111-1111-4111-8111-111111111111"
IRST = "62222222-2222-4222-8222-222222222222"
EO = "63333333-3333-4333-8333-333333333333"
RWR = "64444444-4444-4444-8444-444444444444"
ESM = "65555555-5555-4555-8555-555555555555"
DL = "66666666-6666-4666-8666-666666666666"
FUS = "67777777-7777-4777-8777-777777777777"
RADAR = "68888888-8888-4888-8888-888888888888"


def test_m3_world_004_exact_catalog_applicability() -> None:
    inputs = load_m3_mission_product_inputs(FIXTURE, authority_root=AUTHORITY)
    assert inputs.fixture_id == "M3_WORLD_004_MISSION_SYSTEMS_V1"
    assert len(inputs.subjects) == 8
    assert len(inputs.contracts) == 6
    assert all(contract.subject_type == "MISSION_SYSTEM_INSTANCE" for contract in inputs.contracts)

    positives = (
        ("P1-TRK-*", TRACK_ID),
        ("P1-ID-*", TRACK_ID),
        ("P1-PSV-*", IRST),
        ("P1-PSV-*", EO),
        ("P1-ESM-*", RWR),
        ("P1-ESM-*", ESM),
        ("P1-DL-*", DL),
        ("P1-FUS-*", FUS),
    )
    for family, subject in positives:
        result = project_m3_family_applicability(
            inputs,
            family_code=family,
            mission_system_instance_id=subject,
        )
        assert result.applicable
        assert result.product_input_emitted
        assert result.reason_code.startswith("APPLICABLE_")

    negatives = (
        ("P1-TRK-*", RADAR, "NOT_APPLICABLE_PRODUCT_CAPABILITY_MISSING"),
        ("P1-ID-*", RADAR, "NOT_APPLICABLE_PRODUCT_CAPABILITY_MISSING"),
        ("P1-PSV-*", RADAR, "NOT_APPLICABLE_SYSTEM_TYPE"),
        ("P1-ESM-*", RADAR, "NOT_APPLICABLE_SYSTEM_TYPE"),
        ("P1-DL-*", RADAR, "NOT_APPLICABLE_SYSTEM_TYPE"),
        ("P1-FUS-*", RADAR, "NOT_APPLICABLE_SYSTEM_TYPE"),
    )
    for family, subject, reason in negatives:
        result = project_m3_family_applicability(
            inputs,
            family_code=family,
            mission_system_instance_id=subject,
        )
        assert not result.applicable
        assert not result.product_input_emitted
        assert result.reason_code == reason

    assert not inputs.metric_logic_executed
    assert not inputs.persistence_executed
    assert not inputs.publication_executed


def _mutated(tmp_path: Path, mode: str) -> Path:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if mode == "unknown-product":
        payload["mission_system_instances"][0]["product_semantics"].append(
            "UNFROZEN_PRODUCT"
        )
    elif mode == "unknown-system":
        payload["mission_system_instances"][1]["system_type"] = "UNKNOWN_SENSOR"
    else:
        raise AssertionError(mode)
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_m3_world_004_rejects_unfrozen_product_semantics(tmp_path: Path) -> None:
    with pytest.raises(M3MissionProductApplicabilityError) as captured:
        load_m3_mission_product_inputs(
            _mutated(tmp_path, "unknown-product"),
            authority_root=AUTHORITY,
        )
    assert captured.value.code == "M3_WORLD_004_PRODUCT_SEMANTICS_UNGOVERNED"


def test_m3_world_004_rejects_unknown_system_type(tmp_path: Path) -> None:
    with pytest.raises(M3MissionProductApplicabilityError) as captured:
        load_m3_mission_product_inputs(
            _mutated(tmp_path, "unknown-system"),
            authority_root=AUTHORITY,
        )
    assert captured.value.code == "M3_WORLD_004_CORE_SYSTEM_TYPE_INVALID"


def test_m3_world_004_unknown_family_and_subject_fail_closed() -> None:
    inputs = load_m3_mission_product_inputs(FIXTURE, authority_root=AUTHORITY)
    with pytest.raises(M3MissionProductApplicabilityError) as family_error:
        project_m3_family_applicability(
            inputs,
            family_code="P1-UNKNOWN-*",
            mission_system_instance_id=RADAR,
        )
    assert family_error.value.code == "M3_WORLD_004_FAMILY_NOT_GOVERNED"

    with pytest.raises(M3MissionProductApplicabilityError) as subject_error:
        project_m3_family_applicability(
            inputs,
            family_code="P1-PSV-*",
            mission_system_instance_id="69999999-9999-4999-8999-999999999999",
        )
    assert subject_error.value.code == "M3_WORLD_004_SUBJECT_NOT_FOUND"
