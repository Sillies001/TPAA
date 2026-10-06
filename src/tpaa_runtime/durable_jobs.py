"""PRCB C2 durable formal Job API and governed production worker orchestration."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol, cast

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
    P6PersistenceRepository,
    allocate_p2_release_id,
    p2_release_scope_key,
    ProductionImportService,
    SourceImportCommand,
    SourceProvenanceRepository,
)
from tpaa_assessment import P2AttributionExecution
from tpaa_capability.p3_twin import P3CapabilityEstimate
from tpaa_capability.p6_counterfactual import P6CounterfactualRevision
from tpaa_capability.p6_forecast import P6ForecastRevision
from tpaa_ingest import (
    PRODUCTION_FLIGHT_ADAPTER_ID,
    PRODUCTION_FLIGHT_ADAPTER_VERSION,
    PRODUCTION_FLIGHT_MEDIA_TYPE,
    ProductionFlightJsonAdapter,
    ProductionSourceAdapterError,
    SourceFamily,
    build_production_source_registry,
    validate_production_flight_document,
)
from tpaa_platform import SpawnWorkerDispatcher, WorkerPayload
from tpaa_storage import (
    ComputeJobRepository,
    ComputeJobState,
    LocalObjectStore,
    ParquetColumn,
    ParquetPartition,
    ParquetScalarType,
    ParquetSchema,
    ParquetWriteRequest,
    PolarsParquetPlane,
)

from .durable_repositories import RuntimeCanonicalUnitOfWork, RuntimeUnitOfWorkFactory
from .production_worker import (
    P2_ATTRIBUTION_COMMAND,
    P3_ESTIMATE_COMMAND,
    P6_COUNTERFACTUAL_COMMAND,
    P6_FORECAST_COMMAND,
    ProductionP1WorkerProduct,
    ProductionP2AttributionWorkerInput,
    ProductionP3EstimateWorkerInput,
    ProductionP6CounterfactualWorkerInput,
    ProductionP6ForecastWorkerInput,
)

_GOVERNED_HANDLER = "tpaa_runtime.production_worker:execute"
_P1_COMMAND = "BUILD_P1_RELEASE"


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
        document = validate_production_flight_document(source_bytes)
        metadata = _mapping(payload.get("source_import"), field="source_import")
        family_text = _text(metadata.get("source_family"), field="source_family")
        try:
            family = SourceFamily(family_text)
        except ValueError as exc:
            raise ProductionJobExecutionError(
                "UNSUPPORTED_ADAPTER",
                family_text,
            ) from exc
        if family is not SourceFamily.FLIGHT:
            raise ProductionJobExecutionError("UNSUPPORTED_ADAPTER", family.value)
        session_id = _text(metadata.get("session_id"), field="session_id")
        if document.get("session_id") != session_id:
            raise ProductionJobExecutionError(
                "PRCB_C2_SOURCE_SESSION_DRIFT",
                session_id,
            )
        adapter = ProductionFlightJsonAdapter()
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
        if (
            envelope.adapter_id != PRODUCTION_FLIGHT_ADAPTER_ID
            or envelope.adapter_version != PRODUCTION_FLIGHT_ADAPTER_VERSION
            or envelope.media_type != PRODUCTION_FLIGHT_MEDIA_TYPE
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
        source_command = self._source_import(payload)
        try:
            self._adapters.require_family(source_command.envelope.source_family)
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
                uow.canonical_rows.insert(
                    prerequisite.table,
                    prerequisite.values,
                    field_kinds=prerequisite.field_kinds,
                )
            ProductionImportService(
                adapters=self._adapters,
                provenance=SourceProvenanceRepository(uow.canonical_rows),
            ).register(source_command)
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
        dataset_snapshot_id = _text(
            payload.get("dataset_snapshot_id"),
            field="dataset_snapshot_id",
        )
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

        with self._write_uow_factory() as uow:
            repository = self._p2_repository(uow)
            compute_input = repository.exact_compute_input(dataset_snapshot_id)
            release_repository = P2ReleaseRepository(uow.canonical_rows)
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
            if run.model_artifact_uri is not None or run.model_artifact_hash is not None:
                raise ProductionJobExecutionError(
                    "PRCB_C2_P2_MODEL_ARTIFACT_DRIFT",
                    run.attribution_run_id,
                )
        else:
            if run.model_artifact_hash is None or run.model_artifact_uri is not None:
                raise ProductionJobExecutionError(
                    "PRCB_C2_P2_MODEL_ARTIFACT_DRIFT",
                    run.attribution_run_id,
                )
            artifact_bytes = value.model_artifact_json.encode("ascii")
            logical_uri = (
                "tpaa-object://p2-attribution-model/"
                f"{run.attribution_run_id}.json"
            )
            stored = self._object_store.put_bytes(logical_uri, artifact_bytes)
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
            repository.register_adjusted_estimate(value.adjusted_estimate)
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

    def _p6_repository(
        self,
        uow: RuntimeCanonicalUnitOfWork,
    ) -> P6PersistenceRepository:
        return P6PersistenceRepository(
            uow.canonical_rows,
            object_store=self._object_store,
            model_build_resolver=DurableP6ModelBuildResolver(uow.canonical_rows),
        )

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
        if command == P3_ESTIMATE_COMMAND:
            self._execute_p3_estimate(
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
        del actor
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
                    uow.commit()
                    return JobSubmission(
                        record=_job_record(submission.record),
                        reused=True,
                    )
                queued = control.queue(submission.record.job_id)
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
                        error_detail=type(exc).__name__,
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
        del actor
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
                    uow.commit()
                    return _job_record(current)
                if current.status in {
                    ComputeJobState.SUCCEEDED,
                    ComputeJobState.FAILED,
                }:
                    uow.commit()
                    return _job_record(current)
                cancelled = control.cancel(job_id, reason_code=reason)
                uow.commit()
                return _job_record(cancelled)
        except Exception as exc:
            if getattr(exc, "code", None) == "B3_COMPUTE_JOB_NOT_FOUND":
                raise JobNotFound(job_id) from exc
            raise
