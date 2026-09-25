"""TPAA FastAPI transport adapters."""

from .app import create_app
from .desktop import create_desktop_app
from .m1_app import create_m1_app

__all__ = ["create_app", "create_desktop_app", "create_m1_app"]
