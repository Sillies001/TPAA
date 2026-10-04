from __future__ import annotations

import pytest

from tpaa_platform import (
    EXPECTED_POLARS_VERSION,
    GovernedPolarsRuntime,
    PolarsRuntimeError,
)


def test_governed_polars_runtime_is_exactly_pinned_and_roundtrips_parquet() -> None:
    runtime = GovernedPolarsRuntime()

    assert runtime.identity.engine == "POLARS"
    assert runtime.identity.version == EXPECTED_POLARS_VERSION == "1.44.2"
    assert runtime.identity.streaming_engine == "streaming"

    frame = runtime.frame(
        (
            {"session_time_us": 0, "value": 1.5},
            {"session_time_us": 1, "value": 2.5},
        ),
        schema={"session_time_us": "INT64", "value": "FLOAT64"},
    )
    payload = runtime.write_parquet_bytes(frame)
    restored = runtime.read_parquet_bytes(payload)

    assert runtime.columns(restored) == ("session_time_us", "value")
    assert runtime.rows(restored) == (
        {"session_time_us": 0, "value": 1.5},
        {"session_time_us": 1, "value": 2.5},
    )


def test_governed_polars_runtime_rejects_shape_and_type_drift() -> None:
    runtime = GovernedPolarsRuntime()

    with pytest.raises(PolarsRuntimeError, match="B3_POLARS_ROW_SHAPE_MISMATCH"):
        runtime.frame(
            ({"x": 1, "unexpected": 2},),
            schema={"x": "INT64"},
        )

    with pytest.raises(PolarsRuntimeError, match="B3_POLARS_FRAME_BUILD_FAILED"):
        runtime.frame(
            ({"x": "not-an-int"},),
            schema={"x": "INT64"},
        )
