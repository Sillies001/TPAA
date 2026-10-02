"""PIQB B1 production composition root for Desktop and Service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Never, cast

from fastapi import FastAPI

from tpaa_api.app import create_app
from tpaa_api.desktop import create_desktop_app
from tpaa_api.m1_app import register_m1_routes
from tpaa_api.m3_app import register_m3_routes
from tpaa_api.m4_app import register_m4_routes
from tpaa_api.m6_app import register_m6_routes
from tpaa_api.m7_app import register_m7_routes
from tpaa_api.m8_app import M8PrincipalResolver, register_m8_routes
from tpaa_api.m9_app import M9PrincipalResolver, register_m9_routes
from tpaa_api.runtime import register_product_runtime_routes
from tpaa_application import (
    ApplicationService,
    GetStorageBaselineStatus,
    InMemoryM3ReleasePublicationRepository,
    InMemoryM4DebriefRepository,
    InMemoryM6P2WorkspaceRepository,
    InMemoryM7P3WorkspaceRepository,
    InMemoryM8AssessmentRepository,
    InMemoryM9P6Repository,
    M1PublicationService,
    M3PublicationService,
    M4WorkspaceService,
    M6WorkspaceService,
    M7AircraftContextAdapter,
    M7WorkspaceService,
    M8WorkspaceService,
    M9WorkspaceService,
    build_trusted_runtime_status_use_case,
)
from tpaa_application.m1_repository import InMemorySessionPublicationRepository
from tpaa_longitudinal import (
    InMemoryM4LongitudinalReleaseRepository,
    M4LongitudinalPublicationService,
)

from .admission import ProductAdmissionResolver, ProductFeatureAvailability
from .config import ProductRuntimeConfig, RuntimeProfile


class _UnavailableStorageBaseline:
    def execute(self) -> Never:
        raise RuntimeError(
            "product storage baseline is not configured before PIQB B2 persistence"
        )


@dataclass(frozen=True, slots=True)
class ProductRuntime:
    """One fully composed Application runtime with swappable infrastructure edges."""

    config: ProductRuntimeConfig
    admission: ProductAdmissionResolver
    feature_availability: ProductFeatureAvailability
    application: ApplicationService


def _build(config: ProductRuntimeConfig) -> ProductRuntime:
    admission = ProductAdmissionResolver()

    m1_publication = (
        None
        if config.m1_fixture_root is None
        else M1PublicationService(
            fixture_root=config.m1_fixture_root,
            authority_root=config.authority_root,
            repository=InMemorySessionPublicationRepository(),
        )
    )

    m3_publication = M3PublicationService(
        InMemoryM3ReleasePublicationRepository()
    )
    m4_longitudinal = M4LongitudinalPublicationService(
        InMemoryM4LongitudinalReleaseRepository()
    )
    m4_workspace = M4WorkspaceService(
        longitudinal=m4_longitudinal,
        debrief=InMemoryM4DebriefRepository(),
    )
    m6_workspace = M6WorkspaceService(InMemoryM6P2WorkspaceRepository())
    m7_workspace = M7WorkspaceService(
        InMemoryM7P3WorkspaceRepository(),
        admission_evidence=admission.p3_evidence(),
    )
    m8_workspace = M8WorkspaceService(
        InMemoryM8AssessmentRepository(),
        admission_evidence=admission.m8_evidence(),
        aircraft_context=M7AircraftContextAdapter(m7_workspace),
    )
    m9_workspace = M9WorkspaceService(
        InMemoryM9P6Repository(),
        admission_evidence=admission.p6_evidence(),
    )

    configured = {
        "P1": m1_publication is not None,
        "P2": True,
        "P3": True,
        "P4": True,
        "P5": True,
        "P6": True,
    }
    feature_availability = ProductFeatureAvailability(
        admission,
        configured=configured,
    )
    application = ApplicationService(
        get_storage_baseline_status=cast(
            GetStorageBaselineStatus,
            _UnavailableStorageBaseline(),
        ),
        get_runtime_baseline_status=build_trusted_runtime_status_use_case(
            product_build_version=config.product_build_version
        ),
        m1_publication=m1_publication,
        m3_publication=m3_publication,
        m4_workspace=m4_workspace,
        m6_workspace=m6_workspace,
        m7_workspace=m7_workspace,
        m8_workspace=m8_workspace,
        m9_workspace=m9_workspace,
        feature_availability=feature_availability,
    )
    return ProductRuntime(
        config=config,
        admission=admission,
        feature_availability=feature_availability,
        application=application,
    )


def build_desktop_application(config: ProductRuntimeConfig) -> ProductRuntime:
    """Compose the Desktop Application graph without direct GUI/DB coupling."""

    if config.profile is not RuntimeProfile.DESKTOP:
        raise ValueError("Desktop composition requires RuntimeProfile.DESKTOP")
    return _build(config)


def build_service_application(config: ProductRuntimeConfig) -> ProductRuntime:
    """Compose the Service Application graph with the same business core."""

    if config.profile is not RuntimeProfile.SERVICE:
        raise ValueError("Service composition requires RuntimeProfile.SERVICE")
    return _build(config)


def create_full_desktop_app(
    runtime: ProductRuntime,
    *,
    bearer_token: str,
    m8_principal_resolver: M8PrincipalResolver | None = None,
    m9_principal_resolver: M9PrincipalResolver | None = None,
) -> FastAPI:
    """Expose every currently admitted Application surface on the Desktop backend."""

    return create_desktop_app(
        application=runtime.application,
        bearer_token=bearer_token,
        m8_principal_resolver=m8_principal_resolver,
        m9_principal_resolver=m9_principal_resolver,
    )


def create_full_service_app(
    runtime: ProductRuntime,
    *,
    m8_principal_resolver: M8PrincipalResolver,
    m9_principal_resolver: M9PrincipalResolver,
) -> FastAPI:
    """Expose the same P1-P6 Application graph through one Service process."""

    app = create_app(runtime.application)
    register_product_runtime_routes(app, runtime.application)
    register_m1_routes(app, runtime.application)
    register_m3_routes(app, runtime.application)
    register_m4_routes(app, runtime.application)
    register_m6_routes(app, runtime.application)
    register_m7_routes(app, runtime.application)
    register_m8_routes(
        app,
        runtime.application,
        principal_resolver=m8_principal_resolver,
    )
    register_m9_routes(
        app,
        runtime.application,
        principal_resolver=m9_principal_resolver,
    )
    return app
