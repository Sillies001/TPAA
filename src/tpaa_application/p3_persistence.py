"""PIQB B2 exact P3 persistence over adopted canonical relations."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from tpaa_application.m7_workspace import M7LayerEvidence, M7P3WorkspaceSnapshot
from tpaa_application.p2_persistence import P2PersistenceRepository
from tpaa_capability import (
    P3AircraftTwinRevision,
    P3CapabilityEstimate,
    P3CapabilityModelBuild,
    P3CapabilityModelProduct,
    P3CapabilitySurfaceBuild,
    P3CapabilitySurfaceProduct,
    P3ModelExecutionProfile,
    P3TrainingDatasetSnapshot,
    P3TwinComponentBinding,
)
from tpaa_longitudinal import (
    P3AuthorityPolicy,
    P3LifecycleSegment,
    P3ManagedObject,
    P3ModelValidationSnapshot,
    assert_p3_claim_level,
    validate_managed_object,
)
from tpaa_storage.canonical_rows import CanonicalRowRepository
from tpaa_storage.object_store import LocalObjectStore


class P3PersistenceError(RuntimeError):
    """Fail-closed exact persistence error for P3 durable products."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


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
        raise P3PersistenceError(
            "P3_CANONICAL_JSON_INVALID",
            type(exc).__name__,
        ) from exc


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _mapping(value: object, field: str) -> dict[str, object]:
    decoded: object = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise P3PersistenceError("P3_DB_JSON_INVALID", field) from exc
    if not isinstance(decoded, Mapping):
        raise P3PersistenceError("P3_DB_JSON_INVALID", field)
    return {str(key): item for key, item in decoded.items()}


def _array(value: object, field: str) -> tuple[object, ...]:
    decoded: object = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise P3PersistenceError("P3_DB_ARRAY_INVALID", field) from exc
    if not isinstance(decoded, (list, tuple)):
        raise P3PersistenceError("P3_DB_ARRAY_INVALID", field)
    return tuple(decoded)


def _strings(value: object, field: str) -> tuple[str, ...]:
    result: list[str] = []
    for item in _array(value, field):
        if isinstance(item, UUID):
            result.append(str(item))
        elif isinstance(item, str) and item:
            result.append(item)
        else:
            raise P3PersistenceError("P3_DB_ARRAY_INVALID", field)
    return tuple(result)


def _time_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        normalized = value
        if normalized.tzinfo is not None:
            normalized = normalized.astimezone(UTC)
        return normalized.isoformat().replace("+00:00", "Z")
    raise P3PersistenceError("P3_DB_TIME_INVALID", type(value).__name__)


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise P3PersistenceError("P3_DB_NUMERIC_INVALID", "bool")
    if isinstance(value, (int, float, Decimal, str)):
        return float(value)
    raise P3PersistenceError("P3_DB_NUMERIC_INVALID", type(value).__name__)


def _required_float(value: object, field: str) -> float:
    result = _optional_float(value)
    if result is None:
        raise P3PersistenceError("P3_DB_NUMERIC_INVALID", field)
    return result


def _required_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise P3PersistenceError("P3_DB_INTEGER_INVALID", field)
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal) and value == int(value):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise P3PersistenceError("P3_DB_INTEGER_INVALID", field) from exc
    raise P3PersistenceError("P3_DB_INTEGER_INVALID", field)


def _bool(value: object, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    raise P3PersistenceError("P3_DB_BOOLEAN_INVALID", field)


def _segment_manifest(value: P3LifecycleSegment) -> dict[str, object]:
    return {
        **value.projection(),
        "snapshot_type": value.snapshot_type,
        "frozen": value.frozen,
        "estimate_ids": list(value.estimate_ids),
    }


def _segment_hash(value: P3LifecycleSegment) -> str:
    policy = P3AuthorityPolicy.from_canonical()
    return _canonical_hash(
        {
            "authority_sha256": policy.authority_sha256,
            "profile_sha256": policy.profile_sha256,
            "snapshot_type": value.snapshot_type,
            "segment_snapshot_id": value.segment_snapshot_id,
            "aircraft_id": value.aircraft_id,
            "aircraft_model_id": value.aircraft_model_id,
            "configuration_key": value.configuration_key,
            "configuration_snapshot_ids": list(
                value.configuration_snapshot_ids
            ),
            "lifecycle_event_ids": list(value.lifecycle_event_ids),
            "session_order_scope_id": value.session_order_scope_id,
            "first_session_order": value.first_session_order,
            "last_session_order": value.last_session_order,
            "capability_type": value.capability_type,
            "metric_semantic_id": value.metric_semantic_id,
            "metric_semantic_version": value.metric_semantic_version,
            "reference_condition_id": value.reference_condition_id,
            "unit": value.unit,
            "estimate_ids": list(value.estimate_ids),
            "knowledge_cutoff_utc": value.knowledge_cutoff_utc,
        }
    )


def _validation_manifest(
    value: P3ModelValidationSnapshot,
) -> dict[str, object]:
    return {
        **value.projection(),
        "snapshot_type": value.snapshot_type,
        "frozen": value.frozen,
    }


def _validation_hash(
    value: P3ModelValidationSnapshot,
    *,
    segment_hash: str,
) -> str:
    policy = P3AuthorityPolicy.from_canonical()
    return _canonical_hash(
        {
            "authority_sha256": policy.authority_sha256,
            "profile_sha256": policy.profile_sha256,
            "snapshot_type": value.snapshot_type,
            "validation_snapshot_id": value.validation_snapshot_id,
            "training_dataset_snapshot_id": (
                value.training_dataset_snapshot_id
            ),
            "segment_snapshot_id": value.segment_snapshot_id,
            "segment_hash": segment_hash,
            "training_estimate_ids": list(value.training_estimate_ids),
            "validation_estimate_ids": list(value.validation_estimate_ids),
            "as_of_utc": value.as_of_utc,
        }
    )


class P3PersistenceRepository:
    """Engine-neutral P3-owned exact persistence mapper."""

    def __init__(
        self,
        rows: CanonicalRowRepository,
        *,
        object_store: LocalObjectStore | None = None,
    ) -> None:
        self._rows = rows
        self._object_store = object_store

    def _dataset_row(
        self,
        snapshot_id: str,
    ) -> dict[str, object] | None:
        return self._rows.one(
            "registry.dataset_snapshot",
            where={"dataset_snapshot_id": snapshot_id},
            columns=(
                "dataset_snapshot_id",
                "snapshot_type",
                "query_or_manifest",
                "input_refs",
                "data_hash",
                "schema_version",
                "created_at",
                "frozen",
            ),
        )

    def _register_dataset(
        self,
        *,
        snapshot_id: str,
        snapshot_type: str,
        query_or_manifest: Mapping[str, object],
        input_refs: tuple[str, ...],
        data_hash: str,
        schema_version: str,
        created_at: str,
        frozen: bool,
    ) -> None:
        current = self._dataset_row(snapshot_id)
        expected = {
            "dataset_snapshot_id": snapshot_id,
            "snapshot_type": snapshot_type,
            "query_or_manifest": dict(query_or_manifest),
            "input_refs": input_refs,
            "data_hash": data_hash,
            "schema_version": schema_version,
            "created_at": created_at,
            "frozen": frozen,
        }
        if current is not None:
            actual = {
                "dataset_snapshot_id": str(current["dataset_snapshot_id"]),
                "snapshot_type": str(current["snapshot_type"]),
                "query_or_manifest": _mapping(
                    current["query_or_manifest"],
                    "dataset_snapshot.query_or_manifest",
                ),
                "input_refs": _strings(
                    current["input_refs"],
                    "dataset_snapshot.input_refs",
                ),
                "data_hash": str(current["data_hash"]),
                "schema_version": str(current["schema_version"]),
                "created_at": _time_text(current["created_at"]),
                "frozen": _bool(current["frozen"], "dataset_snapshot.frozen"),
            }
            if actual != expected:
                raise P3PersistenceError(
                    "P3_IMMUTABLE_CONFLICT",
                    snapshot_id,
                )
            return
        self._rows.insert(
            "registry.dataset_snapshot",
            expected,
            field_kinds={
                "query_or_manifest": "json",
                "input_refs": "uuid_array",
            },
        )

    def register_segment(self, value: P3LifecycleSegment) -> None:
        policy = P3AuthorityPolicy.from_canonical()
        if (
            value.snapshot_type != policy.segment_snapshot_type
            or not value.frozen
            or _segment_hash(value) != value.segment_hash
        ):
            raise P3PersistenceError(
                "P3_SEGMENT_IDENTITY_MISMATCH",
                value.segment_snapshot_id,
            )
        self._register_dataset(
            snapshot_id=value.segment_snapshot_id,
            snapshot_type=value.snapshot_type,
            query_or_manifest=_segment_manifest(value),
            input_refs=value.estimate_ids,
            data_hash=value.segment_hash,
            schema_version="TPAA_P3_LONGITUDINAL_SEGMENT_V1",
            created_at=value.knowledge_cutoff_utc,
            frozen=value.frozen,
        )

    def exact_segment(self, snapshot_id: str) -> P3LifecycleSegment:
        row = self._dataset_row(snapshot_id)
        if row is None:
            raise P3PersistenceError("P3_SEGMENT_NOT_FOUND", snapshot_id)
        manifest = _mapping(
            row["query_or_manifest"],
            "segment.query_or_manifest",
        )
        if str(row["snapshot_type"]) != str(
            manifest.get("snapshot_type")
        ):
            raise P3PersistenceError(
                "P3_SEGMENT_IDENTITY_MISMATCH",
                snapshot_id,
            )
        value = P3LifecycleSegment(
            segment_snapshot_id=str(manifest["segment_snapshot_id"]),
            snapshot_type=str(row["snapshot_type"]),
            frozen=_bool(row["frozen"], "segment.frozen"),
            aircraft_id=str(manifest["aircraft_id"]),
            aircraft_model_id=str(manifest["aircraft_model_id"]),
            configuration_key=str(manifest["configuration_key"]),
            configuration_snapshot_ids=_strings(
                manifest["configuration_snapshot_ids"],
                "segment.configuration_snapshot_ids",
            ),
            lifecycle_event_ids=_strings(
                manifest["lifecycle_event_ids"],
                "segment.lifecycle_event_ids",
            ),
            session_order_scope_id=str(
                manifest["session_order_scope_id"]
            ),
            first_session_order=_required_int(
                manifest["first_session_order"],
                "segment.first_session_order",
            ),
            last_session_order=_required_int(
                manifest["last_session_order"],
                "segment.last_session_order",
            ),
            as_of_session_order=_required_int(
                manifest["as_of_session_order"],
                "segment.as_of_session_order",
            ),
            capability_type=str(manifest["capability_type"]),
            metric_semantic_id=str(manifest["metric_semantic_id"]),
            metric_semantic_version=_required_int(
                manifest["metric_semantic_version"],
                "segment.metric_semantic_version",
            ),
            reference_condition_id=str(
                manifest["reference_condition_id"]
            ),
            unit=str(manifest["unit"]),
            observation_count=_required_int(
                manifest["observation_count"],
                "segment.observation_count",
            ),
            episode_count=_required_int(
                manifest["episode_count"],
                "segment.episode_count",
            ),
            independent_aircraft_count=_required_int(
                manifest["independent_aircraft_count"],
                "segment.independent_aircraft_count",
            ),
            effective_evidence_count=_required_float(
                manifest["effective_evidence_count"],
                "segment.effective_evidence_count",
            ),
            knowledge_cutoff_utc=str(
                manifest["knowledge_cutoff_utc"]
            ),
            estimate_ids=_strings(
                manifest["estimate_ids"],
                "segment.estimate_ids",
            ),
            segment_hash=str(row["data_hash"]),
        )
        if (
            value.segment_snapshot_id != snapshot_id
            or value.estimate_ids
            != _strings(row["input_refs"], "segment.input_refs")
            or _segment_hash(value) != value.segment_hash
            or value.observation_count != len(value.estimate_ids)
            or value.as_of_session_order != value.last_session_order
            or value.independent_aircraft_count != 1
            or value.effective_evidence_count
            != float(value.observation_count)
        ):
            raise P3PersistenceError(
                "P3_SEGMENT_IDENTITY_MISMATCH",
                snapshot_id,
            )
        return value

    def register_validation(
        self,
        value: P3ModelValidationSnapshot,
        *,
        segment: P3LifecycleSegment,
    ) -> None:
        policy = P3AuthorityPolicy.from_canonical()
        if (
            value.snapshot_type != policy.validation_snapshot_type
            or not value.frozen
            or value.segment_snapshot_id != segment.segment_snapshot_id
            or _validation_hash(value, segment_hash=segment.segment_hash)
            != value.data_hash
        ):
            raise P3PersistenceError(
                "P3_VALIDATION_IDENTITY_MISMATCH",
                value.validation_snapshot_id,
            )
        refs = (
            value.segment_snapshot_id,
            value.training_dataset_snapshot_id,
            *value.training_estimate_ids,
            *value.validation_estimate_ids,
        )
        self._register_dataset(
            snapshot_id=value.validation_snapshot_id,
            snapshot_type=value.snapshot_type,
            query_or_manifest=_validation_manifest(value),
            input_refs=refs,
            data_hash=value.data_hash,
            schema_version="TPAA_P3_MODEL_VALIDATION_V1",
            created_at=value.as_of_utc,
            frozen=value.frozen,
        )

    def exact_validation(
        self,
        snapshot_id: str,
    ) -> P3ModelValidationSnapshot:
        row = self._dataset_row(snapshot_id)
        if row is None:
            raise P3PersistenceError(
                "P3_VALIDATION_NOT_FOUND",
                snapshot_id,
            )
        manifest = _mapping(
            row["query_or_manifest"],
            "validation.query_or_manifest",
        )
        value = P3ModelValidationSnapshot(
            validation_snapshot_id=str(
                manifest["validation_snapshot_id"]
            ),
            snapshot_type=str(row["snapshot_type"]),
            frozen=_bool(row["frozen"], "validation.frozen"),
            training_dataset_snapshot_id=str(
                manifest["training_dataset_snapshot_id"]
            ),
            profile_id=str(manifest["profile_id"]),
            profile_version=str(manifest["profile_version"]),
            aircraft_id=str(manifest["aircraft_id"]),
            capability_type=str(manifest["capability_type"]),
            segment_snapshot_id=str(
                manifest["segment_snapshot_id"]
            ),
            training_estimate_ids=_strings(
                manifest["training_estimate_ids"],
                "validation.training_estimate_ids",
            ),
            validation_estimate_ids=_strings(
                manifest["validation_estimate_ids"],
                "validation.validation_estimate_ids",
            ),
            independent_aircraft_count=_required_int(
                manifest["independent_aircraft_count"],
                "validation.independent_aircraft_count",
            ),
            observation_count=_required_int(
                manifest["observation_count"],
                "validation.observation_count",
            ),
            effective_evidence_count=_required_float(
                manifest["effective_evidence_count"],
                "validation.effective_evidence_count",
            ),
            claim_evidence_tier=str(
                manifest["claim_evidence_tier"]
            ),
            as_of_utc=str(manifest["as_of_utc"]),
            data_hash=str(row["data_hash"]),
        )
        segment = self.exact_segment(value.segment_snapshot_id)
        policy = P3AuthorityPolicy.from_canonical()
        refs = (
            value.segment_snapshot_id,
            value.training_dataset_snapshot_id,
            *value.training_estimate_ids,
            *value.validation_estimate_ids,
        )
        if (
            value.validation_snapshot_id != snapshot_id
            or value.snapshot_type != policy.validation_snapshot_type
            or value.profile_id != policy.profile_id
            or value.profile_version != policy.profile_version
            or value.claim_evidence_tier
            != policy.default_claim_level
            or refs
            != _strings(row["input_refs"], "validation.input_refs")
            or _validation_hash(
                value,
                segment_hash=segment.segment_hash,
            )
            != value.data_hash
        ):
            raise P3PersistenceError(
                "P3_VALIDATION_IDENTITY_MISMATCH",
                snapshot_id,
            )
        return value

    def register_training(
        self,
        value: P3TrainingDatasetSnapshot,
    ) -> None:
        policy = P3AuthorityPolicy.from_canonical()
        if (
            value.snapshot_type != policy.training_snapshot_type
            or not value.frozen
            or _canonical_hash(dict(value.query_or_manifest))
            != value.data_hash
        ):
            raise P3PersistenceError(
                "P3_TRAINING_IDENTITY_MISMATCH",
                value.dataset_snapshot_id,
            )
        self._register_dataset(
            snapshot_id=value.dataset_snapshot_id,
            snapshot_type=value.snapshot_type,
            query_or_manifest=value.query_or_manifest,
            input_refs=value.input_refs,
            data_hash=value.data_hash,
            schema_version=value.schema_version,
            created_at=value.created_at,
            frozen=value.frozen,
        )

    def exact_training(
        self,
        snapshot_id: str,
    ) -> P3TrainingDatasetSnapshot:
        row = self._dataset_row(snapshot_id)
        if row is None:
            raise P3PersistenceError(
                "P3_TRAINING_NOT_FOUND",
                snapshot_id,
            )
        manifest = _mapping(
            row["query_or_manifest"],
            "training.query_or_manifest",
        )
        members = _array(manifest.get("members"), "training.members")
        estimate_ids: list[str] = []
        session_orders: list[int] = []
        for raw in members:
            member = _mapping(raw, "training.member")
            estimate_ids.append(str(member["estimate_id"]))
            session_orders.append(
                _required_int(
                    member["session_order"],
                    "training.member.session_order",
                )
            )
        value = P3TrainingDatasetSnapshot(
            dataset_snapshot_id=str(row["dataset_snapshot_id"]),
            snapshot_type=str(row["snapshot_type"]),
            query_or_manifest=manifest,
            input_refs=_strings(
                row["input_refs"],
                "training.input_refs",
            ),
            data_hash=str(row["data_hash"]),
            schema_version=str(row["schema_version"]),
            created_at=_time_text(row["created_at"]),
            frozen=_bool(row["frozen"], "training.frozen"),
            estimate_ids=tuple(estimate_ids),
            session_orders=tuple(session_orders),
            segment_snapshot_id=str(
                manifest["segment_snapshot_id"]
            ),
            validation_snapshot_id=str(
                manifest["validation_snapshot_id"]
            ),
            as_of_utc=str(manifest["as_of_utc"]),
        )
        policy = P3AuthorityPolicy.from_canonical()
        if (
            value.snapshot_type != policy.training_snapshot_type
            or _canonical_hash(manifest) != value.data_hash
            or value.input_refs
            != (
                value.segment_snapshot_id,
                value.validation_snapshot_id,
                *value.estimate_ids,
            )
        ):
            raise P3PersistenceError(
                "P3_TRAINING_IDENTITY_MISMATCH",
                snapshot_id,
            )
        return value

    def _managed_object_for_uri(
        self,
        managed_uri: str,
        expected_hash: str,
    ) -> P3ManagedObject:
        row = self._rows.one(
            "registry.object_reference",
            where={"managed_uri": managed_uri},
            columns=(
                "object_ref_id",
                "managed_uri",
                "artifact_sha256",
                "sealed",
                "gc_state",
                "deleted_at",
            ),
        )
        if row is None:
            raise P3PersistenceError(
                "P3_MANAGED_OBJECT_NOT_FOUND",
                managed_uri,
            )
        value = P3ManagedObject(
            object_ref_id=str(row["object_ref_id"]),
            managed_uri=str(row["managed_uri"]),
            artifact_sha256=str(row["artifact_sha256"]),
            sealed=_bool(row["sealed"], "object_reference.sealed"),
            gc_state=str(row["gc_state"]),
            deleted_at=(
                None
                if row["deleted_at"] is None
                else _time_text(row["deleted_at"])
            ),
        )
        try:
            validate_managed_object(
                value,
                expected_uri=managed_uri,
                expected_hash=expected_hash,
            )
        except Exception as exc:
            raise P3PersistenceError(
                "P3_MANAGED_OBJECT_INVALID",
                managed_uri,
            ) from exc
        return value

    def _register_managed_object(
        self,
        value: P3ManagedObject,
        *,
        expected_uri: str,
        expected_hash: str,
        data: bytes,
    ) -> None:
        if self._object_store is None:
            raise P3PersistenceError(
                "P3_OBJECT_STORE_REQUIRED",
                expected_uri,
            )
        try:
            validate_managed_object(
                value,
                expected_uri=expected_uri,
                expected_hash=expected_hash,
            )
        except Exception as exc:
            raise P3PersistenceError(
                "P3_MANAGED_OBJECT_INVALID",
                expected_uri,
            ) from exc
        if hashlib.sha256(data).hexdigest() != expected_hash:
            raise P3PersistenceError(
                "P3_MANAGED_OBJECT_HASH_MISMATCH",
                expected_uri,
            )
        existing = self._rows.one(
            "registry.object_reference",
            where={"object_ref_id": value.object_ref_id},
            columns=("managed_uri", "artifact_sha256"),
        )
        if existing is not None:
            actual = self._managed_object_for_uri(
                str(existing["managed_uri"]),
                str(existing["artifact_sha256"]),
            )
            if actual != value:
                raise P3PersistenceError(
                    "P3_IMMUTABLE_CONFLICT",
                    value.object_ref_id,
                )
            stored = self._object_store.read_bytes(expected_uri)
            if hashlib.sha256(stored).hexdigest() != expected_hash:
                raise P3PersistenceError(
                    "P3_MANAGED_OBJECT_HASH_MISMATCH",
                    expected_uri,
                )
            return
        stored_object = self._object_store.put_bytes(expected_uri, data)
        if stored_object.artifact_sha256 != expected_hash:
            raise P3PersistenceError(
                "P3_MANAGED_OBJECT_HASH_MISMATCH",
                expected_uri,
            )
        self._rows.insert(
            "registry.object_reference",
            {
                "object_ref_id": value.object_ref_id,
                "managed_uri": value.managed_uri,
                "media_type": "application/json",
                "size_bytes": len(data),
                "artifact_sha256": value.artifact_sha256,
                "logical_content_hash": value.artifact_sha256,
                "storage_backend": "LOCAL_OBJECT_STORE",
                "sealed": value.sealed,
                "gc_state": value.gc_state,
                "gc_state_version": 0,
                "deleted_at": value.deleted_at,
            },
        )

    def register_component(
        self,
        *,
        segment: P3LifecycleSegment,
        validation: P3ModelValidationSnapshot,
        training: P3TrainingDatasetSnapshot,
        model_build: P3CapabilityModelBuild,
        surface_build: P3CapabilitySurfaceBuild,
        model_object: P3ManagedObject,
        surface_object: P3ManagedObject,
    ) -> None:
        model = model_build.model
        surface = surface_build.surface
        current = self._try_exact_component(model.capability_model_id)
        if current is not None:
            expected = P3TwinComponentBinding(
                model_build=model_build,
                surface_build=surface_build,
                model_object_ref_id=model_object.object_ref_id,
                surface_object_ref_id=surface_object.object_ref_id,
            )
            if current != expected:
                raise P3PersistenceError(
                    "P3_IMMUTABLE_CONFLICT",
                    model.capability_model_id,
                )
            return
        if (
            model.training_dataset_snapshot_id
            != training.dataset_snapshot_id
            or training.segment_snapshot_id
            != segment.segment_snapshot_id
            or training.validation_snapshot_id
            != validation.validation_snapshot_id
            or validation.training_dataset_snapshot_id
            != training.dataset_snapshot_id
            or surface.capability_model_id
            != model.capability_model_id
        ):
            raise P3PersistenceError(
                "P3_COMPONENT_BINDING_MISMATCH",
                model.capability_model_id,
            )
        if (
            hashlib.sha256(model_build.artifact_bytes).hexdigest()
            != model.model_artifact_hash
            or _canonical_bytes(dict(model_build.artifact))
            != model_build.artifact_bytes
            or hashlib.sha256(surface_build.dataset_bytes).hexdigest()
            != surface.dataset_hash
            or _canonical_bytes(dict(surface_build.dataset))
            != surface_build.dataset_bytes
        ):
            raise P3PersistenceError(
                "P3_COMPONENT_HASH_MISMATCH",
                model.capability_model_id,
            )
        self.register_segment(segment)
        self.register_validation(validation, segment=segment)
        self.register_training(training)
        self._register_managed_object(
            model_object,
            expected_uri=model.model_artifact_uri,
            expected_hash=model.model_artifact_hash,
            data=model_build.artifact_bytes,
        )
        self._register_managed_object(
            surface_object,
            expected_uri=surface.dataset_uri,
            expected_hash=surface.dataset_hash,
            data=surface_build.dataset_bytes,
        )
        self._rows.insert(
            "capability.capability_model",
            {
                "capability_model_id": model.capability_model_id,
                "model_spec_id": model.model_spec_id,
                "model_spec_version": model.model_spec_version,
                "subject_type": model.subject_type,
                "subject_id": model.subject_id,
                "capability_type": model.capability_type,
                "training_dataset_snapshot_id": (
                    model.training_dataset_snapshot_id
                ),
                "plugin_name": model.plugin_name,
                "plugin_version": model.plugin_version,
                "model_artifact_uri": model.model_artifact_uri,
                "model_artifact_hash": model.model_artifact_hash,
                "validity_domain": dict(model.validity_domain),
                "validation_metrics": dict(model.validation_metrics),
                "status": model.status,
                "trained_at": model.trained_at,
                "published_at": model.published_at,
                "supersedes_model_id": model.supersedes_model_id,
            },
            field_kinds={
                "validity_domain": "json",
                "validation_metrics": "json",
            },
        )
        self._rows.insert(
            "capability.capability_surface",
            {
                "surface_id": surface.surface_id,
                "capability_model_id": surface.capability_model_id,
                "surface_semantics": surface.surface_semantics,
                "axes": dict(surface.axes),
                "dataset_uri": surface.dataset_uri,
                "dataset_hash": surface.dataset_hash,
                "uncertainty_dataset_uri": (
                    surface.uncertainty_dataset_uri
                ),
                "validity_domain": dict(surface.validity_domain),
                "created_at": surface.created_at,
            },
            field_kinds={
                "axes": "json",
                "validity_domain": "json",
            },
        )

    def _model(self, model_id: str) -> P3CapabilityModelProduct | None:
        row = self._rows.one(
            "capability.capability_model",
            where={"capability_model_id": model_id},
            columns=(
                "capability_model_id",
                "model_spec_id",
                "model_spec_version",
                "subject_type",
                "subject_id",
                "capability_type",
                "training_dataset_snapshot_id",
                "plugin_name",
                "plugin_version",
                "model_artifact_uri",
                "model_artifact_hash",
                "validity_domain",
                "validation_metrics",
                "status",
                "trained_at",
                "published_at",
                "supersedes_model_id",
            ),
        )
        if row is None:
            return None
        if row["subject_id"] is None:
            raise P3PersistenceError(
                "P3_MODEL_SUBJECT_REQUIRED",
                model_id,
            )
        return P3CapabilityModelProduct(
            capability_model_id=str(row["capability_model_id"]),
            model_spec_id=str(row["model_spec_id"]),
            model_spec_version=str(row["model_spec_version"]),
            subject_type=str(row["subject_type"]),
            subject_id=str(row["subject_id"]),
            capability_type=str(row["capability_type"]),
            training_dataset_snapshot_id=str(
                row["training_dataset_snapshot_id"]
            ),
            plugin_name=str(row["plugin_name"]),
            plugin_version=str(row["plugin_version"]),
            model_artifact_uri=str(row["model_artifact_uri"]),
            model_artifact_hash=str(row["model_artifact_hash"]),
            validity_domain=_mapping(
                row["validity_domain"],
                "capability_model.validity_domain",
            ),
            validation_metrics=_mapping(
                row["validation_metrics"],
                "capability_model.validation_metrics",
            ),
            status=str(row["status"]),
            trained_at=_time_text(row["trained_at"]),
            published_at=(
                None
                if row["published_at"] is None
                else _time_text(row["published_at"])
            ),
            supersedes_model_id=_optional_text(
                row["supersedes_model_id"]
            ),
        )

    def exact_model_build(
        self,
        model_id: str,
    ) -> P3CapabilityModelBuild:
        model = self._model(model_id)
        if model is None:
            raise P3PersistenceError("P3_MODEL_NOT_FOUND", model_id)
        if self._object_store is None:
            raise P3PersistenceError(
                "P3_OBJECT_STORE_REQUIRED",
                model_id,
            )
        managed = self._managed_object_for_uri(
            model.model_artifact_uri,
            model.model_artifact_hash,
        )
        data = self._object_store.read_bytes(managed.managed_uri)
        if hashlib.sha256(data).hexdigest() != model.model_artifact_hash:
            raise P3PersistenceError(
                "P3_MODEL_HASH_MISMATCH",
                model_id,
            )
        try:
            artifact_value: object = json.loads(data.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise P3PersistenceError(
                "P3_MODEL_ARTIFACT_INVALID",
                model_id,
            ) from exc
        artifact = _mapping(artifact_value, "model_artifact")
        if _canonical_bytes(artifact) != data:
            raise P3PersistenceError(
                "P3_MODEL_ARTIFACT_NONCANONICAL",
                model_id,
            )
        training = self.exact_training(
            model.training_dataset_snapshot_id
        )
        fit_ids = _strings(
            artifact.get("fit_window_estimate_ids"),
            "model.fit_window_estimate_ids",
        )
        session_by_estimate = dict(
            zip(
                training.estimate_ids,
                training.session_orders,
                strict=True,
            )
        )
        if not fit_ids or fit_ids[0] not in session_by_estimate:
            raise P3PersistenceError(
                "P3_MODEL_TRAINING_MEMBERSHIP_MISMATCH",
                model_id,
            )
        if (
            artifact.get("training_dataset_snapshot_id")
            != model.training_dataset_snapshot_id
            or artifact.get("aircraft_id") != model.subject_id
            or artifact.get("capability_type")
            != model.capability_type
            or _mapping(
                artifact.get("validity_domain"),
                "model.validity_domain",
            )
            != dict(model.validity_domain)
            or _mapping(
                artifact.get("validation_metrics"),
                "model.validation_metrics",
            )
            != dict(model.validation_metrics)
        ):
            raise P3PersistenceError(
                "P3_MODEL_ARTIFACT_PROJECTION_MISMATCH",
                model_id,
            )
        return P3CapabilityModelBuild(
            model=model,
            artifact=artifact,
            artifact_bytes=data,
            intercept=_required_float(
                artifact.get("intercept"),
                "model.intercept",
            ),
            slope=_required_float(
                artifact.get("slope"),
                "model.slope",
            ),
            current_value=_required_float(
                artifact.get("current_value"),
                "model.current_value",
            ),
            ewma_value=_required_float(
                artifact.get("ewma_value"),
                "model.ewma_value",
            ),
            stability_mad=_required_float(
                artifact.get("stability_mad"),
                "model.stability_mad",
            ),
            p3_uncertainty_half_width=_required_float(
                artifact.get("p3_uncertainty_half_width"),
                "model.p3_uncertainty_half_width",
            ),
            session_order_origin=session_by_estimate[fit_ids[0]],
            fit_estimate_ids=fit_ids,
        )

    def exact_surface_build(
        self,
        model_id: str,
    ) -> P3CapabilitySurfaceBuild:
        rows = self._rows.many(
            "capability.capability_surface",
            where={"capability_model_id": model_id},
            columns=(
                "surface_id",
                "capability_model_id",
                "surface_semantics",
                "axes",
                "dataset_uri",
                "dataset_hash",
                "uncertainty_dataset_uri",
                "validity_domain",
                "created_at",
            ),
        )
        if len(rows) != 1:
            raise P3PersistenceError(
                "P3_SURFACE_CARDINALITY_INVALID",
                f"{model_id}:{len(rows)}",
            )
        row = rows[0]
        surface = P3CapabilitySurfaceProduct(
            surface_id=str(row["surface_id"]),
            capability_model_id=str(row["capability_model_id"]),
            surface_semantics=str(row["surface_semantics"]),
            axes=_mapping(row["axes"], "surface.axes"),
            dataset_uri=str(row["dataset_uri"]),
            dataset_hash=str(row["dataset_hash"]),
            uncertainty_dataset_uri=_optional_text(
                row["uncertainty_dataset_uri"]
            ),
            validity_domain=_mapping(
                row["validity_domain"],
                "surface.validity_domain",
            ),
            created_at=_time_text(row["created_at"]),
        )
        if self._object_store is None:
            raise P3PersistenceError(
                "P3_OBJECT_STORE_REQUIRED",
                surface.surface_id,
            )
        managed = self._managed_object_for_uri(
            surface.dataset_uri,
            surface.dataset_hash,
        )
        data = self._object_store.read_bytes(managed.managed_uri)
        if hashlib.sha256(data).hexdigest() != surface.dataset_hash:
            raise P3PersistenceError(
                "P3_SURFACE_HASH_MISMATCH",
                surface.surface_id,
            )
        try:
            dataset_value: object = json.loads(data.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise P3PersistenceError(
                "P3_SURFACE_DATASET_INVALID",
                surface.surface_id,
            ) from exc
        dataset = _mapping(dataset_value, "surface_dataset")
        model = self._model(model_id)
        if model is None:
            raise P3PersistenceError("P3_MODEL_NOT_FOUND", model_id)
        if (
            _canonical_bytes(dataset) != data
            or dataset.get("capability_model_id") != model_id
            or dataset.get("model_artifact_hash")
            != model.model_artifact_hash
            or dataset.get("surface_semantics")
            != surface.surface_semantics
            or _mapping(
                dataset.get("validity_domain"),
                "surface_dataset.validity_domain",
            )
            != dict(surface.validity_domain)
        ):
            raise P3PersistenceError(
                "P3_SURFACE_PROJECTION_MISMATCH",
                surface.surface_id,
            )
        return P3CapabilitySurfaceBuild(
            surface=surface,
            dataset=dataset,
            dataset_bytes=data,
        )

    def _try_exact_component(
        self,
        model_id: str,
    ) -> P3TwinComponentBinding | None:
        model = self._model(model_id)
        if model is None:
            return None
        model_build = self.exact_model_build(model_id)
        surface_build = self.exact_surface_build(model_id)
        model_object = self._managed_object_for_uri(
            model.model_artifact_uri,
            model.model_artifact_hash,
        )
        surface_object = self._managed_object_for_uri(
            surface_build.surface.dataset_uri,
            surface_build.surface.dataset_hash,
        )
        return P3TwinComponentBinding(
            model_build=model_build,
            surface_build=surface_build,
            model_object_ref_id=model_object.object_ref_id,
            surface_object_ref_id=surface_object.object_ref_id,
        )

    def exact_component(
        self,
        model_id: str,
    ) -> P3TwinComponentBinding:
        value = self._try_exact_component(model_id)
        if value is None:
            raise P3PersistenceError(
                "P3_COMPONENT_NOT_FOUND",
                model_id,
            )
        return value

    def register_twin(
        self,
        value: P3AircraftTwinRevision,
        *,
        components: tuple[P3TwinComponentBinding, ...],
    ) -> None:
        current = self._try_exact_twin(value.twin_revision_id)
        if current is not None:
            if (
                current != value
                or self.exact_twin_components(value.twin_revision_id)
                != components
            ):
                raise P3PersistenceError(
                    "P3_IMMUTABLE_CONFLICT",
                    value.twin_revision_id,
                )
            return
        if (
            tuple(
                item.model_build.model.capability_model_id
                for item in components
            )
            != value.component_model_refs
        ):
            raise P3PersistenceError(
                "P3_TWIN_COMPONENT_ORDER_MISMATCH",
                value.twin_revision_id,
            )
        for component in components:
            exact = self.exact_component(
                component.model_build.model.capability_model_id
            )
            if exact != component:
                raise P3PersistenceError(
                    "P3_TWIN_COMPONENT_MISMATCH",
                    value.twin_revision_id,
                )
        self._rows.insert(
            "capability.aircraft_twin_revision",
            {
                "twin_revision_id": value.twin_revision_id,
                "aircraft_id": value.aircraft_id,
                "revision_no": value.revision_no,
                "component_model_refs": value.component_model_refs,
                "config_snapshot_id": value.config_snapshot_id,
                "valid_from": value.valid_from,
                "valid_to": value.valid_to,
                "as_of_data_time": value.as_of_data_time,
                "published_at": value.published_at,
                "status": value.status,
                "uncertainty_summary": dict(
                    value.uncertainty_summary
                ),
                "evidence_snapshot_id": value.evidence_snapshot_id,
                "supersedes_twin_revision_id": (
                    value.supersedes_twin_revision_id
                ),
            },
            field_kinds={
                "component_model_refs": "uuid_array",
                "uncertainty_summary": "json",
            },
        )

    def _try_exact_twin(
        self,
        twin_revision_id: str,
    ) -> P3AircraftTwinRevision | None:
        row = self._rows.one(
            "capability.aircraft_twin_revision",
            where={"twin_revision_id": twin_revision_id},
            columns=(
                "twin_revision_id",
                "aircraft_id",
                "revision_no",
                "component_model_refs",
                "config_snapshot_id",
                "valid_from",
                "valid_to",
                "as_of_data_time",
                "published_at",
                "status",
                "uncertainty_summary",
                "evidence_snapshot_id",
                "supersedes_twin_revision_id",
            ),
        )
        if row is None:
            return None
        if row["config_snapshot_id"] is None:
            raise P3PersistenceError(
                "P3_TWIN_CONFIG_REQUIRED",
                twin_revision_id,
            )
        return P3AircraftTwinRevision(
            twin_revision_id=str(row["twin_revision_id"]),
            aircraft_id=str(row["aircraft_id"]),
            revision_no=_required_int(
                row["revision_no"],
                "twin.revision_no",
            ),
            component_model_refs=_strings(
                row["component_model_refs"],
                "twin.component_model_refs",
            ),
            config_snapshot_id=str(row["config_snapshot_id"]),
            valid_from=_time_text(row["valid_from"]),
            valid_to=(
                None
                if row["valid_to"] is None
                else _time_text(row["valid_to"])
            ),
            as_of_data_time=_time_text(row["as_of_data_time"]),
            published_at=_time_text(row["published_at"]),
            status=str(row["status"]),
            uncertainty_summary=_mapping(
                row["uncertainty_summary"],
                "twin.uncertainty_summary",
            ),
            evidence_snapshot_id=str(row["evidence_snapshot_id"]),
            supersedes_twin_revision_id=_optional_text(
                row["supersedes_twin_revision_id"]
            ),
        )

    def exact_twin_revision(
        self,
        twin_revision_id: str,
    ) -> P3AircraftTwinRevision:
        value = self._try_exact_twin(twin_revision_id)
        if value is None:
            raise P3PersistenceError(
                "P3_TWIN_NOT_FOUND",
                twin_revision_id,
            )
        return value

    def exact_twin_components(
        self,
        twin_revision_id: str,
    ) -> tuple[P3TwinComponentBinding, ...]:
        twin = self.exact_twin_revision(twin_revision_id)
        return tuple(
            self.exact_component(model_id)
            for model_id in twin.component_model_refs
        )

    def estimate_ids_for_twin(
        self,
        twin_revision_id: str,
    ) -> tuple[str, ...]:
        self.exact_twin_revision(twin_revision_id)
        rows = self._rows.many(
            "capability.intrinsic_capability_estimate",
            where={"twin_revision_id": twin_revision_id},
            columns=("estimate_id",),
            order_by=("estimate_id",),
        )
        return tuple(str(row["estimate_id"]) for row in rows)

    def register_estimate(
        self,
        value: P3CapabilityEstimate,
    ) -> None:
        current = self._try_exact_estimate(value.estimate_id)
        if current is not None:
            if current != value:
                raise P3PersistenceError(
                    "P3_IMMUTABLE_CONFLICT",
                    value.estimate_id,
                )
            return
        profile = P3ModelExecutionProfile.from_canonical()
        try:
            assert_p3_claim_level(value.claim_level)
        except Exception as exc:
            raise P3PersistenceError(
                "P3_ESTIMATE_CLAIM_INVALID",
                value.estimate_id,
            ) from exc
        if value.claim_level != profile.estimate_claim_level:
            raise P3PersistenceError(
                "P3_ESTIMATE_CLAIM_INVALID",
                value.estimate_id,
            )
        twin = self.exact_twin_revision(value.twin_revision_id)
        components = self.exact_twin_components(
            value.twin_revision_id
        )
        matching = [
            item
            for item in components
            if item.model_build.model.capability_type
            == value.capability_type
        ]
        if len(matching) != 1:
            raise P3PersistenceError(
                "P3_ESTIMATE_COMPONENT_MISMATCH",
                value.estimate_id,
            )
        component = matching[0]
        uncertainty = dict(value.uncertainty)
        if (
            twin.aircraft_id
            != component.model_build.model.subject_id
            or uncertainty.get("surface_id")
            != component.surface_build.surface.surface_id
            or uncertainty.get("surface_dataset_hash")
            != component.surface_build.surface.dataset_hash
        ):
            raise P3PersistenceError(
                "P3_ESTIMATE_COMPONENT_MISMATCH",
                value.estimate_id,
            )
        self._rows.insert(
            "capability.intrinsic_capability_estimate",
            {
                "estimate_id": value.estimate_id,
                "twin_revision_id": value.twin_revision_id,
                "capability_type": value.capability_type,
                "condition_point": dict(value.condition_point),
                "value": value.value,
                "unit": value.unit,
                "uncertainty": uncertainty,
                "validity_domain_status": (
                    value.validity_domain_status
                ),
                "as_of_time": value.as_of_time,
                "created_at": value.created_at,
            },
            field_kinds={
                "condition_point": "json",
                "uncertainty": "json",
            },
        )

    def _try_exact_estimate(
        self,
        estimate_id: str,
    ) -> P3CapabilityEstimate | None:
        row = self._rows.one(
            "capability.intrinsic_capability_estimate",
            where={"estimate_id": estimate_id},
            columns=(
                "estimate_id",
                "twin_revision_id",
                "capability_type",
                "condition_point",
                "value",
                "unit",
                "uncertainty",
                "validity_domain_status",
                "as_of_time",
                "created_at",
            ),
        )
        if row is None:
            return None
        profile = P3ModelExecutionProfile.from_canonical()
        value = P3CapabilityEstimate(
            estimate_id=str(row["estimate_id"]),
            twin_revision_id=str(row["twin_revision_id"]),
            capability_type=str(row["capability_type"]),
            condition_point=_mapping(
                row["condition_point"],
                "estimate.condition_point",
            ),
            value=_optional_float(row["value"]),
            unit=str(row["unit"]),
            uncertainty=_mapping(
                row["uncertainty"],
                "estimate.uncertainty",
            ),
            validity_domain_status=str(
                row["validity_domain_status"]
            ),
            claim_level=profile.estimate_claim_level,
            as_of_time=_time_text(row["as_of_time"]),
            created_at=_time_text(row["created_at"]),
        )
        try:
            assert_p3_claim_level(value.claim_level)
        except Exception as exc:
            raise P3PersistenceError(
                "P3_ESTIMATE_CLAIM_INVALID",
                estimate_id,
            ) from exc
        return value

    def exact_capability_estimate(
        self,
        estimate_id: str,
    ) -> P3CapabilityEstimate:
        value = self._try_exact_estimate(estimate_id)
        if value is None:
            raise P3PersistenceError(
                "P3_ESTIMATE_NOT_FOUND",
                estimate_id,
            )
        return value


class P3WorkspaceLayerResolver(Protocol):
    """Resolve exact immutable P1/P2 layers without P3-owned copies."""

    def resolve(
        self,
        *,
        estimate: P3CapabilityEstimate,
        twin: P3AircraftTwinRevision,
        components: tuple[P3TwinComponentBinding, ...],
    ) -> tuple[M7LayerEvidence, M7LayerEvidence]: ...


class CanonicalP3WorkspaceLayerResolver:
    """Resolve M7 upstream layers from exact P2 and P1 authority."""

    _OBSERVATION_COLUMNS = (
        "observation_id",
        "release_id",
        "session_id",
        "episode_id",
        "stage_id",
        "aircraft_id",
        "aircraft_instance_id",
        "subject_entity_id",
        "aircraft_model_id",
        "aircraft_configuration_snapshot_id",
        "context_id",
        "capability_type",
        "capability_level",
        "observed_metric_instance_id",
        "observed_value_numeric",
        "unit",
        "observation_start_session_time_us",
        "observation_end_session_time_us",
        "context_tags",
        "evidence_set_id",
        "coverage",
        "confidence",
        "eligibility_status",
        "exclusion_reason_code",
        "correlation_group_id",
        "comparison_key_hash",
        "observation_schema_version",
        "created_at",
        "supersedes_observation_id",
    )

    def __init__(
        self,
        rows: CanonicalRowRepository,
        p3: P3PersistenceRepository,
        p2: P2PersistenceRepository,
    ) -> None:
        self._rows = rows
        self._p3 = p3
        self._p2 = p2

    def _release_status(self, release_id: str) -> str:
        row = self._rows.one(
            "registry.analysis_release",
            where={"release_id": release_id},
            columns=("status",),
        )
        if row is None:
            raise P3PersistenceError(
                "P3_UPSTREAM_RELEASE_NOT_FOUND",
                release_id,
            )
        return str(row["status"])

    def _selected_p2_estimate_id(
        self,
        *,
        estimate: P3CapabilityEstimate,
        components: tuple[P3TwinComponentBinding, ...],
    ) -> str:
        matches = [
            item
            for item in components
            if item.model_build.model.capability_type
            == estimate.capability_type
        ]
        if len(matches) != 1:
            raise P3PersistenceError(
                "P3_UPSTREAM_COMPONENT_AMBIGUOUS",
                estimate.estimate_id,
            )
        session_order = estimate.condition_point.get(
            "session_order"
        )
        if isinstance(session_order, bool) or not isinstance(
            session_order,
            int,
        ):
            raise P3PersistenceError(
                "P3_UPSTREAM_SESSION_ORDER_INVALID",
                estimate.estimate_id,
            )
        training = self._p3.exact_training(
            matches[0].model_build.model.training_dataset_snapshot_id
        )
        selected = [
            estimate_id
            for estimate_id, order in zip(
                training.estimate_ids,
                training.session_orders,
                strict=True,
            )
            if order == session_order
        ]
        if len(selected) != 1:
            raise P3PersistenceError(
                "P3_UPSTREAM_P2_MEMBERSHIP_AMBIGUOUS",
                estimate.estimate_id,
            )
        return selected[0]

    def resolve(
        self,
        *,
        estimate: P3CapabilityEstimate,
        twin: P3AircraftTwinRevision,
        components: tuple[P3TwinComponentBinding, ...],
    ) -> tuple[M7LayerEvidence, M7LayerEvidence]:
        p2_id = self._selected_p2_estimate_id(
            estimate=estimate,
            components=components,
        )
        p2 = self._p2.exact_adjusted_estimate(p2_id)
        if (
            p2.aircraft_id != twin.aircraft_id
            or p2.capability_type != estimate.capability_type
            or p2.status != "IDENTIFIABLE"
            or self._release_status(p2.p2_release_id)
            != "PUBLISHED"
            or self._release_status(p2.source_release_id)
            != "PUBLISHED"
        ):
            raise P3PersistenceError(
                "P3_UPSTREAM_P2_BINDING_MISMATCH",
                p2_id,
            )
        observation = self._rows.one(
            "metric.capability_observation",
            where={
                "observation_id": p2.source_observation_id
            },
            columns=self._OBSERVATION_COLUMNS,
        )
        if observation is None:
            raise P3PersistenceError(
                "P3_UPSTREAM_P1_NOT_FOUND",
                p2.source_observation_id,
            )
        observed_value = _optional_float(
            observation["observed_value_numeric"]
        )
        if (
            str(observation["release_id"])
            != p2.source_release_id
            or str(observation["aircraft_id"])
            != p2.aircraft_id
            or str(observation["capability_type"])
            != p2.capability_type
            or observed_value is None
        ):
            raise P3PersistenceError(
                "P3_UPSTREAM_P1_BINDING_MISMATCH",
                p2.source_observation_id,
            )
        observed_projection = {
            "observation_id": str(
                observation["observation_id"]
            ),
            "release_id": str(observation["release_id"]),
            "session_id": str(observation["session_id"]),
            "episode_id": str(observation["episode_id"]),
            "stage_id": _optional_text(
                observation["stage_id"]
            ),
            "aircraft_id": str(observation["aircraft_id"]),
            "aircraft_instance_id": str(
                observation["aircraft_instance_id"]
            ),
            "subject_entity_id": str(
                observation["subject_entity_id"]
            ),
            "aircraft_model_id": str(
                observation["aircraft_model_id"]
            ),
            "aircraft_configuration_snapshot_id": (
                _optional_text(
                    observation[
                        "aircraft_configuration_snapshot_id"
                    ]
                )
            ),
            "context_id": str(observation["context_id"]),
            "capability_type": str(
                observation["capability_type"]
            ),
            "capability_level": str(
                observation["capability_level"]
            ),
            "observed_metric_instance_id": str(
                observation["observed_metric_instance_id"]
            ),
            "observed_value": observed_value,
            "unit": str(observation["unit"]),
            "observation_start_session_time_us": (
                _required_int(
                    observation[
                        "observation_start_session_time_us"
                    ],
                    "observation.start",
                )
            ),
            "observation_end_session_time_us": (
                _required_int(
                    observation[
                        "observation_end_session_time_us"
                    ],
                    "observation.end",
                )
            ),
            "context_tags": _mapping(
                observation["context_tags"],
                "observation.context_tags",
            ),
            "evidence_set_id": str(
                observation["evidence_set_id"]
            ),
            "coverage": _required_float(
                observation["coverage"],
                "observation.coverage",
            ),
            "confidence": _required_float(
                observation["confidence"],
                "observation.confidence",
            ),
            "eligibility_status": str(
                observation["eligibility_status"]
            ),
            "exclusion_reason_code": _optional_text(
                observation["exclusion_reason_code"]
            ),
            "correlation_group_id": _optional_text(
                observation["correlation_group_id"]
            ),
            "comparison_key_hash": str(
                observation["comparison_key_hash"]
            ),
            "observation_schema_version": str(
                observation["observation_schema_version"]
            ),
            "created_at": _time_text(
                observation["created_at"]
            ),
            "supersedes_observation_id": _optional_text(
                observation["supersedes_observation_id"]
            ),
        }
        adjusted_projection = {
            "estimate_id": p2.estimate_id,
            "source_observation_id": p2.source_observation_id,
            "source_release_id": p2.source_release_id,
            "p2_release_id": p2.p2_release_id,
            "attribution_run_id": p2.attribution_run_id,
            "aircraft_id": p2.aircraft_id,
            "capability_type": p2.capability_type,
            "reference_condition_id": (
                p2.reference_condition_id
            ),
            "adjusted_value": p2.adjusted_value,
            "unit": p2.unit,
            "uncertainty": {
                "lower": p2.uncertainty_lower,
                "upper": p2.uncertainty_upper,
                "method": p2.uncertainty_method,
                "level": p2.uncertainty_level,
            },
            "residual": p2.residual,
            "factor_effects": p2.factor_effect_mapping(),
            "claim_level": p2.claim_level,
            "status": p2.status,
            "reason_codes": list(p2.reason_codes),
            "evidence_set_id": p2.evidence_set_id,
            "estimate_time": p2.estimate_time,
            "created_at": p2.created_at,
            "supersedes_estimate_id": (
                p2.supersedes_estimate_id
            ),
            "source_logical_hash": p2.logical_hash,
        }
        return (
            M7LayerEvidence(
                layer="P1_OBSERVED",
                release_id=p2.source_release_id,
                logical_hash=_canonical_hash(
                    observed_projection
                ),
                projection=observed_projection,
            ),
            M7LayerEvidence(
                layer="P2_ADJUSTED",
                release_id=p2.p2_release_id,
                logical_hash=_canonical_hash(
                    adjusted_projection
                ),
                projection=adjusted_projection,
            ),
        )


class DurableM7P3WorkspaceRepository:
    """M7 port backed by durable P3 plus exact upstream P1/P2 authority."""

    def __init__(
        self,
        persistence: P3PersistenceRepository,
        resolver: P3WorkspaceLayerResolver,
    ) -> None:
        self._persistence = persistence
        self._resolver = resolver

    def _snapshot(
        self,
        estimate_id: str,
    ) -> M7P3WorkspaceSnapshot:
        estimate = self._persistence.exact_capability_estimate(
            estimate_id
        )
        twin = self._persistence.exact_twin_revision(
            estimate.twin_revision_id
        )
        components = self._persistence.exact_twin_components(
            twin.twin_revision_id
        )
        observed, adjusted = self._resolver.resolve(
            estimate=estimate,
            twin=twin,
            components=components,
        )
        return M7P3WorkspaceSnapshot(
            observed=observed,
            adjusted=adjusted,
            twin=twin,
            estimate=estimate,
            components=components,
        )

    def exact_estimate(
        self,
        estimate_id: str,
    ) -> M7P3WorkspaceSnapshot:
        return self._snapshot(estimate_id)

    def exact_twin(
        self,
        twin_revision_id: str,
    ) -> M7P3WorkspaceSnapshot:
        estimate_ids = self._persistence.estimate_ids_for_twin(
            twin_revision_id
        )
        if len(estimate_ids) != 1:
            raise P3PersistenceError(
                "P3_M7_TWIN_ESTIMATE_AMBIGUOUS",
                f"{twin_revision_id}:{len(estimate_ids)}",
            )
        snapshot = self._snapshot(estimate_ids[0])
        if snapshot.twin.twin_revision_id != twin_revision_id:
            raise P3PersistenceError(
                "P3_M7_TWIN_ESTIMATE_MISMATCH",
                twin_revision_id,
            )
        return snapshot
