from __future__ import annotations

from pathlib import Path

from tpaa_ingest.lineage_quality import (
    DIRECT_SOURCE_FIELD_BY_CANONICAL,
    MISSING,
    PRESENT,
    build_lineage_quality_projection,
)
from tpaa_ingest.source_adapter import load_synthetic_fixture_bundle
from tpaa_registry import register_synthetic_fixture

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "m1"


def test_nominal_fields_trace_to_exact_immutable_source_artifact() -> None:
    path = FIXTURE_ROOT / "BF_M1_NOMINAL_V1"
    projection = build_lineage_quality_projection(path)
    registration = register_synthetic_fixture(path)

    assert projection.source_stream_id == registration.source_stream_id
    assert projection.source_artifact_ref == registration.source_artifact.logical_ref
    assert projection.source_artifact_sha256 == registration.source_artifact.sha256
    first = projection.rows[0]
    assert len(first.fields) == 7
    assert all(field.value_status == PRESENT for field in first.fields)
    for field in first.fields:
        assert field.source_field == DIRECT_SOURCE_FIELD_BY_CANONICAL[
            field.canonical_field
        ]
        assert field.source_stream_ordinal == 0
        assert field.source_artifact_ref == projection.source_artifact_ref
        assert field.source_artifact_sha256 == projection.source_artifact_sha256
        assert field.quality_mask == first.quality_mask


def test_structured_partial_preserves_missing_without_zero_fill() -> None:
    projection = build_lineage_quality_projection(
        FIXTURE_ROOT / "BF_M1_STRUCTURED_PARTIAL_V1"
    )
    missing = [
        field
        for row in projection.rows
        for field in row.fields
        if field.value_status == MISSING
    ]
    assert len(missing) == 8
    assert sum(field.canonical_field == "tas_mps" for field in missing) == 4
    assert sum(field.canonical_field == "mach" for field in missing) == 4


def test_quality_mask_is_propagated_exactly_to_row_and_every_field() -> None:
    path = FIXTURE_ROOT / "BF_M1_CROSS_PLATFORM_V1"
    bundle = load_synthetic_fixture_bundle(path)
    projection = build_lineage_quality_projection(path)

    for source_row, row in zip(bundle.rows, projection.rows, strict=True):
        expected = source_row.values["quality"]
        assert row.quality_mask == expected
        assert all(field.quality_mask == expected for field in row.fields)


def test_projection_replay_is_exact_and_stops_before_downstream_execution() -> None:
    path = FIXTURE_ROOT / "BF_M1_REPLAY_V1"
    first = build_lineage_quality_projection(path)
    second = build_lineage_quality_projection(path)

    assert first == second
    assert first.database_persistence_executed is False
    assert first.episode_projection_executed is False
    assert first.stage_projection_executed is False
    assert first.world_projection_executed is False
    assert first.metric_logic_executed is False
