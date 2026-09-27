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
from .m2_workspace import (
    M2_OBSERVATION_LANE_COUNTS,
    M2_OBSERVATION_LANE_PRESENTATION,
    M2_PRESENTATION_STATE_STYLES,
    M2_RESULT_STATUSES,
    M2FoundationNavigationError,
    M2FoundationNavigationItem,
    M2FoundationNavigationModel,
    M2MetricPresentationState,
    build_m2_foundation_navigation_model,
    build_m2_metric_presentation_state,
    create_m2_foundation_workspace,
)
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
    "M2_OBSERVATION_LANE_COUNTS",
    "M2_OBSERVATION_LANE_PRESENTATION",
    "M2_PRESENTATION_STATE_STYLES",
    "M2_RESULT_STATUSES",
    "M2FoundationNavigationError",
    "M2FoundationNavigationItem",
    "M2FoundationNavigationModel",
    "M2MetricPresentationState",
    "build_m2_foundation_navigation_model",
    "build_m2_metric_presentation_state",
    "create_m1_workspace",
    "create_m2_foundation_workspace",
    "diagnostics_lines",
    "run_desktop",
    "run_gui",
]
