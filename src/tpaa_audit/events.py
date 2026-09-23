"""Deterministic audit event framework for M0 security/governance actions."""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class AuditEvent:
    actor: str
    action: str
    request_id: str
    reason: str
    product_version: str
    authority_hash: str
    system_time_utc: str

    @classmethod
    def create(
        cls,
        *,
        actor: str,
        action: str,
        request_id: str,
        reason: str,
        product_version: str,
        authority_hash: str,
    ) -> AuditEvent:
        required = {
            "actor": actor,
            "action": action,
            "request_id": request_id,
            "reason": reason,
            "product_version": product_version,
            "authority_hash": authority_hash,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"audit event missing fields: {missing}")
        return cls(
            **required,
            system_time_utc=dt.datetime.now(dt.UTC).isoformat(),
        )

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


class InMemoryAuditSink:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self.events.append(event)


class NdjsonAuditSink:
    def __init__(self, path: Path) -> None:
        self.path = path

    def record(self, event: AuditEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event.as_dict(), sort_keys=True, separators=(",", ":")))
            handle.write("\n")
