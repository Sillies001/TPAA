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

__all__ = [
    "AdmissionRecord",
    "FeatureAvailabilityState",
    "ProductAdmissionResolver",
    "ProductFeatureAvailability",
    "ProductRuntime",
    "ProductRuntimeConfig",
    "RuntimeProfile",
    "build_desktop_application",
    "build_service_application",
    "create_full_desktop_app",
    "create_full_service_app",
]
