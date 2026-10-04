from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from tpaa_api import (
    UnifiedPrincipal,
    create_desktop_app,
    create_unified_service_app,
)
from tpaa_application import (
    ApplicationService,
    GetRuntimeBaselineStatus,
    JobAudit,
    M0JobControl,
)
from tpaa_canonical import RuntimeBaselineIdentity, evaluate_runtime_baseline_handshake


class _UnusedStorageUseCase:
    def execute(self) -> object:
        raise AssertionError("storage use case must not be called")


def _identity() -> RuntimeBaselineIdentity:
    return RuntimeBaselineIdentity(
        product_build_version="0.0.0",
        core_baseline="CB-1.4.0",
        baseline_lock_sha256="lock",
        db_schema_version="1.9.0",
        core_authority_artifact_id="CORE_LOGICAL_MODEL",
        core_authority_sha256="core",
        p1_metric_catalog_version="1.14.0",
        p1_metric_catalog_sha256="catalog",
        dto_authority_sha256="dto",
    )


def _application(audits: list[JobAudit] | None = None) -> ApplicationService:
    expected = _identity()
    return ApplicationService(
        get_storage_baseline_status=_UnusedStorageUseCase(),  # type: ignore[arg-type]
        get_runtime_baseline_status=GetRuntimeBaselineStatus(
            lambda: evaluate_runtime_baseline_handshake(
                expected=expected,
                observed=replace(expected),
            )
        ),
        job_control=M0JobControl(
            None if audits is None else audits.append
        ),
    )


def _principal() -> UnifiedPrincipal:
    return UnifiedPrincipal(
        role="INSTRUCTOR_EVALUATOR",
        actor_id="11111111-1111-4111-8111-111111111111",
        scope_match=True,
        validation_only=False,
        privileged_identity_authorized=False,
        visibility_authorized=True,
        export_authorized=True,
    )


def test_unified_principal_projects_exactly_into_m8_and_m9_contexts() -> None:
    principal = _principal()

    m8 = principal.m8_viewer()
    assert m8.viewer_role == principal.role
    assert m8.viewer_actor_id == principal.actor_id
    assert m8.scope_match is True
    assert m8.privileged_identity_authorized is False
    assert m8.visibility_authorized is True
    assert m8.export_authorized is True

    m9 = principal.m9_viewer()
    assert m9.role == principal.role
    assert m9.actor_id == principal.actor_id
    assert m9.scope_match is True
    assert m9.validation_only is False
    assert m9.privileged_identity_authorized is False
    assert m9.export_authorized is True


def test_unified_service_requires_principal_and_ignores_spoofed_actor_header() -> None:
    audits: list[JobAudit] = []
    principal = _principal()
    app = create_unified_service_app(
        application=_application(audits),
        principal_resolver=lambda _request: principal,
    )

    with TestClient(app) as client:
        response = client.post(
            "/jobs",
            headers={
                "Idempotency-Key": "b4-job-001",
                "X-TPAA-Actor": "spoofed-client-actor",
            },
            json={"command": "ECHO", "payload": {"value": "alpha"}},
        )

    assert response.status_code == 202
    assert len(audits) == 1
    assert audits[0].actor == principal.actor_id
    assert audits[0].actor != "spoofed-client-actor"


def test_unified_service_fails_closed_when_principal_resolution_fails() -> None:
    def denied(_request):
        raise PermissionError("identity unavailable")

    app = create_unified_service_app(
        application=_application(),
        principal_resolver=denied,
    )
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "PRINCIPAL_RESOLUTION_REQUIRED"


def test_desktop_and_service_share_one_governed_route_graph() -> None:
    principal = _principal()
    application = _application()
    desktop = create_desktop_app(
        application=application,
        bearer_token="b4-desktop-secret",
        m8_principal_resolver=lambda _request: principal.m8_viewer(),
        m9_principal_resolver=lambda _request: principal.m9_viewer(),
    )
    service = create_unified_service_app(
        application=application,
        principal_resolver=lambda _request: principal,
    )

    governed_prefixes = (
        "/jobs",
        "/m1/",
        "/m3/",
        "/m4/",
        "/m6/",
        "/m7/",
        "/m8/",
        "/m9/",
        "/runtime/",
    )

    def governed_paths(app) -> set[str]:
        return {
            route.path
            for route in app.routes
            if hasattr(route, "path")
            and (
                route.path in {"/health", "/readiness", "/version", "/jobs"}
                or any(route.path.startswith(prefix) for prefix in governed_prefixes)
            )
        }

    assert governed_paths(desktop) == governed_paths(service)
