"""Governed representative Metric computation contracts."""

from .air_foundation import (
    AIR_M1_IMPLEMENTATION,
    AIR_M2_FORMAL_CODES,
    M2AirFormalDelivery,
    build_m2_air_formal_delivery,
    register_m2_air_plugins,
)
from .catalog_engine import (
    CatalogMetricEngine,
    CatalogMetricEngineError,
    M2MetricDefinition,
    M2MetricExecutionBatch,
    M2MetricExecutionPlan,
    M2MetricExecutionRecord,
    M2MetricPluginRequest,
    MetricPluginRegistry,
    build_m2_metric_execution_plan,
)
from .context import MetricAuthority, MetricContext, MetricContextError, build_metric_context
from .engine import (
    MetricBatch,
    MetricComputationError,
    MetricEvidence,
    MetricResult,
    MetricStagingArea,
    TasMachEnvelope,
    compute_representative_metrics,
)

__all__ = [
    "AIR_M1_IMPLEMENTATION",
    "AIR_M2_FORMAL_CODES",
    "CatalogMetricEngine",
    "CatalogMetricEngineError",
    "M2MetricDefinition",
    "M2MetricExecutionBatch",
    "M2MetricExecutionPlan",
    "M2MetricExecutionRecord",
    "M2MetricPluginRequest",
    "M2AirFormalDelivery",
    "MetricPluginRegistry",
    "MetricAuthority",
    "MetricBatch",
    "MetricComputationError",
    "MetricContext",
    "MetricContextError",
    "MetricEvidence",
    "MetricResult",
    "MetricStagingArea",
    "TasMachEnvelope",
    "build_m2_metric_execution_plan",
    "build_m2_air_formal_delivery",
    "build_metric_context",
    "compute_representative_metrics",
    "register_m2_air_plugins",
]
