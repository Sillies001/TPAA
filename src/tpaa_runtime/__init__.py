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
from .config import ProductRuntimeConfig, RuntimeProfile
from .persistence import (
    DesktopPersistenceConfig,
    ProductPersistenceRuntime,
    ServicePersistenceConfig,
    build_desktop_persistence,
    build_service_persistence,
)

__all__ = [
    "AdmissionRecord",
    "DesktopPersistenceConfig",
    "FeatureAvailabilityState",
    "ProductAdmissionResolver",
    "ProductFeatureAvailability",
    "ProductPersistenceRuntime",
    "ProductRuntime",
    "ProductRuntimeConfig",
    "RuntimeProfile",
    "ServicePersistenceConfig",
    "build_desktop_application",
    "build_desktop_persistence",
    "build_service_application",
    "build_service_persistence",
    "create_full_desktop_app",
    "create_full_service_app",
]
