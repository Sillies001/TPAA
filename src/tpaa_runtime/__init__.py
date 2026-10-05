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
from .config import ProductionRuntimeConfig, ProductRuntimeConfig, RuntimeProfile
from .observability import ProductOperationalStatus, ProductQualificationStatus
from .production import (
    ProductionRuntime,
    build_desktop_production_runtime,
    build_service_production_runtime,
    create_production_desktop_app,
    create_production_service_app,
)
from .persistence import (
    DesktopPersistenceConfig,
    ProductPersistenceRuntime,
    ServicePersistenceConfig,
    build_desktop_persistence,
    build_service_persistence,
)
from .security_audit import PostgreSQLSecurityAuditSink, SQLiteSecurityAuditSink

__all__ = [
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
    "ProductionRuntime",
    "ProductionRuntimeConfig",
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
]
