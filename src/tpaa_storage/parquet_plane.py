"""PIQB B3 governed Parquet data plane over logical TPAA object identity."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from tpaa_platform.polars_runtime import GovernedPolarsRuntime
from tpaa_storage.hashing import logical_content_hash
from tpaa_storage.object_seal import LocalSealedObjectFlow
from tpaa_storage.object_store import LocalObjectStore, StoredObject

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class ParquetScalarType(StrEnum):
    STRING = "STRING"
    INT64 = "INT64"
    FLOAT64 = "FLOAT64"
    BOOLEAN = "BOOLEAN"


class ParquetPlaneError(RuntimeError):
    """Fail-closed Parquet plane contract error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True)
class ParquetColumn:
    name: str
    scalar_type: ParquetScalarType
    nullable: bool = False


@dataclass(frozen=True)
class ParquetSchema:
    schema_id: str
    schema_version: str
    columns: tuple[ParquetColumn, ...]


@dataclass(frozen=True)
class ParquetPartition:
    values: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ParquetWriteRequest:
    operation_id: str
    namespace: str
    dataset_kind: str
    dataset_id: str
    schema: ParquetSchema
    partition: ParquetPartition
    rows: tuple[Mapping[str, object], ...]


@dataclass(frozen=True)
class ParquetDatasetArtifact:
    logical_uri: str
    artifact_sha256: str
    logical_content_hash: str
    byte_size: int
    row_count: int
    schema: ParquetSchema
    partition: ParquetPartition
    min_session_time_us: int | None
    max_session_time_us: int | None


def _require_identifier(value: str, *, field: str) -> None:
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ParquetPlaneError("B3_PARQUET_IDENTIFIER_INVALID", field)


def _require_token(value: str, *, field: str) -> None:
    if not value or not _TOKEN_RE.fullmatch(value):
        raise ParquetPlaneError("B3_PARQUET_TOKEN_INVALID", field)


def _validate_schema(schema: ParquetSchema) -> None:
    _require_token(schema.schema_id, field="schema_id")
    _require_token(schema.schema_version, field="schema_version")
    if not schema.columns:
        raise ParquetPlaneError("B3_PARQUET_SCHEMA_EMPTY", schema.schema_id)
    names = [column.name for column in schema.columns]
    if len(names) != len(set(names)):
        raise ParquetPlaneError("B3_PARQUET_SCHEMA_DUPLICATE_COLUMN", schema.schema_id)
    for column in schema.columns:
        _require_identifier(column.name, field=column.name)


def _validate_partition(partition: ParquetPartition, schema: ParquetSchema) -> None:
    names = {column.name for column in schema.columns}
    keys = [key for key, _ in partition.values]
    if len(keys) != len(set(keys)):
        raise ParquetPlaneError("B3_PARQUET_PARTITION_DUPLICATE_KEY", ",".join(keys))
    for key, value in partition.values:
        if key not in names:
            raise ParquetPlaneError("B3_PARQUET_PARTITION_COLUMN_UNKNOWN", key)
        _require_identifier(key, field=key)
        _require_token(value, field=f"partition.{key}")


def _validate_value(value: object, column: ParquetColumn, *, row_index: int) -> None:
    if value is None:
        if column.nullable:
            return
        raise ParquetPlaneError(
            "B3_PARQUET_NULL_FORBIDDEN",
            f"row={row_index} column={column.name}",
        )
    valid = False
    if column.scalar_type is ParquetScalarType.STRING:
        valid = isinstance(value, str)
    elif column.scalar_type is ParquetScalarType.INT64:
        valid = isinstance(value, int) and not isinstance(value, bool)
    elif column.scalar_type is ParquetScalarType.FLOAT64:
        valid = isinstance(value, (int, float)) and not isinstance(value, bool)
        if isinstance(value, float) and not math.isfinite(value):
            valid = False
    elif column.scalar_type is ParquetScalarType.BOOLEAN:
        valid = isinstance(value, bool)
    if not valid:
        raise ParquetPlaneError(
            "B3_PARQUET_VALUE_TYPE_INVALID",
            f"row={row_index} column={column.name}",
        )


def _normalized_rows(
    rows: Sequence[Mapping[str, object]],
    schema: ParquetSchema,
) -> tuple[dict[str, object], ...]:
    columns = tuple(column.name for column in schema.columns)
    expected = set(columns)
    normalized: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        if set(row) != expected:
            raise ParquetPlaneError(
                "B3_PARQUET_ROW_SHAPE_MISMATCH",
                f"row={index}",
            )
        projected: dict[str, object] = {}
        for column in schema.columns:
            value = row[column.name]
            _validate_value(value, column, row_index=index)
            projected[column.name] = value
        normalized.append(projected)
    return tuple(normalized)


def _hash_scalar(value: object) -> object:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ParquetPlaneError("B3_PARQUET_NONFINITE_FLOAT", value.hex())
        return {"float_hex": value.hex()}
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise ParquetPlaneError(
        "B3_PARQUET_HASH_VALUE_UNSUPPORTED",
        type(value).__name__,
    )


def _logical_hash(
    *,
    schema: ParquetSchema,
    partition: ParquetPartition,
    rows: Sequence[Mapping[str, object]],
) -> str:
    payload = {
        "schema": {
            "id": schema.schema_id,
            "version": schema.schema_version,
            "columns": [
                {
                    "name": column.name,
                    "type": column.scalar_type.value,
                    "nullable": column.nullable,
                }
                for column in schema.columns
            ],
        },
        "partition": [
            {"key": key, "value": value} for key, value in partition.values
        ],
        "rows": [
            {
                column.name: _hash_scalar(row[column.name])
                for column in schema.columns
            }
            for row in rows
        ],
    }
    return logical_content_hash(payload)


def _session_time_range(
    rows: Sequence[Mapping[str, object]],
    schema: ParquetSchema,
) -> tuple[int | None, int | None]:
    columns = {column.name: column for column in schema.columns}
    column = columns.get("session_time_us")
    if column is None:
        return None, None
    if column.scalar_type is not ParquetScalarType.INT64:
        raise ParquetPlaneError(
            "B3_PARQUET_SESSION_TIME_TYPE_INVALID",
            column.scalar_type.value,
        )
    values = [
        row["session_time_us"]
        for row in rows
        if row["session_time_us"] is not None
    ]
    if not values:
        return None, None
    typed = [int(value) for value in values if isinstance(value, int)]
    return min(typed), max(typed)


def _logical_uri(request: ParquetWriteRequest) -> str:
    _require_token(request.namespace, field="namespace")
    _require_token(request.dataset_kind, field="dataset_kind")
    _require_token(request.dataset_id, field="dataset_id")
    parts = [
        request.dataset_kind,
        request.dataset_id,
        *(f"{key}={value}" for key, value in request.partition.values),
        "part-000.parquet",
    ]
    return f"tpaa-parquet://{request.namespace}/{'/'.join(parts)}"


class PolarsParquetPlane:
    """Typed, hash-guarded Parquet writer/reader/scanner over local object storage."""

    def __init__(
        self,
        store: LocalObjectStore,
        *,
        runtime: GovernedPolarsRuntime | None = None,
    ) -> None:
        self._store = store
        self._flow = LocalSealedObjectFlow(store)
        self._runtime = runtime or GovernedPolarsRuntime()

    def write(self, request: ParquetWriteRequest) -> ParquetDatasetArtifact:
        _validate_schema(request.schema)
        _validate_partition(request.partition, request.schema)
        _require_token(request.operation_id, field="operation_id")
        rows = _normalized_rows(request.rows, request.schema)
        schema = {
            column.name: column.scalar_type.value
            for column in request.schema.columns
        }
        frame = self._runtime.frame(rows, schema=schema)
        data = self._runtime.write_parquet_bytes(frame)
        uri = _logical_uri(request)
        staged = self._flow.stage(
            sealed_uri=uri,
            data=data,
            operation_id=request.operation_id,
        )
        sealed = self._flow.seal(staged)
        minimum, maximum = _session_time_range(rows, request.schema)
        return ParquetDatasetArtifact(
            logical_uri=sealed.logical_uri,
            artifact_sha256=sealed.artifact_sha256,
            logical_content_hash=_logical_hash(
                schema=request.schema,
                partition=request.partition,
                rows=rows,
            ),
            byte_size=sealed.byte_size,
            row_count=len(rows),
            schema=request.schema,
            partition=request.partition,
            min_session_time_us=minimum,
            max_session_time_us=maximum,
        )

    def _verify_stored(self, artifact: ParquetDatasetArtifact) -> StoredObject:
        stored = StoredObject(
            logical_uri=artifact.logical_uri,
            artifact_sha256=artifact.artifact_sha256,
            byte_size=artifact.byte_size,
        )
        if not self._store.verify(stored):
            raise ParquetPlaneError(
                "B3_PARQUET_ARTIFACT_HASH_MISMATCH",
                artifact.logical_uri,
            )
        return stored

    def _verify_frame(
        self,
        artifact: ParquetDatasetArtifact,
        rows: tuple[dict[str, object], ...],
        columns: tuple[str, ...],
    ) -> tuple[dict[str, object], ...]:
        expected_columns = tuple(column.name for column in artifact.schema.columns)
        if columns != expected_columns:
            raise ParquetPlaneError(
                "B3_PARQUET_SCHEMA_MISMATCH",
                artifact.logical_uri,
            )
        normalized = _normalized_rows(rows, artifact.schema)
        if len(normalized) != artifact.row_count:
            raise ParquetPlaneError(
                "B3_PARQUET_ROW_COUNT_MISMATCH",
                artifact.logical_uri,
            )
        actual_hash = _logical_hash(
            schema=artifact.schema,
            partition=artifact.partition,
            rows=normalized,
        )
        if actual_hash != artifact.logical_content_hash:
            raise ParquetPlaneError(
                "B3_PARQUET_LOGICAL_HASH_MISMATCH",
                artifact.logical_uri,
            )
        return normalized

    def read_rows(
        self,
        artifact: ParquetDatasetArtifact,
    ) -> tuple[dict[str, object], ...]:
        self._verify_stored(artifact)
        data = self._store.read_bytes(artifact.logical_uri)
        frame = self._runtime.read_parquet_bytes(data)
        return self._verify_frame(
            artifact,
            self._runtime.rows(frame),
            self._runtime.columns(frame),
        )

    def scan_rows(
        self,
        artifact: ParquetDatasetArtifact,
    ) -> tuple[dict[str, object], ...]:
        self._verify_stored(artifact)
        path = self._store.physical_path(artifact.logical_uri)
        lazy = self._runtime.scan_parquet(path)
        frame = self._runtime.collect_streaming(lazy)
        return self._verify_frame(
            artifact,
            self._runtime.rows(frame),
            self._runtime.columns(frame),
        )
