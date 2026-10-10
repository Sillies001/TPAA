from __future__ import annotations

import copy
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from tools.testing.ed2_p1_full_input_builder import build_full_p1_request_contract
from tpaa_runtime.production_p1_catalog import (
    build_production_p1_catalog_contract,
    execute_production_p1_catalog,
)
from tpaa_runtime.production_p1_materialization import (
    ProductionP1AircraftBinding,
    ProductionP1ReleaseContext,
    materialize_production_p1_release,
)
from tpaa_runtime.production_p1_request import (
    parse_production_p1_request,
    select_production_p1_sources,
)

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def _id(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"ed2-full-p1-integration:{name}"))


def test_full_116_business_plugins_execute_and_materialize_one_release() -> None:
    aircraft_id = "c2000000-0000-4000-8000-000000000002"
    contract = build_production_p1_catalog_contract(AUTHORITY)
    request_contract = build_full_p1_request_contract(
        aircraft_id=aircraft_id,
        authority_root=AUTHORITY,
    )
    source_selection = select_production_p1_sources(request_contract)
    assert source_selection.source_count == 6
    assert len(source_selection.refs_by_family) == 6
    request = parse_production_p1_request(
        request_contract,
        contract=contract,
        aircraft_id=aircraft_id,
        source_selection=source_selection,
    )
    execution_contract, batch = execute_production_p1_catalog(
        AUTHORITY,
        request.inputs,
    )

    assert execution_contract.plan.logical_hash == contract.plan.logical_hash
    assert len(request.inputs) == 116
    assert batch.metric_codes == contract.metric_codes
    assert len(batch.records) == 116
    assert all(record.plugin_output is not None for record in batch.records)
    assert all(
        record.plugin_output is not None
        and record.plugin_output.get("applicable") is not False
        for record in batch.records
    )

    assert len(request.system_bindings) == 72
    authority_ids = {
        item.mission_system_instance_id
        for item in request.system_authorities
    }
    assert 1 <= len(authority_ids) <= 72
    assert authority_ids == {
        item.mission_system_instance_id
        for item in request.system_bindings.values()
    }
    context = ProductionP1ReleaseContext(
        release_id=_id("release"),
        release_no=1,
        parent_release_id=None,
        request_hash="c" * 64,
        session_id=_id("session"),
        context_id=_id("context"),
        context_version="ED2-FULL-P1-CONTEXT-V1",
        context_binding_hash="d" * 64,
        comparison_context_hash="e" * 64,
        episode_id=_id("episode"),
        stage_id=None,
        start_session_time_us=0,
        end_session_time_us=10_000_000,
        coverage=1.0,
        confidence=1.0,
        observation_schema_version="ED2-P1-OBSERVATION-V1",
        world_product_versions={"truth": "ED2-FULL-P1-WORLD-V1"},
    )
    release = materialize_production_p1_release(
        contract=execution_contract,
        batch=batch,
        inputs=request.inputs,
        context=context,
        aircraft=ProductionP1AircraftBinding(
            aircraft_id=aircraft_id,
            aircraft_model_id=_id("aircraft-model"),
            aircraft_instance_id=_id("aircraft-instance"),
            subject_entity_id=_id("aircraft-entity"),
            capability_dimension="AIRCRAFT_FLIGHT",
            capability_type="ED2_FULL_P1",
        ),
        system_bindings=request.system_bindings,
    )

    assert len(release.definitions) == 116
    assert len(release.metric_instances) == len(release.evidence_sets)
    assert release.metric_instances
    assert release.observations
    assert release.system_observations
    assert len(release.manifest_hash) == 64

    definition_routes = {
        item.metric_code: item.publication_route
        for item in release.definitions
    }
    metric_codes_by_id = {
        item.metric_definition_id: item.metric_code
        for item in release.definitions
    }
    capability_codes = {
        metric_codes_by_id[item.metric_definition_id]
        for item in release.metric_instances
        if definition_routes[
            metric_codes_by_id[item.metric_definition_id]
        ]
        == "CAPABILITY_OBSERVATION"
    }
    system_codes = {
        metric_codes_by_id[item.metric_definition_id]
        for item in release.metric_instances
        if definition_routes[
            metric_codes_by_id[item.metric_definition_id]
        ]
        == "SYSTEM_PERFORMANCE_OBSERVATION"
    }
    evidence_only_codes = {
        metric_codes_by_id[item.metric_definition_id]
        for item in release.metric_instances
        if definition_routes[
            metric_codes_by_id[item.metric_definition_id]
        ]
        == "METRIC_INSTANCE_EVIDENCE_ONLY"
    }
    assert len(capability_codes) == 39
    assert len(system_codes) == 72
    assert len(evidence_only_codes) == 5



def test_missing_scenario_source_publishes_business_insufficiency_not_job_failure() -> None:
    aircraft_id = "c2000000-0000-4000-8000-000000000002"
    contract = build_production_p1_catalog_contract(AUTHORITY)
    payload = copy.deepcopy(
        build_full_p1_request_contract(
            aircraft_id=aircraft_id,
            authority_root=AUTHORITY,
        )
    )
    source_documents = payload["source_documents"]
    assert isinstance(source_documents, list)

    def source_family(item: object) -> str | None:
        if not isinstance(item, dict):
            return None
        metadata = item.get("source_import")
        if not isinstance(metadata, dict):
            return None
        family = metadata.get("source_family")
        return family if isinstance(family, str) else None

    payload["source_documents"] = [
        item
        for item in source_documents
        if source_family(item) != "SCENARIO"
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

    selection = select_production_p1_sources(payload)
    request = parse_production_p1_request(
        payload,
        contract=contract,
        aircraft_id=aircraft_id,
        source_selection=selection,
    )
    execution_contract, batch = execute_production_p1_catalog(
        AUTHORITY,
        request.inputs,
    )

    assert len(batch.records) == 116
    assert all(record.plugin_output is not None for record in batch.records)
    for record in batch.records:
        output = record.plugin_output
        assert output is not None
        assert output["applicable"] is True
        instances = output["instances"]
        assert isinstance(instances, list)
        assert len(instances) == 1
        instance = instances[0]
        assert isinstance(instance, dict)
        assert instance["status"] == "INSUFFICIENT_DATA"
        assert instance["reason_codes"] == [
            "ED2_SOURCE_FAMILY_MISSING_SCENARIO"
        ]
        assert instance["value_numeric"] is None
        assert instance["value_structured"] is None

    release = materialize_production_p1_release(
        contract=execution_contract,
        batch=batch,
        inputs=request.inputs,
        context=ProductionP1ReleaseContext(
            release_id=_id("insufficient-release"),
            release_no=1,
            parent_release_id=None,
            request_hash="e" * 64,
            session_id=_id("insufficient-session"),
            context_id=_id("insufficient-context"),
            context_version="ED2-MISSING-SOURCE-V1",
            context_binding_hash="f" * 64,
            episode_id=_id("insufficient-episode"),
            stage_id=None,
            start_session_time_us=0,
            end_session_time_us=10_000_000,
            coverage=1.0,
            confidence=1.0,
            observation_schema_version="ED2-P1-OBSERVATION-V1",
            world_product_versions={"truth": "ED2-MISSING-SOURCE-WORLD-V1"},
        ),
        aircraft=ProductionP1AircraftBinding(
            aircraft_id=aircraft_id,
            aircraft_model_id=_id("insufficient-aircraft-model"),
            aircraft_instance_id=_id("insufficient-aircraft-instance"),
            subject_entity_id=_id("insufficient-aircraft-entity"),
            capability_dimension="AIRCRAFT_FLIGHT",
            capability_type="ED2_MISSING_SOURCE",
        ),
        system_bindings=request.system_bindings,
    )

    assert len(release.definitions) == 116
    assert len(release.metric_instances) == 116
    assert len(release.observations) == 39
    assert len(release.system_observations) == 72
    assert all(
        item.status == "INSUFFICIENT_DATA"
        for item in release.metric_instances
    )
    assert all(
        item.eligibility_status == "EXCLUDED"
        for item in release.observations
    )
    assert all(
        item.eligibility_status == "EXCLUDED"
        for item in release.system_observations
    )
    first_evidence = release.evidence_sets[0].series_locator
    sufficiency = first_evidence["source_sufficiency"]
    assert isinstance(sufficiency, dict)
    assert sufficiency["status"] == "INSUFFICIENT_DATA"
    assert sufficiency["missing_source_families"] == ["SCENARIO"]
