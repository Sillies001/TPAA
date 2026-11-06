"""W7 P11 production workspace: course/LVC, P6 planning, media, and gates."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast

from .components import configure_table
from .discovery import ProductDiscoveryError, product_items
from .ed2_upper import build_linked_debrief_projection
from .m9_workspace import build_m9_layered_workspace_model
from .w7_projection import (
    W7ProjectionError,
    build_capability_gate,
    build_model_registry_projection,
    build_upper_product_projection,
    local_external_capability_gates,
)


class W7PageError(RuntimeError):
    """Stable W7 GUI orchestration error."""


def _display(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return format(value, ".4g")
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _success(result: tuple[int, Mapping[str, object]], *, operation: str) -> dict[str, object]:
    status, payload = result
    if status not in {200, 201}:
        raise W7PageError(f"{operation}:HTTP_{status}:{payload.get('error')!r}")
    return dict(payload)


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


def _heading(qt_widgets: Any, parent: Any, text: str, name: str) -> Any:
    label = qt_widgets.QLabel(text, parent)
    label.setObjectName(name)
    label.setWordWrap(True)
    label.setProperty("tpaaHeading", True)
    return label


def _status(qt_widgets: Any, parent: Any, text: str, name: str) -> Any:
    label = qt_widgets.QLabel(text, parent)
    label.setObjectName(name)
    label.setWordWrap(True)
    label.setProperty("tpaaMuted", True)
    return label


def _upper_items(transport: Any, kind: str) -> list[dict[str, object]]:
    payload = _success(
        transport.product_request_json("GET", f"/api/v1/upper/{kind}"),
        operation=f"{kind}_INDEX",
    )
    if payload.get("schema") != "TPAA_ED2_UPPER_PRODUCT_INDEX_V1":
        raise W7PageError(f"{kind}_INDEX_SCHEMA_INVALID")
    if payload.get("current_latest_fallback_used") is not False:
        raise W7PageError(f"{kind}_MUTABLE_ALIAS_FORBIDDEN")
    raw = payload.get("items")
    if not isinstance(raw, list):
        raise W7PageError(f"{kind}_INDEX_ITEMS_INVALID")
    result: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise W7PageError(f"{kind}_INDEX_ITEM_INVALID")
        snapshot_id = item.get("snapshot_id")
        if not isinstance(snapshot_id, str) or not snapshot_id:
            raise W7PageError(f"{kind}_INDEX_ID_INVALID")
        result.append(dict(cast(Mapping[str, object], item)))
    return result


def _add_upper_items(selector: Any, items: Sequence[Mapping[str, object]]) -> None:
    prior = selector.currentData()
    selector.clear()
    for item in items:
        exact_id = str(item["snapshot_id"])
        selector.addItem(f"{item.get('as_of_utc', '—')} · {exact_id}", exact_id)
    if prior:
        index = selector.findData(prior)
        if index >= 0:
            selector.setCurrentIndex(index)


def _create_course_lvc_tab(qt_widgets: Any, parent: Any, transport: Any) -> Any:
    root = qt_widgets.QWidget(parent)
    layout = qt_widgets.QVBoxLayout(root)
    layout.addWidget(
        _heading(
            qt_widgets,
            root,
            "Course / Unit analytics and Joint-LVC contract snapshots",
            "tpaaP11CourseLvcHeading",
        )
    )
    guard = _status(
        qt_widgets,
        root,
        "Aggregates obey cohort suppression. A gateway snapshot proves mapping lineage only; "
        "it never claims a live external connection.",
        "tpaaP11LvcClaimGuard",
    )
    guard.setProperty("tpaaState", "error")
    layout.addWidget(guard)

    controls = qt_widgets.QWidget(root)
    controls_layout = qt_widgets.QGridLayout(controls)
    course = qt_widgets.QComboBox(controls)
    course.setObjectName("tpaaP11CourseExact")
    gateway = qt_widgets.QComboBox(controls)
    gateway.setObjectName("tpaaP11GatewayExact")
    refresh = qt_widgets.QPushButton("Refresh immutable snapshots", controls)
    load_course = qt_widgets.QPushButton("Load Course / Unit", controls)
    load_gateway = qt_widgets.QPushButton("Load Joint-LVC contract", controls)
    controls_layout.addWidget(course, 0, 0)
    controls_layout.addWidget(load_course, 0, 1)
    controls_layout.addWidget(gateway, 1, 0)
    controls_layout.addWidget(load_gateway, 1, 1)
    controls_layout.addWidget(refresh, 2, 0, 1, 2)
    layout.addWidget(controls)

    summary = _status(qt_widgets, root, "No exact snapshot selected", "tpaaP11CourseLvcStatus")
    table = qt_widgets.QTableWidget(root)
    table.setObjectName("tpaaP11CourseLvcDetails")
    configure_table(table, qt_widgets)
    layout.addWidget(summary)
    layout.addWidget(table, 1)

    def refresh_items() -> None:
        try:
            _add_upper_items(course, _upper_items(transport, "COURSE_UNIT_ANALYTICS"))
            _add_upper_items(gateway, _upper_items(transport, "JOINT_LVC_GATEWAY"))
            summary.setText(
                f"History ready · analytics={course.count()} · gateway contracts={gateway.count()}"
            )
        except (W7PageError, W7ProjectionError) as exc:
            summary.setText(f"Discovery failed closed · {exc}")
            summary.setProperty("tpaaState", "error")

    def load(kind: str, selector: Any) -> None:
        snapshot_id = str(selector.currentData() or "")
        if not snapshot_id:
            summary.setText(f"EMPTY · no {kind} snapshot is available")
            return
        payload = _success(
            transport.product_request_json("GET", f"/api/v1/upper/{kind}/{snapshot_id}"),
            operation=f"{kind}_EXACT",
        )
        projection = build_upper_product_projection(
            payload,
            expected_snapshot_id=snapshot_id,
            expected_kind=kind,
        )
        rows = [{"field": key, "value": value} for key, value in projection.payload.items()]
        _fill_table(
            table,
            qt_widgets,
            rows,
            (("field", "Governed field"), ("value", "Exact value")),
        )
        suffix = (
            "live endpoint NOT asserted"
            if kind == "JOINT_LVC_GATEWAY"
            else "privacy suppression verified"
        )
        summary.setText(
            f"{kind} · exact={projection.snapshot_id} · as-of={projection.as_of_utc} · {suffix}"
        )

    refresh.clicked.connect(refresh_items)
    load_course.clicked.connect(lambda: load("COURSE_UNIT_ANALYTICS", course))
    load_gateway.clicked.connect(lambda: load("JOINT_LVC_GATEWAY", gateway))
    root._tpaa_refresh = refresh_items
    return root


def _semantic_box(
    qt_widgets: Any,
    parent: Any,
    *,
    title: str,
    name: str,
    color: str,
) -> tuple[Any, Any]:
    box = qt_widgets.QGroupBox(title, parent)
    box.setObjectName(name)
    box.setProperty("tpaaSemanticClass", title.split(" · ", 1)[0])
    box.setStyleSheet(f"QGroupBox#{name} {{ border-left: 6px solid {color}; padding: 8px; }}")
    layout = qt_widgets.QVBoxLayout(box)
    detail = qt_widgets.QLabel("Unavailable", box)
    detail.setWordWrap(True)
    layout.addWidget(detail)
    return box, detail


def _create_planning_tab(qt_widgets: Any, parent: Any, transport: Any) -> Any:
    root = qt_widgets.QWidget(parent)
    layout = qt_widgets.QVBoxLayout(root)
    layout.addWidget(
        _heading(
            qt_widgets,
            root,
            "P6 Forecast / Counterfactual / Recommendation planning",
            "tpaaP11PlanningHeading",
        )
    )
    guard = _status(
        qt_widgets,
        root,
        "The four lanes have permanent visual semantics. Forecast and counterfactual "
        "outputs are projections and can never be upgraded to factual history by this GUI.",
        "tpaaP11ProjectionGuard",
    )
    guard.setProperty("tpaaState", "error")
    layout.addWidget(guard)

    selection = qt_widgets.QWidget(root)
    selection_layout = qt_widgets.QGridLayout(selection)
    recommendation = qt_widgets.QComboBox(selection)
    recommendation.setObjectName("tpaaP11RecommendationExact")
    forecast = qt_widgets.QComboBox(selection)
    forecast.setObjectName("tpaaP11ForecastExact")
    counterfactual = qt_widgets.QComboBox(selection)
    counterfactual.setObjectName("tpaaP11CounterfactualExact")
    refresh = qt_widgets.QPushButton("Refresh recommendation history", selection)
    load = qt_widgets.QPushButton("Load exact governed workspace", selection)
    selection_layout.addWidget(recommendation, 0, 0, 1, 2)
    selection_layout.addWidget(forecast, 1, 0)
    selection_layout.addWidget(counterfactual, 1, 1)
    selection_layout.addWidget(refresh, 2, 0)
    selection_layout.addWidget(load, 2, 1)
    layout.addWidget(selection)

    lanes = qt_widgets.QWidget(root)
    lanes_layout = qt_widgets.QGridLayout(lanes)
    fact_box, fact_detail = _semantic_box(
        qt_widgets,
        lanes,
        title="ACTUAL · immutable factual history",
        name="tpaaP11ActualLane",
        color="#526174",
    )
    forecast_box, forecast_detail = _semantic_box(
        qt_widgets,
        lanes,
        title="FORECAST · predictive projection",
        name="tpaaP11ForecastLane",
        color="#1769aa",
    )
    counter_box, counter_detail = _semantic_box(
        qt_widgets,
        lanes,
        title="COUNTERFACTUAL · scenario projection",
        name="tpaaP11CounterfactualLane",
        color="#e07a00",
    )
    advisory_box, advisory_detail = _semantic_box(
        qt_widgets,
        lanes,
        title="RECOMMENDATION · governed advisory",
        name="tpaaP11RecommendationLane",
        color="#7b3fb2",
    )
    lanes_layout.addWidget(fact_box, 0, 0)
    lanes_layout.addWidget(forecast_box, 0, 1)
    lanes_layout.addWidget(counter_box, 1, 0)
    lanes_layout.addWidget(advisory_box, 1, 1)
    layout.addWidget(lanes, 1)

    approval = qt_widgets.QGroupBox("Recommendation approval transition", root)
    approval_layout = qt_widgets.QHBoxLayout(approval)
    target = qt_widgets.QComboBox(approval)
    target.setObjectName("tpaaP11RecommendationTargetState")
    target.addItems(("IN_REVIEW", "APPROVED", "RELEASED", "REJECTED"))
    reason = qt_widgets.QLineEdit(approval)
    reason.setObjectName("tpaaP11RecommendationReason")
    reason.setPlaceholderText("Required independent review reason")
    approve = qt_widgets.QPushButton("Create immutable approval revision", approval)
    approval_layout.addWidget(target)
    approval_layout.addWidget(reason, 1)
    approval_layout.addWidget(approve)
    layout.addWidget(approval)
    workflow_status = _status(
        qt_widgets, root, "No approval action submitted", "tpaaP11ApprovalStatus"
    )
    layout.addWidget(workflow_status)

    recommendation_items: list[dict[str, object]] = []

    def update_sources(_value: str = "") -> None:
        exact_id = str(recommendation.currentData() or "")
        forecasts: list[str] = []
        counterfactuals: list[str] = []
        for item in recommendation_items:
            if item.get("exact_id") != exact_id:
                continue
            metadata = item.get("metadata")
            if isinstance(metadata, Mapping):
                raw_forecasts = metadata.get("source_forecast_result_ids", [])
                raw_counterfactuals = metadata.get("source_counterfactual_run_ids", [])
                if isinstance(raw_forecasts, list):
                    forecasts = [str(value) for value in raw_forecasts]
                if isinstance(raw_counterfactuals, list):
                    counterfactuals = [str(value) for value in raw_counterfactuals]
            break
        forecast.clear()
        forecast.addItems(forecasts)
        counterfactual.clear()
        counterfactual.addItems(counterfactuals)

    def refresh_items() -> None:
        nonlocal recommendation_items
        try:
            recommendation_items = product_items(transport, "P6_RECOMMENDATION")
        except ProductDiscoveryError as exc:
            workflow_status.setText(f"Discovery failed closed · {exc}")
            workflow_status.setProperty("tpaaState", "error")
            return
        prior = recommendation.currentData()
        recommendation.clear()
        for item in recommendation_items:
            exact_id = str(item["exact_id"])
            metadata = cast(Mapping[str, object], item["metadata"])
            recommendation.addItem(f"{metadata.get('approval_state', '—')} · {exact_id}", exact_id)
        if prior:
            index = recommendation.findData(prior)
            if index >= 0:
                recommendation.setCurrentIndex(index)
        update_sources()
        workflow_status.setText(
            f"Immutable recommendation history: {len(recommendation_items)} revision(s)"
        )

    def load_workspace() -> None:
        forecast_id = forecast.currentText().strip()
        counterfactual_id = counterfactual.currentText().strip()
        recommendation_id = str(recommendation.currentData() or "")
        if not all((forecast_id, counterfactual_id, recommendation_id)):
            workflow_status.setText("EMPTY · exact linked P6 revisions are required")
            return
        path = (
            f"/m9/workspace/forecast/{forecast_id}"
            f"/counterfactual/{counterfactual_id}"
            f"/recommendation/{recommendation_id}"
        )
        payload = _success(transport.m9_request_json("GET", path), operation="P11_P6_EXACT")
        model = build_m9_layered_workspace_model(
            payload,
            expected_forecast_result_id=forecast_id,
            expected_counterfactual_run_id=counterfactual_id,
            expected_recommendation_id=recommendation_id,
        )
        fact_detail.setText(
            "Layer=P1-P5 factual history\nImmutable refs=" + ", ".join(model.exact_fact_refs)
        )
        forecast_detail.setText(
            f"Revision={model.forecast.product_id}\n"
            f"Applicability={model.forecast.applicability_status}\n"
            f"Uncertainty={_display(model.forecast.uncertainty)}\n"
            f"Release={model.forecast.release_state}"
        )
        counter_detail.setText(
            f"Revision={model.counterfactual.product_id}\n"
            f"Applicability={model.counterfactual.applicability_status}\n"
            f"Assumptions={_display(model.counterfactual.assumptions)}\n"
            f"Release={model.counterfactual.release_state}"
        )
        advisory_detail.setText(
            f"Revision={model.recommendation.recommendation_id}\n"
            f"Approval={model.recommendation.approval_state}\n"
            f"Applicability={model.recommendation.applicability_status}\n"
            f"Release={model.recommendation.release_state}"
        )
        workflow_status.setText(
            f"Exact workspace verified · logical hash={model.logical_product_hash}"
        )

    def transition() -> None:
        recommendation_id = str(recommendation.currentData() or "")
        why = reason.text().strip()
        if not recommendation_id or not why:
            workflow_status.setText(
                "APPROVAL REQUIRED · exact recommendation and reason are mandatory"
            )
            return
        payload = _success(
            transport.m9_request_json(
                "POST",
                f"/m9/recommendations/{recommendation_id}/approval",
                body={
                    "request_id": str(uuid.uuid4()),
                    "target_state": target.currentText(),
                    "reason": why,
                    "created_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                },
            ),
            operation="P11_RECOMMENDATION_APPROVAL",
        )
        workflow_status.setText(
            f"Immutable transition accepted · state={payload.get('approval_state')} · "
            f"revision={payload.get('recommendation_id')}"
        )
        refresh_items()

    recommendation.currentTextChanged.connect(update_sources)
    refresh.clicked.connect(refresh_items)
    load.clicked.connect(load_workspace)
    approve.clicked.connect(transition)
    root._tpaa_refresh = refresh_items
    root._tpaa_load = load_workspace
    return root


def _create_media_tab(qt_widgets: Any, parent: Any, transport: Any) -> Any:
    root = qt_widgets.QWidget(parent)
    layout = qt_widgets.QVBoxLayout(root)
    layout.addWidget(
        _heading(
            qt_widgets,
            root,
            "Media / transcript / master-time review and exact compare",
            "tpaaP11MediaHeading",
        )
    )
    controls = qt_widgets.QWidget(root)
    controls_layout = qt_widgets.QGridLayout(controls)
    primary = qt_widgets.QComboBox(controls)
    primary.setObjectName("tpaaP11MediaPrimaryExact")
    comparison = qt_widgets.QComboBox(controls)
    comparison.setObjectName("tpaaP11MediaComparisonExact")
    mode = qt_widgets.QComboBox(controls)
    mode.setObjectName("tpaaP11CompareMode")
    mode.addItems(("ABSOLUTE_SESSION_TIME", "STAGE_ALIGNED"))
    refresh = qt_widgets.QPushButton("Refresh media history", controls)
    load = qt_widgets.QPushButton("Load exact review", controls)
    controls_layout.addWidget(primary, 0, 0)
    controls_layout.addWidget(comparison, 0, 1)
    controls_layout.addWidget(mode, 1, 0)
    controls_layout.addWidget(refresh, 1, 1)
    controls_layout.addWidget(load, 2, 0, 1, 2)
    layout.addWidget(controls)
    summary = _status(qt_widgets, root, "No exact media snapshot selected", "tpaaP11MediaStatus")
    layout.addWidget(summary)

    tabs = qt_widgets.QTabWidget(root)
    timeline = qt_widgets.QTableWidget(tabs)
    timeline.setObjectName("tpaaP11MasterTimeline")
    media = qt_widgets.QTableWidget(tabs)
    media.setObjectName("tpaaP11MediaAssets")
    bookmarks = qt_widgets.QTableWidget(tabs)
    bookmarks.setObjectName("tpaaP11Bookmarks")
    playlists = qt_widgets.QTableWidget(tabs)
    playlists.setObjectName("tpaaP11Playlists")
    for table in (timeline, media, bookmarks, playlists):
        configure_table(table, qt_widgets)
    tabs.addTab(timeline, "Master timeline")
    tabs.addTab(media, "Media / transcript")
    tabs.addTab(bookmarks, "Bookmarks")
    tabs.addTab(playlists, "Playlists")
    layout.addWidget(tabs, 1)

    export = qt_widgets.QPushButton(
        "Export disabled — accepted object-store/redaction gate required", root
    )
    export.setObjectName("tpaaP11MediaExport")
    export.setEnabled(False)
    layout.addWidget(export)

    def refresh_items() -> None:
        try:
            items = _upper_items(transport, "MEDIA_DEBRIEF")
            _add_upper_items(primary, items)
            _add_upper_items(comparison, items)
            if comparison.count() > 1:
                comparison.setCurrentIndex(1)
            summary.setText(
                f"Immutable media history: {len(items)} snapshot(s); no current/latest alias"
            )
        except W7PageError as exc:
            summary.setText(f"Media discovery failed closed · {exc}")
            summary.setProperty("tpaaState", "error")

    def exact(snapshot_id: str) -> dict[str, object]:
        return _success(
            transport.product_request_json("GET", f"/api/v1/upper/MEDIA_DEBRIEF/{snapshot_id}"),
            operation="MEDIA_DEBRIEF_EXACT",
        )

    def load_exact() -> None:
        primary_id = str(primary.currentData() or "")
        comparison_id = str(comparison.currentData() or "")
        if not primary_id:
            summary.setText("EMPTY · no media debrief snapshot is available")
            return
        payload = exact(primary_id)
        build_upper_product_projection(
            payload,
            expected_snapshot_id=primary_id,
            expected_kind="MEDIA_DEBRIEF",
        )
        projection = build_linked_debrief_projection(payload, expected_snapshot_id=primary_id)
        _fill_table(
            timeline,
            qt_widgets,
            projection.timeline,
            (
                ("session_time_us", "Master time (µs)"),
                ("layer", "Semantic layer"),
                ("ref", "Exact reference"),
            ),
        )
        _fill_table(
            media,
            qt_widgets,
            projection.media,
            (
                ("media_id", "Media ID"),
                ("media_type", "Type"),
                ("transcript_status", "Transcript"),
                ("artifact_sha256", "Artifact SHA-256"),
                ("uri", "Managed URI"),
            ),
        )
        _fill_table(
            bookmarks,
            qt_widgets,
            projection.bookmarks,
            (
                ("bookmark_id", "Bookmark"),
                ("session_time_us", "Master time (µs)"),
                ("label", "Label"),
            ),
        )
        _fill_table(
            playlists,
            qt_widgets,
            projection.playlists,
            (("playlist_id", "Playlist"), ("item_refs", "Exact item references")),
        )
        compare_text = "single snapshot"
        if comparison_id and comparison_id != primary_id:
            other = build_linked_debrief_projection(
                exact(comparison_id), expected_snapshot_id=comparison_id
            )
            compare_text = (
                f"compare={comparison_id} · mode={mode.currentText()} · "
                f"timeline {len(projection.timeline)}↔{len(other.timeline)}"
            )
        summary.setText(
            f"Exact={projection.snapshot_id} · release={projection.release_id} · "
            f"layers={','.join(projection.semantic_layers)} · {compare_text} · "
            "export remains gated"
        )

    refresh.clicked.connect(refresh_items)
    load.clicked.connect(load_exact)
    root._tpaa_refresh = refresh_items
    root._tpaa_load = load_exact
    return root


def _create_registry_gate_tab(qt_widgets: Any, parent: Any, transport: Any) -> Any:
    root = qt_widgets.QWidget(parent)
    layout = qt_widgets.QVBoxLayout(root)
    layout.addWidget(
        _heading(
            qt_widgets,
            root,
            "Model registry and external capability activation gates",
            "tpaaP11RegistryHeading",
        )
    )
    model_selector = qt_widgets.QComboBox(root)
    model_selector.setObjectName("tpaaP11ModelExact")
    buttons = qt_widgets.QWidget(root)
    buttons_layout = qt_widgets.QHBoxLayout(buttons)
    refresh = qt_widgets.QPushButton("Refresh model registry", buttons)
    refresh_gates = qt_widgets.QPushButton("Refresh runtime gates", buttons)
    refresh_gates.setObjectName("tpaaP11RefreshExternalGates")
    load = qt_widgets.QPushButton("Load exact model evidence", buttons)
    buttons_layout.addWidget(refresh)
    buttons_layout.addWidget(refresh_gates)
    buttons_layout.addWidget(load)
    model_status = _status(qt_widgets, root, "No exact model selected", "tpaaP11ModelStatus")
    layout.addWidget(model_selector)
    layout.addWidget(buttons)
    layout.addWidget(model_status)

    gate_table = qt_widgets.QTableWidget(root)
    gate_table.setObjectName("tpaaP11ExternalGates")
    configure_table(gate_table, qt_widgets)

    def render_gates(gates: Sequence[Any]) -> None:
        _fill_table(
            gate_table,
            qt_widgets,
            [
                {
                    "capability": gate.capability,
                    "state": gate.state,
                    "enabled": gate.action_enabled,
                    "reason": gate.reason_code,
                    "evidence": gate.acceptance_evidence_sha256,
                }
                for gate in gates
            ],
            (
                ("capability", "External capability"),
                ("state", "Gate state"),
                ("enabled", "Action enabled"),
                ("reason", "Required evidence"),
                ("evidence", "Acceptance SHA-256"),
            ),
        )

    render_gates(local_external_capability_gates())
    layout.addWidget(gate_table, 1)
    rollback = qt_widgets.QPushButton(
        "Model rollback disabled — monitoring endpoint and independent approval required",
        root,
    )
    rollback.setObjectName("tpaaP11ModelRollback")
    rollback.setEnabled(False)
    plugin = qt_widgets.QPushButton(
        "External plugin install disabled — trust root and sandbox not configured", root
    )
    plugin.setObjectName("tpaaP11ExternalPluginInstall")
    plugin.setEnabled(False)
    layout.addWidget(rollback)
    layout.addWidget(plugin)

    def refresh_models() -> None:
        try:
            items = product_items(transport, "P6_MODEL")
        except ProductDiscoveryError as exc:
            model_status.setText(f"Model discovery failed closed · {exc}")
            model_status.setProperty("tpaaState", "error")
            return
        prior = model_selector.currentData()
        model_selector.clear()
        for item in items:
            exact_id = str(item["exact_id"])
            metadata = cast(Mapping[str, object], item["metadata"])
            model_selector.addItem(f"{metadata.get('status', '—')} · {exact_id}", exact_id)
        if prior:
            index = model_selector.findData(prior)
            if index >= 0:
                model_selector.setCurrentIndex(index)
        model_status.setText(f"Immutable model history: {len(items)} revision(s)")

    def refresh_external_gates() -> None:
        payload = _success(
            transport.runtime_request_json("GET", "/runtime/external-capabilities"),
            operation="P11_EXTERNAL_GATES",
        )
        if payload.get("schema") != "TPAA_W7_EXTERNAL_CAPABILITY_AVAILABILITY_V1":
            raise W7PageError("P11_EXTERNAL_GATE_SCHEMA_INVALID")
        raw = payload.get("items")
        if not isinstance(raw, list):
            raise W7PageError("P11_EXTERNAL_GATE_ITEMS_INVALID")
        gates = [
            build_capability_gate(cast(Mapping[str, object], item))
            for item in raw
            if isinstance(item, Mapping)
        ]
        if len(gates) != 4:
            raise W7PageError("P11_EXTERNAL_GATE_SET_INVALID")
        render_gates(gates)
        model_status.setText(
            "Runtime gates verified · enabled="
            + str(sum(1 for gate in gates if gate.action_enabled))
            + "/4"
        )

    def load_model() -> None:
        model_id = str(model_selector.currentData() or "")
        if not model_id:
            model_status.setText("EMPTY · no model revision is visible for this role")
            return
        payload = _success(
            transport.m9_request_json("GET", f"/m9/models/{model_id}"),
            operation="P11_MODEL_EXACT",
        )
        model = build_model_registry_projection(payload, expected_model_id=model_id)
        model_status.setText(
            f"Exact={model.model_id} · status={model.status} · "
            f"validation={model.validation_state} · applicability={model.applicability_status} · "
            f"calibration={model.calibration_status} · plugin={model.plugin_identity} · "
            f"release={model.release_state} · artifact={model.artifact_hash}"
        )

    refresh.clicked.connect(refresh_models)
    refresh_gates.clicked.connect(refresh_external_gates)
    load.clicked.connect(load_model)
    root._tpaa_refresh = refresh_models
    root._tpaa_load = load_model
    return root


def create_p11_page(qt_widgets: Any, parent: Any, *, transport: Any) -> Any:
    """Create the independent P11 production workflow without eager network calls."""

    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaP11Workflow")
    layout = qt_widgets.QVBoxLayout(root)
    header = _status(
        qt_widgets,
        root,
        "P11 · Course / Unit / Joint-LVC & Planning · exact immutable revisions only",
        "tpaaP11Header",
    )
    header.setProperty("tpaaState", "success")
    layout.addWidget(header)
    tabs = qt_widgets.QTabWidget(root)
    tabs.setObjectName("tpaaP11Workspaces")
    tabs.addTab(
        _create_course_lvc_tab(qt_widgets, tabs, transport),
        "Course / Unit & Joint-LVC",
    )
    tabs.addTab(
        _create_planning_tab(qt_widgets, tabs, transport),
        "P6 Planning & Approval",
    )
    tabs.addTab(
        _create_media_tab(qt_widgets, tabs, transport),
        "Media / Transcript / Compare",
    )
    tabs.addTab(
        _create_registry_gate_tab(qt_widgets, tabs, transport),
        "Model Registry & Gates",
    )
    layout.addWidget(tabs, 1)
    root._tpaa_tabs = tabs
    return root


__all__ = ["W7PageError", "create_p11_page"]
