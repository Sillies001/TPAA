from __future__ import annotations

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
    inputs = {
        definition.metric_code: _positive_input(definition)
        for definition in contract.plan.definitions
    }
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
