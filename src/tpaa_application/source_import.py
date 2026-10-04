"""PIQB B3 production import boundary and exact source-provenance persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from tpaa_ingest.production_source import (
    SourceAdapterRegistry,
    SourceArtifactEnvelope,
    SourceFamily,
)
from tpaa_storage.canonical_rows import CanonicalRowRepository


class ProductionImportError(RuntimeError):
    """Fail-closed production import/provenance error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True)
class SourceProvenanceRecord:
    """Exact logical projection over the DB 1.9 source provenance relations."""

    source_id: str
    session_id: str
    source_family: SourceFamily
    platform_id: str | None
    producer_system: str
    schema_name: str
    schema_version: str
    time_basis: str
    nominal_rate_hz: float | None
    source_quality: float
    classification_label: str | None
    ingest_adapter_id: str
    ingest_adapter_version: str
    source_stream_id: str
    stream_code: str
    ordinal_basis: str
    stream_status: str
    artifact_id: str
    source_artifact_sequence: int
    uri: str
    uri_kind: str
    availability_status: str
    last_verified_at: str | None
    media_type: str
    size_bytes: int
    sha256: str
    mtime_source: str | None
    immutable: bool = True


@dataclass(frozen=True)
class SourceImportCommand:
    """Application command after platform code has identified immutable bytes."""

    source_id: str
    session_id: str
    platform_id: str | None
    producer_system: str
    schema_name: str
    schema_version: str
    time_basis: str
    nominal_rate_hz: float | None
    source_quality: float
    source_stream_id: str
    stream_code: str
    ordinal_basis: str
    stream_status: str
    artifact_id: str
    source_artifact_sequence: int
    uri_kind: str
    availability_status: str
    last_verified_at: str | None
    mtime_source: str | None
    envelope: SourceArtifactEnvelope


_DATA_SOURCE_COLUMNS = (
    "source_id",
    "session_id",
    "source_type",
    "platform_id",
    "producer_system",
    "schema_name",
    "schema_version",
    "time_basis",
    "nominal_rate_hz",
    "source_quality",
    "classification_label",
    "ingest_adapter_id",
    "ingest_adapter_version",
)
_SOURCE_STREAM_COLUMNS = (
    "source_stream_id",
    "source_id",
    "stream_code",
    "ordinal_basis",
    "status",
)
_SOURCE_ARTIFACT_COLUMNS = (
    "artifact_id",
    "source_id",
    "source_stream_id",
    "source_artifact_sequence",
    "uri",
    "uri_kind",
    "availability_status",
    "last_verified_at",
    "media_type",
    "size_bytes",
    "sha256",
    "mtime_source",
    "immutable",
)
_UUID_FIELDS = frozenset(
    {
        "artifact_id",
        "platform_id",
        "session_id",
        "source_id",
        "source_stream_id",
    }
)
_ALLOWED_ORDINAL_BASIS = frozenset(
    {"CAPTURE_MANIFEST", "SOURCE_SEQUENCE", "REVIEWED_IMPORT"}
)
_ALLOWED_STREAM_STATUS = frozenset({"ACTIVE", "CLOSED", "ORDER_UNRESOLVED"})
_ALLOWED_URI_KIND = frozenset({"MANAGED", "EXTERNAL_FILE", "EXTERNAL_OBJECT"})
_ALLOWED_AVAILABILITY = frozenset(
    {"AVAILABLE", "MISSING", "CHANGED", "OFFLINE", "UNKNOWN"}
)


def _time_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        normalized = value
        if normalized.tzinfo is not None:
            normalized = normalized.astimezone(UTC)
        return normalized.isoformat().replace("+00:00", "Z")
    raise ProductionImportError("B3_SOURCE_PROVENANCE_TIME_INVALID", field)


def _float_value(value: object, *, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ProductionImportError("B3_SOURCE_PROVENANCE_NUMERIC_INVALID", field)
    if isinstance(value, (int, float, Decimal, str)):
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ProductionImportError(
                "B3_SOURCE_PROVENANCE_NUMERIC_INVALID",
                field,
            ) from exc
    raise ProductionImportError("B3_SOURCE_PROVENANCE_NUMERIC_INVALID", field)


def _required_float(value: object, *, field: str) -> float:
    result = _float_value(value, field=field)
    if result is None:
        raise ProductionImportError("B3_SOURCE_PROVENANCE_NUMERIC_INVALID", field)
    return result


def _required_int(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise ProductionImportError("B3_SOURCE_PROVENANCE_NUMERIC_INVALID", field)
    if isinstance(value, (int, str)):
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ProductionImportError(
                "B3_SOURCE_PROVENANCE_NUMERIC_INVALID",
                field,
            ) from exc
    raise ProductionImportError("B3_SOURCE_PROVENANCE_NUMERIC_INVALID", field)


def _required_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProductionImportError("B3_SOURCE_PROVENANCE_ROW_INVALID", field)
    return value


def _id_text(value: object, *, field: str, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if isinstance(value, (str, UUID)):
        normalized = str(value)
        if normalized:
            return normalized
    raise ProductionImportError("B3_SOURCE_PROVENANCE_ROW_INVALID", field)


def _bool_value(value: object, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    raise ProductionImportError("B3_SOURCE_PROVENANCE_ROW_INVALID", field)


def _require_nonempty(value: str, *, field: str) -> None:
    if not value or value.strip() != value:
        raise ProductionImportError("B3_SOURCE_IMPORT_COMMAND_INVALID", field)


class SourceProvenanceRepository:
    """Engine-neutral exact mapping over existing DB 1.9 canonical relations."""

    def __init__(self, rows: CanonicalRowRepository) -> None:
        self._rows = rows

    @staticmethod
    def _data_source_values(record: SourceProvenanceRecord) -> dict[str, object]:
        return {
            "source_id": record.source_id,
            "session_id": record.session_id,
            "source_type": record.source_family.value,
            "platform_id": record.platform_id,
            "producer_system": record.producer_system,
            "schema_name": record.schema_name,
            "schema_version": record.schema_version,
            "time_basis": record.time_basis,
            "nominal_rate_hz": record.nominal_rate_hz,
            "source_quality": record.source_quality,
            "classification_label": record.classification_label,
            "ingest_adapter_id": record.ingest_adapter_id,
            "ingest_adapter_version": record.ingest_adapter_version,
        }

    @staticmethod
    def _stream_values(record: SourceProvenanceRecord) -> dict[str, object]:
        return {
            "source_stream_id": record.source_stream_id,
            "source_id": record.source_id,
            "stream_code": record.stream_code,
            "ordinal_basis": record.ordinal_basis,
            "status": record.stream_status,
        }

    @staticmethod
    def _artifact_values(record: SourceProvenanceRecord) -> dict[str, object]:
        return {
            "artifact_id": record.artifact_id,
            "source_id": record.source_id,
            "source_stream_id": record.source_stream_id,
            "source_artifact_sequence": record.source_artifact_sequence,
            "uri": record.uri,
            "uri_kind": record.uri_kind,
            "availability_status": record.availability_status,
            "last_verified_at": record.last_verified_at,
            "media_type": record.media_type,
            "size_bytes": record.size_bytes,
            "sha256": record.sha256,
            "mtime_source": record.mtime_source,
            "immutable": record.immutable,
        }

    @staticmethod
    def _normalize_row(current: dict[str, object]) -> dict[str, object]:
        normalized = dict(current)
        for field in _UUID_FIELDS:
            if field in normalized:
                normalized[field] = _id_text(
                    normalized[field],
                    field=field,
                    optional=field == "platform_id",
                )
        for field in ("last_verified_at", "mtime_source"):
            if field in normalized:
                normalized[field] = _time_text(normalized[field], field=field)
        if "nominal_rate_hz" in normalized:
            normalized["nominal_rate_hz"] = _float_value(
                normalized["nominal_rate_hz"],
                field="nominal_rate_hz",
            )
        if "source_quality" in normalized:
            normalized["source_quality"] = _required_float(
                normalized["source_quality"],
                field="source_quality",
            )
        if "immutable" in normalized:
            normalized["immutable"] = _bool_value(
                normalized["immutable"],
                field="immutable",
            )
        for field in ("source_artifact_sequence", "size_bytes"):
            if field in normalized:
                normalized[field] = _required_int(normalized[field], field=field)
        return normalized

    def _ensure_exact_row(
        self,
        table: str,
        *,
        identity: dict[str, object],
        columns: tuple[str, ...],
        expected: dict[str, object],
        conflict_code: str,
    ) -> bool:
        current = self._rows.one(table, where=identity, columns=columns)
        if current is None:
            return False
        if self._normalize_row(current) != expected:
            raise ProductionImportError(
                conflict_code,
                str(next(iter(identity.values()))),
            )
        return True

    def register(self, record: SourceProvenanceRecord) -> None:
        if not 0.0 <= record.source_quality <= 1.0:
            raise ProductionImportError(
                "B3_SOURCE_QUALITY_INVALID",
                str(record.source_quality),
            )
        if record.source_artifact_sequence < 0 or record.size_bytes < 0:
            raise ProductionImportError(
                "B3_SOURCE_PROVENANCE_NUMERIC_INVALID",
                record.artifact_id,
            )
        if not record.immutable:
            raise ProductionImportError(
                "B3_SOURCE_ARTIFACT_MUTABLE_FORBIDDEN",
                record.artifact_id,
            )

        source_values = self._data_source_values(record)
        if not self._ensure_exact_row(
            "registry.data_source",
            identity={"source_id": record.source_id},
            columns=_DATA_SOURCE_COLUMNS,
            expected=source_values,
            conflict_code="B3_SOURCE_IMMUTABLE_CONFLICT",
        ):
            self._rows.insert("registry.data_source", source_values)

        stream_values = self._stream_values(record)
        if not self._ensure_exact_row(
            "registry.source_stream",
            identity={"source_stream_id": record.source_stream_id},
            columns=_SOURCE_STREAM_COLUMNS,
            expected=stream_values,
            conflict_code="B3_SOURCE_STREAM_IMMUTABLE_CONFLICT",
        ):
            self._rows.insert("registry.source_stream", stream_values)

        artifact_values = self._artifact_values(record)
        if not self._ensure_exact_row(
            "registry.source_artifact",
            identity={"artifact_id": record.artifact_id},
            columns=_SOURCE_ARTIFACT_COLUMNS,
            expected=artifact_values,
            conflict_code="B3_SOURCE_ARTIFACT_IMMUTABLE_CONFLICT",
        ):
            self._rows.insert("registry.source_artifact", artifact_values)

    def exact(self, artifact_id: str) -> SourceProvenanceRecord:
        artifact = self._rows.one(
            "registry.source_artifact",
            where={"artifact_id": artifact_id},
            columns=_SOURCE_ARTIFACT_COLUMNS,
        )
        if artifact is None:
            raise ProductionImportError(
                "B3_SOURCE_ARTIFACT_NOT_FOUND",
                artifact_id,
            )
        source_id = _id_text(artifact.get("source_id"), field="source_id")
        stream_id = _id_text(
            artifact.get("source_stream_id"),
            field="source_stream_id",
        )
        if source_id is None or stream_id is None:
            raise ProductionImportError(
                "B3_SOURCE_PROVENANCE_INCOMPLETE",
                artifact_id,
            )
        source = self._rows.one(
            "registry.data_source",
            where={"source_id": source_id},
            columns=_DATA_SOURCE_COLUMNS,
        )
        stream = self._rows.one(
            "registry.source_stream",
            where={"source_stream_id": stream_id},
            columns=_SOURCE_STREAM_COLUMNS,
        )
        if source is None or stream is None:
            raise ProductionImportError(
                "B3_SOURCE_PROVENANCE_INCOMPLETE",
                artifact_id,
            )
        if _id_text(stream.get("source_id"), field="source_id") != source_id:
            raise ProductionImportError(
                "B3_SOURCE_PROVENANCE_INCOMPLETE",
                artifact_id,
            )
        try:
            family = SourceFamily(
                _required_text(source.get("source_type"), field="source_type")
            )
        except ValueError as exc:
            raise ProductionImportError(
                "B3_SOURCE_FAMILY_NOT_GOVERNED",
                str(source.get("source_type")),
            ) from exc

        session_id = _id_text(source.get("session_id"), field="session_id")
        artifact_identity = _id_text(artifact.get("artifact_id"), field="artifact_id")
        if session_id is None or artifact_identity is None:
            raise ProductionImportError(
                "B3_SOURCE_PROVENANCE_INCOMPLETE",
                artifact_id,
            )
        return SourceProvenanceRecord(
            source_id=source_id,
            session_id=session_id,
            source_family=family,
            platform_id=_id_text(
                source.get("platform_id"),
                field="platform_id",
                optional=True,
            ),
            producer_system=_required_text(
                source.get("producer_system"),
                field="producer_system",
            ),
            schema_name=_required_text(source.get("schema_name"), field="schema_name"),
            schema_version=_required_text(
                source.get("schema_version"),
                field="schema_version",
            ),
            time_basis=_required_text(source.get("time_basis"), field="time_basis"),
            nominal_rate_hz=_float_value(
                source.get("nominal_rate_hz"),
                field="nominal_rate_hz",
            ),
            source_quality=_required_float(
                source.get("source_quality"),
                field="source_quality",
            ),
            classification_label=(
                None
                if source.get("classification_label") is None
                else _required_text(
                    source.get("classification_label"),
                    field="classification_label",
                )
            ),
            ingest_adapter_id=_required_text(
                source.get("ingest_adapter_id"),
                field="ingest_adapter_id",
            ),
            ingest_adapter_version=_required_text(
                source.get("ingest_adapter_version"),
                field="ingest_adapter_version",
            ),
            source_stream_id=stream_id,
            stream_code=_required_text(stream.get("stream_code"), field="stream_code"),
            ordinal_basis=_required_text(
                stream.get("ordinal_basis"),
                field="ordinal_basis",
            ),
            stream_status=_required_text(stream.get("status"), field="status"),
            artifact_id=artifact_identity,
            source_artifact_sequence=_required_int(
                artifact.get("source_artifact_sequence"),
                field="source_artifact_sequence",
            ),
            uri=_required_text(artifact.get("uri"), field="uri"),
            uri_kind=_required_text(artifact.get("uri_kind"), field="uri_kind"),
            availability_status=_required_text(
                artifact.get("availability_status"),
                field="availability_status",
            ),
            last_verified_at=_time_text(
                artifact.get("last_verified_at"),
                field="last_verified_at",
            ),
            media_type=_required_text(artifact.get("media_type"), field="media_type"),
            size_bytes=_required_int(artifact.get("size_bytes"), field="size_bytes"),
            sha256=_required_text(artifact.get("sha256"), field="sha256"),
            mtime_source=_time_text(
                artifact.get("mtime_source"),
                field="mtime_source",
            ),
            immutable=_bool_value(artifact.get("immutable"), field="immutable"),
        )


class ProductionImportService:
    """Application boundary that binds an exact adapter envelope to provenance."""

    def __init__(
        self,
        *,
        adapters: SourceAdapterRegistry,
        provenance: SourceProvenanceRepository,
    ) -> None:
        self._adapters = adapters
        self._provenance = provenance

    @staticmethod
    def _validate_command(command: SourceImportCommand) -> None:
        for field, value in (
            ("source_id", command.source_id),
            ("session_id", command.session_id),
            ("producer_system", command.producer_system),
            ("schema_name", command.schema_name),
            ("schema_version", command.schema_version),
            ("time_basis", command.time_basis),
            ("source_stream_id", command.source_stream_id),
            ("stream_code", command.stream_code),
            ("artifact_id", command.artifact_id),
        ):
            _require_nonempty(value, field=field)
        if command.ordinal_basis not in _ALLOWED_ORDINAL_BASIS:
            raise ProductionImportError(
                "B3_SOURCE_ORDINAL_BASIS_INVALID",
                command.ordinal_basis,
            )
        if command.stream_status not in _ALLOWED_STREAM_STATUS:
            raise ProductionImportError(
                "B3_SOURCE_STREAM_STATUS_INVALID",
                command.stream_status,
            )
        if command.uri_kind not in _ALLOWED_URI_KIND:
            raise ProductionImportError(
                "B3_SOURCE_URI_KIND_INVALID",
                command.uri_kind,
            )
        if command.availability_status not in _ALLOWED_AVAILABILITY:
            raise ProductionImportError(
                "B3_SOURCE_AVAILABILITY_INVALID",
                command.availability_status,
            )

    def register(self, command: SourceImportCommand) -> SourceProvenanceRecord:
        self._validate_command(command)
        envelope = command.envelope
        self._adapters.validate_envelope(envelope)
        record = SourceProvenanceRecord(
            source_id=command.source_id,
            session_id=command.session_id,
            source_family=envelope.source_family,
            platform_id=command.platform_id,
            producer_system=command.producer_system,
            schema_name=command.schema_name,
            schema_version=command.schema_version,
            time_basis=command.time_basis,
            nominal_rate_hz=command.nominal_rate_hz,
            source_quality=command.source_quality,
            classification_label=envelope.classification_label,
            ingest_adapter_id=envelope.adapter_id,
            ingest_adapter_version=envelope.adapter_version,
            source_stream_id=command.source_stream_id,
            stream_code=command.stream_code,
            ordinal_basis=command.ordinal_basis,
            stream_status=command.stream_status,
            artifact_id=command.artifact_id,
            source_artifact_sequence=command.source_artifact_sequence,
            uri=envelope.source_ref,
            uri_kind=command.uri_kind,
            availability_status=command.availability_status,
            last_verified_at=command.last_verified_at,
            media_type=envelope.media_type,
            size_bytes=envelope.size_bytes,
            sha256=envelope.artifact_sha256,
            mtime_source=command.mtime_source,
            immutable=True,
        )
        self._provenance.register(record)
        return record
