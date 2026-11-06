from __future__ import annotations

import pytest

from tpaa_application import GuiGatewayError, GuiGatewayPrincipal, GuiGatewayService
from tpaa_security import SecurityRole, derive_gui_permissions, load_security_policy


def _principal(role: SecurityRole, *, subject: str = "g3-subject") -> GuiGatewayPrincipal:
    policy = load_security_policy()
    permissions = policy.role_permissions[role]
    return GuiGatewayPrincipal(
        subject=subject,
        roles=(role.value,),
        gui_permissions=derive_gui_permissions((role,), permissions),
        resource_scopes=("release:allowed",),
    )


def test_catalog_filters_views_by_approved_role_permissions() -> None:
    gateway = GuiGatewayService()
    trainee = gateway.catalog(_principal(SecurityRole.TRAINEE), request_id="trainee")
    administrator = gateway.catalog(
        _principal(SecurityRole.ADMINISTRATOR), request_id="administrator"
    )

    assert len(trainee["views"]) == 23
    assert len(administrator["views"]) == 26
    assert trainee["provenance"] == {
        "authority_id": "GUI_ASYNC_GATEWAY_AUTHORITY",
        "authority_version": "1.0.0",
        "core_baseline": "CB-1.8.0",
        "activation_status": "ACTIVE",
    }
    assert all("required_permissions" in view for view in administrator["views"])


def test_bootstrap_redacts_subject_and_uses_distinct_principal_partitions() -> None:
    gateway = GuiGatewayService()
    first = gateway.bootstrap(
        _principal(SecurityRole.ADMINISTRATOR, subject="actor-a"), request_id="a"
    )
    second = gateway.bootstrap(
        _principal(SecurityRole.ADMINISTRATOR, subject="actor-b"), request_id="b"
    )

    assert first["cache_partition_key"] != second["cache_partition_key"]
    assert "actor-a" not in repr(first)
    assert first["principal"]["resource_scope_count"] == 1
    assert "resource_scopes" not in first["principal"]


def test_selector_paginates_with_context_bound_opaque_cursor() -> None:
    gateway = GuiGatewayService()
    principal = _principal(SecurityRole.ADMINISTRATOR)
    first = gateway.selector(
        principal,
        "views",
        request_id="page-1",
        release_id="release-a",
        limit=7,
    )
    assert len(first["items"]) == 7
    assert first["total_count"] == 26
    assert isinstance(first["next_cursor"], str)

    second = gateway.selector(
        principal,
        "views",
        request_id="page-2",
        release_id="release-a",
        cursor=first["next_cursor"],
        limit=7,
    )
    assert len(second["items"]) == 7
    assert first["items"] != second["items"]

    with pytest.raises(GuiGatewayError, match="CURSOR_INVALID"):
        gateway.selector(
            principal,
            "views",
            request_id="wrong-release",
            release_id="release-b",
            cursor=first["next_cursor"],
            limit=7,
        )
    with pytest.raises(GuiGatewayError, match="CURSOR_INVALID"):
        gateway.selector(
            _principal(SecurityRole.ADMINISTRATOR, subject="other"),
            "views",
            request_id="wrong-principal",
            release_id="release-a",
            cursor=first["next_cursor"],
            limit=7,
        )


def test_pre_g4_dynamic_selector_never_fabricates_business_values() -> None:
    result = GuiGatewayService().selector(
        _principal(SecurityRole.ADMINISTRATOR),
        "batches",
        request_id="dynamic",
        limit=50,
    )
    assert result["items"] == []
    assert result["total_count"] == 0
    assert result["next_cursor"] is None
    assert result["reason_code"] == "CONTEXT_REQUIRED"


def test_unknown_selector_and_invalid_cursor_fail_closed() -> None:
    gateway = GuiGatewayService()
    principal = _principal(SecurityRole.ADMINISTRATOR)
    with pytest.raises(GuiGatewayError, match="NOT_FOUND") as unknown:
        gateway.selector(principal, "unknown", request_id="unknown")
    assert unknown.value.http_status == 404
    with pytest.raises(GuiGatewayError, match="CURSOR_INVALID"):
        gateway.selector(
            principal,
            "views",
            request_id="tampered",
            cursor="not-a-valid-cursor",
        )
