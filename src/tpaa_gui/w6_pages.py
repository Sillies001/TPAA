"""W6 production Desktop pages for P04-P10 product workflows."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast

from .components import configure_table
from .discovery import ProductDiscoveryError, product_items
from .m4_workspace import build_m4_trend_workspace_model
from .m6_workspace import (
    build_m6_comparison_workspace_model,
    build_m6_diagnostics_workspace_model,
)
from .m7_workspace import build_m7_three_layer_workspace_model
from .w6_projection import (
    attribution_display_rows,
    build_individual_assessment,
    build_team_assessment,
    trend_segments,
    validate_model_profile,
    validate_subject_lane,
)


class W6PageError(RuntimeError):
    """Stable W6 GUI orchestration failure."""


def _display(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return format(value, ".4g")
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _success(
    result: tuple[int, Mapping[str, object]], *, operation: str
) -> dict[str, object]:
    status, payload = result
    if status != 200:
        raise W6PageError(f"{operation}:HTTP_{status}:{payload.get('error')!r}")
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


def _banner(qt_widgets: Any, parent: Any, text: str, name: str) -> Any:
    label = qt_widgets.QLabel(text, parent)
    label.setObjectName(name)
    label.setWordWrap(True)
    label.setProperty("tpaaState", "unknown")
    return label


def _discovery_combo(
    qt_widgets: Any, parent: Any, *, object_name: str
) -> tuple[Any, Any, Any]:
    row = qt_widgets.QWidget(parent)
    layout = qt_widgets.QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    combo = qt_widgets.QComboBox(row)
    combo.setObjectName(object_name)
    refresh = qt_widgets.QPushButton("Refresh immutable history", row)
    refresh.setObjectName(f"{object_name}Refresh")
    layout.addWidget(combo, 1)
    layout.addWidget(refresh)
    return row, combo, refresh


def _assessment_page(
    qt_widgets: Any,
    parent: Any,
    *,
    transport: Any,
    kind: str,
    individual: bool,
) -> Any:
    slot = "P04" if individual else "P05"
    root = qt_widgets.QWidget(parent)
    root.setObjectName(f"tpaa{slot}Workflow")
    layout = qt_widgets.QVBoxLayout(root)
    row, selector, refresh = _discovery_combo(
        qt_widgets, root, object_name=f"tpaa{slot}ExactRevision"
    )
    load = qt_widgets.QPushButton("Load exact assessment", root)
    load.setObjectName(f"tpaa{slot}LoadExact")
    semantic = _banner(
        qt_widgets,
        root,
        (
            "INDIVIDUAL only · automatic assessment, instructor annotation, and final "
            "approval remain separate products. Team results are never copied here."
            if individual
            else "TEAM / PACKAGE / MISSION only · composition is immutable. Individual "
            "members remain evidence references, never derived personal scores."
        ),
        f"tpaa{slot}SemanticGuard",
    )
    identity = _banner(qt_widgets, root, "Assessment: no exact revision selected", f"tpaa{slot}Identity")
    lifecycle = _banner(qt_widgets, root, "Lifecycle: unavailable", f"tpaa{slot}Lifecycle")
    evidence = qt_widgets.QTableWidget(root)
    evidence.setObjectName(f"tpaa{slot}Evidence")
    configure_table(evidence, qt_widgets)
    evidence.setMinimumHeight(150)

    action_box = qt_widgets.QGroupBox("Governed reviewer transition", root)
    action_layout = qt_widgets.QHBoxLayout(action_box)
    target_state = qt_widgets.QComboBox(action_box)
    target_state.setObjectName(f"tpaa{slot}TargetState")
    target_state.addItems(("IN_REVIEW", "APPROVED", "REJECTED"))
    reason = qt_widgets.QLineEdit(action_box)
    reason.setObjectName(f"tpaa{slot}TransitionReason")
    reason.setPlaceholderText("Required review/approval/rejection reason")
    apply = qt_widgets.QPushButton("Create immutable revision", action_box)
    apply.setObjectName(f"tpaa{slot}ApplyTransition")
    action_layout.addWidget(target_state)
    action_layout.addWidget(reason, 1)
    action_layout.addWidget(apply)

    layout.addWidget(row)
    layout.addWidget(load)
    layout.addWidget(semantic)
    layout.addWidget(identity)
    layout.addWidget(lifecycle)
    layout.addWidget(evidence, 1)
    layout.addWidget(action_box)

    items: list[dict[str, object]] = []
    active_payload: dict[str, object] | None = None

    def refresh_items() -> None:
        nonlocal items
        try:
            items = product_items(transport, kind)
        except ProductDiscoveryError as exc:
            selector.clear()
            lifecycle.setText(f"History discovery failed closed · {exc}")
            lifecycle.setProperty("tpaaState", "failure")
            return
        prior = selector.currentData()
        selector.clear()
        for item in items:
            metadata = cast(Mapping[str, object], item["metadata"])
            exact_id = str(item["exact_id"])
            selector.addItem(
                f"{metadata.get('status', '—')} · {metadata.get('created_at', '—')} · {exact_id}",
                exact_id,
            )
        if prior:
            index = selector.findData(prior)
            if index >= 0:
                selector.setCurrentIndex(index)
        lifecycle.setText(f"Immutable history: {len(items)} revision(s); no current/latest alias")

    def load_exact() -> None:
        nonlocal active_payload
        exact_id = str(selector.currentData() or "")
        if not exact_id:
            lifecycle.setText("EMPTY · no assessment revision is published for this role")
            return
        path = (
            f"/m8/p4/assessments/{exact_id}"
            if individual
            else f"/m8/p5/assessments/{exact_id}"
        )
        active_payload = _success(
            transport.m8_request_json("GET", path), operation=f"{slot}_EXACT_READ"
        )
        model = (
            build_individual_assessment(active_payload, expected_id=exact_id)
            if individual
            else build_team_assessment(active_payload, expected_id=exact_id)
        )
        identity.setText(
            f"{model.layer} · subject/composition={model.subject_key} · scope={model.scope_id} · "
            f"validity={model.validity_status} · claim={model.claim_level} · as-of={model.as_of_utc}"
        )
        lifecycle.setText(
            f"Exact revision={model.product_id} · approval={model.approval_state} · "
            f"supersedes={model.supersedes_id or 'ROOT'}"
        )
        rows = [{"kind": "EVIDENCE", "reference": ref} for ref in model.evidence_refs]
        rows.extend(
            {"kind": "PARTICIPANT (not personal score)", "reference": ref}
            for ref in model.participant_subject_keys
        )
        _fill_table(evidence, qt_widgets, rows, (("kind", "Kind"), ("reference", "Immutable reference")))

    def transition() -> None:
        exact_id = str(selector.currentData() or "")
        why = reason.text().strip()
        if not exact_id or not why:
            lifecycle.setText("REVIEW REQUIRED · exact revision and reason are mandatory")
            return
        path = (
            f"/m8/p4/assessments/{exact_id}/approval"
            if individual
            else f"/m8/p5/assessments/{exact_id}/approval"
        )
        payload = _success(
            transport.m8_request_json(
                "POST",
                path,
                body={
                    "request_id": str(uuid.uuid4()),
                    "target_state": target_state.currentText(),
                    "reason": why,
                    "created_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                },
            ),
            operation=f"{slot}_TRANSITION",
        )
        new_id = payload.get("actor_assessment_id") or payload.get("mission_assessment_id")
        lifecycle.setText(
            f"Immutable transition accepted · state={payload.get('approval_state')} · revision={new_id}"
        )
        refresh_items()

    refresh.clicked.connect(refresh_items)
    load.clicked.connect(load_exact)
    apply.clicked.connect(transition)
    root._tpaa_refresh = refresh_items
    root._tpaa_load = load_exact
    return root


def create_p04_page(qt_widgets: Any, parent: Any, *, transport: Any) -> Any:
    return _assessment_page(
        qt_widgets, parent, transport=transport, kind="P4_ASSESSMENT", individual=True
    )


def create_p05_page(qt_widgets: Any, parent: Any, *, transport: Any) -> Any:
    return _assessment_page(
        qt_widgets, parent, transport=transport, kind="P5_ASSESSMENT", individual=False
    )


def create_p06_page(qt_widgets: Any, parent: Any, *, transport: Any) -> Any:
    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaP06Workflow")
    layout = qt_widgets.QVBoxLayout(root)
    twin_row, twin, refresh = _discovery_combo(qt_widgets, root, object_name="tpaaP06TwinRevision")
    estimate = qt_widgets.QComboBox(root)
    estimate.setObjectName("tpaaP06Estimate")
    load = qt_widgets.QPushButton("Load exact Twin revision and estimate", root)
    load.setObjectName("tpaaP06LoadExact")
    header = _banner(qt_widgets, root, "Twin: unavailable", "tpaaP06TwinHeader")
    layers = qt_widgets.QTableWidget(root)
    layers.setObjectName("tpaaP06LayerTable")
    configure_table(layers, qt_widgets)
    trace = _banner(
        qt_widgets,
        root,
        "Evidence path: Twin → Estimate → Attribution → Observation → Episode/Stage → Evidence",
        "tpaaP06EvidenceTrace",
    )
    guard = _banner(
        qt_widgets,
        root,
        "Reference-condition estimate only; never fed back as same-Episode observed truth.",
        "tpaaP06TruthGuard",
    )
    layout.addWidget(twin_row)
    layout.addWidget(estimate)
    layout.addWidget(load)
    layout.addWidget(header)
    layout.addWidget(guard)
    layout.addWidget(layers, 1)
    layout.addWidget(trace)
    estimates: list[dict[str, object]] = []

    def update_estimates(*_args: object) -> None:
        estimate.clear()
        twin_id = str(twin.currentData() or "")
        for item in estimates:
            metadata = cast(Mapping[str, object], item["metadata"])
            if metadata.get("twin_revision_id") == twin_id:
                estimate.addItem(str(item["exact_id"]), str(item["exact_id"]))

    def refresh_items() -> None:
        nonlocal estimates
        try:
            twins = product_items(transport, "P3_TWIN")
            estimates = product_items(transport, "P3_ESTIMATE")
        except ProductDiscoveryError as exc:
            header.setText(f"Twin discovery failed closed · {exc}")
            return
        twin.clear()
        for item in twins:
            meta = cast(Mapping[str, object], item["metadata"])
            exact_id = str(item["exact_id"])
            twin.addItem(
                f"{meta.get('aircraft_id', '—')} · r{meta.get('revision_no', '—')} · "
                f"{meta.get('status', '—')} · {exact_id}", exact_id
            )
        update_estimates()
        header.setText(f"Immutable history: {len(twins)} Twin revisions / {len(estimates)} estimates")

    def load_exact() -> None:
        twin_id = str(twin.currentData() or "")
        estimate_id = str(estimate.currentData() or "")
        if not twin_id or not estimate_id:
            header.setText("EMPTY · no published exact Twin/Estimate pair")
            return
        payload = _success(
            transport.m7_request_json(
                "GET", f"/m7/p3/twins/{twin_id}/estimates/{estimate_id}/workspace"
            ), operation="P06_EXACT_TWIN"
        )
        model = build_m7_three_layer_workspace_model(
            payload, expected_twin_revision_id=twin_id, expected_estimate_id=estimate_id
        )
        header.setText(
            f"Twin={model.p3.twin_revision_id} · estimate={model.p3.estimate_id} · "
            f"revision={model.p3.revision_no} · as-of={model.p3.as_of_time} · "
            f"validity={model.p3.validity_domain_status} · value={_display(model.p3.value)} {model.p3.unit}"
        )
        _fill_table(
            layers,
            qt_widgets,
            (
                {"layer": "Observed (L1)", "release": model.observed.release_id, "meaning": "historical fact"},
                {"layer": "Adjusted (L2)", "release": model.adjusted.release_id, "meaning": "association-only"},
                {"layer": "Reference estimate (L3)", "release": model.p3.twin_revision_id, "meaning": model.p3.claim_level},
            ),
            (("layer", "Semantic layer"), ("release", "Exact revision/release"), ("meaning", "Meaning")),
        )

    twin.currentIndexChanged.connect(update_estimates)
    refresh.clicked.connect(refresh_items)
    load.clicked.connect(load_exact)
    root._tpaa_refresh = refresh_items
    root._tpaa_load = load_exact
    return root


def create_p07_page(qt_widgets: Any, parent: Any, *, transport: Any) -> Any:
    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaP07Workflow")
    layout = qt_widgets.QVBoxLayout(root)
    row, selector, refresh = _discovery_combo(qt_widgets, root, object_name="tpaaP07ModelProfile")
    status = _banner(qt_widgets, root, "Model profile: unavailable", "tpaaP07Status")
    cohort = qt_widgets.QTableWidget(root)
    cohort.setObjectName("tpaaP07Cohort")
    configure_table(cohort, qt_widgets)
    notice = _banner(
        qt_widgets,
        root,
        "Only a server-published model/block/configuration cohort is admissible. The GUI will not aggregate aircraft Twins. OUTLIER means review, never automatic fault.",
        "tpaaP07AggregationGuard",
    )
    layout.addWidget(row)
    layout.addWidget(status)
    layout.addWidget(notice)
    layout.addWidget(cohort, 1)
    profiles: list[dict[str, object]] = []

    def refresh_items() -> None:
        nonlocal profiles
        try:
            profiles = product_items(transport, "P3_MODEL_PROFILE")
        except ProductDiscoveryError:
            profiles = []
            selector.clear()
            status.setText(
                "UNAVAILABLE · no authoritative P3 model-profile aggregate API is published; frontend aggregation is forbidden"
            )
            status.setProperty("tpaaState", "review")
            _fill_table(cohort, qt_widgets, (), (("profile", "Profile"),))
            return
        selector.clear()
        rows: list[dict[str, object]] = []
        for item in profiles:
            exact_id = str(item["exact_id"])
            metadata = {
                **cast(dict[str, object], item["metadata"]),
                "profile_id": exact_id,
            }
            validate_model_profile(metadata, expected_id=exact_id)
            selector.addItem(exact_id, exact_id)
            rows.append(metadata)
        status.setText(f"Published immutable model profiles: {len(rows)}")
        _fill_table(
            cohort,
            qt_widgets,
            rows,
            (
                ("aircraft_model_id", "Aircraft model"),
                ("configuration_key", "Block / configuration"),
                ("aircraft_count", "Aircraft count"),
                ("independent_episode_count", "Independent episodes"),
                ("profile_version", "Profile version"),
                ("as_of_utc", "As-of"),
                ("status", "Lifecycle"),
            ),
        )

    refresh.clicked.connect(refresh_items)
    root._tpaa_refresh = refresh_items
    return root


def create_p08_page(qt_widgets: Any, parent: Any, *, transport: Any) -> Any:
    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaP08Workflow")
    layout = qt_widgets.QVBoxLayout(root)
    row, selector, refresh = _discovery_combo(qt_widgets, root, object_name="tpaaP08Estimate")
    load = qt_widgets.QPushButton("Load comparison + diagnostics + evidence bindings", root)
    load.setObjectName("tpaaP08LoadExact")
    summary = _banner(qt_widgets, root, "P2: unavailable", "tpaaP08Summary")
    guard = _banner(
        qt_widgets,
        root,
        "MODEL-CONDITIONED ASSOCIATION ONLY · not causal attribution · not percentage unless the published scale explicitly says so.",
        "tpaaP08CausalityGuard",
    )
    table = qt_widgets.QTableWidget(root)
    # Preserve the qualified automation identifier while moving it to canonical P08.
    table.setObjectName("tpaaM6FactorEffects")
    table.setProperty("tpaaCanonicalObjectName", "tpaaP08AssociationEffects")
    configure_table(table, qt_widgets)
    table.setColumnCount(3)
    table.setHorizontalHeaderLabels(
        ("Factor", "Association contribution", "Reason / identifiability")
    )
    table.setColumnWidth(1, 240)
    table.setMinimumHeight(200)
    layout.addWidget(row)
    layout.addWidget(load)
    layout.addWidget(summary)
    layout.addWidget(guard)
    layout.addWidget(table, 1)
    items: list[dict[str, object]] = []

    def refresh_items() -> None:
        nonlocal items
        try:
            items = product_items(transport, "P2_ESTIMATE")
        except ProductDiscoveryError as exc:
            summary.setText(f"P2 discovery failed closed · {exc}")
            return
        selector.clear()
        for item in items:
            meta = cast(Mapping[str, object], item["metadata"])
            selector.addItem(
                f"{meta.get('capability_type', '—')} · {meta.get('status', '—')} · {item['exact_id']}",
                str(item["exact_id"]),
            )
        summary.setText(f"Immutable P2 estimate history: {len(items)}")

    def load_exact() -> None:
        index = selector.currentIndex()
        if index < 0:
            summary.setText("EMPTY · no P2 estimate published")
            return
        item = items[index]
        estimate_id = str(item["exact_id"])
        meta = cast(Mapping[str, object], item["metadata"])
        release_id = str(meta.get("p2_release_id", ""))
        comparison = _success(
            transport.m6_request_json(
                "GET", f"/m6/p2/releases/{release_id}/estimates/{estimate_id}/comparison"
            ), operation="P08_COMPARISON"
        )
        diagnostics = _success(
            transport.m6_request_json(
                "GET", f"/m6/p2/releases/{release_id}/estimates/{estimate_id}/diagnostics"
            ), operation="P08_DIAGNOSTICS"
        )
        model = build_m6_comparison_workspace_model(
            comparison, expected_p2_release_id=release_id, expected_estimate_id=estimate_id
        )
        detail = build_m6_diagnostics_workspace_model(
            diagnostics, expected_p2_release_id=release_id, expected_estimate_id=estimate_id
        )
        rows = attribution_display_rows(
            status=model.adjusted.status,
            factor_effects=model.adjusted.factor_effects,
            reason_codes=model.adjusted.reason_codes,
        )
        _fill_table(
            table,
            qt_widgets,
            rows,
            (("factor", "Factor"), ("association_effect", "Association effect (original scale)"), ("reason", "Reason / identifiability")),
        )
        summary.setText(
            f"Observed={model.observed.observed_value} {model.observed.unit} · Adjusted={_display(model.adjusted.adjusted_value)} · "
            f"Residual={_display(model.adjusted.residual)} · status={model.adjusted.status} · claim={model.adjusted.claim_level} · "
            f"P1={model.observed.source_release_id} · P2={model.adjusted.p2_release_id} · as-of={detail.as_of_utc}"
        )

    refresh.clicked.connect(refresh_items)
    load.clicked.connect(load_exact)
    root._tpaa_refresh = refresh_items
    root._tpaa_load = load_exact
    return root


def create_p09_page(qt_widgets: Any, parent: Any, *, transport: Any) -> Any:
    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaP09Workflow")
    layout = qt_widgets.QVBoxLayout(root)
    lane = qt_widgets.QComboBox(root)
    lane.setObjectName("tpaaP09SubjectLane")
    lane.addItems(("AIRCRAFT", "MISSION_SYSTEM_INSTANCE"))
    row, selector, refresh = _discovery_combo(qt_widgets, root, object_name="tpaaP09TrendRelease")
    load = qt_widgets.QPushButton("Load exact observed trend", root)
    load.setObjectName("tpaaP09LoadExact")
    status = _banner(qt_widgets, root, "Trend: unavailable", "tpaaP09Status")
    points = qt_widgets.QTableWidget(root)
    points.setObjectName("tpaaP09TrendPoints")
    configure_table(points, qt_widgets)
    breaks = qt_widgets.QTableWidget(root)
    breaks.setObjectName("tpaaP09ConfigurationBreaks")
    configure_table(breaks, qt_widgets)
    layout.addWidget(lane)
    layout.addWidget(row)
    layout.addWidget(load)
    layout.addWidget(status)
    layout.addWidget(points, 2)
    layout.addWidget(breaks, 1)

    def refresh_items() -> None:
        try:
            items = product_items(transport, "M4_RELEASE")
        except ProductDiscoveryError as exc:
            status.setText(f"Trend discovery failed closed · {exc}")
            return
        selector.clear()
        for item in items:
            meta = cast(Mapping[str, object], item["metadata"])
            selector.addItem(
                f"{meta.get('scope_key', '—')} · {meta.get('status', '—')} · {item['exact_id']}",
                str(item["exact_id"]),
            )
        status.setText(f"Immutable longitudinal releases: {len(items)}")

    def load_exact() -> None:
        release_id = str(selector.currentData() or "")
        if not release_id:
            status.setText("EMPTY · no observed trend release")
            return
        payload = _success(
            transport.m4_request_json("GET", f"/m4/longitudinal/releases/{release_id}/trend"),
            operation="P09_TREND",
        )
        model = build_m4_trend_workspace_model(payload, expected_release_id=release_id)
        selected_lane = validate_subject_lane(lane.currentText())
        if model.subject_type != selected_lane:
            status.setText(
                f"EMPTY FOR LANE · release subject={model.subject_type}; selected={selected_lane}; lanes are never merged"
            )
            _fill_table(points, qt_widgets, (), (("value", "Value"),))
            return
        point_rows = [item.projection() for item in model.points]
        _fill_table(
            points,
            qt_widgets,
            point_rows,
            (("session_order", "Session order"), ("value", "Observed value"), ("sample_status", "Status"), ("configuration_key", "Subject-specific configuration"), ("release_id", "Input Session Release")),
        )
        segment_rows = [
            {"start": item.start_order, "end": item.end_order, "configuration": item.configuration_key, "reason": item.reason}
            for item in trend_segments(point_rows)
        ]
        _fill_table(
            breaks,
            qt_widgets,
            segment_rows,
            (("start", "Start"), ("end", "End"), ("configuration", "Configuration / software segment"), ("reason", "Break reason")),
        )
        status.setText(
            f"{model.subject_type}:{model.subject_id} · {model.metric_code} · status={model.status}/{model.trend_status} · "
            f"profile={model.trend_profile_id}@{model.trend_profile_version} · exact release={model.release_id}"
        )

    refresh.clicked.connect(refresh_items)
    load.clicked.connect(load_exact)
    root._tpaa_refresh = refresh_items
    root._tpaa_load = load_exact
    return root


def create_p10_page(qt_widgets: Any, parent: Any, *, transport: Any) -> Any:
    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaP10Workflow")
    layout = qt_widgets.QVBoxLayout(root)
    lane = qt_widgets.QComboBox(root)
    lane.setObjectName("tpaaP10SubjectLane")
    lane.addItems(("HUMAN", "TEAM"))
    refresh = qt_widgets.QPushButton("Refresh exact assessment history", root)
    refresh.setObjectName("tpaaP10RefreshHistory")
    status = _banner(
        qt_widgets,
        root,
        "Longitudinal: select HUMAN or TEAM; the two lanes are never aggregated.",
        "tpaaP10Status",
    )
    history = qt_widgets.QTableWidget(root)
    history.setObjectName("tpaaP10History")
    configure_table(history, qt_widgets)
    notice = _banner(
        qt_widgets,
        root,
        "Exact immutable revisions only. Comparable scenarios/configurations must be published by the server; no GUI score trend or team-to-individual allocation is calculated.",
        "tpaaP10IsolationGuard",
    )
    layout.addWidget(lane)
    layout.addWidget(refresh)
    layout.addWidget(status)
    layout.addWidget(notice)
    layout.addWidget(history, 1)

    def refresh_history() -> None:
        selected = validate_subject_lane(lane.currentText())
        kind = "P4_ASSESSMENT" if selected == "HUMAN" else "P5_ASSESSMENT"
        try:
            items = product_items(transport, kind)
        except ProductDiscoveryError as exc:
            status.setText(f"Longitudinal discovery failed closed · {exc}")
            return
        rows = []
        for item in items:
            meta = cast(Mapping[str, object], item["metadata"])
            rows.append(
                {
                    "lane": selected,
                    "subject": meta.get("actor_id") if selected == "HUMAN" else meta.get("team_id"),
                    "revision": item["exact_id"],
                    "status": meta.get("status"),
                    "created_at": meta.get("created_at"),
                    "scope": meta.get("session_id"),
                }
            )
        _fill_table(
            history,
            qt_widgets,
            rows,
            (("lane", "Lane"), ("subject", "Subject"), ("revision", "Exact revision"), ("status", "Lifecycle"), ("created_at", "Knowledge/publish time"), ("scope", "Session scope")),
        )
        status.setText(
            f"{selected} exact history: {len(rows)} revision(s) · TEAM results are never presented as HUMAN scores"
        )

    refresh.clicked.connect(refresh_history)
    lane.currentTextChanged.connect(lambda _value: refresh_history())
    root._tpaa_refresh = refresh_history
    return root


__all__ = [
    "W6PageError",
    "create_p04_page",
    "create_p05_page",
    "create_p06_page",
    "create_p07_page",
    "create_p08_page",
    "create_p09_page",
    "create_p10_page",
]
