from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tpaa_security import (
    ApprovalError,
    ApprovalService,
    ApprovalStatus,
    AuthorizationPrincipal,
    AuthorizationService,
    BreakGlassService,
    DataClassification,
    InMemoryApprovalEventRepository,
    InMemoryPrivacyAuditSink,
    InMemoryVersionedSecretManager,
    Permission,
    PrivacyService,
    ResourceContext,
    SecretMaterial,
    SecurityRole,
    load_security_policy,
)

NOW = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)


def _principal(subject: str, role: SecurityRole) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        subject=subject,
        roles=frozenset({role}),
        scopes=frozenset({"resource:SESSION:S-1"}),
        authentication_method="TEST",
        credential_id=f"credential-{subject}",
    )


def test_role_matrix_default_deny_scope_and_high_risk_approval() -> None:
    authorization = AuthorizationService(load_security_policy())
    trainee = _principal("trainee", SecurityRole.TRAINEE)
    scoped = ResourceContext(resource_type="SESSION", resource_id="S-1")

    assert authorization.decide(
        trainee, Permission.DERIVED_DATA_READ, resource=scoped
    ).allowed
    assert not authorization.decide(trainee, Permission.RAW_DATA_READ, resource=scoped).allowed
    assert not authorization.decide(
        AuthorizationPrincipal(
            subject="scopeless",
            roles=frozenset({SecurityRole.INSTRUCTOR}),
            scopes=frozenset(),
            authentication_method="TEST",
            credential_id="scopeless",
        ),
        Permission.RAW_DATA_READ,
        resource=scoped,
    ).allowed
    decision = authorization.decide(
        _principal("reviewer", SecurityRole.MODEL_REVIEWER),
        Permission.MODEL_RELEASE,
    )
    assert decision.code == "APPROVAL_REQUIRED"
    assert decision.approval_required


def test_maker_checker_inbox_exact_target_and_one_time_consumption() -> None:
    authorization = AuthorizationService(load_security_policy())
    approvals = ApprovalService(authorization, InMemoryApprovalEventRepository())
    maker = _principal("maker", SecurityRole.INSTRUCTOR)
    checker = _principal("checker", SecurityRole.EVALUATOR)
    target = {"path": "/api/v1/releases/publish"}

    request = approvals.request(
        maker,
        Permission.PUBLICATION_OVERRIDE,
        target_type="API_PATH",
        target_id=str(target["path"]),
        target=target,
        reason="correct an approved instructor finding",
        now=NOW,
    )
    assert request.status is ApprovalStatus.PENDING
    assert approvals.inbox(checker, now=NOW) == (request,)

    with pytest.raises(ApprovalError, match="MAKER_CHECKER_COLLISION"):
        approvals.decide(
            maker,
            request.approval_id,
            approve=True,
            reason="self approval",
            now=NOW,
        )
    approved = approvals.decide(
        checker,
        request.approval_id,
        approve=True,
        reason="evidence reviewed",
        now=NOW,
    )
    assert approved.status is ApprovalStatus.APPROVED
    with pytest.raises(ApprovalError, match="APPROVAL_TARGET_MISMATCH"):
        approvals.consume(
            maker,
            request.approval_id,
            permission=Permission.PUBLICATION_OVERRIDE,
            target_type="API_PATH",
            target_id=str(target["path"]),
            target={"path": "/tampered"},
            now=NOW,
        )
    consumed = approvals.consume(
        maker,
        request.approval_id,
        permission=Permission.PUBLICATION_OVERRIDE,
        target_type="API_PATH",
        target_id=str(target["path"]),
        target=target,
        now=NOW,
    )
    assert consumed.status is ApprovalStatus.CONSUMED
    with pytest.raises(ApprovalError, match="APPROVAL_NOT_USABLE"):
        approvals.consume(
            maker,
            request.approval_id,
            permission=Permission.PUBLICATION_OVERRIDE,
            target_type="API_PATH",
            target_id=str(target["path"]),
            target=target,
            now=NOW,
        )


def test_deidentified_export_manifest_audit_and_retention_conflict() -> None:
    authorization = AuthorizationService(load_security_policy())
    audit = InMemoryPrivacyAuditSink()
    privacy = PrivacyService(
        authorization,
        InMemoryVersionedSecretManager(
            {
                "pseudonym": (
                    SecretMaterial(
                        value=b"test-key-with-rotation-metadata",
                        key_id="pseudonym-key",
                        version="v1",
                    ),
                )
            }
        ),
        pseudonym_key_reference="secret://pseudonym/v1",
        audit=audit,
    )
    exported, manifest = privacy.export(
        _principal("instructor", SecurityRole.INSTRUCTOR),
        {"actor_id": "person-123", "score": 0.82},
        resource=ResourceContext(resource_type="SESSION", resource_id="S-1"),
        classification=DataClassification.OPERATIONAL,
        purpose="training-review",
        tenant="unit-a",
        identified=False,
        retention_until=NOW + timedelta(days=30),
        media_redaction_status="REDACTED",
        now=NOW,
    )
    assert exported == {
        "actor_id_pseudonym": privacy.pseudonymize(
            "person-123", purpose="training-review", tenant="unit-a"
        ),
        "score": 0.82,
    }
    assert manifest.deidentified
    assert manifest.policy_sha256 == authorization.policy.sha256
    assert manifest.redacted_fields == ("actor_id",)
    assert audit.events[0][0] == "DATA_EXPORT"

    held = privacy.retention_decision(
        expired=True,
        legal_hold=False,
        release_references=("release-1",),
        requested_action="DELETE",
    )
    assert held.action == "ARCHIVE"
    assert held.code == "RELEASE_REFERENCE_PRESERVED"
    assert not held.physical_delete_allowed


def test_break_glass_is_admin_only_short_lived_and_policy_limited() -> None:
    authorization = AuthorizationService(load_security_policy())
    repository = InMemoryApprovalEventRepository()
    break_glass = BreakGlassService(authorization, repository)
    administrator = _principal("incident-admin", SecurityRole.ADMINISTRATOR)

    grant = break_glass.issue(
        administrator,
        Permission.PRODUCT_PUBLISH,
        target_id="release-emergency-1",
        ticket="INC-2026-001",
        reason="restore an interrupted approved release",
        ttl=timedelta(minutes=15),
        now=NOW,
    )
    assert grant.expires_at == NOW + timedelta(minutes=15)
    assert repository.events(grant.grant_id)[0].event_type == "BREAK_GLASS_ISSUED"

    with pytest.raises(ApprovalError, match="BREAK_GLASS_ROLE_DENIED"):
        break_glass.issue(
            _principal("instructor", SecurityRole.INSTRUCTOR),
            Permission.PRODUCT_PUBLISH,
            target_id="release-emergency-1",
            ticket="INC-2026-002",
            reason="not an administrator",
            ttl=timedelta(minutes=15),
            now=NOW,
        )
    with pytest.raises(ApprovalError, match="BREAK_GLASS_PERMISSION_DENIED"):
        break_glass.issue(
            administrator,
            Permission.PLUGIN_INSTALL,
            target_id="plugin-1",
            ticket="INC-2026-003",
            reason="plugin installation is never an emergency grant",
            ttl=timedelta(minutes=15),
            now=NOW,
        )


def test_non_global_wildcard_scope_is_denied_but_exact_scope_is_allowed() -> None:
    authorization = AuthorizationService(load_security_policy())
    resource = ResourceContext(resource_type="SESSION", resource_id="S-1")
    wildcard = AuthorizationPrincipal(
        subject="wildcard-instructor",
        roles=frozenset({SecurityRole.INSTRUCTOR}),
        scopes=frozenset({"*"}),
        authentication_method="TEST",
        credential_id="wildcard-instructor",
    )
    exact = AuthorizationPrincipal(
        subject="exact-instructor",
        roles=frozenset({SecurityRole.INSTRUCTOR}),
        scopes=frozenset({"resource:SESSION:S-1"}),
        authentication_method="TEST",
        credential_id="exact-instructor",
    )

    denied = authorization.decide(wildcard, Permission.RAW_DATA_READ, resource=resource)
    allowed = authorization.decide(exact, Permission.RAW_DATA_READ, resource=resource)

    assert denied.allowed is False
    assert denied.code == "RESOURCE_SCOPE_WILDCARD_DENIED"
    assert allowed.allowed is True
    assert allowed.code == "ALLOW"
