"""Transport-neutral HTTP authorization guard for the unified API graph."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Protocol

from .generated_g9_authority import ROUTE_SECURITY_BINDINGS
from .gui_authority import derive_gui_permissions
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


class ApiResourceResolver(Protocol):
    """Resolve an exact resource context before authorization."""

    def resolve(self, method: str, path: str) -> ResourceContext | None: ...


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
    gui_permission_id: str | None


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
            gui_permission_id=gui_permission_id,
        ),
        _route_pattern(template),
    )
    for (
        route_id,
        method,
        template,
        permission_id,
        audit_mode,
        gui_permission_id,
    ) in ROUTE_SECURITY_BINDINGS
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
        resource_resolver: ApiResourceResolver | None = None,
    ) -> None:
        self.authorization = authorization
        self.audit = audit
        self.approval_validator = approval_validator
        self.resource_resolver = resource_resolver

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
            resolved = resource
            if resolved is None and self.resource_resolver is not None:
                resolved = self.resource_resolver.resolve(method.upper(), path)
            target = resolved or ResourceContext(
                resource_type="API_PATH",
                resource_id=path,
            )
            if binding.route_id in {"api.route.097", "api.route.098", "api.route.099"}:
                decision = self._authorize_exact_weapon_event(
                    principal,
                    permission,
                    target,
                    approval_id=validated_approval,
                )
            else:
                decision = self.authorization.decide(
                    principal,
                    permission,
                    resource=target,
                    approval_id=validated_approval,
                )
        if binding is not None and decision.allowed and binding.gui_permission_id is not None:
            business_permissions = frozenset(
                permission
                for role in principal.roles
                for permission in self.authorization.policy.role_permissions[role]
            )
            gui_permissions = derive_gui_permissions(
                principal.roles,
                business_permissions,
            )
            if binding.gui_permission_id not in gui_permissions:
                decision = AuthorizationDecision(
                    allowed=False,
                    code="GUI_PERMISSION_DENIED",
                    policy_sha256=self.authorization.policy.sha256,
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

    def _authorize_exact_weapon_event(
        self,
        principal: AuthorizationPrincipal,
        permission: Permission,
        resource: ResourceContext,
        *,
        approval_id: str | None,
    ) -> AuthorizationDecision:
        """Require exact WE scope or the complete release/context scope tuple."""

        policy = self.authorization.policy
        if resource.resource_type != "WEAPON_EVENT" or resource.weapon_event_id is None:
            return AuthorizationDecision(False, "WEAPON_EVENT_SCOPE_UNRESOLVED", policy.sha256)
        if principal.roles & policy.global_scope_roles:
            return self.authorization.decide(
                principal,
                permission,
                resource=resource,
                approval_id=approval_id,
            )
        if "*" in principal.scopes:
            return AuthorizationDecision(False, "RESOURCE_SCOPE_WILDCARD_DENIED", policy.sha256)
        exact = f"weapon_event:{resource.weapon_event_id}" in principal.scopes
        required = {f"batch:{resource.batch_id}"} if resource.batch_id else set()
        if resource.release_id:
            required.add(f"release:{resource.release_id}")
        if resource.context_id:
            required.add(f"context:{resource.context_id}")
        complete_context = bool(required) and required <= principal.scopes
        if not exact and not complete_context:
            return AuthorizationDecision(False, "WEAPON_EVENT_EXACT_SCOPE_DENIED", policy.sha256)
        return self.authorization.decide(
            principal,
            permission,
            resource=resource,
            approval_id=approval_id,
        )


__all__ = [
    "ApiAuthorizationEvent",
    "ApiAuthorizationGuard",
    "ApiResourceResolver",
    "ApprovalValidator",
    "InMemoryApiAuthorizationAudit",
    "RouteSecurityAuthorityError",
    "RouteSecurityBinding",
    "route_permission",
    "route_security",
]
