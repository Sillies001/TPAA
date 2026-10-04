"""Governed Polars runtime adapter for PIQB B3 compute/storage infrastructure."""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import polars as pl

EXPECTED_POLARS_VERSION = "1.44.2"
SUPPORTED_COLUMN_TYPES = frozenset({"STRING", "INT64", "FLOAT64", "BOOLEAN"})


class PolarsRuntimeError(RuntimeError):
    """Fail-closed Polars runtime contract error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True)
class PolarsRuntimeIdentity:
    engine: str
    version: str
    streaming_engine: str


class GovernedPolarsRuntime:
    """Version-pinned infrastructure wrapper with no TPAA business semantics."""

    def __init__(self) -> None:
        actual = str(pl.__version__)
        if actual != EXPECTED_POLARS_VERSION:
            raise PolarsRuntimeError(
                "B3_POLARS_VERSION_MISMATCH",
                f"expected={EXPECTED_POLARS_VERSION} actual={actual}",
            )

    @property
    def identity(self) -> PolarsRuntimeIdentity:
        return PolarsRuntimeIdentity(
            engine="POLARS",
            version=EXPECTED_POLARS_VERSION,
            streaming_engine="streaming",
        )

    @staticmethod
    def _dtype(token: str) -> Any:
        mapping: dict[str, Any] = {
            "STRING": pl.String,
            "INT64": pl.Int64,
            "FLOAT64": pl.Float64,
            "BOOLEAN": pl.Boolean,
        }
        dtype = mapping.get(token)
        if dtype is None:
            raise PolarsRuntimeError(
                "B3_POLARS_COLUMN_TYPE_UNSUPPORTED",
                token,
            )
        return dtype

    def frame(
        self,
        rows: Sequence[Mapping[str, object]],
        *,
        schema: Mapping[str, str],
    ) -> pl.DataFrame:
        if not schema:
            raise PolarsRuntimeError("B3_POLARS_SCHEMA_EMPTY", "schema")
        if any(token not in SUPPORTED_COLUMN_TYPES for token in schema.values()):
            unsupported = sorted(
                token for token in schema.values() if token not in SUPPORTED_COLUMN_TYPES
            )
            raise PolarsRuntimeError(
                "B3_POLARS_COLUMN_TYPE_UNSUPPORTED",
                ",".join(unsupported),
            )
        columns = tuple(schema)
        expected = set(columns)
        normalized: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            if set(row) != expected:
                raise PolarsRuntimeError(
                    "B3_POLARS_ROW_SHAPE_MISMATCH",
                    f"row={index}",
                )
            normalized.append(
                cast(dict[str, Any], {name: row[name] for name in columns})
            )
        polars_schema: dict[str, Any] = {
            name: self._dtype(token) for name, token in schema.items()
        }
        try:
            return pl.DataFrame(
                normalized,
                schema=polars_schema,
                strict=True,
            )
        except Exception as exc:
            raise PolarsRuntimeError(
                "B3_POLARS_FRAME_BUILD_FAILED",
                str(exc),
            ) from exc

    @staticmethod
    def columns(frame: pl.DataFrame) -> tuple[str, ...]:
        return tuple(str(name) for name in frame.columns)

    @staticmethod
    def rows(frame: pl.DataFrame) -> tuple[dict[str, object], ...]:
        raw = frame.to_dicts()
        return tuple(
            {str(key): cast(object, value) for key, value in row.items()}
            for row in raw
        )

    @staticmethod
    def write_parquet_bytes(frame: pl.DataFrame) -> bytes:
        buffer = io.BytesIO()
        try:
            frame.write_parquet(
                buffer,
                compression="zstd",
                statistics=True,
            )
        except Exception as exc:
            raise PolarsRuntimeError(
                "B3_POLARS_PARQUET_WRITE_FAILED",
                str(exc),
            ) from exc
        return buffer.getvalue()

    @staticmethod
    def read_parquet_bytes(data: bytes) -> pl.DataFrame:
        try:
            return pl.read_parquet(io.BytesIO(data))
        except Exception as exc:
            raise PolarsRuntimeError(
                "B3_POLARS_PARQUET_READ_FAILED",
                str(exc),
            ) from exc

    @staticmethod
    def scan_parquet(path: Path) -> pl.LazyFrame:
        try:
            return pl.scan_parquet(path)
        except Exception as exc:
            raise PolarsRuntimeError(
                "B3_POLARS_PARQUET_SCAN_FAILED",
                str(exc),
            ) from exc

    @staticmethod
    def collect_streaming(frame: pl.LazyFrame) -> pl.DataFrame:
        try:
            return frame.collect(engine="streaming")
        except Exception as exc:
            raise PolarsRuntimeError(
                "B3_POLARS_STREAMING_COLLECT_FAILED",
                str(exc),
            ) from exc
