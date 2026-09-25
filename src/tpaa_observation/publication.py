"""M1 Batch 2 immutable SESSION publication domain.

This module binds the already-computed Batch 1 World/Metric products into an
immutable SESSION Release and CapabilityObservation projections. It deliberately
does not perform persistence or resolve "current/latest" authority. Concrete
repositories consume these frozen logical records.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid5

from tpaa_generated.dto import CapabilityObservationDTO
from tpaa_metric import MetricBatch, MetricContext, MetricResult
from tpaa_world import AircraftObservedWorld

RELEASE_NAMESPACE = UUID("98ca27c0-f551-47dc-9c96-eb5fd0be5366")
DEFINITION_NAMESPACE = UUID("12782b05-0d64-4bec-9892-235a48f8589d")
INSTANCE_NAMESPACE = UUID("b747e29a-6666-49df-b89d-0f95d3ad31d1")
OBSERVATION_NAMESPACE = UUID("8791211a-bffa-4eed-aa42-8a7252cb81f1")

SESSION_SCOPE = "SESSION"
CAPABILITY_ROUTE = "CAPABILITY_OBSERVATION"
CAPABILITY_LEVEL = "CAP_L1_OBSERVED"
OBSERVATION_SCHEMA_VERSION = "1.6.0"


class PublicationError(RuntimeError):
    """Deterministic fail-closed error for M1 publication construction."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _hash(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("ascii")).hexdigest()


def _canonical_uuid(value: str, *, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise PublicationError("M1_PUBLICATION_UUID_INVALID", f"{field}={value!r}") from exc
    canonical = str(parsed)
    if parsed.int == 0 or canonical != value:
        raise PublicationError("M1_PUBLICATION_UUID_INVALID", f"{field}={value!r}")
    return canonical


def _require_hash(value: str, *, field: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise PublicationError("M1_PUBLICATION_HASH_INVALID", f"{field}={value!r}")
    return value


@dataclass(frozen=True)
class AircraftPublicationIdentity:
    """Explicit persisted identities required by CapabilityObservationDTO."""

    aircraft_id: str
    aircraft_model_id: str
    aircraft_instance_id: str
    subject_entity_id: str
    capability_dimension: str
    capability_type: str

    def __post_init__(self) -> None:
        for field in (
            "aircraft_id",
            "aircraft_model_id",
            "aircraft_instance_id",
            "subject_entity_id",
        ):
            _canonical_uuid(getattr(self, field), field=field)
        if not self.capability_dimension.strip():
            raise PublicationError("M1_PUBLICATION_CAPABILITY_DIMENSION_MISSING", "")
        if not self.capability_type.strip():
            raise PublicationError("M1_PUBLICATION_CAPABILITY_TYPE_MISSING", "")


@dataclass(frozen=True)
class ImmutableMetricDefinition:
    metric_definition_id: str
    metric_code: str
    semantic_id: str
    semantic_version: int
    algorithm_id: str
    algorithm_version: str
    subject_type: str
    observation_lane: str
    publication_route: str
    value_kind: str
    structured_output_schema_id: str | None
    unit: str
    catalog_version: str
    catalog_hash: str
    definition_hash: str


@dataclass(frozen=True)
class EvidenceRefSnapshot:
    ref_class: str
    ref_id: str
    logical_hash: str


@dataclass(frozen=True)
class ImmutableEvidenceSet:
    evidence_set_id: str
    session_id: str
    episode_id: str
    stage_id: str | None
    start_session_time_us: int
    end_session_time_us: int
    refs: tuple[EvidenceRefSnapshot, ...]
    details: tuple[tuple[str, str], ...]
    logical_hash: str


@dataclass(frozen=True)
class ImmutableMetricInstance:
    metric_instance_id: str
    metric_definition_id: str
    metric_code: str
    session_id: str
    episode_id: str
    stage_id: str | None
    subject_entity_id: str
    context_id: str
    world_product_id: str
    world_logical_hash: str
    status: str
    reason_codes: tuple[str, ...]
    unit: str
    value_kind: str
    value_numeric: float | None
    value_structured_json: str | None
    evidence_set_id: str
    compute_version: str
    input_hash: str
    logical_hash: str

    def value(self) -> object | None:
        if self.value_structured_json is not None:
            return json.loads(self.value_structured_json)
        return self.value_numeric


@dataclass(frozen=True)
class CapabilityObservationRecord:
    observation_id: str
    release_id: str
    session_id: str
    episode_id: str
    stage_id: str | None
    identity: AircraftPublicationIdentity
    context_id: str
    metric_instance_id: str
    metric_code: str
    metric_semantic_id: str
    metric_semantic_version: int
    structured_output_schema_id: str | None
    unit: str
    value_kind: str
    value_numeric: float | None
    value_structured_json: str | None
    evidence_set_id: str
    observation_start_session_time_us: int
    observation_end_session_time_us: int
    coverage: float
    confidence: float
    eligibility_status: str
    exclusion_reason_code: str | None
    comparison_key_hash: str
    observation_schema_version: str = OBSERVATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not 0.0 <= self.coverage <= 1.0:
            raise PublicationError("M1_PUBLICATION_COVERAGE_INVALID", repr(self.coverage))
        if not 0.0 <= self.confidence <= 1.0:
            raise PublicationError("M1_PUBLICATION_CONFIDENCE_INVALID", repr(self.confidence))
        if self.eligibility_status not in {"ELIGIBLE", "EXCLUDED", "REVIEW_REQUIRED"}:
            raise PublicationError(
                "M1_PUBLICATION_ELIGIBILITY_INVALID",
                self.eligibility_status,
            )
        if self.value_kind == "STRUCTURED":
            if self.eligibility_status == "ELIGIBLE" and self.value_structured_json is None:
                raise PublicationError("M1_PUBLICATION_VALUE_SLOT_INVALID", self.metric_code)
            if self.value_numeric is not None:
                raise PublicationError("M1_PUBLICATION_VALUE_SLOT_INVALID", self.metric_code)
        elif self.value_kind == "NUMERIC":
            if self.eligibility_status == "ELIGIBLE" and self.value_numeric is None:
                raise PublicationError("M1_PUBLICATION_VALUE_SLOT_INVALID", self.metric_code)
            if self.value_structured_json is not None:
                raise PublicationError("M1_PUBLICATION_VALUE_SLOT_INVALID", self.metric_code)

    def dto(self) -> CapabilityObservationDTO:
        value: Any
        if self.value_structured_json is not None:
            value = json.loads(self.value_structured_json)
        else:
            value = self.value_numeric
        payload: CapabilityObservationDTO = {
            "aircraft_id": self.identity.aircraft_id,
            "aircraft_instance_id": self.identity.aircraft_instance_id,
            "aircraft_model_id": self.identity.aircraft_model_id,
            "capability_dimension": self.identity.capability_dimension,
            "capability_level": CAPABILITY_LEVEL,
            "capability_type": self.identity.capability_type,
            "comparison_key_hash": self.comparison_key_hash,
            "confidence": self.confidence,
            "context_id": self.context_id,
            "context_tags": {},
            "coverage": self.coverage,
            "eligibility_status": self.eligibility_status,
            "episode_id": self.episode_id,
            "evidence_set_id": self.evidence_set_id,
            "metric_code": self.metric_code,
            "metric_semantic_id": self.metric_semantic_id,
            "metric_semantic_version": self.metric_semantic_version,
            "observation_end_session_time_us": str(self.observation_end_session_time_us),
            "observation_id": self.observation_id,
            "observation_schema_version": self.observation_schema_version,
            "observation_start_session_time_us": str(self.observation_start_session_time_us),
            "observed_metric_instance_id": self.metric_instance_id,
            "release_id": self.release_id,
            "session_id": self.session_id,
            "subject_entity_id": self.identity.subject_entity_id,
            "unit": self.unit,
            "value_kind": self.value_kind,
        }
        if self.stage_id is not None:
            payload["stage_id"] = self.stage_id
        if self.structured_output_schema_id is not None:
            payload["structured_output_schema_id"] = self.structured_output_schema_id
        if self.exclusion_reason_code is not None:
            payload["exclusion_reason_code"] = self.exclusion_reason_code
        if value is not None:
            payload["value"] = value
        return payload


@dataclass(frozen=True)
class SessionRelease:
    """Immutable logical SESSION release before concrete persistence."""

    release_id: str
    release_no: int
    parent_release_id: str | None
    request_hash: str
    scope_type: str
    scope_key: str
    fixture_id: str
    session_id: str
    context_id: str
    context_version: str
    context_binding_hash: str
    catalog_version: str
    catalog_hash: str
    world_product_id: str
    world_logical_hash: str
    definitions: tuple[ImmutableMetricDefinition, ...]
    evidence_sets: tuple[ImmutableEvidenceSet, ...]
    metric_instances: tuple[ImmutableMetricInstance, ...]
    observations: tuple[CapabilityObservationRecord, ...]
    manifest_hash: str
    status: str = "VALIDATED"

    def __post_init__(self) -> None:
        _canonical_uuid(self.release_id, field="release_id")
        _require_hash(self.request_hash, field="request_hash")
        _require_hash(self.context_binding_hash, field="context_binding_hash")
        _require_hash(self.catalog_hash, field="catalog_hash")
        _require_hash(self.world_logical_hash, field="world_logical_hash")
        _require_hash(self.manifest_hash, field="manifest_hash")
        if self.scope_type != SESSION_SCOPE or self.scope_key != self.session_id:
            raise PublicationError("M1_PUBLICATION_SCOPE_INVALID", self.scope_key)
        if self.release_no < 1:
            raise PublicationError("M1_PUBLICATION_RELEASE_NO_INVALID", str(self.release_no))
        if self.status != "VALIDATED":
            raise PublicationError("M1_PUBLICATION_PRE_PUBLISH_STATUS_INVALID", self.status)

    def logical_membership(self) -> dict[str, object]:
        return {
            "release_id": self.release_id,
            "scope_type": self.scope_type,
            "scope_key": self.scope_key,
            "fixture_id": self.fixture_id,
            "session_id": self.session_id,
            "context_id": self.context_id,
            "context_version": self.context_version,
            "context_binding_hash": self.context_binding_hash,
            "catalog_version": self.catalog_version,
            "catalog_hash": self.catalog_hash,
            "world_product_id": self.world_product_id,
            "world_logical_hash": self.world_logical_hash,
            "definition_hashes": [item.definition_hash for item in self.definitions],
            "evidence_hashes": [item.logical_hash for item in self.evidence_sets],
            "metric_instance_hashes": [item.logical_hash for item in self.metric_instances],
            "observation_ids": [item.observation_id for item in self.observations],
            "manifest_hash": self.manifest_hash,
        }


@dataclass(frozen=True)
class ReplayComparison:
    release_id: str
    world_equal: bool
    metric_batch_equal: bool
    context_equal: bool
    exact_logical_products_equal: bool


def allocate_session_release_id(*, session_id: str, request_hash: str) -> str:
    """Allocate a deterministic release identity before World construction."""

    _canonical_uuid(session_id, field="session_id")
    _require_hash(request_hash, field="request_hash")
    return str(uuid5(RELEASE_NAMESPACE, f"{session_id}|{request_hash}"))


def _definition(context: MetricContext, metric_code: str) -> ImmutableMetricDefinition:
    authority = context.authority(metric_code)
    if authority.publication_route != CAPABILITY_ROUTE:
        raise PublicationError("M1_PUBLICATION_ROUTE_INVALID", metric_code)
    logical = {
        "metric_code": authority.metric_code,
        "semantic_id": authority.semantic_id,
        "semantic_version": authority.semantic_version,
        "algorithm_id": authority.algorithm_id,
        "algorithm_version": authority.algorithm_version,
        "subject_type": authority.subject_type,
        "observation_lane": authority.observation_lane,
        "publication_route": authority.publication_route,
        "value_kind": authority.value_kind,
        "structured_output_schema_id": authority.structured_output_schema_id,
        "unit": authority.unit,
        "catalog_version": context.catalog_version,
        "catalog_hash": context.catalog_sha256,
    }
    definition_hash = _hash(logical)
    return ImmutableMetricDefinition(
        metric_definition_id=str(uuid5(DEFINITION_NAMESPACE, definition_hash)),
        metric_code=authority.metric_code,
        semantic_id=authority.semantic_id,
        semantic_version=authority.semantic_version,
        algorithm_id=authority.algorithm_id,
        algorithm_version=authority.algorithm_version,
        subject_type=authority.subject_type,
        observation_lane=authority.observation_lane,
        publication_route=authority.publication_route,
        value_kind=authority.value_kind,
        structured_output_schema_id=authority.structured_output_schema_id,
        unit=authority.unit,
        catalog_version=context.catalog_version,
        catalog_hash=context.catalog_sha256,
        definition_hash=definition_hash,
    )


def _structured_json(result: MetricResult) -> str | None:
    if result.value_structured is None:
        return None
    return _canonical_json(result.value_structured.as_dict())


def _eligibility(result: MetricResult) -> tuple[str, str | None]:
    if result.status == "VALID":
        return "ELIGIBLE", None
    if result.status == "REVIEW_REQUIRED":
        return "REVIEW_REQUIRED", result.reason_codes[0] if result.reason_codes else None
    return "EXCLUDED", result.reason_codes[0] if result.reason_codes else result.status


def _evidence(
    *,
    result: MetricResult,
    world: AircraftObservedWorld,
) -> ImmutableEvidenceSet:
    refs = tuple(
        EvidenceRefSnapshot(ref.ref_class, ref.ref_id, ref.logical_hash)
        for ref in result.evidence.refs
    )
    logical = {
        "evidence_set_id": result.evidence.evidence_set_id,
        "session_id": world.session_id,
        "episode_id": world.episode_id,
        "stage_id": result.stage_id,
        "start_session_time_us": world.start_session_time_us,
        "end_session_time_us": world.end_session_time_us,
        "refs": [
            {"ref_class": ref.ref_class, "ref_id": ref.ref_id, "logical_hash": ref.logical_hash}
            for ref in refs
        ],
        "details": list(result.evidence.details),
        "metric_evidence_hash": result.evidence.logical_hash,
    }
    return ImmutableEvidenceSet(
        evidence_set_id=result.evidence.evidence_set_id,
        session_id=world.session_id,
        episode_id=world.episode_id,
        stage_id=result.stage_id,
        start_session_time_us=world.start_session_time_us,
        end_session_time_us=world.end_session_time_us,
        refs=refs,
        details=result.evidence.details,
        logical_hash=_hash(logical),
    )


def build_session_release(
    *,
    release_id: str,
    request_hash: str,
    release_no: int,
    parent_release_id: str | None,
    context: MetricContext,
    context_version: str,
    world: AircraftObservedWorld,
    batch: MetricBatch,
    identity: AircraftPublicationIdentity,
) -> SessionRelease:
    """Bind exact Batch 1 products into one immutable pre-publish SESSION Release."""

    canonical_release_id = _canonical_uuid(release_id, field="release_id")
    if not context_version.strip():
        raise PublicationError("M1_PUBLICATION_CONTEXT_VERSION_MISSING", "")
    if world.release_id != canonical_release_id:
        raise PublicationError(
            "M1_PUBLICATION_WORLD_RELEASE_MISMATCH",
            f"world={world.release_id} release={canonical_release_id}",
        )
    if identity.aircraft_id != world.aircraft_id or identity.aircraft_id != context.subject_id:
        raise PublicationError("M1_PUBLICATION_AIRCRAFT_IDENTITY_MISMATCH", identity.aircraft_id)
    if (
        context.session_id != world.session_id
        or batch.metric_context_id != context.metric_context_id
        or batch.world_product_id != world.world_product_id
    ):
        raise PublicationError("M1_PUBLICATION_BATCH_BINDING_MISMATCH", batch.logical_hash)
    if batch.publication_executed or batch.database_persistence_executed:
        raise PublicationError("M1_PUBLICATION_REQUIRES_STAGED_BATCH", batch.logical_hash)
    if not batch.results:
        raise PublicationError("M1_PUBLICATION_EMPTY_BATCH", batch.logical_hash)

    definitions = tuple(_definition(context, result.metric_code) for result in batch.results)
    definitions_by_code = {item.metric_code: item for item in definitions}
    evidence_sets = tuple(_evidence(result=result, world=world) for result in batch.results)
    evidence_by_id = {item.evidence_set_id: item for item in evidence_sets}

    metric_instances: list[ImmutableMetricInstance] = []
    observations: list[CapabilityObservationRecord] = []
    for result in batch.results:
        definition = definitions_by_code[result.metric_code]
        evidence = evidence_by_id[result.evidence.evidence_set_id]
        value_structured_json = _structured_json(result)
        instance_payload = {
            "release_id": canonical_release_id,
            "metric_definition_id": definition.metric_definition_id,
            "metric_code": result.metric_code,
            "session_id": world.session_id,
            "episode_id": world.episode_id,
            "stage_id": result.stage_id,
            "subject_entity_id": identity.subject_entity_id,
            "context_id": context.context_id,
            "world_product_id": world.world_product_id,
            "world_logical_hash": world.logical_content_hash,
            "status": result.status,
            "reason_codes": list(result.reason_codes),
            "unit": result.unit,
            "value_kind": result.value_kind,
            "value_numeric": result.value_numeric,
            "value_structured": (
                json.loads(value_structured_json) if value_structured_json is not None else None
            ),
            "evidence_set_id": evidence.evidence_set_id,
            "compute_version": result.algorithm_version,
            "input_hash": result.logical_hash,
        }
        instance_hash = _hash(instance_payload)
        metric_instance_id = str(uuid5(INSTANCE_NAMESPACE, instance_hash))
        metric_instances.append(
            ImmutableMetricInstance(
                metric_instance_id=metric_instance_id,
                metric_definition_id=definition.metric_definition_id,
                metric_code=result.metric_code,
                session_id=world.session_id,
                episode_id=world.episode_id,
                stage_id=result.stage_id,
                subject_entity_id=identity.subject_entity_id,
                context_id=context.context_id,
                world_product_id=world.world_product_id,
                world_logical_hash=world.logical_content_hash,
                status=result.status,
                reason_codes=result.reason_codes,
                unit=result.unit,
                value_kind=result.value_kind,
                value_numeric=result.value_numeric,
                value_structured_json=value_structured_json,
                evidence_set_id=evidence.evidence_set_id,
                compute_version=result.algorithm_version,
                input_hash=result.logical_hash,
                logical_hash=instance_hash,
            )
        )

        eligibility, exclusion = _eligibility(result)
        comparison_key_hash = _hash(
            {
                "session_id": world.session_id,
                "episode_id": world.episode_id,
                "stage_id": result.stage_id,
                "subject_entity_id": identity.subject_entity_id,
                "metric_semantic_id": result.semantic_id,
                "metric_semantic_version": result.semantic_version,
            }
        )
        observation_id = str(
            uuid5(
                OBSERVATION_NAMESPACE,
                f"{canonical_release_id}|{metric_instance_id}|{comparison_key_hash}",
            )
        )
        observations.append(
            CapabilityObservationRecord(
                observation_id=observation_id,
                release_id=canonical_release_id,
                session_id=world.session_id,
                episode_id=world.episode_id,
                stage_id=result.stage_id,
                identity=identity,
                context_id=context.context_id,
                metric_instance_id=metric_instance_id,
                metric_code=result.metric_code,
                metric_semantic_id=result.semantic_id,
                metric_semantic_version=result.semantic_version,
                structured_output_schema_id=definition.structured_output_schema_id,
                unit=result.unit,
                value_kind=result.value_kind,
                value_numeric=result.value_numeric,
                value_structured_json=value_structured_json,
                evidence_set_id=evidence.evidence_set_id,
                observation_start_session_time_us=world.start_session_time_us,
                observation_end_session_time_us=world.end_session_time_us,
                coverage=world.coverage,
                confidence=world.confidence,
                eligibility_status=eligibility,
                exclusion_reason_code=exclusion,
                comparison_key_hash=comparison_key_hash,
            )
        )

    context_binding_hash = _hash(
        {
            "context_id": context.context_id,
            "context_version": context_version,
            "profile_id": context.profile_id,
            "profile_sha256": context.profile_sha256,
            "input_refs": [
                {"class": ref.ref_class, "id": ref.ref_id, "hash": ref.logical_hash}
                for ref in context.input_refs
            ],
        }
    )
    manifest_payload = {
        "release_id": canonical_release_id,
        "release_no": release_no,
        "parent_release_id": parent_release_id,
        "scope_type": SESSION_SCOPE,
        "scope_key": world.session_id,
        "fixture_id": world.fixture_id,
        "session_id": world.session_id,
        "context_id": context.context_id,
        "context_version": context_version,
        "context_binding_hash": context_binding_hash,
        "catalog_version": context.catalog_version,
        "catalog_hash": context.catalog_sha256,
        "world_product_id": world.world_product_id,
        "world_logical_hash": world.logical_content_hash,
        "definition_hashes": [item.definition_hash for item in definitions],
        "evidence_hashes": [item.logical_hash for item in evidence_sets],
        "metric_instance_hashes": [item.logical_hash for item in metric_instances],
        "observation_ids": [item.observation_id for item in observations],
        "request_hash": request_hash,
    }
    manifest_hash = _hash(manifest_payload)
    return SessionRelease(
        release_id=canonical_release_id,
        release_no=release_no,
        parent_release_id=parent_release_id,
        request_hash=_require_hash(request_hash, field="request_hash"),
        scope_type=SESSION_SCOPE,
        scope_key=world.session_id,
        fixture_id=world.fixture_id,
        session_id=world.session_id,
        context_id=context.context_id,
        context_version=context_version,
        context_binding_hash=context_binding_hash,
        catalog_version=context.catalog_version,
        catalog_hash=context.catalog_sha256,
        world_product_id=world.world_product_id,
        world_logical_hash=world.logical_content_hash,
        definitions=definitions,
        evidence_sets=evidence_sets,
        metric_instances=tuple(metric_instances),
        observations=tuple(observations),
        manifest_hash=manifest_hash,
    )


def compare_replay(
    release: SessionRelease,
    *,
    context: MetricContext,
    context_version: str,
    world: AircraftObservedWorld,
    batch: MetricBatch,
) -> ReplayComparison:
    """Compare recomputed logical products only against release-bound identities."""

    context_equal = (
        release.context_id == context.context_id
        and release.context_version == context_version
        and release.catalog_hash == context.catalog_sha256
        and not context.latest_fallback_used
    )
    world_equal = (
        release.world_logical_hash == world.logical_content_hash
        and release.world_product_id == world.world_product_id
        and world.release_id == release.release_id
    )
    expected_metric_hashes = [item.input_hash for item in release.metric_instances]
    actual_metric_hashes = [result.logical_hash for result in batch.results]
    metric_batch_equal = (
        release.session_id == world.session_id
        and batch.metric_context_id == context.metric_context_id
        and expected_metric_hashes == actual_metric_hashes
    )
    return ReplayComparison(
        release_id=release.release_id,
        world_equal=world_equal,
        metric_batch_equal=metric_batch_equal,
        context_equal=context_equal,
        exact_logical_products_equal=world_equal and metric_batch_equal and context_equal,
    )
