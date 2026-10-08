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
from typing import Final

from tpaa_metric import (
    M3_RUNTIME_METRIC_COUNT,
    M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
    CatalogMetricEngine,
    M2MetricDefinition,
    M2MetricExecutionBatch,
    M2MetricExecutionPlan,
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
    registry = build_m3_runtime_plugin_registry(contract.plan)
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
