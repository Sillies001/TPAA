from __future__ import annotations

from tpaa_security import (
    ApiAuthorizationGuard,
    AuthorizationPrincipal,
    AuthorizationService,
    InMemoryApiAuthorizationAudit,
    ResourceContext,
    SecurityRole,
    load_security_policy,
    route_permission,
)


def test_route_classification_covers_reads_writes_and_high_risk_actions() -> None:
    assert route_permission("GET", "/health") is None
    assert route_permission("GET", "/api/v1/source/items").value == "RAW_DATA_READ"
    assert route_permission("POST", "/jobs").value == "COMPUTE_EXECUTE"
    assert (
        route_permission("POST", "/m1/releases/exact-release-id/replay").value
        == "COMPUTE_EXECUTE"
    )
    assert (
        route_permission("POST", "/api/v1/releases/publish").value
        == "PRODUCT_PUBLISH"
    )
    assert (
        route_permission("POST", "/plugins/install").value == "PLUGIN_INSTALL"
    )


def test_negative_authorization_is_audited_without_direct_subject() -> None:
    audit = InMemoryApiAuthorizationAudit()
    guard = ApiAuthorizationGuard(
        AuthorizationService(load_security_policy()), audit=audit
    )
    trainee = AuthorizationPrincipal(
        subject="direct-person-identifier",
        roles=frozenset({SecurityRole.TRAINEE}),
        scopes=frozenset({"*"}),
        authentication_method="TEST",
        credential_id="credential",
    )
    decision = guard.authorize(
        trainee,
        method="POST",
        path="/plugins/install",
    )
    assert not decision.allowed
    assert decision.code == "PERMISSION_DENIED"
    assert audit.events[0].allowed is False
    assert audit.events[0].permission == "PLUGIN_INSTALL"
    assert audit.events[0].subject.startswith("SUBJECT_SHA256:")
    assert "direct-person-identifier" not in audit.events[0].subject


class _FailingAudit:
    def record(self, event) -> None:  # type: ignore[no-untyped-def]
        raise RuntimeError("persistent audit unavailable")


def _scoped_instructor() -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        subject="instructor-1",
        roles=frozenset({SecurityRole.INSTRUCTOR}),
        scopes=frozenset({"resource:RELEASE:release-1"}),
        authentication_method="TEST",
        credential_id="credential-instructor-1",
    )


def test_allowed_sensitive_read_and_mutation_are_always_audited() -> None:
    audit = InMemoryApiAuthorizationAudit()
    guard = ApiAuthorizationGuard(
        AuthorizationService(load_security_policy()), audit=audit
    )
    principal = _scoped_instructor()
    resource = ResourceContext(resource_type="RELEASE", resource_id="release-1")

    read = guard.authorize(
        principal,
        method="GET",
        path="/m1/releases/release-1",
        resource=resource,
    )
    mutation = guard.authorize(
        principal,
        method="POST",
        path="/m4/debrief/annotations",
        resource=resource,
    )

    assert read.allowed is True
    assert mutation.allowed is True
    assert [event.permission for event in audit.events] == [
        "DERIVED_DATA_READ",
        "ANNOTATION_WRITE",
    ]
    assert all(event.allowed for event in audit.events)


def test_audit_write_failure_denies_an_otherwise_authorized_operation() -> None:
    guard = ApiAuthorizationGuard(
        AuthorizationService(load_security_policy()), audit=_FailingAudit()
    )
    decision = guard.authorize(
        _scoped_instructor(),
        method="GET",
        path="/m1/releases/release-1",
        resource=ResourceContext(resource_type="RELEASE", resource_id="release-1"),
    )

    assert decision.allowed is False
    assert decision.code == "AUDIT_WRITE_FAILED"
