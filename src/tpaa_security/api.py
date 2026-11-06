"""Transport-neutral HTTP authorization guard for the unified API graph."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Protocol

from .generated_g2_authority import ROUTE_SECURITY_BINDINGS
from .permissions import HIGH_RISK_PERMISSIONS, Permission
from .policy import (
    AuthorizationDecision,
    AuthorizationPrincipal,
    AuthorizationService,
    ResourceContext,
)


class ApprovalValidator(Protocol):
    def validate(
        self,
        approval_id: str,
        *,
        principal: AuthorizationPrincipal,
        permission: Permission,
        target_type: str,
        target_id: str,
    ) -> bool: ...


class ApiAuthorizationAudit(Protocol):
    def record(self, event: ApiAuthorizationEvent) -> None: ...


@dataclass(frozen=True, slots=True)
class ApiAuthorizationEvent:
    subject: str
    route_id: str
    method: str
    path: str
    permission: str | None
    allowed: bool
    code: str
    policy_sha256: str


class InMemoryApiAuthorizationAudit:
    def __init__(self) -> None:
        self.events: list[ApiAuthorizationEvent] = []

    def record(self, event: ApiAuthorizationEvent) -> None:
        self.events.append(event)


def _audit_subject(subject: str) -> str:
    digest = hashlib.sha256(subject.encode("utf-8")).hexdigest()
    return f"SUBJECT_SHA256:{digest}"


@dataclass(frozen=True, slots=True)
class RouteSecurityBinding:
    route_id: str
    method: str
    template: str
    permission: Permission | None
    audit_mode: str


class RouteSecurityAuthorityError(LookupError):
    """No approved exact route binding exists for an incoming request."""


def _route_pattern(template: str) -> re.Pattern[str]:
    segments = template.split("/")
    pattern = "/".join(
        (
            ".+"
            if segment.startswith("{") and segment.endswith(":path}")
            else "[^/]+"
            if segment.startswith("{") and segment.endswith("}")
            else re.escape(segment)
        )
        for segment in segments
    )
    return re.compile(f"^{pattern}$")


_ROUTE_TABLE = tuple(
    (
        RouteSecurityBinding(
            route_id=route_id,
            method=method,
            template=template,
            permission=None if permission_id is None else Permission(permission_id),
            audit_mode=audit_mode,
        ),
        _route_pattern(template),
    )
    for route_id, method, template, permission_id, audit_mode in ROUTE_SECURITY_BINDINGS
)


def route_security(method: str, path: str) -> RouteSecurityBinding | None:
    """Return the one approved exact binding, or ``None`` for an unknown route."""

    normalized_method = method.upper()
    matches = [
        binding
        for binding, pattern in _ROUTE_TABLE
        if binding.method == normalized_method and pattern.fullmatch(path)
    ]
    if len(matches) > 1:
        raise RouteSecurityAuthorityError(f"ambiguous route authority: {method} {path}")
    return matches[0] if matches else None


def route_permission(method: str, path: str) -> Permission | None:
    """Return the explicit permission; unknown routes fail closed."""

    binding = route_security(method, path)
    if binding is None:
        raise RouteSecurityAuthorityError(f"unknown route: {method.upper()} {path}")
    return binding.permission


class ApiAuthorizationGuard:
    def __init__(
        self,
        authorization: AuthorizationService,
        *,
        audit: ApiAuthorizationAudit,
        approval_validator: ApprovalValidator | None = None,
    ) -> None:
        self.authorization = authorization
        self.audit = audit
        self.approval_validator = approval_validator

    def authorize(
        self,
        principal: AuthorizationPrincipal,
        *,
        method: str,
        path: str,
        approval_id: str | None = None,
        resource: ResourceContext | None = None,
    ) -> AuthorizationDecision:
        binding = route_security(method, path)
        if binding is None:
            permission = None
            decision = AuthorizationDecision(
                allowed=False,
                code="ROUTE_NOT_AUTHORIZED",
                policy_sha256=self.authorization.policy.sha256,
            )
        elif binding.permission is None:
            permission = None
            decision = AuthorizationDecision(
                allowed=True,
                code="AUTHENTICATED_STATUS_ACCESS",
                policy_sha256=self.authorization.policy.sha256,
            )
        else:
            permission = binding.permission
            validated_approval: str | None = None
            if permission in HIGH_RISK_PERMISSIONS and approval_id:
                if self.approval_validator is not None and self.approval_validator.validate(
                    approval_id,
                    principal=principal,
                    permission=permission,
                    target_type="API_PATH",
                    target_id=path,
                ):
                    validated_approval = approval_id
            target = resource or ResourceContext(
                resource_type="API_PATH",
                resource_id=path,
            )
            decision = self.authorization.decide(
                principal,
                permission,
                resource=target,
                approval_id=validated_approval,
            )
        if binding is None or binding.audit_mode == "ALWAYS" or not decision.allowed:
            try:
                self.audit.record(
                    ApiAuthorizationEvent(
                        subject=_audit_subject(principal.subject),
                        route_id=(
                            "UNREGISTERED" if binding is None else binding.route_id
                        ),
                        method=method.upper(),
                        path=path,
                        permission=None if permission is None else permission.value,
                        allowed=decision.allowed,
                        code=decision.code,
                        policy_sha256=decision.policy_sha256,
                    )
                )
            except Exception:
                return AuthorizationDecision(
                    allowed=False,
                    code="AUDIT_WRITE_FAILED",
                    policy_sha256=decision.policy_sha256,
                )
        return decision


__all__ = [
    "ApiAuthorizationEvent",
    "ApiAuthorizationGuard",
    "ApprovalValidator",
    "InMemoryApiAuthorizationAudit",
    "RouteSecurityAuthorityError",
    "RouteSecurityBinding",
    "route_permission",
    "route_security",
]
