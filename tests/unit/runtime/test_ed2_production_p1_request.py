from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tools.testing.ed2_p1_full_input_builder import build_full_p1_request_contract
from tpaa_ingest import SourceFamily
from tpaa_runtime.production_p1_catalog import build_production_p1_catalog_contract
from tpaa_runtime.production_p1_request import (
    ProductionP1RequestError,
    parse_production_p1_request,
    select_production_p1_sources,
)
from tpaa_storage.hashing import canonical_request_hash

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
AIRCRAFT_ID = "c2000000-0000-4000-8000-000000000002"


def _contract() -> dict[str, object]:
    return build_full_p1_request_contract(
        aircraft_id=AIRCRAFT_ID,
        authority_root=AUTHORITY,
    )


def _source_family(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    metadata = value.get("source_import")
    if not isinstance(metadata, dict):
        return None
    family = metadata.get("source_family")
    return family if isinstance(family, str) else None


def test_full_p1_request_binds_each_metric_to_registered_source_artifacts() -> None:
    payload = _contract()
    catalog = build_production_p1_catalog_contract(AUTHORITY)
    sources = select_production_p1_sources(payload)

    assert sources.source_count == 6
    assert len(sources.refs_by_family) == 6
    request = parse_production_p1_request(
        payload,
        contract=catalog,
        aircraft_id=AIRCRAFT_ID,
        source_selection=sources,
    )

    assert len(request.inputs) == 116
    for metric_code, metric_input in request.inputs.items():
        lineage = metric_input.get("_source_lineage")
        assert isinstance(lineage, list)
        assert lineage
        for raw in lineage:
            assert isinstance(raw, dict)
            assert len(str(raw["artifact_sha256"])) == 64
            assert str(raw["source_id"])
            assert str(raw["artifact_id"])
            assert str(raw["source_ref"])
        assert metric_code in catalog.metric_codes


def test_full_p1_request_rejects_unregistered_required_source_family() -> None:
    payload = _contract()
    sources = payload["source_documents"]
    assert isinstance(sources, list)
    payload["source_documents"] = [
        item
        for item in sources
        if _source_family(item) != "RANGE_ACMI"
    ]
    catalog = build_production_p1_catalog_contract(AUTHORITY)
    selection = select_production_p1_sources(payload)

    with pytest.raises(
        ProductionP1RequestError,
        match="ED2_P1_SOURCE_LINEAGE_UNREGISTERED",
    ):
        parse_production_p1_request(
            payload,
            contract=catalog,
            aircraft_id=AIRCRAFT_ID,
            source_selection=selection,
        )


def test_full_p1_request_forbids_caller_supplied_source_lineage() -> None:
    payload = _contract()
    inputs = payload["p1_catalog_inputs"]
    assert isinstance(inputs, dict)
    first = next(iter(inputs.values()))
    assert isinstance(first, dict)
    first["_source_lineage"] = [{"artifact_sha256": "0" * 64}]
    catalog = build_production_p1_catalog_contract(AUTHORITY)
    selection = select_production_p1_sources(payload)

    with pytest.raises(
        ProductionP1RequestError,
        match="ED2_P1_SOURCE_LINEAGE_OVERRIDE_FORBIDDEN",
    ):
        parse_production_p1_request(
            payload,
            contract=catalog,
            aircraft_id=AIRCRAFT_ID,
            source_selection=selection,
        )


def test_full_p1_source_set_rejects_document_import_session_drift() -> None:
    payload = copy.deepcopy(_contract())
    sources = payload["source_documents"]
    assert isinstance(sources, list)
    scenario_raw = next(
        item
        for item in sources
        if _source_family(item) == "SCENARIO"
    )
    assert isinstance(scenario_raw, dict)
    scenario = scenario_raw
    source_json = scenario["source_json"]
    assert isinstance(source_json, str)
    document = json.loads(source_json)
    assert isinstance(document, dict)
    document["session_id"] = "c2000000-0000-4000-8000-000000000099"
    scenario["source_json"] = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
    )

    with pytest.raises(
        ProductionP1RequestError,
        match="ED2_P1_SOURCE_IMPORT_SESSION_DRIFT",
    ):
        select_production_p1_sources(payload)


def test_full_p1_source_set_rejects_cross_session_interchange() -> None:
    payload = copy.deepcopy(_contract())
    sources = payload["source_documents"]
    assert isinstance(sources, list)
    scenario_raw = next(
        item
        for item in sources
        if _source_family(item) == "SCENARIO"
    )
    assert isinstance(scenario_raw, dict)
    source_json = scenario_raw["source_json"]
    assert isinstance(source_json, str)
    document = json.loads(source_json)
    assert isinstance(document, dict)
    foreign_session = "c2000000-0000-4000-8000-000000000099"
    document["session_id"] = foreign_session
    scenario_raw["source_json"] = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
    )
    metadata = scenario_raw["source_import"]
    assert isinstance(metadata, dict)
    metadata["session_id"] = foreign_session

    with pytest.raises(
        ProductionP1RequestError,
        match="ED2_P1_SOURCE_SET_SESSION_DRIFT",
    ):
        select_production_p1_sources(payload)


def test_full_p1_request_contract_is_hash_safe_and_restores_numeric_inputs() -> None:
    payload = _contract()
    request_hash = canonical_request_hash(
        {"job_type": "BUILD_P1_RELEASE", "payload": payload}
    )
    assert len(request_hash) == 64

    catalog = build_production_p1_catalog_contract(AUTHORITY)
    selection = select_production_p1_sources(payload)
    request = parse_production_p1_request(
        payload,
        contract=catalog,
        aircraft_id=AIRCRAFT_ID,
        source_selection=selection,
    )
    air001 = request.inputs["P1-AIR-001"]
    m1_result = air001["m1_result"]
    assert isinstance(m1_result, dict)
    assert isinstance(m1_result["value_numeric"], float)


def test_full_p1_request_rejects_metric_input_drift_from_source_projection() -> None:
    payload = copy.deepcopy(_contract())
    inputs = payload["p1_catalog_inputs"]
    assert isinstance(inputs, dict)
    metric = inputs["P1-AIR-004"]
    assert isinstance(metric, dict)
    metric["ed2_tamper_probe"] = "CHANGED_AFTER_SOURCE_PROJECTION"

    catalog = build_production_p1_catalog_contract(AUTHORITY)
    selection = select_production_p1_sources(payload)
    with pytest.raises(
        ProductionP1RequestError,
        match="ED2_P1_SOURCE_INPUT_HASH_DRIFT",
    ):
        parse_production_p1_request(
            payload,
            contract=catalog,
            aircraft_id=AIRCRAFT_ID,
            source_selection=selection,
        )


def test_full_p1_request_rejects_missing_source_input_binding_claim() -> None:
    payload = copy.deepcopy(_contract())
    sources = payload["source_documents"]
    assert isinstance(sources, list)
    mission_raw = next(
        item
        for item in sources
        if _source_family(item) == "MISSION_AVIONICS"
    )
    assert isinstance(mission_raw, dict)
    source_json = mission_raw["source_json"]
    assert isinstance(source_json, str)
    document = json.loads(source_json)
    assert isinstance(document, dict)
    raw_payload = document["payload"]
    assert isinstance(raw_payload, dict)
    hashes = raw_payload["metric_input_hashes"]
    assert isinstance(hashes, dict)
    code = next(iter(hashes))
    del hashes[code]
    mission_raw["source_json"] = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
    )

    catalog = build_production_p1_catalog_contract(AUTHORITY)
    selection = select_production_p1_sources(payload)
    with pytest.raises(
        ProductionP1RequestError,
        match="ED2_P1_SOURCE_INPUT_BINDING_MISSING",
    ):
        parse_production_p1_request(
            payload,
            contract=catalog,
            aircraft_id=AIRCRAFT_ID,
            source_selection=selection,
        )



def test_full_p1_request_marks_missing_required_source_as_business_insufficiency() -> None:
    payload = copy.deepcopy(_contract())
    sources = payload["source_documents"]
    assert isinstance(sources, list)
    payload["source_documents"] = [
        item
        for item in sources
        if _source_family(item) != "SCENARIO"
    ]
    lineage = payload["metric_input_source_families"]
    assert isinstance(lineage, dict)
    for metric_code, raw_families in lineage.items():
        assert isinstance(metric_code, str)
        assert isinstance(raw_families, list)
        lineage[metric_code] = [
            family
            for family in raw_families
            if family != "SCENARIO"
        ]

    catalog = build_production_p1_catalog_contract(AUTHORITY)
    selection = select_production_p1_sources(payload)
    assert selection.source_count == 5
    request = parse_production_p1_request(
        payload,
        contract=catalog,
        aircraft_id=AIRCRAFT_ID,
        source_selection=selection,
    )

    assert len(request.inputs) == 116
    for metric_input in request.inputs.values():
        sufficiency = metric_input["_source_sufficiency"]
        assert isinstance(sufficiency, dict)
        assert sufficiency["status"] == "INSUFFICIENT_DATA"
        assert sufficiency["missing_source_families"] == ["SCENARIO"]
        assert sufficiency["reason_codes"] == [
            "ED2_SOURCE_FAMILY_MISSING_SCENARIO"
        ]


def test_full_p1_request_forbids_caller_supplied_source_sufficiency() -> None:
    payload = _contract()
    inputs = payload["p1_catalog_inputs"]
    assert isinstance(inputs, dict)
    first = next(iter(inputs.values()))
    assert isinstance(first, dict)
    first["_source_sufficiency"] = {
        "status": "READY",
        "missing_source_families": [],
    }
    catalog = build_production_p1_catalog_contract(AUTHORITY)
    selection = select_production_p1_sources(payload)

    with pytest.raises(
        ProductionP1RequestError,
        match="ED2_P1_SOURCE_LINEAGE_OVERRIDE_FORBIDDEN",
    ):
        parse_production_p1_request(
            payload,
            contract=catalog,
            aircraft_id=AIRCRAFT_ID,
            source_selection=selection,
        )



def test_full_p1_source_selection_retains_governed_world_projections() -> None:
    payload = _contract()
    selection = select_production_p1_sources(payload)

    flight_refs = selection.refs_by_family[SourceFamily.FLIGHT]
    scenario_refs = selection.refs_by_family[SourceFamily.SCENARIO]
    assert len(flight_refs) == 1
    assert len(scenario_refs) == 1

    action = flight_refs[0].projection_payload.get("action_projection")
    assert isinstance(action, dict)
    assert action["schema"] == "TPAA_ED2_BASIC_FLIGHT_ACTION_PROJECTION_V1"
    assert action["profile_id"] == "BASIC_FLIGHT_ACTION_V1"

    stage = scenario_refs[0].projection_payload.get("stage_projection")
    assert isinstance(stage, dict)
    assert stage["stage_profile_id"] == "BASIC_FLIGHT_V1"
    assert stage["precedence_source"] == "CONTEXT_OFFICIAL_MARKER"
    assert stage["detection_method"] == "CONTEXT"
