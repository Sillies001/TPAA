from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, uuid5

from tools.testing.ed2_p1_full_input_builder import (
    build_full_p1_catalog_inputs,
    build_full_p1_system_authority,
)
from tpaa_runtime.production_p1_catalog import execute_production_p1_catalog
from tpaa_runtime.production_p1_materialization import (
    ProductionP1AircraftBinding,
    ProductionP1ReleaseContext,
    ProductionP1SystemBinding,
    materialize_production_p1_release,
)

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def _id(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"ed2-full-p1-integration:{name}"))


def _mapping(value: object) -> dict[str, object]:
    assert isinstance(value, Mapping)
    assert all(isinstance(key, str) for key in value)
    return dict(cast(Mapping[str, object], value))


def test_full_116_business_plugins_execute_and_materialize_one_release() -> None:
    inputs = build_full_p1_catalog_inputs(authority_root=AUTHORITY)
    contract, batch = execute_production_p1_catalog(AUTHORITY, inputs)

    assert len(inputs) == 116
    assert batch.metric_codes == contract.metric_codes
    assert len(batch.records) == 116
    assert all(record.plugin_output is not None for record in batch.records)
    assert all(
        record.plugin_output is not None
        and record.plugin_output.get("applicable") is not False
        for record in batch.records
    )

    aircraft_id = _id("aircraft")
    systems, metric_bindings = build_full_p1_system_authority(
        inputs,
        authority_root=AUTHORITY,
        aircraft_id=aircraft_id,
    )
    assert len(systems) == 72
    assert len(metric_bindings) == 72
    system_bindings = {
        metric_code: ProductionP1SystemBinding(
            mission_system_instance_id=system_id,
            aircraft_id=aircraft_id,
            reference_truth_profile_version=str(
                systems[system_id]["reference_truth_profile_version"]
            ),
            reference_quality_status=str(
                systems[system_id]["reference_quality_status"]
            ),
            reference_uncertainty_summary=_mapping(
                systems[system_id]["reference_uncertainty_summary"]
            ),
            alignment_uncertainty_summary=_mapping(
                systems[system_id]["alignment_uncertainty_summary"]
            ),
            context_tags=_mapping(systems[system_id]["context_tags"]),
        )
        for metric_code, system_id in metric_bindings.items()
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
        contract=contract,
        batch=batch,
        inputs=inputs,
        context=context,
        aircraft=ProductionP1AircraftBinding(
            aircraft_id=aircraft_id,
            aircraft_model_id=_id("aircraft-model"),
            aircraft_instance_id=_id("aircraft-instance"),
            subject_entity_id=_id("aircraft-entity"),
            capability_dimension="AIRCRAFT_FLIGHT",
            capability_type="ED2_FULL_P1",
        ),
        system_bindings=system_bindings,
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
