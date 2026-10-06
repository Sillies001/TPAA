"""TPAA PIQB product runtime composition."""

from .admission import (
    AdmissionRecord,
    FeatureAvailabilityState,
    ProductAdmissionResolver,
    ProductFeatureAvailability,
)
from .composition import (
    ProductRuntime,
    build_desktop_application,
    build_service_application,
    create_full_desktop_app,
    create_full_service_app,
)
from .config import (
    ProductionPrincipalBinding,
    ProductionRuntimeConfig,
    ProductRuntimeConfig,
    RuntimeProfile,
)
from .identity import (
    ConfiguredBearerIdentityProvider,
    ProductionIdentityError,
    guard_production_principal_resolver,
)
from .observability import ProductOperationalStatus, ProductQualificationStatus
from .persistence import (
    DesktopPersistenceConfig,
    ProductPersistenceRuntime,
    ServicePersistenceConfig,
    build_desktop_persistence,
    build_service_persistence,
)
from .readiness import ProductionDependencyProbe, ProductionRuntimeReadiness
from .production import (
    ProductionRuntime,
    build_desktop_production_runtime,
    build_service_production_runtime,
    create_production_desktop_app,
    create_production_service_app,
)
from .security_audit import PostgreSQLSecurityAuditSink, SQLiteSecurityAuditSink

__all__ = [
    "ConfiguredBearerIdentityProvider",
    "ProductOperationalStatus",
    "ProductQualificationStatus",
    "PostgreSQLSecurityAuditSink",
    "SQLiteSecurityAuditSink",
    "AdmissionRecord",
    "DesktopPersistenceConfig",
    "FeatureAvailabilityState",
    "ProductAdmissionResolver",
    "ProductFeatureAvailability",
    "ProductPersistenceRuntime",
    "ProductRuntime",
    "ProductionDependencyProbe",
    "ProductionIdentityError",
    "ProductionPrincipalBinding",
    "ProductionRuntime",
    "ProductionRuntimeConfig",
    "ProductionRuntimeReadiness",
    "ProductRuntimeConfig",
    "RuntimeProfile",
    "ServicePersistenceConfig",
    "build_desktop_application",
    "build_desktop_production_runtime",
    "build_desktop_persistence",
    "build_service_application",
    "build_service_production_runtime",
    "build_service_persistence",
    "create_full_desktop_app",
    "create_full_service_app",
    "create_production_desktop_app",
    "create_production_service_app",
    "guard_production_principal_resolver",
]
