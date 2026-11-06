"""DB 1.9 audit-ledger adapter for the append-only W3 approval inbox."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from tpaa_security import (
    ApprovalError,
    ApprovalEvent,
    ApprovalService,
    AuthorizationPrincipal,
    Permission,
)
from tpaa_storage import AuditLogWrite
from tpaa_storage.audit_ledger import PersistentAuditLedger


class _ApprovalUow(Protocol):
    audit_log: PersistentAuditLedger

    def __enter__(self) -> _ApprovalUow: ...

    def commit(self) -> None: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...


ApprovalUowFactory = Callable[[], _ApprovalUow]


class PersistentApprovalEventRepository:
    def __init__(
        self,
        read_uow: ApprovalUowFactory,
        write_uow: ApprovalUowFactory,
    ) -> None:
        self._read_uow = read_uow
        self._write_uow = write_uow

    def append(self, event: ApprovalEvent) -> None:
        with self._write_uow() as uow:
            uow.audit_log.append(
                AuditLogWrite(
                    actor_id=None,
                    principal_key=event.actor_subject,
                    action=f"SECURITY_APPROVAL_{event.event_type}",
                    object_type="SECURITY_APPROVAL",
                    object_id=event.approval_id,
                    outcome="SUCCESS",
                    reason=event.reason,
                    details={
                        "event_type": event.event_type,
                        "occurred_at": event.occurred_at.isoformat(),
                        "actor_subject": event.actor_subject,
                        "permission": event.permission.value,
                        "target_type": event.target_type,
                        "target_id": event.target_id,
                        "target_sha256": event.target_sha256,
                        "expires_at": event.expires_at.isoformat(),
                        "policy_sha256": event.policy_sha256,
                        "event_details": event.details,
                    },
                )
            )
            uow.commit()

    def events(self, approval_id: str | None = None) -> tuple[ApprovalEvent, ...]:
        with self._read_uow() as uow:
            rows = uow.audit_log.rows()
        events: list[ApprovalEvent] = []
        for row in rows:
            if row.object_type != "SECURITY_APPROVAL":
                continue
            if approval_id is not None and row.object_id != approval_id:
                continue
            details = row.details
            event_details = details.get("event_details")
            if not isinstance(event_details, dict):
                raise ApprovalError("APPROVAL_AUDIT_INVALID", row.object_id)
            try:
                events.append(
                    ApprovalEvent(
                        approval_id=row.object_id,
                        event_type=str(details["event_type"]),
                        occurred_at=datetime.fromisoformat(str(details["occurred_at"])),
                        actor_subject=str(details["actor_subject"]),
                        permission=Permission(str(details["permission"])),
                        target_type=str(details["target_type"]),
                        target_id=str(details["target_id"]),
                        target_sha256=str(details["target_sha256"]),
                        reason=row.reason or "recorded",
                        expires_at=datetime.fromisoformat(str(details["expires_at"])),
                        policy_sha256=str(details["policy_sha256"]),
                        details={str(key): value for key, value in event_details.items()},
                    )
                )
            except (KeyError, ValueError) as exc:
                raise ApprovalError("APPROVAL_AUDIT_INVALID", row.object_id) from exc
        return tuple(events)


class ApprovalExecutionValidator:
    """Consume one exact approval before a high-risk API action is dispatched."""

    def __init__(self, service: ApprovalService) -> None:
        self._service = service

    def validate(
        self,
        approval_id: str,
        *,
        principal: AuthorizationPrincipal,
        permission: Permission,
        target_type: str,
        target_id: str,
    ) -> bool:
        try:
            self._service.consume(
                principal,
                approval_id,
                permission=permission,
                target_type=target_type,
                target_id=target_id,
                target={"path": target_id},
            )
        except ApprovalError:
            return False
        return True


__all__ = [
    "ApprovalExecutionValidator",
    "PersistentApprovalEventRepository",
]
