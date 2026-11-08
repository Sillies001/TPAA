"""Immutable security-policy loader and default-deny authorization service."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from .permissions import HIGH_RISK_PERMISSIONS, Permission, SecurityRole

POLICY_SCHEMA = "TPAA_SECURITY_POLICY_V1"


class SecurityPolicyError(PermissionError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class HighRiskRule:
    maker_roles: frozenset[SecurityRole]
    checker_roles: frozenset[SecurityRole]


@dataclass(frozen=True, slots=True)
class SecurityPolicy:
    version: str
    sha256: str
    role_permissions: Mapping[SecurityRole, frozenset[Permission]]
    projection_roles: Mapping[SecurityRole, str]
    high_risk_rules: Mapping[Permission, HighRiskRule]
    ownership_required: frozenset[Permission]
    global_scope_roles: frozenset[SecurityRole]
    document: Mapping[str, object]

    def projection_role(self, roles: Iterable[SecurityRole]) -> str:
        selected = tuple(roles)
        if not selected:
            raise SecurityPolicyError("ROLE_REQUIRED", "principal has no role")
        priorities = (
            SecurityRole.ADMINISTRATOR,
            SecurityRole.MODEL_REVIEWER,
            SecurityRole.TRAINING_MANAGER,
            SecurityRole.EVALUATOR,
            SecurityRole.INSTRUCTOR,
            SecurityRole.DATA_ENGINEER,
            SecurityRole.MAINTENANCE_ENGINEERING,
            SecurityRole.UNIT_ANALYST,
            SecurityRole.TRAINEE,
        )
        for role in priorities:
            if role in selected:
                return self.projection_roles[role]
        raise SecurityPolicyError("ROLE_NOT_MAPPED", ",".join(role.value for role in selected))


@dataclass(frozen=True, slots=True)
class AuthorizationPrincipal:
    subject: str
    roles: frozenset[SecurityRole]
    scopes: frozenset[str]
    authentication_method: str
    credential_id: str

    def __post_init__(self) -> None:
        if not self.subject or self.subject != self.subject.strip():
            raise ValueError("subject must be non-empty normalized text")
        if not self.roles:
            raise ValueError("at least one security role is required")
        if not self.authentication_method or not self.credential_id:
            raise ValueError("authentication evidence is required")


@dataclass(frozen=True, slots=True)
class ResourceContext:
    resource_type: str
    resource_id: str
    owner_subject: str | None = None
    session_id: str | None = None
    release_id: str | None = None
    unit_id: str | None = None
    batch_id: str | None = None
    context_id: str | None = None
    weapon_event_id: str | None = None
    classification: str = "INTERNAL"

    def scope_keys(self) -> frozenset[str]:
        values = {
            f"resource:{self.resource_type}:{self.resource_id}",
        }
        if self.owner_subject:
            values.add(f"subject:{self.owner_subject}")
        if self.session_id:
            values.add(f"session:{self.session_id}")
        if self.release_id:
            values.add(f"release:{self.release_id}")
        if self.unit_id:
            values.add(f"unit:{self.unit_id}")
        if self.batch_id:
            values.add(f"batch:{self.batch_id}")
        if self.context_id:
            values.add(f"context:{self.context_id}")
        if self.weapon_event_id:
            values.add(f"weapon_event:{self.weapon_event_id}")
        return frozenset(values)


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    code: str
    policy_sha256: str
    approval_required: bool = False


def _roles(values: object, *, field: str) -> frozenset[SecurityRole]:
    if not isinstance(values, list) or not values:
        raise SecurityPolicyError("POLICY_INVALID", field)
    try:
        return frozenset(SecurityRole(str(value)) for value in values)
    except ValueError as exc:
        raise SecurityPolicyError("POLICY_ROLE_INVALID", field) from exc


def load_security_policy(path: Path | None = None) -> SecurityPolicy:
    source = (
        Path(str(files("tpaa_security").joinpath("TPAA_SECURITY_POLICY_V1.json")))
        if path is None
        else path
    )
    try:
        document: object = json.loads(source.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SecurityPolicyError("POLICY_UNAVAILABLE", str(source)) from exc
    if not isinstance(document, dict) or document.get("schema") != POLICY_SCHEMA:
        raise SecurityPolicyError("POLICY_SCHEMA_MISMATCH", str(source))
    if document.get("default_decision") != "DENY":
        raise SecurityPolicyError("POLICY_DEFAULT_NOT_DENY", str(source))
    raw_permissions = document.get("role_permissions")
    raw_projection = document.get("projection_role_mapping")
    raw_high_risk = document.get("high_risk_permissions")
    if not isinstance(raw_permissions, dict) or not isinstance(raw_projection, dict):
        raise SecurityPolicyError("POLICY_INVALID", "role mappings")
    if not isinstance(raw_high_risk, dict):
        raise SecurityPolicyError("POLICY_INVALID", "high_risk_permissions")

    role_permissions: dict[SecurityRole, frozenset[Permission]] = {}
    projection_roles: dict[SecurityRole, str] = {}
    for role in SecurityRole:
        raw = raw_permissions.get(role.value)
        if not isinstance(raw, list):
            raise SecurityPolicyError("POLICY_ROLE_MISSING", role.value)
        try:
            role_permissions[role] = frozenset(Permission(str(value)) for value in raw)
        except ValueError as exc:
            raise SecurityPolicyError("POLICY_PERMISSION_INVALID", role.value) from exc
        projection = raw_projection.get(role.value)
        if not isinstance(projection, str) or not projection:
            raise SecurityPolicyError("POLICY_PROJECTION_MISSING", role.value)
        projection_roles[role] = projection

    rules: dict[Permission, HighRiskRule] = {}
    for permission in HIGH_RISK_PERMISSIONS:
        raw = raw_high_risk.get(permission.value)
        if not isinstance(raw, dict):
            raise SecurityPolicyError("POLICY_HIGH_RISK_MISSING", permission.value)
        rules[permission] = HighRiskRule(
            maker_roles=_roles(raw.get("maker_roles"), field=f"{permission}.maker_roles"),
            checker_roles=_roles(raw.get("checker_roles"), field=f"{permission}.checker_roles"),
        )
    try:
        ownership = frozenset(
            Permission(str(value)) for value in document["ownership_required_permissions"]
        )
        global_roles = frozenset(
            SecurityRole(str(value)) for value in document["global_scope_roles"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SecurityPolicyError("POLICY_INVALID", "ownership/global scope") from exc
    version = document.get("policy_version")
    if not isinstance(version, str) or not version:
        raise SecurityPolicyError("POLICY_INVALID", "policy_version")
    return SecurityPolicy(
        version=version,
        sha256=hashlib.sha256(_canonical_bytes(document)).hexdigest(),
        role_permissions=role_permissions,
        projection_roles=projection_roles,
        high_risk_rules=rules,
        ownership_required=ownership,
        global_scope_roles=global_roles,
        document=document,
    )


class AuthorizationService:
    def __init__(self, policy: SecurityPolicy) -> None:
        self.policy = policy

    def decide(
        self,
        principal: AuthorizationPrincipal,
        permission: Permission,
        *,
        resource: ResourceContext | None = None,
        approval_id: str | None = None,
    ) -> AuthorizationDecision:
        granted = any(
            permission in self.policy.role_permissions.get(role, frozenset())
            for role in principal.roles
        )
        if not granted:
            return AuthorizationDecision(False, "PERMISSION_DENIED", self.policy.sha256)
        if permission in self.policy.ownership_required:
            global_scope = bool(principal.roles & self.policy.global_scope_roles)
            if not global_scope and "*" in principal.scopes:
                return AuthorizationDecision(
                    False,
                    "RESOURCE_SCOPE_WILDCARD_DENIED",
                    self.policy.sha256,
                )
            owned = resource is not None and bool(
                resource.scope_keys() & principal.scopes
            )
            if not global_scope and not owned:
                return AuthorizationDecision(False, "RESOURCE_SCOPE_DENIED", self.policy.sha256)
        if permission in HIGH_RISK_PERMISSIONS and approval_id is None:
            return AuthorizationDecision(
                False,
                "APPROVAL_REQUIRED",
                self.policy.sha256,
                approval_required=True,
            )
        return AuthorizationDecision(True, "ALLOW", self.policy.sha256)

    def require(
        self,
        principal: AuthorizationPrincipal,
        permission: Permission,
        *,
        resource: ResourceContext | None = None,
        approval_id: str | None = None,
    ) -> AuthorizationDecision:
        decision = self.decide(
            principal,
            permission,
            resource=resource,
            approval_id=approval_id,
        )
        if not decision.allowed:
            raise SecurityPolicyError(decision.code, permission.value)
        return decision


__all__ = [
    "AuthorizationDecision",
    "AuthorizationPrincipal",
    "AuthorizationService",
    "HighRiskRule",
    "POLICY_SCHEMA",
    "ResourceContext",
    "SecurityPolicy",
    "SecurityPolicyError",
    "load_security_policy",
]
