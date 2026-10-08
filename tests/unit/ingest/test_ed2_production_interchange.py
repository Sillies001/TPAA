from __future__ import annotations

import json

import pytest

from tpaa_ingest import (
    FROZEN_SOURCE_FAMILIES,
    PRODUCTION_INTERCHANGE_FAMILIES,
    ProductionInterchangeJsonAdapter,
    ProductionSourceAdapterError,
    SourceFamily,
    build_production_source_registry,
    descriptor_for_interchange_family,
    production_interchange_profile,
    validate_production_interchange_document,
)

SESSION_ID = "e2000000-0000-4000-8000-000000000001"
def _document(family: SourceFamily) -> bytes:
    profile = production_interchange_profile(family)
    return json.dumps(
        {
            "schema": "TPAA_PRODUCTION_INTERCHANGE_SOURCE_V1",
            "schema_version": "1.0.0",
            "source_family": family.value,
            "session_id": SESSION_ID,
            "profile": {
                "profile_id": profile.profile_id,
                "profile_version": profile.profile_version,
                "profile_hash": profile.profile_hash,
            },
            "knowledge_time_utc": "2026-10-08T00:00:00Z",
            "payload": {
                "projection_class": profile.projection_class,
                "lineage_ref": f"source:{family.value}",
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def test_all_nonflight_families_have_exact_governed_interchange_adapters() -> None:
    assert PRODUCTION_INTERCHANGE_FAMILIES == (
        FROZEN_SOURCE_FAMILIES - {SourceFamily.FLIGHT}
    )
    registry = build_production_source_registry()
    assert {
        descriptor.source_family
        for descriptor in registry.inventory()
    } == FROZEN_SOURCE_FAMILIES

    for family in sorted(PRODUCTION_INTERCHANGE_FAMILIES, key=lambda item: item.value):
        descriptor = descriptor_for_interchange_family(family)
        adapter = ProductionInterchangeJsonAdapter(family)
        assert adapter.descriptor == descriptor
        document = validate_production_interchange_document(
            _document(family),
            expected_family=family,
        )
        assert document.source_family is family
        assert document.session_id == SESSION_ID

        envelope = adapter.inspect(
            source_ref=f"gateway://{family.value.lower()}",
            data=_document(family),
            media_type=descriptor.media_types[0],
            classification_label="UNCLASSIFIED",
        )
        assert envelope.source_family is family
        assert envelope.adapter_id == descriptor.adapter_id
        assert envelope.adapter_version == "1.0.0"
        assert len(envelope.artifact_sha256) == 64


def test_interchange_family_mismatch_and_flight_upgrade_fail_closed() -> None:
    tdl = _document(SourceFamily.TDL)
    with pytest.raises(
        ProductionSourceAdapterError,
        match="ED2_INTERCHANGE_FAMILY_MISMATCH",
    ):
        validate_production_interchange_document(
            tdl,
            expected_family=SourceFamily.SCENARIO,
        )

    flight = json.loads(tdl.decode("utf-8"))
    flight["source_family"] = "FLIGHT"
    with pytest.raises(
        ProductionSourceAdapterError,
        match="ED2_INTERCHANGE_FAMILY_UNSUPPORTED",
    ):
        validate_production_interchange_document(
            json.dumps(flight).encode("utf-8"),
        )



def test_interchange_profile_authority_and_projection_class_fail_closed() -> None:
    raw = json.loads(_document(SourceFamily.SCENARIO).decode("utf-8"))
    profile = raw["profile"]
    assert isinstance(profile, dict)
    profile["profile_hash"] = "0" * 64
    with pytest.raises(
        ProductionSourceAdapterError,
        match="ED2_INTERCHANGE_PROFILE_UNAUTHORIZED",
    ):
        validate_production_interchange_document(
            json.dumps(raw).encode("utf-8"),
            expected_family=SourceFamily.SCENARIO,
        )

    raw = json.loads(_document(SourceFamily.SCENARIO).decode("utf-8"))
    payload = raw["payload"]
    assert isinstance(payload, dict)
    payload["projection_class"] = "CLIENT_ASSERTED"
    with pytest.raises(
        ProductionSourceAdapterError,
        match="ED2_INTERCHANGE_PROJECTION_CLASS_DRIFT",
    ):
        validate_production_interchange_document(
            json.dumps(raw).encode("utf-8"),
            expected_family=SourceFamily.SCENARIO,
        )
