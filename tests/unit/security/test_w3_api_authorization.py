from __future__ import annotations

from tpaa_security import (
    ApiAuthorizationGuard,
    AuthorizationPrincipal,
    AuthorizationService,
    InMemoryApiAuthorizationAudit,
    SecurityRole,
    load_security_policy,
    route_permission,
)


def test_route_classification_covers_reads_writes_and_high_risk_actions() -> None:
    assert route_permission("GET", "/health") is None
    assert route_permission("GET", "/api/v1/source/items").value == "RAW_DATA_READ"
    assert route_permission("POST", "/jobs").value == "COMPUTE_EXECUTE"
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
