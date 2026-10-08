"""ED-2.0 production P1 Catalog execution contract.

This module is the production bridge to the already-qualified shared 116-metric
Catalog engine. It does not manufacture missing metric inputs and it does not
silently narrow execution to a representative subset.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from tpaa_metric import (
    M3_RUNTIME_METRIC_COUNT,
    M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
    CatalogMetricEngine,
    M2MetricDefinition,
    M2MetricExecutionBatch,
    M2MetricExecutionPlan,
    M2MetricPlugin,
    M2MetricPluginRequest,
    MetricPluginRegistry,
    build_m3_metric_execution_plan,
    build_m3_runtime_plugin_registry,
)
from tpaa_observation import (
    M3_PUBLICATION_LANE_COUNTS,
    M3_PUBLICATION_METRIC_COUNT,
    M3_PUBLICATION_ROUTE_COUNTS,
    M3PublicationRoutingPlan,
    build_m3_publication_routing_plan,
)

PRODUCTION_P1_CATALOG_METRIC_COUNT: Final = 116
PRODUCTION_P1_SUBJECT_COUNTS: Final = {
    "AIRCRAFT": 40,
    "MISSION_SYSTEM_INSTANCE": 72,
    "TARGET_PAIR": 4,
}
PRODUCTION_P1_REQUIRED_WORLD_KINDS: Final = {
    "AIRCRAFT": ("TRUTH",),
    "MISSION_SYSTEM_INSTANCE": ("TRUTH", "MACHINE"),
    "TARGET_PAIR": ("TRUTH", "MACHINE"),
}


def production_p1_required_world_kinds(
    definition: M2MetricDefinition,
) -> tuple[str, ...]:
    """Return stable Definition-level World kinds, never Release instance IDs."""

    try:
        return PRODUCTION_P1_REQUIRED_WORLD_KINDS[definition.subject_type]
    except KeyError as exc:
        raise ProductionP1CatalogError(
            "ED2_P1_REQUIRED_WORLD_SUBJECT_UNSUPPORTED",
            definition.subject_type,
        ) from exc


class ProductionP1CatalogError(RuntimeError):
    """Fail-closed production Catalog orchestration error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class ProductionP1CatalogContract:
    """Exact frozen identities required by production P1 execution."""

    plan: M2MetricExecutionPlan
    routing: M3PublicationRoutingPlan
    plugin_identity_manifest: tuple[tuple[str, str, str], ...]
    subject_counts: tuple[tuple[str, int], ...]
    lane_counts: tuple[tuple[str, int], ...]
    route_counts: tuple[tuple[str, int], ...]

    @property
    def metric_codes(self) -> tuple[str, ...]:
        return self.plan.metric_codes


def _sorted_counts(values: list[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(Counter(values).items()))


def build_production_p1_catalog_contract(
    authority_root: Path,
) -> ProductionP1CatalogContract:
    """Bind production P1 to the qualified exact 116-definition shared engine."""

    plan = build_m3_metric_execution_plan(authority_root)
    routing = build_m3_publication_routing_plan(authority_root)
    registry = build_m3_runtime_plugin_registry(plan)

    if (
        len(plan.definitions) != PRODUCTION_P1_CATALOG_METRIC_COUNT
        or M3_RUNTIME_METRIC_COUNT != PRODUCTION_P1_CATALOG_METRIC_COUNT
    ):
        raise ProductionP1CatalogError(
            "ED2_P1_CATALOG_COUNT_DRIFT",
            str(len(plan.definitions)),
        )
    if M3_PUBLICATION_METRIC_COUNT != PRODUCTION_P1_CATALOG_METRIC_COUNT:
        raise ProductionP1CatalogError(
            "ED2_P1_PUBLICATION_COUNT_DRIFT",
            str(M3_PUBLICATION_METRIC_COUNT),
        )
    if routing.metric_codes != plan.metric_codes:
        raise ProductionP1CatalogError(
            "ED2_P1_ROUTING_MEMBERSHIP_DRIFT",
            "routing metric codes do not match execution plan",
        )
    if len(registry.plugin_identity_manifest) != PRODUCTION_P1_CATALOG_METRIC_COUNT:
        raise ProductionP1CatalogError(
            "ED2_P1_PLUGIN_COVERAGE_INCOMPLETE",
            str(len(registry.plugin_identity_manifest)),
        )

    subject_counts = _sorted_counts(
        [definition.subject_type for definition in plan.definitions]
    )
    if dict(subject_counts) != PRODUCTION_P1_SUBJECT_COUNTS:
        raise ProductionP1CatalogError(
            "ED2_P1_SUBJECT_MEMBERSHIP_DRIFT",
            repr(dict(subject_counts)),
        )

    lane_counts = _sorted_counts(
        [definition.observation_lane for definition in plan.definitions]
    )
    if dict(lane_counts) != M3_PUBLICATION_LANE_COUNTS:
        raise ProductionP1CatalogError(
            "ED2_P1_LANE_MEMBERSHIP_DRIFT",
            repr(dict(lane_counts)),
        )

    route_counts = _sorted_counts(
        [definition.publication_route for definition in plan.definitions]
    )
    if dict(route_counts) != M3_PUBLICATION_ROUTE_COUNTS:
        raise ProductionP1CatalogError(
            "ED2_P1_ROUTE_MEMBERSHIP_DRIFT",
            repr(dict(route_counts)),
        )

    return ProductionP1CatalogContract(
        plan=plan,
        routing=routing,
        plugin_identity_manifest=registry.plugin_identity_manifest,
        subject_counts=subject_counts,
        lane_counts=lane_counts,
        route_counts=route_counts,
    )


def _source_sufficiency(
    request: M2MetricPluginRequest,
) -> Mapping[str, object] | None:
    raw = request.input_payload.get("_source_sufficiency")
    if raw is None:
        return None
    if not isinstance(raw, Mapping) or not all(
        isinstance(key, str) for key in raw
    ):
        raise ProductionP1CatalogError(
            "ED2_P1_SOURCE_SUFFICIENCY_INVALID",
            request.definition.metric_code,
        )
    return cast(Mapping[str, object], raw)


def _source_gate_runtime_applicable(
    request: M2MetricPluginRequest,
) -> bool:
    definition = request.definition
    applicability = definition.applicability
    mode = applicability.applicability_mode
    if mode in {"SUBJECT_TYPE", "QUALITY_FOUNDATION"}:
        return True
    if mode in {"SYSTEM_TYPE_EXACT", "SYSTEM_TYPE_SET"}:
        system_type = request.input_payload.get("system_type")
        if (
            not isinstance(system_type, str)
            or system_type not in definition.allowed_mission_system_types
        ):
            raise ProductionP1CatalogError(
                "ED2_P1_SOURCE_GATE_APPLICABILITY_INVALID",
                f"{definition.metric_code}:{system_type!r}",
            )
        return system_type in applicability.allowed_system_types
    if mode == "PRODUCT_CAPABILITY":
        required = applicability.required_product_semantics
        raw_products = request.input_payload.get("product_semantics")
        if (
            required is None
            or not isinstance(raw_products, (list, tuple))
            or not all(
                isinstance(item, str) and item
                for item in raw_products
            )
            or len(raw_products) != len(set(raw_products))
        ):
            raise ProductionP1CatalogError(
                "ED2_P1_SOURCE_GATE_APPLICABILITY_INVALID",
                f"{definition.metric_code}:{raw_products!r}",
            )
        return required in raw_products
    raise ProductionP1CatalogError(
        "ED2_P1_SOURCE_GATE_APPLICABILITY_UNSUPPORTED",
        f"{definition.metric_code}:{mode}",
    )


def _source_gate_output(
    request: M2MetricPluginRequest,
) -> Mapping[str, object] | None:
    sufficiency = _source_sufficiency(request)
    if sufficiency is None:
        return None
    status = sufficiency.get("status")
    if status == "READY":
        return None
    if status != "INSUFFICIENT_DATA":
        raise ProductionP1CatalogError(
            "ED2_P1_SOURCE_SUFFICIENCY_STATUS_INVALID",
            f"{request.definition.metric_code}:{status!r}",
        )
    reasons = sufficiency.get("reason_codes")
    if (
        not isinstance(reasons, list)
        or not reasons
        or not all(isinstance(item, str) and item for item in reasons)
    ):
        raise ProductionP1CatalogError(
            "ED2_P1_SOURCE_SUFFICIENCY_REASON_INVALID",
            request.definition.metric_code,
        )
    if "INSUFFICIENT_DATA" not in request.definition.allowed_result_statuses:
        raise ProductionP1CatalogError(
            "ED2_P1_SOURCE_INSUFFICIENT_STATUS_UNSUPPORTED",
            request.definition.metric_code,
        )
    if not _source_gate_runtime_applicable(request):
        return {
            "metric_code": request.definition.metric_code,
            "subject_type": request.definition.subject_type,
            "observation_lane": request.definition.observation_lane,
            "publication_route": request.definition.publication_route,
            "applicable": False,
            "instances": [],
        }
    return {
        "metric_code": request.definition.metric_code,
        "subject_type": request.definition.subject_type,
        "observation_lane": request.definition.observation_lane,
        "publication_route": request.definition.publication_route,
        "applicable": True,
        "instances": [
            {
                "status": "INSUFFICIENT_DATA",
                "reason_codes": list(reasons),
                "value_kind": request.definition.value_kind,
                "value_numeric": None,
                "value_structured": None,
                "evidence": {
                    "source_sufficiency": dict(sufficiency),
                },
            }
        ],
    }


def _source_gated_plugin(
    plugin: M2MetricPlugin,
) -> M2MetricPlugin:
    def execute(request: M2MetricPluginRequest) -> Mapping[str, object]:
        gated = _source_gate_output(request)
        if gated is not None:
            return gated
        return plugin(request)

    return execute


def _build_production_p1_plugin_registry(
    contract: ProductionP1CatalogContract,
) -> MetricPluginRegistry:
    base = build_m3_runtime_plugin_registry(contract.plan)
    production = MetricPluginRegistry()
    for definition in contract.plan.definitions:
        plugin_id, plugin = base.resolve(
            definition.algorithm_id,
            definition.algorithm_version,
        )
        production.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=plugin_id,
            plugin=_source_gated_plugin(plugin),
        )
    if production.plugin_identity_manifest != contract.plugin_identity_manifest:
        raise ProductionP1CatalogError(
            "ED2_P1_PLUGIN_IDENTITY_DRIFT",
            repr(production.plugin_identity_manifest),
        )
    return production


def validate_production_p1_input_membership(
    contract: ProductionP1CatalogContract,
    inputs: Mapping[str, Mapping[str, object]],
) -> None:
    """Require exact 116 input slots before production dispatch.

    Applicability remains owned by the Catalog plugins. Missing subject/source
    prerequisites must be represented by governed input products that cause the
    applicable plugin to return an allowed non-valid state; dropping the Metric
    from the production request is forbidden.
    """

    expected = set(contract.metric_codes)
    observed = set(inputs)
    missing = tuple(sorted(expected - observed))
    extra = tuple(sorted(observed - expected))
    if missing or extra or len(inputs) != PRODUCTION_P1_CATALOG_METRIC_COUNT:
        raise ProductionP1CatalogError(
            "ED2_P1_INPUT_MEMBERSHIP_INCOMPLETE",
            f"missing={missing!r};extra={extra!r};count={len(inputs)}",
        )


def execute_production_p1_catalog(
    authority_root: Path,
    inputs: Mapping[str, Mapping[str, object]],
) -> tuple[ProductionP1CatalogContract, M2MetricExecutionBatch]:
    """Execute the complete production Catalog with the qualified business plugins."""

    contract = build_production_p1_catalog_contract(authority_root)
    validate_production_p1_input_membership(contract, inputs)
    registry = _build_production_p1_plugin_registry(contract)
    batch = CatalogMetricEngine(
        contract.plan,
        registry,
        operator_implementations=M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
    ).execute(inputs)
    if batch.metric_codes != contract.metric_codes:
        raise ProductionP1CatalogError(
            "ED2_P1_EXECUTION_MEMBERSHIP_DRIFT",
            repr(batch.metric_codes),
        )
    return contract, batch
