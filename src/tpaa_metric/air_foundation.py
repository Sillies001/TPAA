"""M2 formal delivery adapter for the three frozen AIR foundation Metrics.

The M1 representative Metric implementation remains the only AIR formula
implementation.  This module binds those immutable M1 results to the shared
CatalogMetricEngine algorithm-id plugin contract and selects the exact M2
P1_FOUNDATION_32 AIR membership for Release qualification.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast
from uuid import uuid5

from tpaa_metric.catalog_engine import (
    CatalogMetricEngineError,
    M2MetricExecutionPlan,
    M2MetricPluginRequest,
    MetricPluginRegistry,
)
from tpaa_metric.context import MetricContext
from tpaa_metric.engine import (
    EVIDENCE_SET_NAMESPACE,
    METRIC_RESULT_NAMESPACE,
    MetricBatch,
    MetricEvidence,
    MetricResult,
    compute_representative_metrics,
)
from tpaa_world import AircraftObservedWorld, WorldEvidenceRef

AIR_M2_FORMAL_CODES = (
    "P1-AIR-001",
    "P1-AIR-002",
    "P1-AIR-003",
)
AIR_M1_IMPLEMENTATION = "tpaa_metric.engine.compute_representative_metrics"


@dataclass(frozen=True)
class M2AirFormalDelivery:
    """Exact three-result M2 projection plus shared-engine input payloads."""

    metric_batch: MetricBatch
    engine_inputs: Mapping[str, Mapping[str, object]]
    m1_batch_logical_hash: str
    logical_hash: str


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def serialize_m1_air_result(
    result: MetricResult,
    *,
    metric_context_id: str,
    world_product_id: str,
) -> dict[str, object]:
    """Return a JSON-safe, self-verifying M1 result projection."""

    return {
        "metric_context_id": metric_context_id,
        "world_product_id": world_product_id,
        "metric_result_id": result.metric_result_id,
        "metric_code": result.metric_code,
        "semantic_id": result.semantic_id,
        "semantic_version": result.semantic_version,
        "algorithm_id": result.algorithm_id,
        "algorithm_version": result.algorithm_version,
        "subject_type": result.subject_type,
        "subject_id": result.subject_id,
        "stage_id": result.stage_id,
        "status": result.status,
        "reason_codes": list(result.reason_codes),
        "unit": result.unit,
        "value_kind": result.value_kind,
        "value_numeric": result.value_numeric,
        "value_structured": (
            None
            if result.value_structured is None
            else result.value_structured.as_dict()
        ),
        "evidence": {
            "evidence_set_id": result.evidence.evidence_set_id,
            "logical_hash": result.evidence.logical_hash,
            "refs": [
                {
                    "ref_class": ref.ref_class,
                    "ref_id": ref.ref_id,
                    "logical_hash": ref.logical_hash,
                }
                for ref in result.evidence.refs
            ],
            "details": [list(item) for item in result.evidence.details],
        },
        "logical_hash": result.logical_hash,
    }


def _string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"M2_AIR_JSON_RESULT_INVALID:{field}")
    return value


def _json_result(value: Mapping[str, object]) -> MetricResult:
    metric_context_id = _string(
        value.get("metric_context_id"),
        field="metric_context_id",
    )
    world_product_id = _string(
        value.get("world_product_id"),
        field="world_product_id",
    )
    evidence_raw = value.get("evidence")
    if not isinstance(evidence_raw, Mapping):
        raise ValueError("M2_AIR_JSON_RESULT_INVALID:evidence")

    refs_raw = evidence_raw.get("refs")
    if not isinstance(refs_raw, list):
        raise ValueError("M2_AIR_JSON_RESULT_INVALID:evidence.refs")
    refs: list[WorldEvidenceRef] = []
    for index, raw in enumerate(refs_raw):
        if not isinstance(raw, Mapping):
            raise ValueError(
                f"M2_AIR_JSON_RESULT_INVALID:evidence.refs[{index}]"
            )
        refs.append(
            WorldEvidenceRef(
                ref_class=_string(
                    raw.get("ref_class"),
                    field=f"evidence.refs[{index}].ref_class",
                ),
                ref_id=_string(
                    raw.get("ref_id"),
                    field=f"evidence.refs[{index}].ref_id",
                ),
                logical_hash=_string(
                    raw.get("logical_hash"),
                    field=f"evidence.refs[{index}].logical_hash",
                ),
            )
        )

    details_raw = evidence_raw.get("details")
    if not isinstance(details_raw, list):
        raise ValueError("M2_AIR_JSON_RESULT_INVALID:evidence.details")
    details: list[tuple[str, str]] = []
    for index, raw in enumerate(details_raw):
        if (
            not isinstance(raw, list)
            or len(raw) != 2
            or not all(isinstance(item, str) for item in raw)
        ):
            raise ValueError(
                f"M2_AIR_JSON_RESULT_INVALID:evidence.details[{index}]"
            )
        details.append((cast(str, raw[0]), cast(str, raw[1])))

    metric_code = _string(value.get("metric_code"), field="metric_code")
    stage_raw = value.get("stage_id")
    if stage_raw is not None and not isinstance(stage_raw, str):
        raise ValueError("M2_AIR_JSON_RESULT_INVALID:stage_id")
    stage_id = stage_raw
    evidence_payload = {
        "metric_code": metric_code,
        "metric_context_id": metric_context_id,
        "world_product_id": world_product_id,
        "stage_id": stage_id,
        "refs": [
            {
                "class": ref.ref_class,
                "id": ref.ref_id,
                "hash": ref.logical_hash,
            }
            for ref in refs
        ],
        "details": [list(item) for item in details],
    }
    evidence_hash = _canonical_hash(evidence_payload)
    if evidence_raw.get("logical_hash") != evidence_hash:
        raise ValueError("M2_AIR_JSON_EVIDENCE_HASH_DRIFT")
    expected_evidence_id = str(
        uuid5(EVIDENCE_SET_NAMESPACE, evidence_hash)
    )
    if evidence_raw.get("evidence_set_id") != expected_evidence_id:
        raise ValueError("M2_AIR_JSON_EVIDENCE_ID_DRIFT")

    semantic_version = value.get("semantic_version")
    if isinstance(semantic_version, bool) or not isinstance(
        semantic_version,
        int,
    ):
        raise ValueError("M2_AIR_JSON_RESULT_INVALID:semantic_version")
    reasons_raw = value.get("reason_codes")
    if not isinstance(reasons_raw, list) or not all(
        isinstance(item, str) for item in reasons_raw
    ):
        raise ValueError("M2_AIR_JSON_RESULT_INVALID:reason_codes")
    status = _string(value.get("status"), field="status")
    value_kind = _string(value.get("value_kind"), field="value_kind")
    numeric_raw = value.get("value_numeric")
    if numeric_raw is not None and (
        isinstance(numeric_raw, bool)
        or not isinstance(numeric_raw, (int, float))
    ):
        raise ValueError("M2_AIR_JSON_RESULT_INVALID:value_numeric")
    if value.get("value_structured") is not None:
        raise ValueError("M2_AIR_JSON_STRUCTURED_VALUE_FORBIDDEN")

    evidence = MetricEvidence(
        evidence_set_id=expected_evidence_id,
        refs=tuple(refs),
        details=tuple(details),
        logical_hash=evidence_hash,
    )
    result_payload = {
        "metric_code": metric_code,
        "semantic_id": _string(value.get("semantic_id"), field="semantic_id"),
        "semantic_version": semantic_version,
        "algorithm_id": _string(
            value.get("algorithm_id"),
            field="algorithm_id",
        ),
        "algorithm_version": _string(
            value.get("algorithm_version"),
            field="algorithm_version",
        ),
        "subject_type": _string(
            value.get("subject_type"),
            field="subject_type",
        ),
        "subject_id": _string(value.get("subject_id"), field="subject_id"),
        "stage_id": stage_id,
        "status": status,
        "reason_codes": list(cast(list[str], reasons_raw)),
        "unit": _string(value.get("unit"), field="unit"),
        "value_kind": value_kind,
        "value": (
            None if numeric_raw is None else float(numeric_raw)
        ),
        "evidence_hash": evidence_hash,
    }
    result_hash = _canonical_hash(result_payload)
    if value.get("logical_hash") != result_hash:
        raise ValueError("M2_AIR_JSON_RESULT_HASH_DRIFT")
    expected_result_id = str(uuid5(METRIC_RESULT_NAMESPACE, result_hash))
    if value.get("metric_result_id") != expected_result_id:
        raise ValueError("M2_AIR_JSON_RESULT_ID_DRIFT")

    return MetricResult(
        metric_result_id=expected_result_id,
        metric_code=metric_code,
        semantic_id=cast(str, result_payload["semantic_id"]),
        semantic_version=semantic_version,
        algorithm_id=cast(str, result_payload["algorithm_id"]),
        algorithm_version=cast(str, result_payload["algorithm_version"]),
        subject_type=cast(str, result_payload["subject_type"]),
        subject_id=cast(str, result_payload["subject_id"]),
        stage_id=stage_id,
        status=status,
        reason_codes=tuple(cast(list[str], reasons_raw)),
        unit=cast(str, result_payload["unit"]),
        value_kind=value_kind,
        value_numeric=(
            None if numeric_raw is None else float(numeric_raw)
        ),
        value_structured=None,
        evidence=evidence,
        logical_hash=result_hash,
    )


def _result_from_request(request: M2MetricPluginRequest) -> MetricResult:
    raw = request.input_payload.get("m1_result")
    if isinstance(raw, MetricResult):
        result = raw
    elif isinstance(raw, Mapping):
        result = _json_result(cast(Mapping[str, object], raw))
    else:
        raise ValueError(
            f"M2_AIR_M1_RESULT_MISSING:{request.definition.metric_code}"
        )
    reuse = request.input_payload.get("implementation_reuse")
    if reuse != AIR_M1_IMPLEMENTATION:
        raise ValueError(
            f"M2_AIR_IMPLEMENTATION_REUSE_DRIFT:{request.definition.metric_code}"
        )
    return result


def _validate_catalog_binding(
    request: M2MetricPluginRequest,
    result: MetricResult,
) -> None:
    definition = request.definition
    if definition.metric_code not in AIR_M2_FORMAL_CODES:
        raise ValueError(f"M2_AIR_DELIVERY_MEMBERSHIP_INVALID:{definition.metric_code}")
    expected = {
        "metric_code": definition.metric_code,
        "semantic_id": definition.semantic_id,
        "semantic_version": definition.semantic_version,
        "algorithm_id": definition.algorithm_id,
        "algorithm_version": definition.algorithm_version,
        "subject_type": definition.subject_type,
        "unit": definition.unit,
        "value_kind": definition.value_kind,
    }
    actual = {
        "metric_code": result.metric_code,
        "semantic_id": result.semantic_id,
        "semantic_version": result.semantic_version,
        "algorithm_id": result.algorithm_id,
        "algorithm_version": result.algorithm_version,
        "subject_type": result.subject_type,
        "unit": result.unit,
        "value_kind": result.value_kind,
    }
    if actual != expected:
        raise ValueError(f"M2_AIR_CATALOG_RESULT_DRIFT:{definition.metric_code}")
    if (
        definition.family != "AIRCRAFT_FLIGHT"
        or definition.subject_type != "AIRCRAFT"
        or definition.value_kind != "NUMERIC"
        or definition.structured_output_schema_id is not None
        or definition.publication_route != "CAPABILITY_OBSERVATION"
        or definition.observation_lane != "AIRCRAFT_CAP_L1_OBSERVATION"
    ):
        raise ValueError(f"M2_AIR_CATALOG_DEFINITION_DRIFT:{definition.metric_code}")
    if result.value_structured is not None:
        raise ValueError(f"M2_AIR_STRUCTURED_VALUE_FORBIDDEN:{definition.metric_code}")


def _air_plugin(request: M2MetricPluginRequest) -> Mapping[str, object]:
    """Project an existing M1 result; no AIR formula is implemented here."""

    result = _result_from_request(request)
    _validate_catalog_binding(request, result)
    return {
        "metric_code": result.metric_code,
        "semantic_id": result.semantic_id,
        "semantic_version": result.semantic_version,
        "algorithm_id": result.algorithm_id,
        "algorithm_version": result.algorithm_version,
        "subject_type": result.subject_type,
        "subject_id": result.subject_id,
        "stage_id": result.stage_id,
        "unit": result.unit,
        "value_kind": result.value_kind,
        "status": result.status,
        "reason_codes": list(result.reason_codes),
        "value_numeric": result.value_numeric,
        "value_structured": None,
        "observation_lane": request.definition.observation_lane,
        "publication_route": request.definition.publication_route,
        "catalog_definition_hash": request.definition.definition_hash,
        "m1_result_logical_hash": result.logical_hash,
        "implementation_reuse": AIR_M1_IMPLEMENTATION,
        "evidence": {
            "evidence_set_id": result.evidence.evidence_set_id,
            "logical_hash": result.evidence.logical_hash,
            "refs": [
                {
                    "ref_class": ref.ref_class,
                    "ref_id": ref.ref_id,
                    "logical_hash": ref.logical_hash,
                }
                for ref in result.evidence.refs
            ],
            "details": [list(item) for item in result.evidence.details],
        },
    }


def register_m2_air_plugins(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
) -> None:
    """Register AIR algorithms in the one shared Catalog plugin registry."""

    allowed_delivery_identities = {
        ("M2", "P1_FOUNDATION_32"),
        ("M2+M3", "P1_FOUNDATION_32+P1_REMAINDER_84"),
    }
    if (plan.delivery_milestone, plan.delivery_batch) not in allowed_delivery_identities:
        raise CatalogMetricEngineError(
            "M2_AIR_DELIVERY_AUTHORITY_DRIFT",
            f"{plan.delivery_milestone}/{plan.delivery_batch}",
        )
    for metric_code in AIR_M2_FORMAL_CODES:
        definition = plan.definition(metric_code)
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m2-air-formal-delivery:{metric_code}:v1",
            plugin=_air_plugin,
        )


def build_m2_air_formal_delivery(
    context: MetricContext,
    world: AircraftObservedWorld,
    *,
    stage_id: str | None = None,
) -> M2AirFormalDelivery:
    """Reuse M1 computation and select only the exact M2 AIR delivery set."""

    m1_batch = compute_representative_metrics(context, world, stage_id=stage_id)
    by_code = {result.metric_code: result for result in m1_batch.results}
    try:
        selected = tuple(by_code[code] for code in AIR_M2_FORMAL_CODES)
    except KeyError as exc:
        raise CatalogMetricEngineError(
            "M2_AIR_M1_RESULT_SET_DRIFT",
            str(exc),
        ) from exc
    selected_hash = _canonical_hash(
        {
            "task_id": "M2-MET-003",
            "delivery_milestone": "M2",
            "delivery_batch": "P1_FOUNDATION_32",
            "metric_context_id": m1_batch.metric_context_id,
            "world_product_id": m1_batch.world_product_id,
            "stage_id": m1_batch.stage_id,
            "metric_codes": AIR_M2_FORMAL_CODES,
            "result_hashes": [result.logical_hash for result in selected],
            "m1_batch_logical_hash": m1_batch.logical_hash,
        }
    )
    selected_batch = MetricBatch(
        metric_context_id=m1_batch.metric_context_id,
        world_product_id=m1_batch.world_product_id,
        stage_id=m1_batch.stage_id,
        results=selected,
        logical_hash=selected_hash,
        staging_status=m1_batch.staging_status,
        database_persistence_executed=m1_batch.database_persistence_executed,
        publication_executed=m1_batch.publication_executed,
    )
    inputs = MappingProxyType(
        {
            result.metric_code: MappingProxyType(
                {
                    "m1_result": cast(object, result),
                    "implementation_reuse": AIR_M1_IMPLEMENTATION,
                }
            )
            for result in selected
        }
    )
    return M2AirFormalDelivery(
        metric_batch=selected_batch,
        engine_inputs=inputs,
        m1_batch_logical_hash=m1_batch.logical_hash,
        logical_hash=selected_hash,
    )
