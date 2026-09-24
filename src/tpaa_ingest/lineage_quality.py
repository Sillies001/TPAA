"""M1-DATA-007 field-level source lineage and quality propagation.

This module attaches immutable source provenance to the exact Canonical flight
channels produced by M1-DATA-005. It preserves the existing quality mask and
missing-value state; it does not invent quality semantics, repair invalid
values, persist datasets, or execute Episode/Stage/World/Metric logic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from tpaa_ingest.canonical_flight_channels import (
    CANONICAL_FLIGHT_CHANNELS,
    CanonicalFlightRow,
    project_canonical_flight_channels,
)
from tpaa_ingest.source_adapter import load_synthetic_fixture_bundle
from tpaa_registry import (
    build_session_time_projection,
    register_synthetic_fixture,
    resolve_aircraft_identity,
)

LINEAGE_QUALITY_AUTHORITY = "M1_DATA_007_LINEAGE_QUALITY_V1"
DIRECT_SOURCE_FIELD_BY_CANONICAL = {
    "body_p_rad_s": "p",
    "nz_g": "nz",
    "heading_true_rad": "heading",
    "tas_mps": "tas",
    "mach": "mach",
    "session_time_us": "source_time_us",
    "quality_mask": "quality",
}
PRESENT = "PRESENT"
MISSING = "MISSING"


class LineageQualityError(RuntimeError):
    """Deterministic fail-closed lineage/quality propagation error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class CanonicalFieldLineage:
    """Trace one Canonical field to one immutable source artifact location."""

    canonical_field: str
    source_field: str
    source_stream_id: str
    source_stream_ordinal: int
    source_artifact_ref: str
    source_artifact_sha256: str
    mapping_ref: str
    time_transform_hash: str | None
    value_status: str
    quality_mask: int


@dataclass(frozen=True)
class CanonicalLineageRow:
    """Field-level provenance and quality for one Canonical aircraft-state row."""

    source_stream_ordinal: int
    session_time_us: int
    quality_mask: int
    fields: tuple[CanonicalFieldLineage, ...]


@dataclass(frozen=True)
class LineageQualityProjection:
    """Replay-stable lineage product for one governed M1 fixture."""

    fixture_id: str
    fixture_version: str
    session_id: str
    aircraft_id: str
    authority_id: str
    source_stream_id: str
    source_artifact_ref: str
    source_artifact_sha256: str
    canonical_logical_hash: str
    rows: tuple[CanonicalLineageRow, ...]
    logical_hash: str
    database_persistence_executed: bool = False
    episode_projection_executed: bool = False
    stage_projection_executed: bool = False
    world_projection_executed: bool = False
    metric_logic_executed: bool = False


def _field_values(row: CanonicalFlightRow) -> dict[str, float | int | None]:
    return {
        "body_p_rad_s": row.body_p_rad_s,
        "nz_g": row.nz_g,
        "heading_true_rad": row.heading_true_rad,
        "tas_mps": row.tas_mps,
        "mach": row.mach,
        "session_time_us": row.session_time_us,
        "quality_mask": row.quality_mask,
    }


def _logical_hash(
    *,
    fixture_id: str,
    session_id: str,
    source_artifact_sha256: str,
    canonical_logical_hash: str,
    rows: tuple[CanonicalLineageRow, ...],
) -> str:
    payload = {
        "authority_id": LINEAGE_QUALITY_AUTHORITY,
        "fixture_id": fixture_id,
        "session_id": session_id,
        "source_artifact_sha256": source_artifact_sha256,
        "canonical_logical_hash": canonical_logical_hash,
        "rows": [
            {
                "source_stream_ordinal": row.source_stream_ordinal,
                "session_time_us": row.session_time_us,
                "quality_mask": row.quality_mask,
                "fields": [
                    {
                        "canonical_field": field.canonical_field,
                        "source_field": field.source_field,
                        "source_stream_id": field.source_stream_id,
                        "source_stream_ordinal": field.source_stream_ordinal,
                        "source_artifact_ref": field.source_artifact_ref,
                        "source_artifact_sha256": field.source_artifact_sha256,
                        "mapping_ref": field.mapping_ref,
                        "time_transform_hash": field.time_transform_hash,
                        "value_status": field.value_status,
                        "quality_mask": field.quality_mask,
                    }
                    for field in row.fields
                ],
            }
            for row in rows
        ],
    }
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def build_lineage_quality_projection(bundle_path: Path) -> LineageQualityProjection:
    """Bind exact Canonical fields to immutable source lineage and quality."""

    bundle = load_synthetic_fixture_bundle(bundle_path)
    registration = register_synthetic_fixture(bundle_path)
    timed = build_session_time_projection(bundle_path)
    aircraft = resolve_aircraft_identity(bundle_path)

    if registration.session_id != bundle.session.session_id:
        raise LineageQualityError(
            "M1_LINEAGE_SESSION_ID_DRIFT",
            f"registry={registration.session_id} source={bundle.session.session_id}",
        )
    if timed.source_stream_id != registration.source_stream_id:
        raise LineageQualityError(
            "M1_LINEAGE_SOURCE_STREAM_DRIFT",
            f"time={timed.source_stream_id} registry={registration.source_stream_id}",
        )

    canonical = project_canonical_flight_channels(
        bundle,
        aircraft_id=aircraft.aircraft_id,
        session_time_us=tuple(row.session_time_us for row in timed.rows),
    )
    if canonical.channel_names != CANONICAL_FLIGHT_CHANNELS:
        raise LineageQualityError(
            "M1_LINEAGE_CANONICAL_CHANNEL_DRIFT",
            repr(canonical.channel_names),
        )
    if len(canonical.rows) != len(bundle.rows):
        raise LineageQualityError(
            "M1_LINEAGE_ROW_COUNT_DRIFT",
            f"canonical={len(canonical.rows)} source={len(bundle.rows)}",
        )

    lineage_rows: list[CanonicalLineageRow] = []
    for source_row, timed_row, canonical_row in zip(
        bundle.rows,
        timed.rows,
        canonical.rows,
        strict=True,
    ):
        ordinal = canonical_row.source_stream_ordinal
        if timed_row.source_stream_ordinal != ordinal:
            raise LineageQualityError(
                "M1_LINEAGE_ORDINAL_DRIFT",
                f"canonical={ordinal} time={timed_row.source_stream_ordinal}",
            )
        if canonical_row.session_time_us != timed_row.session_time_us:
            raise LineageQualityError("M1_LINEAGE_SESSION_TIME_DRIFT", f"ordinal={ordinal}")
        if canonical_row.quality_mask != source_row.values["quality"]:
            raise LineageQualityError("M1_LINEAGE_QUALITY_DRIFT", f"ordinal={ordinal}")

        fields: list[CanonicalFieldLineage] = []
        values = _field_values(canonical_row)
        for canonical_field in CANONICAL_FLIGHT_CHANNELS:
            source_field = DIRECT_SOURCE_FIELD_BY_CANONICAL[canonical_field]
            value = values[canonical_field]
            fields.append(
                CanonicalFieldLineage(
                    canonical_field=canonical_field,
                    source_field=source_field,
                    source_stream_id=registration.source_stream_id,
                    source_stream_ordinal=ordinal,
                    source_artifact_ref=registration.source_artifact.logical_ref,
                    source_artifact_sha256=registration.source_artifact.sha256,
                    mapping_ref=bundle.mapping_version,
                    time_transform_hash=(
                        timed.transform.transform_hash
                        if canonical_field == "session_time_us"
                        else None
                    ),
                    value_status=MISSING if value is None else PRESENT,
                    quality_mask=canonical_row.quality_mask,
                )
            )
        lineage_rows.append(
            CanonicalLineageRow(
                source_stream_ordinal=ordinal,
                session_time_us=canonical_row.session_time_us,
                quality_mask=canonical_row.quality_mask,
                fields=tuple(fields),
            )
        )

    rows = tuple(lineage_rows)
    return LineageQualityProjection(
        fixture_id=bundle.identity.fixture_id,
        fixture_version=bundle.identity.fixture_version,
        session_id=bundle.session.session_id,
        aircraft_id=aircraft.aircraft_id,
        authority_id=LINEAGE_QUALITY_AUTHORITY,
        source_stream_id=registration.source_stream_id,
        source_artifact_ref=registration.source_artifact.logical_ref,
        source_artifact_sha256=registration.source_artifact.sha256,
        canonical_logical_hash=canonical.logical_hash,
        rows=rows,
        logical_hash=_logical_hash(
            fixture_id=bundle.identity.fixture_id,
            session_id=bundle.session.session_id,
            source_artifact_sha256=registration.source_artifact.sha256,
            canonical_logical_hash=canonical.logical_hash,
            rows=rows,
        ),
    )
