"""Transport-neutral HTTP authorization guard for the unified API graph."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

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


_STATUS_PATHS = frozenset(
    {
        "/health",
        "/readiness",
        "/version",
        "/runtime/features",
        "/runtime/qualification",
        "/runtime/observability",
        "/runtime/metrics",
        "/security/session",
    }
)


def route_permission(method: str, path: str) -> Permission | None:
    """Classify every production route; unknown writes never become public."""

    normalized_method = method.upper()
    lowered = path.lower()
    if path in _STATUS_PATHS:
        return None
    if lowered == "/security/approvals" and normalized_method == "POST":
        return None
    if lowered.startswith("/security/approvals"):
        return Permission.APPROVAL_REVIEW
    if "export" in lowered:
        return Permission.EXPORT_DEIDENTIFIED
    if "plugin" in lowered and normalized_method != "GET":
        return Permission.PLUGIN_INSTALL if "install" in lowered else Permission.PLUGIN_ENABLE
    if "override" in lowered and normalized_method != "GET":
        return Permission.PUBLICATION_OVERRIDE
    if "model" in lowered and any(term in lowered for term in ("publish", "release")):
        return Permission.MODEL_RELEASE
    if normalized_method != "GET" and lowered.endswith("/replay"):
        return Permission.COMPUTE_EXECUTE
    if normalized_method == "DELETE" and "release" in lowered:
        return Permission.WITHDRAW_RELEASE
    if normalized_method != "GET" and any(
        term in lowered for term in ("publish", "/release", "/releases")
    ):
        return Permission.PRODUCT_PUBLISH
    if "annotation" in lowered and normalized_method != "GET":
        return Permission.ANNOTATION_WRITE
    if normalized_method != "GET" and any(
        term in lowered for term in ("/source", "/import", "/ingest")
    ):
        return Permission.SOURCE_IMPORT
    if normalized_method != "GET" and any(
        term in lowered for term in ("/config", "/context", "/profile", "/rule")
    ):
        return Permission.CONFIGURATION_WRITE
    if normalized_method != "GET":
        return Permission.COMPUTE_EXECUTE
    if any(term in lowered for term in ("/source", "/raw")):
        return Permission.RAW_DATA_READ
    return Permission.DERIVED_DATA_READ


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
        permission = route_permission(method, path)
        if permission is None:
            decision = AuthorizationDecision(
                allowed=True,
                code="AUTHENTICATED_STATUS_ACCESS",
                policy_sha256=self.authorization.policy.sha256,
            )
        else:
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
        if permission is not None or not decision.allowed:
            try:
                self.audit.record(
                    ApiAuthorizationEvent(
                        subject=_audit_subject(principal.subject),
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
    "route_permission",
]
