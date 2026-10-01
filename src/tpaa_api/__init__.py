"""TPAA FastAPI transport adapters."""

from .app import create_app
from .desktop import create_desktop_app
from .m1_app import create_m1_app
from .m3_app import create_m3_app
from .m4_app import create_m4_app
from .m5_secure import M5ServiceSecurityError, create_m5_service_app
from .m6_app import create_m6_app, register_m6_routes
from .m7_app import create_m7_app, register_m7_routes

__all__ = [
    "create_app",
    "create_desktop_app",
    "create_m1_app",
    "create_m3_app",
    "create_m4_app",
    "M5ServiceSecurityError",
    "create_m6_app",
    "register_m6_routes",
    "create_m7_app",
    "register_m7_routes",
    "create_m5_service_app",
]
