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
    validate_m2_runtime_output as validate_m2_runtime_output,
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
from .sns_accuracy import (
    M2_SNS_ACCURACY_PLUGINS,
    SNS_ACCURACY_CODES,
    build_m2_sns_accuracy_inputs,
    register_m2_sns_accuracy_plugins,
)
from .sns_detection import (
    M2_SNS_DETECTION_PLUGINS,
    SNS_DETECTION_CODES,
    build_m2_sns_detection_inputs,
    register_m2_sns_detection_plugins,
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
    "M2_SNS_DETECTION_PLUGINS",
    "M2_SNS_ACCURACY_PLUGINS",
    "SNS_ACCURACY_CODES",
    "SNS_DETECTION_CODES",
    "TasMachEnvelope",
    "build_m2_metric_execution_plan",
    "build_m2_air_formal_delivery",
    "build_metric_context",
    "build_m2_sns_detection_inputs",
    "build_m2_sns_accuracy_inputs",
    "compute_representative_metrics",
    "register_m2_air_plugins",
    "register_m2_sns_detection_plugins",
    "register_m2_sns_accuracy_plugins",
]
