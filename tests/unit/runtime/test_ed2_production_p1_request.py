from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tools.testing.ed2_p1_full_input_builder import build_full_p1_request_contract
from tpaa_runtime.production_p1_catalog import build_production_p1_catalog_contract
from tpaa_runtime.production_p1_request import (
    ProductionP1RequestError,
    parse_production_p1_request,
    select_production_p1_sources,
)

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
        match="ED2_P1_SOURCE_SET_SESSION_DRIFT",
    ):
        select_production_p1_sources(payload)
