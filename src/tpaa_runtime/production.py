"""PRCB production composition root with explicit durable infrastructure."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI

from tpaa_api.desktop import create_desktop_app
from tpaa_api.m8_app import M8PrincipalResolver
from tpaa_api.m9_app import M9PrincipalResolver
from tpaa_api.unified import UnifiedPrincipalResolver, create_unified_service_app
from tpaa_application import (
    ApplicationService,
    GetStorageBaselineStatus,
    M6WorkspaceService,
    M7AircraftContextAdapter,
    M7WorkspaceService,
    M8WorkspaceService,
    M9WorkspaceService,
    build_trusted_runtime_status_use_case,
)
from tpaa_storage import (
    LocalObjectStore,
    PostgreSQLServiceUnitOfWork,
    SQLiteDesktopUnitOfWork,
)

from .admission import ProductAdmissionResolver, ProductFeatureAvailability
from .config import ProductionRuntimeConfig, RuntimeProfile
from .durable_repositories import (
    DurableM6P2RuntimeRepository,
    DurableM7P3RuntimeRepository,
    DurableM8AssessmentRuntimeRepository,
    DurableM9P6RuntimeRepository,
    RuntimeUnitOfWorkFactory,
)
from .observability import ProductOperationalStatus, ProductQualificationStatus
from .security_audit import PostgreSQLSecurityAuditSink, SQLiteSecurityAuditSink


@dataclass(frozen=True, slots=True)
class ProductionRuntime:
    """One production-only Application runtime with no in-memory product authority."""

    config: ProductionRuntimeConfig
    admission: ProductAdmissionResolver
    feature_availability: ProductFeatureAvailability
    application: ApplicationService


def _validate_storage_status(
    application_status: GetStorageBaselineStatus,
) -> None:
    status = application_status.execute()
    if status.schema_version != "1.9.0":
        raise RuntimeError(
            "production storage schema mismatch "
            f"expected=1.9.0 observed={status.schema_version}"
        )
    if status.core_baseline != "CB-1.4.0":
        raise RuntimeError(
            "production Core baseline mismatch "
            f"expected=CB-1.4.0 observed={status.core_baseline}"
        )


def _compose(
    config: ProductionRuntimeConfig,
    *,
    read_uow_factory: RuntimeUnitOfWorkFactory,
    write_uow_factory: RuntimeUnitOfWorkFactory,
) -> ProductionRuntime:
    object_store = LocalObjectStore(config.object_root)
    object_store.filesystem.ensure_root()

    storage_status = GetStorageBaselineStatus(read_uow_factory)
    _validate_storage_status(storage_status)

    admission = ProductAdmissionResolver()
    m6_workspace = M6WorkspaceService(
        DurableM6P2RuntimeRepository(
            read_uow_factory,
            object_store=object_store,
        )
    )
    m7_workspace = M7WorkspaceService(
        DurableM7P3RuntimeRepository(
            read_uow_factory,
            object_store=object_store,
        ),
        admission_evidence=admission.p3_evidence(),
    )
    if config.profile is RuntimeProfile.DESKTOP:
        assert config.desktop_database_path is not None
        audit_sink = SQLiteSecurityAuditSink(config.desktop_database_path)
    else:
        assert config.service_conninfo is not None
        audit_sink = PostgreSQLSecurityAuditSink(config.service_conninfo)

    m8_workspace = M8WorkspaceService(
        DurableM8AssessmentRuntimeRepository(
            read_uow_factory,
            write_uow_factory,
        ),
        admission_evidence=admission.m8_evidence(),
        aircraft_context=M7AircraftContextAdapter(m7_workspace),
        security_audit_sink=audit_sink,
    )
    m9_workspace = M9WorkspaceService(
        DurableM9P6RuntimeRepository(
            read_uow_factory,
            write_uow_factory,
            object_store=object_store,
        ),
        admission_evidence=admission.p6_evidence(),
        security_audit_sink=audit_sink,
    )

    configured = {
        "P1": False,
        "P2": True,
        "P3": True,
        "P4": True,
        "P5": True,
        "P6": True,
    }
    dependency_ready = {
        "P1": False,
        "P2": True,
        "P3": True,
        "P4": True,
        "P5": True,
        "P6": True,
    }
    feature_availability = ProductFeatureAvailability(
        admission,
        configured=configured,
        dependency_ready=dependency_ready,
    )
    qualification_status = ProductQualificationStatus(
        feature_availability=feature_availability,
        profile=config.profile,
        product_build_version=config.product_build_version,
    )
    application = ApplicationService(
        get_storage_baseline_status=storage_status,
        get_runtime_baseline_status=build_trusted_runtime_status_use_case(
            product_build_version=config.product_build_version
        ),
        m6_workspace=m6_workspace,
        m7_workspace=m7_workspace,
        m8_workspace=m8_workspace,
        m9_workspace=m9_workspace,
        feature_availability=feature_availability,
        qualification_status=qualification_status,
        operational_status=ProductOperationalStatus(qualification_status),
    )
    return ProductionRuntime(
        config=config,
        admission=admission,
        feature_availability=feature_availability,
        application=application,
    )


def build_desktop_production_runtime(
    config: ProductionRuntimeConfig,
) -> ProductionRuntime:
    """Compose production Desktop over DB 1.9 SQLite and local object storage."""

    if config.profile is not RuntimeProfile.DESKTOP:
        raise ValueError("Desktop production composition requires DESKTOP profile")
    assert config.desktop_database_path is not None
    database = config.desktop_database_path

    def read_uow() -> SQLiteDesktopUnitOfWork:
        return SQLiteDesktopUnitOfWork(database)

    def write_uow() -> SQLiteDesktopUnitOfWork:
        return SQLiteDesktopUnitOfWork(database, write=True)

    return _compose(
        config,
        read_uow_factory=read_uow,
        write_uow_factory=write_uow,
    )


def build_service_production_runtime(
    config: ProductionRuntimeConfig,
) -> ProductionRuntime:
    """Compose production Service over DB 1.9 PostgreSQL and object storage."""

    if config.profile is not RuntimeProfile.SERVICE:
        raise ValueError("Service production composition requires SERVICE profile")
    assert config.service_conninfo is not None
    conninfo = config.service_conninfo

    def read_uow() -> PostgreSQLServiceUnitOfWork:
        return PostgreSQLServiceUnitOfWork(conninfo, read_only=True)

    def write_uow() -> PostgreSQLServiceUnitOfWork:
        return PostgreSQLServiceUnitOfWork(conninfo)

    return _compose(
        config,
        read_uow_factory=read_uow,
        write_uow_factory=write_uow,
    )


def create_production_desktop_app(
    runtime: ProductionRuntime,
    *,
    bearer_token: str,
    m8_principal_resolver: M8PrincipalResolver | None = None,
    m9_principal_resolver: M9PrincipalResolver | None = None,
) -> FastAPI:
    """Expose the production Desktop graph without synthetic source fallback."""

    app = create_desktop_app(
        application=runtime.application,
        bearer_token=bearer_token,
        m8_principal_resolver=m8_principal_resolver,
        m9_principal_resolver=m9_principal_resolver,
    )
    app.version = runtime.config.product_build_version
    return app


def create_production_service_app(
    runtime: ProductionRuntime,
    *,
    principal_resolver: UnifiedPrincipalResolver,
) -> FastAPI:
    """Expose production Service through one injected authenticated principal resolver."""

    app = create_unified_service_app(
        application=runtime.application,
        principal_resolver=principal_resolver,
    )
    app.version = runtime.config.product_build_version
    return app
