"""PIQB B2 durable P6 substrate over adopted DB 1.8 canonical relations."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid5

from tpaa_capability import (
    P6ContextRef,
    P6CounterfactualRequestBinding,
    P6FactualSourceRevision,
    P6ForecastExecutionProfile,
    P6ForecastRequestBinding,
    P6InputSnapshot,
    P6ManagedModelObject,
    P6ModelBuild,
    P6ModelDatasetSnapshot,
    P6ModelRevision,
    P6P3ModelRef,
    assert_p6_input_snapshot_identity,
    validate_p6_managed_model_object,
)
from tpaa_context.p6_governance import canonical_hash
from tpaa_storage.canonical_rows import CanonicalRowRepository

_INPUT_NAMESPACE = UUID("7256bfa5-8cb5-54c4-9174-1324fe77f4db")
_FORECAST_REQUEST_NAMESPACE = UUID("55585db6-8d47-5fcb-8b92-cfbe1b468592")
_COUNTERFACTUAL_REQUEST_NAMESPACE = UUID("3a205859-8096-5d99-bf08-1d89d16442b0")
_INPUT_PREFIX = "P6_INPUT_SHA256:"
_FORECAST_REQUEST_PREFIX = "P6_FORECAST_REQUEST_SHA256:"
_COUNTERFACTUAL_REQUEST_PREFIX = "P6_COUNTERFACTUAL_REQUEST_SHA256:"
_INPUT_SCHEMA = "TPAA_P6_INPUT_SNAPSHOT_MANIFEST_V1"
_MODEL_DATASET_SCHEMA = "TPAA_P6_MODEL_DATASET_MANIFEST_V1"


class P6PersistenceError(RuntimeError):
    """Fail-closed exact persistence error for P6 durable products."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


class P6ObjectStore(Protocol):
    """Minimal managed-object port required by durable P6 model persistence."""

    def put_bytes(self, logical_uri: str, data: bytes) -> object: ...

    def read_bytes(self, logical_uri: str) -> bytes: ...


class P6ModelBuildResolver(Protocol):
    """Rehydrate training rows from durable P3/P4 authority, never model JSON."""

    def rebuild(
        self,
        *,
        model: P6ModelRevision,
        artifact: Mapping[str, object],
        artifact_bytes: bytes,
        training: P6ModelDatasetSnapshot,
        validation: P6ModelDatasetSnapshot,
    ) -> P6ModelBuild: ...


def _time_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        normalized = value
        if normalized.tzinfo is not None:
            normalized = normalized.astimezone(UTC)
        return normalized.isoformat().replace("+00:00", "Z")
    raise P6PersistenceError("P6_DB_TIME_INVALID", type(value).__name__)


def _mapping(value: object, field: str) -> dict[str, object]:
    decoded: object = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise P6PersistenceError("P6_DB_JSON_INVALID", field) from exc
    if not isinstance(decoded, Mapping):
        raise P6PersistenceError("P6_DB_JSON_INVALID", field)
    return {str(key): item for key, item in decoded.items()}


def _strings(value: object, field: str) -> tuple[str, ...]:
    decoded: object = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise P6PersistenceError("P6_DB_ARRAY_INVALID", field) from exc
    if not isinstance(decoded, (list, tuple)):
        raise P6PersistenceError("P6_DB_ARRAY_INVALID", field)
    result: list[str] = []
    for item in decoded:
        if isinstance(item, UUID):
            result.append(str(item))
        elif isinstance(item, str):
            result.append(item)
        else:
            raise P6PersistenceError("P6_DB_ARRAY_INVALID", field)
    return tuple(result)


def _manifest_strings(manifest: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = manifest.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise P6PersistenceError("P6_MANIFEST_INVALID", key)
    return tuple(value)


def _bool(value: object, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    raise P6PersistenceError("P6_DB_BOOLEAN_INVALID", field)


def _digest(logical_id: str, prefix: str) -> str:
    if not logical_id.startswith(prefix):
        raise P6PersistenceError("P6_LOGICAL_ID_INVALID", logical_id)
    value = logical_id[len(prefix) :]
    if len(value) != 64:
        raise P6PersistenceError("P6_LOGICAL_ID_INVALID", logical_id)
    try:
        int(value, 16)
    except ValueError as exc:
        raise P6PersistenceError("P6_LOGICAL_ID_INVALID", logical_id) from exc
    return value.lower()


def _physical(namespace: UUID, logical_id: str, prefix: str) -> str:
    _digest(logical_id, prefix)
    return str(uuid5(namespace, logical_id))


def _input_manifest(value: P6InputSnapshot) -> dict[str, object]:
    return {
        "schema": _INPUT_SCHEMA,
        "factual_source_refs": list(value.factual_source_refs),
        "p3_model_refs": list(value.p3_model_refs),
        "scenario_context_refs": list(value.scenario_context_refs),
        "target_scope": value.target_scope,
        "subject_or_composition_ref": value.subject_or_composition_ref,
        "forecast_origin_utc": value.forecast_origin_utc,
        "as_of_utc": value.as_of_utc,
        "availability_status": value.availability_status,
        "reason_codes": list(value.reason_codes),
        "source_bindings": [
            {
                "phase": item.phase,
                "revision_id": item.revision_id,
                "publication_status": item.publication_status,
                "knowledge_time_utc": item.knowledge_time_utc,
                "is_target_outcome": item.is_target_outcome,
                "is_post_horizon_outcome": item.is_post_horizon_outcome,
            }
            for item in value.source_bindings
        ],
        "p3_bindings": [
            {
                "model_ref_id": item.model_ref_id,
                "publication_status": item.publication_status,
                "knowledge_time_utc": item.knowledge_time_utc,
            }
            for item in value.p3_bindings
        ],
        "context_bindings": [
            {
                "context_ref_id": item.context_ref_id,
                "status": item.status,
                "knowledge_time_utc": item.knowledge_time_utc,
            }
            for item in value.context_bindings
        ],
    }


def _forecast_request_hash(value: P6ForecastRequestBinding) -> str:
    return canonical_hash(
        {
            "input_snapshot_id": value.input_snapshot_id,
            "forecast_spec_id": value.forecast_spec_id,
            "forecast_spec_version": value.forecast_spec_version,
            "target_scope": value.target_scope,
            "subject_ref": value.subject_ref,
            "target_code": value.target_code,
            "forecast_origin_utc": value.forecast_origin_utc,
            "horizon_spec": dict(value.horizon_spec),
            "capability_model_id": value.capability_model_id,
            "model_profile_id": value.model_profile_id,
            "model_profile_version": value.model_profile_version,
            "training_dataset_snapshot_id": value.training_dataset_snapshot_id,
            "validation_dataset_snapshot_id": value.validation_dataset_snapshot_id,
            "assumption_profile_id": value.assumption_profile_id,
            "assumption_profile_version": value.assumption_profile_version,
            "as_of_utc": value.as_of_utc,
        }
    )


def _counterfactual_request_hash(value: P6CounterfactualRequestBinding) -> str:
    return canonical_hash(
        {
            "input_snapshot_id": value.input_snapshot_id,
            "base_product_refs": list(value.base_product_refs),
            "scenario_definition_id": value.scenario_definition_id,
            "interventions": dict(value.interventions),
            "held_fixed_assumptions": dict(value.held_fixed_assumptions),
            "model_refs": list(value.model_refs),
            "applicability_profile_ref": value.applicability_profile_ref,
            "as_of_utc": value.as_of_utc,
        }
    )


class P6PersistenceRepository:
    """DB 1.8 exact P6 substrate shared by SQLite and PostgreSQL."""

    def __init__(
        self,
        rows: CanonicalRowRepository,
        *,
        object_store: P6ObjectStore | None = None,
        model_build_resolver: P6ModelBuildResolver | None = None,
    ) -> None:
        self._rows = rows
        self._object_store = object_store
        self._model_build_resolver = model_build_resolver

    def register_input(self, value: P6InputSnapshot) -> None:
        current = self._try_input(value.input_snapshot_id)
        if current is not None:
            if current != value:
                raise P6PersistenceError("P6_IMMUTABLE_CONFLICT", value.input_snapshot_id)
            return
        assert_p6_input_snapshot_identity(value)
        refs = tuple(
            dict.fromkeys(
                value.factual_source_refs
                + value.p3_model_refs
                + value.scenario_context_refs
            )
        )
        self._rows.insert(
            "registry.dataset_snapshot",
            {
                "dataset_snapshot_id": _physical(
                    _INPUT_NAMESPACE,
                    value.input_snapshot_id,
                    _INPUT_PREFIX,
                ),
                "snapshot_type": value.snapshot_type,
                "query_or_manifest": _input_manifest(value),
                "input_refs": refs,
                "data_hash": value.data_hash,
                "schema_version": _INPUT_SCHEMA,
                "frozen": value.frozen,
            },
            field_kinds={
                "query_or_manifest": "json",
                "input_refs": "uuid_array",
            },
        )

    def _input_from_row(self, row: dict[str, object]) -> P6InputSnapshot:
        if str(row["schema_version"]) != _INPUT_SCHEMA:
            raise P6PersistenceError("P6_INPUT_SCHEMA_INVALID", str(row["schema_version"]))
        manifest = _mapping(row["query_or_manifest"], "dataset_snapshot.query_or_manifest")
        raw_sources = manifest.get("source_bindings")
        raw_p3 = manifest.get("p3_bindings")
        raw_context = manifest.get("context_bindings")
        if not isinstance(raw_sources, list) or not isinstance(raw_p3, list) or not isinstance(raw_context, list):
            raise P6PersistenceError("P6_MANIFEST_INVALID", "bindings")
        sources: list[P6FactualSourceRevision] = []
        for raw in raw_sources:
            item = _mapping(raw, "source_binding")
            sources.append(
                P6FactualSourceRevision(
                    phase=str(item["phase"]),
                    revision_id=str(item["revision_id"]),
                    publication_status=str(item["publication_status"]),
                    knowledge_time_utc=str(item["knowledge_time_utc"]),
                    is_target_outcome=bool(item.get("is_target_outcome", False)),
                    is_post_horizon_outcome=bool(
                        item.get("is_post_horizon_outcome", False)
                    ),
                )
            )
        p3_bindings: list[P6P3ModelRef] = []
        for raw in raw_p3:
            item = _mapping(raw, "p3_binding")
            p3_bindings.append(
                P6P3ModelRef(
                    model_ref_id=str(item["model_ref_id"]),
                    publication_status=str(item["publication_status"]),
                    knowledge_time_utc=str(item["knowledge_time_utc"]),
                )
            )
        context_bindings: list[P6ContextRef] = []
        for raw in raw_context:
            item = _mapping(raw, "context_binding")
            context_bindings.append(
                P6ContextRef(
                    context_ref_id=str(item["context_ref_id"]),
                    status=str(item["status"]),
                    knowledge_time_utc=str(item["knowledge_time_utc"]),
                )
            )
        data_hash = str(row["data_hash"])
        logical_id = f"{_INPUT_PREFIX}{data_hash}"
        if str(row["dataset_snapshot_id"]) != _physical(
            _INPUT_NAMESPACE,
            logical_id,
            _INPUT_PREFIX,
        ):
            raise P6PersistenceError("P6_PHYSICAL_ID_MISMATCH", logical_id)
        value = P6InputSnapshot(
            input_snapshot_id=logical_id,
            snapshot_type=str(row["snapshot_type"]),
            factual_source_refs=_manifest_strings(manifest, "factual_source_refs"),
            p3_model_refs=_manifest_strings(manifest, "p3_model_refs"),
            scenario_context_refs=_manifest_strings(
                manifest,
                "scenario_context_refs",
            ),
            target_scope=str(manifest["target_scope"]),
            subject_or_composition_ref=str(manifest["subject_or_composition_ref"]),
            forecast_origin_utc=str(manifest["forecast_origin_utc"]),
            as_of_utc=str(manifest["as_of_utc"]),
            data_hash=data_hash,
            availability_status=str(manifest["availability_status"]),
            reason_codes=_manifest_strings(manifest, "reason_codes"),
            source_bindings=tuple(sources),
            p3_bindings=tuple(p3_bindings),
            context_bindings=tuple(context_bindings),
            frozen=_bool(row["frozen"], "dataset_snapshot.frozen"),
        )
        assert_p6_input_snapshot_identity(value)
        expected_refs = tuple(
            dict.fromkeys(
                value.factual_source_refs
                + value.p3_model_refs
                + value.scenario_context_refs
            )
        )
        if _strings(row["input_refs"], "dataset_snapshot.input_refs") != expected_refs:
            raise P6PersistenceError("P6_INPUT_REF_PROJECTION_MISMATCH", logical_id)
        return value

    def _try_input(self, object_id: str) -> P6InputSnapshot | None:
        row = self._rows.one(
            "registry.dataset_snapshot",
            where={
                "dataset_snapshot_id": _physical(
                    _INPUT_NAMESPACE,
                    object_id,
                    _INPUT_PREFIX,
                )
            },
            columns=(
                "dataset_snapshot_id",
                "snapshot_type",
                "query_or_manifest",
                "input_refs",
                "data_hash",
                "schema_version",
                "frozen",
            ),
        )
        return None if row is None else self._input_from_row(row)

    def exact_input(self, object_id: str) -> P6InputSnapshot:
        value = self._try_input(object_id)
        if value is None:
            raise P6PersistenceError("M9_INPUT_NOT_FOUND", object_id)
        return value

    def _register_model_dataset(self, value: P6ModelDatasetSnapshot) -> None:
        current = self._try_model_dataset(value.dataset_snapshot_id)
        if current is not None:
            if current != value:
                raise P6PersistenceError(
                    "P6_IMMUTABLE_CONFLICT",
                    value.dataset_snapshot_id,
                )
            return
        profile = P6ForecastExecutionProfile.from_canonical()
        material = {
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
            "profile_sha256": profile.profile_sha256,
            "snapshot_type": value.snapshot_type,
            "row_ids": list(value.row_ids),
            "p3_estimate_ids": list(value.p3_estimate_ids),
            "p4_revision_ids": list(value.p4_revision_ids),
            "as_of_utc": value.as_of_utc,
            "frozen": value.frozen,
        }
        if canonical_hash(material) != value.data_hash:
            raise P6PersistenceError(
                "P6_MODEL_DATASET_HASH_MISMATCH",
                value.dataset_snapshot_id,
            )
        self._rows.insert(
            "registry.dataset_snapshot",
            {
                "dataset_snapshot_id": value.dataset_snapshot_id,
                "snapshot_type": value.snapshot_type,
                "query_or_manifest": {
                    "schema": _MODEL_DATASET_SCHEMA,
                    **material,
                },
                "input_refs": value.p3_estimate_ids + value.p4_revision_ids,
                "data_hash": value.data_hash,
                "schema_version": _MODEL_DATASET_SCHEMA,
                "frozen": value.frozen,
            },
            field_kinds={
                "query_or_manifest": "json",
                "input_refs": "uuid_array",
            },
        )

    def _try_model_dataset(
        self,
        dataset_snapshot_id: str,
    ) -> P6ModelDatasetSnapshot | None:
        row = self._rows.one(
            "registry.dataset_snapshot",
            where={"dataset_snapshot_id": dataset_snapshot_id},
            columns=(
                "dataset_snapshot_id",
                "snapshot_type",
                "query_or_manifest",
                "input_refs",
                "data_hash",
                "schema_version",
                "frozen",
            ),
        )
        if row is None:
            return None
        if str(row["schema_version"]) != _MODEL_DATASET_SCHEMA:
            raise P6PersistenceError(
                "P6_MODEL_DATASET_SCHEMA_INVALID",
                dataset_snapshot_id,
            )
        manifest = _mapping(row["query_or_manifest"], "dataset_snapshot.query_or_manifest")
        profile = P6ForecastExecutionProfile.from_canonical()
        value = P6ModelDatasetSnapshot(
            dataset_snapshot_id=str(row["dataset_snapshot_id"]),
            snapshot_type=str(row["snapshot_type"]),
            row_ids=_manifest_strings(manifest, "row_ids"),
            p3_estimate_ids=_manifest_strings(manifest, "p3_estimate_ids"),
            p4_revision_ids=_manifest_strings(manifest, "p4_revision_ids"),
            as_of_utc=str(manifest["as_of_utc"]),
            data_hash=str(row["data_hash"]),
            frozen=_bool(row["frozen"], "dataset_snapshot.frozen"),
        )
        material = {
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
            "profile_sha256": profile.profile_sha256,
            "snapshot_type": value.snapshot_type,
            "row_ids": list(value.row_ids),
            "p3_estimate_ids": list(value.p3_estimate_ids),
            "p4_revision_ids": list(value.p4_revision_ids),
            "as_of_utc": value.as_of_utc,
            "frozen": value.frozen,
        }
        if canonical_hash(material) != value.data_hash:
            raise P6PersistenceError(
                "P6_MODEL_DATASET_HASH_MISMATCH",
                dataset_snapshot_id,
            )
        if _strings(row["input_refs"], "dataset_snapshot.input_refs") != (
            value.p3_estimate_ids + value.p4_revision_ids
        ):
            raise P6PersistenceError(
                "P6_MODEL_DATASET_REF_MISMATCH",
                dataset_snapshot_id,
            )
        return value

    def exact_model_dataset(self, dataset_snapshot_id: str) -> P6ModelDatasetSnapshot:
        value = self._try_model_dataset(dataset_snapshot_id)
        if value is None:
            raise P6PersistenceError("P6_MODEL_DATASET_NOT_FOUND", dataset_snapshot_id)
        return value

    def register_model_build(
        self,
        build: P6ModelBuild,
        managed_object: P6ManagedModelObject,
    ) -> None:
        model = build.model
        current = self._try_model(model.capability_model_id)
        if current is not None:
            if current != model or self.exact_managed_object(model.capability_model_id) != managed_object:
                raise P6PersistenceError(
                    "P6_IMMUTABLE_CONFLICT",
                    model.capability_model_id,
                )
            return
        self._register_model_dataset(build.datasets.training)
        self._register_model_dataset(build.datasets.validation)
        artifact_hash = hashlib.sha256(build.artifact_bytes).hexdigest()
        if artifact_hash != model.model_artifact_hash:
            raise P6PersistenceError("P6_MODEL_HASH_MISMATCH", model.capability_model_id)
        if _mapping(build.artifact_bytes.decode("ascii"), "model_artifact") != dict(build.artifact):
            raise P6PersistenceError(
                "P6_MODEL_ARTIFACT_PROJECTION_MISMATCH",
                model.capability_model_id,
            )
        validate_p6_managed_model_object(model, managed_object)
        if self._object_store is None:
            raise P6PersistenceError(
                "P6_MODEL_OBJECT_STORE_REQUIRED",
                model.capability_model_id,
            )
        self._object_store.put_bytes(model.model_artifact_uri, build.artifact_bytes)
        if hashlib.sha256(
            self._object_store.read_bytes(model.model_artifact_uri)
        ).hexdigest() != model.model_artifact_hash:
            raise P6PersistenceError("P6_MODEL_HASH_MISMATCH", model.capability_model_id)
        self._rows.insert(
            "registry.object_reference",
            {
                "object_ref_id": managed_object.object_ref_id,
                "managed_uri": managed_object.managed_uri,
                "media_type": "application/json",
                "size_bytes": len(build.artifact_bytes),
                "artifact_sha256": managed_object.artifact_sha256,
                "logical_content_hash": managed_object.artifact_sha256,
                "storage_backend": "LOCAL_OBJECT_STORE",
                "sealed": managed_object.sealed,
                "gc_state": managed_object.gc_state,
                "gc_state_version": 0,
                "created_at": managed_object.sealed_at_utc,
                "deleted_at": managed_object.deleted_at,
            },
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
                "training_dataset_snapshot_id": model.training_dataset_snapshot_id,
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
            "capability.p6_model_revision",
            {
                "capability_model_id": model.capability_model_id,
                "validation_dataset_snapshot_id": model.validation_dataset_snapshot_id,
                "applicability_profile_ref": model.applicability_profile_ref,
                "uncertainty_profile_ref": model.uncertainty_profile_ref,
            },
        )

    def _try_model(self, model_id: str) -> P6ModelRevision | None:
        base = self._rows.one(
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
        if base is None:
            return None
        revision = self._rows.one(
            "capability.p6_model_revision",
            where={"capability_model_id": model_id},
            columns=(
                "validation_dataset_snapshot_id",
                "applicability_profile_ref",
                "uncertainty_profile_ref",
            ),
        )
        if revision is None:
            raise P6PersistenceError("P6_MODEL_REVISION_METADATA_MISSING", model_id)
        object_row = self._rows.one(
            "registry.object_reference",
            where={"managed_uri": str(base["model_artifact_uri"])},
            columns=(
                "object_ref_id",
                "artifact_sha256",
                "sealed",
                "gc_state",
                "deleted_at",
            ),
        )
        if object_row is None or base["subject_id"] is None:
            raise P6PersistenceError("P6_MODEL_OBJECT_NOT_FOUND", model_id)
        value = P6ModelRevision(
            capability_model_id=str(base["capability_model_id"]),
            model_spec_id=str(base["model_spec_id"]),
            model_spec_version=str(base["model_spec_version"]),
            subject_type=str(base["subject_type"]),
            subject_id=str(base["subject_id"]),
            capability_type=str(base["capability_type"]),
            training_dataset_snapshot_id=str(base["training_dataset_snapshot_id"]),
            validation_dataset_snapshot_id=str(
                revision["validation_dataset_snapshot_id"]
            ),
            plugin_name=str(base["plugin_name"]),
            plugin_version=str(base["plugin_version"]),
            model_artifact_uri=str(base["model_artifact_uri"]),
            model_artifact_hash=str(base["model_artifact_hash"]),
            model_object_ref_id=str(object_row["object_ref_id"]),
            validity_domain=_mapping(base["validity_domain"], "capability_model.validity_domain"),
            validation_metrics=_mapping(
                base["validation_metrics"],
                "capability_model.validation_metrics",
            ),
            applicability_profile_ref=str(revision["applicability_profile_ref"]),
            uncertainty_profile_ref=str(revision["uncertainty_profile_ref"]),
            status=str(base["status"]),
            trained_at=_time_text(base["trained_at"]),
            published_at=(
                None if base["published_at"] is None else _time_text(base["published_at"])
            ),
            supersedes_model_id=(
                None if base["supersedes_model_id"] is None else str(base["supersedes_model_id"])
            ),
        )
        if (
            str(object_row["artifact_sha256"]) != value.model_artifact_hash
            or not _bool(object_row["sealed"], "object_reference.sealed")
            or str(object_row["gc_state"]) != "ACTIVE"
            or object_row["deleted_at"] is not None
        ):
            raise P6PersistenceError("P6_MODEL_OBJECT_INVALID", model_id)
        self.exact_model_dataset(value.training_dataset_snapshot_id)
        self.exact_model_dataset(value.validation_dataset_snapshot_id)
        return value

    def exact_model_revision(self, model_id: str) -> P6ModelRevision:
        value = self._try_model(model_id)
        if value is None:
            raise P6PersistenceError("M9_MODEL_NOT_FOUND", model_id)
        return value

    def exact_managed_object(self, model_id: str) -> P6ManagedModelObject:
        model = self.exact_model_revision(model_id)
        row = self._rows.one(
            "registry.object_reference",
            where={"object_ref_id": model.model_object_ref_id},
            columns=(
                "object_ref_id",
                "managed_uri",
                "artifact_sha256",
                "sealed",
                "gc_state",
                "deleted_at",
                "created_at",
            ),
        )
        if row is None:
            raise P6PersistenceError("M9_MODEL_OBJECT_NOT_FOUND", model_id)
        value = P6ManagedModelObject(
            object_ref_id=str(row["object_ref_id"]),
            managed_uri=str(row["managed_uri"]),
            artifact_sha256=str(row["artifact_sha256"]),
            sealed=_bool(row["sealed"], "object_reference.sealed"),
            gc_state=str(row["gc_state"]),
            deleted_at=(
                None if row["deleted_at"] is None else _time_text(row["deleted_at"])
            ),
            sealed_at_utc=_time_text(row["created_at"]),
        )
        validate_p6_managed_model_object(model, value)
        return value

    def exact_model_build(self, object_id: str) -> P6ModelBuild:
        model = self.exact_model_revision(object_id)
        if self._object_store is None or self._model_build_resolver is None:
            raise P6PersistenceError(
                "P6_MODEL_BUILD_DEPENDENCY_BLOCKED",
                object_id,
            )
        artifact_bytes = self._object_store.read_bytes(model.model_artifact_uri)
        if hashlib.sha256(artifact_bytes).hexdigest() != model.model_artifact_hash:
            raise P6PersistenceError("P6_MODEL_HASH_MISMATCH", object_id)
        artifact = _mapping(artifact_bytes.decode("ascii"), "model_artifact")
        build = self._model_build_resolver.rebuild(
            model=model,
            artifact=artifact,
            artifact_bytes=artifact_bytes,
            training=self.exact_model_dataset(model.training_dataset_snapshot_id),
            validation=self.exact_model_dataset(model.validation_dataset_snapshot_id),
        )
        if build.model != model or build.artifact_bytes != artifact_bytes:
            raise P6PersistenceError(
                "P6_MODEL_BUILD_RECONSTRUCTION_MISMATCH",
                object_id,
            )
        return build

    def replace_model_release(self, model: P6ModelRevision) -> None:
        current = self.exact_model_revision(model.capability_model_id)
        before = current.projection()
        after = model.projection()
        for key in ("status", "published_at"):
            before.pop(key)
            after.pop(key)
        if before != after:
            raise P6PersistenceError(
                "P6_IMMUTABLE_CONFLICT",
                model.capability_model_id,
            )
        if current.status == model.status and current.published_at == model.published_at:
            return
        self._rows.update_exact(
            "capability.capability_model",
            where={"capability_model_id": model.capability_model_id},
            values={
                "status": model.status,
                "published_at": model.published_at,
            },
        )

    def register_forecast_request(self, value: P6ForecastRequestBinding) -> None:
        current = self._try_forecast_request(value.forecast_request_id)
        if current is not None:
            if current != value:
                raise P6PersistenceError(
                    "P6_IMMUTABLE_CONFLICT",
                    value.forecast_request_id,
                )
            return
        if (
            _forecast_request_hash(value) != value.request_hash
            or value.forecast_request_id
            != f"{_FORECAST_REQUEST_PREFIX}{value.request_hash}"
        ):
            raise P6PersistenceError(
                "P6_FORECAST_REQUEST_HASH_MISMATCH",
                value.forecast_request_id,
            )
        input_snapshot = self.exact_input(value.input_snapshot_id)
        model = self.exact_model_revision(value.capability_model_id)
        if (
            input_snapshot.target_scope != value.target_scope
            or input_snapshot.subject_or_composition_ref != value.subject_ref
            or model.training_dataset_snapshot_id != value.training_dataset_snapshot_id
            or model.validation_dataset_snapshot_id != value.validation_dataset_snapshot_id
        ):
            raise P6PersistenceError(
                "P6_FORECAST_REQUEST_BINDING_MISMATCH",
                value.forecast_request_id,
            )
        self._rows.insert(
            "intelligence.forecast_request",
            {
                "forecast_request_id": _physical(
                    _FORECAST_REQUEST_NAMESPACE,
                    value.forecast_request_id,
                    _FORECAST_REQUEST_PREFIX,
                ),
                "input_snapshot_id": _physical(
                    _INPUT_NAMESPACE,
                    value.input_snapshot_id,
                    _INPUT_PREFIX,
                ),
                "forecast_spec_id": value.forecast_spec_id,
                "forecast_spec_version": value.forecast_spec_version,
                "target_scope": value.target_scope,
                "subject_ref": value.subject_ref,
                "target_code": value.target_code,
                "forecast_origin_utc": value.forecast_origin_utc,
                "horizon_spec": dict(value.horizon_spec),
                "capability_model_id": value.capability_model_id,
                "model_profile_id": value.model_profile_id,
                "model_profile_version": value.model_profile_version,
                "training_dataset_snapshot_id": value.training_dataset_snapshot_id,
                "validation_dataset_snapshot_id": value.validation_dataset_snapshot_id,
                "assumption_profile_id": value.assumption_profile_id,
                "assumption_profile_version": value.assumption_profile_version,
                "as_of_utc": value.as_of_utc,
                "request_hash": value.request_hash,
            },
            field_kinds={"horizon_spec": "json"},
        )

    def _try_forecast_request(
        self,
        object_id: str,
    ) -> P6ForecastRequestBinding | None:
        row = self._rows.one(
            "intelligence.forecast_request",
            where={
                "forecast_request_id": _physical(
                    _FORECAST_REQUEST_NAMESPACE,
                    object_id,
                    _FORECAST_REQUEST_PREFIX,
                )
            },
            columns=(
                "input_snapshot_id",
                "forecast_spec_id",
                "forecast_spec_version",
                "target_scope",
                "subject_ref",
                "target_code",
                "forecast_origin_utc",
                "horizon_spec",
                "capability_model_id",
                "model_profile_id",
                "model_profile_version",
                "training_dataset_snapshot_id",
                "validation_dataset_snapshot_id",
                "assumption_profile_id",
                "assumption_profile_version",
                "as_of_utc",
                "request_hash",
            ),
        )
        if row is None:
            return None
        request_hash = str(row["request_hash"])
        if object_id != f"{_FORECAST_REQUEST_PREFIX}{request_hash}":
            raise P6PersistenceError("P6_LOGICAL_ID_MISMATCH", object_id)
        input_snapshot = self._input_by_physical(str(row["input_snapshot_id"]))
        value = P6ForecastRequestBinding(
            forecast_request_id=object_id,
            input_snapshot_id=input_snapshot.input_snapshot_id,
            forecast_spec_id=str(row["forecast_spec_id"]),
            forecast_spec_version=str(row["forecast_spec_version"]),
            target_scope=str(row["target_scope"]),
            subject_ref=str(row["subject_ref"]),
            target_code=str(row["target_code"]),
            forecast_origin_utc=_time_text(row["forecast_origin_utc"]),
            horizon_spec=_mapping(row["horizon_spec"], "forecast_request.horizon_spec"),
            capability_model_id=str(row["capability_model_id"]),
            model_profile_id=str(row["model_profile_id"]),
            model_profile_version=str(row["model_profile_version"]),
            training_dataset_snapshot_id=str(row["training_dataset_snapshot_id"]),
            validation_dataset_snapshot_id=str(row["validation_dataset_snapshot_id"]),
            assumption_profile_id=str(row["assumption_profile_id"]),
            assumption_profile_version=str(row["assumption_profile_version"]),
            as_of_utc=_time_text(row["as_of_utc"]),
            request_hash=request_hash,
        )
        if _forecast_request_hash(value) != request_hash:
            raise P6PersistenceError("P6_FORECAST_REQUEST_HASH_MISMATCH", object_id)
        return value

    def exact_forecast_request(self, object_id: str) -> P6ForecastRequestBinding:
        value = self._try_forecast_request(object_id)
        if value is None:
            raise P6PersistenceError("M9_FORECAST_REQUEST_NOT_FOUND", object_id)
        return value

    def register_counterfactual_request(
        self,
        value: P6CounterfactualRequestBinding,
    ) -> None:
        current = self._try_counterfactual_request(value.counterfactual_request_id)
        if current is not None:
            if current != value:
                raise P6PersistenceError(
                    "P6_IMMUTABLE_CONFLICT",
                    value.counterfactual_request_id,
                )
            return
        if (
            _counterfactual_request_hash(value) != value.request_hash
            or value.counterfactual_request_id
            != f"{_COUNTERFACTUAL_REQUEST_PREFIX}{value.request_hash}"
        ):
            raise P6PersistenceError(
                "P6_COUNTERFACTUAL_REQUEST_HASH_MISMATCH",
                value.counterfactual_request_id,
            )
        self.exact_input(value.input_snapshot_id)
        for model_id in value.model_refs:
            self.exact_model_revision(model_id)
        self._rows.insert(
            "intelligence.counterfactual_request",
            {
                "counterfactual_request_id": _physical(
                    _COUNTERFACTUAL_REQUEST_NAMESPACE,
                    value.counterfactual_request_id,
                    _COUNTERFACTUAL_REQUEST_PREFIX,
                ),
                "input_snapshot_id": _physical(
                    _INPUT_NAMESPACE,
                    value.input_snapshot_id,
                    _INPUT_PREFIX,
                ),
                "base_product_refs": value.base_product_refs,
                "scenario_definition_id": value.scenario_definition_id,
                "interventions": dict(value.interventions),
                "held_fixed_assumptions": dict(value.held_fixed_assumptions),
                "model_refs": value.model_refs,
                "applicability_profile_ref": value.applicability_profile_ref,
                "as_of_utc": value.as_of_utc,
                "request_hash": value.request_hash,
            },
            field_kinds={
                "base_product_refs": "text_array",
                "interventions": "json",
                "held_fixed_assumptions": "json",
                "model_refs": "text_array",
            },
        )

    def _try_counterfactual_request(
        self,
        object_id: str,
    ) -> P6CounterfactualRequestBinding | None:
        row = self._rows.one(
            "intelligence.counterfactual_request",
            where={
                "counterfactual_request_id": _physical(
                    _COUNTERFACTUAL_REQUEST_NAMESPACE,
                    object_id,
                    _COUNTERFACTUAL_REQUEST_PREFIX,
                )
            },
            columns=(
                "input_snapshot_id",
                "base_product_refs",
                "scenario_definition_id",
                "interventions",
                "held_fixed_assumptions",
                "model_refs",
                "applicability_profile_ref",
                "as_of_utc",
                "request_hash",
            ),
        )
        if row is None:
            return None
        request_hash = str(row["request_hash"])
        if object_id != f"{_COUNTERFACTUAL_REQUEST_PREFIX}{request_hash}":
            raise P6PersistenceError("P6_LOGICAL_ID_MISMATCH", object_id)
        input_snapshot = self._input_by_physical(str(row["input_snapshot_id"]))
        value = P6CounterfactualRequestBinding(
            counterfactual_request_id=object_id,
            input_snapshot_id=input_snapshot.input_snapshot_id,
            base_product_refs=_strings(
                row["base_product_refs"],
                "counterfactual_request.base_product_refs",
            ),
            scenario_definition_id=str(row["scenario_definition_id"]),
            interventions=_mapping(
                row["interventions"],
                "counterfactual_request.interventions",
            ),
            held_fixed_assumptions=_mapping(
                row["held_fixed_assumptions"],
                "counterfactual_request.held_fixed_assumptions",
            ),
            model_refs=_strings(
                row["model_refs"],
                "counterfactual_request.model_refs",
            ),
            applicability_profile_ref=str(row["applicability_profile_ref"]),
            as_of_utc=_time_text(row["as_of_utc"]),
            request_hash=request_hash,
        )
        if _counterfactual_request_hash(value) != request_hash:
            raise P6PersistenceError(
                "P6_COUNTERFACTUAL_REQUEST_HASH_MISMATCH",
                object_id,
            )
        return value

    def exact_counterfactual_request(
        self,
        object_id: str,
    ) -> P6CounterfactualRequestBinding:
        value = self._try_counterfactual_request(object_id)
        if value is None:
            raise P6PersistenceError(
                "M9_COUNTERFACTUAL_REQUEST_NOT_FOUND",
                object_id,
            )
        return value

    def _input_by_physical(self, physical_id: str) -> P6InputSnapshot:
        row = self._rows.one(
            "registry.dataset_snapshot",
            where={"dataset_snapshot_id": physical_id},
            columns=(
                "dataset_snapshot_id",
                "snapshot_type",
                "query_or_manifest",
                "input_refs",
                "data_hash",
                "schema_version",
                "frozen",
            ),
        )
        if row is None:
            raise P6PersistenceError("M9_INPUT_NOT_FOUND", physical_id)
        return self._input_from_row(row)
