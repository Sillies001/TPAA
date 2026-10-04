"""Engine-neutral security audit records emitted by Application services."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SecurityAuditRecord:
    actor_id: str | None
    principal_key: str
    action: str
    object_type: str
    object_id: str
    outcome: str
    request_id: str | None = None
    reason: str | None = None
    details: Mapping[str, object] | None = None


class SecurityAuditSink(Protocol):
    """Application-side port; infrastructure persists without leaking drivers."""

    def record(self, event: SecurityAuditRecord) -> None:
        """Persist or forward one security audit event."""


class InMemorySecurityAuditSink:
    """Deterministic sink for unit tests and non-persistent compositions."""

    def __init__(self) -> None:
        self.events: list[SecurityAuditRecord] = []

    def record(self, event: SecurityAuditRecord) -> None:
        self.events.append(event)
