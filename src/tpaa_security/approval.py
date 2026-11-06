"""Append-only approval inbox and emergency-access controls."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import uuid4

from .permissions import HIGH_RISK_PERMISSIONS, Permission, SecurityRole
from .policy import AuthorizationPrincipal, AuthorizationService, SecurityPolicyError


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"


class ApprovalError(PermissionError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


@dataclass(frozen=True, slots=True)
class ApprovalEvent:
    approval_id: str
    event_type: str
    occurred_at: datetime
    actor_subject: str
    permission: Permission
    target_type: str
    target_id: str
    target_sha256: str
    reason: str
    expires_at: datetime
    policy_sha256: str
    details: dict[str, object]


class ApprovalEventRepository(Protocol):
    def append(self, event: ApprovalEvent) -> None: ...

    def events(self, approval_id: str | None = None) -> tuple[ApprovalEvent, ...]: ...


class InMemoryApprovalEventRepository:
    def __init__(self) -> None:
        self._events: list[ApprovalEvent] = []

    def append(self, event: ApprovalEvent) -> None:
        self._events.append(event)

    def events(self, approval_id: str | None = None) -> tuple[ApprovalEvent, ...]:
        return tuple(
            event
            for event in self._events
            if approval_id is None or event.approval_id == approval_id
        )


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    approval_id: str
    permission: Permission
    target_type: str
    target_id: str
    target_sha256: str
    maker_subject: str
    status: ApprovalStatus
    created_at: datetime
    expires_at: datetime
    checker_subject: str | None = None


def _required(value: str, field: str) -> str:
    if not value or value != value.strip():
        raise ApprovalError("APPROVAL_TEXT_INVALID", field)
    return value


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _subject_key(subject: str) -> str:
    return "subject:" + hashlib.sha256(subject.encode()).hexdigest()


class ApprovalService:
    def __init__(
        self,
        authorization: AuthorizationService,
        repository: ApprovalEventRepository,
    ) -> None:
        self.authorization = authorization
        self.repository = repository

    def _state(self, approval_id: str, *, now: datetime) -> ApprovalRequest:
        events = self.repository.events(approval_id)
        if not events or events[0].event_type != "REQUESTED":
            raise ApprovalError("APPROVAL_NOT_FOUND", approval_id)
        first = events[0]
        status = ApprovalStatus.PENDING
        checker: str | None = None
        for event in events[1:]:
            if event.event_type == "APPROVED":
                status = ApprovalStatus.APPROVED
                checker = event.actor_subject
            elif event.event_type == "REJECTED":
                status = ApprovalStatus.REJECTED
                checker = event.actor_subject
            elif event.event_type == "CONSUMED":
                status = ApprovalStatus.CONSUMED
        if status in {ApprovalStatus.PENDING, ApprovalStatus.APPROVED} and now >= first.expires_at:
            status = ApprovalStatus.EXPIRED
        return ApprovalRequest(
            approval_id=approval_id,
            permission=first.permission,
            target_type=first.target_type,
            target_id=first.target_id,
            target_sha256=first.target_sha256,
            maker_subject=first.actor_subject,
            status=status,
            created_at=first.occurred_at,
            expires_at=first.expires_at,
            checker_subject=checker,
        )

    def request(
        self,
        maker: AuthorizationPrincipal,
        permission: Permission,
        *,
        target_type: str,
        target_id: str,
        target: object,
        reason: str,
        ttl: timedelta = timedelta(hours=24),
        now: datetime | None = None,
    ) -> ApprovalRequest:
        if permission not in HIGH_RISK_PERMISSIONS:
            raise ApprovalError("APPROVAL_NOT_REQUIRED", permission.value)
        rule = self.authorization.policy.high_risk_rules[permission]
        if not maker.roles & rule.maker_roles:
            raise ApprovalError("MAKER_ROLE_DENIED", permission.value)
        if ttl <= timedelta(0) or ttl > timedelta(days=7):
            raise ApprovalError("APPROVAL_TTL_INVALID")
        instant = datetime.now(UTC) if now is None else now.astimezone(UTC)
        approval_id = str(uuid4())
        event = ApprovalEvent(
            approval_id=approval_id,
            event_type="REQUESTED",
            occurred_at=instant,
            actor_subject=_subject_key(maker.subject),
            permission=permission,
            target_type=_required(target_type, "target_type"),
            target_id=_required(target_id, "target_id"),
            target_sha256=_digest(target),
            reason=_required(reason, "reason"),
            expires_at=instant + ttl,
            policy_sha256=self.authorization.policy.sha256,
            details={"maker_roles": sorted(role.value for role in maker.roles)},
        )
        self.repository.append(event)
        return self._state(approval_id, now=instant)

    def decide(
        self,
        checker: AuthorizationPrincipal,
        approval_id: str,
        *,
        approve: bool,
        reason: str,
        now: datetime | None = None,
    ) -> ApprovalRequest:
        instant = datetime.now(UTC) if now is None else now.astimezone(UTC)
        current = self._state(approval_id, now=instant)
        if current.status is not ApprovalStatus.PENDING:
            raise ApprovalError("APPROVAL_NOT_PENDING", current.status.value)
        if _subject_key(checker.subject) == current.maker_subject:
            raise ApprovalError("MAKER_CHECKER_COLLISION", approval_id)
        self.authorization.require(checker, Permission.APPROVAL_REVIEW)
        rule = self.authorization.policy.high_risk_rules[current.permission]
        if not checker.roles & rule.checker_roles:
            raise ApprovalError("CHECKER_ROLE_DENIED", current.permission.value)
        first = self.repository.events(approval_id)[0]
        self.repository.append(
            ApprovalEvent(
                approval_id=approval_id,
                event_type="APPROVED" if approve else "REJECTED",
                occurred_at=instant,
                actor_subject=_subject_key(checker.subject),
                permission=current.permission,
                target_type=current.target_type,
                target_id=current.target_id,
                target_sha256=current.target_sha256,
                reason=_required(reason, "reason"),
                expires_at=current.expires_at,
                policy_sha256=first.policy_sha256,
                details={"checker_roles": sorted(role.value for role in checker.roles)},
            )
        )
        return self._state(approval_id, now=instant)

    def consume(
        self,
        actor: AuthorizationPrincipal,
        approval_id: str,
        *,
        permission: Permission,
        target_type: str,
        target_id: str,
        target: object,
        now: datetime | None = None,
    ) -> ApprovalRequest:
        instant = datetime.now(UTC) if now is None else now.astimezone(UTC)
        current = self._state(approval_id, now=instant)
        if current.status is not ApprovalStatus.APPROVED:
            raise ApprovalError("APPROVAL_NOT_USABLE", current.status.value)
        if _subject_key(actor.subject) != current.maker_subject:
            raise ApprovalError("APPROVAL_MAKER_REQUIRED", approval_id)
        if (
            current.permission is not permission
            or current.target_type != target_type
            or current.target_id != target_id
            or current.target_sha256 != _digest(target)
        ):
            raise ApprovalError("APPROVAL_TARGET_MISMATCH", approval_id)
        try:
            self.authorization.require(actor, permission, approval_id=approval_id)
        except SecurityPolicyError as exc:
            raise ApprovalError(exc.code, permission.value) from exc
        first = self.repository.events(approval_id)[0]
        self.repository.append(
            ApprovalEvent(
                approval_id=approval_id,
                event_type="CONSUMED",
                occurred_at=instant,
                actor_subject=_subject_key(actor.subject),
                permission=permission,
                target_type=target_type,
                target_id=target_id,
                target_sha256=current.target_sha256,
                reason="approved action executed",
                expires_at=current.expires_at,
                policy_sha256=first.policy_sha256,
                details={"checker_subject": current.checker_subject or ""},
            )
        )
        return self._state(approval_id, now=instant)

    def inbox(
        self,
        checker: AuthorizationPrincipal,
        *,
        now: datetime | None = None,
    ) -> tuple[ApprovalRequest, ...]:
        instant = datetime.now(UTC) if now is None else now.astimezone(UTC)
        self.authorization.require(checker, Permission.APPROVAL_REVIEW)
        ids = dict.fromkeys(event.approval_id for event in self.repository.events())
        items = []
        for approval_id in ids:
            state = self._state(approval_id, now=instant)
            rule = self.authorization.policy.high_risk_rules[state.permission]
            if state.status is ApprovalStatus.PENDING and checker.roles & rule.checker_roles:
                items.append(state)
        return tuple(items)


@dataclass(frozen=True, slots=True)
class BreakGlassGrant:
    grant_id: str
    subject: str
    permission: Permission
    target_id: str
    ticket: str
    expires_at: datetime
    policy_sha256: str


class BreakGlassService:
    def __init__(
        self, authorization: AuthorizationService, repository: ApprovalEventRepository
    ) -> None:
        self.authorization = authorization
        self.repository = repository

    def issue(
        self,
        principal: AuthorizationPrincipal,
        permission: Permission,
        *,
        target_id: str,
        ticket: str,
        reason: str,
        ttl: timedelta,
        now: datetime | None = None,
    ) -> BreakGlassGrant:
        if SecurityRole.ADMINISTRATOR not in principal.roles:
            raise ApprovalError("BREAK_GLASS_ROLE_DENIED")
        self.authorization.require(principal, Permission.BREAK_GLASS)
        document = self.authorization.policy.document.get("break_glass")
        if not isinstance(document, dict):
            raise ApprovalError("BREAK_GLASS_POLICY_INVALID")
        allowed = document.get("allowed_permissions")
        maximum = document.get("maximum_seconds")
        if not isinstance(allowed, list) or permission.value not in allowed:
            raise ApprovalError("BREAK_GLASS_PERMISSION_DENIED", permission.value)
        if not isinstance(maximum, int) or ttl <= timedelta(0) or ttl > timedelta(seconds=maximum):
            raise ApprovalError("BREAK_GLASS_TTL_DENIED")
        instant = datetime.now(UTC) if now is None else now.astimezone(UTC)
        grant_id = str(uuid4())
        self.repository.append(
            ApprovalEvent(
                approval_id=grant_id,
                event_type="BREAK_GLASS_ISSUED",
                occurred_at=instant,
                actor_subject=_subject_key(principal.subject),
                permission=permission,
                target_type="BREAK_GLASS",
                target_id=_required(target_id, "target_id"),
                target_sha256=_digest({"ticket": _required(ticket, "ticket")}),
                reason=_required(reason, "reason"),
                expires_at=instant + ttl,
                policy_sha256=self.authorization.policy.sha256,
                details={"ticket": ticket},
            )
        )
        return BreakGlassGrant(
            grant_id=grant_id,
            subject=principal.subject,
            permission=permission,
            target_id=target_id,
            ticket=ticket,
            expires_at=instant + ttl,
            policy_sha256=self.authorization.policy.sha256,
        )


__all__ = [
    "ApprovalError",
    "ApprovalEvent",
    "ApprovalEventRepository",
    "ApprovalRequest",
    "ApprovalService",
    "ApprovalStatus",
    "BreakGlassGrant",
    "BreakGlassService",
    "InMemoryApprovalEventRepository",
]
