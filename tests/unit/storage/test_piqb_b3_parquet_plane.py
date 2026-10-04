from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tpaa_storage import (
    LocalObjectStore,
    ParquetColumn,
    ParquetDatasetArtifact,
    ParquetPartition,
    ParquetPlaneError,
    ParquetScalarType,
    ParquetSchema,
    ParquetWriteRequest,
    PolarsParquetPlane,
)


def _schema() -> ParquetSchema:
    return ParquetSchema(
        schema_id="FLIGHT_CANONICAL",
        schema_version="1.0.0",
        columns=(
            ParquetColumn("session_time_us", ParquetScalarType.INT64),
            ParquetColumn("aircraft_id", ParquetScalarType.STRING),
            ParquetColumn("tas_mps", ParquetScalarType.FLOAT64, nullable=True),
            ParquetColumn("valid", ParquetScalarType.BOOLEAN),
        ),
    )


def _request() -> ParquetWriteRequest:
    return ParquetWriteRequest(
        operation_id="b3-op-001",
        namespace="session",
        dataset_kind="canonical-flight",
        dataset_id="11111111-1111-4111-8111-111111111111",
        schema=_schema(),
        partition=ParquetPartition((("aircraft_id", "AIRCRAFT-01"),)),
        rows=(
            {
                "session_time_us": 100,
                "aircraft_id": "AIRCRAFT-01",
                "tas_mps": 120.5,
                "valid": True,
            },
            {
                "session_time_us": 200,
                "aircraft_id": "AIRCRAFT-01",
                "tas_mps": None,
                "valid": False,
            },
        ),
    )


def test_parquet_plane_write_read_scan_and_hashes_survive_restart(
    tmp_path: Path,
) -> None:
    root = tmp_path / "object-store"
    plane = PolarsParquetPlane(LocalObjectStore(root))

    artifact = plane.write(_request())

    assert artifact.logical_uri == (
        "tpaa-parquet://session/canonical-flight/"
        "11111111-1111-4111-8111-111111111111/"
        "aircraft_id=AIRCRAFT-01/part-000.parquet"
    )
    assert len(artifact.artifact_sha256) == 64
    assert len(artifact.logical_content_hash) == 64
    assert artifact.row_count == 2
    assert artifact.min_session_time_us == 100
    assert artifact.max_session_time_us == 200
    assert plane.read_rows(artifact) == _request().rows

    restarted = PolarsParquetPlane(LocalObjectStore(root))
    assert restarted.scan_rows(artifact) == _request().rows


def test_parquet_plane_logical_hash_is_distinct_from_byte_hash(tmp_path: Path) -> None:
    plane = PolarsParquetPlane(LocalObjectStore(tmp_path / "objects"))
    artifact = plane.write(_request())

    assert artifact.logical_content_hash != artifact.artifact_sha256


def test_parquet_plane_fails_closed_on_partition_and_artifact_drift(
    tmp_path: Path,
) -> None:
    plane = PolarsParquetPlane(LocalObjectStore(tmp_path / "objects"))

    with pytest.raises(ParquetPlaneError, match="B3_PARQUET_PARTITION_COLUMN_UNKNOWN"):
        plane.write(
            replace(
                _request(),
                partition=ParquetPartition((("unknown", "x"),)),
            )
        )

    artifact = plane.write(_request())
    tampered = ParquetDatasetArtifact(
        logical_uri=artifact.logical_uri,
        artifact_sha256="0" * 64,
        logical_content_hash=artifact.logical_content_hash,
        byte_size=artifact.byte_size,
        row_count=artifact.row_count,
        schema=artifact.schema,
        partition=artifact.partition,
        min_session_time_us=artifact.min_session_time_us,
        max_session_time_us=artifact.max_session_time_us,
    )
    with pytest.raises(ParquetPlaneError, match="B3_PARQUET_ARTIFACT_HASH_MISMATCH"):
        plane.read_rows(tampered)
