"""M4 release-bound longitudinal and Evidence-first Debrief presentation adapter.

This module consumes API DTOs only. It never imports persistence, Application,
Metric, World, or longitudinal business engines and performs no trend recomputation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast


class M4DesktopTransport(Protocol):
    """Narrow GUI-side M4 HTTP transport contract."""

    def m4_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        ...


class M4WorkspacePresentationError(RuntimeError):
    """Fail-closed presentation-contract error."""


@dataclass(frozen=True)
class M4TrendPointPresentation:
    point_order: int
    sample_id: str
    source_release_id: str
    session_id: str
    session_order: str
    value: float | None
    sample_status: str
    configuration_key: str

    def projection(self) -> dict[str, object]:
        return {
            "point_order": self.point_order,
            "sample_id": self.sample_id,
            "release_id": self.source_release_id,
            "session_id": self.session_id,
            "session_order": self.session_order,
            "value": self.value,
            "sample_status": self.sample_status,
            "configuration_key": self.configuration_key,
        }


@dataclass(frozen=True)
class M4TrendWorkspaceModel:
    release_id: str
    longitudinal_scope_id: str
    longitudinal_scope_key: str
    subject_type: str
    subject_id: str
    metric_code: str
    metric_semantic_id: str
    metric_semantic_version: int
    comparison_key_hash: str
    trend_profile_id: str
    trend_profile_version: str
    trend_profile_hash: str
    input_hash: str
    status: str
    reason_codes: tuple[str, ...]
    trend_status: str
    current_value: float | None
    ewma_value: float | None
    slope: float | None
    slope_unit: str | None
    stability_mad: float | None
    points: tuple[M4TrendPointPresentation, ...]

    def projection(self) -> dict[str, object]:
        return {
            "release_id": self.release_id,
            "longitudinal_scope_id": self.longitudinal_scope_id,
            "longitudinal_scope_key": self.longitudinal_scope_key,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "metric_code": self.metric_code,
            "metric_semantic_id": self.metric_semantic_id,
            "metric_semantic_version": self.metric_semantic_version,
            "comparison_key_hash": self.comparison_key_hash,
            "trend_profile_id": self.trend_profile_id,
            "trend_profile_version": self.trend_profile_version,
            "trend_profile_hash": self.trend_profile_hash,
            "input_hash": self.input_hash,
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "trend_status": self.trend_status,
            "current_value": self.current_value,
            "ewma_value": self.ewma_value,
            "slope": self.slope,
            "slope_unit": self.slope_unit,
            "stability_mad": self.stability_mad,
            "points": [item.projection() for item in self.points],
        }


@dataclass(frozen=True)
class M4DebriefTimelinePresentation:
    item_id: str
    item_type: str
    session_id: str
    evidence_set_id: str | None
    source_release_id: str
    knowledge_time_mode: str
    start_session_time_us: str | None
    end_session_time_us: str | None


@dataclass(frozen=True)
class M4AnnotationPresentation:
    annotation_id: str
    author_id: str
    annotation_type: str
    body_text: str
    visibility: str
    status: str
    revision_no: int
    supersedes_annotation_id: str | None
    evidence_set_id: str | None
    reason: str
    audit_id: str
    request_id: str
    created_at: str


@dataclass(frozen=True)
class M4DebriefWorkspaceModel:
    base_release_id: str
    view_mode: str
    retrospective_release_id: str | None
    manifest_hash: str
    timeline: tuple[M4DebriefTimelinePresentation, ...]
    annotations: tuple[M4AnnotationPresentation, ...]

    def projection(self) -> dict[str, object]:
        return {
            "base_release_id": self.base_release_id,
            "view_mode": self.view_mode,
            "retrospective_release_id": self.retrospective_release_id,
            "manifest_hash": self.manifest_hash,
            "timeline": [
                {
                    "item_id": item.item_id,
                    "item_type": item.item_type,
                    "session_id": item.session_id,
                    "evidence_set_id": item.evidence_set_id,
                    "source_release_id": item.source_release_id,
                    "knowledge_time_mode": item.knowledge_time_mode,
                    "start_session_time_us": item.start_session_time_us,
                    "end_session_time_us": item.end_session_time_us,
                }
                for item in self.timeline
            ],
            "annotations": [
                {
                    "annotation_id": item.annotation_id,
                    "author_id": item.author_id,
                    "annotation_type": item.annotation_type,
                    "body_text": item.body_text,
                    "visibility": item.visibility,
                    "status": item.status,
                    "revision_no": item.revision_no,
                    "supersedes_annotation_id": item.supersedes_annotation_id,
                    "evidence_set_id": item.evidence_set_id,
                    "reason": item.reason,
                    "audit_id": item.audit_id,
                    "request_id": item.request_id,
                    "created_at": item.created_at,
                }
                for item in self.annotations
            ],
        }


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise M4WorkspacePresentationError(
            f"M4_GUI_MAPPING_INVALID:{field}"
        )
    return cast(Mapping[str, object], value)


def _list(value: object, *, field: str) -> list[object]:
    if not isinstance(value, list):
        raise M4WorkspacePresentationError(
            f"M4_GUI_LIST_INVALID:{field}"
        )
    return cast(list[object], value)


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise M4WorkspacePresentationError(
            f"M4_GUI_FIELD_INVALID:{field}"
        )
    return value


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field=field)


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise M4WorkspacePresentationError(
            f"M4_GUI_INTEGER_INVALID:{field}"
        )
    return value


def _number(value: object, *, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise M4WorkspacePresentationError(
            f"M4_GUI_NUMBER_INVALID:{field}"
        )
    return float(value)


def _strings(value: object, *, field: str) -> tuple[str, ...]:
    items = _list(value, field=field)
    if not all(isinstance(item, str) and item for item in items):
        raise M4WorkspacePresentationError(
            f"M4_GUI_STRING_LIST_INVALID:{field}"
        )
    return tuple(cast(list[str], items))


def build_m4_trend_workspace_model(
    projection: Mapping[str, object],
    *,
    expected_release_id: str,
) -> M4TrendWorkspaceModel:
    """Validate/copy API-projected trend values without business recomputation."""

    release = _mapping(projection.get("release"), field="release")
    scope = _mapping(projection.get("scope"), field="scope")
    series = _mapping(projection.get("series"), field="series")
    raw_points = _list(projection.get("points"), field="points")
    release_id = _text(release.get("release_id"), field="release.release_id")
    if release_id != expected_release_id:
        raise M4WorkspacePresentationError(
            "M4_GUI_RELEASE_MISMATCH"
        )
    if _text(series.get("release_id"), field="series.release_id") != release_id:
        raise M4WorkspacePresentationError(
            "M4_GUI_SERIES_RELEASE_MISMATCH"
        )
    scope_id = _text(
        scope.get("longitudinal_scope_id"),
        field="scope.longitudinal_scope_id",
    )
    if (
        _text(
            series.get("longitudinal_scope_id"),
            field="series.longitudinal_scope_id",
        )
        != scope_id
    ):
        raise M4WorkspacePresentationError(
            "M4_GUI_SCOPE_MISMATCH"
        )
    trend_id = _text(series.get("trend_id"), field="series.trend_id")
    points: list[M4TrendPointPresentation] = []
    for index, raw in enumerate(raw_points):
        point = _mapping(raw, field=f"points[{index}]")
        if _text(point.get("trend_id"), field="point.trend_id") != trend_id:
            raise M4WorkspacePresentationError(
                "M4_GUI_POINT_TREND_MISMATCH"
            )
        points.append(
            M4TrendPointPresentation(
                point_order=_integer(
                    point.get("point_order"),
                    field="point.point_order",
                ),
                sample_id=_text(
                    point.get("sample_id"),
                    field="point.sample_id",
                ),
                source_release_id=_text(
                    point.get("release_id"),
                    field="point.release_id",
                ),
                session_id=_text(
                    point.get("session_id"),
                    field="point.session_id",
                ),
                session_order=str(
                    _integer(
                        point.get("session_order"),
                        field="point.session_order",
                    )
                ),
                value=_number(point.get("value"), field="point.value"),
                sample_status=_text(
                    point.get("sample_status"),
                    field="point.sample_status",
                ),
                configuration_key=_text(
                    point.get("configuration_key"),
                    field="point.configuration_key",
                ),
            )
        )
    if _integer(
        series.get("sample_count_total"),
        field="series.sample_count_total",
    ) != len(points):
        raise M4WorkspacePresentationError(
            "M4_GUI_POINT_COUNT_MISMATCH"
        )
    return M4TrendWorkspaceModel(
        release_id=release_id,
        longitudinal_scope_id=scope_id,
        longitudinal_scope_key=_text(
            scope.get("longitudinal_scope_key"),
            field="scope.longitudinal_scope_key",
        ),
        subject_type=_text(
            series.get("subject_type"),
            field="series.subject_type",
        ),
        subject_id=_text(
            series.get("subject_id"),
            field="series.subject_id",
        ),
        metric_code=_text(
            series.get("metric_code"),
            field="series.metric_code",
        ),
        metric_semantic_id=_text(
            series.get("metric_semantic_id"),
            field="series.metric_semantic_id",
        ),
        metric_semantic_version=_integer(
            series.get("metric_semantic_version"),
            field="series.metric_semantic_version",
        ),
        comparison_key_hash=_text(
            series.get("comparison_key_hash"),
            field="series.comparison_key_hash",
        ),
        trend_profile_id=_text(
            series.get("trend_profile_id"),
            field="series.trend_profile_id",
        ),
        trend_profile_version=_text(
            series.get("trend_profile_version"),
            field="series.trend_profile_version",
        ),
        trend_profile_hash=_text(
            series.get("trend_profile_hash"),
            field="series.trend_profile_hash",
        ),
        input_hash=_text(
            series.get("input_hash"),
            field="series.input_hash",
        ),
        status=_text(series.get("status"), field="series.status"),
        reason_codes=_strings(
            series.get("reason_codes"),
            field="series.reason_codes",
        ),
        trend_status=_text(
            series.get("trend_status"),
            field="series.trend_status",
        ),
        current_value=_number(
            series.get("current_value"),
            field="series.current_value",
        ),
        ewma_value=_number(
            series.get("ewma_value"),
            field="series.ewma_value",
        ),
        slope=_number(series.get("slope"), field="series.slope"),
        slope_unit=_optional_text(
            series.get("slope_unit"),
            field="series.slope_unit",
        ),
        stability_mad=_number(
            series.get("stability_mad"),
            field="series.stability_mad",
        ),
        points=tuple(points),
    )


def build_m4_debrief_workspace_model(
    projection: Mapping[str, object],
    *,
    expected_base_release_id: str,
) -> M4DebriefWorkspaceModel:
    """Validate/copy exact-release Debrief DTOs and revision identities."""

    query = _mapping(projection.get("query"), field="query")
    base = _mapping(projection.get("base_release"), field="base_release")
    base_release_id = _text(
        query.get("base_release_id"),
        field="query.base_release_id",
    )
    if (
        base_release_id != expected_base_release_id
        or _text(
            base.get("release_id"),
            field="base_release.release_id",
        )
        != base_release_id
    ):
        raise M4WorkspacePresentationError(
            "M4_GUI_DEBRIEF_RELEASE_MISMATCH"
        )
    view_mode = _text(
        query.get("view_mode"),
        field="query.view_mode",
    )
    retrospective_release_id = _optional_text(
        query.get("retrospective_release_id"),
        field="query.retrospective_release_id",
    )

    timeline: list[M4DebriefTimelinePresentation] = []
    for index, raw in enumerate(
        _list(projection.get("timeline"), field="timeline")
    ):
        item = _mapping(raw, field=f"timeline[{index}]")
        if (
            _text(
                item.get("base_release_id"),
                field="timeline.base_release_id",
            )
            != base_release_id
        ):
            raise M4WorkspacePresentationError(
                "M4_GUI_TIMELINE_RELEASE_MISMATCH"
            )
        mode = _text(
            item.get("knowledge_time_mode"),
            field="timeline.knowledge_time_mode",
        )
        if mode != view_mode:
            raise M4WorkspacePresentationError(
                "M4_GUI_TIMELINE_MODE_MISMATCH"
            )
        timeline.append(
            M4DebriefTimelinePresentation(
                item_id=_text(
                    item.get("item_id"),
                    field="timeline.item_id",
                ),
                item_type=_text(
                    item.get("item_type"),
                    field="timeline.item_type",
                ),
                session_id=_text(
                    item.get("session_id"),
                    field="timeline.session_id",
                ),
                evidence_set_id=_optional_text(
                    item.get("evidence_set_id"),
                    field="timeline.evidence_set_id",
                ),
                source_release_id=_text(
                    item.get("source_release_id"),
                    field="timeline.source_release_id",
                ),
                knowledge_time_mode=mode,
                start_session_time_us=_optional_text(
                    item.get("start_session_time_us"),
                    field="timeline.start_session_time_us",
                ),
                end_session_time_us=_optional_text(
                    item.get("end_session_time_us"),
                    field="timeline.end_session_time_us",
                ),
            )
        )

    annotations: list[M4AnnotationPresentation] = []
    for index, raw in enumerate(
        _list(projection.get("annotations"), field="annotations")
    ):
        item = _mapping(raw, field=f"annotations[{index}]")
        if (
            _text(
                item.get("base_release_id"),
                field="annotation.base_release_id",
            )
            != base_release_id
        ):
            raise M4WorkspacePresentationError(
                "M4_GUI_ANNOTATION_RELEASE_MISMATCH"
            )
        annotations.append(
            M4AnnotationPresentation(
                annotation_id=_text(
                    item.get("annotation_id"),
                    field="annotation.annotation_id",
                ),
                author_id=_text(
                    item.get("author_id"),
                    field="annotation.author_id",
                ),
                annotation_type=_text(
                    item.get("annotation_type"),
                    field="annotation.annotation_type",
                ),
                body_text=_text(
                    item.get("body_text"),
                    field="annotation.body_text",
                ),
                visibility=_text(
                    item.get("visibility"),
                    field="annotation.visibility",
                ),
                status=_text(
                    item.get("status"),
                    field="annotation.status",
                ),
                revision_no=_integer(
                    item.get("revision_no"),
                    field="annotation.revision_no",
                ),
                supersedes_annotation_id=_optional_text(
                    item.get("supersedes_annotation_id"),
                    field="annotation.supersedes_annotation_id",
                ),
                evidence_set_id=_optional_text(
                    item.get("evidence_set_id"),
                    field="annotation.evidence_set_id",
                ),
                reason=_text(
                    item.get("reason"),
                    field="annotation.reason",
                ),
                audit_id=_text(
                    item.get("audit_id"),
                    field="annotation.audit_id",
                ),
                request_id=_text(
                    item.get("request_id"),
                    field="annotation.request_id",
                ),
                created_at=_text(
                    item.get("created_at"),
                    field="annotation.created_at",
                ),
            )
        )
    return M4DebriefWorkspaceModel(
        base_release_id=base_release_id,
        view_mode=view_mode,
        retrospective_release_id=retrospective_release_id,
        manifest_hash=_text(
            base.get("manifest_hash"),
            field="base_release.manifest_hash",
        ),
        timeline=tuple(timeline),
        annotations=tuple(annotations),
    )


def build_annotation_command_payload(
    *,
    request_id: str,
    operation: str,
    base_release_id: str,
    target_annotation_id: str | None,
    session_id: str,
    author_id: str,
    annotation_type: str,
    body_text: str,
    visibility: str,
    reason: str,
    evidence_set_id: str | None,
) -> dict[str, object]:
    """Build transport payload only; Application owns all revision semantics."""

    return {
        "request_id": request_id,
        "operation": operation,
        "base_release_id": base_release_id,
        "target_annotation_id": target_annotation_id,
        "session_id": session_id,
        "episode_id": None,
        "stage_id": None,
        "author_id": author_id,
        "annotation_type": annotation_type,
        "start_session_time_us": None,
        "end_session_time_us": None,
        "body_text": body_text,
        "visibility": visibility,
        "reason": reason,
        "evidence_set_id": evidence_set_id,
    }


def _success(
    status: int,
    payload: Mapping[str, object],
) -> Mapping[str, object]:
    if status != 200:
        raise M4WorkspacePresentationError(
            f"M4_GUI_HTTP_ERROR:{status}:{payload!r}"
        )
    return payload


def create_m4_workspace(
    *,
    qt_widgets: Any,
    transport: M4DesktopTransport,
    parent: Any = None,
) -> Any:
    """Create a transport-only Qt workspace for governed M4 DTOs."""

    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaM4Workspace")
    layout = qt_widgets.QVBoxLayout(root)

    release_input = qt_widgets.QLineEdit(root)
    release_input.setObjectName("tpaaM4ReleaseInput")
    trend_button = qt_widgets.QPushButton("Load longitudinal trend", root)
    trend_button.setObjectName("tpaaM4TrendLoad")
    layout.addWidget(release_input)
    layout.addWidget(trend_button)

    trend_identity = qt_widgets.QLabel("Trend: unavailable", root)
    trend_identity.setObjectName("tpaaM4TrendIdentity")
    trend_profile = qt_widgets.QLabel("Profile: unavailable", root)
    trend_profile.setObjectName("tpaaM4TrendProfile")
    trend_status = qt_widgets.QLabel("Status: unavailable", root)
    trend_status.setObjectName("tpaaM4TrendStatus")
    layout.addWidget(trend_identity)
    layout.addWidget(trend_profile)
    layout.addWidget(trend_status)

    points_table = qt_widgets.QTableWidget(root)
    points_table.setObjectName("tpaaM4TrendPoints")
    points_table.setColumnCount(6)
    points_table.setHorizontalHeaderLabels(
        [
            "Order",
            "Session order",
            "Value",
            "Status",
            "Session Release",
            "Session",
        ]
    )
    points_table.setEditTriggers(
        qt_widgets.QAbstractItemView.EditTrigger.NoEditTriggers
    )
    layout.addWidget(points_table)

    view_mode = qt_widgets.QComboBox(root)
    view_mode.setObjectName("tpaaM4DebriefViewMode")
    view_mode.addItems(["ORIGINAL_AS_KNOWN", "RETROSPECTIVE"])
    retrospective_input = qt_widgets.QLineEdit(root)
    retrospective_input.setObjectName("tpaaM4RetrospectiveReleaseInput")
    debrief_button = qt_widgets.QPushButton("Load Debrief", root)
    debrief_button.setObjectName("tpaaM4DebriefLoad")
    layout.addWidget(view_mode)
    layout.addWidget(retrospective_input)
    layout.addWidget(debrief_button)

    debrief_identity = qt_widgets.QLabel("Debrief: unavailable", root)
    debrief_identity.setObjectName("tpaaM4DebriefIdentity")
    layout.addWidget(debrief_identity)

    timeline_table = qt_widgets.QTableWidget(root)
    timeline_table.setObjectName("tpaaM4DebriefTimeline")
    timeline_table.setColumnCount(5)
    timeline_table.setHorizontalHeaderLabels(
        ["Type", "Item", "Session", "Evidence", "Source Release"]
    )
    timeline_table.setEditTriggers(
        qt_widgets.QAbstractItemView.EditTrigger.NoEditTriggers
    )
    layout.addWidget(timeline_table)

    annotation_operation = qt_widgets.QComboBox(root)
    annotation_operation.setObjectName("tpaaM4AnnotationOperation")
    annotation_operation.addItems(["CREATE", "SUPERSEDE", "DELETE"])
    annotation_target = qt_widgets.QLineEdit(root)
    annotation_target.setObjectName("tpaaM4AnnotationTarget")
    annotation_author = qt_widgets.QLineEdit(root)
    annotation_author.setObjectName("tpaaM4AnnotationAuthor")
    annotation_type = qt_widgets.QComboBox(root)
    annotation_type.setObjectName("tpaaM4AnnotationType")
    annotation_type.addItems(
        [
            "BOOKMARK",
            "COMMENT",
            "EVIDENCE_NOTE",
            "DEBRIEF_POINT",
            "CORRECTION_NOTE",
        ]
    )
    annotation_body = qt_widgets.QLineEdit(root)
    annotation_body.setObjectName("tpaaM4AnnotationBody")
    annotation_reason = qt_widgets.QLineEdit(root)
    annotation_reason.setObjectName("tpaaM4AnnotationReason")
    annotation_button = qt_widgets.QPushButton("Apply annotation revision", root)
    annotation_button.setObjectName("tpaaM4AnnotationApply")
    for widget in (
        annotation_operation,
        annotation_target,
        annotation_author,
        annotation_type,
        annotation_body,
        annotation_reason,
        annotation_button,
    ):
        layout.addWidget(widget)

    annotation_status = qt_widgets.QLabel("Annotation: IDLE", root)
    annotation_status.setObjectName("tpaaM4AnnotationStatus")
    layout.addWidget(annotation_status)

    active_trend: M4TrendWorkspaceModel | None = None
    known_annotation_ids: list[str] = []

    def load_trend() -> None:
        nonlocal active_trend
        release_id = release_input.text().strip()
        status, payload = transport.m4_request_json(
            "GET",
            f"/m4/longitudinal/releases/{release_id}/trend",
        )
        projection = _success(status, payload)
        model = build_m4_trend_workspace_model(
            projection,
            expected_release_id=release_id,
        )
        active_trend = model
        trend_identity.setText(
            f"{model.metric_code} · {model.subject_type}:{model.subject_id} · "
            f"Release {model.release_id}"
        )
        trend_profile.setText(
            f"Profile {model.trend_profile_id}@{model.trend_profile_version} · "
            f"{model.trend_profile_hash} · comparison={model.comparison_key_hash}"
        )
        trend_status.setText(
            f"{model.status} · {model.trend_status} · reasons="
            f"{','.join(model.reason_codes) or '-'}"
        )
        points_table.setRowCount(len(model.points))
        for row, point in enumerate(model.points):
            values = (
                point.point_order,
                point.session_order,
                point.value,
                point.sample_status,
                point.source_release_id,
                point.session_id,
            )
            for column, value in enumerate(values):
                points_table.setItem(
                    row,
                    column,
                    qt_widgets.QTableWidgetItem(
                        "" if value is None else str(value)
                    ),
                )

    def load_debrief() -> None:
        release_id = release_input.text().strip()
        mode = view_mode.currentText()
        query = (
            f"?view_mode={mode}&annotation_view=NONE"
        )
        retrospective = retrospective_input.text().strip()
        if mode == "RETROSPECTIVE":
            query += f"&retrospective_release_id={retrospective}"
        status, payload = transport.m4_request_json(
            "GET",
            f"/m4/debrief/releases/{release_id}{query}",
        )
        projection = _success(status, payload)
        model = build_m4_debrief_workspace_model(
            projection,
            expected_base_release_id=release_id,
        )
        debrief_identity.setText(
            f"{model.view_mode} · base={model.base_release_id} · "
            f"retrospective={model.retrospective_release_id or '-'} · "
            f"manifest={model.manifest_hash}"
        )
        timeline_table.setRowCount(len(model.timeline))
        for row, item in enumerate(model.timeline):
            values = (
                item.item_type,
                item.item_id,
                item.session_id,
                item.evidence_set_id,
                item.source_release_id,
            )
            for column, value in enumerate(values):
                timeline_table.setItem(
                    row,
                    column,
                    qt_widgets.QTableWidgetItem(
                        "" if value is None else str(value)
                    ),
                )

    def apply_annotation() -> None:
        if active_trend is None or not active_trend.points:
            raise M4WorkspacePresentationError(
                "M4_GUI_ANNOTATION_REQUIRES_LOADED_RELEASE"
            )
        request_id = (
            f"gui-{active_trend.release_id}-"
            f"{len(known_annotation_ids) + 1}"
        )
        operation = annotation_operation.currentText()
        target = annotation_target.text().strip() or None
        payload = build_annotation_command_payload(
            request_id=request_id,
            operation=operation,
            base_release_id=active_trend.release_id,
            target_annotation_id=target,
            session_id=active_trend.points[-1].session_id,
            author_id=annotation_author.text().strip(),
            annotation_type=annotation_type.currentText(),
            body_text=annotation_body.text(),
            visibility="PROJECT",
            reason=annotation_reason.text(),
            evidence_set_id=None,
        )
        status, response = transport.m4_request_json(
            "POST",
            "/m4/debrief/annotations",
            body=payload,
        )
        result = _success(status, response)
        annotation_id = _text(
            result.get("annotation_id"),
            field="annotation.annotation_id",
        )
        known_annotation_ids.append(annotation_id)
        annotation_target.setText(annotation_id)
        annotation_status.setText(
            f"Annotation: {result.get('status')} · "
            f"revision={result.get('revision_no')} · id={annotation_id}"
        )

    trend_button.clicked.connect(load_trend)
    debrief_button.clicked.connect(load_debrief)
    annotation_button.clicked.connect(apply_annotation)
    return root
