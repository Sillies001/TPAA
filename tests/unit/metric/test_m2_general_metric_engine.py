from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

import pytest

from tpaa_metric import (
    CatalogMetricEngine,
    CatalogMetricEngineError,
    M2MetricPluginRequest,
    MetricPluginRegistry,
    build_m2_metric_execution_plan,
)
from tpaa_metric.operators import (
    TimedValue,
    arithmetic_mean,
    circular_mean,
    linear_interpolate,
    rms,
    wrap_pi,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def _probe(request: M2MetricPluginRequest) -> dict[str, object]:
    return {
        "metric_code": request.definition.metric_code,
        "algorithm_id": request.definition.algorithm_id,
        "operators": sorted(request.operators),
        "input": dict(request.input_payload),
        "upstream": list(request.upstream_result_hashes),
    }


def _registry() -> MetricPluginRegistry:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    for algorithm_id in dict.fromkeys(
        definition.algorithm_id for definition in plan.definitions
    ):
        registry.register(
            algorithm_id,
            plugin_id="contract-probe-v1",
            plugin=_probe,
        )
    return registry


def _inputs() -> dict[str, dict[str, object]]:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    return {
        definition.metric_code: {
            "fixture": "M2-MET-001-CONTRACT",
            "catalog_index": definition.catalog_index,
        }
        for definition in plan.definitions
    }


def test_m2_plan_is_exact_catalog_foundation_batch() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)

    assert plan.catalog_id == "P1_METRIC_CATALOG"
    assert plan.db_schema_version == "1.6.0"
    assert plan.delivery_milestone == "M2"
    assert plan.delivery_batch == "P1_FOUNDATION_32"
    assert len(plan.catalog_metric_codes) == 32
    assert len(set(plan.catalog_metric_codes)) == 32
    assert set(plan.metric_codes) == set(plan.catalog_metric_codes)
    assert Counter(item.family for item in plan.definitions) == {
        "REFERENCE_TRUTH": 3,
        "TIME_ALIGNMENT": 5,
        "AIRCRAFT_FLIGHT": 3,
        "SENSOR_DETECTION": 4,
        "SENSOR_ACCURACY": 17,
    }
    assert plan.required_operator_ids == (
        "CIRCULAR_MEAN_V1",
        "DERIVATIVE_LLS_V1",
        "LINEAR_INTERPOLATION_V1",
        "MEAN_V1",
        "MEDIAN_V1",
        "QUANTILE_HF7_V1",
        "RMS_V1",
        "WRAP_PI_V1",
    )
    assert len(plan.logical_hash) == 64
    assert len(plan.catalog_sha256) == 64


def test_m2_plan_is_dependency_ordered_and_sns_stays_radar_only() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    positions = {code: index for index, code in enumerate(plan.metric_codes)}

    for definition in plan.definitions:
        for dependency in definition.metric_dependencies:
            assert positions[dependency] < positions[definition.metric_code]

    sns = [item for item in plan.definitions if item.metric_code.startswith("P1-SNS-")]
    assert len(sns) == 21
    assert all(item.subject_type == "MISSION_SYSTEM_INSTANCE" for item in sns)
    assert all(item.applicability.key == "P1-SNS-*" for item in sns)
    assert all(item.applicability.applicability_mode == "SYSTEM_TYPE_EXACT" for item in sns)
    assert all(item.applicability.allowed_system_types == ("RADAR",) for item in sns)


def test_one_engine_dispatches_all_families_by_algorithm_id_replay_stably() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    engine = CatalogMetricEngine(plan, _registry())
    inputs = _inputs()

    first = engine.execute(inputs)
    second = engine.execute(inputs)

    assert first == second
    assert first.dispatch_key == "algorithm_id"
    assert len(first.records) == 32
    assert first.metric_codes == plan.metric_codes
    assert len({record.plugin_id for record in first.records}) == 1
    assert {record.plugin_id for record in first.records} == {"contract-probe-v1"}
    assert len(first.logical_hash) == 64

    seen: dict[str, str] = {}
    for record in first.records:
        definition = plan.definition(record.metric_code)
        assert record.algorithm_id == definition.algorithm_id
        assert record.operator_bindings == definition.operator_bindings
        assert record.upstream_result_hashes == tuple(
            (dependency, seen[dependency])
            for dependency in definition.metric_dependencies
        )
        seen[record.metric_code] = record.logical_hash


def test_subset_execution_closes_metric_dependencies_and_missing_plugin_fails_closed() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    engine = CatalogMetricEngine(plan, _registry())
    batch = engine.execute(_inputs(), metric_codes=("P1-SNS-005",))

    assert batch.metric_codes[-1] == "P1-SNS-005"
    assert "P1-QA-001" in batch.metric_codes
    assert "P1-QA-002" in batch.metric_codes
    assert "P1-QA-005" in batch.metric_codes

    empty_engine = CatalogMetricEngine(plan, MetricPluginRegistry())
    with pytest.raises(CatalogMetricEngineError) as caught:
        empty_engine.execute(_inputs(), metric_codes=("P1-AIR-001",))
    assert caught.value.code == "M2_METRIC_PLUGIN_MISSING"


def test_plugin_registry_rejects_duplicate_algorithm_registration() -> None:
    registry = MetricPluginRegistry()
    registry.register(
        "alg.example",
        plugin_id="contract-probe-v1",
        plugin=_probe,
    )
    with pytest.raises(CatalogMetricEngineError) as caught:
        registry.register(
            "alg.example",
            plugin_id="contract-probe-v1",
            plugin=_probe,
        )
    assert caught.value.code == "M2_METRIC_PLUGIN_DUPLICATE"


def test_governed_m2_operator_primitives_are_deterministic_and_fail_closed() -> None:
    assert arithmetic_mean((1.0, 2.0, 3.0)) == 2.0
    assert rms((3.0, 4.0)) == pytest.approx(math.sqrt(12.5))
    assert wrap_pi(math.pi) == pytest.approx(-math.pi)
    assert wrap_pi(-math.pi) == pytest.approx(-math.pi)
    assert circular_mean((math.radians(179.0), math.radians(-179.0))) == pytest.approx(
        -math.pi,
        abs=1e-12,
    )

    values = (
        TimedValue(0, 0.0),
        TimedValue(1_000_000, 10.0),
        TimedValue(5_000_000, 50.0),
    )
    assert linear_interpolate(values, 500_000, max_gap_us=2_000_000) == 5.0
    with pytest.raises(ValueError, match="OUTSIDE_VALID_PIECE"):
        linear_interpolate(values, 3_000_000, max_gap_us=2_000_000)
