"""Single fail-closed policy for currently admitted production principals.

This module deliberately preserves the existing five-role production boundary.
It reports, but does not grant, Canonical/design permissions that still require
an approved role-mapping decision.
"""

from __future__ import annotations

from enum import StrEnum


class ProductionRole(StrEnum):
    SUBJECT_SELF = "SUBJECT_SELF"
    INSTRUCTOR_EVALUATOR = "INSTRUCTOR_EVALUATOR"
    TEAM_LEAD = "TEAM_LEAD"
    ANALYST = "ANALYST"
    ADMIN_AUDITOR = "ADMIN_AUDITOR"


class ProductPermission(StrEnum):
    DIRECT_IDENTITY_READ = "DIRECT_IDENTITY_READ"
    ANNOTATION_BODY_READ = "ANNOTATION_BODY_READ"
    INTEROP_EXPORT = "INTEROP_EXPORT"
    ASSESSMENT_APPROVE = "ASSESSMENT_APPROVE"
    RECOMMENDATION_APPROVE = "RECOMMENDATION_APPROVE"
    MODEL_RELEASE = "MODEL_RELEASE"
    PRODUCT_PUBLISH = "PRODUCT_PUBLISH"
    PUBLICATION_OVERRIDE = "PUBLICATION_OVERRIDE"
    PLUGIN_INSTALL = "PLUGIN_INSTALL"


class PrincipalPolicyError(ValueError):
    """One principal mapping violates the admitted production policy."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


_RESTRICTED_ROLES = frozenset(
    {ProductionRole.TEAM_LEAD, ProductionRole.ANALYST}
)


def production_role(value: str | ProductionRole) -> ProductionRole:
    try:
        return ProductionRole(value)
    except ValueError as exc:
        raise PrincipalPolicyError(
            "ROLE_NOT_AUTHORIZED",
            "production role is not in frozen role family",
        ) from exc


def validate_production_principal_policy(
    *,
    role: str | ProductionRole,
    privileged_identity_authorized: bool,
    visibility_authorized: bool,
    export_authorized: bool,
) -> ProductionRole:
    """Validate the existing role/explicit-grant envelope without expansion."""

    selected = production_role(role)
    if selected in _RESTRICTED_ROLES and (
        privileged_identity_authorized
        or visibility_authorized
        or export_authorized
    ):
        raise PrincipalPolicyError(
            "ROLE_PRIVILEGE_ESCALATION",
            "role cannot receive configured identity, visibility, or export privilege",
        )
    if selected is not ProductionRole.ADMIN_AUDITOR and export_authorized:
        raise PrincipalPolicyError(
            "EXPORT_PRIVILEGE_ESCALATION",
            "role cannot receive export privilege",
        )
    return selected


def permission_governance_status() -> dict[str, object]:
    """Return a secret-free diagnostic; this function grants no permission."""

    return {
        "schema": "TPAA_PERMISSION_GOVERNANCE_STATUS_V1",
        "status": "PARTIAL",
        "admitted_production_roles": [role.value for role in ProductionRole],
        "explicit_deployment_grants": [
            ProductPermission.DIRECT_IDENTITY_READ.value,
            ProductPermission.ANNOTATION_BODY_READ.value,
            ProductPermission.INTEROP_EXPORT.value,
        ],
        "canonical_policy_actions": [
            ProductPermission.ASSESSMENT_APPROVE.value,
            ProductPermission.RECOMMENDATION_APPROVE.value,
        ],
        "canonical_roles_not_admitted_for_production": ["MODEL_REVIEWER"],
        "unwired_high_risk_permissions": [
            ProductPermission.MODEL_RELEASE.value,
            ProductPermission.PRODUCT_PUBLISH.value,
            ProductPermission.PUBLICATION_OVERRIDE.value,
            ProductPermission.PLUGIN_INSTALL.value,
        ],
        "design_role_mapping": "PRODUCT_DECISION_REQUIRED",
        "default_decision": "DENY",
    }


__all__ = [
    "PrincipalPolicyError",
    "ProductPermission",
    "ProductionRole",
    "permission_governance_status",
    "production_role",
    "validate_production_principal_policy",
]
