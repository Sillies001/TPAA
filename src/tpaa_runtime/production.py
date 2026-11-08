"""PRCB production composition root with explicit durable infrastructure."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from fastapi import FastAPI

from tpaa_api.desktop import create_desktop_app
from tpaa_api.m8_app import M8PrincipalResolver
from tpaa_api.m9_app import M9PrincipalResolver
from tpaa_api.unified import UnifiedPrincipalResolver, create_unified_service_app
from tpaa_application import (
    ApplicationService,
    BatchEventsApplicationService,
    BatchImportService,
    CoAttackApplicationService,
    ED2UpperProductService,
    GetStorageBaselineStatus,
    GuiGatewayService,
    HistoricalOverviewApplicationService,
    M4WorkspaceService,
    M6WorkspaceService,
    M7AircraftContextAdapter,
    M7WorkspaceService,
    M8WorkspaceService,
    M9WorkspaceService,
    ReplayContextApplicationService,
    SecurityAuditSink,
    SourceWorkflowService,
    W7ExternalCapabilityRegistry,
    WeaponEventApplicationError,
    WeaponEventApplicationService,
    build_trusted_runtime_status_use_case,
)
from tpaa_longitudinal import M4LongitudinalPublicationService
from tpaa_qualification import W9FinalQualificationStatus, load_m5_qualification_authority
from tpaa_security import (
    ApiAuthorizationGuard,
    ApprovalService,
    AuthorizationService,
    HttpsJwksProvider,
    JsonRevocationRegistry,
    MtlsCertificateVerifier,
    MtlsConfiguration,
    OidcConfiguration,
    OidcTokenVerifier,
    ResourceContext,
    load_security_policy,
)
from tpaa_storage import (
    SERVICE_WRITE_GATE_LOCK_ID,
    LocalObjectStore,
    ObjectStore,
    PostgreSQLMigrationService,
    PostgreSQLServiceUnitOfWork,
    SQLiteDesktopUnitOfWork,
    SQLiteMigrationService,
)

from .admission import ProductAdmissionResolver, ProductFeatureAvailability
from .approval_repository import (
    ApprovalExecutionValidator,
    PersistentApprovalEventRepository,
)
from .config import ProductionRuntimeConfig, RuntimeProfile
from .consistency import desktop_write_quiescence_lock
from .durable_batch import DurableBatchRepository
from .durable_batch_events import DurableBatchEventSource
from .durable_co_attack import DurableCoAttackSource
from .durable_discovery import DurableProductDiscovery
from .durable_episode import DurableEpisodeRevisionService
from .durable_historical_overview import DurableHistoricalOverviewAdapter
from .durable_longitudinal import (
    DurableM4DebriefRepository,
    DurableM4LongitudinalReleaseRepository,
)
from .durable_p1 import DurableP1ReleaseReadService
from .durable_repositories import (
    DurableM6P2RuntimeRepository,
    DurableM7P3RuntimeRepository,
    DurableM8AssessmentRuntimeRepository,
    DurableM9P6RuntimeRepository,
    RuntimeCanonicalUnitOfWork,
    RuntimeUnitOfWorkFactory,
)
from .durable_weapon_event import DurableWeaponEventReadAdapter
from .ed2_upper_repository import DurableED2UpperProductRepository
from .federated_identity import (
    OidcMtlsRequestIdentityProvider,
    oidc_mtls_principal_resolver,
)
from .formal_evidence import load_formal_runtime_evidence
from .g5_activation import validate_g5_activation
from .g6_activation import validate_g6_activation
from .g7_activation import validate_g7_activation
from .g8_activation import validate_g8_activation
from .g9_activation import validate_g9_activation
from .g10_activation import validate_g10_activation
from .g11_activation import validate_g11_activation
from .g12_activation import validate_g12_activation
from .gui_capabilities import resolve_gui_capabilities
from .identity import (
    configured_service_principal_resolver,
    guard_production_principal_resolver,
)
from .observability import PRCBOperationalStatus, PRCBQualificationStatus
from .operational_metrics import CachedOperationalMetrics, ProductionOperationalMetrics
from .readiness import ProductionDependencyProbe, ProductionRuntimeReadiness
from .security_audit import (
    ApplicationApiAuthorizationAudit,
    PostgreSQLSecurityAuditSink,
    SQLiteSecurityAuditSink,
    WeaponEventSecurityAuditAdapter,
)
from .w8_operations import W8OperationsStatus


@dataclass(frozen=True, slots=True)
class ProductionRuntime:
    """One production-only Application runtime with no in-memory product authority."""

    config: ProductionRuntimeConfig
    admission: ProductAdmissionResolver
    feature_availability: ProductFeatureAvailability
    application: ApplicationService
    service_principal_resolver: UnifiedPrincipalResolver | None
    authorization_guard: ApiAuthorizationGuard
    approval_service: ApprovalService


_WEAPON_EVENT_PATH = re.compile(r"^/api/v1/gui/weapon-events/([^/]+)(?:/.*)?$")


@dataclass(frozen=True, slots=True)
class _WeaponEventResourceResolver:
    application: ApplicationService

    def resolve(self, method: str, path: str) -> ResourceContext | None:
        if method != "GET":
            return None
        match = _WEAPON_EVENT_PATH.fullmatch(path)
        if match is None:
            return None
        weapon_event_id = match.group(1)
        try:
            scope = self.application.weapon_event().resource_scope(weapon_event_id)
        except WeaponEventApplicationError as exc:
            if exc.code != "WEAPON_EVENT_NOT_FOUND":
                raise
            return ResourceContext(
                resource_type="WEAPON_EVENT",
                resource_id=weapon_event_id,
                weapon_event_id=weapon_event_id,
            )
        return ResourceContext(
            resource_type="WEAPON_EVENT",
            resource_id=scope.weapon_event_id,
            weapon_event_id=scope.weapon_event_id,
            batch_id=scope.batch_id,
            release_id=scope.release_id,
            context_id=scope.context_id,
        )


def _validate_storage_status(
    application_status: GetStorageBaselineStatus,
    *,
    authority_root: Path,
) -> None:
    status = application_status.execute()
    lock_path = authority_root.parent / "BASELINE_LOCK.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    baseline = lock.get("baseline")
    if not isinstance(baseline, dict):
        raise RuntimeError("production baseline lock is invalid")
    expected_schema = baseline.get("db_schema")
    logical_model = json.loads(
        (authority_root / "CORE_LOGICAL_MODEL.json").read_text(encoding="utf-8")
    )
    expected_core = logical_model.get("core_baseline")
    if not isinstance(expected_schema, str) or not isinstance(expected_core, str):
        raise RuntimeError("production baseline identity is invalid")
    if status.schema_version != expected_schema:
        raise RuntimeError(
            "production storage schema mismatch "
            f"expected={expected_schema} observed={status.schema_version}"
        )
    if status.core_baseline != expected_core:
        raise RuntimeError(
            "production Core baseline mismatch "
            f"expected={expected_core} observed={status.core_baseline}"
        )


def _compose(
    config: ProductionRuntimeConfig,
    *,
    read_uow_factory: RuntimeUnitOfWorkFactory,
    write_uow_factory: RuntimeUnitOfWorkFactory,
) -> ProductionRuntime:
    object_store: ObjectStore = config.object_store or LocalObjectStore(config.object_root)
    object_store.ensure_ready()

    storage_status = GetStorageBaselineStatus(read_uow_factory)
    _validate_storage_status(storage_status, authority_root=config.authority_root)

    admission = ProductAdmissionResolver()
    from .durable_jobs import DurableApplicationJobControl, ProductionJobExecutor

    job_executor = ProductionJobExecutor(
        authority_root=config.authority_root,
        write_uow_factory=write_uow_factory,
        object_store=object_store,
    )
    job_control = DurableApplicationJobControl(
        read_uow_factory=read_uow_factory,
        write_uow_factory=write_uow_factory,
        executor=job_executor,
    )
    p1_release_reads = DurableP1ReleaseReadService(
        read_uow_factory,
        production_compute_configured=True,
        object_store=object_store,
    )
    m4_workspace = M4WorkspaceService(
        longitudinal=M4LongitudinalPublicationService(
            DurableM4LongitudinalReleaseRepository(
                read_uow_factory,
                authority_root=config.authority_root,
            )
        ),
        debrief=DurableM4DebriefRepository(
            read_uow_factory,
            write_uow_factory,
        ),
    )
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
    audit_sink: SecurityAuditSink
    if config.profile is RuntimeProfile.DESKTOP:
        assert config.desktop_database_path is not None
        audit_sink = SQLiteSecurityAuditSink(
            config.desktop_database_path,
            authority_root=config.authority_root,
            write_consistency_lock=desktop_write_quiescence_lock(config.object_root),
        )
    else:
        assert config.service_conninfo is not None
        audit_sink = PostgreSQLSecurityAuditSink(
            config.service_conninfo,
            authority_root=config.authority_root,
        )

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

    service_principal_resolver: UnifiedPrincipalResolver | None = None
    if config.profile is RuntimeProfile.SERVICE:
        if config.service_identity is not None:
            identity_config = config.service_identity
            revocations = JsonRevocationRegistry(identity_config.revocation_file)
            policy = load_security_policy()
            service_principal_resolver = oidc_mtls_principal_resolver(
                OidcMtlsRequestIdentityProvider(
                    oidc=OidcTokenVerifier(
                        OidcConfiguration(
                            issuer=identity_config.issuer,
                            audience=identity_config.audience,
                        ),
                        HttpsJwksProvider(identity_config.jwks_uri),
                        revocations,
                    ),
                    mtls=MtlsCertificateVerifier(
                        MtlsConfiguration(
                            ca_certificate_pem=identity_config.ca_bundle_path.read_bytes(),
                            allowed_spiffe_prefixes=(identity_config.allowed_spiffe_prefixes),
                        ),
                        revocations,
                    ),
                    policy=policy,
                )
            )
        elif config.service_principals:
            service_principal_resolver = configured_service_principal_resolver(
                config.service_principals
            )

    configured = {
        "P1": True,
        "P2": True,
        "P3": True,
        "P4": True,
        "P5": True,
        "P6": True,
    }
    baseline_lock = json.loads(
        (config.authority_root.parent / "BASELINE_LOCK.json").read_text(encoding="utf-8")
    )
    baseline_identity = baseline_lock.get("baseline")
    migration_target_schema = (
        baseline_identity.get("db_schema")
        if isinstance(baseline_identity, dict)
        else None
    )
    if not isinstance(migration_target_schema, str):
        raise RuntimeError("production migration target is missing from baseline lock")
    core_model = json.loads(
        (config.authority_root / "CORE_LOGICAL_MODEL.json").read_text(encoding="utf-8")
    )
    expected_storage_core = core_model.get("core_baseline")
    if not isinstance(expected_storage_core, str):
        raise RuntimeError("production storage Core is missing from logical model")
    migration_authority_root = config.authority_root.parents[2] / "migrations" / "authority"
    if config.profile is RuntimeProfile.DESKTOP:
        assert config.desktop_database_path is not None
        desktop_migration = SQLiteMigrationService(
            config.desktop_database_path,
            current_authority_root=config.authority_root,
            migration_authority_root=migration_authority_root,
            target_schema_version=migration_target_schema,
        )

        def migration_ready() -> bool:
            status = desktop_migration.status()
            return status.verified and status.at_head

    else:
        assert config.service_conninfo is not None
        state_root = config.migration_state_root or (config.object_root.parent / ".tpaa-migrations")
        service_migration = PostgreSQLMigrationService(
            config.service_conninfo,
            state_root=state_root,
            current_authority_root=config.authority_root,
            migration_authority_root=migration_authority_root,
            target_schema_version=migration_target_schema,
        )
        migration_ready = service_migration.ready
    dependency_probe = ProductionDependencyProbe(
        storage_status=storage_status,
        object_root=config.object_root,
        object_store=object_store,
        identity_ready=(
            config.profile is RuntimeProfile.DESKTOP or service_principal_resolver is not None
        ),
        migration_ready=migration_ready,
        expected_schema_version=migration_target_schema,
        expected_core_baseline=expected_storage_core,
    )
    feature_availability = ProductFeatureAvailability(
        admission,
        configured=configured,
        dependency_ready=dependency_probe.phase_flags,
    )
    qualification_status = PRCBQualificationStatus(
        feature_availability=feature_availability,
        profile=config.profile,
        product_build_version=config.product_build_version,
    )
    base_operational_metrics = ProductionOperationalMetrics(
        profile=config.profile,
        read_uow_factory=read_uow_factory,
        object_root=config.object_root,
        object_store=config.object_store,
        desktop_database=config.desktop_database_path,
    )
    operational_metrics = (
        CachedOperationalMetrics(base_operational_metrics)
        if config.profile is RuntimeProfile.SERVICE
        else base_operational_metrics
    )
    core_runtime_status = build_trusted_runtime_status_use_case(
        product_build_version=config.product_build_version,
        authority_root=config.authority_root,
    )
    ed2_upper = ED2UpperProductService(
        DurableED2UpperProductRepository(
            read_uow_factory,
            write_uow_factory,
        )
    )
    m5_authority = load_m5_qualification_authority(config.authority_root.parent)
    formal_evidence = (
        None
        if config.formal_qualification is None
        else load_formal_runtime_evidence(
            config.formal_qualification,
            authority=m5_authority,
        )
    )
    source_workflow = SourceWorkflowService(object_store)
    gui_capabilities = resolve_gui_capabilities(config.authority_root)
    g4_active = "G4" in gui_capabilities.active
    g5_active = "G5" in gui_capabilities.active
    g6_active = "G6" in gui_capabilities.active
    g7_active = "G7" in gui_capabilities.active
    g8_active = "G8" in gui_capabilities.active
    g9_active = "G9" in gui_capabilities.active
    _ = "G10" in gui_capabilities.active  # G10 adds no new service; gate validated below
    _ = "G11" in gui_capabilities.active  # G11 hardening adds no new service
    _ = "G12" in gui_capabilities.active  # G12 design freeze adds no new service
    weapon_event_audit = WeaponEventSecurityAuditAdapter(audit_sink)
    _ = weapon_event_audit
    weapon_event_service = (
        WeaponEventApplicationService(
            adapter=DurableWeaponEventReadAdapter(read_uow_factory),
            capability_enabled=True,
            adapter_ready=True,
        )
        if g5_active
        else None
    )
    product_discovery = DurableProductDiscovery(read_uow_factory)
    application = ApplicationService(
        get_storage_baseline_status=storage_status,
        job_control=job_control,
        get_runtime_baseline_status=ProductionRuntimeReadiness(
            core_runtime_status,
            feature_availability,
        ),
        m1_publication=p1_release_reads,
        m4_workspace=m4_workspace,
        m6_workspace=m6_workspace,
        m7_workspace=m7_workspace,
        m8_workspace=m8_workspace,
        m9_workspace=m9_workspace,
        product_discovery=product_discovery,
        feature_availability=feature_availability,
        qualification_status=qualification_status,
        operational_status=PRCBOperationalStatus(
            qualification_status,
            metrics=operational_metrics,
        ),
        gui_gateway=GuiGatewayService(core_baseline=gui_capabilities.core_baseline),
        ed2_upper=ed2_upper,
        source_workflow=source_workflow,
        batch_import=(
            BatchImportService(
                DurableBatchRepository(read_uow_factory, write_uow_factory),
                source_workflow,
            )
            if g4_active
            else None
        ),
        weapon_event=weapon_event_service,
        historical_overview=(
            HistoricalOverviewApplicationService(
                adapter=DurableHistoricalOverviewAdapter(read_uow_factory),
                capability_enabled=True,
                adapter_ready=True,
            )
            if g6_active
            else None
        ),
        batch_events=(
            BatchEventsApplicationService(
                adapter=DurableBatchEventSource(read_uow_factory),
                capability_enabled=True,
                adapter_ready=True,
            )
            if g7_active
            else None
        ),
        co_attack=(
            CoAttackApplicationService(
                adapter=DurableCoAttackSource(read_uow_factory),
                capability_enabled=True,
                adapter_ready=True,
            )
            if g8_active
            else None
        ),
        replay_context=(
            ReplayContextApplicationService(
                weapon_event_service,
                presentation_source=product_discovery,
            )
            if g9_active and weapon_event_service is not None
            else None
        ),
        episode_revision=DurableEpisodeRevisionService(write_uow_factory),
        w7_external_capabilities=(
            W7ExternalCapabilityRegistry.local_closed()
            if formal_evidence is None
            else formal_evidence.w7_external_capabilities
        ),
        w8_operations_status=(
            W8OperationsStatus.local_closed(m5_authority)
            if formal_evidence is None
            else formal_evidence.w8_operations_status
        ),
        w9_final_qualification_status=(
            W9FinalQualificationStatus.local_closed()
            if formal_evidence is None
            else formal_evidence.w9_final_qualification_status
        ),
    )
    policy = load_security_policy()
    authorization = AuthorizationService(policy)
    approval_service = ApprovalService(
        authorization,
        PersistentApprovalEventRepository(read_uow_factory, write_uow_factory),
    )
    # Read-only gate: any mismatch raises before a ProductionRuntime or HTTP app is published.
    validate_g5_activation(gui_capabilities, application)
    validate_g6_activation(gui_capabilities, application)
    validate_g7_activation(gui_capabilities, application)
    validate_g8_activation(gui_capabilities, application)
    validate_g9_activation(gui_capabilities, application)
    validate_g10_activation(gui_capabilities, application)
    validate_g11_activation(gui_capabilities, application)
    validate_g12_activation(gui_capabilities, application)
    return ProductionRuntime(
        config=config,
        admission=admission,
        feature_availability=feature_availability,
        application=application,
        service_principal_resolver=service_principal_resolver,
        authorization_guard=ApiAuthorizationGuard(
            authorization,
            audit=ApplicationApiAuthorizationAudit(audit_sink),
            approval_validator=ApprovalExecutionValidator(approval_service),
            resource_resolver=_WeaponEventResourceResolver(application),
        ),
        approval_service=approval_service,
    )


def build_desktop_production_runtime(
    config: ProductionRuntimeConfig,
) -> ProductionRuntime:
    """Compose production Desktop over DB 1.9 SQLite and local object storage."""

    if config.profile is not RuntimeProfile.DESKTOP:
        raise ValueError("Desktop production composition requires DESKTOP profile")
    assert config.desktop_database_path is not None
    database = config.desktop_database_path

    def read_uow() -> RuntimeCanonicalUnitOfWork:
        return cast(
            RuntimeCanonicalUnitOfWork,
            SQLiteDesktopUnitOfWork(
                database,
                authority_root=config.authority_root,
            ),
        )

    def write_uow() -> RuntimeCanonicalUnitOfWork:
        return cast(
            RuntimeCanonicalUnitOfWork,
            SQLiteDesktopUnitOfWork(
                database,
                write=True,
                authority_root=config.authority_root,
                write_consistency_lock=desktop_write_quiescence_lock(config.object_root),
            ),
        )

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

    def read_uow() -> RuntimeCanonicalUnitOfWork:
        return cast(
            RuntimeCanonicalUnitOfWork,
            PostgreSQLServiceUnitOfWork(
                conninfo,
                read_only=True,
                authority_root=config.authority_root,
            ),
        )

    def write_uow() -> RuntimeCanonicalUnitOfWork:
        return cast(
            RuntimeCanonicalUnitOfWork,
            PostgreSQLServiceUnitOfWork(
                conninfo,
                write_gate_lock_id=SERVICE_WRITE_GATE_LOCK_ID,
                authority_root=config.authority_root,
            ),
        )

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
    principal_resolver: UnifiedPrincipalResolver | None = None,
    desktop_nonce: str | None = None,
) -> FastAPI:
    """Expose the production Desktop graph without synthetic source fallback."""

    app = create_desktop_app(
        application=runtime.application,
        bearer_token=bearer_token,
        m8_principal_resolver=m8_principal_resolver,
        m9_principal_resolver=m9_principal_resolver,
        principal_resolver=principal_resolver,
        authorization_guard=runtime.authorization_guard,
        approval_service=runtime.approval_service,
        desktop_nonce=desktop_nonce,
    )
    app.version = runtime.config.product_build_version
    return app


def create_production_service_app(
    runtime: ProductionRuntime,
    *,
    principal_resolver: UnifiedPrincipalResolver | None = None,
) -> FastAPI:
    """Expose Service through configured or injected least-privilege identity."""

    selected = principal_resolver or runtime.service_principal_resolver
    if selected is None:
        raise ValueError("production Service identity provider is not configured")
    app = create_unified_service_app(
        application=runtime.application,
        principal_resolver=guard_production_principal_resolver(selected),
        authorization_guard=runtime.authorization_guard,
        approval_service=runtime.approval_service,
    )
    app.version = runtime.config.product_build_version
    return app
