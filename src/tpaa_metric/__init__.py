"""Governed representative Metric computation contracts."""

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
    "CatalogMetricEngine",
    "CatalogMetricEngineError",
    "M2MetricDefinition",
    "M2MetricExecutionBatch",
    "M2MetricExecutionPlan",
    "M2MetricExecutionRecord",
    "M2MetricPluginRequest",
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
    "build_metric_context",
    "compute_representative_metrics",
]
