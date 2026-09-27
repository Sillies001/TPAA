"""M3-MET-001 general-engine expansion contract.

This module extends the existing CatalogMetricEngine plan to the exact integrated
P1 Catalog set: qualified P1_FOUNDATION_32 plus M3 P1_REMAINDER_84. It does not
implement family business Metric semantics; M3-MET-002..008 own those algorithms.

M3-only operators are bound as deterministic fail-closed sentinels here so the
general engine can compile and dispatch the frozen 116-definition contract
without pretending those business primitives are implemented early.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from types import MappingProxyType

from tpaa_metric.catalog_engine import (
    CatalogMetricEngineError,
    M2_DELIVERY_BATCH,
    M2_DELIVERY_MILESTONE,
    M2MetricExecutionPlan,
    build_catalog_metric_execution_plan,
)
from tpaa_metric.operators import M2_OPERATOR_IMPLEMENTATIONS

M3_DELIVERY_MILESTONE = "M3"
M3_DELIVERY_BATCH = "P1_REMAINDER_84"
M3_REMAINDER_COUNT = 84
M3_INTEGRATED_COUNT = 116
M3_INTEGRATED_DELIVERY_MILESTONE = "M2+M3"
M3_INTEGRATED_DELIVERY_BATCH = "P1_FOUNDATION_32+P1_REMAINDER_84"

M3_EXPECTED_FAMILY_COUNTS: Mapping[str, int] = MappingProxyType(
    {
        "REFERENCE_TRUTH": 3,
        "TIME_ALIGNMENT": 5,
        "AIRCRAFT_FLIGHT": 20,
        "AIRCRAFT_ENERGY": 8,
        "AIRCRAFT_CONTROL_RESPONSE": 4,
        "AIRCRAFT_HANDLING": 4,
        "AIRCRAFT_PERSISTENCE": 3,
        "SENSOR_DETECTION": 4,
        "SENSOR_ACCURACY": 17,
        "TRACK_PERFORMANCE": 7,
        "ASSOCIATION_IDENTIFICATION": 12,
        "PASSIVE_SENSOR": 7,
        "RWR_ESM": 6,
        "DATALINK": 8,
        "SENSOR_FUSION": 8,
    }
)

M3_DEFERRED_OPERATOR_IDS = (
    "BANDPASS_BUTTERWORTH4_ZP_V1",
    "CV_PROPAGATION_V1",
    "GEODESIC_PAIR_RATE_V1",
    "MAD_V1",
    "ROLLING_MEDIAN_V1",
    "THEIL_SEN_GAIN_V1",
)


def _deferred_operator(operator_id: str) -> Callable[..., object]:
    def deferred(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise CatalogMetricEngineError(
            "M3_METRIC_OPERATOR_BUSINESS_SEMANTICS_DEFERRED",
            operator_id,
        )

    return deferred


_operator_implementations: dict[str, Callable[..., object]] = dict(
    M2_OPERATOR_IMPLEMENTATIONS
)
for _operator_id in M3_DEFERRED_OPERATOR_IDS:
    _operator_implementations[_operator_id] = _deferred_operator(_operator_id)

M3_CONTRACT_OPERATOR_IMPLEMENTATIONS: Mapping[
    str,
    Callable[..., object],
] = MappingProxyType(_operator_implementations)


def build_m3_metric_execution_plan(
    authority_root: Path,
) -> M2MetricExecutionPlan:
    """Compile the exact integrated 116-definition P1 Catalog plan."""

    return build_catalog_metric_execution_plan(
        authority_root,
        delivery_scope=(
            (M2_DELIVERY_MILESTONE, M2_DELIVERY_BATCH),
            (M3_DELIVERY_MILESTONE, M3_DELIVERY_BATCH),
        ),
        expected_count=M3_INTEGRATED_COUNT,
        expected_family_counts=M3_EXPECTED_FAMILY_COUNTS,
        plan_delivery_milestone=M3_INTEGRATED_DELIVERY_MILESTONE,
        plan_delivery_batch=M3_INTEGRATED_DELIVERY_BATCH,
        operator_implementations=M3_CONTRACT_OPERATOR_IMPLEMENTATIONS,
    )
