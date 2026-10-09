"""PRCB C2 governed production domain work executed inside a fresh spawn worker."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast
from uuid import UUID, uuid5

from tpaa_application.p2_persistence import P2DurableComputeInput
from tpaa_application.p4_p5_compute_input import P5DurableComputeInput
from tpaa_assessment import (
    P4AssessmentRevision,
    P4SubjectContext,
    P4SubjectSource,
    P5AssessmentRevision,
    build_p4_assessment_revision,
    build_p4_subject_context,
    build_p5_aggregation,
    build_p5_assessment_revision,
    execute_p2_attribution,
    materialize_p4_human_machine_evidence,
    materialize_p5_team_mission_evidence,
)
from tpaa_assessment.ed2_profile import (
    ED2AssessmentProfileResult,
    evaluate_ed2_training_assessment,
)
from tpaa_capability.p3_model import (
    P3CapabilityModelBuild,
    P3CapabilitySurfaceBuild,
    P3ModelExecutionProfile,
    P3TrainingDatasetSnapshot,
    build_capability_surface,
    execute_capability_model,
    materialize_training_dataset,
)
from tpaa_capability.p3_twin import (
    P3AircraftTwinRevision,
    P3CapabilityEstimate,
    P3TwinComponentBinding,
    evaluate_twin_capability_estimate,
    publish_aircraft_twin_revision,
)
from tpaa_capability.p6_counterfactual import execute_p6_counterfactual
from tpaa_capability.p6_forecast import (
    P6CapabilityTrainingRow,
    P6ForecastExecutionProfile,
    P6ManagedModelObject,
    P6ModelBuild,
    P6ModelRevision,
    execute_p6_forecast,
    execute_p6_model_training,
)
from tpaa_capability.p6_input import (
    P6ContextRef,
    P6CounterfactualRequestBinding,
    P6FactualSourceRevision,
    P6ForecastRequestBinding,
    P6InputSnapshot,
    P6P3ModelRef,
    build_p6_counterfactual_request_binding,
    build_p6_forecast_request_binding,
    build_p6_input_snapshot,
)
from tpaa_context import M8RoleModelBinding, P3ClaimEnvelope
from tpaa_episode import (
    ProductionStageError,
    ProductionStageProjection,
    project_production_basic_stages,
)
from tpaa_generated.dto import EvaluationContextDTO
from tpaa_ingest import SourceFamily
from tpaa_ingest.canonical_flight_channels import CanonicalFlightRow
from tpaa_ingest.production_flight_json import validate_production_flight_document
from tpaa_longitudinal import (
    P3AdjustedEstimateInput,
    P3AuthorityPolicy,
    P3LifecycleSegment,
    P3ManagedObject,
    P3ModelValidationSnapshot,
    build_p3_lifecycle_segment,
    build_p3_validation_snapshot,
)
from tpaa_metric import CatalogMetricEngineError
from tpaa_observation import allocate_session_release_id
from tpaa_platform.worker import WorkerPayload, WorkerResult
from tpaa_storage.canonical_rows import FieldKind
from tpaa_storage.hashing import canonical_request_hash
from tpaa_storage.product_identity import product_object_ref_id
from tpaa_storage.publication_bundle import (
    CorePublicationBundle,
    CoreWorldProductRecord,
    CoreWorldRelationRecord,
)
from tpaa_world import (
    M8EvidenceRef,
    M8WorldFactRef,
    P4InteractionScopeSnapshot,
    P5CompositionSnapshot,
    P5ParticipantBinding,
    build_p4_interaction_scope_snapshot,
    build_p5_composition_snapshot,
)

from .production_p1_catalog import (
    ProductionP1CatalogError,
    build_production_p1_catalog_contract,
    execute_production_p1_catalog,
    production_p1_required_world_kinds,
)
from .production_p1_materialization import (
    ProductionP1AircraftBinding,
    ProductionP1MaterializationError,
    ProductionP1ReleaseContext,
    materialize_production_p1_release,
)
from .production_p1_request import (
    ProductionP1RequestError,
    ProductionP1SourceSelection,
    parse_production_p1_request,
    select_production_p1_sources,
)
from .production_p1_world import (
    PRODUCTION_P1_WORLD_SOURCE_FAMILIES,
    ProductionP1WorldPolicyError,
    validate_production_p1_world_authority,
)

PRODUCTION_P1_WORKER_SCHEMA = "TPAA_ED2_B1_P1_WORKER_PRODUCT_V1"
P1_BUILD_COMMAND = "BUILD_P1_RELEASE"
P2_ATTRIBUTION_COMMAND = "P2_ATTRIBUTION"
P3_BUILD_COMMAND = "P3_BUILD_PRODUCTS"
P3_ESTIMATE_COMMAND = "P3_ESTIMATE"
P4_ASSESSMENT_COMMAND = "P4_ASSESSMENT"
P5_ASSESSMENT_COMMAND = "P5_ASSESSMENT"
P6_BUILD_COMMAND = "P6_BUILD_PRODUCTS"
P6_FORECAST_COMMAND = "P6_FORECAST"
P6_COUNTERFACTUAL_COMMAND = "P6_COUNTERFACTUAL"
_DATASET_NAMESPACE = UUID("daf518fe-13aa-4d23-9130-b42ac188e4cf")
_EPISODE_NAMESPACE = UUID("2f54fd82-6212-4750-a2cf-9469c6ac65ec")
_WORLD_NAMESPACE = UUID("e119738b-1527-4998-b67a-50730604ea28")
_RELATION_NAMESPACE = UUID("4c1ea412-4f78-4547-b510-6cff4631b2ee")


class ProductionWorkerError(RuntimeError):
    """Fail-closed production worker input or domain-composition error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True)
class ProductionPrerequisiteRow:
    """One explicit DB 1.9 prerequisite row decided from governed production input."""

    table: str
    values: dict[str, object]
    field_kinds: dict[str, FieldKind]


@dataclass(frozen=True)
class ProductionP1WorkerProduct:
    """Serializable worker-decided P1 product; parent only persists this result."""

    schema: str
    release: CorePublicationBundle
    canonical_rows: tuple[dict[str, object], ...]
    dataset_id: str
    canonical_logical_hash: str
    world_product_id: str
    world_logical_hash: str
    metric_batch_hash: str
    source_sha256: str
    prerequisites: tuple[ProductionPrerequisiteRow, ...]


@dataclass(frozen=True)
class ProductionP2AttributionWorkerInput:
    """Exact durable P2 inputs plus canonical Job payload for worker verification."""

    job_payload: dict[str, object]
    compute_input: P2DurableComputeInput
    p2_release_id: str
    execution_time_utc: str
    supersedes_estimate_id: str | None


@dataclass(frozen=True)
class ProductionP3BuildWorkerInput:
    """Exact P2 history used to construct governed P3 products in the worker."""

    job_payload: dict[str, object]
    estimates: tuple[P3AdjustedEstimateInput, ...]
    segment_snapshot_id: str
    validation_snapshot_id: str
    training_dataset_snapshot_id: str
    configuration_snapshot_id: str
    as_of_utc: str
    training_created_at_utc: str
    trained_at_utc: str
    surface_created_at_utc: str
    twin_valid_from_utc: str
    twin_published_at_utc: str
    estimate_created_at_utc: str


@dataclass(frozen=True)
class ProductionP3BuildWorkerProduct:
    """P3 model/surface/twin and in-domain estimates decided by the worker."""

    segment: P3LifecycleSegment
    validation: P3ModelValidationSnapshot
    training: P3TrainingDatasetSnapshot
    model_build: P3CapabilityModelBuild
    surface_build: P3CapabilitySurfaceBuild
    model_object: P3ManagedObject
    surface_object: P3ManagedObject
    component: P3TwinComponentBinding
    twin: P3AircraftTwinRevision
    estimates: tuple[P3CapabilityEstimate, ...]


@dataclass(frozen=True)
class ProductionP3EstimateWorkerInput:
    """Exact durable P3 inputs plus canonical Job payload for worker verification."""

    job_payload: dict[str, object]
    twin: P3AircraftTwinRevision
    components: tuple[P3TwinComponentBinding, ...]
    capability_type: str
    condition_point: dict[str, object]
    as_of_time_utc: str
    created_at_utc: str


@dataclass(frozen=True)
class ProductionP4BuildWorkerInput:
    """Exact durable inputs for worker-side P4 subject/scope construction."""

    job_payload: dict[str, object]
    source: P4SubjectSource
    role_model: M8RoleModelBinding
    fact_refs: tuple[M8WorldFactRef, ...]
    machine_evidence: tuple[M8EvidenceRef, ...]
    p3_estimate: P3CapabilityEstimate | None
    confidence: float
    created_at_utc: str


@dataclass(frozen=True)
class ProductionP4AssessmentWorkerProduct:
    subject: P4SubjectContext
    scope: P4InteractionScopeSnapshot
    revision: P4AssessmentRevision
    assessment_result: ED2AssessmentProfileResult


@dataclass(frozen=True)
class ProductionP4AssessmentWorkerInput:
    """Frozen P4 scope plus exact upstream claim authority."""

    job_payload: dict[str, object]
    subject: P4SubjectContext
    scope: P4InteractionScopeSnapshot
    p3_estimate: P3CapabilityEstimate | None
    confidence: float
    created_at_utc: str


@dataclass(frozen=True)
class ProductionP5BuildWorkerInput:
    """Exact P4 members for worker-side P5 composition construction."""

    job_payload: dict[str, object]
    session_id: str
    mission_episode_id: str
    team_id: str | None
    p4_revisions: tuple[P4AssessmentRevision, ...]
    world_snapshot_refs: tuple[str, ...]
    scenario_context_artifact_id: str | None
    role_model_context_artifact_id: str
    assessment_spec_id: str
    assessment_spec_version: str
    as_of_utc: str
    objective_result_refs: tuple[str, ...]
    evidence_set_id: str
    confidence: float
    created_at_utc: str


@dataclass(frozen=True)
class ProductionP5AssessmentWorkerProduct:
    composition: P5CompositionSnapshot
    compute_input: P5DurableComputeInput
    revision: P5AssessmentRevision
    assessment_result: ED2AssessmentProfileResult


@dataclass(frozen=True)
class ProductionP5AssessmentWorkerInput:
    """Frozen P5 composition and exact member revisions."""

    job_payload: dict[str, object]
    compute_input: P5DurableComputeInput
    confidence: float
    created_at_utc: str


@dataclass(frozen=True)
class ProductionP6BuildWorkerInput:
    """Exact approved P4/P3 history and factual inputs for P6 construction."""

    job_payload: dict[str, object]
    training_rows: tuple[P6CapabilityTrainingRow, ...]
    factual_sources: tuple[P6FactualSourceRevision, ...]
    p3_model_refs: tuple[P6P3ModelRef, ...]
    scenario_context_refs: tuple[P6ContextRef, ...]
    target_scope: str
    subject_or_composition_ref: str
    forecast_origin_utc: str
    as_of_utc: str
    trained_at_utc: str
    sealed_at_utc: str
    forecast_spec: dict[str, object] | None
    counterfactual_spec: dict[str, object] | None


@dataclass(frozen=True)
class ProductionP6BuildWorkerProduct:
    model_build: P6ModelBuild
    managed_object: P6ManagedModelObject
    input_snapshot: P6InputSnapshot
    forecast_request: P6ForecastRequestBinding | None
    counterfactual_request: P6CounterfactualRequestBinding | None


@dataclass(frozen=True)
class ProductionP6ForecastWorkerInput:
    """Exact durable P6 inputs plus canonical Job payload for worker verification."""

    job_payload: dict[str, object]
    request: P6ForecastRequestBinding
    input_snapshot: P6InputSnapshot
    model_build: P6ModelBuild
    managed_object: P6ManagedModelObject
    published_at_utc: str


@dataclass(frozen=True)
class ProductionP6CounterfactualWorkerInput:
    """Exact durable P6 counterfactual inputs for governed worker execution."""

    job_payload: dict[str, object]
    request: P6CounterfactualRequestBinding
    input_snapshot: P6InputSnapshot
    models: tuple[P6ModelRevision, ...]
    created_at_utc: str


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field)
    return cast(dict[str, object], value)


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field)
    return value


def _uuid(value: object, *, field: str) -> str:
    text_value = _text(value, field=field)
    try:
        parsed = UUID(text_value)
    except ValueError as exc:
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field) from exc
    if parsed.int == 0 or str(parsed) != text_value:
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field)
    return text_value


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field)
    return value


def _number(value: object, *, field: str) -> float:
    if isinstance(value, bool):
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field)
    if isinstance(value, str):
        if not value or value.strip() != value:
            raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field)
        try:
            decimal = Decimal(value)
        except InvalidOperation as exc:
            raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field) from exc
        if not decimal.is_finite():
            raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field)
        result = float(decimal)
    elif isinstance(value, (int, float)):
        result = float(value)
    else:
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field)
    if not math.isfinite(result):
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field)
    return result


def _optional_number(
    row: dict[str, object],
    *,
    name: str,
) -> float | None:
    value = row.get(name)
    return None if value is None else _number(value, field=name)


def _session_type(value: object) -> str:
    session_type = _text(value, field="source_import.session_type")
    if session_type not in {"LIVE", "SIM", "LVC"}:
        raise ProductionWorkerError(
            "PRCB_C2_SESSION_TYPE_INVALID",
            session_type,
        )
    return session_type


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _world_source_state(
    source_selection: ProductionP1SourceSelection,
    *,
    required: frozenset[SourceFamily],
) -> tuple[str, float, tuple[str, ...], str | None]:
    actual = frozenset(
        family
        for family in required
        if source_selection.refs_by_family.get(family)
    )
    missing = tuple(
        sorted(
            required - actual,
            key=lambda item: item.value,
        )
    )
    if not actual:
        status = "MISSING"
    elif missing:
        status = "PARTIAL"
    else:
        status = "READY"
    coverage = len(actual) / len(required)
    reasons = tuple(
        f"ED2_SOURCE_FAMILY_MISSING_{family.value}"
        for family in missing
    )
    signature = (
        None
        if not actual
        else _hash(
            [
                {
                    "source_family": family.value,
                    "artifact_sha256": ref.artifact_sha256,
                }
                for family in sorted(actual, key=lambda item: item.value)
                for ref in source_selection.refs_by_family[family]
            ]
        )
    )
    return status, coverage, reasons, signature


def _scenario_stage_payload(
    source_selection: ProductionP1SourceSelection,
) -> tuple[Mapping[str, object] | None, str | None]:
    scenario_refs = source_selection.refs_by_family.get(
        SourceFamily.SCENARIO,
        (),
    )
    if not scenario_refs:
        return None, None
    candidates = tuple(
        ref
        for ref in scenario_refs
        if "stage_projection" in ref.projection_payload
    )
    if len(candidates) != 1:
        raise ProductionWorkerError(
            "ED2_STAGE_SOURCE_PROJECTION_CARDINALITY",
            str(len(candidates)),
        )
    return candidates[0].projection_payload, candidates[0].artifact_sha256


def _stage_relations(
    projection: ProductionStageProjection,
    *,
    episode_id: str,
    source_authority_signature: str | None,
) -> tuple[CoreWorldRelationRecord, ...]:
    if projection.status != "READY":
        return ()
    result: list[CoreWorldRelationRecord] = []
    for left, right in zip(
        projection.stages,
        projection.stages[1:],
        strict=False,
    ):
        relation_id = str(
            uuid5(
                _RELATION_NAMESPACE,
                json.dumps(
                    {
                        "episode_id": episode_id,
                        "relation_type": "PRECEDES",
                        "subject_ref": left.stage_id,
                        "object_ref": right.stage_id,
                        "method_version": projection.projector_version,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                    allow_nan=False,
                ),
            )
        )
        result.append(
            CoreWorldRelationRecord(
                relation_id=relation_id,
                episode_id=episode_id,
                stage_id=left.stage_id,
                relation_type="PRECEDES",
                subject_ref=left.stage_id,
                object_ref=right.stage_id,
                subject_series_id=None,
                object_series_id=None,
                cross_series=False,
                start_session_time_us=None,
                end_session_time_us=None,
                properties={
                    "stage_profile_id": projection.stage_profile_id,
                    "from_stage_type": left.stage_type,
                    "to_stage_type": right.stage_type,
                    "stage_projection_hash": projection.logical_hash,
                    "source_authority_signature": source_authority_signature,
                },
                confidence=min(left.confidence, right.confidence),
                relation_source="OFFICIAL",
                method_version=projection.projector_version,
            )
        )
    return tuple(result)


def _action_world_state(
    source_selection: ProductionP1SourceSelection,
    *,
    start_session_time_us: int,
    end_session_time_us: int,
) -> tuple[str, float, tuple[str, ...], str | None]:
    flight_refs = source_selection.refs_by_family.get(SourceFamily.FLIGHT, ())
    if len(flight_refs) != 1:
        raise ProductionWorkerError(
            "ED2_ACTION_SOURCE_CARDINALITY_INVALID",
            str(len(flight_refs)),
        )
    raw_projection = flight_refs[0].projection_payload.get(
        "action_projection"
    )
    if raw_projection is None:
        return (
            "MISSING",
            0.0,
            ("ED2_ACTION_PROJECTION_MISSING",),
            None,
        )
    projection = _mapping(
        raw_projection,
        field="FLIGHT.action_projection",
    )
    raw_events = projection.get("events")
    if not isinstance(raw_events, list) or not raw_events:
        raise ProductionWorkerError(
            "ED2_ACTION_PROJECTION_INVALID",
            "events",
        )

    covered = 0
    for index, raw_event in enumerate(raw_events):
        event = _mapping(
            raw_event,
            field=f"FLIGHT.action_projection.events[{index}]",
        )
        event_start = _integer(
            event.get("start_session_time_us"),
            field=(
                f"FLIGHT.action_projection.events[{index}]."
                "start_session_time_us"
            ),
        )
        event_end = _integer(
            event.get("end_session_time_us"),
            field=(
                f"FLIGHT.action_projection.events[{index}]."
                "end_session_time_us"
            ),
        )
        if (
            event_start < start_session_time_us
            or event_end > end_session_time_us
            or event_start >= event_end
        ):
            raise ProductionWorkerError(
                "ED2_ACTION_INTERVAL_OUTSIDE_EPISODE",
                f"{event_start}:{event_end}",
            )
        covered += event_end - event_start

    span = end_session_time_us - start_session_time_us
    if span <= 0:
        raise ProductionWorkerError(
            "ED2_ACTION_EPISODE_INTERVAL_INVALID",
            f"{start_session_time_us}:{end_session_time_us}",
        )
    coverage = min(1.0, covered / span)
    signature = _hash(
        {
            "artifact_sha256": flight_refs[0].artifact_sha256,
            "action_projection_hash": _hash(projection),
        }
    )
    if coverage == 1.0:
        return "READY", coverage, (), signature
    return (
        "PARTIAL",
        coverage,
        ("ED2_ACTION_COVERAGE_INCOMPLETE",),
        signature,
    )


def _canonical_rows(document: dict[str, object]) -> tuple[CanonicalFlightRow, ...]:
    transform = _mapping(document.get("time_transform"), field="time_transform")
    scale = _number(transform.get("scale"), field="time_transform.scale")
    offset = _integer(transform.get("offset_us"), field="time_transform.offset_us")
    rows_raw = document.get("rows")
    if not isinstance(rows_raw, list):
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", "rows")
    result: list[CanonicalFlightRow] = []
    prior: int | None = None
    for ordinal, raw in enumerate(rows_raw):
        row = _mapping(raw, field=f"rows[{ordinal}]")
        source_time = _integer(row.get("source_time_us"), field="source_time_us")
        session_time = int(round(source_time * scale)) + offset
        if prior is not None and session_time <= prior:
            raise ProductionWorkerError("PRCB_C2_SESSION_TIME_INVALID", str(ordinal))
        prior = session_time

        quality = _integer(row.get("quality"), field="quality")
        if quality < 0:
            raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", "quality")
        result.append(
            CanonicalFlightRow(
                source_stream_ordinal=ordinal,
                session_time_us=session_time,
                body_p_rad_s=_optional_number(row, name="p"),
                nz_g=_optional_number(row, name="nz"),
                heading_true_rad=_optional_number(row, name="heading"),
                tas_mps=_optional_number(row, name="tas"),
                mach=_optional_number(row, name="mach"),
                quality_mask=quality,
            )
        )
    if len(result) < 2:
        raise ProductionWorkerError("PRCB_C2_CANONICAL_TOO_SHORT", str(len(result)))
    return tuple(result)


def _row_dict(row: CanonicalFlightRow) -> dict[str, object]:
    return {
        "source_stream_ordinal": row.source_stream_ordinal,
        "session_time_us": row.session_time_us,
        "body_p_rad_s": row.body_p_rad_s,
        "nz_g": row.nz_g,
        "heading_true_rad": row.heading_true_rad,
        "tas_mps": row.tas_mps,
        "mach": row.mach,
        "quality_mask": row.quality_mask,
    }


def build_p1_worker_product(
    payload: Mapping[str, object],
    *,
    request_hash: str,
    authority_root: Path,
) -> ProductionP1WorkerProduct:
    """Execute governed Source→World→exact-116 Catalog→Release in the worker."""

    body = dict(payload)
    try:
        source_selection = select_production_p1_sources(body)
    except ProductionP1RequestError as exc:
        raise ProductionWorkerError(exc.code, exc.detail) from exc

    flight_payload = source_selection.flight_payload
    flight_refs = source_selection.refs_by_family.get(SourceFamily.FLIGHT, ())
    if len(flight_refs) != 1:
        raise ProductionWorkerError(
            "ED2_P1_PRIMARY_FLIGHT_SOURCE_CARDINALITY",
            str(len(flight_refs)),
        )
    flight_artifact_id = flight_refs[0].artifact_id
    source_json = _text(
        flight_payload.get("source_json"),
        field="source_json",
    )
    source_bytes = source_json.encode("utf-8")
    document = validate_production_flight_document(source_bytes)
    session_id = _uuid(document.get("session_id"), field="session_id")
    aircraft_id = _uuid(document.get("aircraft_id"), field="aircraft_id")
    canonical_rows = _canonical_rows(document)
    canonical_payload = [_row_dict(row) for row in canonical_rows]
    canonical_hash = _hash(
        {
            "schema": "CANONICAL_AIRCRAFT_STATE_V1",
            "session_id": session_id,
            "aircraft_id": aircraft_id,
            "rows": canonical_payload,
        }
    )
    dataset_id = str(uuid5(_DATASET_NAMESPACE, canonical_hash))
    release_id = allocate_session_release_id(
        session_id=session_id,
        request_hash=request_hash,
    )
    episode_id = str(
        uuid5(_EPISODE_NAMESPACE, f"{session_id}|{canonical_hash}")
    )

    context_raw = _mapping(
        body.get("evaluation_context"),
        field="evaluation_context",
    )
    context_id = _uuid(
        context_raw.get("context_id"),
        field="evaluation_context.context_id",
    )
    if _uuid(
        context_raw.get("session_id"),
        field="evaluation_context.session_id",
    ) != session_id:
        raise ProductionWorkerError(
            "PRCB_C2_CONTEXT_SESSION_DRIFT",
            context_id,
        )
    context_version = _text(
        context_raw.get("context_version"),
        field="evaluation_context.context_version",
    )
    context_projection: EvaluationContextDTO = {
        "context_id": context_id,
        "session_id": session_id,
        "context_version": context_version,
        "revision_no": _integer(
            context_raw.get("revision_no"),
            field="evaluation_context.revision_no",
        ),
        "rule_set_version": _text(
            context_raw.get("rule_set_version"),
            field="evaluation_context.rule_set_version",
        ),
        "metric_profile_version": _text(
            context_raw.get("metric_profile_version"),
            field="evaluation_context.metric_profile_version",
        ),
        "status": _text(
            context_raw.get("status"),
            field="evaluation_context.status",
        ),
    }

    start = canonical_rows[0].session_time_us
    end = canonical_rows[-1].session_time_us + 1
    context_hash = _hash(dict(context_projection))
    comparison_context_hash = _hash(
        {
            "context_version": context_projection["context_version"],
            "revision_no": context_projection["revision_no"],
            "rule_set_version": context_projection["rule_set_version"],
            "metric_profile_version": context_projection[
                "metric_profile_version"
            ],
            "status": context_projection["status"],
        }
    )
    episode_hash = _hash(
        {
            "episode_id": episode_id,
            "session_id": session_id,
            "start_session_time_us": start,
            "end_session_time_us": end,
            "context_id": context_id,
        }
    )
    source_import = _mapping(
        flight_payload.get("source_import"),
        field="source_import",
    )
    source_sha = hashlib.sha256(source_bytes).hexdigest()

    identity_raw = _mapping(
        body.get("publication_identity"),
        field="publication_identity",
    )
    aircraft_binding = ProductionP1AircraftBinding(
        aircraft_id=aircraft_id,
        aircraft_model_id=_uuid(
            identity_raw.get("aircraft_model_id"),
            field="publication_identity.aircraft_model_id",
        ),
        aircraft_instance_id=_uuid(
            identity_raw.get("aircraft_instance_id"),
            field="publication_identity.aircraft_instance_id",
        ),
        subject_entity_id=_uuid(
            identity_raw.get("subject_entity_id"),
            field="publication_identity.subject_entity_id",
        ),
        capability_dimension=_text(
            identity_raw.get("capability_dimension"),
            field="publication_identity.capability_dimension",
        ),
        capability_type=_text(
            identity_raw.get("capability_type"),
            field="publication_identity.capability_type",
        ),
    )

    expected_version_token = _integer(
        body.get("expected_version_token"),
        field="expected_version_token",
    )
    if expected_version_token != 0:
        raise ProductionWorkerError(
            "PRCB_C2_RELEASE_REVISION_NOT_CONFIGURED",
            str(expected_version_token),
        )
    parent_raw = body.get("parent_release_id")
    parent_release_id = (
        None
        if parent_raw is None
        else _uuid(parent_raw, field="parent_release_id")
    )
    if parent_release_id is not None:
        raise ProductionWorkerError(
            "PRCB_C2_PARENT_RELEASE_INVALID",
            parent_release_id,
        )

    try:
        validate_production_p1_world_authority(authority_root)
        (
            stage_source_payload,
            stage_source_artifact_sha256,
        ) = _scenario_stage_payload(source_selection)
        stage_projection = project_production_basic_stages(
            stage_source_payload,
            episode_id=episode_id,
            start_session_time_us=start,
            end_session_time_us=end,
            authority_root=authority_root,
        )
        stage_relations = _stage_relations(
            stage_projection,
            episode_id=episode_id,
            source_authority_signature=stage_source_artifact_sha256,
        )

        (
            context_status,
            context_coverage,
            context_reasons,
            context_signature,
        ) = _world_source_state(
            source_selection,
            required=PRODUCTION_P1_WORLD_SOURCE_FAMILIES["CONTEXT"],
        )
        (
            truth_status,
            truth_coverage,
            truth_reasons,
            truth_signature,
        ) = _world_source_state(
            source_selection,
            required=PRODUCTION_P1_WORLD_SOURCE_FAMILIES["TRUTH"],
        )
        (
            action_status,
            action_coverage,
            action_reasons,
            action_signature,
        ) = _action_world_state(
            source_selection,
            start_session_time_us=start,
            end_session_time_us=end,
        )
        (
            machine_status,
            machine_coverage,
            machine_reasons,
            machine_signature,
        ) = _world_source_state(
            source_selection,
            required=PRODUCTION_P1_WORLD_SOURCE_FAMILIES["MACHINE"],
        )
        basic_world_ready = (
            stage_projection.status == "READY"
            and context_status == "READY"
            and truth_status == "READY"
            and action_status == "READY"
            and machine_status == "READY"
        )

        context_world_hash = _hash(
            {
                "world_kind": "CONTEXT",
                "release_id": release_id,
                "session_id": session_id,
                "episode_id": episode_id,
                "context_logical_hash": context_hash,
                "stage_projection_hash": stage_projection.logical_hash,
                "source_authority_signature": context_signature,
                "status": context_status,
                "coverage": context_coverage,
                "reason_codes": list(context_reasons),
                "request_hash": request_hash,
            }
        )
        context_world_id = str(
            uuid5(_WORLD_NAMESPACE, f"CONTEXT|{context_world_hash}")
        )
        action_world_hash = _hash(
            {
                "world_kind": "ACTION",
                "release_id": release_id,
                "session_id": session_id,
                "episode_id": episode_id,
                "aircraft_id": aircraft_id,
                "stage_projection_hash": stage_projection.logical_hash,
                "source_authority_signature": action_signature,
                "status": action_status,
                "coverage": action_coverage,
                "reason_codes": list(action_reasons),
                "request_hash": request_hash,
            }
        )
        action_world_id = str(
            uuid5(_WORLD_NAMESPACE, f"ACTION|{action_world_hash}")
        )
        truth_world_hash = _hash(
            {
                "world_kind": "TRUTH",
                "release_id": release_id,
                "session_id": session_id,
                "episode_id": episode_id,
                "aircraft_id": aircraft_id,
                "dataset_id": dataset_id,
                "canonical_logical_hash": canonical_hash,
                "context_logical_hash": context_hash,
                "episode_logical_hash": episode_hash,
                "stage_projection_hash": stage_projection.logical_hash,
                "stage_ids": [
                    stage.stage_id for stage in stage_projection.stages
                ],
                "source_authority_signature": truth_signature,
                "status": truth_status,
                "coverage": truth_coverage,
                "reason_codes": list(truth_reasons),
                "request_hash": request_hash,
            }
        )
        truth_world_id = str(
            uuid5(_WORLD_NAMESPACE, f"TRUTH|{truth_world_hash}")
        )
        machine_world_hash = _hash(
            {
                "world_kind": "MACHINE",
                "release_id": release_id,
                "session_id": session_id,
                "episode_id": episode_id,
                "aircraft_id": aircraft_id,
                "context_logical_hash": context_hash,
                "episode_logical_hash": episode_hash,
                "stage_projection_hash": stage_projection.logical_hash,
                "stage_ids": [
                    stage.stage_id for stage in stage_projection.stages
                ],
                "source_authority_signature": machine_signature,
                "status": machine_status,
                "coverage": machine_coverage,
                "reason_codes": list(machine_reasons),
                "request_hash": request_hash,
            }
        )
        machine_world_id = str(
            uuid5(_WORLD_NAMESPACE, f"MACHINE|{machine_world_hash}")
        )
        world_id = truth_world_id
        world_hash = truth_world_hash

        context_world = CoreWorldProductRecord(
            world_product_id=context_world_id,
            episode_id=episode_id,
            stage_id=None,
            world_kind="CONTEXT",
            subject_id=None,
            observer_id=None,
            actor_id=None,
            aircraft_id=aircraft_id,
            aircraft_instance_id=aircraft_binding.aircraft_instance_id,
            dataset_id=None,
            start_session_time_us=start,
            end_session_time_us=end,
            status=context_status,
            coverage=context_coverage,
            confidence=context_coverage,
            reason_codes=context_reasons,
            source_authority_signature=context_signature,
            world_version="ED2_PRODUCTION_P1_CONTEXT_WORLD_V1",
            policy_version="ED2-CONFORMANCE:B1",
            artifact_sha256=None,
            logical_content_hash=context_world_hash,
            request_hash=request_hash,
        )
        action_world = CoreWorldProductRecord(
            world_product_id=action_world_id,
            episode_id=episode_id,
            stage_id=None,
            world_kind="ACTION",
            subject_id=aircraft_binding.subject_entity_id,
            observer_id=None,
            actor_id=None,
            aircraft_id=aircraft_id,
            aircraft_instance_id=aircraft_binding.aircraft_instance_id,
            dataset_id=None,
            start_session_time_us=start,
            end_session_time_us=end,
            status=action_status,
            coverage=action_coverage,
            confidence=action_coverage,
            reason_codes=action_reasons,
            source_authority_signature=action_signature,
            world_version="ED2_PRODUCTION_P1_ACTION_WORLD_V1",
            policy_version="ED2-CONFORMANCE:B1",
            artifact_sha256=None,
            logical_content_hash=action_world_hash,
            request_hash=request_hash,
        )
        truth_world = CoreWorldProductRecord(
            world_product_id=truth_world_id,
            episode_id=episode_id,
            stage_id=None,
            world_kind="TRUTH",
            subject_id=aircraft_binding.subject_entity_id,
            observer_id=None,
            actor_id=None,
            aircraft_id=aircraft_id,
            aircraft_instance_id=aircraft_binding.aircraft_instance_id,
            dataset_id=dataset_id,
            start_session_time_us=start,
            end_session_time_us=end,
            status=truth_status,
            coverage=truth_coverage,
            confidence=truth_coverage,
            reason_codes=truth_reasons,
            source_authority_signature=truth_signature,
            world_version="ED2_PRODUCTION_P1_TRUTH_WORLD_V1",
            policy_version="ED2-CONFORMANCE:B1",
            artifact_sha256=None,
            logical_content_hash=truth_world_hash,
            request_hash=request_hash,
        )
        machine_world = CoreWorldProductRecord(
            world_product_id=machine_world_id,
            episode_id=episode_id,
            stage_id=None,
            world_kind="MACHINE",
            subject_id=aircraft_binding.subject_entity_id,
            observer_id=None,
            actor_id=None,
            aircraft_id=aircraft_id,
            aircraft_instance_id=aircraft_binding.aircraft_instance_id,
            dataset_id=None,
            start_session_time_us=start,
            end_session_time_us=end,
            status=machine_status,
            coverage=machine_coverage,
            confidence=machine_coverage,
            reason_codes=machine_reasons,
            source_authority_signature=machine_signature,
            world_version="ED2_PRODUCTION_P1_MACHINE_WORLD_V1",
            policy_version="ED2-CONFORMANCE:B1",
            artifact_sha256=None,
            logical_content_hash=machine_world_hash,
            request_hash=request_hash,
        )

        contract = build_production_p1_catalog_contract(authority_root)
        request = parse_production_p1_request(
            body,
            contract=contract,
            aircraft_id=aircraft_id,
            source_selection=source_selection,
        )
        execution_contract, metric_batch = execute_production_p1_catalog(
            authority_root,
            request.inputs,
        )
        if execution_contract.plan.logical_hash != contract.plan.logical_hash:
            raise ProductionP1CatalogError(
                "ED2_P1_EXECUTION_PLAN_DRIFT",
                execution_contract.plan.logical_hash,
            )
        relation_ids = tuple(
            relation.relation_id for relation in stage_relations
        )
        release = materialize_production_p1_release(
            contract=execution_contract,
            batch=metric_batch,
            inputs=request.inputs,
            context=ProductionP1ReleaseContext(
                release_id=release_id,
                release_no=1,
                parent_release_id=None,
                request_hash=request_hash,
                session_id=session_id,
                context_id=context_id,
                context_version=context_version,
                context_binding_hash=context_hash,
                comparison_context_hash=comparison_context_hash,
                episode_id=episode_id,
                stage_id=None,
                start_session_time_us=start,
                end_session_time_us=end,
                coverage=min(
                    context_coverage,
                    truth_coverage,
                    action_coverage,
                    machine_coverage,
                ),
                confidence=min(
                    context_coverage,
                    truth_coverage,
                    action_coverage,
                    machine_coverage,
                ),
                observation_schema_version="ED2-P1-OBSERVATION-V1",
                world_product_versions={
                    "context_world_product_id": context_world_id,
                    "context_world_logical_hash": context_world_hash,
                    "truth_world_product_id": truth_world_id,
                    "truth_world_logical_hash": truth_world_hash,
                    "action_world_product_id": action_world_id,
                    "action_world_logical_hash": action_world_hash,
                    "machine_world_product_id": machine_world_id,
                    "machine_world_logical_hash": machine_world_hash,
                    "basic_core_ready": basic_world_ready,
                    "canonical_dataset_id": dataset_id,
                    "canonical_logical_hash": canonical_hash,
                    "stage_profile_id": stage_projection.stage_profile_id,
                    "stage_projection_status": stage_projection.status,
                    "stage_projection_hash": stage_projection.logical_hash,
                    "stage_registry_sha256": (
                        stage_projection.stage_registry_sha256
                    ),
                    "stage_source_artifact_sha256": (
                        stage_source_artifact_sha256
                    ),
                    "stage_ids": [
                        stage.stage_id for stage in stage_projection.stages
                    ],
                },
                world_product_ids=(
                    context_world_id,
                    truth_world_id,
                    action_world_id,
                    machine_world_id,
                ),
                relation_ids=relation_ids,
            ),
            aircraft=aircraft_binding,
            system_bindings=request.system_bindings,
            world_products=(
                context_world,
                truth_world,
                action_world,
                machine_world,
            ),
            world_relations=stage_relations,
        )
    except (
        CatalogMetricEngineError,
        ProductionP1CatalogError,
        ProductionP1MaterializationError,
        ProductionP1RequestError,
        ProductionP1WorldPolicyError,
        ProductionStageError,
    ) as exc:
        raise ProductionWorkerError(exc.code, exc.detail) from exc

    prerequisites: list[ProductionPrerequisiteRow] = [
        ProductionPrerequisiteRow(
            table="registry.training_session",
            values={
                "session_id": session_id,
                "session_code": _text(
                    source_import.get("session_code"),
                    field="source_import.session_code",
                ),
                "session_type": _session_type(
                    source_import.get("session_type"),
                ),
                "start_session_time_us": start,
                "end_session_time_us": end,
                "training_type_set": [],
                "data_status": "READY",
                "source_count": source_selection.source_count,
                "schema_version": "1.9.0",
            },
            field_kinds={"training_type_set": "text_array"},
        ),
        ProductionPrerequisiteRow(
            table="registry.dataset_snapshot",
            values={
                "dataset_snapshot_id": dataset_id,
                "snapshot_type": "CANONICAL_FLIGHT",
                "query_or_manifest": {
                    "schema": "TPAA_ED2_B1_CANONICAL_DATASET_V1",
                    "session_id": session_id,
                    "aircraft_id": aircraft_id,
                    "canonical_logical_hash": canonical_hash,
                    "source_sha256": source_sha,
                },
                "input_refs": [flight_artifact_id],
                "data_hash": canonical_hash,
                "schema_version": "1.9.0",
                "frozen": True,
            },
            field_kinds={
                "query_or_manifest": "json",
                "input_refs": "uuid_array",
            },
        ),
        ProductionPrerequisiteRow(
            table="master.aircraft_model",
            values={
                "aircraft_model_id": aircraft_binding.aircraft_model_id,
                "type_code": _text(
                    identity_raw.get("aircraft_type_code"),
                    field="publication_identity.aircraft_type_code",
                ),
                "model_name": _text(
                    identity_raw.get("aircraft_model_name"),
                    field="publication_identity.aircraft_model_name",
                ),
            },
            field_kinds={},
        ),
        ProductionPrerequisiteRow(
            table="master.aircraft",
            values={
                "aircraft_id": aircraft_id,
                "aircraft_model_id": aircraft_binding.aircraft_model_id,
                "internal_code": _text(
                    identity_raw.get("aircraft_internal_code"),
                    field="publication_identity.aircraft_internal_code",
                ),
                "master_data_status": "ACTIVE",
            },
            field_kinds={},
        ),
        ProductionPrerequisiteRow(
            table="master.entity",
            values={
                "entity_id": aircraft_binding.subject_entity_id,
                "session_id": session_id,
                "entity_type": "AIRCRAFT",
                "alias": _text(
                    identity_raw.get("entity_alias"),
                    field="publication_identity.entity_alias",
                ),
            },
            field_kinds={},
        ),
        ProductionPrerequisiteRow(
            table="master.aircraft_instance",
            values={
                "aircraft_instance_id": aircraft_binding.aircraft_instance_id,
                "session_id": session_id,
                "aircraft_id": aircraft_id,
                "entity_id": aircraft_binding.subject_entity_id,
                "instance_seq": 0,
                "start_session_time_us": start,
                "end_session_time_us": end,
                "start_reason": "PRODUCTION_IMPORT",
                "identity_scope": "SESSION_ONLY",
                "identity_confidence": 1.0,
            },
            field_kinds={},
        ),
        ProductionPrerequisiteRow(
            table="context.evaluation_context",
            values=dict(context_projection),
            field_kinds={},
        ),
        ProductionPrerequisiteRow(
            table="episode.training_episode",
            values={
                "episode_id": episode_id,
                "session_id": session_id,
                "episode_type": "BASIC_FLIGHT",
                "context_id": context_id,
                "start_session_time_us": start,
                "end_session_time_us": end,
                "subject_scope": "AIRCRAFT",
                "primary_aircraft_id": aircraft_id,
                "world_capability_code": "BASIC_CORE",
                "episode_status": "READY",
                "detector_version": "ED2_B1_PRODUCTION_EPISODE_V1",
                "coverage": 1.0,
                "confidence": 1.0,
                "data_sufficiency_status": (
                    "SUFFICIENT"
                    if basic_world_ready
                    else "INSUFFICIENT_DATA"
                ),
            },
            field_kinds={},
        ),
    ]

    for stage in stage_projection.stages:
        prerequisites.append(
            ProductionPrerequisiteRow(
                table="episode.episode_stage",
                values={
                    "stage_id": stage.stage_id,
                    "episode_id": stage.episode_id,
                    "stage_type": stage.stage_type,
                    "stage_order": stage.stage_order,
                    "start_session_time_us": stage.start_session_time_us,
                    "end_session_time_us": stage.end_session_time_us,
                    "detection_method": stage.detection_method,
                    "stage_status": stage.stage_status,
                    "coverage": stage.coverage,
                    "confidence": stage.confidence,
                    "detector_version": stage.detector_version,
                    "supersedes_stage_id": None,
                },
                field_kinds={},
            )
        )

    for system in request.system_authorities:
        prerequisites.append(
            ProductionPrerequisiteRow(
                table="master.mission_system_instance",
                values={
                    "mission_system_instance_id": (
                        system.mission_system_instance_id
                    ),
                    "aircraft_id": system.aircraft_id,
                    "system_type": system.system_type,
                    "system_code": system.system_code,
                    "hardware_version": system.hardware_version,
                    "software_version": system.software_version,
                    "installation_id": system.installation_id,
                    "alignment_profile_version": (
                        system.alignment_profile_version
                    ),
                    "status": system.status,
                    "configuration_hash": system.configuration_hash,
                },
                field_kinds={},
            )
        )

    definition_by_code = {
        item.metric_code: item
        for item in execution_contract.plan.definitions
    }
    for definition_ref in release.definitions:
        definition = definition_by_code[definition_ref.metric_code]
        capability_dimension = (
            aircraft_binding.capability_dimension
            if definition.subject_type == "AIRCRAFT"
            else definition.family
        )
        prerequisites.append(
            ProductionPrerequisiteRow(
                table="metric.metric_definition",
                values={
                    "metric_definition_id": (
                        definition_ref.metric_definition_id
                    ),
                    "metric_code": definition.metric_code,
                    "version": definition.algorithm_version,
                    "catalog_version": definition_ref.catalog_version,
                    "catalog_hash": definition_ref.catalog_hash,
                    "metric_semantic_id": definition.semantic_id,
                    "metric_semantic_version": definition.semantic_version,
                    "name": definition.name,
                    "subject_type": definition.subject_type,
                    "observation_lane": definition.observation_lane,
                    "publication_route": definition.publication_route,
                    "category": definition.family,
                    "calculation_layer": "METRIC",
                    "capability_level": "CAP_L1_OBSERVED",
                    "capability_dimension": capability_dimension,
                    "required_world_products": list(
                        production_p1_required_world_kinds(definition)
                    ),
                    "scope": "EPISODE",
                    "spec_uri": (
                        "canonical://P1_METRIC_CATALOG/"
                        f"{definition.metric_code}"
                    ),
                    "spec_hash": definition.definition_hash,
                    "definition_hash": definition.definition_hash,
                    "plugin_name": definition.algorithm_id,
                    "plugin_version": definition.algorithm_version,
                    "status": "ACTIVE",
                },
                field_kinds={"required_world_products": "json"},
            )
        )

    return ProductionP1WorkerProduct(
        schema=PRODUCTION_P1_WORKER_SCHEMA,
        release=release,
        canonical_rows=tuple(canonical_payload),
        dataset_id=dataset_id,
        canonical_logical_hash=canonical_hash,
        world_product_id=world_id,
        world_logical_hash=world_hash,
        metric_batch_hash=metric_batch.logical_hash,
        source_sha256=source_sha,
        prerequisites=tuple(prerequisites),
    )


def _verify_job_request(
    payload: WorkerPayload,
    job_payload: dict[str, object],
) -> None:
    expected = canonical_request_hash(
        {"job_type": payload.command, "payload": job_payload}
    )
    if expected != payload.request_hash:
        raise ProductionWorkerError(
            "PRCB_C2_REQUEST_HASH_MISMATCH",
            payload.job_id,
        )


def _execute_p1(payload: WorkerPayload) -> WorkerResult:
    body = _mapping(payload.domain_payload, field="domain_payload")
    authority_root = Path(_text(body.get("authority_root"), field="authority_root"))
    request_payload = _mapping(body.get("job_payload"), field="job_payload")
    _verify_job_request(payload, request_payload)
    product = build_p1_worker_product(
        request_payload,
        request_hash=payload.request_hash,
        authority_root=authority_root,
    )
    return WorkerResult(
        job_id=payload.job_id,
        request_hash=payload.request_hash,
        command=payload.command,
        status="SUCCEEDED",
        output=(
            product.schema,
            product.release.release_id,
            product.release.manifest_hash,
            product.canonical_logical_hash,
            product.world_logical_hash,
            product.metric_batch_hash,
        ),
        domain_payload=product,
    )


def _execute_p2_attribution(payload: WorkerPayload) -> WorkerResult:
    body = payload.domain_payload
    if not isinstance(body, ProductionP2AttributionWorkerInput):
        raise ProductionWorkerError(
            "PRCB_C2_WORKER_PRODUCT_INVALID",
            type(body).__name__,
        )
    _verify_job_request(payload, body.job_payload)
    compute_input = body.compute_input
    value = execute_p2_attribution(
        bundle=compute_input.input_bundle,
        target_feature_set=compute_input.target_feature_set,
        cohort_rows=compute_input.cohort_rows,
        reference_factor_values=compute_input.reference_factor_values,
        p2_release_id=body.p2_release_id,
        evidence_set_id=compute_input.input_bundle.target.evidence_set_id,
        execution_time_utc=body.execution_time_utc,
        created_by="PRCB_C2_PRODUCTION_WORKER",
        supersedes_estimate_id=body.supersedes_estimate_id,
    )
    return WorkerResult(
        job_id=payload.job_id,
        request_hash=payload.request_hash,
        command=payload.command,
        status="SUCCEEDED",
        output=(
            value.attribution_run.attribution_run_id,
            value.adjusted_estimate.estimate_id,
            value.adjusted_estimate.logical_hash,
        ),
        domain_payload=value,
    )


def _execute_p3_build(payload: WorkerPayload) -> WorkerResult:
    body = payload.domain_payload
    if not isinstance(body, ProductionP3BuildWorkerInput):
        raise ProductionWorkerError(
            "PRCB_C2_WORKER_PRODUCT_INVALID",
            type(body).__name__,
        )
    _verify_job_request(payload, body.job_payload)
    policy = P3AuthorityPolicy.from_canonical()
    profile = P3ModelExecutionProfile.from_canonical()
    segment = build_p3_lifecycle_segment(
        segment_snapshot_id=body.segment_snapshot_id,
        estimates=body.estimates,
        lifecycle_events=(),
        as_of_utc=body.as_of_utc,
        policy=policy,
    )
    validation = build_p3_validation_snapshot(
        validation_snapshot_id=body.validation_snapshot_id,
        training_dataset_snapshot_id=body.training_dataset_snapshot_id,
        segment=segment,
        estimates=body.estimates,
        as_of_utc=body.as_of_utc,
        policy=policy,
    )
    training = materialize_training_dataset(
        segment=segment,
        validation=validation,
        estimates=body.estimates,
        created_at_utc=body.training_created_at_utc,
        policy=policy,
        profile=profile,
    )
    model_build = execute_capability_model(
        training=training,
        validation=validation,
        segment=segment,
        estimates=body.estimates,
        trained_at_utc=body.trained_at_utc,
        policy=policy,
        profile=profile,
    )
    surface_build = build_capability_surface(
        model_build=model_build,
        created_at_utc=body.surface_created_at_utc,
        profile=profile,
    )
    model_object = P3ManagedObject(
        object_ref_id=product_object_ref_id(
            model_build.model.model_artifact_uri,
            model_build.model.model_artifact_hash,
        ),
        managed_uri=model_build.model.model_artifact_uri,
        artifact_sha256=model_build.model.model_artifact_hash,
        sealed=True,
        gc_state="ACTIVE",
        deleted_at=None,
    )
    surface_object = P3ManagedObject(
        object_ref_id=product_object_ref_id(
            surface_build.surface.dataset_uri,
            surface_build.surface.dataset_hash,
        ),
        managed_uri=surface_build.surface.dataset_uri,
        artifact_sha256=surface_build.surface.dataset_hash,
        sealed=True,
        gc_state="ACTIVE",
        deleted_at=None,
    )
    component = P3TwinComponentBinding(
        model_build=model_build,
        surface_build=surface_build,
        model_object_ref_id=model_object.object_ref_id,
        surface_object_ref_id=surface_object.object_ref_id,
    )
    twin = publish_aircraft_twin_revision(
        aircraft_id=segment.aircraft_id,
        components=(component,),
        config_snapshot_id=body.configuration_snapshot_id,
        evidence_snapshot_id=training.dataset_snapshot_id,
        valid_from_utc=body.twin_valid_from_utc,
        valid_to_utc=None,
        as_of_data_time_utc=body.as_of_utc,
        published_at_utc=body.twin_published_at_utc,
        profile=profile,
    )
    estimates = tuple(
        evaluate_twin_capability_estimate(
            twin=twin,
            components=(component,),
            capability_type=segment.capability_type,
            condition_point={
                "session_order": item.session_order,
                "reference_condition_id": segment.reference_condition_id,
            },
            as_of_time_utc=twin.as_of_data_time,
            created_at_utc=body.estimate_created_at_utc,
            profile=profile,
            policy=policy,
        )
        for item in sorted(
            body.estimates,
            key=lambda value: (value.session_order, value.estimate_id),
        )
    )
    product = ProductionP3BuildWorkerProduct(
        segment=segment,
        validation=validation,
        training=training,
        model_build=model_build,
        surface_build=surface_build,
        model_object=model_object,
        surface_object=surface_object,
        component=component,
        twin=twin,
        estimates=estimates,
    )
    return WorkerResult(
        job_id=payload.job_id,
        request_hash=payload.request_hash,
        command=payload.command,
        status="SUCCEEDED",
        output=(
            twin.twin_revision_id,
            model_build.model.capability_model_id,
            *(item.estimate_id for item in estimates),
        ),
        domain_payload=product,
    )


def _execute_p3_estimate(payload: WorkerPayload) -> WorkerResult:
    body = payload.domain_payload
    if not isinstance(body, ProductionP3EstimateWorkerInput):
        raise ProductionWorkerError(
            "PRCB_C2_WORKER_PRODUCT_INVALID",
            type(body).__name__,
        )
    _verify_job_request(payload, body.job_payload)
    value = evaluate_twin_capability_estimate(
        twin=body.twin,
        components=body.components,
        capability_type=body.capability_type,
        condition_point=body.condition_point,
        as_of_time_utc=body.as_of_time_utc,
        created_at_utc=body.created_at_utc,
    )
    return WorkerResult(
        job_id=payload.job_id,
        request_hash=payload.request_hash,
        command=payload.command,
        status="SUCCEEDED",
        output=(value.estimate_id,),
        domain_payload=value,
    )


def _p3_claim_envelope(
    subject: P4SubjectContext,
    estimate: P3CapabilityEstimate | None,
) -> P3ClaimEnvelope:
    if estimate is None:
        if subject.p3_estimate_id is not None:
            raise ProductionWorkerError(
                "PRCB_C2_P4_P3_ESTIMATE_MISSING",
                subject.p3_estimate_id,
            )
        return P3ClaimEnvelope(
            claim_level="P3_EVIDENCE_UNAVAILABLE",
            validity_status="UNAVAILABLE",
            as_of_utc=subject.as_of_utc,
            uncertainty_lower=None,
            uncertainty_upper=None,
        )
    if (
        subject.p3_estimate_id != estimate.estimate_id
        or subject.twin_revision_id != estimate.twin_revision_id
    ):
        raise ProductionWorkerError(
            "PRCB_C2_P4_P3_IDENTITY_DRIFT",
            estimate.estimate_id,
        )
    lower_raw = estimate.uncertainty.get("lower")
    upper_raw = estimate.uncertainty.get("upper")
    lower = (
        None
        if lower_raw is None
        else _number(lower_raw, field="p3.uncertainty.lower")
    )
    upper = (
        None
        if upper_raw is None
        else _number(upper_raw, field="p3.uncertainty.upper")
    )
    return P3ClaimEnvelope(
        claim_level=estimate.claim_level,
        validity_status=estimate.validity_domain_status,
        as_of_utc=estimate.as_of_time,
        uncertainty_lower=lower,
        uncertainty_upper=upper,
    )


def _p4_worker_product(
    *,
    subject: P4SubjectContext,
    scope: P4InteractionScopeSnapshot,
    p3_estimate: P3CapabilityEstimate | None,
    confidence: float,
    created_at_utc: str,
) -> ProductionP4AssessmentWorkerProduct:
    evidence = materialize_p4_human_machine_evidence(subject, scope)
    claim = _p3_claim_envelope(subject, p3_estimate)
    revision = build_p4_assessment_revision(
        subject,
        evidence=evidence,
        annotations=(),
        p3_claim=claim,
        confidence=confidence,
        created_at_utc=created_at_utc,
        approval_state="DRAFT",
        supersedes_id=None,
    )
    result = evaluate_ed2_training_assessment(
        evidence_availability=tuple(
            item.availability_status for item in evidence
        ),
        p3_validity_statuses=(claim.validity_status,),
        approval_states=(revision.approval_state,),
    )
    return ProductionP4AssessmentWorkerProduct(
        subject=subject,
        scope=scope,
        revision=revision,
        assessment_result=result,
    )


def _execute_p4_build(payload: WorkerPayload) -> WorkerResult:
    body = payload.domain_payload
    if not isinstance(body, ProductionP4BuildWorkerInput):
        raise ProductionWorkerError(
            "PRCB_C2_WORKER_PRODUCT_INVALID",
            type(body).__name__,
        )
    _verify_job_request(payload, body.job_payload)
    subject = build_p4_subject_context(
        body.source,
        role_model=body.role_model,
    )
    scope = build_p4_interaction_scope_snapshot(
        subject_context_id=subject.subject_context_id,
        episode_id=subject.episode_id,
        as_of_utc=subject.as_of_utc,
        fact_refs=body.fact_refs,
        machine_evidence=body.machine_evidence,
        instructor_evidence=(),
    )
    product = _p4_worker_product(
        subject=subject,
        scope=scope,
        p3_estimate=body.p3_estimate,
        confidence=body.confidence,
        created_at_utc=body.created_at_utc,
    )
    return WorkerResult(
        job_id=payload.job_id,
        request_hash=payload.request_hash,
        command=payload.command,
        status="SUCCEEDED",
        output=(
            product.revision.actor_assessment_id,
            product.revision.logical_content_hash,
            product.assessment_result.qualification_status,
        ),
        domain_payload=product,
    )


def _execute_p4_assessment(payload: WorkerPayload) -> WorkerResult:
    body = payload.domain_payload
    if not isinstance(body, ProductionP4AssessmentWorkerInput):
        raise ProductionWorkerError(
            "PRCB_C2_WORKER_PRODUCT_INVALID",
            type(body).__name__,
        )
    _verify_job_request(payload, body.job_payload)
    product = _p4_worker_product(
        subject=body.subject,
        scope=body.scope,
        p3_estimate=body.p3_estimate,
        confidence=body.confidence,
        created_at_utc=body.created_at_utc,
    )
    return WorkerResult(
        job_id=payload.job_id,
        request_hash=payload.request_hash,
        command=payload.command,
        status="SUCCEEDED",
        output=(
            product.revision.actor_assessment_id,
            product.revision.logical_content_hash,
            product.assessment_result.qualification_status,
        ),
        domain_payload=product,
    )


def _p5_worker_product(
    *,
    compute_input: P5DurableComputeInput,
    confidence: float,
    created_at_utc: str,
) -> ProductionP5AssessmentWorkerProduct:
    evidence = materialize_p5_team_mission_evidence(
        compute_input.composition,
        p4_revisions=compute_input.p4_revisions,
        evidence_set_id=compute_input.evidence_set_id,
        objective_result_refs=compute_input.objective_result_refs,
        as_of_utc=compute_input.as_of_utc,
    )
    aggregation = build_p5_aggregation(evidence)
    revision = build_p5_assessment_revision(
        compute_input.composition,
        evidence=evidence,
        aggregation=aggregation,
        confidence=confidence,
        created_at_utc=created_at_utc,
        approval_state="DRAFT",
        supersedes=None,
    )
    result = evaluate_ed2_training_assessment(
        evidence_availability=(evidence.availability_status,),
        p3_validity_statuses=tuple(
            item.p3_validity_status for item in compute_input.p4_revisions
        ),
        approval_states=(revision.approval_state,),
    )
    return ProductionP5AssessmentWorkerProduct(
        composition=compute_input.composition,
        compute_input=compute_input,
        revision=revision,
        assessment_result=result,
    )


def _execute_p5_build(payload: WorkerPayload) -> WorkerResult:
    body = payload.domain_payload
    if not isinstance(body, ProductionP5BuildWorkerInput):
        raise ProductionWorkerError(
            "PRCB_C2_WORKER_PRODUCT_INVALID",
            type(body).__name__,
        )
    _verify_job_request(payload, body.job_payload)
    participants = tuple(
        P5ParticipantBinding(
            subject_key=revision.subject_key,
            role_code=revision.role_code,
            aircraft_id=revision.aircraft_id,
            twin_revision_id=revision.twin_revision_id,
            p4_revision_id=revision.actor_assessment_id,
        )
        for revision in body.p4_revisions
    )
    composition = build_p5_composition_snapshot(
        session_id=body.session_id,
        mission_episode_id=body.mission_episode_id,
        team_id=body.team_id,
        participants=participants,
        world_snapshot_refs=body.world_snapshot_refs,
        scenario_context_artifact_id=body.scenario_context_artifact_id,
        role_model_context_artifact_id=body.role_model_context_artifact_id,
        assessment_spec_id=body.assessment_spec_id,
        assessment_spec_version=body.assessment_spec_version,
        as_of_utc=body.as_of_utc,
    )
    compute_input = P5DurableComputeInput(
        composition=composition,
        p4_revisions=body.p4_revisions,
        objective_result_refs=body.objective_result_refs,
        evidence_set_id=body.evidence_set_id,
        as_of_utc=body.as_of_utc,
    )
    product = _p5_worker_product(
        compute_input=compute_input,
        confidence=body.confidence,
        created_at_utc=body.created_at_utc,
    )
    return WorkerResult(
        job_id=payload.job_id,
        request_hash=payload.request_hash,
        command=payload.command,
        status="SUCCEEDED",
        output=(
            product.revision.mission_assessment_id,
            product.revision.logical_content_hash,
            product.assessment_result.qualification_status,
        ),
        domain_payload=product,
    )


def _execute_p5_assessment(payload: WorkerPayload) -> WorkerResult:
    body = payload.domain_payload
    if not isinstance(body, ProductionP5AssessmentWorkerInput):
        raise ProductionWorkerError(
            "PRCB_C2_WORKER_PRODUCT_INVALID",
            type(body).__name__,
        )
    _verify_job_request(payload, body.job_payload)
    product = _p5_worker_product(
        compute_input=body.compute_input,
        confidence=body.confidence,
        created_at_utc=body.created_at_utc,
    )
    return WorkerResult(
        job_id=payload.job_id,
        request_hash=payload.request_hash,
        command=payload.command,
        status="SUCCEEDED",
        output=(
            product.revision.mission_assessment_id,
            product.revision.logical_content_hash,
            product.assessment_result.qualification_status,
        ),
        domain_payload=product,
    )


def _execute_p6_build(payload: WorkerPayload) -> WorkerResult:
    body = payload.domain_payload
    if not isinstance(body, ProductionP6BuildWorkerInput):
        raise ProductionWorkerError(
            "PRCB_C2_WORKER_PRODUCT_INVALID",
            type(body).__name__,
        )
    _verify_job_request(payload, body.job_payload)
    build = execute_p6_model_training(
        body.training_rows,
        as_of_utc=body.as_of_utc,
        trained_at_utc=body.trained_at_utc,
    )
    managed = P6ManagedModelObject(
        object_ref_id=build.model.model_object_ref_id,
        managed_uri=build.model.model_artifact_uri,
        artifact_sha256=build.model.model_artifact_hash,
        sealed=True,
        gc_state="ACTIVE",
        deleted_at=None,
        sealed_at_utc=body.sealed_at_utc,
    )
    snapshot = build_p6_input_snapshot(
        factual_sources=body.factual_sources,
        p3_model_refs=body.p3_model_refs,
        scenario_context_refs=body.scenario_context_refs,
        target_scope=body.target_scope,
        subject_or_composition_ref=body.subject_or_composition_ref,
        forecast_origin_utc=body.forecast_origin_utc,
        as_of_utc=body.as_of_utc,
    )
    profile = P6ForecastExecutionProfile.from_canonical()
    forecast_request: P6ForecastRequestBinding | None = None
    if body.forecast_spec is not None:
        forecast_request = build_p6_forecast_request_binding(
            input_snapshot=snapshot,
            forecast_spec_id=_text(
                body.forecast_spec.get("forecast_spec_id"),
                field="forecast.forecast_spec_id",
            ),
            forecast_spec_version=_text(
                body.forecast_spec.get("forecast_spec_version"),
                field="forecast.forecast_spec_version",
            ),
            target_code=profile.target_code,
            horizon_spec={
                "type": profile.horizon_type,
                "steps": profile.horizon_steps,
                "target_session_order": build.target_session_order,
            },
            capability_model_id=build.model.capability_model_id,
            model_profile_id=profile.profile_id,
            model_profile_version=profile.profile_version,
            training_dataset_snapshot_id=(
                build.model.training_dataset_snapshot_id
            ),
            validation_dataset_snapshot_id=(
                build.model.validation_dataset_snapshot_id
            ),
            assumption_profile_id=_text(
                body.forecast_spec.get("assumption_profile_id"),
                field="forecast.assumption_profile_id",
            ),
            assumption_profile_version=_text(
                body.forecast_spec.get("assumption_profile_version"),
                field="forecast.assumption_profile_version",
            ),
        )
    counterfactual_request: P6CounterfactualRequestBinding | None = None
    if body.counterfactual_spec is not None:
        raw_bases = body.counterfactual_spec.get("base_product_refs")
        if not isinstance(raw_bases, list) or not all(
            isinstance(item, str) for item in raw_bases
        ):
            raise ProductionWorkerError(
                "PRCB_C2_PAYLOAD_INVALID",
                "counterfactual.base_product_refs",
            )
        interventions = _mapping(
            body.counterfactual_spec.get("interventions"),
            field="counterfactual.interventions",
        )
        held_fixed = _mapping(
            body.counterfactual_spec.get("held_fixed_assumptions"),
            field="counterfactual.held_fixed_assumptions",
        )
        counterfactual_request = build_p6_counterfactual_request_binding(
            input_snapshot=snapshot,
            base_product_refs=cast(list[str], raw_bases),
            scenario_definition_id=_uuid(
                body.counterfactual_spec.get("scenario_definition_id"),
                field="counterfactual.scenario_definition_id",
            ),
            interventions=interventions,
            held_fixed_assumptions=held_fixed,
            model_refs=(build.model.capability_model_id,),
            applicability_profile_ref=profile.applicability_profile_ref,
        )
    if forecast_request is None and counterfactual_request is None:
        raise ProductionWorkerError(
            "PRCB_C2_P6_REQUEST_REQUIRED",
            "forecast/counterfactual",
        )
    product = ProductionP6BuildWorkerProduct(
        model_build=build,
        managed_object=managed,
        input_snapshot=snapshot,
        forecast_request=forecast_request,
        counterfactual_request=counterfactual_request,
    )
    return WorkerResult(
        job_id=payload.job_id,
        request_hash=payload.request_hash,
        command=payload.command,
        status="SUCCEEDED",
        output=(
            build.model.capability_model_id,
            snapshot.input_snapshot_id,
            *(
                ()
                if forecast_request is None
                else (forecast_request.forecast_request_id,)
            ),
            *(
                ()
                if counterfactual_request is None
                else (counterfactual_request.counterfactual_request_id,)
            ),
        ),
        domain_payload=product,
    )


def _execute_p6_forecast(payload: WorkerPayload) -> WorkerResult:
    body = payload.domain_payload
    if not isinstance(body, ProductionP6ForecastWorkerInput):
        raise ProductionWorkerError(
            "PRCB_C2_WORKER_PRODUCT_INVALID",
            type(body).__name__,
        )
    _verify_job_request(payload, body.job_payload)
    value = execute_p6_forecast(
        request=body.request,
        input_snapshot=body.input_snapshot,
        model_build=body.model_build,
        managed_object=body.managed_object,
        published_at_utc=body.published_at_utc,
    )
    return WorkerResult(
        job_id=payload.job_id,
        request_hash=payload.request_hash,
        command=payload.command,
        status="SUCCEEDED",
        output=(value.forecast_result_id, value.logical_content_hash),
        domain_payload=value,
    )


def _execute_p6_counterfactual(payload: WorkerPayload) -> WorkerResult:
    body = payload.domain_payload
    if not isinstance(body, ProductionP6CounterfactualWorkerInput):
        raise ProductionWorkerError(
            "PRCB_C2_WORKER_PRODUCT_INVALID",
            type(body).__name__,
        )
    _verify_job_request(payload, body.job_payload)
    value = execute_p6_counterfactual(
        request=body.request,
        input_snapshot=body.input_snapshot,
        models=body.models,
        created_at_utc=body.created_at_utc,
    )
    return WorkerResult(
        job_id=payload.job_id,
        request_hash=payload.request_hash,
        command=payload.command,
        status="SUCCEEDED",
        output=(value.counterfactual_run_id, value.logical_content_hash),
        domain_payload=value,
    )


def execute(payload: WorkerPayload) -> WorkerResult:
    """Governed runtime worker handler. Unknown commands fail closed."""

    try:
        if payload.command == P1_BUILD_COMMAND:
            return _execute_p1(payload)
        if payload.command == P2_ATTRIBUTION_COMMAND:
            return _execute_p2_attribution(payload)
        if payload.command == P3_BUILD_COMMAND:
            return _execute_p3_build(payload)
        if payload.command == P3_ESTIMATE_COMMAND:
            return _execute_p3_estimate(payload)
        if payload.command == P4_ASSESSMENT_COMMAND:
            if isinstance(payload.domain_payload, ProductionP4BuildWorkerInput):
                return _execute_p4_build(payload)
            return _execute_p4_assessment(payload)
        if payload.command == P5_ASSESSMENT_COMMAND:
            if isinstance(payload.domain_payload, ProductionP5BuildWorkerInput):
                return _execute_p5_build(payload)
            return _execute_p5_assessment(payload)
        if payload.command == P6_BUILD_COMMAND:
            return _execute_p6_build(payload)
        if payload.command == P6_FORECAST_COMMAND:
            return _execute_p6_forecast(payload)
        if payload.command == P6_COUNTERFACTUAL_COMMAND:
            return _execute_p6_counterfactual(payload)
        return WorkerResult(
            job_id=payload.job_id,
            request_hash=payload.request_hash,
            command=payload.command,
            status="FAILED",
            error_code="PRCB_C2_DOMAIN_COMMAND_UNSUPPORTED",
        )
    except Exception as exc:
        code = getattr(exc, "code", "PRCB_C2_DOMAIN_EXECUTION_FAILED")
        return WorkerResult(
            job_id=payload.job_id,
            request_hash=payload.request_hash,
            command=payload.command,
            status="FAILED",
            error_code=str(code),
        )
