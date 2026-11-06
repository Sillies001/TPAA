"""W2 Source inspect/validate/stage/canonicalize application boundary."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from tpaa_ingest import (
    FLIGHT_RECORDER_CSV_ADAPTER_ID,
    FLIGHT_RECORDER_CSV_ADAPTER_VERSION,
    FLIGHT_RECORDER_CSV_MEDIA_TYPE,
    PRODUCTION_FLIGHT_ADAPTER_ID,
    PRODUCTION_FLIGHT_ADAPTER_VERSION,
    PRODUCTION_FLIGHT_MEDIA_TYPE,
    PRODUCTION_FLIGHT_SCHEMA,
    PRODUCTION_FLIGHT_SCHEMA_VERSION,
    FlightRecorderCsvProfile,
    ProductionSourceAdapterError,
    SourceFamily,
    build_production_source_registry,
    normalize_flight_recorder_csv,
)
from tpaa_storage import ObjectStore, ObjectStoreError

SOURCE_RAW_NAMESPACE = "source-raw"
SOURCE_STREAM_CHUNK_BYTES = 1024 * 1024
SOURCE_MAX_ARTIFACT_BYTES = 64 * 1024 * 1024


class SourceWorkflowError(RuntimeError):
    """Transport-safe fail-closed W2 Source workflow error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


class CancellationProbe(Protocol):
    def __call__(self) -> bool: ...


def bounded_source_bytes(
    chunks: Iterable[bytes],
    *,
    cancelled: CancellationProbe | None = None,
    max_bytes: int = SOURCE_MAX_ARTIFACT_BYTES,
) -> bytes:
    """Consume bounded chunks with cooperative cancellation and no silent truncation."""

    if max_bytes <= 0 or max_bytes > SOURCE_MAX_ARTIFACT_BYTES:
        raise SourceWorkflowError("W2_SOURCE_LIMIT_INVALID", str(max_bytes))
    payload = bytearray()
    for index, chunk in enumerate(chunks):
        if cancelled is not None and cancelled():
            raise SourceWorkflowError("W2_SOURCE_IMPORT_CANCELLED", str(index))
        if not isinstance(chunk, bytes) or not chunk:
            raise SourceWorkflowError("W2_SOURCE_CHUNK_INVALID", str(index))
        if len(chunk) > SOURCE_STREAM_CHUNK_BYTES:
            raise SourceWorkflowError("W2_SOURCE_CHUNK_TOO_LARGE", str(len(chunk)))
        payload.extend(chunk)
        if len(payload) > max_bytes:
            raise SourceWorkflowError("SOURCE_ARTIFACT_SIZE_INVALID", str(len(payload)))
    if not payload:
        raise SourceWorkflowError("W2_SOURCE_EMPTY", "0")
    return bytes(payload)


def _uuid(value: str, *, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise SourceWorkflowError("W2_SOURCE_ID_INVALID", field) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise SourceWorkflowError("W2_SOURCE_ID_INVALID", field)
    return value


def _text(value: str, *, field: str) -> str:
    if not value or value.strip() != value:
        raise SourceWorkflowError("W2_SOURCE_FIELD_INVALID", field)
    return value


def _raw_uri(artifact_id: str) -> str:
    return f"tpaa-object://{SOURCE_RAW_NAMESPACE}/{artifact_id}/source.csv"


def _canonical_uri(artifact_id: str) -> str:
    return f"tpaa-object://source-ingress/{artifact_id}/source.json"


class SourceWorkflowService:
    """Application service for a reviewable Source-to-Canonical ingress sequence."""

    def __init__(self, object_store: ObjectStore) -> None:
        self._store = object_store
        self._registry = build_production_source_registry()

    def adapter_registry(self) -> dict[str, object]:
        return {
            "schema": "TPAA_SOURCE_ADAPTER_REGISTRY_V1",
            "items": [
                {
                    "adapter_id": item.adapter_id,
                    "adapter_version": item.adapter_version,
                    "source_family": item.source_family.value,
                    "media_types": list(item.media_types),
                    "external_decoder": item.external_decoder,
                }
                for item in self._registry.inventory()
            ],
        }

    def stage_p1_request_manifest(self, data: bytes) -> dict[str, object]:
        """Stage inline source documents from one governed P1 request manifest.

        The method deliberately performs only ingress work: JSON shape checks,
        immutable byte storage, and reference replacement.  The production P1
        worker remains the sole authority for Catalog membership, identities,
        metric inputs, and publication eligibility.
        """

        if not data or len(data) > SOURCE_MAX_ARTIFACT_BYTES:
            raise SourceWorkflowError("SOURCE_ARTIFACT_SIZE_INVALID", str(len(data)))
        try:
            decoded = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceWorkflowError("W5_P1_MANIFEST_JSON_INVALID", str(exc)) from exc
        if not isinstance(decoded, dict) or not all(
            isinstance(key, str) for key in decoded
        ):
            raise SourceWorkflowError("W5_P1_MANIFEST_ROOT_INVALID", "root")
        if decoded.get("schema") != "TPAA_ED2_B1_FULL_P1_REQUEST_CONTRACT_V1":
            raise SourceWorkflowError("W5_P1_MANIFEST_SCHEMA_INVALID", "schema")
        raw_documents = decoded.get("source_documents")
        if not isinstance(raw_documents, list) or not raw_documents:
            raise SourceWorkflowError(
                "W5_P1_MANIFEST_SOURCE_DOCUMENTS_INVALID",
                "source_documents",
            )

        staged_documents: list[dict[str, object]] = []
        families: list[str] = []
        for index, raw in enumerate(raw_documents):
            field = f"source_documents[{index}]"
            if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
                raise SourceWorkflowError("W5_P1_MANIFEST_DOCUMENT_INVALID", field)
            item = dict(raw)
            source_json = item.pop("source_json", None)
            if not isinstance(source_json, str) or not source_json:
                raise SourceWorkflowError("W5_P1_MANIFEST_INLINE_SOURCE_REQUIRED", field)
            metadata = item.get("source_import")
            if not isinstance(metadata, dict):
                raise SourceWorkflowError(
                    "W5_P1_MANIFEST_SOURCE_IMPORT_INVALID",
                    field,
                )
            source_import = dict(metadata)
            artifact_id = source_import.get("artifact_id")
            if not isinstance(artifact_id, str):
                raise SourceWorkflowError("W5_P1_MANIFEST_ARTIFACT_ID_INVALID", field)
            _uuid(artifact_id, field=f"{field}.artifact_id")
            family = source_import.get("source_family")
            if not isinstance(family, str) or not family:
                raise SourceWorkflowError("W5_P1_MANIFEST_SOURCE_FAMILY_INVALID", field)
            source_bytes = source_json.encode("utf-8")
            if len(source_bytes) > SOURCE_MAX_ARTIFACT_BYTES:
                raise SourceWorkflowError(
                    "SOURCE_ARTIFACT_SIZE_INVALID",
                    f"{field}:{len(source_bytes)}",
                )
            try:
                stored = self._store.put_bytes_immutable(
                    _canonical_uri(artifact_id),
                    source_bytes,
                )
            except ObjectStoreError as exc:
                raise SourceWorkflowError("W5_P1_MANIFEST_STAGE_FAILED", field) from exc
            source_import["uri_kind"] = "MANAGED"
            source_import["source_ref"] = stored.logical_uri
            item["source_import"] = source_import
            item["source_artifact"] = {
                "logical_uri": stored.logical_uri,
                "artifact_sha256": stored.artifact_sha256,
                "byte_size": stored.byte_size,
            }
            staged_documents.append(item)
            families.append(family)

        payload = dict(decoded)
        payload["source_documents"] = staged_documents
        return {
            "status": "STAGED",
            "schema": "TPAA_W5_P1_REQUEST_STAGE_V1",
            "source_document_count": len(staged_documents),
            "source_families": families,
            "payload": payload,
        }

    def inspect_flight_csv(
        self,
        data: bytes,
        *,
        session_id: str,
        aircraft_id: str,
        source_ref: str,
    ) -> dict[str, object]:
        _text(source_ref, field="source_ref")
        profile = FlightRecorderCsvProfile(
            session_id=session_id,
            aircraft_id=aircraft_id,
        )
        try:
            normalized = normalize_flight_recorder_csv(data, profile=profile)
        except ProductionSourceAdapterError as exc:
            raise SourceWorkflowError(exc.code, exc.detail) from exc
        return {
            "status": "VALID",
            "source_family": SourceFamily.FLIGHT.value,
            "source_ref": source_ref,
            "adapter_id": FLIGHT_RECORDER_CSV_ADAPTER_ID,
            "adapter_version": FLIGHT_RECORDER_CSV_ADAPTER_VERSION,
            "media_type": FLIGHT_RECORDER_CSV_MEDIA_TYPE,
            "inspection": asdict(normalized.inspection),
            "profiles": {
                "time": profile.time_profile_id,
                "reference_frame": profile.reference_frame_profile_id,
                "unit": profile.unit_profile_id,
                "association": profile.association_profile_id,
            },
            "canonical_schema": PRODUCTION_FLIGHT_SCHEMA,
            "canonical_schema_version": PRODUCTION_FLIGHT_SCHEMA_VERSION,
        }

    def stage_flight_csv(
        self,
        data: bytes,
        *,
        session_id: str,
        aircraft_id: str,
        source_ref: str,
        raw_artifact_id: str,
        canonical_artifact_id: str,
        source_id: str,
        source_stream_id: str,
        producer_system: str,
        session_code: str,
        session_type: str,
        classification_label: str | None = None,
        nominal_rate_hz: float | None = None,
        verified_at: datetime | None = None,
    ) -> dict[str, object]:
        """Validate, canonicalize and immutably stage raw and normalized bytes."""

        profile = FlightRecorderCsvProfile(
            session_id=session_id,
            aircraft_id=aircraft_id,
        )

        for field, value in (
            ("raw_artifact_id", raw_artifact_id),
            ("canonical_artifact_id", canonical_artifact_id),
            ("source_id", source_id),
            ("source_stream_id", source_stream_id),
        ):
            _uuid(value, field=field)
        _text(source_ref, field="source_ref")
        _text(producer_system, field="producer_system")
        _text(session_code, field="session_code")
        if session_type not in {"LIVE", "SIM", "LVC"}:
            raise SourceWorkflowError("W2_SOURCE_SESSION_TYPE_INVALID", session_type)
        if nominal_rate_hz is not None and nominal_rate_hz <= 0.0:
            raise SourceWorkflowError("W2_SOURCE_RATE_INVALID", str(nominal_rate_hz))
        if classification_label is not None:
            _text(classification_label, field="classification_label")

        try:
            normalized = normalize_flight_recorder_csv(data, profile=profile)
            raw_stored = self._store.put_bytes_immutable(_raw_uri(raw_artifact_id), data)
            canonical_stored = self._store.put_bytes_immutable(
                _canonical_uri(canonical_artifact_id),
                normalized.production_bytes,
            )
        except ProductionSourceAdapterError as exc:
            raise SourceWorkflowError(exc.code, exc.detail) from exc
        except ObjectStoreError as exc:
            raise SourceWorkflowError("W2_SOURCE_STAGE_FAILED", str(exc)) from exc

        timestamp = verified_at or datetime.now(UTC)
        verified = timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z")
        source_import: dict[str, object] = {
            "source_family": SourceFamily.FLIGHT.value,
            "source_id": source_id,
            "session_id": profile.session_id,
            "platform_id": None,
            "producer_system": producer_system,
            "schema_name": PRODUCTION_FLIGHT_SCHEMA,
            "schema_version": PRODUCTION_FLIGHT_SCHEMA_VERSION,
            "time_basis": "SESSION_US_EXPLICIT",
            "nominal_rate_hz": (
                None if nominal_rate_hz is None else format(nominal_rate_hz, ".17g")
            ),
            "source_quality": "1.0",
            "source_stream_id": source_stream_id,
            "stream_code": "FLIGHT_PRIMARY",
            "ordinal_basis": "SOURCE_SEQUENCE",
            "stream_status": "ACTIVE",
            "artifact_id": canonical_artifact_id,
            "source_artifact_sequence": 0,
            "uri_kind": "MANAGED",
            "availability_status": "AVAILABLE",
            "last_verified_at": verified,
            "mtime_source": None,
            "source_ref": canonical_stored.logical_uri,
            "media_type": PRODUCTION_FLIGHT_MEDIA_TYPE,
            "classification_label": classification_label,
            "session_code": session_code,
            "session_type": session_type,
            "ingress_adapter_id": FLIGHT_RECORDER_CSV_ADAPTER_ID,
            "ingress_adapter_version": FLIGHT_RECORDER_CSV_ADAPTER_VERSION,
            "canonical_adapter_id": PRODUCTION_FLIGHT_ADAPTER_ID,
            "canonical_adapter_version": PRODUCTION_FLIGHT_ADAPTER_VERSION,
        }
        return {
            "status": "STAGED",
            "inspection": asdict(normalized.inspection),
            "raw_artifact": {
                "artifact_id": raw_artifact_id,
                "logical_uri": raw_stored.logical_uri,
                "artifact_sha256": raw_stored.artifact_sha256,
                "byte_size": raw_stored.byte_size,
            },
            "source_document": {
                "source_import": source_import,
                "source_artifact": {
                    "logical_uri": canonical_stored.logical_uri,
                    "artifact_sha256": canonical_stored.artifact_sha256,
                    "byte_size": canonical_stored.byte_size,
                },
                "raw_source_lineage": {
                    "artifact_id": raw_artifact_id,
                    "logical_uri": raw_stored.logical_uri,
                    "artifact_sha256": hashlib.sha256(data).hexdigest(),
                    "byte_size": len(data),
                },
            },
        }
