"""PIQB B5 production Desktop composition over existing qualified GUI surfaces."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .diagnostics import DiagnosticsSnapshot
from .m1_workspace import create_m1_workspace
from .m3_workspace import M3_GUI_TRAINING_KEYS, create_m3_workspace_navigation
from .m4_workspace import create_m4_workspace
from .m6_workspace import create_m6_workspace
from .m7_workspace import create_m7_workspace
from .m8_workspace import create_m8_workspace
from .m9_workspace import create_m9_workspace
from .visualization import (
    VisualizationPresentationError,
    build_2d_polyline,
    build_cesium_trajectory_packets,
    build_trajectory_presentation,
)


class ProductShellError(RuntimeError):
    """Stable B5 Desktop composition error."""


class ProductDesktopTransport(Protocol):
    def m1_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]: ...

    def m3_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]: ...

    def m4_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
    ) -> tuple[int, dict[str, Any]]: ...

    def m6_request_json(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, object] | None = None,
    ) -> tuple[int, Mapping[str, object]]: ...

    def m7_request_json(
        self,
        method: str,
        path: str,
    ) -> tuple[int, Mapping[str, object]]: ...

    def m8_request_json(
        self,
        method: str,
        path: str,
    ) -> tuple[int, Mapping[str, object]]: ...

    def m9_request_json(
        self,
        method: str,
        path: str,
    ) -> tuple[int, Mapping[str, object]]: ...

    def runtime_request_json(
        self,
        method: str,
        path: str,
    ) -> tuple[int, Mapping[str, object]]: ...


@dataclass(frozen=True, slots=True)
class ProductNavigationItem:
    slot: str
    key: str
    title: str
    surface: str
    semantic_class: str


PRODUCT_NAVIGATION = (
    ProductNavigationItem("P01", "SESSION_RELEASE", "Session / Release", "M1", "C"),
    ProductNavigationItem("P02", "DATA_QUALITY", "Data Quality", "M1/M3", "C"),
    ProductNavigationItem("P03", "METRIC_EVIDENCE", "Metric / Evidence", "M1/M3", "P"),
    ProductNavigationItem("P04", "TRAINING_WORKSPACE", "Training Workspace", "M3", "W"),
    ProductNavigationItem("P05", "LONGITUDINAL_DEBRIEF", "Longitudinal / Debrief", "M4", "J"),
    ProductNavigationItem("P06", "P2_ATTRIBUTION", "P2 Adjusted / Attribution", "M6", "P2"),
    ProductNavigationItem("P07", "P3_TWIN_CAPABILITY", "P3 Twin / Capability", "M7", "P3"),
    ProductNavigationItem(
        "P08",
        "P4_ACTOR_ASSESSMENT",
        "P4 Actor Assessment",
        "M8",
        "ASSESSMENT",
    ),
    ProductNavigationItem(
        "P09",
        "P5_MISSION_ASSESSMENT",
        "P5 Mission Assessment",
        "M8",
        "ASSESSMENT",
    ),
    ProductNavigationItem("P10", "P6_FORECAST", "P6 Forecast", "M9", "P6"),
    ProductNavigationItem(
        "P11",
        "P6_COUNTERFACTUAL",
        "P6 Counterfactual",
        "M9",
        "P6",
    ),
    ProductNavigationItem(
        "P12",
        "P6_RECOMMENDATION",
        "P6 Recommendation",
        "M9",
        "P6",
    ),
    ProductNavigationItem(
        "P13",
        "GOVERNANCE_DIAGNOSTICS",
        "Governance / Diagnostics",
        "Runtime",
        "M",
    ),
)
PRODUCT_SPINE = (
    "session_id",
    "episode_id",
    "stage_id",
    "scope",
    "subject",
    "session_time",
    "release_id",
)
SEMANTIC_LAYERS = ("C", "W", "P", "A", "J", "M", "ASSESSMENT", "P2", "P3", "P6")


def validate_product_navigation() -> None:
    expected_slots = tuple(f"P{index:02d}" for index in range(1, 14))
    slots = tuple(item.slot for item in PRODUCT_NAVIGATION)
    if slots != expected_slots:
        raise ProductShellError("B5_PRODUCT_NAVIGATION_SLOT_MISMATCH")
    keys = tuple(item.key for item in PRODUCT_NAVIGATION)
    if len(set(keys)) != len(keys):
        raise ProductShellError("B5_PRODUCT_NAVIGATION_KEY_DUPLICATE")
    if set(SEMANTIC_LAYERS) != {
        "C",
        "W",
        "P",
        "A",
        "J",
        "M",
        "ASSESSMENT",
        "P2",
        "P3",
        "P6",
    }:
        raise ProductShellError("B5_SEMANTIC_LAYER_SET_INVALID")


def _create_m3_launcher(
    qt_core: Any,
    qt_widgets: Any,
    parent: Any,
    *,
    transport: ProductDesktopTransport,
) -> Any:
    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaB5M3Launcher")
    layout = qt_widgets.QVBoxLayout(root)
    instructions = qt_widgets.QLabel(
        "Bind exact BASIC/WVR/BVR/STRIKE Release IDs. No latest/default fallback.",
        root,
    )
    layout.addWidget(instructions)
    inputs: dict[str, Any] = {}
    for training_key in M3_GUI_TRAINING_KEYS:
        line = qt_widgets.QLineEdit(root)
        line.setObjectName(f"tpaaB5M3{training_key}ReleaseId")
        line.setPlaceholderText(f"Exact {training_key} release UUID")
        layout.addWidget(line)
        inputs[training_key] = line
    load_button = qt_widgets.QPushButton("Load exact training workspaces", root)
    load_button.setObjectName("tpaaB5M3Load")
    status = qt_widgets.QLabel("M3 workspace: waiting for exact Release IDs", root)
    status.setObjectName("tpaaB5M3Status")
    layout.addWidget(load_button)
    layout.addWidget(status)
    state: dict[str, Any] = {"workspace": None}

    def load() -> None:
        release_ids = {
            key: str(widget.text()).strip()
            for key, widget in inputs.items()
        }
        if any(not value for value in release_ids.values()):
            status.setText("M3 workspace: exact Release IDs required")
            return
        previous = state.get("workspace")
        if previous is not None:
            previous.deleteLater()
        workspace = create_m3_workspace_navigation(
            qt_core,
            qt_widgets,
            root,
            transport=transport,
            release_ids_by_training=release_ids,
        )
        workspace.setObjectName("tpaaB5M3Workspace")
        layout.addWidget(workspace)
        state["workspace"] = workspace
        status.setText("M3 workspace: exact Release set loaded")

    load_button.clicked.connect(load)
    return root


def _create_runtime_page(
    qt_widgets: Any,
    parent: Any,
    *,
    transport: ProductDesktopTransport,
) -> Any:
    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaB5RuntimeGovernance")
    layout = qt_widgets.QVBoxLayout(root)
    refresh = qt_widgets.QPushButton("Refresh qualification / observability", root)
    refresh.setObjectName("tpaaB5RuntimeRefresh")
    output = qt_widgets.QPlainTextEdit(root)
    output.setObjectName("tpaaB5RuntimeState")
    output.setReadOnly(True)
    layout.addWidget(refresh)
    layout.addWidget(output)

    def load() -> None:
        qualification_status, qualification = transport.runtime_request_json(
            "GET",
            "/runtime/qualification",
        )
        observability_status, observability = transport.runtime_request_json(
            "GET",
            "/runtime/observability",
        )
        payload = {
            "qualification_http_status": qualification_status,
            "qualification": dict(qualification),
            "observability_http_status": observability_status,
            "observability": dict(observability),
        }
        output.setPlainText(json.dumps(payload, indent=2, sort_keys=True))

    refresh.clicked.connect(load)
    return root


def _create_visualization_page(qt_widgets: Any, parent: Any) -> Any:
    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaB5TrajectoryMedia")
    layout = qt_widgets.QVBoxLayout(root)
    notice = qt_widgets.QLabel(
        "Exact release-bound trajectory/media payload only; unsupported sources remain explicit.",
        root,
    )
    release_id = qt_widgets.QLineEdit(root)
    release_id.setObjectName("tpaaB5TrajectoryReleaseId")
    release_id.setPlaceholderText("Exact Release UUID")
    payload = qt_widgets.QPlainTextEdit(root)
    payload.setObjectName("tpaaB5TrajectoryPayload")
    payload.setPlaceholderText("TPAA_TRAJECTORY_PRESENTATION_V1 JSON")
    render = qt_widgets.QPushButton("Render governed 2D / Cesium-ready presentation", root)
    render.setObjectName("tpaaB5TrajectoryRender")
    output = qt_widgets.QPlainTextEdit(root)
    output.setObjectName("tpaaB5TrajectoryOutput")
    output.setReadOnly(True)
    status = qt_widgets.QLabel(
        "Trajectory/media: unavailable until an exact presentation payload is supplied",
        root,
    )
    status.setObjectName("tpaaB5TrajectoryStatus")
    for widget in (notice, release_id, payload, render, status, output):
        layout.addWidget(widget)

    def render_payload() -> None:
        expected_release_id = release_id.text().strip()
        if not expected_release_id:
            status.setText("Trajectory/media: exact Release ID required")
            return
        try:
            decoded = json.loads(payload.toPlainText())
            if not isinstance(decoded, dict):
                raise VisualizationPresentationError("VIS_ROOT_INVALID")
            presentation = build_trajectory_presentation(
                decoded,
                expected_release_id=expected_release_id,
            )
            result = {
                "release_id": presentation.release_id,
                "sample_count": len(presentation.samples),
                "media_count": len(presentation.media),
                "polyline_2d": build_2d_polyline(presentation),
                "cesium_packets": build_cesium_trajectory_packets(presentation),
            }
        except (json.JSONDecodeError, VisualizationPresentationError) as exc:
            status.setText(f"Trajectory/media: INVALID · {exc}")
            output.clear()
            return
        status.setText("Trajectory/media: exact presentation ready")
        output.setPlainText(json.dumps(result, indent=2, sort_keys=True))

    render.clicked.connect(render_payload)
    return root


def create_product_workspace(
    qt_core: Any,
    qt_widgets: Any,
    parent: Any,
    *,
    transport: ProductDesktopTransport,
    diagnostics_provider: Callable[[], DiagnosticsSnapshot],
) -> Any:
    """Compose P01-P13 over existing qualified transport-only GUI surfaces."""

    validate_product_navigation()
    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaB5ProductWorkspace")
    outer = qt_widgets.QVBoxLayout(root)

    spine = qt_widgets.QLabel("Product spine · " + " / ".join(PRODUCT_SPINE), root)
    spine.setObjectName("tpaaB5ProductSpine")
    semantic = qt_widgets.QLabel("Semantic layers · " + " / ".join(SEMANTIC_LAYERS), root)
    semantic.setObjectName("tpaaB5SemanticLegend")
    outer.addWidget(spine)
    outer.addWidget(semantic)

    body = qt_widgets.QWidget(root)
    body_layout = qt_widgets.QHBoxLayout(body)
    navigation = qt_widgets.QListWidget(body)
    navigation.setObjectName("tpaaB5ProductNavigation")
    stack = qt_widgets.QStackedWidget(body)
    stack.setObjectName("tpaaB5ProductStack")
    body_layout.addWidget(navigation)
    body_layout.addWidget(stack)
    outer.addWidget(body)

    m1 = create_m1_workspace(
        qt_core,
        qt_widgets,
        stack,
        transport=transport,
        diagnostics_provider=diagnostics_provider,
    )
    m3 = _create_m3_launcher(qt_core, qt_widgets, stack, transport=transport)

    m4_tabs = qt_widgets.QTabWidget(stack)
    m4_tabs.setObjectName("tpaaB5LongitudinalVisualTabs")
    m4_tabs.addTab(
        create_m4_workspace(
            qt_widgets=qt_widgets,
            transport=transport,
            parent=m4_tabs,
        ),
        "Debrief",
    )
    m4_tabs.addTab(_create_visualization_page(qt_widgets, m4_tabs), "Trajectory / Media")

    m6 = create_m6_workspace(qt_widgets=qt_widgets, transport=transport, parent=stack)
    m7 = create_m7_workspace(qt_widgets=qt_widgets, transport=transport, parent=stack)
    m8 = create_m8_workspace(qt_widgets=qt_widgets, transport=transport, parent=stack)
    m9 = create_m9_workspace(qt_widgets, transport, stack)
    runtime = _create_runtime_page(qt_widgets, stack, transport=transport)

    pages = {
        "M1": m1,
        "M3": m3,
        "M4": m4_tabs,
        "M6": m6,
        "M7": m7,
        "M8": m8,
        "M9": m9,
        "Runtime": runtime,
    }
    page_index: dict[str, int] = {}
    for key, page in pages.items():
        page_index[key] = stack.addWidget(page)

    slot_surface = {
        "P01": "M1",
        "P02": "M1",
        "P03": "M1",
        "P04": "M3",
        "P05": "M4",
        "P06": "M6",
        "P07": "M7",
        "P08": "M8",
        "P09": "M8",
        "P10": "M9",
        "P11": "M9",
        "P12": "M9",
        "P13": "Runtime",
    }
    row_to_page: list[int] = []
    for item in PRODUCT_NAVIGATION:
        navigation.addItem(
            f"{item.slot} · {item.title} · [{item.semantic_class}]"
        )
        row_to_page.append(page_index[slot_surface[item.slot]])

    def change_page(row: int) -> None:
        if 0 <= row < len(row_to_page):
            stack.setCurrentIndex(row_to_page[row])

    navigation.currentRowChanged.connect(change_page)
    navigation.setCurrentRow(0)
    root._tpaa_navigation = navigation
    root._tpaa_stack = stack
    root._tpaa_row_to_page = tuple(row_to_page)
    return root
