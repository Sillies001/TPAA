"""Engine-neutral governed Release lifecycle management for W1."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from tpaa_storage import AuditLogWrite
from tpaa_storage.canonical_rows import CanonicalRowRepository


class ReleaseManagementError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class ManagedRelease:
    release_id: str
    scope_type: str
    scope_key: str
    release_no: int
    status: str
    parent_release_id: str | None
    manifest_hash: str
    created_at: str
    published_at: str | None
    current: bool

    def payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReleaseLifecycleReceipt:
    release_id: str
    action: str
    status: str
    scope_type: str
    scope_key: str
    current_release_id: str | None
    version_token: int
    changed_at_utc: str

    def payload(self) -> dict[str, object]:
        return asdict(self)


class _Audit(Protocol):
    def append(self, value: AuditLogWrite) -> None: ...


class _Uow(Protocol):
    canonical_rows: CanonicalRowRepository
    audit_log: _Audit

    def __enter__(self) -> _Uow: ...
    def commit(self) -> None: ...
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...


UowFactory = Callable[[], _Uow]

_RELEASE_COLUMNS = (
    "release_id",
    "scope_type",
    "scope_key",
    "release_no",
    "status",
    "parent_release_id",
    "manifest_hash",
    "created_at",
    "published_at",
)


def _uuid(value: str, *, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ReleaseManagementError("RELEASE_UUID_INVALID", field) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise ReleaseManagementError("RELEASE_UUID_INVALID", field)
    return value


def _required(value: str, *, field: str) -> str:
    if not value or value != value.strip():
        raise ReleaseManagementError("RELEASE_TEXT_INVALID", field)
    return value


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReleaseManagementError("RELEASE_INTEGER_INVALID", field)
    return value


def _time(value: object) -> str:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, str) and value:
        return value
    raise ReleaseManagementError("RELEASE_TIME_INVALID", type(value).__name__)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


class ReleaseManagementService:
    """List and transition releases without changing immutable release content."""

    def __init__(self, read_uow: UowFactory, write_uow: UowFactory) -> None:
        self._read_uow = read_uow
        self._write_uow = write_uow

    @staticmethod
    def _pointer(
        rows: CanonicalRowRepository,
        scope_type: str,
        scope_key: str,
    ) -> tuple[str | None, int]:
        pointer = rows.one(
            "registry.release_scope_pointer",
            where={"scope_type": scope_type, "scope_key": scope_key},
            columns=("current_release_id", "version_token"),
        )
        if pointer is None:
            raise ReleaseManagementError("RELEASE_POINTER_NOT_FOUND", scope_key)
        current = pointer["current_release_id"]
        return (
            None if current is None else str(current),
            _integer(pointer["version_token"], field="version_token"),
        )

    @staticmethod
    def _release(rows: CanonicalRowRepository, release_id: str) -> dict[str, object]:
        row = rows.one(
            "registry.analysis_release",
            where={"release_id": _uuid(release_id, field="release_id")},
            columns=_RELEASE_COLUMNS,
        )
        if row is None:
            raise ReleaseManagementError("RELEASE_NOT_FOUND", release_id)
        return row

    def list(self, *, scope_type: str, scope_key: str) -> tuple[ManagedRelease, ...]:
        if scope_type not in {"SESSION", "LONGITUDINAL"}:
            raise ReleaseManagementError("RELEASE_SCOPE_TYPE_INVALID", scope_type)
        _required(scope_key, field="scope_key")
        with self._read_uow() as uow:
            current, _token = self._pointer(uow.canonical_rows, scope_type, scope_key)
            rows = uow.canonical_rows.many(
                "registry.analysis_release",
                where={"scope_type": scope_type, "scope_key": scope_key},
                columns=_RELEASE_COLUMNS,
                order_by=("release_no",),
            )
        return tuple(
            ManagedRelease(
                release_id=str(row["release_id"]),
                scope_type=str(row["scope_type"]),
                scope_key=str(row["scope_key"]),
                release_no=_integer(row["release_no"], field="release_no"),
                status=str(row["status"]),
                parent_release_id=(
                    None if row["parent_release_id"] is None else str(row["parent_release_id"])
                ),
                manifest_hash=str(row["manifest_hash"]),
                created_at=_time(row["created_at"]),
                published_at=(
                    None if row["published_at"] is None else _time(row["published_at"])
                ),
                current=str(row["release_id"]) == current,
            )
            for row in rows
        )

    def withdraw(
        self,
        release_id: str,
        *,
        expected_version_token: int,
        principal_key: str,
        actor_id: str | None = None,
        request_id: str | None = None,
        reason: str,
    ) -> ReleaseLifecycleReceipt:
        if expected_version_token < 0:
            raise ReleaseManagementError("RELEASE_VERSION_TOKEN_INVALID", str(expected_version_token))
        _required(principal_key, field="principal_key")
        _required(reason, field="reason")
        changed_at = _now()
        with self._write_uow() as uow:
            row = self._release(uow.canonical_rows, release_id)
            if str(row["status"]) != "PUBLISHED":
                raise ReleaseManagementError("RELEASE_NOT_WITHDRAWABLE", str(row["status"]))
            scope_type = str(row["scope_type"])
            scope_key = str(row["scope_key"])
            current, token = self._pointer(uow.canonical_rows, scope_type, scope_key)
            if token != expected_version_token or current != release_id:
                raise ReleaseManagementError(
                    "RELEASE_CAS_CONFLICT",
                    f"expected={expected_version_token} actual={token}",
                )
            uow.canonical_rows.update_exact(
                "registry.analysis_release",
                where={"release_id": release_id, "status": "PUBLISHED"},
                values={"status": "WITHDRAWN"},
            )
            next_token = token + 1
            uow.canonical_rows.update_exact(
                "registry.release_scope_pointer",
                where={
                    "scope_type": scope_type,
                    "scope_key": scope_key,
                    "version_token": token,
                },
                values={
                    "current_release_id": None,
                    "version_token": next_token,
                    "updated_at": changed_at,
                },
            )
            uow.audit_log.append(
                AuditLogWrite(
                    actor_id=actor_id,
                    principal_key=principal_key,
                    action="RELEASE_WITHDRAW",
                    object_type="ANALYSIS_RELEASE",
                    object_id=release_id,
                    outcome="SUCCESS",
                    request_id=request_id,
                    reason=reason,
                    details={"scope_type": scope_type, "scope_key": scope_key},
                )
            )
            uow.commit()
        return ReleaseLifecycleReceipt(
            release_id=release_id,
            action="WITHDRAW",
            status="WITHDRAWN",
            scope_type=scope_type,
            scope_key=scope_key,
            current_release_id=None,
            version_token=next_token,
            changed_at_utc=changed_at,
        )

    def supersede(
        self,
        release_id: str,
        *,
        successor_release_id: str,
        expected_version_token: int,
        principal_key: str,
        actor_id: str | None = None,
        request_id: str | None = None,
        reason: str,
    ) -> ReleaseLifecycleReceipt:
        _uuid(successor_release_id, field="successor_release_id")
        _required(principal_key, field="principal_key")
        _required(reason, field="reason")
        changed_at = _now()
        with self._write_uow() as uow:
            previous = self._release(uow.canonical_rows, release_id)
            successor = self._release(uow.canonical_rows, successor_release_id)
            if str(previous["status"]) != "PUBLISHED":
                raise ReleaseManagementError("RELEASE_NOT_SUPERSEDEABLE", str(previous["status"]))
            if str(successor["status"]) != "PUBLISHED":
                raise ReleaseManagementError("SUCCESSOR_NOT_PUBLISHED", str(successor["status"]))
            scope_type = str(previous["scope_type"])
            scope_key = str(previous["scope_key"])
            if (
                str(successor["scope_type"]) != scope_type
                or str(successor["scope_key"]) != scope_key
                or str(successor["parent_release_id"]) != release_id
            ):
                raise ReleaseManagementError("SUCCESSOR_LINEAGE_MISMATCH", successor_release_id)
            current, token = self._pointer(uow.canonical_rows, scope_type, scope_key)
            if token != expected_version_token or current != successor_release_id:
                raise ReleaseManagementError(
                    "RELEASE_CAS_CONFLICT",
                    f"expected={expected_version_token} actual={token}",
                )
            uow.canonical_rows.update_exact(
                "registry.analysis_release",
                where={"release_id": release_id, "status": "PUBLISHED"},
                values={"status": "SUPERSEDED"},
            )
            uow.audit_log.append(
                AuditLogWrite(
                    actor_id=actor_id,
                    principal_key=principal_key,
                    action="RELEASE_SUPERSEDE",
                    object_type="ANALYSIS_RELEASE",
                    object_id=release_id,
                    outcome="SUCCESS",
                    request_id=request_id,
                    reason=reason,
                    details={"successor_release_id": successor_release_id},
                )
            )
            uow.commit()
        return ReleaseLifecycleReceipt(
            release_id=release_id,
            action="SUPERSEDE",
            status="SUPERSEDED",
            scope_type=scope_type,
            scope_key=scope_key,
            current_release_id=successor_release_id,
            version_token=token,
            changed_at_utc=changed_at,
        )


__all__ = [
    "ManagedRelease",
    "ReleaseLifecycleReceipt",
    "ReleaseManagementError",
    "ReleaseManagementService",
]
