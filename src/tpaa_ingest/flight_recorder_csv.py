"""Governed UTF-8 CSV adapter for de-identified flight-recorder exports.

The profile is intentionally narrow: it defines physical columns and units,
keeps physical row order, records source-clock resets before normalization and
requires an explicit monotonic Session Time column.  It never guesses a clock,
aircraft association, reference frame or unit.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from .production_flight_json import (
    PRODUCTION_FLIGHT_SCHEMA,
    PRODUCTION_FLIGHT_SCHEMA_VERSION,
    validate_production_flight_document,
)
from .production_source import (
    ProductionSourceAdapterError,
    SourceAdapterDescriptor,
    SourceArtifactEnvelope,
    SourceFamily,
)

FLIGHT_RECORDER_CSV_ADAPTER_ID = "tpaa-flight-recorder-csv"
FLIGHT_RECORDER_CSV_ADAPTER_VERSION = "1.0.0"
FLIGHT_RECORDER_CSV_MEDIA_TYPE = "text/csv"
FLIGHT_RECORDER_CSV_PROFILE_ID = "TPAA_FLIGHT_RECORDER_CSV_V1"
FLIGHT_RECORDER_CSV_MAPPING_VERSION = "1.0.0"
FLIGHT_RECORDER_TIME_PROFILE = "EXPLICIT_SESSION_TIME_V1"
FLIGHT_RECORDER_REFERENCE_FRAME = "BODY_NED_TRUE_V1"
FLIGHT_RECORDER_UNIT_PROFILE = "DEG_KNOT_SI_NORMALIZATION_V1"
FLIGHT_RECORDER_ASSOCIATION_PROFILE = "EXPLICIT_AIRCRAFT_UUID_V1"

_HEADERS = (
    "source_time_us",
    "session_time_us",
    "p_deg_s",
    "nz_g",
    "heading_deg_true",
    "tas_kt",
    "mach",
    "quality_mask",
)
_KNOT_TO_MPS = 0.514444


@dataclass(frozen=True, slots=True)
class FlightRecorderCsvProfile:
    """Frozen identities required before source-specific data is interpreted."""

    session_id: str
    aircraft_id: str
    time_profile_id: str = FLIGHT_RECORDER_TIME_PROFILE
    reference_frame_profile_id: str = FLIGHT_RECORDER_REFERENCE_FRAME
    unit_profile_id: str = FLIGHT_RECORDER_UNIT_PROFILE
    association_profile_id: str = FLIGHT_RECORDER_ASSOCIATION_PROFILE

    def validate(self) -> None:
        for field, value in (
            ("session_id", self.session_id),
            ("aircraft_id", self.aircraft_id),
        ):
            try:
                parsed = UUID(value)
            except ValueError as exc:
                raise ProductionSourceAdapterError(
                    "W2_FLIGHT_CSV_PROFILE_INVALID", field
                ) from exc
            if parsed.int == 0 or str(parsed) != value:
                raise ProductionSourceAdapterError(
                    "W2_FLIGHT_CSV_PROFILE_INVALID", field
                )
        expected = (
            ("time_profile_id", self.time_profile_id, FLIGHT_RECORDER_TIME_PROFILE),
            (
                "reference_frame_profile_id",
                self.reference_frame_profile_id,
                FLIGHT_RECORDER_REFERENCE_FRAME,
            ),
            ("unit_profile_id", self.unit_profile_id, FLIGHT_RECORDER_UNIT_PROFILE),
            (
                "association_profile_id",
                self.association_profile_id,
                FLIGHT_RECORDER_ASSOCIATION_PROFILE,
            ),
        )
        for field, actual, authority in expected:
            if actual != authority:
                raise ProductionSourceAdapterError(
                    "W2_FLIGHT_CSV_PROFILE_UNSUPPORTED", f"{field}={actual}"
                )


@dataclass(frozen=True, slots=True)
class FlightRecorderCsvInspection:
    row_count: int
    clock_segment_count: int
    start_session_time_us: int
    end_session_time_us: int
    missing_value_counts: dict[str, int]
    source_sha256: str
    mapping_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class NormalizedFlightRecorderCsv:
    inspection: FlightRecorderCsvInspection
    production_document: dict[str, object]
    production_bytes: bytes


def _integer(value: str, *, field: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise ProductionSourceAdapterError("W2_FLIGHT_CSV_ROW_INVALID", field) from exc
    if str(result) != value.strip():
        raise ProductionSourceAdapterError("W2_FLIGHT_CSV_ROW_INVALID", field)
    return result


def _number(value: str, *, field: str, optional: bool = True) -> float | None:
    if not value.strip() and optional:
        return None
    try:
        result = float(value)
    except ValueError as exc:
        raise ProductionSourceAdapterError("W2_FLIGHT_CSV_ROW_INVALID", field) from exc
    if not math.isfinite(result):
        raise ProductionSourceAdapterError("W2_FLIGHT_CSV_ROW_INVALID", field)
    return result


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def normalize_flight_recorder_csv(
    data: bytes,
    *,
    profile: FlightRecorderCsvProfile,
) -> NormalizedFlightRecorderCsv:
    """Normalize an exact CSV artifact without reordering or implicit inference."""

    profile.validate()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ProductionSourceAdapterError(
            "W2_FLIGHT_CSV_ENCODING_INVALID", "UTF-8"
        ) from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if tuple(reader.fieldnames or ()) != _HEADERS:
        raise ProductionSourceAdapterError(
            "W2_FLIGHT_CSV_SCHEMA_UNSUPPORTED", repr(reader.fieldnames)
        )

    rows: list[dict[str, object]] = []
    missing = {name: 0 for name in ("p", "nz", "heading", "tas", "mach")}
    previous_source: int | None = None
    previous_session: int | None = None
    first_session: int | None = None
    clock_segment = 0
    segment_starts = [0]
    for physical_ordinal, raw in enumerate(reader, start=0):
        if None in raw or set(raw) != set(_HEADERS):
            raise ProductionSourceAdapterError(
                "W2_FLIGHT_CSV_ROW_INVALID", f"row={physical_ordinal + 2}:shape"
            )
        source_time = _integer(
            cast(str, raw["source_time_us"]),
            field=f"row={physical_ordinal + 2}:source_time_us",
        )
        session_time = _integer(
            cast(str, raw["session_time_us"]),
            field=f"row={physical_ordinal + 2}:session_time_us",
        )
        if previous_source is not None and source_time <= previous_source:
            clock_segment += 1
            segment_starts.append(physical_ordinal)
        if previous_session is not None and session_time <= previous_session:
            raise ProductionSourceAdapterError(
                "W2_FLIGHT_CSV_SESSION_TIME_INVALID",
                f"row={physical_ordinal + 2}",
            )
        if first_session is None:
            first_session = session_time

        p_deg_s = _number(
            cast(str, raw["p_deg_s"]), field=f"row={physical_ordinal + 2}:p_deg_s"
        )
        nz_g = _number(cast(str, raw["nz_g"]), field=f"row={physical_ordinal + 2}:nz_g")
        heading_deg = _number(
            cast(str, raw["heading_deg_true"]),
            field=f"row={physical_ordinal + 2}:heading_deg_true",
        )
        tas_kt = _number(
            cast(str, raw["tas_kt"]), field=f"row={physical_ordinal + 2}:tas_kt"
        )
        mach = _number(cast(str, raw["mach"]), field=f"row={physical_ordinal + 2}:mach")
        quality = _integer(
            cast(str, raw["quality_mask"]),
            field=f"row={physical_ordinal + 2}:quality_mask",
        )
        if quality < 0:
            raise ProductionSourceAdapterError(
                "W2_FLIGHT_CSV_ROW_INVALID", f"row={physical_ordinal + 2}:quality_mask"
            )
        if heading_deg is not None and not 0.0 <= heading_deg < 360.0:
            raise ProductionSourceAdapterError(
                "W2_FLIGHT_CSV_ROW_INVALID",
                f"row={physical_ordinal + 2}:heading_deg_true",
            )
        if tas_kt is not None and tas_kt < 0.0:
            raise ProductionSourceAdapterError(
                "W2_FLIGHT_CSV_ROW_INVALID", f"row={physical_ordinal + 2}:tas_kt"
            )
        if mach is not None and mach < 0.0:
            raise ProductionSourceAdapterError(
                "W2_FLIGHT_CSV_ROW_INVALID", f"row={physical_ordinal + 2}:mach"
            )

        values = {
            "p": None if p_deg_s is None else math.radians(p_deg_s),
            "nz": nz_g,
            "heading": None if heading_deg is None else math.radians(heading_deg),
            "tas": None if tas_kt is None else tas_kt * _KNOT_TO_MPS,
            "mach": mach,
        }
        for name, value in values.items():
            if value is None:
                missing[name] += 1
        rows.append(
            {
                "source_time_us": session_time,
                **values,
                "quality": quality,
                "source_row_ordinal": physical_ordinal,
                "source_clock_segment": clock_segment,
            }
        )
        previous_source = source_time
        previous_session = session_time

    if not rows or first_session is None or previous_session is None:
        raise ProductionSourceAdapterError("W2_FLIGHT_CSV_ROW_INVALID", "no rows")

    source_sha256 = hashlib.sha256(data).hexdigest()
    mapping_manifest = {
        "profile_id": FLIGHT_RECORDER_CSV_PROFILE_ID,
        "mapping_version": FLIGHT_RECORDER_CSV_MAPPING_VERSION,
        "adapter_id": FLIGHT_RECORDER_CSV_ADAPTER_ID,
        "adapter_version": FLIGHT_RECORDER_CSV_ADAPTER_VERSION,
        "source_artifact_sha256": source_sha256,
        "physical_order_preserved": True,
        "source_clock_segment_starts": segment_starts,
        "time_profile_id": profile.time_profile_id,
        "reference_frame_profile_id": profile.reference_frame_profile_id,
        "unit_profile_id": profile.unit_profile_id,
        "association_profile_id": profile.association_profile_id,
        "unit_mappings": {
            "p_deg_s": "body_p_rad_s",
            "nz_g": "nz_g",
            "heading_deg_true": "heading_true_rad",
            "tas_kt": "tas_mps",
            "mach": "mach",
        },
    }
    manifest_hash = hashlib.sha256(_canonical_bytes(mapping_manifest)).hexdigest()
    document: dict[str, object] = {
        "schema": PRODUCTION_FLIGHT_SCHEMA,
        "schema_version": PRODUCTION_FLIGHT_SCHEMA_VERSION,
        "session_id": profile.session_id,
        "aircraft_id": profile.aircraft_id,
        "time_transform": {"scale": 1.0, "offset_us": 0},
        "rows": rows,
        "source_profile": {
            "profile_id": FLIGHT_RECORDER_CSV_PROFILE_ID,
            "mapping_manifest": mapping_manifest,
            "mapping_manifest_sha256": manifest_hash,
        },
    }
    production_bytes = _canonical_bytes(document)
    validate_production_flight_document(production_bytes)
    inspection = FlightRecorderCsvInspection(
        row_count=len(rows),
        clock_segment_count=clock_segment + 1,
        start_session_time_us=first_session,
        end_session_time_us=previous_session,
        missing_value_counts=missing,
        source_sha256=source_sha256,
        mapping_manifest_sha256=manifest_hash,
    )
    return NormalizedFlightRecorderCsv(
        inspection=inspection,
        production_document=document,
        production_bytes=production_bytes,
    )


class FlightRecorderCsvAdapter:
    """Explicit adapter for the W2 governed flight-recorder CSV profile."""

    @property
    def descriptor(self) -> SourceAdapterDescriptor:
        return SourceAdapterDescriptor(
            adapter_id=FLIGHT_RECORDER_CSV_ADAPTER_ID,
            adapter_version=FLIGHT_RECORDER_CSV_ADAPTER_VERSION,
            source_family=SourceFamily.FLIGHT,
            media_types=(FLIGHT_RECORDER_CSV_MEDIA_TYPE,),
            external_decoder=False,
        )

    def inspect(
        self,
        *,
        source_ref: str,
        data: bytes,
        media_type: str,
        classification_label: str | None = None,
        profile: FlightRecorderCsvProfile | None = None,
    ) -> SourceArtifactEnvelope:
        if media_type != FLIGHT_RECORDER_CSV_MEDIA_TYPE:
            raise ProductionSourceAdapterError(
                "B3_SOURCE_ADAPTER_MEDIA_TYPE_UNSUPPORTED", media_type
            )
        if profile is None:
            raise ProductionSourceAdapterError(
                "W2_FLIGHT_CSV_PROFILE_REQUIRED", "profile"
            )
        normalize_flight_recorder_csv(data, profile=profile)
        if not source_ref or source_ref.strip() != source_ref:
            raise ProductionSourceAdapterError(
                "B3_SOURCE_ADAPTER_DESCRIPTOR_INVALID", "source_ref"
            )
        return SourceArtifactEnvelope(
            source_family=SourceFamily.FLIGHT,
            adapter_id=FLIGHT_RECORDER_CSV_ADAPTER_ID,
            adapter_version=FLIGHT_RECORDER_CSV_ADAPTER_VERSION,
            source_ref=source_ref,
            artifact_sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            media_type=media_type,
            classification_label=classification_label,
        )
