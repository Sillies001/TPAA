"""Reusable W4 Qt components with stable object and accessibility contracts."""

from __future__ import annotations

from typing import Any

from .design_system import ScaledMetrics, scaled_metrics
from .shell_state import ApplicationShellState, ShellSelection


def _accessible(widget: Any, *, name: str, description: str) -> None:
    widget.setAccessibleName(name)
    widget.setAccessibleDescription(description)


def configure_form_layout(layout: Any, qt_widgets: Any, *, dpi: float = 96.0) -> None:
    metrics = scaled_metrics(dpi)
    layout.setContentsMargins(
        metrics.space_md,
        metrics.space_md,
        metrics.space_md,
        metrics.space_md,
    )
    layout.setHorizontalSpacing(metrics.space_md)
    layout.setVerticalSpacing(metrics.space_sm)
    layout.setRowWrapPolicy(qt_widgets.QFormLayout.RowWrapPolicy.WrapLongRows)
    layout.setFieldGrowthPolicy(qt_widgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)


def configure_table(
    table: Any,
    qt_widgets: Any,
    *,
    dpi: float = 96.0,
    stretch_last: bool = True,
) -> None:
    metrics = scaled_metrics(dpi)
    table.setAlternatingRowColors(True)
    table.setWordWrap(False)
    table.setSelectionBehavior(qt_widgets.QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(qt_widgets.QAbstractItemView.SelectionMode.SingleSelection)
    table.verticalHeader().setDefaultSectionSize(metrics.table_row_height)
    table.verticalHeader().setMinimumSectionSize(metrics.table_row_height)
    table.horizontalHeader().setMinimumSectionSize(metrics.control_height * 2)
    table.horizontalHeader().setStretchLastSection(stretch_last)


def create_state_panel(
    qt_widgets: Any,
    parent: Any,
    *,
    kind: str,
    title: str,
    message: str,
) -> Any:
    normalized = kind.upper()
    if normalized not in {"EMPTY", "ERROR", "LOADING"}:
        raise ValueError(f"unsupported state panel: {kind}")
    panel = qt_widgets.QFrame(parent)
    panel.setObjectName(f"tpaa{normalized.title()}State")
    panel.setProperty("tpaaSurface", True)
    layout = qt_widgets.QVBoxLayout(panel)
    heading = qt_widgets.QLabel(title, panel)
    heading.setObjectName(f"tpaa{normalized.title()}StateTitle")
    heading.setProperty("tpaaHeading", True)
    detail = qt_widgets.QLabel(message, panel)
    detail.setObjectName(f"tpaa{normalized.title()}StateMessage")
    detail.setProperty("tpaaMuted", normalized != "ERROR")
    if normalized == "ERROR":
        detail.setProperty("tpaaState", "error")
    detail.setWordWrap(True)
    layout.addWidget(heading)
    layout.addWidget(detail)
    layout.addStretch(1)
    _accessible(panel, name=title, description=message)
    return panel


def create_mission_header(
    qt_widgets: Any,
    parent: Any,
    state: ApplicationShellState,
    *,
    metrics: ScaledMetrics | None = None,
) -> Any:
    active_metrics = metrics or scaled_metrics()
    frame = qt_widgets.QFrame(parent)
    frame.setObjectName("tpaaMissionHeader")
    frame.setProperty("tpaaSurface", True)
    layout = qt_widgets.QGridLayout(frame)
    layout.setContentsMargins(
        active_metrics.space_md,
        active_metrics.space_sm,
        active_metrics.space_md,
        active_metrics.space_sm,
    )
    title = qt_widgets.QLabel("No Session selected", frame)
    title.setObjectName("tpaaMissionHeaderTitle")
    title.setProperty("tpaaHeading", True)
    context = qt_widgets.QLabel("Context: exact selection required", frame)
    context.setObjectName("tpaaMissionHeaderContext")
    context.setProperty("tpaaMuted", True)
    scope = qt_widgets.QLabel("Episode —  |  Stage —  |  Release —", frame)
    scope.setObjectName("tpaaMissionHeaderScope")
    scope.setProperty("tpaaMuted", True)
    quality = qt_widgets.QLabel("Data confidence: unavailable", frame)
    quality.setObjectName("tpaaMissionHeaderQuality")
    quality.setProperty("tpaaMuted", True)
    layout.addWidget(title, 0, 0)
    layout.addWidget(quality, 0, 1)
    layout.addWidget(context, 1, 0)
    layout.addWidget(scope, 1, 1)

    def render(selection: ShellSelection, _changed: frozenset[str]) -> None:
        title.setText(
            "No Session selected"
            if selection.session_id is None
            else f"Session {selection.session_id}"
        )
        context.setText(
            "Context: exact selection required"
            if selection.context_id is None
            else f"Context {selection.context_id}  |  version {selection.context_version or '—'}"
        )
        scope.setText(
            f"Episode {selection.episode_id or '—'}  |  Stage {selection.stage_id or '—'}"
            f"  |  Release {selection.release_id or '—'}"
        )

    state.subscribe(render)
    render(state.selection, frozenset())
    _accessible(
        frame,
        name="Mission context",
        description="Current exact Session, Episode, Stage, Context, and Release selection",
    )
    frame._tpaa_render_selection = render
    return frame


def create_detail_drawer(
    qt_widgets: Any,
    parent: Any,
    state: ApplicationShellState,
    *,
    metrics: ScaledMetrics | None = None,
) -> Any:
    active_metrics = metrics or scaled_metrics()
    drawer = qt_widgets.QFrame(parent)
    drawer.setObjectName("tpaaDetailEvidenceDrawer")
    drawer.setProperty("tpaaSurface", True)
    drawer.setMinimumWidth(active_metrics.drawer_width)
    drawer.setMaximumWidth(active_metrics.drawer_width * 2)
    layout = qt_widgets.QVBoxLayout(drawer)
    heading = qt_widgets.QLabel("Detail & Evidence", drawer)
    heading.setProperty("tpaaHeading", True)
    heading.setObjectName("tpaaDetailDrawerTitle")
    tabs = qt_widgets.QTabWidget(drawer)
    tabs.setObjectName("tpaaDetailDrawerTabs")
    for name, object_name, message in (
        ("Selection", "tpaaDrawerSelection", "Select a governed object to inspect exact identity."),
        ("Evidence", "tpaaDrawerEvidence", "Evidence remains bound to immutable observations."),
        ("Provenance", "tpaaDrawerProvenance", "Provenance and chain identity are not reconstructed."),
    ):
        panel = qt_widgets.QPlainTextEdit(tabs)
        panel.setObjectName(object_name)
        panel.setReadOnly(True)
        panel.setPlainText(message)
        tabs.addTab(panel, name)
    layout.addWidget(heading)
    layout.addWidget(tabs)

    def render(selection: ShellSelection, changed: frozenset[str]) -> None:
        if not changed:
            return
        selection_panel = tabs.widget(0)
        selection_panel.setPlainText(
            "\n".join(
                (
                    f"Page: {selection.page_id}",
                    f"Session: {selection.session_id or '—'}",
                    f"Episode: {selection.episode_id or '—'}",
                    f"Stage: {selection.stage_id or '—'}",
                    f"Metric instance: {selection.metric_instance_id or '—'}",
                    f"Observation: {selection.observation_id or '—'}",
                    f"Release: {selection.release_id or '—'}",
                )
            )
        )

    state.subscribe(render)
    _accessible(
        drawer,
        name="Detail and evidence drawer",
        description="Shared immutable selection, evidence, and provenance details",
    )
    drawer._tpaa_render_selection = render
    return drawer


def create_shell_status_bar(
    qt_widgets: Any,
    parent: Any,
    state: ApplicationShellState,
    *,
    readiness: str,
) -> Any:
    frame = qt_widgets.QFrame(parent)
    frame.setObjectName("tpaaShellStatusBar")
    layout = qt_widgets.QHBoxLayout(frame)
    runtime = qt_widgets.QLabel(f"Runtime: {readiness}", frame)
    runtime.setObjectName("tpaaShellRuntimeStatus")
    runtime.setProperty("tpaaState", "success" if readiness == "READY" else "error")
    selection = qt_widgets.QLabel("Selection: P01", frame)
    selection.setObjectName("tpaaShellSelectionStatus")
    selection.setProperty("tpaaMuted", True)
    hint = qt_widgets.QLabel("Keyboard: Tab / Shift+Tab  •  resizable panels", frame)
    hint.setObjectName("tpaaShellKeyboardHint")
    hint.setProperty("tpaaMuted", True)
    layout.addWidget(runtime)
    layout.addWidget(selection, 1)
    layout.addWidget(hint)

    def render(value: ShellSelection, _changed: frozenset[str]) -> None:
        selection.setText(
            f"Selection: {value.page_id}  •  Session {value.session_id or '—'}"
            f"  •  Release {value.release_id or '—'}"
        )

    state.subscribe(render)
    render(state.selection, frozenset())
    _accessible(frame, name="Application status", description="Runtime and current selection status")
    frame._tpaa_render_selection = render
    return frame


__all__ = [
    "configure_form_layout",
    "configure_table",
    "create_detail_drawer",
    "create_mission_header",
    "create_shell_status_bar",
    "create_state_panel",
]
