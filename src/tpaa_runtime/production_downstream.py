"""ED2 B2 production prerequisite assembly and durable publication.

The parent process performs exact DB/object-store projection and persistence only.
P3/P4/P5/P6 domain construction itself is dispatched to the governed worker.
No qualification seed module is imported by this product path.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID, uuid5

from tpaa_application import (
    ED2AssessmentResultRepository,
    P2PersistenceRepository,
    P3PersistenceRepository,
    P4P5ComputeInputRepository,
    P4P5PersistenceRepository,
    P6PersistenceRepository,
)
from tpaa_application.ed2_assessment_result import assessment_result_from_profile
from tpaa_assessment import (
    P2ArtifactBinding,
    P2AttributionSpec,
    P2AuthorityPolicy,
    P2CohortRow,
    P2CohortSnapshot,
    P2ExecutionProfile,
    P2FactorFeatureSet,
    P2ReferenceCondition,
    P4SubjectSource,
    build_p2_input_bundle,
    materialize_factor_feature_set,
)
from tpaa_assessment.ed2_profile import (
    ED2_ASSESSMENT_PROFILE_ID,
    ED2_ASSESSMENT_PROFILE_SCHEMA,
    ED2_ASSESSMENT_PROFILE_VERSION,
    ed2_training_assessment_profile,
)
from tpaa_capability import (
    P6CapabilityTrainingRow,
    P6ContextRef,
    P6FactualSourceRevision,
    P6P3ModelRef,
)
from tpaa_context import M8AuthorityPolicy, M8RoleModelBinding
from tpaa_longitudinal import P3AdjustedEstimateInput
from tpaa_storage.canonical_rows import CanonicalRowRepository
from tpaa_storage.object_store import LocalObjectStore
from tpaa_storage.product_identity import product_object_ref_id
from tpaa_world import M8EvidenceRef, M8WorldFactRef

from .production_worker import (
    ProductionP3BuildWorkerInput,
    ProductionP3BuildWorkerProduct,
    ProductionP4AssessmentWorkerProduct,
    ProductionP4BuildWorkerInput,
    ProductionP5AssessmentWorkerProduct,
    ProductionP5BuildWorkerInput,
    ProductionP6BuildWorkerInput,
    ProductionP6BuildWorkerProduct,
)

_CONTEXT_NAMESPACE = UUID("a276879f-522f-4df8-93c0-b979bfa72610")
_P2_COHORT_NAMESPACE = UUID("4d8d4ae0-7392-4a77-b3c4-16cf0b43d236")
_P3_SEGMENT_NAMESPACE = UUID("34d30785-a65c-4c55-85d3-ab2581427e23")
_P3_VALIDATION_NAMESPACE = UUID("7ce308f9-f24b-4bd0-863b-653fab8873f8")
_P3_TRAINING_NAMESPACE = UUID("3af4ed3d-0396-4b7f-b250-25946dd299ca")
_P3_CONFIG_NAMESPACE = UUID("98e2ee10-6cc4-4631-8863-3a7b3aba54b1")
_P3_SCOPE_NAMESPACE = UUID("d31c8c61-b532-4c38-849b-2947a672ab0d")
_P3_ASSIGNMENT_NAMESPACE = UUID("b457cd4f-d31b-4a18-907d-e44a3b99d1bd")


class ProductionDownstreamError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class ProductionP2Prepared:
    dataset_snapshot_id: str
    target_observation_id: str


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        raise ProductionDownstreamError("ED2_B2_INPUT_INVALID", field)
    return dict(cast(Mapping[str, object], value))


def _texts(value: object, field: str) -> tuple[str, ...]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise ProductionDownstreamError("ED2_B2_INPUT_INVALID", field)
    result = tuple(cast(Sequence[str], value))
    if len(set(result)) != len(result):
        raise ProductionDownstreamError("ED2_B2_IDENTITY_DUPLICATE", field)
    return result


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ProductionDownstreamError("ED2_B2_INPUT_INVALID", field)
    if value.upper() in {"CURRENT", "LATEST", "DEFAULT"}:
        raise ProductionDownstreamError(
            "ED2_B2_POINTER_FALLBACK_FORBIDDEN",
            f"{field}={value}",
        )
    return value


def _optional_text(value: object, field: str) -> str | None:
    return None if value is None else _text(value, field)


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProductionDownstreamError("ED2_B2_INPUT_INVALID", field)
    return value


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float, Decimal),
    ):
        raise ProductionDownstreamError("ED2_B2_INPUT_INVALID", field)
    result = float(value)
    if result != result or result in {float("inf"), float("-inf")}:
        raise ProductionDownstreamError("ED2_B2_INPUT_INVALID", field)
    return result


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ProductionDownstreamError(
            "ED2_B2_CANONICAL_JSON_INVALID",
            type(exc).__name__,
        ) from exc


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _uuid5(namespace: UUID, value: object) -> str:
    return str(uuid5(namespace, _hash(value)))


def _utc_text(value: object, field: str) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ProductionDownstreamError("ED2_B2_TIME_INVALID", field)
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    text = _text(value, field)
    if not text.endswith("Z") or "T" not in text:
        raise ProductionDownstreamError("ED2_B2_TIME_INVALID", field)
    try:
        datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise ProductionDownstreamError("ED2_B2_TIME_INVALID", field) from exc
    return text


def _persist_object_reference(
    rows: CanonicalRowRepository,
    object_store: LocalObjectStore,
    *,
    logical_uri: str,
    data: bytes,
) -> tuple[str, str]:
    digest = hashlib.sha256(data).hexdigest()
    object_ref_id = product_object_ref_id(logical_uri, digest)
    stored = object_store.put_bytes(logical_uri, data)
    if stored.artifact_sha256 != digest:
        raise ProductionDownstreamError(
            "ED2_B2_MANAGED_OBJECT_HASH_MISMATCH",
            logical_uri,
        )
    expected: dict[str, object] = {
        "managed_uri": logical_uri,
        "media_type": "application/json",
        "size_bytes": len(data),
        "artifact_sha256": digest,
        "logical_content_hash": digest,
        "storage_backend": "LOCAL_OBJECT_STORE",
        "sealed": True,
        "gc_state": "ACTIVE",
        "gc_state_version": 0,
        "deleted_at": None,
    }
    current = rows.one(
        "registry.object_reference",
        where={"object_ref_id": object_ref_id},
        columns=tuple(expected),
    )
    if current is None:
        rows.insert(
            "registry.object_reference",
            {"object_ref_id": object_ref_id, **expected},
        )
    elif any(current[key] != value for key, value in expected.items()):
        raise ProductionDownstreamError(
            "ED2_B2_MANAGED_OBJECT_IMMUTABLE_CONFLICT",
            object_ref_id,
        )
    return object_ref_id, digest


def _context_artifact_bytes(
    rows: CanonicalRowRepository,
    object_store: LocalObjectStore,
    *,
    artifact_kind: str,
    logical_key: str,
    artifact_version: str,
    schema_version: str,
    data: bytes,
) -> P2ArtifactBinding:
    digest = hashlib.sha256(data).hexdigest()
    identity = {
        "artifact_kind": artifact_kind,
        "logical_key": logical_key,
        "artifact_version": artifact_version,
        "schema_version": schema_version,
        "artifact_sha256": digest,
    }
    context_artifact_id = _uuid5(_CONTEXT_NAMESPACE, identity)
    logical_uri = (
        "tpaa-object://production-context/"
        f"{context_artifact_id}.json"
    )
    object_ref_id, stored_hash = _persist_object_reference(
        rows,
        object_store,
        logical_uri=logical_uri,
        data=data,
    )
    if stored_hash != digest:
        raise AssertionError("stored context-artifact hash drift")
    expected: dict[str, object] = {
        "artifact_kind": artifact_kind,
        "logical_key": logical_key,
        "artifact_version": artifact_version,
        "object_ref_id": object_ref_id,
        "artifact_sha256": digest,
        "schema_version": schema_version,
        "status": "ACTIVE",
    }
    current = rows.one(
        "registry.context_artifact",
        where={"context_artifact_id": context_artifact_id},
        columns=tuple(expected),
    )
    if current is None:
        rows.insert(
            "registry.context_artifact",
            {"context_artifact_id": context_artifact_id, **expected},
        )
    elif any(current[key] != value for key, value in expected.items()):
        raise ProductionDownstreamError(
            "ED2_B2_CONTEXT_ARTIFACT_IMMUTABLE_CONFLICT",
            context_artifact_id,
        )
    return P2ArtifactBinding(
        context_artifact_id=context_artifact_id,
        object_ref_id=object_ref_id,
        artifact_kind=artifact_kind,
        logical_key=logical_key,
        artifact_version=artifact_version,
        schema_version=schema_version,
        artifact_sha256=digest,
        status="ACTIVE",
        sealed=True,
    )


def _context_artifact_from_spec(
    rows: CanonicalRowRepository,
    object_store: LocalObjectStore,
    *,
    spec: Mapping[str, object],
    artifact_kind: str,
    logical_key_prefix: str,
    schema_version: str,
    exact_logical_key: str | None = None,
) -> P2ArtifactBinding:
    logical_key = _text(spec.get("logical_key"), "logical_key")
    version = _text(spec.get("artifact_version"), "artifact_version")
    requested_schema = _text(spec.get("schema_version"), "schema_version")
    payload = _mapping(spec.get("payload"), "payload")
    if (
        (exact_logical_key is not None and logical_key != exact_logical_key)
        or not logical_key.startswith(logical_key_prefix)
        or requested_schema != schema_version
    ):
        raise ProductionDownstreamError(
            "ED2_B2_CONTEXT_ARTIFACT_PROFILE_MISMATCH",
            logical_key,
        )
    return _context_artifact_bytes(
        rows,
        object_store,
        artifact_kind=artifact_kind,
        logical_key=logical_key,
        artifact_version=version,
        schema_version=requested_schema,
        data=_canonical_bytes(payload),
    )


def _ready_world_refs(
    rows: CanonicalRowRepository,
    *,
    release_id: str,
    episode_id: str,
) -> tuple[str, ...]:
    products = rows.many(
        "world.world_product_manifest",
        where={
            "release_id": release_id,
            "episode_id": episode_id,
            "status": "READY",
        },
        columns=("world_product_id",),
        order_by=("world_product_id",),
    )
    return tuple(str(row["world_product_id"]) for row in products)


def prepare_p2_compute_input(
    rows: CanonicalRowRepository,
    object_store: LocalObjectStore,
    payload: Mapping[str, object],
) -> ProductionP2Prepared:
    policy = P2AuthorityPolicy.from_canonical()
    profile = P2ExecutionProfile.from_canonical()
    repository = P2PersistenceRepository(rows, object_store=object_store)

    target_id = _text(
        payload.get("target_observation_id"),
        "target_observation_id",
    )
    cohort_ids = _texts(
        payload.get("cohort_observation_ids"),
        "cohort_observation_ids",
    )
    if target_id in cohort_ids:
        raise ProductionDownstreamError(
            "ED2_B2_P2_TARGET_IN_COHORT",
            target_id,
        )
    target = repository.exact_source_observation(target_id)
    cohort_observations = tuple(
        repository.exact_source_observation(observation_id)
        for observation_id in cohort_ids
    )
    feature_spec = _context_artifact_from_spec(
        rows,
        object_store,
        spec=_mapping(payload.get("feature_spec"), "feature_spec"),
        artifact_kind=policy.feature_artifact_kind,
        logical_key_prefix=policy.feature_logical_key_prefix,
        schema_version=policy.feature_schema_version,
    )
    reference_binding = _context_artifact_from_spec(
        rows,
        object_store,
        spec=_mapping(
            payload.get("reference_condition"),
            "reference_condition",
        ),
        artifact_kind=policy.reference_artifact_kind,
        logical_key_prefix=policy.reference_logical_key_prefix,
        schema_version=policy.reference_schema_version,
    )
    attribution_binding = _context_artifact_from_spec(
        rows,
        object_store,
        spec=_mapping(payload.get("attribution_spec"), "attribution_spec"),
        artifact_kind=policy.attribution_artifact_kind,
        logical_key_prefix=policy.attribution_logical_key_prefix,
        schema_version=policy.attribution_schema_version,
        exact_logical_key=profile.attribution_spec_id,
    )
    if attribution_binding.artifact_version != profile.attribution_spec_version:
        raise ProductionDownstreamError(
            "ED2_B2_P2_ATTRIBUTION_VERSION_DRIFT",
            attribution_binding.artifact_version,
        )

    factor_order = _texts(payload.get("factor_order"), "factor_order")
    factor_values_raw = _mapping(
        payload.get("factor_values_by_observation"),
        "factor_values_by_observation",
    )
    factor_values = {
        observation_id: _mapping(
            raw,
            f"factor_values_by_observation.{observation_id}",
        )
        for observation_id, raw in factor_values_raw.items()
    }
    expected_factor_ids = {target_id, *cohort_ids}
    if set(factor_values) != expected_factor_ids:
        raise ProductionDownstreamError(
            "ED2_B2_P2_FACTOR_MEMBERSHIP_MISMATCH",
            ",".join(sorted(set(factor_values) ^ expected_factor_ids)),
        )
    reference_raw = _mapping(
        payload.get("reference_factor_values"),
        "reference_factor_values",
    )
    if set(reference_raw) != set(factor_order):
        raise ProductionDownstreamError(
            "ED2_B2_P2_REFERENCE_FACTOR_MISMATCH",
            ",".join(sorted(set(reference_raw) ^ set(factor_order))),
        )
    reference_factors = {
        factor: _number(
            reference_raw[factor],
            f"reference_factor_values.{factor}",
        )
        for factor in factor_order
    }
    as_of_utc = _utc_text(payload.get("as_of_utc"), "as_of_utc")
    cohort_spec_id = _text(payload.get("cohort_spec_id"), "cohort_spec_id")
    cohort_spec_version = _text(
        payload.get("cohort_spec_version"),
        "cohort_spec_version",
    )
    dimensions: tuple[tuple[str, str | int], ...] = (
        ("capability_type", target.capability_type),
        ("metric_semantic_id", target.metric_semantic_id),
        ("metric_semantic_version", target.metric_semantic_version),
        ("unit", target.unit),
        ("aircraft_model_id", target.aircraft_model_id),
        ("comparison_key_hash", target.comparison_key_hash),
    )
    latest_knowledge = max(
        (item.knowledge_time_utc for item in cohort_observations),
        default=target.knowledge_time_utc,
    )
    cohort_material = {
        "cohort_spec_id": cohort_spec_id,
        "cohort_spec_version": cohort_spec_version,
        "comparability_dimensions": [
            {"name": name, "value": value} for name, value in dimensions
        ],
        "knowledge_cutoff_utc": latest_knowledge,
        "observation_ids": list(cohort_ids),
        "episode_ids": sorted(
            {item.episode_id for item in cohort_observations}
        ),
        "subject_ids": sorted(
            {item.subject_entity_id for item in cohort_observations}
        ),
    }
    cohort = P2CohortSnapshot(
        dataset_snapshot_id=_uuid5(_P2_COHORT_NAMESPACE, cohort_material),
        snapshot_type=policy.cohort_snapshot_type,
        data_hash=_hash(cohort_material),
        schema_version="1.9.0",
        frozen=True,
        cohort_spec_id=cohort_spec_id,
        cohort_spec_version=cohort_spec_version,
        comparability_dimensions=dimensions,
        knowledge_cutoff_utc=latest_knowledge,
        raw_record_count=len(cohort_observations),
        observation_count=len(cohort_observations),
        independent_subject_count=len(
            {item.subject_entity_id for item in cohort_observations}
        ),
        effective_evidence_count=float(len(cohort_observations)),
        observation_ids=cohort_ids,
        episode_ids=tuple(
            sorted({item.episode_id for item in cohort_observations})
        ),
        subject_ids=tuple(
            sorted({item.subject_entity_id for item in cohort_observations})
        ),
    )
    bundle = build_p2_input_bundle(
        target=target,
        feature_spec=feature_spec,
        reference_condition=P2ReferenceCondition(
            reference_condition_id=reference_binding.context_artifact_id,
            binding=reference_binding,
        ),
        cohort=cohort,
        attribution_spec=P2AttributionSpec(
            attribution_spec_id=profile.attribution_spec_id,
            attribution_spec_version=profile.attribution_spec_version,
            model_plugin=profile.model_plugin,
            model_plugin_version=profile.model_plugin_version,
            uncertainty_method=profile.uncertainty_method,
            uncertainty_level=profile.uncertainty_level,
            binding=attribution_binding,
        ),
        as_of_utc=as_of_utc,
    )

    def feature(
        observation_id: str,
    ) -> P2FactorFeatureSet:
        observation = (
            target
            if observation_id == target_id
            else next(
                item
                for item in cohort_observations
                if item.observation_id == observation_id
            )
        )
        values = factor_values[observation_id]
        if set(values) != set(factor_order):
            raise ProductionDownstreamError(
                "ED2_B2_P2_FACTOR_SHAPE_MISMATCH",
                observation_id,
            )
        return materialize_factor_feature_set(
            source=observation,
            feature_spec=feature_spec,
            factor_order=factor_order,
            factor_values={
                factor: (
                    None
                    if values[factor] is None
                    else _number(
                        values[factor],
                        f"factor_values.{observation_id}.{factor}",
                    )
                )
                for factor in factor_order
            },
            world_refs=_ready_world_refs(
                rows,
                release_id=observation.release_id,
                episode_id=observation.episode_id,
            ),
            confidence=observation.confidence,
            created_at=as_of_utc,
            reference_condition_id=reference_binding.context_artifact_id,
            profile=profile,
        )

    target_feature = feature(target_id)
    cohort_rows = tuple(
        P2CohortRow(
            observation=observation,
            feature_set=feature(observation.observation_id),
        )
        for observation in cohort_observations
    )
    repository.register_workspace_inputs(
        bundle,
        target_feature,
        cohort_rows=cohort_rows,
        reference_factor_values=reference_factors,
    )
    rebuilt = repository.exact_compute_input(cohort.dataset_snapshot_id)
    if (
        rebuilt.input_bundle != bundle
        or rebuilt.target_feature_set != target_feature
        or rebuilt.cohort_rows != cohort_rows
        or rebuilt.reference_factor_values != reference_factors
    ):
        raise ProductionDownstreamError(
            "ED2_B2_P2_RESTART_REBUILD_FAILED",
            cohort.dataset_snapshot_id,
        )
    return ProductionP2Prepared(
        dataset_snapshot_id=cohort.dataset_snapshot_id,
        target_observation_id=target_id,
    )


def _release_status(rows: CanonicalRowRepository, release_id: str) -> str:
    row = rows.one(
        "registry.analysis_release",
        where={"release_id": release_id},
        columns=("status",),
    )
    if row is None:
        raise ProductionDownstreamError(
            "ED2_B2_RELEASE_NOT_FOUND",
            release_id,
        )
    return str(row["status"])


def _session_occurrence(
    rows: CanonicalRowRepository,
    session_id: str,
    overrides: Mapping[str, object],
) -> str:
    row = rows.one(
        "registry.training_session",
        where={"session_id": session_id},
        columns=("start_occurred_at_utc",),
    )
    if row is None:
        raise ProductionDownstreamError(
            "ED2_B2_SESSION_NOT_FOUND",
            session_id,
        )
    if row["start_occurred_at_utc"] is not None:
        return _utc_text(
            row["start_occurred_at_utc"],
            "training_session.start_occurred_at_utc",
        )
    if session_id not in overrides:
        raise ProductionDownstreamError(
            "ED2_B2_SESSION_OCCURRENCE_REQUIRED",
            session_id,
        )
    return _utc_text(
        overrides[session_id],
        f"session_occurred_at_utc_by_session.{session_id}",
    )


def _ensure_session_order_authority(
    rows: CanonicalRowRepository,
    *,
    aircraft_id: str,
    session_ids: tuple[str, ...],
    session_order_by_session: Mapping[str, object],
    specification: Mapping[str, object],
) -> tuple[str, dict[str, tuple[str, int]]]:
    if set(session_order_by_session) != set(session_ids):
        raise ProductionDownstreamError(
            "ED2_B2_SESSION_ORDER_MEMBERSHIP_MISMATCH",
            aircraft_id,
        )
    selector = _mapping(
        specification.get("selector_json"),
        "selector_json",
    )
    scope_material = {
        "aircraft_id": aircraft_id,
        "scope_code": _text(specification.get("scope_code"), "scope_code"),
        "scope_type": _text(specification.get("scope_type"), "scope_type"),
        "subject_kind": _text(
            specification.get("subject_kind"),
            "subject_kind",
        ),
        "selector_json": selector,
        "selector_language_version": _text(
            specification.get("selector_language_version"),
            "selector_language_version",
        ),
        "scope_revision": _integer(
            specification.get("scope_revision"),
            "scope_revision",
        ),
    }
    scope_id = _uuid5(_P3_SCOPE_NAMESPACE, scope_material)
    expected_scope: dict[str, object] = {
        "scope_code": scope_material["scope_code"],
        "scope_type": scope_material["scope_type"],
        "subject_kind": scope_material["subject_kind"],
        "selector_json": selector,
        "selector_hash": _hash(selector),
        "selector_language_version": scope_material[
            "selector_language_version"
        ],
        "scope_revision": scope_material["scope_revision"],
        "status": "ACTIVE",
        "supersedes_scope_id": None,
        "description": _optional_text(
            specification.get("description"),
            "description",
        ),
    }
    current = rows.one(
        "registry.session_order_scope",
        where={"session_order_scope_id": scope_id},
        columns=tuple(expected_scope),
    )
    if current is None:
        rows.insert(
            "registry.session_order_scope",
            {"session_order_scope_id": scope_id, **expected_scope},
            field_kinds={"selector_json": "json"},
        )
    else:
        normalized_scope = dict(current)
        selector_value = normalized_scope.get("selector_json")
        if isinstance(selector_value, str):
            normalized_scope["selector_json"] = json.loads(selector_value)
        if any(
            normalized_scope[key] != value
            for key, value in expected_scope.items()
        ):
            raise ProductionDownstreamError(
                "ED2_B2_SESSION_ORDER_SCOPE_CONFLICT",
                scope_id,
            )
    assignments: dict[str, tuple[str, int]] = {}
    seen_orders: set[int] = set()
    for session_id in session_ids:
        order_value = _integer(
            session_order_by_session[session_id],
            f"session_order_by_session.{session_id}",
        )
        if order_value < 0 or order_value in seen_orders:
            raise ProductionDownstreamError(
                "ED2_B2_SESSION_ORDER_INVALID",
                f"{session_id}:{order_value}",
            )
        seen_orders.add(order_value)
        assignment_id = _uuid5(
            _P3_ASSIGNMENT_NAMESPACE,
            {
                "scope_id": scope_id,
                "session_id": session_id,
                "order_value": order_value,
            },
        )
        expected_assignment: dict[str, object] = {
            "session_order_scope_id": scope_id,
            "session_id": session_id,
            "order_value": order_value,
            "source": "MANUAL_REVIEWED",
            "revision_no": 1,
            "supersedes_assignment_id": None,
            "is_current": True,
            "reason": "ED2_B2_EXPLICIT_LONGITUDINAL_ORDER",
            "operator_ref": None,
        }
        current_assignment = rows.one(
            "registry.session_order_assignment",
            where={"assignment_id": assignment_id},
            columns=tuple(expected_assignment),
        )
        if current_assignment is None:
            rows.insert(
                "registry.session_order_assignment",
                {"assignment_id": assignment_id, **expected_assignment},
            )
        elif any(
            current_assignment[key] != value
            for key, value in expected_assignment.items()
        ):
            raise ProductionDownstreamError(
                "ED2_B2_SESSION_ORDER_ASSIGNMENT_CONFLICT",
                assignment_id,
            )
        assignments[session_id] = (assignment_id, order_value)
    return scope_id, assignments


def _ensure_configuration_snapshot(
    rows: CanonicalRowRepository,
    *,
    aircraft_id: str,
    anchor_session_id: str,
    specification: Mapping[str, object],
) -> tuple[str, str]:
    configuration_id = _text(
        specification.get("aircraft_configuration_id"),
        "aircraft_configuration_id",
    )
    try:
        UUID(configuration_id)
    except ValueError as exc:
        raise ProductionDownstreamError(
            "ED2_B2_CONFIGURATION_ID_INVALID",
            configuration_id,
        ) from exc
    snapshot_json = _mapping(
        specification.get("snapshot_json"),
        "configuration.snapshot_json",
    )
    snapshot_hash = _hash(snapshot_json)
    snapshot_id = _uuid5(
        _P3_CONFIG_NAMESPACE,
        {
            "aircraft_id": aircraft_id,
            "aircraft_configuration_id": configuration_id,
            "snapshot_hash": snapshot_hash,
        },
    )
    expected: dict[str, object] = {
        "aircraft_configuration_id": configuration_id,
        "aircraft_id": aircraft_id,
        "session_id": anchor_session_id,
        "effective_session_time_us": _integer(
            specification.get("effective_session_time_us"),
            "effective_session_time_us",
        ),
        "snapshot_json": snapshot_json,
        "snapshot_hash": snapshot_hash,
    }
    current = rows.one(
        "master.aircraft_configuration_snapshot",
        where={"snapshot_id": snapshot_id},
        columns=tuple(expected),
    )
    if current is None:
        rows.insert(
            "master.aircraft_configuration_snapshot",
            {"snapshot_id": snapshot_id, **expected},
            field_kinds={"snapshot_json": "json"},
        )
    else:
        normalized_snapshot = dict(current)
        snapshot_value = normalized_snapshot.get("snapshot_json")
        if isinstance(snapshot_value, str):
            normalized_snapshot["snapshot_json"] = json.loads(snapshot_value)
        if any(
            normalized_snapshot[key] != value
            for key, value in expected.items()
        ):
            raise ProductionDownstreamError(
                "ED2_B2_CONFIGURATION_SNAPSHOT_CONFLICT",
                snapshot_id,
            )
    return snapshot_id, snapshot_hash


def prepare_p3_build_worker_input(
    rows: CanonicalRowRepository,
    object_store: LocalObjectStore,
    *,
    job_payload: Mapping[str, object],
    production_input: Mapping[str, object],
) -> ProductionP3BuildWorkerInput:
    p2_ids = _texts(
        production_input.get("p2_estimate_ids"),
        "p2_estimate_ids",
    )
    if not p2_ids:
        raise ProductionDownstreamError(
            "ED2_B2_P3_HISTORY_REQUIRED",
            "p2_estimate_ids",
        )
    p2 = P2PersistenceRepository(rows, object_store=object_store)
    estimates = tuple(p2.exact_adjusted_estimate(item) for item in p2_ids)
    aircraft_ids = {item.aircraft_id for item in estimates}
    capability_types = {item.capability_type for item in estimates}
    reference_ids = {item.reference_condition_id for item in estimates}
    if (
        len(aircraft_ids) != 1
        or len(capability_types) != 1
        or len(reference_ids) != 1
    ):
        raise ProductionDownstreamError(
            "ED2_B2_P3_HISTORY_DOMAIN_DRIFT",
            ",".join(p2_ids),
        )
    aircraft_id = next(iter(aircraft_ids))
    observation_pairs = tuple(
        (
            p2.exact_source_observation(item.source_observation_id),
            rows.one(
                "metric.capability_observation",
                where={"observation_id": item.source_observation_id},
                columns=("session_id", "episode_id"),
            ),
        )
        for item in estimates
    )
    if any(row is None for _, row in observation_pairs):
        raise ProductionDownstreamError(
            "ED2_B2_P3_SOURCE_OBSERVATION_NOT_FOUND",
            ",".join(p2_ids),
        )
    typed_pairs = cast(
        tuple[tuple[object, dict[str, object]], ...],
        observation_pairs,
    )
    session_ids = tuple(
        str(row["session_id"]) for _, row in typed_pairs
    )
    if len(set(session_ids)) != len(session_ids):
        raise ProductionDownstreamError(
            "ED2_B2_P3_DISTINCT_SESSION_REQUIRED",
            ",".join(session_ids),
        )
    order_mapping = _mapping(
        production_input.get("session_order_by_session"),
        "session_order_by_session",
    )
    scope_id, assignments = _ensure_session_order_authority(
        rows,
        aircraft_id=aircraft_id,
        session_ids=session_ids,
        session_order_by_session=order_mapping,
        specification=_mapping(
            production_input.get("session_order_scope"),
            "session_order_scope",
        ),
    )
    config_id, config_hash = _ensure_configuration_snapshot(
        rows,
        aircraft_id=aircraft_id,
        anchor_session_id=session_ids[0],
        specification=_mapping(
            production_input.get("configuration"),
            "configuration",
        ),
    )
    occurrences = _mapping(
        production_input.get("session_occurred_at_utc_by_session"),
        "session_occurred_at_utc_by_session",
    )
    p3_inputs: list[P3AdjustedEstimateInput] = []
    for estimate, (observation_raw, row) in zip(
        estimates,
        typed_pairs,
        strict=True,
    ):
        from tpaa_assessment import P1ObservationInput

        if not isinstance(observation_raw, P1ObservationInput):
            raise TypeError("expected P1ObservationInput")
        observation = observation_raw
        session_id = str(row["session_id"])
        _, session_order = assignments[session_id]
        p3_inputs.append(
            P3AdjustedEstimateInput(
                estimate_id=estimate.estimate_id,
                p2_release_id=estimate.p2_release_id,
                p2_release_status=_release_status(
                    rows,
                    estimate.p2_release_id,
                ),
                source_observation_id=estimate.source_observation_id,
                source_release_id=estimate.source_release_id,
                source_release_status=_release_status(
                    rows,
                    estimate.source_release_id,
                ),
                attribution_run_id=estimate.attribution_run_id,
                aircraft_id=estimate.aircraft_id,
                aircraft_model_id=observation.aircraft_model_id,
                configuration_snapshot_id=config_id,
                configuration_snapshot_hash=config_hash,
                configuration_key=f"AIRCRAFT_CONFIG_SHA256:{config_hash}",
                session_id=session_id,
                episode_id=str(row["episode_id"]),
                session_occurred_at_utc=_session_occurrence(
                    rows,
                    session_id,
                    occurrences,
                ),
                session_order_scope_id=scope_id,
                session_order_scope_status="ACTIVE",
                session_order_assignment_current=True,
                session_order=session_order,
                capability_type=estimate.capability_type,
                metric_semantic_id=observation.metric_semantic_id,
                metric_semantic_version=observation.metric_semantic_version,
                comparison_key_hash=observation.comparison_key_hash,
                reference_condition_id=estimate.reference_condition_id,
                adjusted_value=estimate.adjusted_value,
                unit=estimate.unit,
                uncertainty_lower=estimate.uncertainty_lower,
                uncertainty_upper=estimate.uncertainty_upper,
                factor_effects=estimate.factor_effect_mapping(),
                claim_level=estimate.claim_level,
                status=estimate.status,
                evidence_set_id=estimate.evidence_set_id,
                knowledge_time_utc=observation.knowledge_time_utc,
                estimate_time=estimate.estimate_time,
                created_at=estimate.created_at,
            )
        )
    as_of_utc = _utc_text(
        production_input.get("as_of_utc"),
        "as_of_utc",
    )
    segment_id = _uuid5(
        _P3_SEGMENT_NAMESPACE,
        {
            "p2_estimate_ids": list(p2_ids),
            "scope_id": scope_id,
            "configuration_snapshot_id": config_id,
            "as_of_utc": as_of_utc,
        },
    )
    training_id = _uuid5(
        _P3_TRAINING_NAMESPACE,
        {"segment_id": segment_id, "p2_estimate_ids": list(p2_ids)},
    )
    validation_id = _uuid5(
        _P3_VALIDATION_NAMESPACE,
        {"training_id": training_id, "segment_id": segment_id},
    )
    return ProductionP3BuildWorkerInput(
        job_payload=dict(job_payload),
        estimates=tuple(p3_inputs),
        segment_snapshot_id=segment_id,
        validation_snapshot_id=validation_id,
        training_dataset_snapshot_id=training_id,
        configuration_snapshot_id=config_id,
        as_of_utc=as_of_utc,
        training_created_at_utc=_utc_text(
            production_input.get("training_created_at_utc"),
            "training_created_at_utc",
        ),
        trained_at_utc=_utc_text(
            production_input.get("trained_at_utc"),
            "trained_at_utc",
        ),
        surface_created_at_utc=_utc_text(
            production_input.get("surface_created_at_utc"),
            "surface_created_at_utc",
        ),
        twin_valid_from_utc=_utc_text(
            production_input.get("twin_valid_from_utc"),
            "twin_valid_from_utc",
        ),
        twin_published_at_utc=_utc_text(
            production_input.get("twin_published_at_utc"),
            "twin_published_at_utc",
        ),
        estimate_created_at_utc=_utc_text(
            production_input.get("estimate_created_at_utc"),
            "estimate_created_at_utc",
        ),
    )


def persist_p3_worker_product(
    rows: CanonicalRowRepository,
    object_store: LocalObjectStore,
    product: ProductionP3BuildWorkerProduct,
) -> None:
    repository = P3PersistenceRepository(rows, object_store=object_store)
    repository.register_component(
        segment=product.segment,
        validation=product.validation,
        training=product.training,
        model_build=product.model_build,
        surface_build=product.surface_build,
        model_object=product.model_object,
        surface_object=product.surface_object,
    )
    repository.register_twin(
        product.twin,
        components=(product.component,),
    )
    for estimate in product.estimates:
        repository.register_estimate(estimate)
        if repository.exact_capability_estimate(estimate.estimate_id) != estimate:
            raise ProductionDownstreamError(
                "ED2_B2_P3_RESTART_REBUILD_FAILED",
                estimate.estimate_id,
            )


def _bind_context_artifact(
    rows: CanonicalRowRepository,
    *,
    context_id: str,
    binding_role: str,
    context_artifact_id: str,
) -> None:
    current = rows.one(
        "context.context_artifact_binding",
        where={
            "context_id": context_id,
            "binding_role": binding_role,
        },
        columns=("context_artifact_id",),
    )
    if current is None:
        rows.insert(
            "context.context_artifact_binding",
            {
                "context_id": context_id,
                "binding_role": binding_role,
                "context_artifact_id": context_artifact_id,
            },
        )
    elif str(current["context_artifact_id"]) != context_artifact_id:
        raise ProductionDownstreamError(
            "ED2_B2_CONTEXT_BINDING_CONFLICT",
            f"{context_id}:{binding_role}",
        )


def _m8_role_and_profile(
    rows: CanonicalRowRepository,
    object_store: LocalObjectStore,
    *,
    authority_root: Path,
    context_id: str,
    as_of_utc: str,
) -> tuple[M8RoleModelBinding, P2ArtifactBinding]:
    policy = M8AuthorityPolicy.from_canonical()
    role_path = authority_root / "P4_P5_ROLE_PRIVACY_PROFILE.json"
    try:
        role_bytes = role_path.read_bytes()
    except OSError as exc:
        raise ProductionDownstreamError(
            "ED2_B2_ROLE_PROFILE_READ_FAILED",
            type(exc).__name__,
        ) from exc
    if hashlib.sha256(role_bytes).hexdigest() != policy.role_profile_sha256:
        raise ProductionDownstreamError(
            "ED2_B2_ROLE_PROFILE_HASH_MISMATCH",
            role_path.name,
        )
    role_binding = _context_artifact_bytes(
        rows,
        object_store,
        artifact_kind=policy.role_artifact_kind,
        logical_key=policy.role_logical_key,
        artifact_version=policy.role_profile_version,
        schema_version=policy.role_schema_version,
        data=role_bytes,
    )
    profile_binding = _context_artifact_bytes(
        rows,
        object_store,
        artifact_kind="ASSESSMENT_PROFILE",
        logical_key=ED2_ASSESSMENT_PROFILE_ID,
        artifact_version=ED2_ASSESSMENT_PROFILE_VERSION,
        schema_version=ED2_ASSESSMENT_PROFILE_SCHEMA,
        data=_canonical_bytes(ed2_training_assessment_profile()),
    )
    _bind_context_artifact(
        rows,
        context_id=context_id,
        binding_role=policy.role_binding_role,
        context_artifact_id=role_binding.context_artifact_id,
    )
    _bind_context_artifact(
        rows,
        context_id=context_id,
        binding_role="ASSESSMENT_PROFILE",
        context_artifact_id=profile_binding.context_artifact_id,
    )
    return (
        M8RoleModelBinding(
            context_artifact_id=role_binding.context_artifact_id,
            object_ref_id=role_binding.object_ref_id,
            artifact_kind=role_binding.artifact_kind,
            binding_role=policy.role_binding_role,
            logical_key=role_binding.logical_key,
            artifact_version=role_binding.artifact_version,
            schema_version=role_binding.schema_version,
            artifact_sha256=role_binding.artifact_sha256,
            status=role_binding.status,
            sealed=role_binding.sealed,
            effective_from_utc=as_of_utc,
            effective_to_utc=None,
        ),
        profile_binding,
    )


def _world_fact(
    rows: CanonicalRowRepository,
    *,
    world_product_id: str,
    episode_id: str,
) -> M8WorldFactRef:
    row = rows.one(
        "world.world_product_manifest",
        where={"world_product_id": world_product_id},
        columns=(
            "episode_id",
            "stage_id",
            "world_kind",
            "status",
            "logical_content_hash",
            "created_at",
        ),
    )
    if row is None or str(row["episode_id"]) != episode_id:
        raise ProductionDownstreamError(
            "ED2_B2_WORLD_PRODUCT_NOT_FOUND",
            world_product_id,
        )
    if str(row["status"]) != "READY":
        raise ProductionDownstreamError(
            "ED2_B2_WORLD_PRODUCT_NOT_READY",
            world_product_id,
        )
    layers = {
        "TRUTH": "GROUND_TRUTH",
        "PERCEPTION": "PERCEIVED_WORLD",
        "ACTION": "ACTION_WORLD",
    }
    kind = str(row["world_kind"])
    if kind not in layers:
        raise ProductionDownstreamError(
            "ED2_B2_P4_WORLD_KIND_UNSUPPORTED",
            kind,
        )
    return M8WorldFactRef(
        ref_id=f"world:{world_product_id}",
        world_layer=layers[kind],
        episode_id=episode_id,
        stage_id=(
            None if row["stage_id"] is None else str(row["stage_id"])
        ),
        source_hash=str(row["logical_content_hash"]),
        knowledge_time_utc=_utc_text(
            row["created_at"],
            "world.created_at",
        ),
    )


def _p3_source_episode_ids(
    p2: P2PersistenceRepository,
    p3: P3PersistenceRepository,
    *,
    twin_revision_id: str,
) -> tuple[str, ...]:
    components = p3.exact_twin_components(twin_revision_id)
    episode_ids: set[str] = set()
    for component in components:
        training = p3.exact_training(
            component.model_build.model.training_dataset_snapshot_id
        )
        for estimate_id in training.estimate_ids:
            adjusted = p2.exact_adjusted_estimate(estimate_id)
            observation = p2.exact_source_observation(
                adjusted.source_observation_id
            )
            episode_ids.add(observation.episode_id)
    return tuple(sorted(episode_ids))


def prepare_p4_build_worker_input(
    rows: CanonicalRowRepository,
    object_store: LocalObjectStore,
    *,
    authority_root: Path,
    job_payload: Mapping[str, object],
    production_input: Mapping[str, object],
    confidence: float,
    created_at_utc: str,
) -> ProductionP4BuildWorkerInput:
    p3 = P3PersistenceRepository(rows, object_store=object_store)
    p2 = P2PersistenceRepository(rows, object_store=object_store)
    estimate = p3.exact_capability_estimate(
        _text(production_input.get("p3_estimate_id"), "p3_estimate_id")
    )
    twin = p3.exact_twin_revision(estimate.twin_revision_id)
    session_id = _text(production_input.get("session_id"), "session_id")
    episode_id = _text(production_input.get("episode_id"), "episode_id")
    episode = rows.one(
        "episode.training_episode",
        where={"episode_id": episode_id},
        columns=("session_id", "context_id", "primary_aircraft_id"),
    )
    if (
        episode is None
        or str(episode["session_id"]) != session_id
        or (
            episode["primary_aircraft_id"] is not None
            and str(episode["primary_aircraft_id"]) != twin.aircraft_id
        )
    ):
        raise ProductionDownstreamError(
            "ED2_B2_P4_EPISODE_BINDING_MISMATCH",
            episode_id,
        )
    source_observation = p2.exact_source_observation(
        _text(
            production_input.get("source_observation_id"),
            "source_observation_id",
        )
    )
    if (
        source_observation.episode_id != episode_id
        or source_observation.aircraft_id != twin.aircraft_id
    ):
        raise ProductionDownstreamError(
            "ED2_B2_P4_SOURCE_OBSERVATION_MISMATCH",
            source_observation.observation_id,
        )
    context_id = str(episode["context_id"])
    role_model, _profile_binding = _m8_role_and_profile(
        rows,
        object_store,
        authority_root=authority_root,
        context_id=context_id,
        as_of_utc=estimate.as_of_time,
    )
    world_product_id = _text(
        production_input.get("world_product_id"),
        "world_product_id",
    )
    fact = _world_fact(
        rows,
        world_product_id=world_product_id,
        episode_id=episode_id,
    )
    availability = _text(
        production_input.get(
            "evidence_availability_status",
            "AVAILABLE",
        ),
        "evidence_availability_status",
    )
    if availability == "AVAILABLE":
        numeric_value: float | None = source_observation.observed_value
    elif availability in {
        "UNAVAILABLE",
        "NOT_IDENTIFIABLE",
        "OUT_OF_DOMAIN",
    }:
        numeric_value = None
    else:
        raise ProductionDownstreamError(
            "ED2_B2_P4_EVIDENCE_AVAILABILITY_INVALID",
            availability,
        )
    machine = M8EvidenceRef(
        evidence_id=(
            "machine:ed2:"
            + _hash(
                {
                    "observation_id": source_observation.observation_id,
                    "world_product_id": world_product_id,
                    "availability": availability,
                }
            )
        ),
        origin="MACHINE",
        evidence_family=_text(
            production_input.get(
                "evidence_family",
                "OUTCOME_CONTEXT",
            ),
            "evidence_family",
        ),
        evidence_set_id=source_observation.evidence_set_id,
        episode_id=episode_id,
        world_refs=(fact.ref_id,),
        source_refs=(source_observation.observation_id,),
        availability_status=availability,
        numeric_value=numeric_value,
        knowledge_time_utc=source_observation.knowledge_time_utc,
    )
    source = P4SubjectSource(
        actor_id=_text(production_input.get("actor_id"), "actor_id"),
        role_code=_text(
            production_input.get("role_code", "SUBJECT_SELF"),
            "role_code",
        ),
        seat_code=_optional_text(
            production_input.get("seat_code"),
            "seat_code",
        ),
        function_code=_optional_text(
            production_input.get("function_code"),
            "function_code",
        ),
        session_id=session_id,
        episode_id=episode_id,
        stage_id=_optional_text(
            production_input.get("stage_id"),
            "stage_id",
        ),
        aircraft_id=twin.aircraft_id,
        twin_revision_id=twin.twin_revision_id,
        p3_estimate_id=estimate.estimate_id,
        p3_source_episode_ids=_p3_source_episode_ids(
            p2,
            p3,
            twin_revision_id=twin.twin_revision_id,
        ),
        assessment_spec_id=ED2_ASSESSMENT_PROFILE_ID,
        assessment_spec_version=ED2_ASSESSMENT_PROFILE_VERSION,
        world_refs=(fact.ref_id,),
        evidence_set_id=source_observation.evidence_set_id,
        as_of_utc=estimate.as_of_time,
        knowledge_time_utc=source_observation.knowledge_time_utc,
    )
    return ProductionP4BuildWorkerInput(
        job_payload=dict(job_payload),
        source=source,
        role_model=role_model,
        fact_refs=(fact,),
        machine_evidence=(machine,),
        p3_estimate=estimate,
        confidence=confidence,
        created_at_utc=created_at_utc,
    )


def persist_p4_worker_product(
    rows: CanonicalRowRepository,
    product: ProductionP4AssessmentWorkerProduct,
) -> str:
    products = P4P5PersistenceRepository(rows)
    products.register_p4_subject(product.subject)
    scope_id = P4P5ComputeInputRepository(rows).register_p4_scope(
        product.scope
    )
    products.register_p4_revision(
        product.subject,
        product.revision,
        annotations=(),
    )
    result = assessment_result_from_profile(
        revision_kind="P4",
        revision_id=product.revision.actor_assessment_id,
        result=product.assessment_result,
    )
    ED2AssessmentResultRepository(rows).register(
        result,
        created_at_utc=product.revision.created_at_utc,
    )
    return scope_id


def prepare_p5_build_worker_input(
    rows: CanonicalRowRepository,
    *,
    job_payload: Mapping[str, object],
    production_input: Mapping[str, object],
    confidence: float,
    created_at_utc: str,
) -> ProductionP5BuildWorkerInput:
    products = P4P5PersistenceRepository(rows)
    revision_ids = _texts(
        production_input.get("p4_revision_ids"),
        "p4_revision_ids",
    )
    revisions = tuple(products.exact_p4_revision(item) for item in revision_ids)
    if not revisions:
        raise ProductionDownstreamError(
            "ED2_B2_P5_PARTICIPANTS_REQUIRED",
            "p4_revision_ids",
        )
    sessions = {item.session_id for item in revisions}
    episodes = {item.episode_id for item in revisions}
    evidence_sets = {item.evidence_set_id for item in revisions}
    subjects = tuple(
        products.exact_p4_subject(item.subject_context_id)
        for item in revisions
    )
    role_artifacts = {
        item.role_model_context_artifact_id for item in subjects
    }
    if (
        len(sessions) != 1
        or len(episodes) != 1
        or len(evidence_sets) != 1
        or len(role_artifacts) != 1
    ):
        raise ProductionDownstreamError(
            "ED2_B2_P5_COMPOSITION_DOMAIN_DRIFT",
            ",".join(revision_ids),
        )
    explicit_session = production_input.get("session_id")
    explicit_episode = production_input.get("mission_episode_id")
    session_id = next(iter(sessions))
    episode_id = next(iter(episodes))
    if explicit_session is not None and _text(
        explicit_session,
        "session_id",
    ) != session_id:
        raise ProductionDownstreamError(
            "ED2_B2_P5_SESSION_MISMATCH",
            session_id,
        )
    if explicit_episode is not None and _text(
        explicit_episode,
        "mission_episode_id",
    ) != episode_id:
        raise ProductionDownstreamError(
            "ED2_B2_P5_EPISODE_MISMATCH",
            episode_id,
        )
    world_refs = tuple(
        sorted({ref for subject in subjects for ref in subject.world_refs})
    )
    return ProductionP5BuildWorkerInput(
        job_payload=dict(job_payload),
        session_id=session_id,
        mission_episode_id=episode_id,
        team_id=_optional_text(
            production_input.get("team_id"),
            "team_id",
        ),
        p4_revisions=revisions,
        world_snapshot_refs=world_refs,
        scenario_context_artifact_id=_optional_text(
            production_input.get("scenario_context_artifact_id"),
            "scenario_context_artifact_id",
        ),
        role_model_context_artifact_id=next(iter(role_artifacts)),
        assessment_spec_id=ED2_ASSESSMENT_PROFILE_ID,
        assessment_spec_version=ED2_ASSESSMENT_PROFILE_VERSION,
        as_of_utc=_utc_text(
            production_input.get("as_of_utc"),
            "as_of_utc",
        ),
        objective_result_refs=_texts(
            production_input.get("objective_result_refs", ()),
            "objective_result_refs",
        ),
        evidence_set_id=next(iter(evidence_sets)),
        confidence=confidence,
        created_at_utc=created_at_utc,
    )


def persist_p5_worker_product(
    rows: CanonicalRowRepository,
    product: ProductionP5AssessmentWorkerProduct,
) -> str:
    selection_id = P4P5ComputeInputRepository(rows).register_p5_selection(
        product.composition,
        objective_result_refs=product.compute_input.objective_result_refs,
        evidence_set_id=product.compute_input.evidence_set_id,
        as_of_utc=product.compute_input.as_of_utc,
    )
    P4P5PersistenceRepository(rows).register_p5_revision(
        product.composition,
        product.revision,
    )
    result = assessment_result_from_profile(
        revision_kind="P5",
        revision_id=product.revision.mission_assessment_id,
        result=product.assessment_result,
    )
    ED2AssessmentResultRepository(rows).register(
        result,
        created_at_utc=product.revision.created_at_utc,
    )
    return selection_id


def _assignment_for_p3_estimate(
    rows: CanonicalRowRepository,
    p2: P2PersistenceRepository,
    p3: P3PersistenceRepository,
    estimate_id: str,
) -> tuple[str, str, int]:
    estimate = p3.exact_capability_estimate(estimate_id)
    components = p3.exact_twin_components(estimate.twin_revision_id)
    matches = tuple(
        component
        for component in components
        if component.model_build.model.capability_type == estimate.capability_type
    )
    if len(matches) != 1:
        raise ProductionDownstreamError(
            "ED2_B2_P6_P3_COMPONENT_AMBIGUOUS",
            estimate_id,
        )
    training = p3.exact_training(
        matches[0].model_build.model.training_dataset_snapshot_id
    )
    segment = p3.exact_segment(training.segment_snapshot_id)
    condition_order = estimate.condition_point.get("session_order")
    if isinstance(condition_order, bool) or not isinstance(
        condition_order,
        int,
    ):
        raise ProductionDownstreamError(
            "ED2_B2_P6_SESSION_ORDER_INVALID",
            estimate_id,
        )
    p2_ids = [
        item
        for item, order in zip(
            training.estimate_ids,
            training.session_orders,
            strict=True,
        )
        if order == condition_order
    ]
    if len(p2_ids) != 1:
        raise ProductionDownstreamError(
            "ED2_B2_P6_P2_MEMBERSHIP_AMBIGUOUS",
            estimate_id,
        )
    adjusted = p2.exact_adjusted_estimate(p2_ids[0])
    observation = p2.exact_source_observation(
        adjusted.source_observation_id
    )
    row = rows.one(
        "metric.capability_observation",
        where={"observation_id": observation.observation_id},
        columns=("session_id",),
    )
    if row is None:
        raise ProductionDownstreamError(
            "ED2_B2_P6_SOURCE_SESSION_NOT_FOUND",
            observation.observation_id,
        )
    session_id = str(row["session_id"])
    assignment = rows.one(
        "registry.session_order_assignment",
        where={
            "session_order_scope_id": segment.session_order_scope_id,
            "session_id": session_id,
            "order_value": condition_order,
            "is_current": True,
        },
        columns=("assignment_id",),
    )
    if assignment is None:
        raise ProductionDownstreamError(
            "ED2_B2_P6_ASSIGNMENT_NOT_FOUND",
            estimate_id,
        )
    config_ids = {
        item for item in segment.configuration_snapshot_ids
    }
    if len(config_ids) != 1:
        raise ProductionDownstreamError(
            "ED2_B2_P6_CONFIGURATION_AMBIGUOUS",
            estimate_id,
        )
    return (
        str(assignment["assignment_id"]),
        next(iter(config_ids)),
        condition_order,
    )


def prepare_p6_build_worker_input(
    rows: CanonicalRowRepository,
    object_store: LocalObjectStore,
    *,
    job_payload: Mapping[str, object],
    production_input: Mapping[str, object],
) -> ProductionP6BuildWorkerInput:
    p2 = P2PersistenceRepository(rows, object_store=object_store)
    p3 = P3PersistenceRepository(rows, object_store=object_store)
    p45 = P4P5PersistenceRepository(rows)
    raw_rows = production_input.get("training_rows")
    if (
        not isinstance(raw_rows, Sequence)
        or isinstance(raw_rows, (str, bytes))
        or not raw_rows
    ):
        raise ProductionDownstreamError(
            "ED2_B2_P6_TRAINING_ROWS_REQUIRED",
            "training_rows",
        )
    training_rows: list[P6CapabilityTrainingRow] = []
    p3_model_refs: dict[str, P6P3ModelRef] = {}
    for index, raw in enumerate(raw_rows):
        item = _mapping(raw, f"training_rows[{index}]")
        estimate = p3.exact_capability_estimate(
            _text(item.get("p3_estimate_id"), "p3_estimate_id")
        )
        revision = p45.exact_p4_revision(
            _text(item.get("p4_revision_id"), "p4_revision_id")
        )
        assignment_id, configuration_id, order = _assignment_for_p3_estimate(
            rows,
            p2,
            p3,
            estimate.estimate_id,
        )
        training_rows.append(
            P6CapabilityTrainingRow(
                estimate=estimate,
                p4_revision=revision,
                aircraft_id=p3.exact_twin_revision(estimate.twin_revision_id).aircraft_id,
                configuration_snapshot_id=configuration_id,
                session_order_assignment_id=assignment_id,
                session_order=order,
            )
        )
        for component in p3.exact_twin_components(
            estimate.twin_revision_id
        ):
            model = component.model_build.model
            twin = p3.exact_twin_revision(estimate.twin_revision_id)
            p3_model_refs[model.capability_model_id] = P6P3ModelRef(
                model_ref_id=model.capability_model_id,
                publication_status="PUBLISHED",
                knowledge_time_utc=twin.published_at,
            )

    factual_raw = production_input.get("factual_sources")
    if (
        not isinstance(factual_raw, Sequence)
        or isinstance(factual_raw, (str, bytes))
        or not factual_raw
    ):
        raise ProductionDownstreamError(
            "ED2_B2_P6_FACTUAL_SOURCE_REQUIRED",
            "factual_sources",
        )
    factual_sources: list[P6FactualSourceRevision] = []
    for index, raw in enumerate(factual_raw):
        item = _mapping(raw, f"factual_sources[{index}]")
        phase = _text(item.get("phase"), "factual_source.phase")
        revision_id = _text(
            item.get("revision_id"),
            "factual_source.revision_id",
        )
        if phase == "P4":
            revision = p45.exact_p4_revision(revision_id)
            if revision.approval_state != "APPROVED":
                raise ProductionDownstreamError(
                    "ED2_B2_P6_FACTUAL_REVISION_NOT_APPROVED",
                    revision_id,
                )
            knowledge_time = revision.created_at_utc
        elif phase == "P5":
            revision5 = p45.exact_p5_revision(revision_id)
            if revision5.approval_state != "APPROVED":
                raise ProductionDownstreamError(
                    "ED2_B2_P6_FACTUAL_REVISION_NOT_APPROVED",
                    revision_id,
                )
            knowledge_time = revision5.created_at_utc
        else:
            raise ProductionDownstreamError(
                "ED2_B2_P6_FACTUAL_PHASE_INVALID",
                phase,
            )
        factual_sources.append(
            P6FactualSourceRevision(
                phase=phase,
                revision_id=revision_id,
                publication_status="PUBLISHED",
                knowledge_time_utc=knowledge_time,
                is_target_outcome=False,
                is_post_horizon_outcome=False,
            )
        )

    context_raw = production_input.get("scenario_context_refs", ())
    if (
        not isinstance(context_raw, Sequence)
        or isinstance(context_raw, (str, bytes))
    ):
        raise ProductionDownstreamError(
            "ED2_B2_P6_CONTEXT_INVALID",
            "scenario_context_refs",
        )
    context_refs = tuple(
        P6ContextRef(
            context_ref_id=_text(
                _mapping(raw, "scenario_context_ref").get(
                    "context_ref_id"
                ),
                "scenario_context_ref.context_ref_id",
            ),
            status=_text(
                _mapping(raw, "scenario_context_ref").get("status"),
                "scenario_context_ref.status",
            ),
            knowledge_time_utc=_utc_text(
                _mapping(raw, "scenario_context_ref").get(
                    "knowledge_time_utc"
                ),
                "scenario_context_ref.knowledge_time_utc",
            ),
        )
        for raw in context_raw
    )
    forecast_raw = production_input.get("forecast")
    counterfactual_raw = production_input.get("counterfactual")
    return ProductionP6BuildWorkerInput(
        job_payload=dict(job_payload),
        training_rows=tuple(training_rows),
        factual_sources=tuple(factual_sources),
        p3_model_refs=tuple(
            p3_model_refs[key] for key in sorted(p3_model_refs)
        ),
        scenario_context_refs=context_refs,
        target_scope=_text(
            production_input.get("target_scope"),
            "target_scope",
        ),
        subject_or_composition_ref=_text(
            production_input.get("subject_or_composition_ref"),
            "subject_or_composition_ref",
        ),
        forecast_origin_utc=_utc_text(
            production_input.get("forecast_origin_utc"),
            "forecast_origin_utc",
        ),
        as_of_utc=_utc_text(
            production_input.get("as_of_utc"),
            "as_of_utc",
        ),
        trained_at_utc=_utc_text(
            production_input.get("trained_at_utc"),
            "trained_at_utc",
        ),
        sealed_at_utc=_utc_text(
            production_input.get("sealed_at_utc"),
            "sealed_at_utc",
        ),
        forecast_spec=(
            None
            if forecast_raw is None
            else _mapping(forecast_raw, "forecast")
        ),
        counterfactual_spec=(
            None
            if counterfactual_raw is None
            else _mapping(counterfactual_raw, "counterfactual")
        ),
    )


def persist_p6_worker_product(
    rows: CanonicalRowRepository,
    object_store: LocalObjectStore,
    product: ProductionP6BuildWorkerProduct,
) -> None:
    repository = P6PersistenceRepository(rows, object_store=object_store)
    repository.register_model_build(
        product.model_build,
        product.managed_object,
    )
    repository.register_input(product.input_snapshot)
    if product.forecast_request is not None:
        repository.register_forecast_request(product.forecast_request)
        if (
            repository.exact_forecast_request(
                product.forecast_request.forecast_request_id
            )
            != product.forecast_request
        ):
            raise ProductionDownstreamError(
                "ED2_B2_P6_FORECAST_REQUEST_RESTART_DRIFT",
                product.forecast_request.forecast_request_id,
            )
    if product.counterfactual_request is not None:
        repository.register_counterfactual_request(
            product.counterfactual_request
        )
        if (
            repository.exact_counterfactual_request(
                product.counterfactual_request.counterfactual_request_id
            )
            != product.counterfactual_request
        ):
            raise ProductionDownstreamError(
                "ED2_B2_P6_COUNTERFACTUAL_REQUEST_RESTART_DRIFT",
                product.counterfactual_request.counterfactual_request_id,
            )
