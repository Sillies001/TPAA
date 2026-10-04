"""DB 1.9 audit.audit_log adapter with SQLite/PostgreSQL normalization."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from .canonical_rows import CanonicalRowRepository


class PersistentAuditError(RuntimeError):
    """Fail-closed persistent audit error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class AuditLogWrite:
    actor_id: str | None
    principal_key: str
    action: str
    object_type: str
    object_id: str
    outcome: str
    request_id: str | None = None
    reason: str | None = None
    details: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class AuditLogRow:
    audit_id: int
    actor_id: str | None
    principal_key: str
    action: str
    object_type: str
    object_id: str
    outcome: str
    request_id: str | None
    reason: str | None
    details: dict[str, object]
    created_at: str


_COLUMNS = (
    "audit_id",
    "actor_id",
    "action",
    "object_type",
    "object_id",
    "new_value",
    "reason",
    "request_id",
    "created_at",
)


def _required(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise PersistentAuditError("B4_AUDIT_TEXT_INVALID", field)
    return value


def _actor(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, str):
        try:
            parsed = UUID(value)
        except ValueError as exc:
            raise PersistentAuditError("B4_AUDIT_ACTOR_INVALID", value) from exc
        if str(parsed) != value or parsed.int == 0:
            raise PersistentAuditError("B4_AUDIT_ACTOR_INVALID", value)
        return value
    raise PersistentAuditError("B4_AUDIT_ACTOR_INVALID", type(value).__name__)


def _optional(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _required(value, field=field)


def _timestamp(value: object) -> str:
    if isinstance(value, datetime):
        normalized = value
        if normalized.tzinfo is not None:
            normalized = normalized.astimezone(UTC)
        return normalized.isoformat().replace("+00:00", "Z")
    if isinstance(value, str) and value:
        return value
    raise PersistentAuditError("B4_AUDIT_TIME_INVALID", str(value))


def _payload(value: object) -> dict[str, object]:
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise PersistentAuditError("B4_AUDIT_JSON_INVALID", value) from exc
    if not isinstance(parsed, dict):
        raise PersistentAuditError(
            "B4_AUDIT_JSON_INVALID",
            type(parsed).__name__,
        )
    return {str(key): item for key, item in parsed.items()}


class PersistentAuditLedger:
    """Transaction-scoped sole adapter for existing DB 1.9 audit.audit_log."""

    def __init__(self, rows: CanonicalRowRepository) -> None:
        self._rows = rows

    def append(self, value: AuditLogWrite) -> None:
        actor_id = _actor(value.actor_id)
        principal_key = _required(value.principal_key, field="principal_key")
        action = _required(value.action, field="action")
        object_type = _required(value.object_type, field="object_type")
        object_id = _required(value.object_id, field="object_id")
        outcome = _required(value.outcome, field="outcome")
        request_id = _optional(value.request_id, field="request_id")
        reason = _optional(value.reason, field="reason")
        details = dict(value.details or {})
        self._rows.insert(
            "audit.audit_log",
            {
                "actor_id": actor_id,
                "action": action,
                "object_type": object_type,
                "object_id": object_id,
                "new_value": {
                    "principal_key": principal_key,
                    "outcome": outcome,
                    "details": details,
                },
                "reason": reason,
                "request_id": request_id,
            },
            field_kinds={"new_value": "json"},
        )

    def rows(self) -> tuple[AuditLogRow, ...]:
        result: list[AuditLogRow] = []
        for row in self._rows.many(
            "audit.audit_log",
            where={},
            columns=_COLUMNS,
            order_by=("audit_id",),
        ):
            raw_id = row.get("audit_id")
            if isinstance(raw_id, bool) or not isinstance(raw_id, int):
                raise PersistentAuditError(
                    "B4_AUDIT_ID_INVALID",
                    str(raw_id),
                )
            body = _payload(row.get("new_value"))
            principal_key = _required(
                body.get("principal_key"),
                field="principal_key",
            )
            outcome = _required(body.get("outcome"), field="outcome")
            raw_details = body.get("details", {})
            if not isinstance(raw_details, dict):
                raise PersistentAuditError(
                    "B4_AUDIT_DETAILS_INVALID",
                    type(raw_details).__name__,
                )
            result.append(
                AuditLogRow(
                    audit_id=raw_id,
                    actor_id=_actor(row.get("actor_id")),
                    principal_key=principal_key,
                    action=_required(row.get("action"), field="action"),
                    object_type=_required(
                        row.get("object_type"),
                        field="object_type",
                    ),
                    object_id=_required(row.get("object_id"), field="object_id"),
                    outcome=outcome,
                    request_id=_optional(
                        row.get("request_id"),
                        field="request_id",
                    ),
                    reason=_optional(row.get("reason"), field="reason"),
                    details={str(key): item for key, item in raw_details.items()},
                    created_at=_timestamp(row.get("created_at")),
                )
            )
        return tuple(result)
