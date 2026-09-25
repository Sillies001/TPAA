"""TPAA Desktop GUI transport shell and local-backend lifecycle."""

from .desktop import run_desktop
from .diagnostics import DiagnosticsIdentity, DiagnosticsSnapshot, diagnostics_lines
from .local_backend import (
    LocalBackendController,
    LocalBackendError,
    LocalBackendState,
    LocalBackendStatus,
)
from .m1_workspace import M1DesktopTransport, M1WorkspaceError, create_m1_workspace
from .shell import PYSIDE6_DEPENDENCY_MISSING, GuiShellConfig, GuiShellError, run_gui

__all__ = [
    "PYSIDE6_DEPENDENCY_MISSING",
    "DiagnosticsIdentity",
    "DiagnosticsSnapshot",
    "GuiShellConfig",
    "GuiShellError",
    "LocalBackendController",
    "LocalBackendError",
    "LocalBackendState",
    "LocalBackendStatus",
    "M1DesktopTransport",
    "M1WorkspaceError",
    "create_m1_workspace",
    "diagnostics_lines",
    "run_desktop",
    "run_gui",
]
