"""M9 Batch 3 frozen P6 runtime role/privacy/release enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

from .m8_p4_p5 import pseudonymous_subject_key
from .p6_governance import P6AuthorityPolicy, P6GovernanceError, exact_text, exact_uuid

_ROLE_PROFILE_ID = "P6_ROLE_PRIVACY_RELEASE_PROFILE"


@dataclass(frozen=True, slots=True)
class P6RoleRule:
    role: str
    projection_read_scope: str
    direct_actor_id: bool | str
    model_metadata_read: bool | str
    model_release: bool
    forecast_run: bool | str
    counterfactual_run: bool | str
    recommendation_approval: bool
    interop_export: bool | str
    audit_read: bool | str


@dataclass(frozen=True, slots=True)
class P6RuntimeSecurityPolicy:
    profile_sha256: str
    profile_id: str
    profile_version: str
    p6_authority_sha256: str
    role_rules: tuple[P6RoleRule, ...]
    recommendation_approval_role: str
    model_release_role: str
    request_id_required: bool
    duplicate_request_id_idempotent: bool
    unrestricted_log_exclusions: tuple[str, ...]

    @classmethod
    def from_canonical(
        cls,
        loader: CanonicalArtifactLoader | None = None,
    ) -> "P6RuntimeSecurityPolicy":
        canonical = loader or CanonicalArtifactLoader()
        try:
            profile = canonical.load(
                _ROLE_PROFILE_ID,
                expectation=ArtifactExpectation(
                    version="1.0.0",
                    schema_version="1.6.0",
                    required_top_level_keys=(
                        "source_bindings",
                        "scope",
                        "role_matrix",
                        "projection_contract",
                        "write_authorization_contract",
                        "release_approval_contract",
                        "export_audit_contract",
                    ),
                ),
            )
        except Exception as exc:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_AUTHORITY_REQUIRED",
                str(exc),
            ) from exc
        root = dict(profile.payload)
        bindings = root.get("source_bindings")
        write = root.get("write_authorization_contract")
        projection = root.get("projection_contract")
        release = root.get("release_approval_contract")
        export = root.get("export_audit_contract")
        scope = root.get("scope")
        rows = root.get("role_matrix")
        if (
            not isinstance(bindings, dict)
            or not isinstance(write, dict)
            or not isinstance(projection, dict)
            or not isinstance(release, dict)
            or not isinstance(export, dict)
            or not isinstance(scope, dict)
            or not isinstance(rows, list)
        ):
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_AUTHORITY_REQUIRED",
                "P6 role/privacy profile structure",
            )
        authority = P6AuthorityPolicy.from_canonical(canonical)
        if (
            bindings.get("p6_authority_sha256") != authority.authority_sha256
            or root.get("profile_id") != _ROLE_PROFILE_ID
            or root.get("version") != "1.0.0"
            or scope.get("default_deny") is not True
            or write.get("recommendation_approval_role")
            != "INSTRUCTOR_EVALUATOR"
            or write.get("model_release_role") != "MODEL_REVIEWER"
            or write.get("request_id_required") is not True
            or write.get("duplicate_request_id_idempotent") is not True
            or write.get("admin_auditor_business_approval_by_privilege_forbidden")
            is not True
            or write.get("admin_auditor_model_release_by_privilege_forbidden")
            is not True
            or release.get(
                "model_release_and_recommendation_release_are_distinct"
            )
            is not True
            or release.get(
                "recommendation_release_requires_approved_source_projection_refs"
            )
            is not True
            or release.get("release_does_not_convert_projection_to_fact")
            is not True
            or export.get("interop_export_requires_explicit_authorization")
            is not True
            or export.get("unrestricted_export_of_direct_identity_forbidden")
            is not True
        ):
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_AUTHORITY_REQUIRED",
                "P6 role/privacy profile drift",
            )
        rules: list[P6RoleRule] = []
        for raw in rows:
            if not isinstance(raw, dict):
                raise P6GovernanceError(
                    "FAIL_CLOSED_P6_AUTHORITY_REQUIRED",
                    "P6 role row",
                )
            rules.append(
                P6RoleRule(
                    role=cast(str, raw["role"]),
                    projection_read_scope=cast(str, raw["projection_read_scope"]),
                    direct_actor_id=cast(bool | str, raw["direct_actor_id"]),
                    model_metadata_read=cast(
                        bool | str,
                        raw["model_metadata_read"],
                    ),
                    model_release=bool(raw["model_release"]),
                    forecast_run=cast(bool | str, raw["forecast_run"]),
                    counterfactual_run=cast(
                        bool | str,
                        raw["counterfactual_run"],
                    ),
                    recommendation_approval=bool(
                        raw["recommendation_approval"]
                    ),
                    interop_export=cast(bool | str, raw["interop_export"]),
                    audit_read=cast(bool | str, raw["audit_read"]),
                )
            )
        exclusions = projection.get("unrestricted_client_logs_must_exclude")
        if not isinstance(exclusions, list) or not all(
            isinstance(item, str) and item for item in exclusions
        ):
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_AUTHORITY_REQUIRED",
                "unrestricted log exclusions",
            )
        return cls(
            profile_sha256=profile.sha256,
            profile_id=_ROLE_PROFILE_ID,
            profile_version="1.0.0",
            p6_authority_sha256=authority.authority_sha256,
            role_rules=tuple(rules),
            recommendation_approval_role="INSTRUCTOR_EVALUATOR",
            model_release_role="MODEL_REVIEWER",
            request_id_required=write.get("request_id_required") is True,
            duplicate_request_id_idempotent=(
                write.get("duplicate_request_id_idempotent") is True
            ),
            unrestricted_log_exclusions=tuple(cast(list[str], exclusions)),
        )

    def role_rule(self, role: str) -> P6RoleRule:
        for rule in self.role_rules:
            if rule.role == role:
                return rule
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_AUTHORITY_REQUIRED",
            f"unknown P6 role={role!r}",
        )


@dataclass(frozen=True, slots=True)
class P6SecurityViewer:
    role: str
    actor_id: str | None
    scope_match: bool
    validation_only: bool = False
    privileged_identity_authorized: bool = False
    export_authorized: bool = False


@dataclass(frozen=True, slots=True)
class P6SecurityAuditEvent:
    principal_key: str
    action: str
    object_ref: str
    outcome: str
    request_id: str | None


def p6_principal_key(
    viewer: P6SecurityViewer,
    *,
    policy: P6RuntimeSecurityPolicy | None = None,
) -> str:
    q = policy or P6RuntimeSecurityPolicy.from_canonical()
    q.role_rule(viewer.role)
    if viewer.actor_id is None:
        return f"ROLE:{viewer.role}"
    exact_uuid(
        viewer.actor_id,
        field="viewer.actor_id",
        policy=P6AuthorityPolicy.from_canonical(),
    )
    return pseudonymous_subject_key(viewer.actor_id)


def assert_p6_permission(
    viewer: P6SecurityViewer,
    action: str,
    *,
    policy: P6RuntimeSecurityPolicy | None = None,
) -> None:
    q = policy or P6RuntimeSecurityPolicy.from_canonical()
    rule = q.role_rule(viewer.role)
    if not viewer.scope_match:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_AUTHORITY_REQUIRED",
            f"{viewer.role}:{action}:scope",
        )
    permission: bool | str
    if action == "MODEL_RELEASE":
        permission = rule.model_release
    elif action == "FORECAST_RUN":
        permission = rule.forecast_run
    elif action == "COUNTERFACTUAL_RUN":
        permission = rule.counterfactual_run
    elif action == "RECOMMENDATION_APPROVAL":
        permission = rule.recommendation_approval
    elif action == "INTEROP_EXPORT":
        permission = rule.interop_export
    elif action == "AUDIT_READ":
        permission = rule.audit_read
    else:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_AUTHORITY_REQUIRED",
            f"unknown P6 action={action!r}",
        )
    allowed = permission is True
    if permission == "VALIDATION_ONLY":
        allowed = viewer.validation_only
    elif permission == "EXPLICIT_EXPORT_AUTHORIZATION_REQUIRED":
        allowed = viewer.export_authorized
    elif isinstance(permission, str) and action == "AUDIT_READ":
        allowed = True
    if not allowed:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_AUTHORITY_REQUIRED",
            f"{viewer.role}:{action}:denied",
        )


def project_p6_subject_id(
    subject_id: str,
    viewer: P6SecurityViewer,
    *,
    policy: P6RuntimeSecurityPolicy | None = None,
) -> str | None:
    q = policy or P6RuntimeSecurityPolicy.from_canonical()
    p = P6AuthorityPolicy.from_canonical()
    exact_uuid(subject_id, field="subject_id", policy=p)
    if viewer.actor_id is not None:
        exact_uuid(viewer.actor_id, field="viewer.actor_id", policy=p)
    rule = q.role_rule(viewer.role)
    permission = rule.direct_actor_id
    allowed = False
    if viewer.scope_match:
        if permission is True:
            allowed = True
        elif permission == "OWN_ONLY":
            allowed = viewer.actor_id == subject_id
        elif permission == "ASSIGNED_SCOPE_ONLY":
            allowed = True
        elif permission == "AUTHORIZED_AUDIT_SCOPE_ONLY":
            allowed = viewer.privileged_identity_authorized
    return subject_id if allowed else None


def assert_safe_request_id(
    request_id: str,
    *,
    policy: P6RuntimeSecurityPolicy | None = None,
) -> str:
    q = policy or P6RuntimeSecurityPolicy.from_canonical()
    if not q.request_id_required:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_AUTHORITY_REQUIRED",
            "request-id requirement drift",
        )
    return exact_text(
        request_id,
        field="request_id",
        policy=P6AuthorityPolicy.from_canonical(),
    )
