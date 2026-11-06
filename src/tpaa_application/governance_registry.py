"""Governed Context, configuration, and lifecycle registry for W1."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid5

from tpaa_storage import AuditLogWrite, ObjectStore
from tpaa_storage.canonical_rows import CanonicalRowRepository
from tpaa_storage.product_identity import product_object_ref_id

_CONTEXT_NAMESPACE = UUID("17b56120-847a-5d98-8f9b-735ac8e0bc09")
_SNAPSHOT_NAMESPACE = UUID("b692bc09-4b0f-5b41-89d6-72ec39b9a0d8")
_LIFECYCLE_NAMESPACE = UUID("4cfdd68c-e69c-5a79-a350-d82bf927680a")
_CONTEXT_KINDS = {
    "SCENARIO",
    "ASSESSMENT_PROFILE",
    "SYLLABUS",
    "ROLE_MODEL",
    "REFERENCE_SET",
    "RULE_SET",
    "METRIC_PROFILE",
    "LONGITUDINAL_PROFILE",
}


class GovernanceRegistryError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


class _Audit(Protocol):
    def append(self, value: AuditLogWrite) -> None: ...


class _Uow(Protocol):
    canonical_rows: CanonicalRowRepository
    audit_log: _Audit

    def __enter__(self) -> _Uow: ...
    def commit(self) -> None: ...
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...


UowFactory = Callable[[], _Uow]


@dataclass(frozen=True, slots=True)
class ContextArtifactRecord:
    context_artifact_id: str
    artifact_kind: str
    logical_key: str
    artifact_version: str
    object_ref_id: str
    artifact_sha256: str
    schema_version: str
    status: str

    def payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ConfigurationRecord:
    aircraft_configuration_id: str
    aircraft_id: str
    block: str | None
    software_version: str | None
    hardware_baseline: str | None
    sensor_configuration: dict[str, object]
    ew_configuration: dict[str, object]
    weapon_interface_configuration: dict[str, object]
    load_configuration: dict[str, object]
    valid_from: str
    valid_to: str | None
    source_ref: str
    approval_status: str

    def payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ConfigurationSnapshotRecord:
    snapshot_id: str
    aircraft_configuration_id: str
    aircraft_id: str
    session_id: str
    effective_session_time_us: int
    snapshot_json: dict[str, object]
    snapshot_hash: str

    def payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LifecycleEventRecord:
    lifecycle_event_id: str
    aircraft_id: str
    event_type: str
    start_occurred_at_utc: str | None
    end_occurred_at_utc: str | None
    flight_hours_total: float | None
    properties: dict[str, object]
    source_ref: str

    def payload(self) -> dict[str, object]:
        return asdict(self)


def _required(value: str, field: str) -> str:
    if not value or value != value.strip():
        raise GovernanceRegistryError("REGISTRY_TEXT_INVALID", field)
    return value


def _uuid(value: str, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise GovernanceRegistryError("REGISTRY_UUID_INVALID", field) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise GovernanceRegistryError("REGISTRY_UUID_INVALID", field)
    return value


def _json_bytes(value: Mapping[str, object]) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise GovernanceRegistryError("REGISTRY_JSON_INVALID", str(exc)) from exc


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise GovernanceRegistryError("REGISTRY_MAPPING_INVALID", field)
    return dict(value)


def _stored_equal(actual: object, expected: object) -> bool:
    if isinstance(actual, UUID):
        return str(actual) == expected
    if isinstance(actual, datetime) and isinstance(expected, str):
        return actual.astimezone(UTC).isoformat().replace("+00:00", "Z") == expected
    if isinstance(actual, str) and isinstance(expected, Mapping):
        try:
            parsed: object = json.loads(actual)
            return bool(parsed == expected)
        except json.JSONDecodeError:
            return False
    return actual == expected


def _identity(namespace: UUID, value: Mapping[str, object]) -> str:
    return str(uuid5(namespace, _json_bytes(value).decode("ascii")))


def _audit(
    uow: _Uow,
    *,
    action: str,
    object_type: str,
    object_id: str,
    principal_key: str,
    actor_id: str | None,
    request_id: str | None,
    reason: str | None,
    details: dict[str, object],
) -> None:
    uow.audit_log.append(
        AuditLogWrite(
            actor_id=actor_id,
            principal_key=_required(principal_key, "principal_key"),
            action=action,
            object_type=object_type,
            object_id=object_id,
            outcome="SUCCESS",
            request_id=request_id,
            reason=reason,
            details=details,
        )
    )


def _exact(
    rows: CanonicalRowRepository,
    *,
    table: str,
    key: str,
    value: str,
    expected: Mapping[str, object],
    conflict: str,
) -> bool:
    current = rows.one(table, where={key: value}, columns=tuple(expected))
    if current is None:
        return False
    if any(not _stored_equal(current[name], item) for name, item in expected.items()):
        raise GovernanceRegistryError(conflict, value)
    return True


class GovernanceRegistryService:
    """Public application boundary shared by Desktop and Service profiles."""

    def __init__(
        self,
        read_uow: UowFactory,
        write_uow: UowFactory,
        object_store: ObjectStore,
        *,
        storage_backend: str,
    ) -> None:
        self._read_uow = read_uow
        self._write_uow = write_uow
        self._objects = object_store
        self._storage_backend = _required(storage_backend, "storage_backend")

    def publish_context(
        self,
        *,
        artifact_kind: str,
        logical_key: str,
        artifact_version: str,
        schema_version: str,
        payload: Mapping[str, object],
        principal_key: str,
        actor_id: str | None = None,
        request_id: str | None = None,
        reason: str | None = None,
    ) -> ContextArtifactRecord:
        if artifact_kind not in _CONTEXT_KINDS:
            raise GovernanceRegistryError("CONTEXT_KIND_INVALID", artifact_kind)
        logical_key = _required(logical_key, "logical_key")
        artifact_version = _required(artifact_version, "artifact_version")
        schema_version = _required(schema_version, "schema_version")
        data = _json_bytes(payload)
        digest = hashlib.sha256(data).hexdigest()
        identity = {
            "artifact_kind": artifact_kind,
            "logical_key": logical_key,
            "artifact_version": artifact_version,
            "schema_version": schema_version,
            "artifact_sha256": digest,
        }
        artifact_id = _identity(_CONTEXT_NAMESPACE, identity)
        logical_uri = f"tpaa-object://governance-context/{artifact_id}.json"
        stored = self._objects.put_bytes_immutable(logical_uri, data)
        if stored.artifact_sha256 != digest:
            raise GovernanceRegistryError("CONTEXT_OBJECT_HASH_MISMATCH", artifact_id)
        object_id = product_object_ref_id(logical_uri, digest)
        object_values: dict[str, object] = {
            "managed_uri": logical_uri,
            "media_type": "application/json",
            "size_bytes": len(data),
            "artifact_sha256": digest,
            "logical_content_hash": digest,
            "storage_backend": self._storage_backend,
            "sealed": True,
            "gc_state": "ACTIVE",
            "gc_state_version": 0,
            "deleted_at": None,
        }
        artifact_values: dict[str, object] = {
            **identity,
            "object_ref_id": object_id,
            "status": "ACTIVE",
        }
        with self._write_uow() as uow:
            object_replay = _exact(
                uow.canonical_rows,
                table="registry.object_reference",
                key="object_ref_id",
                value=object_id,
                expected=object_values,
                conflict="CONTEXT_OBJECT_IMMUTABLE_CONFLICT",
            )
            if not object_replay:
                uow.canonical_rows.insert(
                    "registry.object_reference",
                    {"object_ref_id": object_id, **object_values},
                )
            replay = _exact(
                uow.canonical_rows,
                table="registry.context_artifact",
                key="context_artifact_id",
                value=artifact_id,
                expected=artifact_values,
                conflict="CONTEXT_ARTIFACT_IMMUTABLE_CONFLICT",
            )
            if not replay:
                uow.canonical_rows.insert(
                    "registry.context_artifact",
                    {"context_artifact_id": artifact_id, **artifact_values},
                )
            _audit(
                uow,
                action="CONTEXT_PUBLISH_REPLAY" if replay else "CONTEXT_PUBLISH",
                object_type="CONTEXT_ARTIFACT",
                object_id=artifact_id,
                principal_key=principal_key,
                actor_id=actor_id,
                request_id=request_id,
                reason=reason,
                details={"artifact_sha256": digest, "exact_replay": replay},
            )
            uow.commit()
        return ContextArtifactRecord(
            context_artifact_id=artifact_id,
            artifact_kind=artifact_kind,
            logical_key=logical_key,
            artifact_version=artifact_version,
            object_ref_id=object_id,
            artifact_sha256=digest,
            schema_version=schema_version,
            status="ACTIVE",
        )

    def retire_context(
        self,
        context_artifact_id: str,
        *,
        principal_key: str,
        reason: str,
        actor_id: str | None = None,
        request_id: str | None = None,
    ) -> ContextArtifactRecord:
        record = self.exact_context(context_artifact_id)
        if record.status != "ACTIVE":
            raise GovernanceRegistryError("CONTEXT_NOT_ACTIVE", record.status)
        with self._write_uow() as uow:
            uow.canonical_rows.update_exact(
                "registry.context_artifact",
                where={"context_artifact_id": record.context_artifact_id, "status": "ACTIVE"},
                values={"status": "RETIRED"},
            )
            _audit(
                uow,
                action="CONTEXT_RETIRE",
                object_type="CONTEXT_ARTIFACT",
                object_id=record.context_artifact_id,
                principal_key=principal_key,
                actor_id=actor_id,
                request_id=request_id,
                reason=_required(reason, "reason"),
                details={"previous_status": "ACTIVE"},
            )
            uow.commit()
        return ContextArtifactRecord(
            context_artifact_id=record.context_artifact_id,
            artifact_kind=record.artifact_kind,
            logical_key=record.logical_key,
            artifact_version=record.artifact_version,
            object_ref_id=record.object_ref_id,
            artifact_sha256=record.artifact_sha256,
            schema_version=record.schema_version,
            status="RETIRED",
        )

    def exact_context(self, context_artifact_id: str) -> ContextArtifactRecord:
        key = _uuid(context_artifact_id, "context_artifact_id")
        columns = tuple(ContextArtifactRecord.__dataclass_fields__)
        with self._read_uow() as uow:
            row = uow.canonical_rows.one(
                "registry.context_artifact", where={"context_artifact_id": key}, columns=columns
            )
        if row is None:
            raise GovernanceRegistryError("CONTEXT_NOT_FOUND", key)
        return ContextArtifactRecord(**{name: str(row[name]) for name in columns})

    def list_contexts(
        self, *, artifact_kind: str, logical_key: str
    ) -> tuple[ContextArtifactRecord, ...]:
        if artifact_kind not in _CONTEXT_KINDS:
            raise GovernanceRegistryError("CONTEXT_KIND_INVALID", artifact_kind)
        columns = tuple(ContextArtifactRecord.__dataclass_fields__)
        with self._read_uow() as uow:
            rows = uow.canonical_rows.many(
                "registry.context_artifact",
                where={"artifact_kind": artifact_kind, "logical_key": logical_key},
                columns=columns,
                order_by=("artifact_version",),
            )
        return tuple(
            ContextArtifactRecord(**{name: str(row[name]) for name in columns}) for row in rows
        )

    def create_configuration(
        self,
        record: ConfigurationRecord,
        *,
        principal_key: str,
        actor_id: str | None = None,
        request_id: str | None = None,
        reason: str | None = None,
    ) -> ConfigurationRecord:
        if record.approval_status != "DRAFT":
            raise GovernanceRegistryError("CONFIGURATION_MUST_START_DRAFT", record.approval_status)
        values = record.payload()
        config_id = _uuid(record.aircraft_configuration_id, "aircraft_configuration_id")
        _uuid(record.aircraft_id, "aircraft_id")
        _uuid(record.source_ref, "source_ref")
        with self._write_uow() as uow:
            replay = _exact(
                uow.canonical_rows,
                table="master.aircraft_configuration",
                key="aircraft_configuration_id",
                value=config_id,
                expected={k: v for k, v in values.items() if k != "aircraft_configuration_id"},
                conflict="CONFIGURATION_IMMUTABLE_CONFLICT",
            )
            if not replay:
                uow.canonical_rows.insert(
                    "master.aircraft_configuration",
                    values,
                    field_kinds={
                        "sensor_configuration": "json",
                        "ew_configuration": "json",
                        "weapon_interface_configuration": "json",
                        "load_configuration": "json",
                    },
                )
            _audit(
                uow,
                action="CONFIGURATION_CREATE_REPLAY" if replay else "CONFIGURATION_CREATE",
                object_type="AIRCRAFT_CONFIGURATION",
                object_id=config_id,
                principal_key=principal_key,
                actor_id=actor_id,
                request_id=request_id,
                reason=reason,
                details={"exact_replay": replay, "aircraft_id": record.aircraft_id},
            )
            uow.commit()
        return record

    def review_configuration(
        self,
        aircraft_configuration_id: str,
        *,
        decision: str,
        principal_key: str,
        reason: str,
        actor_id: str | None = None,
        request_id: str | None = None,
    ) -> ConfigurationRecord:
        if decision not in {"APPROVED", "REJECTED"}:
            raise GovernanceRegistryError("CONFIGURATION_DECISION_INVALID", decision)
        current = self.exact_configuration(aircraft_configuration_id)
        if current.approval_status != "DRAFT":
            raise GovernanceRegistryError("CONFIGURATION_ALREADY_REVIEWED", current.approval_status)
        with self._write_uow() as uow:
            uow.canonical_rows.update_exact(
                "master.aircraft_configuration",
                where={"aircraft_configuration_id": aircraft_configuration_id, "approval_status": "DRAFT"},
                values={"approval_status": decision},
            )
            _audit(
                uow,
                action="CONFIGURATION_REVIEW",
                object_type="AIRCRAFT_CONFIGURATION",
                object_id=aircraft_configuration_id,
                principal_key=principal_key,
                actor_id=actor_id,
                request_id=request_id,
                reason=_required(reason, "reason"),
                details={"decision": decision},
            )
            uow.commit()
        return ConfigurationRecord(
            aircraft_configuration_id=current.aircraft_configuration_id,
            aircraft_id=current.aircraft_id,
            block=current.block,
            software_version=current.software_version,
            hardware_baseline=current.hardware_baseline,
            sensor_configuration=current.sensor_configuration,
            ew_configuration=current.ew_configuration,
            weapon_interface_configuration=current.weapon_interface_configuration,
            load_configuration=current.load_configuration,
            valid_from=current.valid_from,
            valid_to=current.valid_to,
            source_ref=current.source_ref,
            approval_status=decision,
        )

    def exact_configuration(self, aircraft_configuration_id: str) -> ConfigurationRecord:
        key = _uuid(aircraft_configuration_id, "aircraft_configuration_id")
        columns = tuple(ConfigurationRecord.__dataclass_fields__)
        with self._read_uow() as uow:
            row = uow.canonical_rows.one(
                "master.aircraft_configuration",
                where={"aircraft_configuration_id": key},
                columns=columns,
            )
        if row is None:
            raise GovernanceRegistryError("CONFIGURATION_NOT_FOUND", key)
        payload = dict(row)
        for field in (
            "sensor_configuration",
            "ew_configuration",
            "weapon_interface_configuration",
            "load_configuration",
        ):
            raw = payload[field]
            decoded: object = json.loads(raw) if isinstance(raw, str) else raw
            payload[field] = _mapping(decoded, field)
        return ConfigurationRecord(
            aircraft_configuration_id=str(payload["aircraft_configuration_id"]),
            aircraft_id=str(payload["aircraft_id"]),
            block=None if payload["block"] is None else str(payload["block"]),
            software_version=(
                None if payload["software_version"] is None else str(payload["software_version"])
            ),
            hardware_baseline=(
                None if payload["hardware_baseline"] is None else str(payload["hardware_baseline"])
            ),
            sensor_configuration=_mapping(payload["sensor_configuration"], "sensor_configuration"),
            ew_configuration=_mapping(payload["ew_configuration"], "ew_configuration"),
            weapon_interface_configuration=_mapping(
                payload["weapon_interface_configuration"], "weapon_interface_configuration"
            ),
            load_configuration=_mapping(payload["load_configuration"], "load_configuration"),
            valid_from=str(payload["valid_from"]),
            valid_to=None if payload["valid_to"] is None else str(payload["valid_to"]),
            source_ref=str(payload["source_ref"]),
            approval_status=str(payload["approval_status"]),
        )

    def list_configurations(self, aircraft_id: str) -> tuple[ConfigurationRecord, ...]:
        key = _uuid(aircraft_id, "aircraft_id")
        columns = tuple(ConfigurationRecord.__dataclass_fields__)
        with self._read_uow() as uow:
            rows = uow.canonical_rows.many(
                "master.aircraft_configuration",
                where={"aircraft_id": key},
                columns=columns,
                order_by=("valid_from",),
            )
        return tuple(self.exact_configuration(str(row["aircraft_configuration_id"])) for row in rows)

    def snapshot_configuration(
        self,
        aircraft_configuration_id: str,
        *,
        session_id: str,
        effective_session_time_us: int,
        principal_key: str,
        actor_id: str | None = None,
        request_id: str | None = None,
        reason: str | None = None,
    ) -> ConfigurationSnapshotRecord:
        if isinstance(effective_session_time_us, bool) or effective_session_time_us < 0:
            raise GovernanceRegistryError("CONFIGURATION_SNAPSHOT_TIME_INVALID", str(effective_session_time_us))
        _uuid(session_id, "session_id")
        configuration = self.exact_configuration(aircraft_configuration_id)
        if configuration.approval_status != "APPROVED":
            raise GovernanceRegistryError("CONFIGURATION_NOT_APPROVED", configuration.approval_status)
        snapshot_json = configuration.payload()
        snapshot_hash = hashlib.sha256(_json_bytes(snapshot_json)).hexdigest()
        identity = {
            "aircraft_configuration_id": aircraft_configuration_id,
            "session_id": session_id,
            "effective_session_time_us": effective_session_time_us,
            "snapshot_hash": snapshot_hash,
        }
        snapshot_id = _identity(_SNAPSHOT_NAMESPACE, identity)
        values: dict[str, object] = {
            "aircraft_configuration_id": aircraft_configuration_id,
            "aircraft_id": configuration.aircraft_id,
            "session_id": session_id,
            "effective_session_time_us": effective_session_time_us,
            "snapshot_json": snapshot_json,
            "snapshot_hash": snapshot_hash,
        }
        with self._write_uow() as uow:
            replay = _exact(
                uow.canonical_rows,
                table="master.aircraft_configuration_snapshot",
                key="snapshot_id",
                value=snapshot_id,
                expected=values,
                conflict="CONFIGURATION_SNAPSHOT_IMMUTABLE_CONFLICT",
            )
            if not replay:
                uow.canonical_rows.insert(
                    "master.aircraft_configuration_snapshot",
                    {"snapshot_id": snapshot_id, **values},
                    field_kinds={"snapshot_json": "json"},
                )
            _audit(
                uow,
                action="CONFIGURATION_SNAPSHOT_REPLAY" if replay else "CONFIGURATION_SNAPSHOT",
                object_type="AIRCRAFT_CONFIGURATION_SNAPSHOT",
                object_id=snapshot_id,
                principal_key=principal_key,
                actor_id=actor_id,
                request_id=request_id,
                reason=reason,
                details={"exact_replay": replay, "snapshot_hash": snapshot_hash},
            )
            uow.commit()
        return ConfigurationSnapshotRecord(
            snapshot_id=snapshot_id,
            aircraft_configuration_id=aircraft_configuration_id,
            aircraft_id=configuration.aircraft_id,
            session_id=session_id,
            effective_session_time_us=effective_session_time_us,
            snapshot_json=snapshot_json,
            snapshot_hash=snapshot_hash,
        )

    def record_lifecycle_event(
        self,
        *,
        aircraft_id: str,
        event_type: str,
        source_ref: str,
        properties: Mapping[str, object],
        principal_key: str,
        start_occurred_at_utc: str | None = None,
        end_occurred_at_utc: str | None = None,
        flight_hours_total: float | None = None,
        actor_id: str | None = None,
        request_id: str | None = None,
        reason: str | None = None,
    ) -> LifecycleEventRecord:
        _uuid(aircraft_id, "aircraft_id")
        _uuid(source_ref, "source_ref")
        event_type = _required(event_type, "event_type")
        if flight_hours_total is not None and flight_hours_total < 0:
            raise GovernanceRegistryError("LIFECYCLE_FLIGHT_HOURS_INVALID", str(flight_hours_total))
        values: dict[str, object] = {
            "aircraft_id": aircraft_id,
            "event_type": event_type,
            "start_occurred_at_utc": start_occurred_at_utc,
            "end_occurred_at_utc": end_occurred_at_utc,
            "flight_hours_total": flight_hours_total,
            "properties": dict(properties),
            "source_ref": source_ref,
        }
        event_id = _identity(_LIFECYCLE_NAMESPACE, values)
        with self._write_uow() as uow:
            replay = _exact(
                uow.canonical_rows,
                table="master.aircraft_lifecycle_event",
                key="lifecycle_event_id",
                value=event_id,
                expected=values,
                conflict="LIFECYCLE_EVENT_IMMUTABLE_CONFLICT",
            )
            if not replay:
                uow.canonical_rows.insert(
                    "master.aircraft_lifecycle_event",
                    {"lifecycle_event_id": event_id, **values},
                    field_kinds={"properties": "json"},
                )
            _audit(
                uow,
                action="LIFECYCLE_EVENT_REPLAY" if replay else "LIFECYCLE_EVENT_RECORD",
                object_type="AIRCRAFT_LIFECYCLE_EVENT",
                object_id=event_id,
                principal_key=principal_key,
                actor_id=actor_id,
                request_id=request_id,
                reason=reason,
                details={"exact_replay": replay, "event_type": event_type},
            )
            uow.commit()
        return LifecycleEventRecord(
            lifecycle_event_id=event_id,
            aircraft_id=aircraft_id,
            event_type=event_type,
            start_occurred_at_utc=start_occurred_at_utc,
            end_occurred_at_utc=end_occurred_at_utc,
            flight_hours_total=flight_hours_total,
            properties=dict(properties),
            source_ref=source_ref,
        )

    def list_lifecycle_events(self, aircraft_id: str) -> tuple[LifecycleEventRecord, ...]:
        key = _uuid(aircraft_id, "aircraft_id")
        columns = tuple(LifecycleEventRecord.__dataclass_fields__)
        with self._read_uow() as uow:
            rows = uow.canonical_rows.many(
                "master.aircraft_lifecycle_event",
                where={"aircraft_id": key},
                columns=columns,
                order_by=("start_occurred_at_utc", "lifecycle_event_id"),
            )
        records: list[LifecycleEventRecord] = []
        for row in rows:
            payload = dict(row)
            payload["properties"] = _mapping(
                json.loads(payload["properties"])
                if isinstance(payload["properties"], str)
                else payload["properties"],
                "properties",
            )
            for field in ("lifecycle_event_id", "aircraft_id", "event_type", "source_ref"):
                payload[field] = str(payload[field])
            for field in ("start_occurred_at_utc", "end_occurred_at_utc"):
                payload[field] = None if payload[field] is None else str(payload[field])
            records.append(
                LifecycleEventRecord(
                    lifecycle_event_id=str(payload["lifecycle_event_id"]),
                    aircraft_id=str(payload["aircraft_id"]),
                    event_type=str(payload["event_type"]),
                    start_occurred_at_utc=(
                        None
                        if payload["start_occurred_at_utc"] is None
                        else str(payload["start_occurred_at_utc"])
                    ),
                    end_occurred_at_utc=(
                        None
                        if payload["end_occurred_at_utc"] is None
                        else str(payload["end_occurred_at_utc"])
                    ),
                    flight_hours_total=(
                        None
                        if payload["flight_hours_total"] is None
                        else float(str(payload["flight_hours_total"]))
                    ),
                    properties=_mapping(payload["properties"], "properties"),
                    source_ref=str(payload["source_ref"]),
                )
            )
        return tuple(records)


__all__ = [
    "ConfigurationRecord",
    "ConfigurationSnapshotRecord",
    "ContextArtifactRecord",
    "GovernanceRegistryError",
    "GovernanceRegistryService",
    "LifecycleEventRecord",
]
