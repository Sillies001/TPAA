"""PIQB B4 composition adapters from Application audit port to DB 1.9 ledger."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from tpaa_application import SecurityAuditRecord, SecurityAuditSink
from tpaa_security import ApiAuthorizationEvent
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
    authority_root: Path | None = None
    write_consistency_lock: Path | None = None

    def record(self, event: SecurityAuditRecord) -> None:
        with SQLiteDesktopUnitOfWork(
            self.database,
            write=True,
            authority_root=self.authority_root,
            write_consistency_lock=self.write_consistency_lock,
        ) as uow:
            uow.audit_log.append(_write(event))
            uow.commit()


@dataclass(frozen=True, slots=True)
class PostgreSQLSecurityAuditSink(SecurityAuditSink):
    conninfo: str
    authority_root: Path | None = None

    def record(self, event: SecurityAuditRecord) -> None:
        with PostgreSQLServiceUnitOfWork(
            self.conninfo,
            authority_root=self.authority_root,
        ) as uow:
            uow.audit_log.append(_write(event))
            uow.commit()


@dataclass(frozen=True, slots=True)
class ApplicationApiAuthorizationAudit:
    """Persist authorization decisions without storing a direct user identity."""

    sink: SecurityAuditSink

    def record(self, event: ApiAuthorizationEvent) -> None:
        principal_key = (
            event.subject
            if event.subject.startswith("SUBJECT_SHA256:")
            else "SUBJECT_SHA256:" + hashlib.sha256(event.subject.encode()).hexdigest()
        )
        object_id = "api-path:" + hashlib.sha256(event.path.encode()).hexdigest()
        self.sink.record(
            SecurityAuditRecord(
                actor_id=None,
                principal_key=principal_key,
                action="API_AUTHORIZATION",
                object_type="API_ROUTE",
                object_id=object_id,
                outcome="ALLOW" if event.allowed else "DENY",
                reason=event.code,
                details={
                    "route_id": event.route_id,
                    "method": event.method,
                    "permission": event.permission,
                    "policy_sha256": event.policy_sha256,
                },
            )
        )


@dataclass(frozen=True, slots=True)
class WeaponEventSecurityAuditAdapter:
    """Persist G5 detector/identity rejection events through the shared ledger."""

    sink: SecurityAuditSink

    def record(self, event_type: str, details: Mapping[str, object]) -> None:
        requested_batch = str(details.get("requested_batch_id", "UNKNOWN"))
        source_launch = str(details.get("source_launch_id", "UNKNOWN"))
        self.sink.record(
            SecurityAuditRecord(
                actor_id=None,
                principal_key="COMPONENT:" + str(details.get("actor", "weapon_event")),
                action=event_type,
                object_type="WEAPON_EVENT_SOURCE_FACT",
                object_id=(
                    "source-launch-sha256:"
                    + hashlib.sha256(source_launch.encode("utf-8")).hexdigest()
                ),
                outcome="DENY",
                reason="CROSS_BATCH_WEAPON_EVENT_FORBIDDEN",
                details={
                    "requested_batch_id": requested_batch,
                    "fact_batch_id": str(details.get("fact_batch_id", "UNKNOWN")),
                },
            )
        )
