"""TPAA Desktop GUI transport shell and local-backend lifecycle."""

from .desktop import run_desktop
from .local_backend import LocalBackendController, LocalBackendError, LocalBackendState, LocalBackendStatus
from .shell import PYSIDE6_DEPENDENCY_MISSING, GuiShellConfig, GuiShellError, run_gui

__all__ = [
    "PYSIDE6_DEPENDENCY_MISSING",
    "GuiShellConfig",
    "GuiShellError",
    "LocalBackendController",
    "LocalBackendError",
    "LocalBackendState",
    "LocalBackendStatus",
    "run_desktop",
    "run_gui",
]
