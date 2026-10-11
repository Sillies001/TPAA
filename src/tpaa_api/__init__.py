"""TPAA FastAPI transport adapters."""

from .app import create_app, register_base_routes
from .desktop import create_desktop_app
from .ed2_upper import register_ed2_upper_routes
from .m1_app import create_m1_app, register_m1_routes
from .m3_app import create_m3_app, register_m3_routes
from .m4_app import create_m4_app, register_m4_routes
from .m5_secure import M5ServiceSecurityError, create_m5_service_app
from .m6_app import create_m6_app, register_m6_routes
from .m7_app import create_m7_app, register_m7_routes
from .m8_app import M8PrincipalResolver, create_m8_app, register_m8_routes
from .m9_app import M9PrincipalResolver, create_m9_app, register_m9_routes
from .product_v1 import (
    PRODUCT_API_AUTHORITY_SHA256,
    PRODUCT_API_VERSION,
    ProductV1Authority,
    ProductV1Envelope,
    register_product_v1_routes,
)
from .runtime import register_product_runtime_routes
from .unified import (
    UnifiedPrincipal,
    UnifiedPrincipalResolver,
    create_unified_service_app,
    register_unified_routes,
)

__all__ = [
    "register_ed2_upper_routes",
    "M5ServiceSecurityError",
    "M8PrincipalResolver",
    "M9PrincipalResolver",
    "UnifiedPrincipal",
    "UnifiedPrincipalResolver",
    "create_app",
    "create_desktop_app",
    "create_m1_app",
    "create_m3_app",
    "create_m4_app",
    "create_m5_service_app",
    "create_m6_app",
    "create_m7_app",
    "create_m8_app",
    "create_m9_app",
    "create_unified_service_app",
    "register_base_routes",
    "register_m1_routes",
    "register_m3_routes",
    "register_m4_routes",
    "register_m6_routes",
    "register_m7_routes",
    "register_m8_routes",
    "register_m9_routes",
    "PRODUCT_API_AUTHORITY_SHA256",
    "PRODUCT_API_VERSION",
    "ProductV1Authority",
    "ProductV1Envelope",
    "register_product_v1_routes",
    "register_product_runtime_routes",
    "register_unified_routes",
]
