from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

import pytest

from tpaa_metric.catalog_engine import (
    CatalogMetricEngine,
    CatalogMetricEngineError,
    M2MetricExecutionPlan,
    M2MetricPluginRequest,
    MetricPluginRegistry,
    build_m2_metric_execution_plan,
)
from tpaa_metric.operators import M2_OPERATOR_IMPLEMENTATIONS
from tpaa_metric.qa_foundation import (
    QA_AUTHORITY_BLOCKED_CODES,
    QA_FOUNDATION_CODES,
    build_m2_qa_inputs,
    register_m2_qa_plugins,
)
from tpaa_world import (
    project_m2_radar_sensor_world,
    project_m2_reference_time_world,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
FIXTURES = ROOT / "tests" / "fixtures" / "m2"
SAFE_CODES = ("P1-QA-003", "P1-QA-004", "P1-QA-005", "P1-QA-007", "P1-QA-008")


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _runtime() -> tuple[
    M2MetricExecutionPlan,
    MetricPluginRegistry,
    dict[str, Mapping[str, object]],
    CatalogMetricEngine,
]:
    reference_time = project_m2_reference_time_world(
        FIXTURES / "RT_M2_NOMINAL_V1",
        FIXTURES / "TA_M2_NOMINAL_V1",
        authority_root=AUTHORITY,
        release_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1",
    )
    radar = project_m2_radar_sensor_world(
        FIXTURES / "MSI_M2_RADAR_V1",
        FIXTURES / "MA_M2_NOMINAL_V1",
        authority_root=AUTHORITY,
        release_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2",
    )
    plan = build_m2_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    register_m2_qa_plugins(plan, registry)
    inputs = build_m2_qa_inputs(reference_time, radar)
    return plan, registry, inputs, CatalogMetricEngine(plan, registry)


def _direct(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
    inputs: Mapping[str, Mapping[str, object]],
    metric_code: str,
) -> dict[str, object]:
    definition = plan.definition(metric_code)
    _plugin_id, plugin = registry.resolve(definition.algorithm_id)
    operators = MappingProxyType(
        {
            operator_id: M2_OPERATOR_IMPLEMENTATIONS[operator_id]
            for operator_id in definition.operator_bindings
        }
    )
    return dict(
        plugin(
            M2MetricPluginRequest(
                definition=definition,
                input_payload=inputs[metric_code],
                upstream_result_hashes=(),
                operators=operators,
            )
        )
    )


def _instance(output: Mapping[str, object], index: int = 0) -> dict[str, object]:
    instances = output["instances"]
    assert isinstance(instances, list)
    item = instances[index]
    assert isinstance(item, dict)
    assert all(isinstance(key, str) for key in item)
    return item


def test_m2_qa_registry_is_catalog_driven_and_safe_subset_replays() -> None:
    plan, registry, inputs, engine = _runtime()
    qa_codes = tuple(code for code in plan.metric_codes if code.startswith("P1-QA-"))
    assert len(qa_codes) == 8
    assert set(qa_codes) == set(QA_FOUNDATION_CODES)
    assert QA_AUTHORITY_BLOCKED_CODES == ("P1-QA-001", "P1-QA-002")

    expected_algorithms = {plan.definition(code).algorithm_id for code in QA_FOUNDATION_CODES}
    assert set(registry.plugin_ids) == expected_algorithms

    first = engine.execute(inputs, metric_codes=SAFE_CODES)
    replayed = engine.execute(inputs, metric_codes=SAFE_CODES)
    assert first == replayed
    assert first.metric_codes == SAFE_CODES

    direct = {code: _direct(plan, registry, inputs, code) for code in SAFE_CODES}
    for record in first.records:
        assert record.plugin_output_hash == _canonical_hash(direct[record.metric_code])


@pytest.mark.parametrize("metric_code", ["P1-QA-001", "P1-QA-002", "P1-QA-006"])
def test_m2_qa_authority_and_dependency_gaps_fail_closed(metric_code: str) -> None:
    _plan, _registry, inputs, engine = _runtime()
    with pytest.raises(CatalogMetricEngineError) as caught:
        engine.execute(inputs, metric_codes=(metric_code,))
    assert caught.value.code == "M2_QA_AUTHORITY_GAP"


def test_m2_qa_frozen_fixture_golden_values() -> None:
    plan, registry, inputs, _engine = _runtime()
    qa003 = _direct(plan, registry, inputs, "P1-QA-003")
    qa004 = _direct(plan, registry, inputs, "P1-QA-004")
    qa005 = _direct(plan, registry, inputs, "P1-QA-005")
    qa006 = _direct(plan, registry, inputs, "P1-QA-006")
    qa007 = _direct(plan, registry, inputs, "P1-QA-007")
    qa008 = _direct(plan, registry, inputs, "P1-QA-008")

    assert [_instance(qa003, index)["value_numeric"] for index in range(2)] == [
        2000.0,
        2000.0,
    ]

    qa004_instance = _instance(qa004)
    assert qa004_instance["value_numeric"] == 40000.0
    qa004_diagnostics = qa004_instance["diagnostics"]
    assert isinstance(qa004_diagnostics, dict)
    assert qa004_diagnostics["p95_us"] == 49000.0

    qa005_instance = _instance(qa005)
    assert qa005_instance["value_numeric"] == 50000.0
    qa005_diagnostics = qa005_instance["diagnostics"]
    assert isinstance(qa005_diagnostics, dict)
    assert qa005_diagnostics["max_us"] == 50000.0

    expected_qa006 = 5.0 / math.sqrt(14.0)
    for index in range(3):
        structured = _instance(qa006, index)["value_structured"]
        assert isinstance(structured, dict)
        assert structured["normalized_residual_status"] == "VALID"
        assert structured["normalized_residual"] == pytest.approx(expected_qa006)

    assert _instance(qa007)["value_numeric"] == pytest.approx(
        math.sqrt((500.0 / math.sqrt(3.0)) ** 2 + 100.0**2)
    )
    assert _instance(qa008)["value_numeric"] == pytest.approx(
        math.sqrt((800.0 / math.sqrt(3.0)) ** 2 + 200.0**2)
    )
