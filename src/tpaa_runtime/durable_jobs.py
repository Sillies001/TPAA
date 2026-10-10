"""PRCB C2 durable formal Job API and governed production worker orchestration."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID

from tpaa_application import (
    DurableJobControl,
    DurableJobControlError,
    DurableP6ModelBuildResolver,
    IdempotencyConflict,
    JobNotFound,
    JobRecord,
    JobStatus,
    JobSubmission,
    P2PersistenceRepository,
    P2ReleaseRepository,
    P3PersistenceRepository,
    P4P5ComputeInputRepository,
    P4P5PersistenceRepository,
    P6PersistenceError,
    P6PersistenceRepository,
    ProductionImportService,
    SourceImportCommand,
    SourceProvenanceRepository,
    allocate_p2_release_id,
    p2_release_scope_key,
)
from tpaa_assessment import P2AttributionExecution
from tpaa_capability.p3_twin import P3CapabilityEstimate
from tpaa_capability.p6_counterfactual import P6CounterfactualRevision
from tpaa_capability.p6_forecast import P6ForecastRevision
from tpaa_ingest import (
    ProductionFlightJsonAdapter,
    ProductionInterchangeJsonAdapter,
    ProductionSourceAdapterError,
    SourceAdapter,
    SourceFamily,
    build_production_source_registry,
    validate_production_flight_document,
    validate_production_interchange_document,
)
from tpaa_platform import SpawnWorkerDispatcher, WorkerPayload
from tpaa_storage import (
    AuditLogWrite,
    ComputeJobRepository,
    ComputeJobState,
    LocalObjectStore,
    ParquetColumn,
    ParquetDatasetArtifact,
    ParquetPartition,
    ParquetScalarType,
    ParquetSchema,
    ParquetWriteRequest,
    PolarsParquetPlane,
)
from tpaa_storage.product_identity import product_object_ref_id

from .durable_repositories import RuntimeCanonicalUnitOfWork, RuntimeUnitOfWorkFactory
from .production_downstream import (
    persist_p3_worker_product,
    persist_p4_worker_product,
    persist_p5_worker_product,
    persist_p6_worker_product,
    prepare_p2_compute_input,
    prepare_p3_build_worker_input,
    prepare_p4_build_worker_input,
    prepare_p5_build_worker_input,
    prepare_p6_build_worker_input,
)
from .production_job_output import ProductionJobOutputRepository
from .production_worker import (
    P2_ATTRIBUTION_COMMAND,
    P3_BUILD_COMMAND,
    P3_ESTIMATE_COMMAND,
    P4_ASSESSMENT_COMMAND,
    P5_ASSESSMENT_COMMAND,
    P6_BUILD_COMMAND,
    P6_COUNTERFACTUAL_COMMAND,
    P6_FORECAST_COMMAND,
    ProductionP1WorkerProduct,
    ProductionP2AttributionWorkerInput,
    ProductionP3BuildWorkerProduct,
    ProductionP3EstimateWorkerInput,
    ProductionP4AssessmentWorkerInput,
    ProductionP4AssessmentWorkerProduct,
    ProductionP4BuildWorkerInput,
    ProductionP5AssessmentWorkerInput,
    ProductionP5AssessmentWorkerProduct,
    ProductionP5BuildWorkerInput,
    ProductionP6BuildWorkerProduct,
    ProductionP6CounterfactualWorkerInput,
    ProductionP6ForecastWorkerInput,
    ProductionPrerequisiteRow,
)

_GOVERNED_HANDLER = "tpaa_runtime.production_worker:execute"
_P1_COMMAND = "BUILD_P1_RELEASE"
_P1_CANONICAL_DATASET_PRODUCER_VERSION = "ED2-B1-P1-CANONICAL-1.0.0"


class ProductionJobExecutionError(RuntimeError):
    """Fail-closed production job execution error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


class DurableJobExecutor(Protocol):
    def execute(
        self,
        *,
        job_id: str,
        request_hash: str,
        job_key: str,
        command: str,
        payload: Mapping[str, object],
    ) -> None: ...

    def cancel(self, job_id: str) -> None: ...


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ProductionJobExecutionError("PRCB_C2_JOB_PAYLOAD_INVALID", field)
    return cast(dict[str, object], value)


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductionJobExecutionError("PRCB_C2_JOB_PAYLOAD_INVALID", field)
    return value


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProductionJobExecutionError("PRCB_C2_JOB_PAYLOAD_INVALID", field)
    return value


def _number(value: object, *, field: str) -> float:
    if isinstance(value, bool):
        raise ProductionJobExecutionError("PRCB_C2_JOB_PAYLOAD_INVALID", field)
    if isinstance(value, str):
        if not value or value.strip() != value:
            raise ProductionJobExecutionError("PRCB_C2_JOB_PAYLOAD_INVALID", field)
        try:
            decimal = Decimal(value)
        except InvalidOperation as exc:
            raise ProductionJobExecutionError(
                "PRCB_C2_JOB_PAYLOAD_INVALID",
                field,
            ) from exc
        if not decimal.is_finite():
            raise ProductionJobExecutionError("PRCB_C2_JOB_PAYLOAD_INVALID", field)
        return float(decimal)
    if isinstance(value, (int, float)):
        return float(value)
    raise ProductionJobExecutionError("PRCB_C2_JOB_PAYLOAD_INVALID", field)


_P6_RECONSTRUCTION_SAFE_DETAILS = frozenset(
    {
        "dataset_snapshot_contract",
        "artifact_canonical_json",
        "artifact_bytes",
        "model_metadata",
        "applicability_evidence",
        "fit_row_ids",
        "fit_row_membership",
        "uncertainty_calibration",
        "intercept",
        "slope",
        "session_order_origin",
        "target_session_order",
    }
)
_P6_RECONSTRUCTION_SAFE_PREFIXES = frozenset(
    {
        "p3_component_model",
        "p3_segment_binding",
        "p3_session_order_scope",
        "session_order_assignment",
        "training_session",
        "session_order",
        "dataset_membership",
        "artifact_binding",
    }
)


_PREREQUISITE_IDENTITY_COLUMNS: dict[str, str] = {
    "registry.training_session": "session_id",
    "registry.dataset_snapshot": "dataset_snapshot_id",
    "registry.object_reference": "object_ref_id",
    "registry.dataset_manifest": "dataset_id",
    "master.aircraft_model": "aircraft_model_id",
    "master.aircraft": "aircraft_id",
    "master.entity": "entity_id",
    "master.aircraft_instance": "aircraft_instance_id",
    "context.evaluation_context": "context_id",
    "episode.training_episode": "episode_id",
    "episode.episode_stage": "stage_id",
    "master.mission_system_instance": "mission_system_instance_id",
    "metric.metric_definition": "metric_definition_id",
}


def _governed_job_failure_detail(exc: Exception) -> str:
    """Expose only governed table/field names for prerequisite drift diagnostics."""

    error_kind = type(exc).__name__
    if (
        isinstance(exc, ProductionJobExecutionError)
        and exc.code == "ED2_P1_PREREQUISITE_IDENTITY_DRIFT"
    ):
        table, _, remainder = exc.detail.partition(":")
        _, separator, fields = remainder.rpartition(":fields=")
        if (
            table in _PREREQUISITE_IDENTITY_COLUMNS
            and separator
            and fields
            and all(part.isidentifier() for part in fields.split(","))
        ):
            return f"{error_kind}:{table}:fields={fields}"
    if (
        isinstance(exc, P6PersistenceError)
        and exc.code == "P6_MODEL_BUILD_RECONSTRUCTION_MISMATCH"
    ):
        detail = exc.detail
        category, separator, _remainder = detail.partition(":")
        if detail in _P6_RECONSTRUCTION_SAFE_DETAILS:
            return f"{error_kind}:{detail}"
        if separator and category in _P6_RECONSTRUCTION_SAFE_PREFIXES:
            return f"{error_kind}:{category}"
    return error_kind


def _logical_prerequisite_value(
    value: object,
    *,
    field_kind: str,
) -> object:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if field_kind in {"json", "text_array", "uuid_array"}:
        parsed = value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ProductionJobExecutionError(
                    "ED2_P1_PREREQUISITE_STORED_VALUE_INVALID",
                    field_kind,
                ) from exc
        if field_kind in {"text_array", "uuid_array"}:
            if isinstance(parsed, tuple):
                return list(parsed)
            if not isinstance(parsed, list):
                raise ProductionJobExecutionError(
                    "ED2_P1_PREREQUISITE_STORED_VALUE_INVALID",
                    field_kind,
                )
        return parsed
    return value


def _persist_or_verify_prerequisite(
    uow: RuntimeCanonicalUnitOfWork,
    prerequisite: ProductionPrerequisiteRow,
) -> None:
    identity_column = _PREREQUISITE_IDENTITY_COLUMNS.get(prerequisite.table)
    if identity_column is None:
        raise ProductionJobExecutionError(
            "ED2_P1_PREREQUISITE_TABLE_UNSUPPORTED",
            prerequisite.table,
        )
    if identity_column not in prerequisite.values:
        raise ProductionJobExecutionError(
            "ED2_P1_PREREQUISITE_IDENTITY_MISSING",
            f"{prerequisite.table}:{identity_column}",
        )
    identity = prerequisite.values[identity_column]
    columns = tuple(prerequisite.values)
    existing = uow.canonical_rows.one(
        prerequisite.table,
        where={identity_column: identity},
        columns=columns,
    )
    if existing is None:
        uow.canonical_rows.insert(
            prerequisite.table,
            prerequisite.values,
            field_kinds=prerequisite.field_kinds,
        )
        return

    mismatched: list[str] = []
    for column, expected in prerequisite.values.items():
        kind = prerequisite.field_kinds.get(column, "scalar")
        actual_logical = _logical_prerequisite_value(
            existing[column],
            field_kind=kind,
        )
        expected_logical = _logical_prerequisite_value(
            expected,
            field_kind=kind,
        )
        if actual_logical != expected_logical:
            mismatched.append(column)
    if mismatched:
        raise ProductionJobExecutionError(
            "ED2_P1_PREREQUISITE_IDENTITY_DRIFT",
            (
                f"{prerequisite.table}:{identity_column}={identity}:"
                f"fields={','.join(sorted(mismatched))}"
            ),
        )


def _canonical_dataset_prerequisites(
    product: ProductionP1WorkerProduct,
    artifact: ParquetDatasetArtifact,
    *,
    request_hash: str,
) -> tuple[ProductionPrerequisiteRow, ProductionPrerequisiteRow]:
    """Bind the sealed canonical Parquet object to DB 1.9 dataset authority."""

    if (
        artifact.schema.schema_id != "CANONICAL_AIRCRAFT_STATE_V1"
        or artifact.schema.schema_version != "1.0.0"
        or artifact.row_count != len(product.canonical_rows)
        or artifact.min_session_time_us is None
        or artifact.max_session_time_us is None
        or artifact.min_session_time_us >= artifact.max_session_time_us
    ):
        raise ProductionJobExecutionError(
            "ED2_P1_CANONICAL_DATASET_ARTIFACT_INVALID",
            artifact.logical_uri,
        )

    object_ref_id = product_object_ref_id(
        artifact.logical_uri,
        artifact.artifact_sha256,
    )
    object_reference = ProductionPrerequisiteRow(
        table="registry.object_reference",
        values={
            "object_ref_id": object_ref_id,
            "managed_uri": artifact.logical_uri,
            "media_type": "application/vnd.apache.parquet",
            "size_bytes": artifact.byte_size,
            "artifact_sha256": artifact.artifact_sha256,
            "logical_content_hash": artifact.logical_content_hash,
            "storage_backend": "LOCAL_OBJECT_STORE",
            "sealed": True,
            "gc_state": "ACTIVE",
            "gc_state_version": 0,
            "gc_marked_at": None,
            "deleted_at": None,
        },
        field_kinds={},
    )
    dataset_manifest = ProductionPrerequisiteRow(
        table="registry.dataset_manifest",
        values={
            "dataset_id": product.dataset_id,
            # The manifest must precede Release publication because World has an
            # immediate dataset FK. Release ownership is therefore intentionally
            # nullable here; immutable request/world lineage binds the dataset.
            "release_id": None,
            "scope_type": "SESSION",
            "session_id": product.release.session_id,
            "longitudinal_scope_id": None,
            "dataset_kind": "CANONICAL_FLIGHT",
            "logical_name": f"production/canonical-flight/{product.dataset_id}",
            "object_ref_id": object_ref_id,
            "storage_uri": artifact.logical_uri,
            "partition_spec": [
                {"key": key, "value": value}
                for key, value in artifact.partition.values
            ],
            "schema_version": artifact.schema.schema_version,
            "row_count": artifact.row_count,
            "min_session_time_us": artifact.min_session_time_us,
            "max_session_time_us": artifact.max_session_time_us,
            "artifact_sha256": artifact.artifact_sha256,
            "logical_content_hash": artifact.logical_content_hash,
            "producer_component": "tpaa_runtime.production_p1",
            "producer_version": _P1_CANONICAL_DATASET_PRODUCER_VERSION,
            "input_hash": request_hash,
            "status": "READY",
            "supersedes_dataset_id": None,
        },
        field_kinds={"partition_spec": "json"},
    )
    return object_reference, dataset_manifest


def _audit_actor_id(actor: str) -> str | None:
    try:
        parsed = UUID(actor)
    except ValueError:
        return None
    return actor if str(parsed) == actor else None


def _record_job_audit(
    uow: RuntimeCanonicalUnitOfWork,
    *,
    actor: str,
    action: str,
    job_id: str,
    request_id: str | None,
    reason: str | None,
    status: str,
) -> None:
    principal_key = actor.strip()
    if not principal_key:
        raise ProductionJobExecutionError(
            "PRCB_C3_PRINCIPAL_KEY_REQUIRED",
            action,
        )
    uow.audit_log.append(
        AuditLogWrite(
            actor_id=_audit_actor_id(principal_key),
            principal_key=principal_key,
            action=action,
            object_type="COMPUTE_JOB",
            object_id=job_id,
            outcome="ALLOW",
            request_id=request_id,
            reason=reason,
            details={"status": status},
        )
    )


def _job_record(record: object) -> JobRecord:
    from tpaa_storage.compute_job import ComputeJobRecord

    if not isinstance(record, ComputeJobRecord):
        raise TypeError("expected ComputeJobRecord")
    cancellation_reason = (
        record.reason_codes[-1]
        if record.status is ComputeJobState.CANCELLED and record.reason_codes
        else None
    )
    return JobRecord(
        job_id=record.job_id,
        idempotency_key=record.job_key,
        request_hash=record.input_hash,
        command=record.job_type,
        status=JobStatus(record.status.value),
        cancellation_reason=cancellation_reason,
    )


def _parquet_schema() -> ParquetSchema:
    return ParquetSchema(
        schema_id="CANONICAL_AIRCRAFT_STATE_V1",
        schema_version="1.0.0",
        columns=(
            ParquetColumn("source_stream_ordinal", ParquetScalarType.INT64),
            ParquetColumn("session_time_us", ParquetScalarType.INT64),
            ParquetColumn("body_p_rad_s", ParquetScalarType.FLOAT64, nullable=True),
            ParquetColumn("nz_g", ParquetScalarType.FLOAT64, nullable=True),
            ParquetColumn("heading_true_rad", ParquetScalarType.FLOAT64, nullable=True),
            ParquetColumn("tas_mps", ParquetScalarType.FLOAT64, nullable=True),
            ParquetColumn("mach", ParquetScalarType.FLOAT64, nullable=True),
            ParquetColumn("quality_mask", ParquetScalarType.INT64),
        ),
    )


class ProductionJobExecutor:
    """Parent infrastructure; domain computation is wholly decided by the worker."""

    def __init__(
        self,
        *,
        authority_root: Path,
        write_uow_factory: RuntimeUnitOfWorkFactory,
        object_store: LocalObjectStore,
        max_workers: int = 2,
    ) -> None:
        self._authority_root = authority_root
        self._write_uow_factory = write_uow_factory
        self._object_store = object_store
        self._dispatcher = SpawnWorkerDispatcher(max_workers=max_workers)
        self._adapters = build_production_source_registry()

    def cancel(self, job_id: str) -> None:
        self._dispatcher.cancel(job_id)

    @staticmethod
    def _source_import(payload: Mapping[str, object]) -> SourceImportCommand:
        source_json = _text(payload.get("source_json"), field="source_json")
        source_bytes = source_json.encode("utf-8")
        metadata = _mapping(payload.get("source_import"), field="source_import")
        family_text = _text(metadata.get("source_family"), field="source_family")
        try:
            family = SourceFamily(family_text)
        except ValueError as exc:
            raise ProductionJobExecutionError(
                "UNSUPPORTED_ADAPTER",
                family_text,
            ) from exc

        adapter: SourceAdapter
        if family is SourceFamily.FLIGHT:
            document = validate_production_flight_document(source_bytes)
            adapter = ProductionFlightJsonAdapter()
            document_session_id = document.get("session_id")
        else:
            adapter = ProductionInterchangeJsonAdapter(family)
            interchange = validate_production_interchange_document(
                source_bytes,
                expected_family=family,
            )
            document_session_id = interchange.session_id

        session_id = _text(metadata.get("session_id"), field="session_id")
        if document_session_id != session_id:
            raise ProductionJobExecutionError(
                "PRCB_C2_SOURCE_SESSION_DRIFT",
                session_id,
            )
        envelope = adapter.inspect(
            source_ref=_text(metadata.get("source_ref"), field="source_ref"),
            data=source_bytes,
            media_type=_text(metadata.get("media_type"), field="media_type"),
            classification_label=(
                None
                if metadata.get("classification_label") is None
                else _text(
                    metadata.get("classification_label"),
                    field="classification_label",
                )
            ),
        )
        descriptor = adapter.descriptor
        if (
            envelope.adapter_id != descriptor.adapter_id
            or envelope.adapter_version != descriptor.adapter_version
            or envelope.media_type not in descriptor.media_types
            or envelope.source_family is not family
        ):
            raise ProductionJobExecutionError(
                "PRCB_C2_ADAPTER_IDENTITY_DRIFT",
                envelope.adapter_id,
            )
        return SourceImportCommand(
            source_id=_text(metadata.get("source_id"), field="source_id"),
            session_id=session_id,
            platform_id=(
                None
                if metadata.get("platform_id") is None
                else _text(metadata.get("platform_id"), field="platform_id")
            ),
            producer_system=_text(
                metadata.get("producer_system"),
                field="producer_system",
            ),
            schema_name=_text(metadata.get("schema_name"), field="schema_name"),
            schema_version=_text(
                metadata.get("schema_version"),
                field="schema_version",
            ),
            time_basis=_text(metadata.get("time_basis"), field="time_basis"),
            nominal_rate_hz=(
                None
                if metadata.get("nominal_rate_hz") is None
                else _number(
                    metadata.get("nominal_rate_hz"),
                    field="nominal_rate_hz",
                )
            ),
            source_quality=_number(
                metadata.get("source_quality"),
                field="source_quality",
            ),
            source_stream_id=_text(
                metadata.get("source_stream_id"),
                field="source_stream_id",
            ),
            stream_code=_text(metadata.get("stream_code"), field="stream_code"),
            ordinal_basis=_text(
                metadata.get("ordinal_basis"),
                field="ordinal_basis",
            ),
            stream_status=_text(
                metadata.get("stream_status"),
                field="stream_status",
            ),
            artifact_id=_text(metadata.get("artifact_id"), field="artifact_id"),
            source_artifact_sequence=_integer(
                metadata.get("source_artifact_sequence"),
                field="source_artifact_sequence",
            ),
            uri_kind=_text(metadata.get("uri_kind"), field="uri_kind"),
            availability_status=_text(
                metadata.get("availability_status"),
                field="availability_status",
            ),
            last_verified_at=(
                None
                if metadata.get("last_verified_at") is None
                else _text(
                    metadata.get("last_verified_at"),
                    field="last_verified_at",
                )
            ),
            mtime_source=(
                None
                if metadata.get("mtime_source") is None
                else _text(metadata.get("mtime_source"), field="mtime_source")
            ),
            envelope=envelope,
        )

    @staticmethod
    def _source_imports(
        payload: Mapping[str, object],
    ) -> tuple[SourceImportCommand, ...]:
        raw_documents = payload.get("source_documents")
        if raw_documents is None:
            return (ProductionJobExecutor._source_import(payload),)
        if (
            not isinstance(raw_documents, Sequence)
            or isinstance(raw_documents, (str, bytes))
            or not raw_documents
        ):
            raise ProductionJobExecutionError(
                "ED2_SOURCE_SET_INVALID",
                "source_documents",
            )

        commands: list[SourceImportCommand] = []
        source_ids: set[str] = set()
        artifact_ids: set[str] = set()
        session_id: str | None = None
        for index, raw in enumerate(raw_documents):
            document = _mapping(
                raw,
                field=f"source_documents[{index}]",
            )
            command = ProductionJobExecutor._source_import(document)
            if session_id is None:
                session_id = command.session_id
            elif command.session_id != session_id:
                raise ProductionJobExecutionError(
                    "ED2_SOURCE_SET_SESSION_DRIFT",
                    command.session_id,
                )
            if command.source_id in source_ids:
                raise ProductionJobExecutionError(
                    "ED2_SOURCE_SET_IDENTITY_DUPLICATE",
                    command.source_id,
                )
            if command.artifact_id in artifact_ids:
                raise ProductionJobExecutionError(
                    "ED2_SOURCE_SET_IDENTITY_DUPLICATE",
                    command.artifact_id,
                )
            source_ids.add(command.source_id)
            artifact_ids.add(command.artifact_id)
            commands.append(command)
        return tuple(commands)


    @staticmethod
    def _bind_parquet(
        product: ProductionP1WorkerProduct,
        *,
        logical_uri: str,
        logical_content_hash: str,
    ) -> ProductionP1WorkerProduct:
        evidence = tuple(
            replace(
                item,
                series_locator={
                    **item.series_locator,
                    "canonical_dataset_uri": logical_uri,
                    "canonical_logical_content_hash": logical_content_hash,
                    "canonical_dataset_id": product.dataset_id,
                },
            )
            for item in product.release.evidence_sets
        )
        return replace(
            product,
            release=replace(product.release, evidence_sets=evidence),
        )

    def _execute_p1(
        self,
        *,
        job_id: str,
        request_hash: str,
        job_key: str,
        command: str,
        payload: Mapping[str, object],
    ) -> None:
        if command != _P1_COMMAND:
            raise ProductionJobExecutionError(
                "PRCB_C2_DOMAIN_COMMAND_UNSUPPORTED",
                command,
            )
        source_commands = self._source_imports(payload)
        for source_command in source_commands:
            try:
                self._adapters.require_family(
                    source_command.envelope.source_family
                )
            except ProductionSourceAdapterError as exc:
                raise ProductionJobExecutionError(exc.code, exc.detail) from exc

        result = self._dispatcher.dispatch(
            WorkerPayload(
                job_id=job_id,
                request_hash=request_hash,
                command=command,
                handler=_GOVERNED_HANDLER,
                domain_payload={
                    "authority_root": str(self._authority_root),
                    "job_payload": dict(payload),
                },
            ),
            timeout_seconds=120.0,
        )
        if result.status != "SUCCEEDED":
            raise ProductionJobExecutionError(
                result.error_code or "PRCB_C2_WORKER_FAILED",
                job_id,
            )
        product = result.domain_payload
        if not isinstance(product, ProductionP1WorkerProduct):
            raise ProductionJobExecutionError(
                "PRCB_C2_WORKER_PRODUCT_INVALID",
                type(product).__name__,
            )

        parquet = PolarsParquetPlane(self._object_store)
        artifact = parquet.write(
            ParquetWriteRequest(
                operation_id=job_id,
                namespace="production",
                dataset_kind="canonical-flight",
                dataset_id=product.dataset_id,
                schema=_parquet_schema(),
                partition=ParquetPartition(),
                rows=product.canonical_rows,
            )
        )
        if parquet.scan_rows(artifact) != product.canonical_rows:
            raise ProductionJobExecutionError(
                "PRCB_C2_PARQUET_RESTART_SCAN_DRIFT",
                artifact.logical_uri,
            )
        product = self._bind_parquet(
            product,
            logical_uri=artifact.logical_uri,
            logical_content_hash=artifact.logical_content_hash,
        )
        canonical_dataset_prerequisites = _canonical_dataset_prerequisites(
            product,
            artifact,
            request_hash=request_hash,
        )

        expected_version = _integer(
            payload.get("expected_version_token"),
            field="expected_version_token",
        )
        if expected_version != 0:
            raise ProductionJobExecutionError(
                "PRCB_C2_RELEASE_REVISION_NOT_CONFIGURED",
                str(expected_version),
            )
        with self._write_uow_factory() as uow:
            for prerequisite in product.prerequisites:
                _persist_or_verify_prerequisite(uow, prerequisite)
            for prerequisite in canonical_dataset_prerequisites:
                _persist_or_verify_prerequisite(uow, prerequisite)
            import_service = ProductionImportService(
                adapters=self._adapters,
                provenance=SourceProvenanceRepository(uow.canonical_rows),
            )
            for source_command in source_commands:
                import_service.register(source_command)
            uow.publication.publish(
                product.release,
                idempotency_key=f"{job_key}:P1_RELEASE",
                expected_version_token=expected_version,
            )
            DurableJobControl(
                ComputeJobRepository(uow.canonical_rows)
            ).succeed(job_id)
            uow.commit()


    def _p2_repository(
        self,
        uow: RuntimeCanonicalUnitOfWork,
    ) -> P2PersistenceRepository:
        return P2PersistenceRepository(
            uow.canonical_rows,
            object_store=self._object_store,
        )

    @staticmethod
    def _p2_manifest_hash(
        *,
        job_id: str,
        request_hash: str,
        dataset_snapshot_id: str,
        release_id: str,
        value: P2AttributionExecution,
    ) -> str:
        payload = {
            "schema": "TPAA_PRCB_C2_P2_RELEASE_MANIFEST_V1",
            "job_id": job_id,
            "request_hash": request_hash,
            "dataset_snapshot_id": dataset_snapshot_id,
            "release_id": release_id,
            "attribution_run_id": value.attribution_run.attribution_run_id,
            "run_request_hash": value.attribution_run.run_request_hash,
            "model_artifact_hash": value.attribution_run.model_artifact_hash,
            "estimate_id": value.adjusted_estimate.estimate_id,
            "estimate_logical_hash": value.adjusted_estimate.logical_hash,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        return hashlib.sha256(encoded).hexdigest()

    def _execute_p2_attribution(
        self,
        *,
        job_id: str,
        request_hash: str,
        payload: Mapping[str, object],
    ) -> None:
        production_raw = payload.get("production_input")
        production_input = (
            None
            if production_raw is None
            else _mapping(production_raw, field="production_input")
        )
        if production_input is None:
            dataset_snapshot_id = _text(
                payload.get("dataset_snapshot_id"),
                field="dataset_snapshot_id",
            )
        else:
            with self._write_uow_factory() as uow:
                prepared = prepare_p2_compute_input(
                    uow.canonical_rows,
                    self._object_store,
                    production_input,
                )
                dataset_snapshot_id = prepared.dataset_snapshot_id
                explicit = payload.get("dataset_snapshot_id")
                if (
                    explicit is not None
                    and _text(explicit, field="dataset_snapshot_id")
                    != dataset_snapshot_id
                ):
                    raise ProductionJobExecutionError(
                        "ED2_B2_P2_DATASET_ID_DRIFT",
                        dataset_snapshot_id,
                    )
                compute_input = self._p2_repository(
                    uow
                ).exact_compute_input(dataset_snapshot_id)
                lineage = P2ReleaseRepository(
                    uow.canonical_rows
                ).source_lineage(
                    compute_input.input_bundle.target.release_id
                )
                # No commit: preparation is replayed atomically after worker success.

        execution_time_utc = _text(
            payload.get("execution_time_utc"),
            field="execution_time_utc",
        )
        expected_version_token = _integer(
            payload.get("expected_version_token"),
            field="expected_version_token",
        )
        if expected_version_token < 0:
            raise ProductionJobExecutionError(
                "PRCB_C2_P2_EXPECTED_VERSION_INVALID",
                str(expected_version_token),
            )
        supersedes_raw = payload.get("supersedes_estimate_id")
        supersedes_estimate_id = (
            None
            if supersedes_raw is None
            else _text(
                supersedes_raw,
                field="supersedes_estimate_id",
            )
        )

        if production_input is None:
            with self._write_uow_factory() as uow:
                repository = self._p2_repository(uow)
                compute_input = repository.exact_compute_input(
                    dataset_snapshot_id
                )
                release_repository = P2ReleaseRepository(
                    uow.canonical_rows
                )
                lineage = release_repository.source_lineage(
                    compute_input.input_bundle.target.release_id
                )
                uow.commit()

        scope_key = p2_release_scope_key(
            compute_input.input_bundle.target.observation_id
        )
        release_id = allocate_p2_release_id(
            job_id=job_id,
            request_hash=request_hash,
            scope_key=scope_key,
        )
        result = self._dispatcher.dispatch(
            WorkerPayload(
                job_id=job_id,
                request_hash=request_hash,
                command=P2_ATTRIBUTION_COMMAND,
                handler=_GOVERNED_HANDLER,
                domain_payload=ProductionP2AttributionWorkerInput(
                    job_payload=dict(payload),
                    compute_input=compute_input,
                    p2_release_id=release_id,
                    execution_time_utc=execution_time_utc,
                    supersedes_estimate_id=supersedes_estimate_id,
                ),
            ),
            timeout_seconds=120.0,
        )
        value = result.domain_payload
        if result.status != "SUCCEEDED" or not isinstance(
            value,
            P2AttributionExecution,
        ):
            raise ProductionJobExecutionError(
                result.error_code or "PRCB_C2_WORKER_FAILED",
                job_id,
            )

        run = value.attribution_run
        if value.model_artifact_json is None:
            if (
                run.model_artifact_uri is not None
                or run.model_artifact_hash is not None
            ):
                raise ProductionJobExecutionError(
                    "PRCB_C2_P2_MODEL_ARTIFACT_DRIFT",
                    run.attribution_run_id,
                )
        else:
            if (
                run.model_artifact_hash is None
                or run.model_artifact_uri is not None
            ):
                raise ProductionJobExecutionError(
                    "PRCB_C2_P2_MODEL_ARTIFACT_DRIFT",
                    run.attribution_run_id,
                )
            artifact_bytes = value.model_artifact_json.encode("ascii")
            logical_uri = (
                "tpaa-object://p2-attribution-model/"
                f"{run.attribution_run_id}.json"
            )
            stored = self._object_store.put_bytes(
                logical_uri,
                artifact_bytes,
            )
            if stored.artifact_sha256 != run.model_artifact_hash:
                raise ProductionJobExecutionError(
                    "PRCB_C2_P2_MODEL_ARTIFACT_HASH_MISMATCH",
                    run.attribution_run_id,
                )
            run = replace(run, model_artifact_uri=logical_uri)
            value = replace(value, attribution_run=run)

        manifest_hash = self._p2_manifest_hash(
            job_id=job_id,
            request_hash=request_hash,
            dataset_snapshot_id=dataset_snapshot_id,
            release_id=release_id,
            value=value,
        )
        with self._write_uow_factory() as uow:
            if production_input is not None:
                replayed = prepare_p2_compute_input(
                    uow.canonical_rows,
                    self._object_store,
                    production_input,
                )
                if replayed.dataset_snapshot_id != dataset_snapshot_id:
                    raise ProductionJobExecutionError(
                        "ED2_B2_P2_PREPARE_REPLAY_DRIFT",
                        dataset_snapshot_id,
                    )
            repository = self._p2_repository(uow)
            repository.register_attribution_run(
                value.attribution_run,
                compute_job_id=job_id,
            )
            P2ReleaseRepository(uow.canonical_rows).publish(
                job_id=job_id,
                release_id=release_id,
                scope_key=scope_key,
                lineage=lineage,
                expected_version_token=expected_version_token,
                manifest_hash=manifest_hash,
                published_at_utc=execution_time_utc,
            )
            repository.register_adjusted_estimate(
                value.adjusted_estimate
            )
            DurableJobControl(
                ComputeJobRepository(uow.canonical_rows)
            ).succeed(job_id)
            uow.commit()

    def _p3_repository(
        self,
        uow: RuntimeCanonicalUnitOfWork,
    ) -> P3PersistenceRepository:
        return P3PersistenceRepository(
            uow.canonical_rows,
            object_store=self._object_store,
        )

    def _execute_p3_build(
        self,
        *,
        job_id: str,
        request_hash: str,
        payload: Mapping[str, object],
    ) -> None:
        production_input = _mapping(
            payload.get("production_input"),
            field="production_input",
        )
        with self._write_uow_factory() as uow:
            worker_input = prepare_p3_build_worker_input(
                uow.canonical_rows,
                self._object_store,
                job_payload=payload,
                production_input=production_input,
            )
            # No commit: authority rows are replayed after worker success.
        result = self._dispatcher.dispatch(
            WorkerPayload(
                job_id=job_id,
                request_hash=request_hash,
                command=P3_BUILD_COMMAND,
                handler=_GOVERNED_HANDLER,
                domain_payload=worker_input,
            ),
            timeout_seconds=120.0,
        )
        product = result.domain_payload
        if result.status != "SUCCEEDED" or not isinstance(
            product,
            ProductionP3BuildWorkerProduct,
        ):
            raise ProductionJobExecutionError(
                result.error_code or "PRCB_C2_WORKER_FAILED",
                job_id,
            )
        with self._write_uow_factory() as uow:
            replayed = prepare_p3_build_worker_input(
                uow.canonical_rows,
                self._object_store,
                job_payload=payload,
                production_input=production_input,
            )
            if replayed != worker_input:
                raise ProductionJobExecutionError(
                    "ED2_B2_P3_PREPARE_REPLAY_DRIFT",
                    job_id,
                )
            persist_p3_worker_product(
                uow.canonical_rows,
                self._object_store,
                product,
            )
            ProductionJobOutputRepository(
                uow.canonical_rows
            ).register(
                job_id=job_id,
                command=P3_BUILD_COMMAND,
                product_refs=(
                    ("capability_model_id", product.model_build.model.capability_model_id),
                    ("twin_revision_id", product.twin.twin_revision_id),
                    *tuple(
                        (
                            f"estimate_{index + 1}",
                            estimate.estimate_id,
                        )
                        for index, estimate in enumerate(product.estimates)
                    ),
                ),
            )
            DurableJobControl(
                ComputeJobRepository(uow.canonical_rows)
            ).succeed(job_id)
            uow.commit()

    def _execute_p3_estimate(
        self,
        *,
        job_id: str,
        request_hash: str,
        payload: Mapping[str, object],
    ) -> None:
        twin_revision_id = _text(
            payload.get("twin_revision_id"),
            field="twin_revision_id",
        )
        capability_type = _text(
            payload.get("capability_type"),
            field="capability_type",
        )
        condition_point = _mapping(
            payload.get("condition_point"),
            field="condition_point",
        )
        as_of_time_utc = _text(
            payload.get("as_of_time_utc"),
            field="as_of_time_utc",
        )
        created_at_utc = _text(
            payload.get("created_at_utc"),
            field="created_at_utc",
        )
        with self._write_uow_factory() as uow:
            repository = self._p3_repository(uow)
            twin = repository.exact_twin_revision(twin_revision_id)
            components = repository.exact_twin_components(twin_revision_id)
            uow.commit()

        result = self._dispatcher.dispatch(
            WorkerPayload(
                job_id=job_id,
                request_hash=request_hash,
                command=P3_ESTIMATE_COMMAND,
                handler=_GOVERNED_HANDLER,
                domain_payload=ProductionP3EstimateWorkerInput(
                    job_payload=dict(payload),
                    twin=twin,
                    components=components,
                    capability_type=capability_type,
                    condition_point=condition_point,
                    as_of_time_utc=as_of_time_utc,
                    created_at_utc=created_at_utc,
                ),
            ),
            timeout_seconds=120.0,
        )
        value = result.domain_payload
        if result.status != "SUCCEEDED" or not isinstance(
            value,
            P3CapabilityEstimate,
        ):
            raise ProductionJobExecutionError(
                result.error_code or "PRCB_C2_WORKER_FAILED",
                job_id,
            )
        with self._write_uow_factory() as uow:
            self._p3_repository(uow).register_estimate(value)
            DurableJobControl(
                ComputeJobRepository(uow.canonical_rows)
            ).succeed(job_id)
            uow.commit()


    def _p4_p5_products(
        self,
        uow: RuntimeCanonicalUnitOfWork,
    ) -> P4P5PersistenceRepository:
        return P4P5PersistenceRepository(uow.canonical_rows)

    def _p4_p5_inputs(
        self,
        uow: RuntimeCanonicalUnitOfWork,
    ) -> P4P5ComputeInputRepository:
        return P4P5ComputeInputRepository(uow.canonical_rows)

    def _execute_p4_assessment(
        self,
        *,
        job_id: str,
        request_hash: str,
        payload: Mapping[str, object],
    ) -> None:
        confidence = _number(
            payload.get("confidence"),
            field="confidence",
        )
        created_at_utc = _text(
            payload.get("created_at_utc"),
            field="created_at_utc",
        )
        production_raw = payload.get("production_input")
        production_input = (
            None
            if production_raw is None
            else _mapping(production_raw, field="production_input")
        )
        worker_input: ProductionP4BuildWorkerInput | ProductionP4AssessmentWorkerInput
        if production_input is not None:
            with self._write_uow_factory() as uow:
                worker_input = prepare_p4_build_worker_input(
                    uow.canonical_rows,
                    self._object_store,
                    authority_root=self._authority_root,
                    job_payload=payload,
                    production_input=production_input,
                    confidence=confidence,
                    created_at_utc=created_at_utc,
                )
                # No commit: context rows are replayed atomically after success.
        else:
            snapshot_id = _text(
                payload.get("scope_snapshot_id"),
                field="scope_snapshot_id",
            )
            with self._write_uow_factory() as uow:
                products = self._p4_p5_products(uow)
                scope = self._p4_p5_inputs(uow).exact_p4_scope(
                    snapshot_id
                )
                if scope.instructor_evidence:
                    raise ProductionJobExecutionError(
                        "PRCB_C2_P4_HUMAN_INPUT_REQUIRES_MUTATION_WORKFLOW",
                        snapshot_id,
                    )
                subject = products.exact_p4_subject(
                    scope.subject_context_id
                )
                p3_estimate_id = subject.p3_estimate_id
                p3_estimate = (
                    None
                    if p3_estimate_id is None
                    else self._p3_repository(
                        uow
                    ).exact_capability_estimate(p3_estimate_id)
                )
                worker_input = ProductionP4AssessmentWorkerInput(
                    job_payload=dict(payload),
                    subject=subject,
                    scope=scope,
                    p3_estimate=p3_estimate,
                    confidence=confidence,
                    created_at_utc=created_at_utc,
                )
                uow.commit()

        result = self._dispatcher.dispatch(
            WorkerPayload(
                job_id=job_id,
                request_hash=request_hash,
                command=P4_ASSESSMENT_COMMAND,
                handler=_GOVERNED_HANDLER,
                domain_payload=worker_input,
            ),
            timeout_seconds=120.0,
        )
        product = result.domain_payload
        if result.status != "SUCCEEDED" or not isinstance(
            product,
            ProductionP4AssessmentWorkerProduct,
        ):
            raise ProductionJobExecutionError(
                result.error_code or "PRCB_C2_WORKER_FAILED",
                job_id,
            )
        value = product.revision
        if value.approval_state != "DRAFT" or value.instructor_annotation_ids:
            raise ProductionJobExecutionError(
                "PRCB_C2_P4_AUTOMATION_AUTHORITY_VIOLATION",
                value.actor_assessment_id,
            )
        with self._write_uow_factory() as uow:
            if production_input is not None:
                replayed = prepare_p4_build_worker_input(
                    uow.canonical_rows,
                    self._object_store,
                    authority_root=self._authority_root,
                    job_payload=payload,
                    production_input=production_input,
                    confidence=confidence,
                    created_at_utc=created_at_utc,
                )
                if replayed != worker_input:
                    raise ProductionJobExecutionError(
                        "ED2_B2_P4_PREPARE_REPLAY_DRIFT",
                        job_id,
                    )
            scope_snapshot_id = persist_p4_worker_product(
                uow.canonical_rows,
                product,
            )
            ProductionJobOutputRepository(
                uow.canonical_rows
            ).register(
                job_id=job_id,
                command=P4_ASSESSMENT_COMMAND,
                product_refs=(
                    (
                        "actor_assessment_id",
                        product.revision.actor_assessment_id,
                    ),
                    ("scope_snapshot_id", scope_snapshot_id),
                    (
                        "subject_context_id",
                        product.subject.subject_context_id,
                    ),
                ),
            )
            DurableJobControl(
                ComputeJobRepository(uow.canonical_rows)
            ).succeed(job_id)
            uow.commit()

    def _execute_p5_assessment(
        self,
        *,
        job_id: str,
        request_hash: str,
        payload: Mapping[str, object],
    ) -> None:
        confidence = _number(
            payload.get("confidence"),
            field="confidence",
        )
        created_at_utc = _text(
            payload.get("created_at_utc"),
            field="created_at_utc",
        )
        production_raw = payload.get("production_input")
        production_input = (
            None
            if production_raw is None
            else _mapping(production_raw, field="production_input")
        )
        worker_input: ProductionP5BuildWorkerInput | ProductionP5AssessmentWorkerInput
        if production_input is not None:
            with self._write_uow_factory() as uow:
                worker_input = prepare_p5_build_worker_input(
                    uow.canonical_rows,
                    job_payload=payload,
                    production_input=production_input,
                    confidence=confidence,
                    created_at_utc=created_at_utc,
                )
                # Read-only preparation; no commit required.
        else:
            snapshot_id = _text(
                payload.get("selection_snapshot_id"),
                field="selection_snapshot_id",
            )
            with self._write_uow_factory() as uow:
                compute_input = self._p4_p5_inputs(
                    uow
                ).exact_p5_selection(snapshot_id)
                worker_input = ProductionP5AssessmentWorkerInput(
                    job_payload=dict(payload),
                    compute_input=compute_input,
                    confidence=confidence,
                    created_at_utc=created_at_utc,
                )
                uow.commit()

        result = self._dispatcher.dispatch(
            WorkerPayload(
                job_id=job_id,
                request_hash=request_hash,
                command=P5_ASSESSMENT_COMMAND,
                handler=_GOVERNED_HANDLER,
                domain_payload=worker_input,
            ),
            timeout_seconds=120.0,
        )
        product = result.domain_payload
        if result.status != "SUCCEEDED" or not isinstance(
            product,
            ProductionP5AssessmentWorkerProduct,
        ):
            raise ProductionJobExecutionError(
                result.error_code or "PRCB_C2_WORKER_FAILED",
                job_id,
            )
        value = product.revision
        if (
            value.approval_state != "DRAFT"
            or value.overall_score is not None
            or value.grade is not None
        ):
            raise ProductionJobExecutionError(
                "PRCB_C2_P5_AUTOMATION_AUTHORITY_VIOLATION",
                value.mission_assessment_id,
            )
        with self._write_uow_factory() as uow:
            if production_input is not None:
                replayed = prepare_p5_build_worker_input(
                    uow.canonical_rows,
                    job_payload=payload,
                    production_input=production_input,
                    confidence=confidence,
                    created_at_utc=created_at_utc,
                )
                if replayed != worker_input:
                    raise ProductionJobExecutionError(
                        "ED2_B2_P5_PREPARE_REPLAY_DRIFT",
                        job_id,
                    )
            selection_snapshot_id = persist_p5_worker_product(
                uow.canonical_rows,
                product,
            )
            ProductionJobOutputRepository(
                uow.canonical_rows
            ).register(
                job_id=job_id,
                command=P5_ASSESSMENT_COMMAND,
                product_refs=(
                    (
                        "mission_assessment_id",
                        product.revision.mission_assessment_id,
                    ),
                    ("composition_id", product.composition.composition_id),
                    ("selection_snapshot_id", selection_snapshot_id),
                ),
            )
            DurableJobControl(
                ComputeJobRepository(uow.canonical_rows)
            ).succeed(job_id)
            uow.commit()

    def _p6_repository(
        self,
        uow: RuntimeCanonicalUnitOfWork,
    ) -> P6PersistenceRepository:
        return P6PersistenceRepository(
            uow.canonical_rows,
            object_store=self._object_store,
            model_build_resolver=DurableP6ModelBuildResolver(uow.canonical_rows),
        )

    def _execute_p6_build(
        self,
        *,
        job_id: str,
        request_hash: str,
        payload: Mapping[str, object],
    ) -> None:
        production_input = _mapping(
            payload.get("production_input"),
            field="production_input",
        )
        with self._write_uow_factory() as uow:
            worker_input = prepare_p6_build_worker_input(
                uow.canonical_rows,
                self._object_store,
                job_payload=payload,
                production_input=production_input,
            )
            # Read-only exact-product projection; no commit required.
        result = self._dispatcher.dispatch(
            WorkerPayload(
                job_id=job_id,
                request_hash=request_hash,
                command=P6_BUILD_COMMAND,
                handler=_GOVERNED_HANDLER,
                domain_payload=worker_input,
            ),
            timeout_seconds=120.0,
        )
        product = result.domain_payload
        if result.status != "SUCCEEDED" or not isinstance(
            product,
            ProductionP6BuildWorkerProduct,
        ):
            raise ProductionJobExecutionError(
                result.error_code or "PRCB_C2_WORKER_FAILED",
                job_id,
            )
        with self._write_uow_factory() as uow:
            replayed = prepare_p6_build_worker_input(
                uow.canonical_rows,
                self._object_store,
                job_payload=payload,
                production_input=production_input,
            )
            if replayed != worker_input:
                raise ProductionJobExecutionError(
                    "ED2_B2_P6_PREPARE_REPLAY_DRIFT",
                    job_id,
                )
            persist_p6_worker_product(
                uow.canonical_rows,
                self._object_store,
                product,
            )
            p6_refs: list[tuple[str, str]] = [
                (
                    "capability_model_id",
                    product.model_build.model.capability_model_id,
                ),
                (
                    "input_snapshot_id",
                    product.input_snapshot.input_snapshot_id,
                ),
            ]
            if product.forecast_request is not None:
                p6_refs.append(
                    (
                        "forecast_request_id",
                        product.forecast_request.forecast_request_id,
                    )
                )
            if product.counterfactual_request is not None:
                p6_refs.append(
                    (
                        "counterfactual_request_id",
                        product.counterfactual_request.counterfactual_request_id,
                    )
                )
            ProductionJobOutputRepository(
                uow.canonical_rows
            ).register(
                job_id=job_id,
                command=P6_BUILD_COMMAND,
                product_refs=tuple(p6_refs),
            )
            DurableJobControl(
                ComputeJobRepository(uow.canonical_rows)
            ).succeed(job_id)
            uow.commit()

    def _execute_p6_forecast(
        self,
        *,
        job_id: str,
        request_hash: str,
        payload: Mapping[str, object],
    ) -> None:
        request_id = _text(
            payload.get("forecast_request_id"),
            field="forecast_request_id",
        )
        published_at = _text(
            payload.get("published_at_utc"),
            field="published_at_utc",
        )
        with self._write_uow_factory() as uow:
            repository = self._p6_repository(uow)
            request = repository.exact_forecast_request(request_id)
            input_snapshot = repository.exact_input(request.input_snapshot_id)
            model_build = repository.exact_model_build(request.capability_model_id)
            managed = repository.exact_managed_object(request.capability_model_id)
            uow.commit()

        result = self._dispatcher.dispatch(
            WorkerPayload(
                job_id=job_id,
                request_hash=request_hash,
                command=P6_FORECAST_COMMAND,
                handler=_GOVERNED_HANDLER,
                domain_payload=ProductionP6ForecastWorkerInput(
                    job_payload=dict(payload),
                    request=request,
                    input_snapshot=input_snapshot,
                    model_build=model_build,
                    managed_object=managed,
                    published_at_utc=published_at,
                ),
            ),
            timeout_seconds=120.0,
        )
        value = result.domain_payload
        if result.status != "SUCCEEDED" or not isinstance(value, P6ForecastRevision):
            raise ProductionJobExecutionError(
                result.error_code or "PRCB_C2_WORKER_FAILED",
                job_id,
            )
        with self._write_uow_factory() as uow:
            self._p6_repository(uow).register_forecast(value)
            ProductionJobOutputRepository(
                uow.canonical_rows
            ).register(
                job_id=job_id,
                command=P6_FORECAST_COMMAND,
                product_refs=(
                    ("forecast_result_id", value.forecast_result_id),
                    ("forecast_run_id", value.forecast_run_id),
                    ("model_revision_id", value.model_revision_id),
                ),
            )
            DurableJobControl(
                ComputeJobRepository(uow.canonical_rows)
            ).succeed(job_id)
            uow.commit()

    def _execute_p6_counterfactual(
        self,
        *,
        job_id: str,
        request_hash: str,
        payload: Mapping[str, object],
    ) -> None:
        request_id = _text(
            payload.get("counterfactual_request_id"),
            field="counterfactual_request_id",
        )
        created_at = _text(
            payload.get("created_at_utc"),
            field="created_at_utc",
        )
        with self._write_uow_factory() as uow:
            repository = self._p6_repository(uow)
            request = repository.exact_counterfactual_request(request_id)
            input_snapshot = repository.exact_input(request.input_snapshot_id)
            models = tuple(
                repository.exact_model_revision(model_id)
                for model_id in request.model_refs
            )
            uow.commit()

        result = self._dispatcher.dispatch(
            WorkerPayload(
                job_id=job_id,
                request_hash=request_hash,
                command=P6_COUNTERFACTUAL_COMMAND,
                handler=_GOVERNED_HANDLER,
                domain_payload=ProductionP6CounterfactualWorkerInput(
                    job_payload=dict(payload),
                    request=request,
                    input_snapshot=input_snapshot,
                    models=models,
                    created_at_utc=created_at,
                ),
            ),
            timeout_seconds=120.0,
        )
        value = result.domain_payload
        if (
            result.status != "SUCCEEDED"
            or not isinstance(value, P6CounterfactualRevision)
        ):
            raise ProductionJobExecutionError(
                result.error_code or "PRCB_C2_WORKER_FAILED",
                job_id,
            )
        with self._write_uow_factory() as uow:
            self._p6_repository(uow).register_counterfactual(value)
            ProductionJobOutputRepository(
                uow.canonical_rows
            ).register(
                job_id=job_id,
                command=P6_COUNTERFACTUAL_COMMAND,
                product_refs=(
                    (
                        "counterfactual_run_id",
                        value.counterfactual_run_id,
                    ),
                    (
                        "counterfactual_request_id",
                        value.counterfactual_request_id,
                    ),
                ),
            )
            DurableJobControl(
                ComputeJobRepository(uow.canonical_rows)
            ).succeed(job_id)
            uow.commit()

    def execute(
        self,
        *,
        job_id: str,
        request_hash: str,
        job_key: str,
        command: str,
        payload: Mapping[str, object],
    ) -> None:
        if command == _P1_COMMAND:
            self._execute_p1(
                job_id=job_id,
                request_hash=request_hash,
                job_key=job_key,
                command=command,
                payload=payload,
            )
            return
        if command == P2_ATTRIBUTION_COMMAND:
            self._execute_p2_attribution(
                job_id=job_id,
                request_hash=request_hash,
                payload=payload,
            )
            return
        if command == P3_BUILD_COMMAND:
            self._execute_p3_build(
                job_id=job_id,
                request_hash=request_hash,
                payload=payload,
            )
            return
        if command == P3_ESTIMATE_COMMAND:
            self._execute_p3_estimate(
                job_id=job_id,
                request_hash=request_hash,
                payload=payload,
            )
            return
        if command == P4_ASSESSMENT_COMMAND:
            self._execute_p4_assessment(
                job_id=job_id,
                request_hash=request_hash,
                payload=payload,
            )
            return
        if command == P5_ASSESSMENT_COMMAND:
            self._execute_p5_assessment(
                job_id=job_id,
                request_hash=request_hash,
                payload=payload,
            )
            return
        if command == P6_BUILD_COMMAND:
            self._execute_p6_build(
                job_id=job_id,
                request_hash=request_hash,
                payload=payload,
            )
            return
        if command == P6_FORECAST_COMMAND:
            self._execute_p6_forecast(
                job_id=job_id,
                request_hash=request_hash,
                payload=payload,
            )
            return
        if command == P6_COUNTERFACTUAL_COMMAND:
            self._execute_p6_counterfactual(
                job_id=job_id,
                request_hash=request_hash,
                payload=payload,
            )
            return
        raise ProductionJobExecutionError(
            "PRCB_C2_DOMAIN_COMMAND_UNSUPPORTED",
            command,
        )


class DurableApplicationJobControl:
    """Application Job DTOs backed by the durable DB 1.9 lifecycle."""

    def __init__(
        self,
        *,
        read_uow_factory: RuntimeUnitOfWorkFactory,
        write_uow_factory: RuntimeUnitOfWorkFactory,
        executor: DurableJobExecutor,
    ) -> None:
        self._read_uow_factory = read_uow_factory
        self._write_uow_factory = write_uow_factory
        self._executor = executor

    def _get_durable(self, job_id: str) -> object:
        try:
            with self._read_uow_factory() as uow:
                record = DurableJobControl(
                    ComputeJobRepository(uow.canonical_rows)
                ).get(job_id)
                uow.commit()
                return record
        except Exception as exc:
            if getattr(exc, "code", None) == "B3_COMPUTE_JOB_NOT_FOUND":
                raise JobNotFound(job_id) from exc
            raise

    def submit(
        self,
        *,
        idempotency_key: str,
        command: str,
        payload: dict[str, object],
        actor: str,
    ) -> JobSubmission:
        try:
            with self._write_uow_factory() as uow:
                control = DurableJobControl(
                    ComputeJobRepository(uow.canonical_rows)
                )
                submission = control.submit(
                    job_key=idempotency_key,
                    job_type=command,
                    payload=payload,
                    # The production source is worker-governed and may describe a
                    # Session that is not durable yet. Keep this nullable until
                    # prerequisites are persisted so fresh-DB submission cannot
                    # violate the DB 1.9 training_session foreign key.
                    session_id=None,
                )
                if submission.reused:
                    _record_job_audit(
                        uow,
                        actor=actor,
                        action="JOB_SUBMIT_REUSE",
                        job_id=submission.record.job_id,
                        request_id=idempotency_key,
                        reason=None,
                        status=submission.record.status.value,
                    )
                    uow.commit()
                    return JobSubmission(
                        record=_job_record(submission.record),
                        reused=True,
                    )
                queued = control.queue(submission.record.job_id)
                _record_job_audit(
                    uow,
                    actor=actor,
                    action="JOB_SUBMIT",
                    job_id=queued.job_id,
                    request_id=idempotency_key,
                    reason=None,
                    status=queued.status.value,
                )
                uow.commit()
        except DurableJobControlError as exc:
            if exc.code == "B3_JOB_IDEMPOTENCY_CONFLICT":
                raise IdempotencyConflict(idempotency_key) from exc
            raise

        with self._write_uow_factory() as uow:
            running = DurableJobControl(
                ComputeJobRepository(uow.canonical_rows)
            ).start(queued.job_id)
            uow.commit()

        try:
            self._executor.execute(
                job_id=running.job_id,
                request_hash=running.input_hash,
                job_key=running.job_key,
                command=running.job_type,
                payload=payload,
            )
        except Exception as exc:
            with self._write_uow_factory() as uow:
                control = DurableJobControl(
                    ComputeJobRepository(uow.canonical_rows)
                )
                current = control.get(running.job_id)
                if current.status in {
                    ComputeJobState.SUBMITTED,
                    ComputeJobState.QUEUED,
                    ComputeJobState.RUNNING,
                }:
                    current = control.fail(
                        running.job_id,
                        reason_code=str(
                            getattr(exc, "code", "PRCB_C2_EXECUTION_FAILED")
                        ),
                        error_detail=_governed_job_failure_detail(exc),
                    )
                uow.commit()
            return JobSubmission(record=_job_record(current), reused=False)

        with self._write_uow_factory() as uow:
            control = DurableJobControl(
                ComputeJobRepository(uow.canonical_rows)
            )
            current = control.get(running.job_id)
            if current.status is ComputeJobState.RUNNING:
                terminal = control.succeed(running.job_id)
            elif current.status is ComputeJobState.SUCCEEDED:
                terminal = current
            else:
                raise DurableJobControlError(
                    "B3_JOB_TERMINAL_STATE_INVALID",
                    f"{running.job_id}:{current.status.value}",
                )
            uow.commit()
        return JobSubmission(record=_job_record(terminal), reused=False)

    def get(self, job_id: str) -> JobRecord:
        return _job_record(self._get_durable(job_id))

    def cancel(self, *, job_id: str, actor: str, reason: str) -> JobRecord:
        if not reason.strip():
            raise ValueError("reason must be non-empty")
        self._executor.cancel(job_id)
        try:
            with self._write_uow_factory() as uow:
                control = DurableJobControl(
                    ComputeJobRepository(uow.canonical_rows)
                )
                current = control.get(job_id)
                if current.status is ComputeJobState.CANCELLED:
                    _record_job_audit(
                        uow,
                        actor=actor,
                        action="JOB_CANCEL_NOOP",
                        job_id=job_id,
                        request_id=None,
                        reason=reason,
                        status=current.status.value,
                    )
                    uow.commit()
                    return _job_record(current)
                if current.status in {
                    ComputeJobState.SUCCEEDED,
                    ComputeJobState.FAILED,
                }:
                    _record_job_audit(
                        uow,
                        actor=actor,
                        action="JOB_CANCEL_NOOP",
                        job_id=job_id,
                        request_id=None,
                        reason=reason,
                        status=current.status.value,
                    )
                    uow.commit()
                    return _job_record(current)
                cancelled = control.cancel(job_id, reason_code=reason)
                _record_job_audit(
                    uow,
                    actor=actor,
                    action="JOB_CANCEL",
                    job_id=job_id,
                    request_id=None,
                    reason=reason,
                    status=cancelled.status.value,
                )
                uow.commit()
                return _job_record(cancelled)
        except Exception as exc:
            if getattr(exc, "code", None) == "B3_COMPUTE_JOB_NOT_FOUND":
                raise JobNotFound(job_id) from exc
            raise
