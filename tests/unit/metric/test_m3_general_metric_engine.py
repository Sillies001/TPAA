from __future__ import annotations

import json
from pathlib import Path

import pytest

from tpaa_metric import (
    M3_CONTRACT_OPERATOR_IMPLEMENTATIONS,
    M3_DEFERRED_OPERATOR_IDS,
    CatalogMetricEngine,
    CatalogMetricEngineError,
    M2MetricPluginRequest,
    MetricPluginRegistry,
    build_m2_metric_execution_plan,
    build_m3_metric_execution_plan,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
CATALOG = AUTHORITY / "P1_METRIC_CATALOG.json"


def _catalog_partition() -> tuple[set[str], set[str]]:
    raw = json.loads(CATALOG.read_text(encoding="utf-8"))
    metrics = raw["metrics"]
    foundation = {
        item["metric_code"]
        for item in metrics
        if item["delivery_milestone"] == "M2"
        and item["delivery_batch"] == "P1_FOUNDATION_32"
    }
    remainder = {
        item["metric_code"]
        for item in metrics
        if item["delivery_milestone"] == "M3"
        and item["delivery_batch"] == "P1_REMAINDER_84"
    }
    return foundation, remainder


def _probe(request: M2MetricPluginRequest) -> dict[str, object]:
    return {
        "metric_code": request.definition.metric_code,
        "definition_hash": request.definition.definition_hash,
        "operator_ids": sorted(request.operators),
        "input_token": request.input_payload["input_token"],
        "upstream_result_hashes": list(request.upstream_result_hashes),
    }


def test_m3_general_plan_is_exact_32_plus_84_with_foundation_unchanged() -> None:
    foundation_plan = build_m2_metric_execution_plan(AUTHORITY)
    integrated_plan = build_m3_metric_execution_plan(AUTHORITY)
    foundation_codes, remainder_codes = _catalog_partition()

    assert len(foundation_codes) == 32
    assert len(remainder_codes) == 84
    assert foundation_codes.isdisjoint(remainder_codes)
    assert set(integrated_plan.metric_codes) == foundation_codes | remainder_codes
    assert len(integrated_plan.metric_codes) == 116
    assert set(foundation_plan.metric_codes) == foundation_codes

    integrated_by_code = {
        definition.metric_code: definition
        for definition in integrated_plan.definitions
    }
    for definition in foundation_plan.definitions:
        integrated = integrated_by_code[definition.metric_code]
        assert integrated.definition_hash == definition.definition_hash
        assert integrated.semantic_id == definition.semantic_id
        assert integrated.algorithm_id == definition.algorithm_id
        assert integrated.algorithm_version == definition.algorithm_version


def test_m3_general_engine_contract_probe_executes_all_116() -> None:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    identities = {
        (definition.algorithm_id, definition.algorithm_version)
        for definition in plan.definitions
    }
    for algorithm_id, algorithm_version in sorted(identities):
        registry.register(
            algorithm_id,
            algorithm_version=algorithm_version,
            plugin_id="m3-met-001-contract-probe-v1",
            plugin=_probe,
        )

    inputs = {
        definition.metric_code: {
            "input_token": f"M3-MET-001::{definition.metric_code}",
        }
        for definition in plan.definitions
    }
    engine = CatalogMetricEngine(
        plan,
        registry,
        operator_implementations=M3_CONTRACT_OPERATOR_IMPLEMENTATIONS,
    )
    first = engine.execute(inputs, validate_runtime_contract=False)
    replay = engine.execute(inputs, validate_runtime_contract=False)

    assert len(first.records) == 116
    assert first.metric_codes == plan.metric_codes
    assert first == replay
    assert len(first.logical_hash) == 64


def test_m3_deferred_operator_contract_is_fail_closed() -> None:
    assert set(M3_DEFERRED_OPERATOR_IDS) <= set(M3_CONTRACT_OPERATOR_IMPLEMENTATIONS)
    deferred = M3_CONTRACT_OPERATOR_IMPLEMENTATIONS[M3_DEFERRED_OPERATOR_IDS[0]]
    with pytest.raises(CatalogMetricEngineError) as captured:
        deferred()
    assert (
        captured.value.code
        == "M3_METRIC_OPERATOR_BUSINESS_SEMANTICS_DEFERRED"
    )
