"""PIQB B4 composition adapters from Application audit port to DB 1.9 ledger."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tpaa_application import SecurityAuditRecord, SecurityAuditSink
from tpaa_storage import (
    AuditLogWrite,
    PostgreSQLServiceUnitOfWork,
    SQLiteDesktopUnitOfWork,
)


def _write(event: SecurityAuditRecord) -> AuditLogWrite:
    return AuditLogWrite(
        actor_id=event.actor_id,
        principal_key=event.principal_key,
        action=event.action,
        object_type=event.object_type,
        object_id=event.object_id,
        outcome=event.outcome,
        request_id=event.request_id,
        reason=event.reason,
        details=dict(event.details or {}),
    )


@dataclass(frozen=True, slots=True)
class SQLiteSecurityAuditSink(SecurityAuditSink):
    database: Path

    def record(self, event: SecurityAuditRecord) -> None:
        with SQLiteDesktopUnitOfWork(self.database, write=True) as uow:
            uow.audit_log.append(_write(event))
            uow.commit()


@dataclass(frozen=True, slots=True)
class PostgreSQLSecurityAuditSink(SecurityAuditSink):
    conninfo: str

    def record(self, event: SecurityAuditRecord) -> None:
        with PostgreSQLServiceUnitOfWork(self.conninfo) as uow:
            uow.audit_log.append(_write(event))
            uow.commit()
