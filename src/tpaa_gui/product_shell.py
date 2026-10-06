"""PIQB B5 production Desktop composition over existing qualified GUI surfaces."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .diagnostics import DiagnosticsSnapshot
from .discovery import (
    ProductDiscoveryError,
    release_ids,
    session_items,
    session_release_items,
)
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

    def product_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Mapping[str, object]]: ...

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
    ProductNavigationItem(
        "P01",
        "SESSION_RELEASE",
        "Session / Release",
        "M1",
        "C",
    ),
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



def _create_session_release_browser(
    qt_widgets: Any,
    parent: Any,
    *,
    transport: ProductDesktopTransport,
) -> Any:
    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaC4SessionReleaseBrowser")
    layout = qt_widgets.QVBoxLayout(root)
    notice = qt_widgets.QLabel(
        "Immutable Session → Release navigation; no current/latest fallback.",
        root,
    )
    session_selector = qt_widgets.QComboBox(root)
    session_selector.setObjectName("tpaaC4SessionSelector")
    release_selector = qt_widgets.QComboBox(root)
    release_selector.setObjectName("tpaaC4ReleaseSelector")
    refresh = qt_widgets.QPushButton("Refresh Sessions", root)
    refresh.setObjectName("tpaaC4SessionRefresh")
    load_release = qt_widgets.QPushButton("Open exact Release", root)
    load_release.setObjectName("tpaaC4ReleaseOpen")
    status = qt_widgets.QLabel("Discovery: not loaded", root)
    status.setObjectName("tpaaC4SessionReleaseStatus")
    output = qt_widgets.QPlainTextEdit(root)
    output.setObjectName("tpaaC4SessionReleaseOutput")
    output.setReadOnly(True)
    for widget in (
        notice,
        session_selector,
        release_selector,
        refresh,
        load_release,
        status,
        output,
    ):
        layout.addWidget(widget)

    sessions: list[dict[str, object]] = []

    def populate_releases(_session_label: str = "") -> None:
        index = session_selector.currentIndex()
        release_selector.clear()
        if index < 0 or index >= len(sessions):
            return
        session_id = sessions[index].get("session_id")
        if not isinstance(session_id, str):
            status.setText("Discovery: invalid Session identity")
            return
        try:
            releases = session_release_items(transport, session_id)
        except ProductDiscoveryError as exc:
            status.setText(f"Discovery: Release error · {exc}")
            return
        for item in releases:
            release_id = item.get("release_id")
            release_no = item.get("release_no")
            if isinstance(release_id, str):
                release_selector.addItem(
                    f"#{release_no} · {release_id}",
                    release_id,
                )
        status.setText(
            f"Discovery: Session {session_id} · "
            f"{release_selector.count()} immutable Releases"
        )

    def refresh_sessions() -> None:
        nonlocal sessions
        try:
            sessions = session_items(transport)
        except ProductDiscoveryError as exc:
            status.setText(f"Discovery: Session error · {exc}")
            return
        session_selector.clear()
        for item in sessions:
            session_id = item.get("session_id")
            session_code = item.get("session_code")
            if not isinstance(session_id, str):
                continue
            session_selector.addItem(
                f"{session_code or '-'} · {session_id}",
                session_id,
            )
        populate_releases()

    def open_release() -> None:
        release_id = release_selector.currentData()
        if not isinstance(release_id, str) or not release_id:
            status.setText("Discovery: exact Release selection required")
            return
        http_status, payload = transport.product_request_json(
            "GET",
            f"/api/v1/products/p1/releases/{release_id}",
        )
        if http_status != 200:
            status.setText(f"Discovery: Release HTTP error {http_status}")
            output.clear()
            return
        status.setText(f"Discovery: exact Release {release_id}")
        output.setPlainText(
            json.dumps(dict(payload), indent=2, sort_keys=True)
        )

    session_selector.currentTextChanged.connect(populate_releases)
    refresh.clicked.connect(refresh_sessions)
    load_release.clicked.connect(open_release)
    return root


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
        selector = qt_widgets.QComboBox(root)
        selector.setObjectName(f"tpaaB5M3{training_key}ReleaseId")
        layout.addWidget(selector)
        inputs[training_key] = selector
    refresh = qt_widgets.QPushButton("Refresh exact Release discovery", root)
    refresh.setObjectName("tpaaB5M3ReleaseRefresh")
    load_button = qt_widgets.QPushButton("Load exact training workspaces", root)
    load_button.setObjectName("tpaaB5M3Load")
    status = qt_widgets.QLabel("M3 workspace: discovery not loaded", root)
    status.setObjectName("tpaaB5M3Status")
    layout.addWidget(refresh)
    layout.addWidget(load_button)
    layout.addWidget(status)
    state: dict[str, Any] = {"workspace": None}

    def refresh_releases() -> None:
        try:
            discovered = release_ids(transport)
        except ProductDiscoveryError as exc:
            status.setText(f"M3 workspace: discovery error · {exc}")
            return
        for selector in inputs.values():
            selector.clear()
            selector.addItems(discovered)
        status.setText(
            f"M3 workspace: {len(discovered)} immutable Releases discovered"
        )

    def load() -> None:
        selected_release_ids = {
            key: str(widget.currentText()).strip()
            for key, widget in inputs.items()
        }
        if any(not value for value in selected_release_ids.values()):
            status.setText("M3 workspace: exact Release discovery required")
            return
        previous = state.get("workspace")
        if previous is not None:
            previous.deleteLater()
        workspace = create_m3_workspace_navigation(
            qt_core,
            qt_widgets,
            root,
            transport=transport,
            release_ids_by_training=selected_release_ids,
        )
        workspace.setObjectName("tpaaB5M3Workspace")
        layout.addWidget(workspace)
        state["workspace"] = workspace
        status.setText("M3 workspace: exact Release set loaded")

    refresh.clicked.connect(refresh_releases)
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


def _create_visualization_page(
    qt_widgets: Any,
    parent: Any,
    *,
    transport: ProductDesktopTransport,
) -> Any:
    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaB5TrajectoryMedia")
    layout = qt_widgets.QVBoxLayout(root)
    notice = qt_widgets.QLabel(
        "Exact release-bound backend projection only; "
        "unsupported sources remain explicit.",
        root,
    )
    release_id = qt_widgets.QComboBox(root)
    release_id.setObjectName("tpaaB5TrajectoryReleaseId")
    refresh = qt_widgets.QPushButton("Refresh exact Release discovery", root)
    refresh.setObjectName("tpaaB5TrajectoryRefresh")
    render = qt_widgets.QPushButton(
        "Load governed 2D / Cesium-ready presentation",
        root,
    )
    render.setObjectName("tpaaB5TrajectoryRender")
    output = qt_widgets.QPlainTextEdit(root)
    output.setObjectName("tpaaB5TrajectoryOutput")
    output.setReadOnly(True)
    status = qt_widgets.QLabel(
        "Trajectory/media: exact Release discovery not loaded",
        root,
    )
    status.setObjectName("tpaaB5TrajectoryStatus")
    for widget in (notice, release_id, refresh, render, status, output):
        layout.addWidget(widget)

    def refresh_releases() -> None:
        try:
            discovered = release_ids(transport)
        except ProductDiscoveryError as exc:
            status.setText(f"Trajectory/media: discovery error · {exc}")
            return
        release_id.clear()
        release_id.addItems(discovered)
        status.setText(
            f"Trajectory/media: {len(discovered)} immutable Releases discovered"
        )

    def render_payload() -> None:
        expected_release_id = release_id.currentText().strip()
        if not expected_release_id:
            status.setText("Trajectory/media: exact Release discovery required")
            return
        http_status, binding = transport.product_request_json(
            "GET",
            (
                "/api/v1/discovery/releases/"
                f"{expected_release_id}/presentation"
            ),
        )
        if http_status != 200:
            status.setText(
                f"Trajectory/media: presentation HTTP error {http_status}"
            )
            output.clear()
            return
        if binding.get("available") is not True:
            reason = binding.get("reason_code", "UNAVAILABLE")
            status.setText(f"Trajectory/media: UNAVAILABLE · {reason}")
            output.setPlainText(
                json.dumps(dict(binding), indent=2, sort_keys=True)
            )
            return
        decoded = binding.get("presentation")
        if not isinstance(decoded, Mapping):
            status.setText("Trajectory/media: INVALID presentation binding")
            output.clear()
            return
        try:
            presentation = build_trajectory_presentation(
                decoded,
                expected_release_id=expected_release_id,
            )
        except VisualizationPresentationError as exc:
            status.setText(f"Trajectory/media: INVALID · {exc}")
            output.clear()
            return
        result = {
            "release_id": presentation.release_id,
            "sample_count": len(presentation.samples),
            "media_count": len(presentation.media),
            "polyline_2d": build_2d_polyline(presentation),
            "cesium_packets": build_cesium_trajectory_packets(presentation),
        }
        status.setText("Trajectory/media: exact presentation ready")
        output.setPlainText(json.dumps(result, indent=2, sort_keys=True))

    refresh.clicked.connect(refresh_releases)
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

    m1_tabs = qt_widgets.QTabWidget(stack)
    m1_tabs.setObjectName("tpaaC4SessionM1Tabs")
    discovery = _create_session_release_browser(
        qt_widgets,
        m1_tabs,
        transport=transport,
    )
    m1 = create_m1_workspace(
        qt_core,
        qt_widgets,
        m1_tabs,
        transport=transport,
        diagnostics_provider=diagnostics_provider,
    )
    m1_tabs.addTab(discovery, "Session / Release")
    m1_tabs.addTab(m1, "Data Quality / Metric Evidence")
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
    m4_tabs.addTab(
        _create_visualization_page(
            qt_widgets,
            m4_tabs,
            transport=transport,
        ),
        "Trajectory / Media",
    )

    m6 = create_m6_workspace(qt_widgets=qt_widgets, transport=transport, parent=stack)
    m7 = create_m7_workspace(qt_widgets=qt_widgets, transport=transport, parent=stack)
    m8 = create_m8_workspace(qt_widgets=qt_widgets, transport=transport, parent=stack)
    m9 = create_m9_workspace(qt_widgets, transport, stack)
    runtime = _create_runtime_page(qt_widgets, stack, transport=transport)

    pages = {
        "M1": m1_tabs,
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
            if row == 0:
                m1_tabs.setCurrentIndex(0)
            elif row in {1, 2}:
                m1_tabs.setCurrentIndex(1)

    navigation.currentRowChanged.connect(change_page)
    navigation.setCurrentRow(0)
    root._tpaa_navigation = navigation
    root._tpaa_stack = stack
    root._tpaa_row_to_page = tuple(row_to_page)
    return root
