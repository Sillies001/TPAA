"""W5 production Desktop pages for the P1 user workflow."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from .components import configure_table
from .discovery import ProductDiscoveryError, product_items, session_items
from .shell_state import ApplicationShellState
from .visualization import VisualizationPresentationError, build_trajectory_presentation
from .w5_projection import (
    SessionOverviewProjection,
    W5ProjectionError,
    build_session_overview,
    observation_quality_rows,
    status_meaning,
    verify_exact_replay,
)


class W5PageError(RuntimeError):
    """Stable W5 GUI orchestration failure."""


def _payload(
    result: tuple[int, Mapping[str, object]],
    *,
    operation: str,
    expected: frozenset[int] = frozenset({200}),
) -> dict[str, object]:
    status, value = result
    if status not in expected:
        error = value.get("error")
        raise W5PageError(f"{operation}:HTTP_{status}:{error!r}")
    return dict(value)


def _rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _display(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return format(value, ".4g")
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _fill_table(
    table: Any,
    qt_widgets: Any,
    rows: Sequence[Mapping[str, object]],
    columns: Sequence[tuple[str, str]],
) -> None:
    table.clearContents()
    table.setRowCount(len(rows))
    table.setColumnCount(len(columns))
    table.setHorizontalHeaderLabels([label for _field, label in columns])
    for row_index, row in enumerate(rows):
        for column_index, (field, _label) in enumerate(columns):
            table.setItem(
                row_index,
                column_index,
                qt_widgets.QTableWidgetItem(_display(row.get(field))),
            )
    table.resizeColumnsToContents()


def _release_items(transport: Any) -> list[dict[str, object]]:
    return product_items(transport, "P1_RELEASE")


def _populate_release_combo(combo: Any, transport: Any) -> int:
    items = _release_items(transport)
    prior = combo.currentData()
    combo.clear()
    for item in items:
        metadata = cast(dict[str, object], item["metadata"])
        exact_id = str(item["exact_id"])
        label = (
            f"{metadata.get('session_id', '—')} · r{metadata.get('release_no', '—')}"
            f" · {metadata.get('status', '—')} · {exact_id}"
        )
        combo.addItem(label, exact_id)
    if prior is not None:
        index = combo.findData(prior)
        if index >= 0:
            combo.setCurrentIndex(index)
    return len(items)


def _exact_release_bundle(transport: Any, release_id: str) -> dict[str, dict[str, object]]:
    if not release_id or release_id.lower() in {"latest", "current"}:
        raise W5PageError("W5_EXACT_RELEASE_REQUIRED")
    return {
        "release": _payload(
            transport.m1_request_json("GET", f"/m1/releases/{release_id}"),
            operation="release",
        ),
        "context": _payload(
            transport.m1_request_json("GET", f"/m1/releases/{release_id}/context"),
            operation="context",
        ),
        "topology": _payload(
            transport.m1_request_json("GET", f"/m1/releases/{release_id}/topology"),
            operation="topology",
        ),
        "metrics": _payload(
            transport.m1_request_json("GET", f"/m1/releases/{release_id}/metrics"),
            operation="metrics",
        ),
        "observations": _payload(
            transport.m1_request_json("GET", f"/m1/releases/{release_id}/observations"),
            operation="observations",
        ),
        "world": _payload(
            transport.m1_request_json("GET", f"/m1/releases/{release_id}/world-graph"),
            operation="world_graph",
        ),
    }


def _overview(bundle: Mapping[str, Mapping[str, object]]) -> SessionOverviewProjection:
    return build_session_overview(
        release=bundle["release"],
        context=bundle["context"],
        topology=bundle["topology"],
        metrics_payload=bundle["metrics"],
        observations_payload=bundle["observations"],
        world_graph=bundle["world"],
    )


def create_p01_page(
    qt_core: Any,
    qt_widgets: Any,
    parent: Any,
    *,
    transport: Any,
    state: ApplicationShellState,
) -> Any:
    """Training Session list plus real request import/job/publication workflow."""

    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaP01Workflow")
    layout = qt_widgets.QVBoxLayout(root)

    filters = qt_widgets.QGroupBox("Session search & filters", root)
    filter_layout = qt_widgets.QHBoxLayout(filters)
    search = qt_widgets.QLineEdit(filters)
    search.setObjectName("tpaaP01SessionSearch")
    search.setPlaceholderText("Session code / immutable Session ID")
    session_type = qt_widgets.QComboBox(filters)
    session_type.setObjectName("tpaaP01SessionTypeFilter")
    session_type.addItems(("ALL TYPES", "LIVE", "SIM", "LVC"))
    data_status = qt_widgets.QComboBox(filters)
    data_status.setObjectName("tpaaP01DataStatusFilter")
    data_status.addItems(("ALL DATA STATUS", "READY", "PARTIAL", "FAILED"))
    refresh = qt_widgets.QPushButton("Refresh Sessions", filters)
    refresh.setObjectName("tpaaP01RefreshSessions")
    filter_layout.addWidget(search, 1)
    filter_layout.addWidget(session_type)
    filter_layout.addWidget(data_status)
    filter_layout.addWidget(refresh)

    table = qt_widgets.QTableWidget(root)
    table.setObjectName("tpaaP01SessionTable")
    configure_table(table, qt_widgets)
    table.setMinimumHeight(220)

    importer = qt_widgets.QGroupBox("Governed real-file import → P1 publication", root)
    import_layout = qt_widgets.QGridLayout(importer)
    import_notice = qt_widgets.QLabel(
        "Select a governed TPAA P1 request manifest. Inline source JSON is staged as "
        "immutable managed artifacts before BUILD_P1_RELEASE is submitted.",
        importer,
    )
    import_notice.setWordWrap(True)
    import_notice.setProperty("tpaaMuted", True)
    path_edit = qt_widgets.QLineEdit(importer)
    path_edit.setObjectName("tpaaP01ManifestPath")
    path_edit.setPlaceholderText("TPAA_ED2_B1_FULL_P1_REQUEST_CONTRACT_V1 JSON file")
    browse = qt_widgets.QPushButton("Browse…", importer)
    browse.setObjectName("tpaaP01BrowseManifest")
    stage = qt_widgets.QPushButton("1  Validate & stage sources", importer)
    stage.setObjectName("tpaaP01StageManifest")
    publish = qt_widgets.QPushButton("2  Build & publish P1 Release", importer)
    publish.setObjectName("tpaaP01PublishRelease")
    publish.setEnabled(False)
    job_id = qt_widgets.QLineEdit(importer)
    job_id.setObjectName("tpaaP01JobId")
    job_id.setReadOnly(True)
    job_id.setPlaceholderText("Formal compute job ID")
    poll = qt_widgets.QPushButton("Refresh job status", importer)
    poll.setObjectName("tpaaP01RefreshJob")
    poll.setEnabled(False)
    status = qt_widgets.QLabel("Import: waiting for a real governed file", importer)
    status.setObjectName("tpaaP01ImportStatus")
    status.setProperty("tpaaState", "unknown")
    import_layout.addWidget(import_notice, 0, 0, 1, 4)
    import_layout.addWidget(path_edit, 1, 0, 1, 3)
    import_layout.addWidget(browse, 1, 3)
    import_layout.addWidget(stage, 2, 0, 1, 2)
    import_layout.addWidget(publish, 2, 2, 1, 2)
    import_layout.addWidget(job_id, 3, 0, 1, 3)
    import_layout.addWidget(poll, 3, 3)
    import_layout.addWidget(status, 4, 0, 1, 4)

    layout.addWidget(filters)
    layout.addWidget(table, 1)
    layout.addWidget(importer)
    all_sessions: list[dict[str, object]] = []
    staged_payload: dict[str, object] | None = None
    source_hash: str | None = None

    columns = (
        ("session_code", "Session"),
        ("session_type", "Type"),
        ("data_status", "Data"),
        ("release_count", "Releases"),
        ("release_status", "Latest published state"),
        ("session_id", "Immutable Session ID"),
    )

    def apply_filters() -> None:
        needle = search.text().strip().casefold()
        selected_type = session_type.currentText()
        selected_status = data_status.currentText()
        filtered = []
        for item in all_sessions:
            haystack = f"{item.get('session_code', '')} {item.get('session_id', '')}".casefold()
            if needle and needle not in haystack:
                continue
            if selected_type != "ALL TYPES" and item.get("session_type") != selected_type:
                continue
            if selected_status != "ALL DATA STATUS" and item.get("data_status") != selected_status:
                continue
            filtered.append(item)
        _fill_table(table, qt_widgets, filtered, columns)
        table._tpaa_rows = filtered

    def refresh_sessions() -> None:
        nonlocal all_sessions
        try:
            discovered = session_items(transport)
            enriched: list[dict[str, object]] = []
            for item in discovered:
                session_id_value = str(item.get("session_id", ""))
                release_rows = _payload(
                    transport.product_request_json(
                        "GET",
                        f"/api/v1/discovery/sessions/{session_id_value}/releases",
                    ),
                    operation="session_releases",
                )
                releases = _rows(release_rows.get("items"))
                enriched.append(
                    {
                        **item,
                        "release_count": len(releases),
                        "release_status": releases[-1].get("status") if releases else "N_A",
                    }
                )
            all_sessions = enriched
            apply_filters()
            status.setText(f"Sessions: {len(all_sessions)} governed records")
        except (ProductDiscoveryError, W5PageError, RuntimeError) as exc:
            status.setText(f"Sessions: ERROR · {exc}")
            status.setProperty("tpaaState", "error")

    def select_session(row: int, _column: int) -> None:
        rows = getattr(table, "_tpaa_rows", [])
        if 0 <= row < len(rows):
            selected = rows[row]
            value = selected.get("session_id")
            if isinstance(value, str) and value:
                state.select_session(value)

    def browse_manifest() -> None:
        selected, _kind = qt_widgets.QFileDialog.getOpenFileName(
            root,
            "Select governed P1 request manifest",
            "",
            "TPAA P1 request (*.json);;JSON files (*.json)",
        )
        if selected:
            path_edit.setText(selected)

    def stage_manifest() -> None:
        nonlocal staged_payload, source_hash
        candidate = Path(path_edit.text().strip())
        try:
            if not candidate.is_file():
                raise W5PageError("W5_IMPORT_FILE_NOT_FOUND")
            raw = candidate.read_bytes()
            source_hash = hashlib.sha256(raw).hexdigest()
            result = _payload(
                transport.source_request_bytes(
                    "/api/v1/sources/p1-request/stage",
                    data=raw,
                    content_type="application/json",
                ),
                operation="stage_p1_manifest",
                expected=frozenset({201}),
            )
            payload = result.get("payload")
            if result.get("status") != "STAGED" or not isinstance(payload, Mapping):
                raise W5PageError("W5_IMPORT_STAGE_RESPONSE_INVALID")
            staged_payload = dict(payload)
            publish.setEnabled(True)
            families = result.get("source_families")
            status.setText(
                f"Import: STAGED · {result.get('source_document_count')} sources · {families}"
            )
            status.setProperty("tpaaState", "success")
        except (OSError, RuntimeError, W5PageError) as exc:
            staged_payload = None
            publish.setEnabled(False)
            status.setText(f"Import: FAILURE · {exc}")
            status.setProperty("tpaaState", "error")

    class _JobBridge(qt_core.QObject):  # type: ignore[misc]
        completed = qt_core.Signal(object, object)

    job_bridge = _JobBridge(root)

    def perform_publish() -> dict[str, object]:
        if staged_payload is None or source_hash is None:
            raise W5PageError("W5_STAGED_MANIFEST_REQUIRED")
        result = _payload(
            transport.job_request_json(
                "POST",
                "/jobs",
                body={"command": "BUILD_P1_RELEASE", "payload": staged_payload},
                headers={"Idempotency-Key": f"w5-p1-{source_hash}"},
            ),
            operation="build_p1_release",
            expected=frozenset({200, 202}),
        )
        identifier = result.get("job_id")
        if not isinstance(identifier, str) or not identifier:
            raise W5PageError("W5_JOB_ID_MISSING")
        return result

    def render_publish(result: object, error: object) -> None:
        publish.setEnabled(staged_payload is not None)
        stage.setEnabled(True)
        if error is not None:
            status.setText(f"Publication: FAILURE · {error}")
            status.setProperty("tpaaState", "error")
            return
        if not isinstance(result, Mapping):
            status.setText("Publication: FAILURE · W5_JOB_RESPONSE_INVALID")
            status.setProperty("tpaaState", "error")
            return
        identifier = result.get("job_id")
        if not isinstance(identifier, str) or not identifier:
            status.setText("Publication: FAILURE · W5_JOB_ID_MISSING")
            status.setProperty("tpaaState", "error")
            return
        job_id.setText(identifier)
        poll.setEnabled(True)
        job_status = result.get("status", "UNKNOWN")
        status.setText(f"Publication job: {job_status} · {identifier}")
        status.setProperty(
            "tpaaState",
            "success" if job_status == "SUCCEEDED" else "unknown",
        )
        if job_status == "SUCCEEDED":
            refresh_sessions()

    def publish_release_sync() -> None:
        try:
            render_publish(perform_publish(), None)
        except (RuntimeError, W5PageError) as exc:
            render_publish(None, exc)

    def publish_release() -> None:
        if staged_payload is None or source_hash is None:
            status.setText("Publication: staged manifest required")
            return
        publish.setEnabled(False)
        stage.setEnabled(False)
        status.setText("Publication job: RUNNING · governed P1 compute is in progress")
        status.setProperty("tpaaState", "unknown")

        def run() -> None:
            try:
                job_bridge.completed.emit(perform_publish(), None)
            except (RuntimeError, W5PageError) as exc:
                job_bridge.completed.emit(None, exc)

        threading.Thread(
            target=run,
            name="tpaa-w5-p1-publication",
            daemon=True,
        ).start()

    def refresh_job() -> None:
        identifier = job_id.text().strip()
        if not identifier:
            return
        try:
            result = _payload(
                transport.job_request_json("GET", f"/jobs/{identifier}"),
                operation="job_status",
            )
            job_status = result.get("status", "UNKNOWN")
            status.setText(f"Publication job: {job_status} · {identifier}")
            status.setProperty(
                "tpaaState",
                "success" if job_status == "SUCCEEDED" else "unknown",
            )
            if job_status == "SUCCEEDED":
                refresh_sessions()
        except (RuntimeError, W5PageError) as exc:
            status.setText(f"Job status: FAILURE · {exc}")
            status.setProperty("tpaaState", "error")

    refresh.clicked.connect(refresh_sessions)
    search.textChanged.connect(apply_filters)
    session_type.currentTextChanged.connect(apply_filters)
    data_status.currentTextChanged.connect(apply_filters)
    table.cellClicked.connect(select_session)
    browse.clicked.connect(browse_manifest)
    stage.clicked.connect(stage_manifest)
    publish.clicked.connect(publish_release)
    job_bridge.completed.connect(render_publish)
    poll.clicked.connect(refresh_job)
    root._tpaa_refresh_sessions = refresh_sessions
    root._tpaa_stage_manifest = stage_manifest
    root._tpaa_publish_release = publish_release_sync
    root._tpaa_publish_release_async = publish_release
    return root


def _metric_table(qt_widgets: Any, parent: Any, name: str) -> Any:
    table = qt_widgets.QTableWidget(parent)
    table.setObjectName(name)
    configure_table(table, qt_widgets)
    return table


def create_p02_page(
    qt_core: Any,
    qt_widgets: Any,
    parent: Any,
    *,
    transport: Any,
    state: ApplicationShellState,
) -> Any:
    """Exact Session/Episode overview with separated P1 subject lanes."""

    del qt_core
    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaP02Workflow")
    layout = qt_widgets.QVBoxLayout(root)
    controls = qt_widgets.QHBoxLayout()
    release_combo = qt_widgets.QComboBox(root)
    release_combo.setObjectName("tpaaP02ReleaseId")
    refresh = qt_widgets.QPushButton("Refresh exact Releases", root)
    load = qt_widgets.QPushButton("Load Session / Episode overview", root)
    controls.addWidget(release_combo, 1)
    controls.addWidget(refresh)
    controls.addWidget(load)
    layout.addLayout(controls)

    mission = qt_widgets.QGroupBox("Mission Header", root)
    mission_layout = qt_widgets.QGridLayout(mission)
    mission_labels: dict[str, Any] = {}
    for index, label in enumerate(
        ("Session", "Episode", "Context/Profile", "Release", "Data Confidence", "World Capability")
    ):
        key = label.lower().replace("/", "_").replace(" ", "_")
        value = qt_widgets.QLabel("—", mission)
        value.setObjectName(f"tpaaP02Mission{index}")
        mission_layout.addWidget(qt_widgets.QLabel(label, mission), index // 3, (index % 3) * 2)
        mission_layout.addWidget(value, index // 3, (index % 3) * 2 + 1)
        mission_labels[key] = value
    layout.addWidget(mission)

    splitter = qt_widgets.QSplitter(root)
    episode_tree = qt_widgets.QTreeWidget(splitter)
    episode_tree.setObjectName("tpaaP02EpisodeNavigator")
    episode_tree.setHeaderLabels(("Episode / Stage", "Status", "Coverage", "Time µs"))
    lanes = qt_widgets.QTabWidget(splitter)
    lanes.setObjectName("tpaaP02SubjectLanes")
    aircraft = _metric_table(qt_widgets, lanes, "tpaaP02AircraftPerformance")
    mission_system = _metric_table(qt_widgets, lanes, "tpaaP02MissionSystemPerformance")
    reference = _metric_table(qt_widgets, lanes, "tpaaP02ReferenceTruthQuality")
    lanes.addTab(aircraft, "Aircraft Performance")
    lanes.addTab(mission_system, "Mission-System Performance")
    lanes.addTab(reference, "Reference Truth Quality")
    splitter.addWidget(episode_tree)
    splitter.addWidget(lanes)
    splitter.setStretchFactor(1, 1)
    layout.addWidget(splitter, 1)
    status = qt_widgets.QLabel("Exact Release not loaded", root)
    status.setObjectName("tpaaP02Status")
    layout.addWidget(status)
    current: SessionOverviewProjection | None = None
    metric_columns = (
        ("metric_code", "Metric"),
        ("status", "Status"),
        ("value_kind", "Value kind"),
        ("unit", "Unit"),
        ("metric_instance_id", "Immutable metric instance"),
    )

    def refresh_releases() -> None:
        try:
            count = _populate_release_combo(release_combo, transport)
            status.setText(f"{count} immutable P1 Releases discovered")
        except (ProductDiscoveryError, RuntimeError) as exc:
            status.setText(f"Release discovery: ERROR · {exc}")

    def load_overview() -> None:
        nonlocal current
        release_id = release_combo.currentData()
        if not isinstance(release_id, str):
            status.setText("Exact Release selection required")
            return
        try:
            bundle = _exact_release_bundle(transport, release_id)
            current = _overview(bundle)
            mission_labels["session"].setText(current.session_id)
            mission_labels["episode"].setText(current.episode_id)
            mission_labels["context_profile"].setText(
                f"{current.context_id} / {current.context_version}"
            )
            mission_labels["release"].setText(
                f"{current.release_status} / {current.release_id}"
            )
            coverage = [_float_value(item.get("coverage")) for item in current.observations]
            confidence = [_float_value(item.get("confidence")) for item in current.observations]
            mission_labels["data_confidence"].setText(
                "UNKNOWN" if not confidence else f"{sum(confidence) / len(confidence):.3f}"
            )
            world = ", ".join(
                f"{item.get('world_kind', 'W')}:{item.get('status', 'UNKNOWN')}"
                for item in current.world_products
            )
            mission_labels["world_capability"].setText(world or "UNKNOWN")
            episode_tree.clear()
            root_item = qt_widgets.QTreeWidgetItem(
                (current.episode_id, "DETECTED", _display(min(coverage) if coverage else None), "")
            )
            root_item.setData(0, 32, current.episode_id)
            episode_tree.addTopLevelItem(root_item)
            for stage in current.stages:
                child = qt_widgets.QTreeWidgetItem(
                    (
                        str(stage.get("stage_type", "Stage")),
                        _display(stage.get("stage_status")),
                        _display(stage.get("coverage")),
                        f"{stage.get('start_session_time_us')}–{stage.get('end_session_time_us')}",
                    )
                )
                child.setData(0, 32, stage.get("stage_id"))
                root_item.addChild(child)
            root_item.setExpanded(True)
            _fill_table(aircraft, qt_widgets, current.aircraft_metrics, metric_columns)
            _fill_table(mission_system, qt_widgets, current.mission_system_metrics, metric_columns)
            _fill_table(reference, qt_widgets, current.reference_quality_metrics, metric_columns)
            state.update(
                session_id=current.session_id,
                episode_id=current.episode_id,
                context_id=current.context_id,
                context_version=current.context_version,
                release_id=current.release_id,
            )
            status.setText(
                f"Exact overview ready · Aircraft {len(current.aircraft_metrics)} · "
                f"Mission-System {len(current.mission_system_metrics)} · "
                f"Reference Quality {len(current.reference_quality_metrics)}"
            )
        except (RuntimeError, W5PageError, W5ProjectionError, ValueError) as exc:
            current = None
            status.setText(f"Overview: FAILURE · {exc}")

    def select_stage(item: Any, _column: int) -> None:
        if current is None:
            return
        identifier = item.data(0, 32)
        if item.parent() is None:
            state.select_episode(str(identifier))
        else:
            state.select_stage(str(identifier))

    refresh.clicked.connect(refresh_releases)
    load.clicked.connect(load_overview)
    episode_tree.itemClicked.connect(select_stage)
    root._tpaa_refresh_releases = refresh_releases
    root._tpaa_load_overview = load_overview
    return root


def _draw_series(scene: Any, rows: Sequence[Mapping[str, object]], field: str) -> int:
    values: list[tuple[float, float]] = []
    for row in rows:
        raw_time = row.get("session_time_us")
        raw_value = row.get(field)
        try:
            time_value = float(str(raw_time))
        except ValueError:
            continue
        if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
            values.append((time_value, float(raw_value)))
    scene.clear()
    if len(values) < 2:
        scene.addText(f"{field}: insufficient exact samples")
        return len(values)
    min_x, max_x = values[0][0], values[-1][0]
    ys = [value for _time, value in values]
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1e-12)
    points = [
        ((time - min_x) / span_x * 720.0, 210.0 - (value - min_y) / span_y * 180.0)
        for time, value in values
    ]
    for left, right in zip(points, points[1:], strict=False):
        scene.addLine(left[0], left[1], right[0], right[1])
    scene.addText(f"{field} · exact Session Time · {len(values)} samples")
    scene.setSceneRect(0, 0, 740, 240)
    return len(values)


def _draw_trajectory(scene: Any, presentation: Any) -> None:
    scene.clear()
    if len(presentation.samples) < 2:
        scene.addText("2D trajectory unavailable: fewer than two exact geodetic samples")
        return
    xs = [item.longitude_deg for item in presentation.samples]
    ys = [item.latitude_deg for item in presentation.samples]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-12)
    span_y = max(max_y - min_y, 1e-12)
    points = [
        ((x - min_x) / span_x * 720.0, 210.0 - (y - min_y) / span_y * 180.0)
        for x, y in zip(xs, ys, strict=True)
    ]
    for left, right in zip(points, points[1:], strict=False):
        scene.addLine(left[0], left[1], right[0], right[1])
    scene.addEllipse(points[0][0] - 4, points[0][1] - 4, 8, 8)
    scene.addEllipse(points[-1][0] - 4, points[-1][1] - 4, 8, 8)
    scene.addText(f"Exact 2D trajectory · {len(points)} samples")
    scene.setSceneRect(0, 0, 740, 240)


def create_p03_page(
    qt_core: Any,
    qt_widgets: Any,
    parent: Any,
    *,
    transport: Any,
    state: ApplicationShellState,
) -> Any:
    """Interactive evidence/replay with exact timeline, series and evidence linking."""

    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaP03Workflow")
    layout = qt_widgets.QVBoxLayout(root)
    controls = qt_widgets.QHBoxLayout()
    release_combo = qt_widgets.QComboBox(root)
    release_combo.setObjectName("tpaaP03ReleaseId")
    refresh = qt_widgets.QPushButton("Refresh exact Releases", root)
    load = qt_widgets.QPushButton("Load exact replay", root)
    previous = qt_widgets.QPushButton("◀ Previous Stage", root)
    next_button = qt_widgets.QPushButton("Next Stage ▶", root)
    controls.addWidget(release_combo, 1)
    controls.addWidget(refresh)
    controls.addWidget(load)
    controls.addWidget(previous)
    controls.addWidget(next_button)
    layout.addLayout(controls)

    top = qt_widgets.QSplitter(qt_core.Qt.Orientation.Horizontal, root)
    replay_tabs = qt_widgets.QTabWidget(top)
    trajectory_view = qt_widgets.QGraphicsView(replay_tabs)
    trajectory_view.setObjectName("tpaaP03Exact2DTrajectory")
    trajectory_scene = qt_widgets.QGraphicsScene(trajectory_view)
    trajectory_view.setScene(trajectory_scene)
    trajectory_scene.addText("Select an exact Release to load 2D trajectory")
    series_view = qt_widgets.QGraphicsView(replay_tabs)
    series_view.setObjectName("tpaaP03LinkedSeriesPlot")
    series_scene = qt_widgets.QGraphicsScene(series_view)
    series_view.setScene(series_scene)
    series_scene.addText("Linked exact series not loaded")
    replay_tabs.addTab(trajectory_view, "2D Replay")
    replay_tabs.addTab(series_view, "Linked Flight Plot")
    detail_tabs = qt_widgets.QTabWidget(top)
    metrics = _metric_table(qt_widgets, detail_tabs, "tpaaP03MetricTable")
    evidence = qt_widgets.QPlainTextEdit(detail_tabs)
    evidence.setObjectName("tpaaP03EvidenceDetail")
    evidence.setReadOnly(True)
    detail_tabs.addTab(metrics, "Metric / Observation")
    detail_tabs.addTab(evidence, "Evidence / Provenance")
    top.addWidget(replay_tabs)
    top.addWidget(detail_tabs)
    top.setStretchFactor(0, 2)
    top.setStretchFactor(1, 1)
    layout.addWidget(top, 2)

    timeline = qt_widgets.QTableWidget(root)
    timeline.setObjectName("tpaaP03MasterTimeline")
    configure_table(timeline, qt_widgets)
    timeline.setMinimumHeight(180)
    cursor = qt_widgets.QSlider(qt_core.Qt.Orientation.Horizontal, root)
    cursor.setObjectName("tpaaP03MasterTimeCursor")
    cursor.setRange(0, 1000)
    layout.addWidget(qt_widgets.QLabel("Master Timeline · Stage / W / P / A / J / M / Observation", root))
    layout.addWidget(timeline)
    layout.addWidget(cursor)
    status = qt_widgets.QLabel("Replay: exact Release not loaded", root)
    status.setObjectName("tpaaP03Status")
    layout.addWidget(status)
    active_release: str | None = None
    active_stages: list[dict[str, object]] = []
    time_bounds: tuple[int, int] | None = None
    metric_rows: list[dict[str, object]] = []

    def refresh_releases() -> None:
        try:
            count = _populate_release_combo(release_combo, transport)
            status.setText(f"Replay discovery: {count} immutable Releases")
        except (ProductDiscoveryError, RuntimeError) as exc:
            status.setText(f"Replay discovery: ERROR · {exc}")

    def load_replay() -> None:
        nonlocal active_release, active_stages, time_bounds, metric_rows
        release_id = release_combo.currentData()
        if not isinstance(release_id, str):
            status.setText("Replay: exact Release selection required")
            return
        try:
            bundle = _exact_release_bundle(transport, release_id)
            projection = _overview(bundle)
            replay = _payload(
                transport.m1_request_json("POST", f"/m1/releases/{release_id}/replay"),
                operation="historical_replay",
            )
            replay_status = verify_exact_replay(replay, release_id)
            active_release = release_id
            active_stages = list(projection.stages)
            session = cast(Mapping[str, object], bundle["topology"]["session"])
            start = int(str(session["start_session_time_us"]))
            end = int(str(session["end_session_time_us"]))
            time_bounds = (start, end)
            series = _payload(
                transport.m1_request_json(
                    "GET",
                    f"/m1/releases/{release_id}/series?start_session_time_us={start}"
                    f"&end_session_time_us={end}&limit=1000",
                ),
                operation="series",
            )
            _draw_series(series_scene, _rows(series.get("rows")), "nz_g")
            binding = _payload(
                transport.product_request_json(
                    "GET",
                    f"/api/v1/discovery/releases/{release_id}/presentation",
                ),
                operation="trajectory_binding",
            )
            trajectory_scene.clear()
            if binding.get("available") is True and isinstance(
                binding.get("presentation"), Mapping
            ):
                presentation = build_trajectory_presentation(
                    cast(Mapping[str, object], binding["presentation"]),
                    expected_release_id=release_id,
                )
                _draw_trajectory(trajectory_scene, presentation)
            else:
                trajectory_scene.addText(
                    "2D trajectory unavailable · "
                    + str(binding.get("reason_code", "UNKNOWN"))
                    + "\nNo inferred/current-data fallback is permitted."
                )
            _fill_table(
                timeline,
                qt_widgets,
                active_stages,
                (
                    ("stage_order", "#"),
                    ("stage_type", "Stage"),
                    ("stage_status", "Status"),
                    ("coverage", "Coverage"),
                    ("confidence", "Confidence"),
                    ("start_session_time_us", "Start µs"),
                    ("end_session_time_us", "End µs"),
                ),
            )
            metric_rows = _rows(bundle["metrics"].get("items"))
            _fill_table(
                metrics,
                qt_widgets,
                metric_rows,
                (
                    ("metric_code", "Metric"),
                    ("status", "Status"),
                    ("value_kind", "Kind"),
                    ("observation_lane", "Lane"),
                    ("metric_instance_id", "Exact instance"),
                ),
            )
            state.update(
                session_id=projection.session_id,
                episode_id=projection.episode_id,
                context_id=projection.context_id,
                context_version=projection.context_version,
                release_id=release_id,
                time_start_us=start,
                time_end_us=end,
            )
            status.setText(
                f"Replay: {replay_status} · exact Release {release_id} · "
                f"{series.get('returned', 0)} linked samples"
            )
        except (
            RuntimeError,
            W5PageError,
            W5ProjectionError,
            VisualizationPresentationError,
            KeyError,
            ValueError,
        ) as exc:
            active_release = None
            status.setText(f"Replay: FAILURE · {exc}")

    def select_stage(row: int, _column: int) -> None:
        if not (0 <= row < len(active_stages)):
            return
        stage = active_stages[row]
        start = int(str(stage["start_session_time_us"]))
        end = int(str(stage["end_session_time_us"]))
        state.update(
            stage_id=str(stage["stage_id"]),
            time_start_us=start,
            time_end_us=end,
        )
        if time_bounds is not None:
            span = max(time_bounds[1] - time_bounds[0], 1)
            cursor.setValue(round((start - time_bounds[0]) / span * 1000))

    def shift_stage(delta: int) -> None:
        if not active_stages:
            return
        row = timeline.currentRow()
        row = 0 if row < 0 else max(0, min(len(active_stages) - 1, row + delta))
        timeline.selectRow(row)
        select_stage(row, 0)

    def select_metric(row: int, _column: int) -> None:
        if active_release is None or not (0 <= row < len(metric_rows)):
            return
        metric = metric_rows[row]
        code = metric.get("metric_code")
        if not isinstance(code, str):
            return
        try:
            detail = _payload(
                transport.m1_request_json(
                    "GET", f"/m1/releases/{active_release}/metrics/{code}"
                ),
                operation="metric_detail",
            )
            proof = _payload(
                transport.m1_request_json(
                    "GET",
                    f"/m1/releases/{active_release}/metrics/{code}/evidence",
                ),
                operation="metric_evidence",
            )
            if detail.get("release_id") != active_release or proof.get("release_id") != active_release:
                raise W5PageError("W5_METRIC_EVIDENCE_RELEASE_DRIFT")
            evidence.setPlainText(
                json.dumps(
                    {"metric": detail, "evidence": proof},
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            detail_tabs.setCurrentWidget(evidence)
            state.update(
                metric_instance_id=str(detail.get("metric_instance_id")),
                observation_id=next(
                    (
                        str(item.get("observation_id"))
                        for item in _rows(
                            _exact_release_bundle(transport, active_release)["observations"].get(
                                "items"
                            )
                        )
                        if item.get("observed_metric_instance_id")
                        == detail.get("metric_instance_id")
                    ),
                    None,
                ),
            )
            status.setText(f"Evidence linked · {code} · immutable exact Release")
        except (RuntimeError, W5PageError) as exc:
            status.setText(f"Evidence: FAILURE · {exc}")

    refresh.clicked.connect(refresh_releases)
    load.clicked.connect(load_replay)
    timeline.cellClicked.connect(select_stage)
    metrics.cellClicked.connect(select_metric)
    previous.clicked.connect(lambda: shift_stage(-1))
    next_button.clicked.connect(lambda: shift_stage(1))
    root._tpaa_refresh_releases = refresh_releases
    root._tpaa_load_replay = load_replay
    return root


def create_p12_page(
    qt_core: Any,
    qt_widgets: Any,
    parent: Any,
    *,
    transport: Any,
    state: ApplicationShellState,
) -> Any:
    """Data quality, World coverage, and non-lossy Observation eligibility."""

    del qt_core
    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaP12Workflow")
    layout = qt_widgets.QVBoxLayout(root)
    controls = qt_widgets.QHBoxLayout()
    combo = qt_widgets.QComboBox(root)
    combo.setObjectName("tpaaP12ReleaseId")
    refresh = qt_widgets.QPushButton("Refresh exact Releases", root)
    load = qt_widgets.QPushButton("Load Data Quality", root)
    controls.addWidget(combo, 1)
    controls.addWidget(refresh)
    controls.addWidget(load)
    layout.addLayout(controls)
    cards = qt_widgets.QHBoxLayout()
    card_labels: dict[str, Any] = {}
    for title in ("Overall Data Quality", "World Capability", "M Coverage", "Observation Eligibility"):
        frame = qt_widgets.QFrame(root)
        frame.setProperty("tpaaSurface", True)
        frame_layout = qt_widgets.QVBoxLayout(frame)
        heading = qt_widgets.QLabel(title, frame)
        heading.setProperty("tpaaMuted", True)
        value = qt_widgets.QLabel("UNKNOWN", frame)
        value.setProperty("tpaaHeading", True)
        frame_layout.addWidget(heading)
        frame_layout.addWidget(value)
        cards.addWidget(frame)
        card_labels[title] = value
    layout.addLayout(cards)
    tabs = qt_widgets.QTabWidget(root)
    quality = _metric_table(qt_widgets, tabs, "tpaaP12QualityDimensions")
    coverage = _metric_table(qt_widgets, tabs, "tpaaP12WorldCoverage")
    eligibility = _metric_table(qt_widgets, tabs, "tpaaP12ObservationEligibility")
    tabs.addTab(quality, "Time / Reference / Association Quality")
    tabs.addTab(coverage, "Source / World Coverage")
    tabs.addTab(eligibility, "Observation Eligibility")
    layout.addWidget(tabs, 1)
    status = qt_widgets.QLabel("Quality: exact Release not loaded", root)
    status.setObjectName("tpaaP12Status")
    layout.addWidget(status)

    def refresh_releases() -> None:
        try:
            status.setText(f"{_populate_release_combo(combo, transport)} immutable Releases")
        except (ProductDiscoveryError, RuntimeError) as exc:
            status.setText(f"Quality discovery: ERROR · {exc}")

    def load_quality() -> None:
        release_id = combo.currentData()
        if not isinstance(release_id, str):
            status.setText("Quality: exact Release selection required")
            return
        try:
            projection = _overview(_exact_release_bundle(transport, release_id))
            rows = list(observation_quality_rows(projection))
            counts: dict[str, int] = {}
            for item in rows:
                key = str(item.get("eligibility", "UNKNOWN"))
                counts[key] = counts.get(key, 0) + 1
            eligible = counts.get("ELIGIBLE", 0)
            review = counts.get("REVIEW_REQUIRED", 0)
            excluded = counts.get("EXCLUDED", 0)
            overall = (
                "UNKNOWN"
                if not rows
                else "REVIEW_REQUIRED"
                if review or excluded
                else "READY"
            )
            worlds = list(projection.world_products)
            world_ready = sum(1 for item in worlds if item.get("status") == "READY")
            card_values = {
                "Overall Data Quality": overall,
                "World Capability": f"{world_ready}/{len(worlds)} READY" if worlds else "UNKNOWN",
                "M Coverage": _display(
                    min(
                        (
                            _float_value(item.get("coverage"))
                            for item in worlds
                            if item.get("world_kind") == "MACHINE"
                        ),
                        default=None,
                    )
                ),
                "Observation Eligibility": (
                    f"{eligible} eligible · {review} review · {excluded} excluded"
                ),
            }
            for title, value in card_values.items():
                card_labels[title].setText(value)
                card_labels[title].setProperty(
                    "tpaaState", status_meaning(value.split()[0]).kind
                )
            metric_rows = list(projection.reference_quality_metrics)
            dimensions = (
                ("Ownship/Target INS time uncertainty", ("TIME", "UNCERTAINTY")),
                ("Sensor Time Offset", ("TIME", "OFFSET")),
                ("Sensor-to-INS Latency", ("LATENCY",)),
                ("Interpolation Age", ("INTERPOLATION", "AGE")),
                ("Reference Truth Uncertainty", ("REFERENCE", "UNCERTAINTY")),
                ("Association Coverage", ("ASSOCIATION", "COVERAGE")),
            )
            dimension_rows: list[dict[str, object]] = []
            for label, tokens in dimensions:
                match = next(
                    (
                        item
                        for item in metric_rows
                        if all(token in str(item.get("metric_code", "")).upper() for token in tokens)
                    ),
                    None,
                )
                dimension_rows.append(
                    {
                        "dimension": label,
                        "status": "UNKNOWN" if match is None else match.get("status"),
                        "metric_code": None if match is None else match.get("metric_code"),
                        "evidence": None if match is None else match.get("metric_instance_id"),
                    }
                )
            _fill_table(
                quality,
                qt_widgets,
                dimension_rows,
                (
                    ("dimension", "Quality dimension"),
                    ("status", "Status"),
                    ("metric_code", "Governed metric"),
                    ("evidence", "Exact evidence anchor"),
                ),
            )
            _fill_table(
                coverage,
                qt_widgets,
                worlds,
                (
                    ("world_kind", "World / Source"),
                    ("status", "Status"),
                    ("coverage", "Coverage"),
                    ("confidence", "Confidence"),
                    ("reason_codes", "Reason codes"),
                    ("world_product_id", "Exact World product"),
                ),
            )
            _fill_table(
                eligibility,
                qt_widgets,
                rows,
                (
                    ("metric_code", "Metric"),
                    ("eligibility", "Eligibility"),
                    ("coverage", "Coverage"),
                    ("confidence", "Confidence"),
                    ("reason", "Exclusion / review reason"),
                    ("evidence_set_id", "Evidence"),
                    ("observation_id", "Observation"),
                ),
            )
            state.update(
                session_id=projection.session_id,
                episode_id=projection.episode_id,
                context_id=projection.context_id,
                context_version=projection.context_version,
                release_id=release_id,
            )
            status.setText(
                f"Quality ready · all {len(rows)} observations retained · "
                "N/A / Unknown / Failure remain distinct"
            )
        except (RuntimeError, W5PageError, W5ProjectionError, ValueError) as exc:
            status.setText(f"Quality: FAILURE · {exc}")

    refresh.clicked.connect(refresh_releases)
    load.clicked.connect(load_quality)
    root._tpaa_refresh_releases = refresh_releases
    root._tpaa_load_quality = load_quality
    return root


def create_p13_page(
    qt_core: Any,
    qt_widgets: Any,
    parent: Any,
    *,
    transport: Any,
    state: ApplicationShellState,
) -> Any:
    """Version/publication/model/access/audit/runtime governance cockpit."""

    del qt_core
    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaP13Workflow")
    layout = qt_widgets.QVBoxLayout(root)
    controls = qt_widgets.QHBoxLayout()
    combo = qt_widgets.QComboBox(root)
    combo.setObjectName("tpaaP13ReleaseId")
    refresh = qt_widgets.QPushButton("Refresh governance", root)
    load = qt_widgets.QPushButton("Load exact governance snapshot", root)
    controls.addWidget(combo, 1)
    controls.addWidget(refresh)
    controls.addWidget(load)
    layout.addLayout(controls)
    tabs = qt_widgets.QTabWidget(root)
    tabs.setObjectName("tpaaP13GovernanceTabs")
    panels: dict[str, Any] = {}
    for title, name in (
        ("Release / Publication / Provenance", "release"),
        ("Catalog / Profiles / Context", "catalog"),
        ("Models / Twins", "models"),
        ("Permissions / Approvals", "permissions"),
        ("Audit / Runtime", "runtime"),
    ):
        panel = qt_widgets.QPlainTextEdit(tabs)
        panel.setObjectName(f"tpaaP13{name.title()}Panel")
        panel.setReadOnly(True)
        panel.setPlainText("Exact governed snapshot not loaded")
        tabs.addTab(panel, title)
        panels[name] = panel
    layout.addWidget(tabs, 1)
    status = qt_widgets.QLabel("Governance: exact Release not loaded", root)
    status.setObjectName("tpaaP13Status")
    layout.addWidget(status)

    def refresh_governance() -> None:
        try:
            count = _populate_release_combo(combo, transport)
            status.setText(f"Governance: {count} exact P1 Releases discovered")
        except (ProductDiscoveryError, RuntimeError) as exc:
            status.setText(f"Governance discovery: ERROR · {exc}")

    def load_governance() -> None:
        release_id = combo.currentData()
        if not isinstance(release_id, str):
            status.setText("Governance: exact Release selection required")
            return
        try:
            bundle = _exact_release_bundle(transport, release_id)
            projection = _overview(bundle)
            replay = _payload(
                transport.m1_request_json("POST", f"/m1/releases/{release_id}/replay"),
                operation="governance_replay",
            )
            verify_exact_replay(replay, release_id)
            models: dict[str, object] = {}
            for kind in ("P3_TWIN", "P3_ESTIMATE", "P6_MODEL"):
                try:
                    models[kind] = product_items(transport, kind)
                except ProductDiscoveryError as exc:
                    models[kind] = {"status": "UNAVAILABLE", "reason": str(exc)}
            permissions_status, permissions_payload = transport.security_request_json(
                "GET", "/security/approvals"
            )
            qualification = _payload(
                transport.runtime_request_json("GET", "/runtime/qualification"),
                operation="runtime_qualification",
            )
            observability = _payload(
                transport.runtime_request_json("GET", "/runtime/observability"),
                operation="runtime_observability",
            )
            release_view = {
                "release": bundle["release"],
                "historical_replay": {
                    "status": replay.get("status"),
                    "current_latest_fallback_used": replay.get(
                        "current_latest_fallback_used", False
                    ),
                    "manifest_hash": replay.get("manifest_hash")
                    or bundle["release"].get("manifest_hash"),
                },
            }
            definition_versions = sorted(
                {
                    (
                        str(item.get("metric_code")),
                        str(item.get("definition_hash")),
                    )
                    for item in _rows(bundle["metrics"].get("items"))
                }
            )
            catalog_view = {
                "catalog_version": bundle["release"].get("catalog_version"),
                "catalog_hash": bundle["release"].get("catalog_hash"),
                "context": bundle["context"],
                "metric_semantic_bindings": definition_versions,
                "reference_truth_profile": "UNKNOWN if not present in exact Context/Metric evidence",
                "sensor_installation_alignment_profile": (
                    "UNKNOWN if not present in exact Metric evidence"
                ),
                "golden_status": qualification.get("status", "UNKNOWN"),
            }
            permissions_view = {
                "http_status": permissions_status,
                "approval_inbox": dict(permissions_payload),
                "mutation_policy": "signed Desktop identity + server authorization guard",
            }
            runtime_view = {
                "qualification": qualification,
                "observability": observability,
                "release_audit_anchor": bundle["release"].get("manifest_hash"),
                "historical_replay": replay,
            }
            for name, value in (
                ("release", release_view),
                ("catalog", catalog_view),
                ("models", models),
                ("permissions", permissions_view),
                ("runtime", runtime_view),
            ):
                panels[name].setPlainText(
                    json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)
                )
            state.update(
                session_id=projection.session_id,
                episode_id=projection.episode_id,
                context_id=projection.context_id,
                context_version=projection.context_version,
                release_id=release_id,
            )
            status.setText(
                "Governance ready · exact Release/Catalog/Profile/Model/Permission/Audit/Runtime"
            )
        except (RuntimeError, W5PageError, W5ProjectionError, ValueError) as exc:
            status.setText(f"Governance: FAILURE · {exc}")

    refresh.clicked.connect(refresh_governance)
    load.clicked.connect(load_governance)
    root._tpaa_refresh_governance = refresh_governance
    root._tpaa_load_governance = load_governance
    return root


__all__ = [
    "W5PageError",
    "create_p01_page",
    "create_p02_page",
    "create_p03_page",
    "create_p12_page",
    "create_p13_page",
]
