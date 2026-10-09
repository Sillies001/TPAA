from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

from tools.testing.m3_runtime_closure_check import (
    _positive_input,
    _runtime_probe_output,
)
from tpaa_metric import (
    M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
    CatalogMetricEngine,
    M2MetricExecutionBatch,
    M2MetricPluginRequest,
    MetricPluginRegistry,
)
from tpaa_runtime.production_p1_catalog import (
    ProductionP1CatalogContract,
    build_production_p1_catalog_contract,
)
from tpaa_runtime.production_p1_materialization import (
    ProductionP1AircraftBinding,
    ProductionP1MaterializationError,
    ProductionP1ReleaseContext,
    ProductionP1SystemBinding,
    materialize_production_p1_release,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def _id(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"ed2-p1-materialization:{name}"))


def _execution() -> tuple[
    ProductionP1CatalogContract,
    M2MetricExecutionBatch,
    dict[str, dict[str, object]],
]:
    contract = build_production_p1_catalog_contract(AUTHORITY)
    registry = MetricPluginRegistry()

    def probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return _runtime_probe_output(
            request.definition,
            request.input_payload,
            request.upstream_result_hashes,
        )

    for definition in contract.plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"ed2-materialization-probe:{definition.metric_code}:v1",
            plugin=probe,
        )
    inputs = {}
    for definition in contract.plan.definitions:
        payload = _positive_input(definition)
        payload["_source_lineage"] = [
            {
                "source_family": "FLIGHT",
                "source_id": _id("source"),
                "artifact_id": _id("artifact"),
                "artifact_sha256": "e" * 64,
                "adapter_id": "ed2-materialization-test",
                "adapter_version": "1.0.0",
                "source_ref": "test://ed2/materialization",
            }
        ]
        payload["_source_sufficiency"] = {
            "status": "READY",
            "required_source_families": ["FLIGHT"],
            "actual_source_families": ["FLIGHT"],
            "missing_source_families": [],
            "reason_codes": [],
        }
        inputs[definition.metric_code] = payload
    batch = CatalogMetricEngine(
        contract.plan,
        registry,
        operator_implementations=M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
    ).execute(inputs)
    return contract, batch, inputs


def _context() -> ProductionP1ReleaseContext:
    return ProductionP1ReleaseContext(
        release_id=_id("release"),
        release_no=1,
        parent_release_id=None,
        request_hash="a" * 64,
        session_id=_id("session"),
        context_id=_id("context"),
        context_version="ED2-CONTEXT-V1",
        context_binding_hash="b" * 64,
        comparison_context_hash="c" * 64,
        episode_id=_id("episode"),
        stage_id=None,
        start_session_time_us=1_000_000,
        end_session_time_us=11_000_000,
        coverage=1.0,
        confidence=1.0,
        observation_schema_version="ED2-P1-OBSERVATION-V1",
        world_product_versions={"truth": "ED2-WORLD-V1"},
    )


def _aircraft() -> ProductionP1AircraftBinding:
    return ProductionP1AircraftBinding(
        aircraft_id=_id("aircraft"),
        aircraft_model_id=_id("aircraft-model"),
        aircraft_instance_id=_id("aircraft-instance"),
        subject_entity_id=_id("aircraft-entity"),
        capability_dimension="AIRCRAFT_FLIGHT",
        capability_type="KINEMATIC_ENERGY_CONTROL",
    )


def _systems(
    contract: ProductionP1CatalogContract,
) -> dict[str, ProductionP1SystemBinding]:
    definitions = contract.plan.definitions
    return {
        definition.metric_code: ProductionP1SystemBinding(
            mission_system_instance_id=_id(
                f"system:{definition.metric_code}"
            ),
            aircraft_id=_id("aircraft"),
            reference_truth_profile_version="ED2-REFERENCE-V1",
            reference_quality_status="AVAILABLE",
            reference_uncertainty_summary={"status": "BOUNDED"},
            alignment_uncertainty_summary={"status": "BOUNDED"},
            context_tags={"metric_family": definition.family},
        )
        for definition in definitions
        if definition.subject_type == "MISSION_SYSTEM_INSTANCE"
    }


def test_exact_116_execution_materializes_all_three_publication_routes() -> None:
    contract, batch, inputs = _execution()
    systems = _systems(contract)

    release = materialize_production_p1_release(
        contract=contract,
        batch=batch,
        inputs=inputs,
        context=_context(),
        aircraft=_aircraft(),
        system_bindings=systems,
    )

    assert len(release.definitions) == 116
    assert len(release.metric_instances) == 116
    assert len(release.evidence_sets) == 116
    assert len(release.observations) == 39
    assert len(release.system_observations) == 72
    assert len(
        {
            item.metric_definition_id
            for item in release.definitions
        }
    ) == 116
    assert len(
        {
            item.metric_instance_id
            for item in release.metric_instances
        }
    ) == 116

    observed_ids = {
        item.observed_metric_instance_id
        for item in release.observations
    }
    system_observed_ids = {
        item.observed_metric_instance_id
        for item in release.system_observations
    }
    all_instance_ids = {
        item.metric_instance_id
        for item in release.metric_instances
    }
    evidence_only_ids = all_instance_ids - observed_ids - system_observed_ids
    assert len(evidence_only_ids) == 5

    by_code = {
        definition.metric_code: definition
        for definition in release.definitions
    }
    instance_by_definition = {
        item.metric_definition_id: item
        for item in release.metric_instances
    }
    for code, definition in by_code.items():
        instance = instance_by_definition[definition.metric_definition_id]
        if definition.subject_type == "AIRCRAFT":
            assert instance.subject_entity_id == _id("aircraft-entity")
            assert instance.mission_system_instance_id is None
        elif definition.subject_type == "MISSION_SYSTEM_INSTANCE":
            assert instance.subject_entity_id is None
            assert (
                instance.mission_system_instance_id
                == systems[code].mission_system_instance_id
            )
        else:
            assert definition.subject_type == "TARGET_PAIR"
            assert instance.subject_entity_id is None
            assert instance.mission_system_instance_id is None

    replay = materialize_production_p1_release(
        contract=contract,
        batch=batch,
        inputs=dict(reversed(tuple(inputs.items()))),
        context=_context(),
        aircraft=_aircraft(),
        system_bindings=systems,
    )
    assert replay == release
    assert len(release.manifest_hash) == 64


def test_system_metric_instance_requires_explicit_subject_binding() -> None:
    contract, batch, inputs = _execution()
    systems = _systems(contract)
    missing_code = next(iter(systems))
    del systems[missing_code]

    with pytest.raises(
        ProductionP1MaterializationError,
        match="ED2_P1_SYSTEM_BINDING_MISSING",
    ):
        materialize_production_p1_release(
            contract=contract,
            batch=batch,
            inputs=inputs,
            context=_context(),
            aircraft=_aircraft(),
            system_bindings=systems,
        )



def test_materialization_rejects_post_execution_input_evidence_drift() -> None:
    contract, batch, inputs = _execution()
    first_code = contract.metric_codes[0]
    inputs[first_code]["_source_sufficiency"] = {
        "status": "INSUFFICIENT_DATA",
        "required_source_families": ["FLIGHT", "SCENARIO"],
        "actual_source_families": ["FLIGHT"],
        "missing_source_families": ["SCENARIO"],
        "reason_codes": ["ED2_SOURCE_FAMILY_MISSING_SCENARIO"],
    }

    with pytest.raises(
        ProductionP1MaterializationError,
        match="ED2_P1_INPUT_PAYLOAD_HASH_DRIFT",
    ):
        materialize_production_p1_release(
            contract=contract,
            batch=batch,
            inputs=inputs,
            context=_context(),
            aircraft=_aircraft(),
            system_bindings=_systems(contract),
        )



def test_p2_comparison_key_excludes_exact_subject_and_context_identity() -> None:
    contract, batch, inputs = _execution()
    first = materialize_production_p1_release(
        contract=contract,
        batch=batch,
        inputs=inputs,
        context=_context(),
        aircraft=_aircraft(),
        system_bindings=_systems(contract),
    )
    alternate_context = ProductionP1ReleaseContext(
        release_id=_id("release-2"),
        release_no=1,
        parent_release_id=None,
        request_hash="d" * 64,
        session_id=_id("session-2"),
        context_id=_id("context-2"),
        context_version="ED2-CONTEXT-V1",
        context_binding_hash="e" * 64,
        comparison_context_hash="c" * 64,
        episode_id=_id("episode-2"),
        stage_id=None,
        start_session_time_us=1_000_000,
        end_session_time_us=11_000_000,
        coverage=1.0,
        confidence=1.0,
        observation_schema_version="ED2-P1-OBSERVATION-V1",
        world_product_versions={"truth": "ED2-WORLD-V1"},
    )
    alternate_aircraft = ProductionP1AircraftBinding(
        aircraft_id=_id("aircraft"),
        aircraft_model_id=_id("aircraft-model"),
        aircraft_instance_id=_id("aircraft-instance-2"),
        subject_entity_id=_id("aircraft-entity-2"),
        capability_dimension="AIRCRAFT_FLIGHT",
        capability_type="KINEMATIC_ENERGY_CONTROL",
    )
    second = materialize_production_p1_release(
        contract=contract,
        batch=batch,
        inputs=inputs,
        context=alternate_context,
        aircraft=alternate_aircraft,
        system_bindings=_systems(contract),
    )
    first_by_definition = {
        item.observed_metric_instance_id: item.comparison_key_hash
        for item in first.observations
    }
    second_by_definition = {
        item.observed_metric_instance_id: item.comparison_key_hash
        for item in second.observations
    }
    first_instance_codes = {
        item.metric_instance_id: item.metric_code for item in first.metric_instances
    }
    second_instance_codes = {
        item.metric_instance_id: item.metric_code for item in second.metric_instances
    }
    first_codes = {
        first_instance_codes[item.observed_metric_instance_id]: (
            item.observed_metric_instance_id
        )
        for item in first.observations
    }
    second_codes = {
        second_instance_codes[item.observed_metric_instance_id]: (
            item.observed_metric_instance_id
        )
        for item in second.observations
    }
    common = sorted(set(first_codes) & set(second_codes))
    assert common
    for code in common:
        assert (
            first_by_definition[first_codes[code]]
            == second_by_definition[second_codes[code]]
        )

    changed_profile = replace(
        alternate_context,
        release_id=_id("release-3"),
        request_hash="f" * 64,
        comparison_context_hash="1" * 64,
    )
    third = materialize_production_p1_release(
        contract=contract,
        batch=batch,
        inputs=inputs,
        context=changed_profile,
        aircraft=alternate_aircraft,
        system_bindings=_systems(contract),
    )
    third_by_definition = {
        item.observed_metric_instance_id: item.comparison_key_hash
        for item in third.observations
    }
    third_instance_codes = {
        item.metric_instance_id: item.metric_code for item in third.metric_instances
    }
    third_codes = {
        third_instance_codes[item.observed_metric_instance_id]: (
            item.observed_metric_instance_id
        )
        for item in third.observations
    }
    assert any(
        first_by_definition[first_codes[code]]
        != third_by_definition[third_codes[code]]
        for code in common
    )
