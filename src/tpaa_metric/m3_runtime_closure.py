"""M3 integrated runtime closure for the exact 116-metric P1 Catalog.

This module assembles the already-qualified foundation and M3 family plugins in
one shared Catalog registry. It intentionally does not introduce a second
Metric engine or family-specific dispatch layer.
"""

from __future__ import annotations

from tpaa_metric.air_foundation import register_m2_air_plugins
from tpaa_metric.catalog_engine import (
    CatalogMetricEngineError,
    M2MetricExecutionPlan,
    MetricPluginRegistry,
)
from tpaa_metric.m3_air import register_m3_air_plugins
from tpaa_metric.m3_datalink import register_m3_datalink_plugins
from tpaa_metric.m3_esm import register_m3_esm_plugins
from tpaa_metric.m3_fusion import register_m3_fusion_plugins
from tpaa_metric.m3_fusion_operators import M3_FUSION_OPERATOR_IMPLEMENTATIONS
from tpaa_metric.m3_identification import register_m3_identification_plugins
from tpaa_metric.m3_passive import register_m3_passive_plugins
from tpaa_metric.m3_track import register_m3_track_plugins
from tpaa_metric.qa_foundation import register_m2_qa_plugins
from tpaa_metric.sns_accuracy import register_m2_sns_accuracy_plugins
from tpaa_metric.sns_detection import register_m2_sns_detection_plugins

M3_RUNTIME_METRIC_COUNT = 116
M3_RUNTIME_OPERATOR_IMPLEMENTATIONS = M3_FUSION_OPERATOR_IMPLEMENTATIONS


def build_m3_runtime_plugin_registry(
    plan: M2MetricExecutionPlan,
) -> MetricPluginRegistry:
    """Build the exact integrated 116-plugin registry on the shared engine."""

    if len(plan.definitions) != M3_RUNTIME_METRIC_COUNT:
        raise CatalogMetricEngineError(
            "M3_RUNTIME_DEFINITION_COUNT_DRIFT",
            f"{len(plan.definitions)}->{M3_RUNTIME_METRIC_COUNT}",
        )

    registry = MetricPluginRegistry()
    register_m2_qa_plugins(plan, registry)
    register_m2_air_plugins(plan, registry)
    register_m2_sns_detection_plugins(plan, registry)
    register_m2_sns_accuracy_plugins(plan, registry)
    register_m3_air_plugins(plan, registry)
    register_m3_track_plugins(plan, registry)
    register_m3_identification_plugins(plan, registry)
    register_m3_passive_plugins(plan, registry)
    register_m3_esm_plugins(plan, registry)
    register_m3_datalink_plugins(plan, registry)
    register_m3_fusion_plugins(plan, registry)

    unresolved: list[str] = []
    for definition in plan.definitions:
        try:
            registry.resolve(
                definition.algorithm_id,
                definition.algorithm_version,
            )
        except CatalogMetricEngineError:
            unresolved.append(definition.metric_code)
    if unresolved:
        raise CatalogMetricEngineError(
            "M3_RUNTIME_PLUGIN_COVERAGE_INCOMPLETE",
            repr(tuple(unresolved)),
        )

    if len(registry.plugin_identity_manifest) != M3_RUNTIME_METRIC_COUNT:
        raise CatalogMetricEngineError(
            "M3_RUNTIME_PLUGIN_IDENTITY_COUNT_DRIFT",
            repr(len(registry.plugin_identity_manifest)),
        )
    return registry
