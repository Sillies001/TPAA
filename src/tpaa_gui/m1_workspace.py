"""M1 Batch 3 Desktop workspace over the authenticated local HTTP transport."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

from .diagnostics import DiagnosticsSnapshot


class M1DesktopTransport(Protocol):
    """Narrow GUI-side transport; bearer credentials stay inside the implementation."""

    def m1_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        ...


class M1WorkspaceError(RuntimeError):
    """Stable presentation-layer failure without domain reinterpretation."""


def _require_success(status: int, payload: dict[str, Any]) -> dict[str, Any]:
    if 200 <= status < 300 and payload.get("outcome") != "SYSTEM_ERROR":
        return payload
    error = payload.get("error")
    code = error.get("code") if isinstance(error, dict) else None
    raise M1WorkspaceError(str(code or f"HTTP_{status}"))


def _cursor_time(start: int, end: int, slider_value: int) -> int:
    """Map a display slider to one session-time cursor without changing Stage authority."""

    if end <= start:
        return start
    bounded = min(1000, max(0, slider_value))
    return start + ((end - start) * bounded // 1000)


def _active_stage_index(stages: list[dict[str, Any]], cursor: int) -> int | None:
    for index, stage in enumerate(stages):
        try:
            start = int(stage["start_session_time_us"])
            end = int(stage["end_session_time_us"])
        except (KeyError, TypeError, ValueError):
            continue
        if start <= cursor < end or (cursor == end and index == len(stages) - 1):
            return index
    return None


def create_m1_workspace(
    qt_core: Any,
    qt_widgets: Any,
    parent: Any,
    *,
    transport: M1DesktopTransport,
    diagnostics_provider: Callable[[], DiagnosticsSnapshot],
) -> Any:
    """Create the release-bound Batch 3 workspace with stable automation object names."""

    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaM1Workspace")
    outer = qt_widgets.QVBoxLayout(root)

    browser_group = qt_widgets.QGroupBox("M1 Session Browser", root)
    browser_group.setObjectName("tpaaM1SessionBrowser")
    browser = qt_widgets.QGridLayout(browser_group)

    fixture = qt_widgets.QComboBox(browser_group)
    fixture.setObjectName("tpaaM1FixtureSelector")
    fixture.addItems(["BF_M1_NOMINAL_V1"])
    browser.addWidget(qt_widgets.QLabel("Synthetic fixture", browser_group), 0, 0)
    browser.addWidget(fixture, 0, 1, 1, 3)

    identity_fields: list[tuple[str, str]] = [
        ("Aircraft model id", "tpaaM1AircraftModelId"),
        ("Aircraft instance id", "tpaaM1AircraftInstanceId"),
        ("Subject entity id", "tpaaM1SubjectEntityId"),
        ("Capability dimension", "tpaaM1CapabilityDimension"),
        ("Capability type", "tpaaM1CapabilityType"),
    ]
    identity_inputs: dict[str, Any] = {}
    for row, (label, object_name) in enumerate(identity_fields, start=1):
        widget = qt_widgets.QLineEdit(browser_group)
        widget.setObjectName(object_name)
        widget.setPlaceholderText("Explicit upstream/test binding required")
        identity_inputs[object_name] = widget
        browser.addWidget(qt_widgets.QLabel(label, browser_group), row, 0)
        browser.addWidget(widget, row, 1, 1, 3)

    run_button = qt_widgets.QPushButton("Import → Compute → Publish", browser_group)
    run_button.setObjectName("tpaaM1RunJourney")
    browser.addWidget(run_button, len(identity_fields) + 1, 0, 1, 2)

    release_selector = qt_widgets.QComboBox(browser_group)
    release_selector.setObjectName("tpaaM1ReleaseSelector")
    browser.addWidget(qt_widgets.QLabel("Release", browser_group), len(identity_fields) + 1, 2)
    browser.addWidget(release_selector, len(identity_fields) + 1, 3)
    outer.addWidget(browser_group)

    header_group = qt_widgets.QGroupBox("Context / Mission Header", root)
    header_group.setObjectName("tpaaM1ContextHeader")
    header = qt_widgets.QGridLayout(header_group)
    readiness_label = qt_widgets.QLabel("Readiness: NOT_READY", header_group)
    readiness_label.setObjectName("tpaaM1Readiness")
    baseline_label = qt_widgets.QLabel("Baseline: unavailable", header_group)
    baseline_label.setObjectName("tpaaM1Baseline")
    release_label = qt_widgets.QLabel("Release: unavailable", header_group)
    release_label.setObjectName("tpaaM1ReleaseIdentity")
    context_label = qt_widgets.QLabel("Context: unavailable", header_group)
    context_label.setObjectName("tpaaM1ContextIdentity")
    workflow_status = qt_widgets.QLabel("Workflow: IDLE", header_group)
    workflow_status.setObjectName("tpaaM1WorkflowStatus")
    header.addWidget(readiness_label, 0, 0)
    header.addWidget(baseline_label, 0, 1)
    header.addWidget(release_label, 1, 0, 1, 2)
    header.addWidget(context_label, 2, 0, 1, 2)
    header.addWidget(workflow_status, 3, 0, 1, 2)
    outer.addWidget(header_group)

    timeline_group = qt_widgets.QGroupBox("Master Timeline / Stage lane", root)
    timeline_group.setObjectName("tpaaM1TimelineGroup")
    timeline_layout = qt_widgets.QVBoxLayout(timeline_group)
    cursor_label = qt_widgets.QLabel("Cursor: unavailable", timeline_group)
    cursor_label.setObjectName("tpaaM1CursorTime")
    slider = qt_widgets.QSlider(qt_core.Qt.Orientation.Horizontal, timeline_group)
    slider.setObjectName("tpaaM1TimelineSlider")
    slider.setRange(0, 1000)
    stage_list = qt_widgets.QListWidget(timeline_group)
    stage_list.setObjectName("tpaaM1StageLane")
    timeline_layout.addWidget(cursor_label)
    timeline_layout.addWidget(slider)
    timeline_layout.addWidget(stage_list)
    outer.addWidget(timeline_group)

    metric_group = qt_widgets.QGroupBox("Metrics / Detail / Evidence", root)
    metric_group.setObjectName("tpaaM1MetricGroup")
    metric_layout = qt_widgets.QGridLayout(metric_group)
    metric_table = qt_widgets.QTableWidget(metric_group)
    metric_table.setObjectName("tpaaM1MetricList")
    metric_table.setColumnCount(5)
    metric_table.setHorizontalHeaderLabels(
        ["Metric", "Status", "Value kind", "Coverage", "Confidence"]
    )
    metric_table.setSelectionBehavior(qt_widgets.QAbstractItemView.SelectionBehavior.SelectRows)
    metric_table.setSelectionMode(qt_widgets.QAbstractItemView.SelectionMode.SingleSelection)
    metric_detail = qt_widgets.QPlainTextEdit(metric_group)
    metric_detail.setObjectName("tpaaM1MetricDetail")
    metric_detail.setReadOnly(True)
    evidence_detail = qt_widgets.QPlainTextEdit(metric_group)
    evidence_detail.setObjectName("tpaaM1EvidenceDetail")
    evidence_detail.setReadOnly(True)
    metric_cursor = qt_widgets.QLabel("Metric cursor: unavailable", metric_group)
    metric_cursor.setObjectName("tpaaM1MetricCursor")
    evidence_cursor = qt_widgets.QLabel("Evidence cursor: unavailable", metric_group)
    evidence_cursor.setObjectName("tpaaM1EvidenceCursor")
    metric_layout.addWidget(metric_table, 0, 0, 4, 1)
    metric_layout.addWidget(metric_cursor, 0, 1)
    metric_layout.addWidget(metric_detail, 1, 1)
    metric_layout.addWidget(evidence_cursor, 2, 1)
    metric_layout.addWidget(evidence_detail, 3, 1)
    outer.addWidget(metric_group)

    state_group = qt_widgets.QGroupBox("Quality / Failure states", root)
    state_group.setObjectName("tpaaM1StateLegend")
    state_layout = qt_widgets.QHBoxLayout(state_group)
    state_styles = {
        "N_A": "QLabel { border: 2px dashed #6b7280; padding: 4px; }",
        "INSUFFICIENT": "QLabel { border: 2px solid #b45309; padding: 4px; }",
        "INVALID": "QLabel { border: 2px solid #b91c1c; padding: 4px; font-weight: bold; }",
        "SYSTEM_ERROR": "QLabel { border: 3px double #7e22ce; padding: 4px; font-weight: bold; }",
    }
    state_object_names = {
        "N_A": "tpaaM1StateNA",
        "INSUFFICIENT": "tpaaM1StateINSUFFICIENT",
        "INVALID": "tpaaM1StateINVALID",
        "SYSTEM_ERROR": "tpaaM1StateSYSTEMERROR",
    }
    for state, style in state_styles.items():
        badge = qt_widgets.QLabel(state, state_group)
        badge.setObjectName(state_object_names[state])
        badge.setStyleSheet(style)
        state_layout.addWidget(badge)
    outer.addWidget(state_group)

    replay_button = qt_widgets.QPushButton("Replay selected Release", root)
    replay_button.setObjectName("tpaaM1Replay")
    replay_status = qt_widgets.QLabel("Replay: IDLE", root)
    replay_status.setObjectName("tpaaM1ReplayStatus")
    outer.addWidget(replay_button)
    outer.addWidget(replay_status)

    current: dict[str, Any] = {
        "release_id": None,
        "topology": None,
        "metrics": [],
        "observations": [],
    }

    def refresh_runtime_header() -> None:
        snapshot = diagnostics_provider()
        readiness_label.setText(f"Readiness: {snapshot.readiness}")
        observed = snapshot.observed
        baseline = "unavailable" if observed is None else observed.core_baseline
        baseline_label.setText(f"Baseline: {baseline}")

    def request(
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = None if idempotency_key is None else {"Idempotency-Key": idempotency_key}
        status, payload = transport.m1_request_json(method, path, body=body, headers=headers)
        return _require_success(status, payload)

    def explicit_value(object_name: str) -> str:
        value = str(identity_inputs[object_name].text()).strip()
        if not value:
            raise M1WorkspaceError("EXPLICIT_PUBLICATION_IDENTITY_REQUIRED")
        return value

    def render_cursor() -> None:
        topology = current.get("topology")
        if not isinstance(topology, dict):
            return
        session = topology.get("session")
        stages = topology.get("stages")
        if not isinstance(session, dict) or not isinstance(stages, list):
            return
        try:
            start = int(session["start_session_time_us"])
            end = int(session["end_session_time_us"])
        except (KeyError, TypeError, ValueError):
            return
        cursor = _cursor_time(start, end, slider.value())
        text = f"Cursor: {cursor}"
        cursor_label.setText(text)
        metric_cursor.setText(f"Metric cursor: {cursor}")
        evidence_cursor.setText(f"Evidence cursor: {cursor}")
        stage_index = _active_stage_index(
            [item for item in stages if isinstance(item, dict)],
            cursor,
        )
        if stage_index is not None:
            stage_list.setCurrentRow(stage_index)

    def render_metric_detail(row: int, _column: int = 0) -> None:
        release_id = current.get("release_id")
        metrics = current.get("metrics")
        if not isinstance(release_id, str) or not isinstance(metrics, list):
            return
        if row < 0 or row >= len(metrics):
            return
        item = metrics[row]
        if not isinstance(item, dict):
            return
        code = item.get("metric_code")
        if not isinstance(code, str):
            return
        try:
            detail = request("GET", f"/m1/releases/{release_id}/metrics/{code}")
            evidence = request("GET", f"/m1/releases/{release_id}/metrics/{code}/evidence")
        except Exception as exc:
            workflow_status.setText(f"Workflow: SYSTEM_ERROR {type(exc).__name__}")
            return
        metric_detail.setPlainText(json.dumps(detail, indent=2, sort_keys=True))
        evidence_detail.setPlainText(json.dumps(evidence, indent=2, sort_keys=True))
        render_cursor()

    def render_release(release_id: str) -> None:
        release = request("GET", f"/m1/releases/{release_id}")
        context = request("GET", f"/m1/releases/{release_id}/context")
        topology = request("GET", f"/m1/releases/{release_id}/topology")
        metrics_payload = request("GET", f"/m1/releases/{release_id}/metrics")
        observations_payload = request("GET", f"/m1/releases/{release_id}/observations")
        metrics = metrics_payload.get("items")
        observations = observations_payload.get("items")
        if not isinstance(metrics, list) or not isinstance(observations, list):
            raise M1WorkspaceError("INVALID_RELEASE_PROJECTION")

        current.update(
            release_id=release_id,
            topology=topology,
            metrics=metrics,
            observations=observations,
        )
        release_selector.clear()
        release_selector.addItem(release_id)
        provenance = release.get("provenance")
        release_label.setText(
            f"Release: {release_id} status={release.get('status')} provenance="
            f"{json.dumps(provenance, sort_keys=True)}"
        )
        context_label.setText(
            f"Context: {context.get('context_id')} version={context.get('context_version')} "
            f"rule_set={context.get('rule_set_version')}"
        )

        stage_list.clear()
        stages = topology.get("stages")
        if not isinstance(stages, list) or len(stages) != 4:
            raise M1WorkspaceError("FOUR_STAGE_PROJECTION_REQUIRED")
        for stage in stages:
            if not isinstance(stage, dict):
                raise M1WorkspaceError("INVALID_STAGE_PROJECTION")
            stage_list.addItem(
                f"{stage.get('stage_type')} [{stage.get('start_session_time_us')},"
                f"{stage.get('end_session_time_us')}) status={stage.get('stage_status')} "
                f"coverage={stage.get('coverage')} confidence={stage.get('confidence')}"
            )

        observation_by_metric = {
            item.get("metric_code"): item
            for item in observations
            if isinstance(item, dict) and isinstance(item.get("metric_code"), str)
        }
        metric_table.setRowCount(len(metrics))
        for row, item in enumerate(metrics):
            if not isinstance(item, dict):
                raise M1WorkspaceError("INVALID_METRIC_PROJECTION")
            code = item.get("metric_code")
            observation = observation_by_metric.get(code, {})
            values = [
                code,
                item.get("status"),
                item.get("value_kind"),
                observation.get("coverage") if isinstance(observation, dict) else None,
                observation.get("confidence") if isinstance(observation, dict) else None,
            ]
            for column, value in enumerate(values):
                metric_table.setItem(row, column, qt_widgets.QTableWidgetItem(str(value)))
        if len(metrics) != 5:
            raise M1WorkspaceError("FIVE_METRIC_PROJECTION_REQUIRED")
        metric_table.selectRow(0)
        render_metric_detail(0)
        render_cursor()

    def run_journey() -> None:
        refresh_runtime_header()
        workflow_status.setText("Workflow: RUNNING")
        try:
            fixture_id = fixture.currentText()
            imported = request(
                "POST",
                "/m1/commands/import-session",
                body={"fixture_id": fixture_id},
                idempotency_key=f"desktop-import:{fixture_id}",
            )
            computed = request(
                "POST",
                "/m1/commands/compute-session",
                body={"fixture_id": fixture_id},
                idempotency_key=f"desktop-compute:{fixture_id}",
            )
            publish_body: dict[str, object] = {
                "fixture_id": fixture_id,
                "aircraft_model_id": explicit_value("tpaaM1AircraftModelId"),
                "aircraft_instance_id": explicit_value("tpaaM1AircraftInstanceId"),
                "subject_entity_id": explicit_value("tpaaM1SubjectEntityId"),
                "capability_dimension": explicit_value("tpaaM1CapabilityDimension"),
                "capability_type": explicit_value("tpaaM1CapabilityType"),
                "expected_version_token": 0,
            }
            published = request(
                "POST",
                "/m1/commands/publish-session",
                body=publish_body,
                idempotency_key=f"desktop-publish:{fixture_id}",
            )
            release_id = published.get("release_id")
            if not isinstance(release_id, str):
                raise M1WorkspaceError("RELEASE_ID_MISSING")
            if imported.get("session_id") != published.get("session_id"):
                raise M1WorkspaceError("SESSION_ID_DRIFT")
            if computed.get("fixture_id") != fixture_id:
                raise M1WorkspaceError("COMPUTE_FIXTURE_DRIFT")
            render_release(release_id)
            workflow_status.setText("Workflow: PUBLISHED")
        except Exception as exc:
            workflow_status.setText(f"Workflow: SYSTEM_ERROR {type(exc).__name__}:{exc}")

    def replay_release() -> None:
        release_id = current.get("release_id")
        if not isinstance(release_id, str):
            replay_status.setText("Replay: SYSTEM_ERROR RELEASE_REQUIRED")
            return
        try:
            payload = request("POST", f"/m1/releases/{release_id}/replay")
            replay_status.setText(
                f"Replay: {payload.get('status')} exact={payload.get('exact_logical_products_equal')} "
                f"fallback={payload.get('current_latest_fallback_used')}"
            )
        except Exception as exc:
            replay_status.setText(f"Replay: SYSTEM_ERROR {type(exc).__name__}:{exc}")

    refresh_runtime_header()
    run_button.clicked.connect(run_journey)
    replay_button.clicked.connect(replay_release)
    slider.valueChanged.connect(lambda _value: render_cursor())
    metric_table.cellClicked.connect(render_metric_detail)
    return root
