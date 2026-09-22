"""TPAA FastAPI transport adapters."""

from .app import create_app
from .desktop import create_desktop_app

__all__ = ["create_app", "create_desktop_app"]
