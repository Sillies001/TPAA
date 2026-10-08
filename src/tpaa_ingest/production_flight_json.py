"""PRCB C2 production-format FLIGHT source adapter."""

from __future__ import annotations

import hashlib
import json
import math
from typing import cast
from uuid import UUID

from .production_interchange_json import production_interchange_descriptors
from .production_source import (
    ProductionSourceAdapterError,
    SourceAdapterDescriptor,
    SourceAdapterRegistry,
    SourceArtifactEnvelope,
    SourceFamily,
)

PRODUCTION_FLIGHT_SCHEMA = "TPAA_PRODUCTION_FLIGHT_SOURCE_V1"
PRODUCTION_FLIGHT_SCHEMA_VERSION = "1.0.0"
PRODUCTION_FLIGHT_ADAPTER_ID = "tpaa-production-flight-json"
PRODUCTION_FLIGHT_ADAPTER_VERSION = "1.0.0"
PRODUCTION_FLIGHT_MEDIA_TYPE = "application/vnd.tpaa.flight+json"
_REQUIRED_ROW_FIELDS = frozenset(
    {"source_time_us", "p", "nz", "heading", "tas", "mach", "quality"}
)


def _uuid(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ProductionSourceAdapterError("PRCB_SOURCE_DOCUMENT_INVALID", field)
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ProductionSourceAdapterError(
            "PRCB_SOURCE_DOCUMENT_INVALID",
            field,
        ) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise ProductionSourceAdapterError("PRCB_SOURCE_DOCUMENT_INVALID", field)
    return value


def _finite_number(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProductionSourceAdapterError("PRCB_SOURCE_DOCUMENT_INVALID", field)
    result = float(value)
    if not math.isfinite(result):
        raise ProductionSourceAdapterError("PRCB_SOURCE_DOCUMENT_INVALID", field)
    return result


def _optional_number(value: object, *, field: str) -> float | None:
    if value is None:
        return None
    return _finite_number(value, field=field)


def validate_production_flight_document(data: bytes) -> dict[str, object]:
    """Validate one exact production FLIGHT JSON document without format guessing."""

    try:
        raw: object = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProductionSourceAdapterError(
            "PRCB_SOURCE_DOCUMENT_INVALID",
            "json",
        ) from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ProductionSourceAdapterError("PRCB_SOURCE_DOCUMENT_INVALID", "root")
    document = cast(dict[str, object], raw)
    if document.get("schema") != PRODUCTION_FLIGHT_SCHEMA:
        raise ProductionSourceAdapterError(
            "PRCB_SOURCE_SCHEMA_UNSUPPORTED",
            str(document.get("schema")),
        )
    if document.get("schema_version") != PRODUCTION_FLIGHT_SCHEMA_VERSION:
        raise ProductionSourceAdapterError(
            "PRCB_SOURCE_SCHEMA_UNSUPPORTED",
            str(document.get("schema_version")),
        )
    _uuid(document.get("session_id"), field="session_id")
    _uuid(document.get("aircraft_id"), field="aircraft_id")

    transform = document.get("time_transform")
    if not isinstance(transform, dict):
        raise ProductionSourceAdapterError(
            "PRCB_SOURCE_DOCUMENT_INVALID",
            "time_transform",
        )
    scale = _finite_number(transform.get("scale"), field="time_transform.scale")
    offset = transform.get("offset_us")
    if scale <= 0.0 or isinstance(offset, bool) or not isinstance(offset, int):
        raise ProductionSourceAdapterError(
            "PRCB_SOURCE_DOCUMENT_INVALID",
            "time_transform",
        )

    rows = document.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ProductionSourceAdapterError("PRCB_SOURCE_DOCUMENT_INVALID", "rows")
    previous: int | None = None
    for index, item in enumerate(rows):
        if not isinstance(item, dict) or set(item) != _REQUIRED_ROW_FIELDS:
            raise ProductionSourceAdapterError(
                "PRCB_SOURCE_DOCUMENT_INVALID",
                f"rows[{index}]",
            )
        source_time = item.get("source_time_us")
        quality = item.get("quality")
        if (
            isinstance(source_time, bool)
            or not isinstance(source_time, int)
            or (previous is not None and source_time <= previous)
        ):
            raise ProductionSourceAdapterError(
                "PRCB_SOURCE_DOCUMENT_INVALID",
                f"rows[{index}].source_time_us",
            )
        previous = source_time
        if isinstance(quality, bool) or not isinstance(quality, int) or quality < 0:
            raise ProductionSourceAdapterError(
                "PRCB_SOURCE_DOCUMENT_INVALID",
                f"rows[{index}].quality",
            )
        for field in ("p", "nz", "heading", "tas", "mach"):
            _optional_number(item.get(field), field=f"rows[{index}].{field}")
    return document


class ProductionFlightJsonAdapter:
    """Exact adapter for the versioned TPAA production FLIGHT JSON profile."""

    @property
    def descriptor(self) -> SourceAdapterDescriptor:
        return SourceAdapterDescriptor(
            adapter_id=PRODUCTION_FLIGHT_ADAPTER_ID,
            adapter_version=PRODUCTION_FLIGHT_ADAPTER_VERSION,
            source_family=SourceFamily.FLIGHT,
            media_types=(PRODUCTION_FLIGHT_MEDIA_TYPE,),
            external_decoder=False,
        )

    def inspect(
        self,
        *,
        source_ref: str,
        data: bytes,
        media_type: str,
        classification_label: str | None = None,
    ) -> SourceArtifactEnvelope:
        if media_type != PRODUCTION_FLIGHT_MEDIA_TYPE:
            raise ProductionSourceAdapterError(
                "B3_SOURCE_ADAPTER_MEDIA_TYPE_UNSUPPORTED",
                media_type,
            )
        validate_production_flight_document(data)
        if not source_ref.strip():
            raise ProductionSourceAdapterError(
                "B3_SOURCE_ADAPTER_DESCRIPTOR_INVALID",
                "source_ref",
            )
        descriptor = self.descriptor
        return SourceArtifactEnvelope(
            source_family=SourceFamily.FLIGHT,
            adapter_id=descriptor.adapter_id,
            adapter_version=descriptor.adapter_version,
            source_ref=source_ref,
            artifact_sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            media_type=media_type,
            classification_label=classification_label,
        )


def build_production_source_registry() -> SourceAdapterRegistry:
    """Return exact production descriptors for all six frozen source families."""

    flight = ProductionFlightJsonAdapter()
    return SourceAdapterRegistry(
        (flight.descriptor, *production_interchange_descriptors())
    )
