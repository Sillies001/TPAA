"""M3 integrated publication routing for the exact 116-metric P1 Catalog.

M3-OBS-001 extends the already-qualified M2 publication-routing contract to the
integrated M2+M3 Catalog plan. Metric values are not recomputed here: the
Catalog-owned observation_lane/publication_route metadata is projected into one
deterministic, fail-closed routing plan while the qualified M2 foundation
targets remain byte-for-byte logical equals.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from tpaa_metric import build_m3_metric_execution_plan

from .m2_publication import (
    M2MetricPublicationTarget,
    M2PublicationRoutingError,
    build_m2_publication_routing_plan,
    route_m2_metric_definition,
)

M3_PUBLICATION_METRIC_COUNT = 116
M3_PUBLICATION_ROUTE_COUNTS = {
    "CAPABILITY_OBSERVATION": 39,
    "METRIC_INSTANCE_EVIDENCE_ONLY": 5,
    "SYSTEM_PERFORMANCE_OBSERVATION": 72,
}
M3_PUBLICATION_LANE_COUNTS = {
    "AIRCRAFT_CAP_L1_OBSERVATION": 39,
    "QUALITY_EVIDENCE_ONLY": 5,
    "SYSTEM_PERFORMANCE_OBSERVATION": 72,
}


@dataclass(frozen=True)
class M3PublicationRoutingPlan:
    catalog_id: str
    catalog_version: str
    catalog_hash: str
    metric_execution_plan_hash: str
    foundation_publication_routing_plan_hash: str
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
            "M3_PUBLICATION_TARGET_MISSING",
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


def _target_projection(target: M2MetricPublicationTarget) -> dict[str, object]:
    return {
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


def build_m3_publication_routing_plan(
    authority_root: Path,
) -> M3PublicationRoutingPlan:
    """Compile exact integrated 116-metric publication routing from authority."""

    metric_plan = build_m3_metric_execution_plan(authority_root)
    targets = tuple(
        route_m2_metric_definition(definition)
        for definition in metric_plan.definitions
    )
    if (
        len(targets) != M3_PUBLICATION_METRIC_COUNT
        or len({target.metric_code for target in targets})
        != M3_PUBLICATION_METRIC_COUNT
        or tuple(target.metric_code for target in targets)
        != metric_plan.metric_codes
    ):
        raise M2PublicationRoutingError(
            "M3_PUBLICATION_MEMBERSHIP_INVALID",
            repr(tuple(target.metric_code for target in targets)),
        )

    route_counts = dict(
        Counter(target.publication_route for target in targets)
    )
    lane_counts = dict(
        Counter(target.observation_lane for target in targets)
    )
    if route_counts != M3_PUBLICATION_ROUTE_COUNTS:
        raise M2PublicationRoutingError(
            "M3_PUBLICATION_ROUTE_COUNTS_DRIFT",
            repr(dict(sorted(route_counts.items()))),
        )
    if lane_counts != M3_PUBLICATION_LANE_COUNTS:
        raise M2PublicationRoutingError(
            "M3_PUBLICATION_LANE_COUNTS_DRIFT",
            repr(dict(sorted(lane_counts.items()))),
        )

    foundation = build_m2_publication_routing_plan(authority_root)
    target_by_code = {target.metric_code: target for target in targets}
    foundation_preserved = all(
        target_by_code[foundation_target.metric_code] == foundation_target
        for foundation_target in foundation.targets
    )
    if not foundation_preserved:
        raise M2PublicationRoutingError(
            "M3_PUBLICATION_FOUNDATION_ROUTE_DRIFT",
            foundation.logical_hash,
        )

    projection = [_target_projection(target) for target in targets]
    logical_hash = _canonical_hash(
        {
            "catalog_id": metric_plan.catalog_id,
            "catalog_version": metric_plan.catalog_version,
            "catalog_hash": metric_plan.catalog_sha256,
            "metric_execution_plan_hash": metric_plan.logical_hash,
            "foundation_publication_routing_plan_hash": foundation.logical_hash,
            "targets": projection,
        }
    )
    return M3PublicationRoutingPlan(
        catalog_id=metric_plan.catalog_id,
        catalog_version=metric_plan.catalog_version,
        catalog_hash=metric_plan.catalog_sha256,
        metric_execution_plan_hash=metric_plan.logical_hash,
        foundation_publication_routing_plan_hash=foundation.logical_hash,
        targets=targets,
        logical_hash=logical_hash,
    )
