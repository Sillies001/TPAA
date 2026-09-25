from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from tpaa_context import resolve_evaluation_context
from tpaa_metric import (
    AIR_M1_IMPLEMENTATION,
    AIR_M2_FORMAL_CODES,
    CatalogMetricEngine,
    MetricPluginRegistry,
    build_m2_air_formal_delivery,
    build_m2_metric_execution_plan,
    build_metric_context,
    register_m2_air_plugins,
)
from tpaa_observation import (
    AircraftPublicationIdentity,
    build_session_release,
    compare_replay,
)
from tpaa_world import project_minimal_p1_world

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
RELEASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3"


def _runtime(fixture_id: str, *, stage_id: str | None = None):
    bundle = FIXTURES / fixture_id
    world = project_minimal_p1_world(
        bundle,
        authority_root=AUTHORITY,
        release_id=RELEASE_ID,
    )
    context = build_metric_context(bundle, authority_root=AUTHORITY, world=world)
    delivery = build_m2_air_formal_delivery(context, world, stage_id=stage_id)
    plan = build_m2_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    register_m2_air_plugins(plan, registry)
    engine = CatalogMetricEngine(plan, registry)
    return bundle, world, context, delivery, plan, registry, engine


def _engine_outputs(delivery, plan, registry):
    from tpaa_metric.catalog_engine import M2MetricPluginRequest
    from tpaa_metric.operators import M2_OPERATOR_IMPLEMENTATIONS

    outputs = {}
    for code in AIR_M2_FORMAL_CODES:
        definition = plan.definition(code)
        _plugin_id, plugin = registry.resolve(definition.algorithm_id)
        outputs[code] = dict(
            plugin(
                M2MetricPluginRequest(
                    definition=definition,
                    input_payload=delivery.engine_inputs[code],
                    upstream_result_hashes=(),
                    operators={
                        operator_id: M2_OPERATOR_IMPLEMENTATIONS[operator_id]
                        for operator_id in definition.operator_bindings
                    },
                )
            )
        )
    return outputs


def test_air_delivery_uses_shared_catalog_engine_and_exact_m2_membership() -> None:
    _, _, _, delivery, plan, registry, engine = _runtime("BF_M1_NOMINAL_V1")

    assert tuple(result.metric_code for result in delivery.metric_batch.results) == (
        AIR_M2_FORMAL_CODES
    )
    assert "P1-AIR-004" not in delivery.engine_inputs
    assert "P1-AIR-007" not in delivery.engine_inputs
    assert {plan.definition(code).algorithm_id for code in AIR_M2_FORMAL_CODES} == set(
        registry.plugin_ids
    )
    assert set(registry.plugin_ids.values()) == {
        f"m2-air-formal-delivery:{code}:v1" for code in AIR_M2_FORMAL_CODES
    }

    first = engine.execute(delivery.engine_inputs, metric_codes=AIR_M2_FORMAL_CODES)
    replay = engine.execute(delivery.engine_inputs, metric_codes=AIR_M2_FORMAL_CODES)
    assert first == replay
    assert first.metric_codes == AIR_M2_FORMAL_CODES
    assert all(
        output["implementation_reuse"] == AIR_M1_IMPLEMENTATION
        for output in _engine_outputs(delivery, plan, registry).values()
    )


def test_air_catalog_bindings_and_nominal_golden_are_exact() -> None:
    _, _, _, delivery, plan, registry, _ = _runtime("BF_M1_NOMINAL_V1")
    outputs = _engine_outputs(delivery, plan, registry)

    expected = {
        "P1-AIR-001": (
            "tpaa.p1.air.max_abs_body_roll_rate",
            "alg.tpaa.p1.air.max_abs_body_roll_rate",
            "1.0.1",
            "rad/s",
        ),
        "P1-AIR-002": (
            "tpaa.p1.air.max_nz",
            "alg.tpaa.p1.air.max_nz",
            "1.0.1",
            "g",
        ),
        "P1-AIR-003": (
            "tpaa.p1.air.true_heading_rate",
            "alg.tpaa.p1.air.true_heading_rate",
            "1.0.0",
            "rad/s",
        ),
    }
    for code, (semantic_id, algorithm_id, algorithm_version, unit) in expected.items():
        definition = plan.definition(code)
        assert (
            definition.semantic_id,
            definition.algorithm_id,
            definition.algorithm_version,
            definition.unit,
        ) == (semantic_id, algorithm_id, algorithm_version, unit)
        assert definition.subject_type == "AIRCRAFT"
        assert definition.value_kind == "NUMERIC"
        assert definition.structured_output_schema_id is None
        assert definition.observation_lane == "AIRCRAFT_CAP_L1_OBSERVATION"
        assert definition.publication_route == "CAPABILITY_OBSERVATION"
        assert outputs[code]["catalog_definition_hash"] == definition.definition_hash

    assert outputs["P1-AIR-001"]["value_numeric"] == pytest.approx(0.6)
    assert outputs["P1-AIR-002"]["value_numeric"] == pytest.approx(2.5)
    air002_details = dict(outputs["P1-AIR-002"]["evidence"]["details"])
    assert air002_details["diagnostic_min_nz_g"] == "1.0"
    assert outputs["P1-AIR-003"]["value_numeric"] == pytest.approx(0.1)


def test_air_golden_negatives_reuse_m1_behavior_without_formula_copy() -> None:
    _, _, _, wrap, wrap_plan, wrap_registry, _ = _runtime("BF_M1_ANGLE_WRAP_V1")
    wrap_output = _engine_outputs(wrap, wrap_plan, wrap_registry)["P1-AIR-003"]
    assert wrap_output["value_numeric"] == pytest.approx(0.03490658503988659)
    assert dict(wrap_output["evidence"]["details"])["operator"] == "DERIVATIVE_LLS_V1"

    _, _, _, gap, gap_plan, gap_registry, _ = _runtime("BF_M1_GAP_V1")
    gap_outputs = _engine_outputs(gap, gap_plan, gap_registry)
    assert gap_outputs["P1-AIR-001"]["status"] == "INSUFFICIENT_DATA"
    assert gap_outputs["P1-AIR-001"]["reason_codes"] == ["MAX_GAP_EXCEEDED"]
    assert gap_outputs["P1-AIR-003"]["value_numeric"] == pytest.approx(0.1)

    _, world, context, _, plan, registry, _ = _runtime("BF_M1_NOMINAL_V1")
    rows = list(world.canonical_rows)
    rows[6] = replace(rows[6], nz_g=99.0, quality_mask=1)
    invalid_peak = build_m2_air_formal_delivery(
        context,
        replace(world, canonical_rows=tuple(rows)),
    )
    output = _engine_outputs(invalid_peak, plan, registry)["P1-AIR-002"]
    assert output["value_numeric"] == pytest.approx(2.5)


def test_air_stage_boundary_and_short_derivative_fail_closed() -> None:
    bundle = FIXTURES / "BF_M1_STAGE_BOUNDARY_V1"
    world = project_minimal_p1_world(
        bundle,
        authority_root=AUTHORITY,
        release_id=RELEASE_ID,
    )
    context = build_metric_context(bundle, authority_root=AUTHORITY, world=world)
    plan = build_m2_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    register_m2_air_plugins(plan, registry)

    setup = build_m2_air_formal_delivery(context, world, stage_id=world.stages[0].stage_id)
    execution = build_m2_air_formal_delivery(
        context,
        world,
        stage_id=world.stages[1].stage_id,
    )
    setup_outputs = _engine_outputs(setup, plan, registry)
    execution_outputs = _engine_outputs(execution, plan, registry)
    assert setup_outputs["P1-AIR-001"]["value_numeric"] == pytest.approx(0.5)
    assert execution_outputs["P1-AIR-001"]["value_numeric"] == pytest.approx(9.0)
    assert setup_outputs["P1-AIR-003"]["status"] == "INSUFFICIENT_DATA"
    assert setup_outputs["P1-AIR-003"]["reason_codes"] == ["DERIVATIVE_UNAVAILABLE"]


def test_air_release_is_exact_immutable_three_metric_snapshot_and_replays() -> None:
    bundle, world, context, delivery, plan, _, _ = _runtime("BF_M1_NOMINAL_V1")
    resolved = resolve_evaluation_context(bundle, authority_root=AUTHORITY)
    release = build_session_release(
        release_id=RELEASE_ID,
        request_hash=hashlib.sha256(b"M2-MET-003").hexdigest(),
        release_no=1,
        parent_release_id=None,
        context=context,
        context_version=resolved.context_version,
        context_projection={
            "context_id": resolved.context_id,
            "session_id": resolved.session_id,
            "context_version": resolved.context_version,
            "revision_no": resolved.revision_no,
            "rule_set_version": resolved.rule_set_version,
            "metric_profile_version": resolved.metric_profile_version,
            "status": resolved.status,
        },
        world=world,
        batch=delivery.metric_batch,
        identity=AircraftPublicationIdentity(
            aircraft_id=world.aircraft_id,
            aircraft_model_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1",
            aircraft_instance_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2",
            subject_entity_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb3",
            capability_dimension="AIRCRAFT_FLIGHT",
            capability_type="BASIC_FLIGHT",
        ),
    )

    assert tuple(item.metric_code for item in release.definitions) == AIR_M2_FORMAL_CODES
    assert tuple(item.metric_code for item in release.metric_instances) == AIR_M2_FORMAL_CODES
    assert tuple(item.metric_code for item in release.observations) == AIR_M2_FORMAL_CODES
    assert all(len(item.definition_hash) == 64 for item in release.definitions)
    assert all(len(item.logical_hash) == 64 for item in release.evidence_sets)
    assert all(
        item.publication_route == plan.definition(item.metric_code).publication_route
        and item.observation_lane == plan.definition(item.metric_code).observation_lane
        for item in release.definitions
    )
    comparison = compare_replay(
        release,
        context=context,
        context_version=resolved.context_version,
        world=world,
        batch=delivery.metric_batch,
    )
    assert comparison.exact_logical_products_equal is True
    assert context.latest_fallback_used is False
    with pytest.raises(FrozenInstanceError):
        release.status = "MUTATED"  # type: ignore[misc]
