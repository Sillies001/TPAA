"""Catalog-owned publication routing for the frozen M2 foundation metrics.

M2-OBS-001 does not recompute metric values. It projects the immutable
observation_lane/publication_route metadata already frozen in the Catalog into
an executable, fail-closed routing plan.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from tpaa_metric import M2MetricDefinition, build_m2_metric_execution_plan


class M2PublicationRoutingError(RuntimeError):
    """Deterministic fail-closed M2 publication-routing error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class M2PublicationRouteContract:
    observation_lane: str
    allowed_subject_types: tuple[str, ...]
    observation_record_type: str | None


M2_PUBLICATION_ROUTE_CONTRACTS: Mapping[str, M2PublicationRouteContract] = (
    MappingProxyType(
        {
            "CAPABILITY_OBSERVATION": M2PublicationRouteContract(
                observation_lane="AIRCRAFT_CAP_L1_OBSERVATION",
                allowed_subject_types=("AIRCRAFT",),
                observation_record_type="CAPABILITY_OBSERVATION",
            ),
            "SYSTEM_PERFORMANCE_OBSERVATION": M2PublicationRouteContract(
                observation_lane="SYSTEM_PERFORMANCE_OBSERVATION",
                allowed_subject_types=("MISSION_SYSTEM_INSTANCE",),
                observation_record_type="SYSTEM_PERFORMANCE_OBSERVATION",
            ),
            "METRIC_INSTANCE_EVIDENCE_ONLY": M2PublicationRouteContract(
                observation_lane="QUALITY_EVIDENCE_ONLY",
                allowed_subject_types=("AIRCRAFT", "TARGET_PAIR"),
                observation_record_type=None,
            ),
        }
    )
)


@dataclass(frozen=True)
class M2MetricPublicationTarget:
    metric_code: str
    semantic_id: str
    semantic_version: int
    definition_hash: str
    subject_type: str
    observation_lane: str
    publication_route: str
    observation_record_type: str | None
    p1_longitudinal_trend_eligibility: bool
    persist_metric_instance: bool = True
    persist_evidence_set: bool = True


@dataclass(frozen=True)
class M2PublicationRoutingPlan:
    catalog_id: str
    catalog_version: str
    catalog_hash: str
    metric_execution_plan_hash: str
    targets: tuple[M2MetricPublicationTarget, ...]
    logical_hash: str

    @property
    def metric_codes(self) -> tuple[str, ...]:
        return tuple(target.metric_code for target in self.targets)

    def target(self, metric_code: str) -> M2MetricPublicationTarget:
        for target in self.targets:
            if target.metric_code == metric_code:
                return target
        raise M2PublicationRoutingError(
            "M2_PUBLICATION_TARGET_MISSING",
            metric_code,
        )


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def route_m2_metric_definition(
    definition: M2MetricDefinition,
) -> M2MetricPublicationTarget:
    """Resolve one Catalog definition to its frozen publication sink."""

    contract = M2_PUBLICATION_ROUTE_CONTRACTS.get(definition.publication_route)
    if contract is None:
        raise M2PublicationRoutingError(
            "M2_PUBLICATION_ROUTE_UNKNOWN",
            f"{definition.metric_code}:{definition.publication_route}",
        )
    if definition.observation_lane != contract.observation_lane:
        raise M2PublicationRoutingError(
            "M2_PUBLICATION_LANE_MISMATCH",
            (
                f"{definition.metric_code}:{definition.observation_lane}"
                f"!={contract.observation_lane}"
            ),
        )
    if definition.subject_type not in contract.allowed_subject_types:
        raise M2PublicationRoutingError(
            "M2_PUBLICATION_SUBJECT_MISMATCH",
            (
                f"{definition.metric_code}:{definition.subject_type}"
                f" not in {contract.allowed_subject_types!r}"
            ),
        )
    if (
        definition.publication_route == "METRIC_INSTANCE_EVIDENCE_ONLY"
        and definition.p1_longitudinal_trend_eligibility
    ):
        raise M2PublicationRoutingError(
            "M2_PUBLICATION_QUALITY_TREND_FORBIDDEN",
            definition.metric_code,
        )

    return M2MetricPublicationTarget(
        metric_code=definition.metric_code,
        semantic_id=definition.semantic_id,
        semantic_version=definition.semantic_version,
        definition_hash=definition.definition_hash,
        subject_type=definition.subject_type,
        observation_lane=definition.observation_lane,
        publication_route=definition.publication_route,
        observation_record_type=contract.observation_record_type,
        p1_longitudinal_trend_eligibility=(
            definition.p1_longitudinal_trend_eligibility
        ),
    )


def build_m2_publication_routing_plan(
    authority_root: Path,
) -> M2PublicationRoutingPlan:
    """Compile exact M2 P1_FOUNDATION_32 publication routing from authority."""

    metric_plan = build_m2_metric_execution_plan(authority_root)
    targets = tuple(
        route_m2_metric_definition(definition)
        for definition in metric_plan.definitions
    )
    if len(targets) != 32 or len({item.metric_code for item in targets}) != 32:
        raise M2PublicationRoutingError(
            "M2_PUBLICATION_FOUNDATION_MEMBERSHIP_INVALID",
            repr(tuple(item.metric_code for item in targets)),
        )
    projection = [
        {
            "metric_code": target.metric_code,
            "semantic_id": target.semantic_id,
            "semantic_version": target.semantic_version,
            "definition_hash": target.definition_hash,
            "subject_type": target.subject_type,
            "observation_lane": target.observation_lane,
            "publication_route": target.publication_route,
            "observation_record_type": target.observation_record_type,
            "p1_longitudinal_trend_eligibility": (
                target.p1_longitudinal_trend_eligibility
            ),
            "persist_metric_instance": target.persist_metric_instance,
            "persist_evidence_set": target.persist_evidence_set,
        }
        for target in targets
    ]
    logical_hash = _canonical_hash(
        {
            "catalog_id": metric_plan.catalog_id,
            "catalog_version": metric_plan.catalog_version,
            "catalog_hash": metric_plan.catalog_sha256,
            "metric_execution_plan_hash": metric_plan.logical_hash,
            "targets": projection,
        }
    )
    return M2PublicationRoutingPlan(
        catalog_id=metric_plan.catalog_id,
        catalog_version=metric_plan.catalog_version,
        catalog_hash=metric_plan.catalog_sha256,
        metric_execution_plan_hash=metric_plan.logical_hash,
        targets=targets,
        logical_hash=logical_hash,
    )
