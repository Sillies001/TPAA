"""M2 Basic Flight foundation navigation over release-bound projections.

This presentation module consumes already-frozen Release projection data. It
does not import Metric/World/Storage packages, connect to a database, or
recompute business semantics.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

M2_FOUNDATION_CODES = frozenset(
    [
        *(f"P1-QA-{index:03d}" for index in range(1, 9)),
        *(f"P1-AIR-{index:03d}" for index in range(1, 4)),
        *(f"P1-SNS-{index:03d}" for index in range(1, 22)),
    ]
)
M2_NAMESPACE_COUNTS = {"QA": 8, "AIR": 3, "SNS": 21}
M2_OBSERVATION_LANE_COUNTS = {
    "AIRCRAFT_CAP_L1_OBSERVATION": 3,
    "SYSTEM_PERFORMANCE_OBSERVATION": 24,
    "QUALITY_EVIDENCE_ONLY": 5,
}
M2_OBSERVATION_LANE_PRESENTATION = {
    "AIRCRAFT_CAP_L1_OBSERVATION": (
        "CAPABILITY_OBSERVATION",
        "Aircraft capability observation",
        True,
    ),
    "SYSTEM_PERFORMANCE_OBSERVATION": (
        "SYSTEM_PERFORMANCE_OBSERVATION",
        "Mission-system performance observation",
        True,
    ),
    "QUALITY_EVIDENCE_ONLY": (
        "METRIC_INSTANCE_EVIDENCE_ONLY",
        "Quality evidence only",
        False,
    ),
}
M2_RESULT_STATUSES = frozenset(
    {"VALID", "N_A", "INSUFFICIENT_DATA", "INVALID", "REVIEW_REQUIRED"}
)
M2_PRESENTATION_STATE_STYLES = {
    "VALID": "QLabel { border: 1px solid; padding: 4px; }",
    "N_A": "QLabel { border: 2px dashed; padding: 4px; }",
    "INSUFFICIENT_DATA": "QLabel { border: 2px dotted; padding: 4px; }",
    "INVALID": "QLabel { border: 3px solid; padding: 4px; font-weight: bold; }",
    "REVIEW_REQUIRED": "QLabel { border: 3px double; padding: 4px; }",
    "WRONG_SENSOR_NOT_APPLICABLE": (
        "QLabel { border: 2px groove; padding: 4px; font-style: italic; }"
    ),
    "NOT_APPLICABLE": "QLabel { border: 2px groove; padding: 4px; }",
    "SYSTEM_ERROR": (
        "QLabel { border: 4px double; padding: 4px; font-weight: bold; }"
    ),
    "MIXED_RESULT_STATES": (
        "QLabel { border: 2px solid; padding: 4px; font-style: italic; }"
    ),
}


class M2FoundationNavigationError(RuntimeError):
    """Stable presentation-layer failure for invalid release projections."""


@dataclass(frozen=True)
class M2MetricPresentationState:
    metric_code: str
    kind: str
    label: str
    reason_codes: tuple[str, ...]
    result_statuses: tuple[str, ...]
    system_type: str | None
    system_error_code: str | None
    style_sheet: str
    release_bound: bool = True

    def projection(self) -> dict[str, object]:
        return {
            "metric_code": self.metric_code,
            "kind": self.kind,
            "label": self.label,
            "reason_codes": list(self.reason_codes),
            "result_statuses": list(self.result_statuses),
            "system_type": self.system_type,
            "system_error_code": self.system_error_code,
            "style_sheet": self.style_sheet,
            "release_bound": self.release_bound,
        }


@dataclass(frozen=True)
class M2FoundationNavigationItem:
    metric_code: str
    semantic_id: str
    semantic_version: int
    definition_hash: str
    subject_type: str
    value_kind: str
    observation_lane: str
    publication_route: str

    @property
    def namespace(self) -> str:
        return self.metric_code.split("-", 2)[1]

    @property
    def lane_presentation_label(self) -> str:
        contract = M2_OBSERVATION_LANE_PRESENTATION.get(self.observation_lane)
        if contract is None:
            raise M2FoundationNavigationError(
                f"M2_GUI_OBSERVATION_LANE_UNKNOWN:{self.observation_lane}"
            )
        return contract[1]

    @property
    def observation_record_expected(self) -> bool:
        contract = M2_OBSERVATION_LANE_PRESENTATION.get(self.observation_lane)
        if contract is None:
            raise M2FoundationNavigationError(
                f"M2_GUI_OBSERVATION_LANE_UNKNOWN:{self.observation_lane}"
            )
        return contract[2]

    def projection(self) -> dict[str, object]:
        return {
            "metric_code": self.metric_code,
            "semantic_id": self.semantic_id,
            "semantic_version": self.semantic_version,
            "definition_hash": self.definition_hash,
            "subject_type": self.subject_type,
            "value_kind": self.value_kind,
            "observation_lane": self.observation_lane,
            "publication_route": self.publication_route,
            "lane_presentation_label": self.lane_presentation_label,
            "observation_record_expected": self.observation_record_expected,
        }


@dataclass(frozen=True)
class M2FoundationNavigationModel:
    release_id: str
    manifest_hash: str
    items: tuple[M2FoundationNavigationItem, ...]

    @property
    def metric_codes(self) -> tuple[str, ...]:
        return tuple(item.metric_code for item in self.items)

    def by_namespace(self, namespace: str) -> tuple[M2FoundationNavigationItem, ...]:
        if namespace == "ALL":
            return self.items
        if namespace not in M2_NAMESPACE_COUNTS:
            raise M2FoundationNavigationError(
                f"M2_GUI_FOUNDATION_NAMESPACE_UNKNOWN:{namespace}"
            )
        return tuple(item for item in self.items if item.namespace == namespace)

    def by_observation_lane(
        self,
        observation_lane: str,
    ) -> tuple[M2FoundationNavigationItem, ...]:
        if observation_lane == "ALL":
            return self.items
        if observation_lane not in M2_OBSERVATION_LANE_COUNTS:
            raise M2FoundationNavigationError(
                f"M2_GUI_OBSERVATION_LANE_UNKNOWN:{observation_lane}"
            )
        return tuple(
            item
            for item in self.items
            if item.observation_lane == observation_lane
        )

    def filtered(
        self,
        *,
        namespace: str,
        observation_lane: str,
    ) -> tuple[M2FoundationNavigationItem, ...]:
        namespace_items = self.by_namespace(namespace)
        if observation_lane == "ALL":
            return namespace_items
        if observation_lane not in M2_OBSERVATION_LANE_COUNTS:
            raise M2FoundationNavigationError(
                f"M2_GUI_OBSERVATION_LANE_UNKNOWN:{observation_lane}"
            )
        return tuple(
            item
            for item in namespace_items
            if item.observation_lane == observation_lane
        )

    def item(self, metric_code: str) -> M2FoundationNavigationItem:
        for item in self.items:
            if item.metric_code == metric_code:
                return item
        raise M2FoundationNavigationError(
            f"M2_GUI_FOUNDATION_METRIC_UNKNOWN:{metric_code}"
        )


def _string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise M2FoundationNavigationError(
            f"M2_GUI_FOUNDATION_FIELD_INVALID:{field}"
        )
    return value


def _integer(value: object, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise M2FoundationNavigationError(
            f"M2_GUI_FOUNDATION_FIELD_INVALID:{field}"
        )
    return value


def _reason_codes(
    value: object,
    *,
    field: str,
    required: bool = False,
) -> tuple[str, ...]:
    if value is None:
        if required:
            raise M2FoundationNavigationError(
                f"M2_GUI_STATE_REASON_CODES_REQUIRED:{field}"
            )
        return ()
    if (
        not isinstance(value, list)
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise M2FoundationNavigationError(
            f"M2_GUI_STATE_REASON_CODES_INVALID:{field}"
        )
    result = tuple(value)
    if required and not result:
        raise M2FoundationNavigationError(
            f"M2_GUI_STATE_REASON_CODES_REQUIRED:{field}"
        )
    return result


def build_m2_metric_presentation_state(
    payload: Mapping[str, object],
) -> M2MetricPresentationState:
    """Preserve precomputed result/applicability/system-error states for the GUI."""

    metric_code = _string(payload.get("metric_code"), field="metric_code")
    raw_instances = payload.get("instances")
    system_error = payload.get("system_error_code")
    applicable = payload.get("applicable")

    if system_error is not None:
        error_code = _string(system_error, field="system_error_code")
        if applicable is not None or raw_instances not in (None, []):
            raise M2FoundationNavigationError(
                f"M2_GUI_STATE_SYSTEM_ERROR_AMBIGUOUS:{metric_code}"
            )
        kind = "SYSTEM_ERROR"
        return M2MetricPresentationState(
            metric_code=metric_code,
            kind=kind,
            label=f"System error · {error_code}",
            reason_codes=(),
            result_statuses=(),
            system_type=None,
            system_error_code=error_code,
            style_sheet=M2_PRESENTATION_STATE_STYLES[kind],
        )

    if applicable is False:
        if raw_instances != []:
            raise M2FoundationNavigationError(
                f"M2_GUI_STATE_NOT_APPLICABLE_INSTANCES_PRESENT:{metric_code}"
            )
        system_type = _string(payload.get("system_type"), field="system_type")
        reasons = _reason_codes(
            payload.get("applicability_reason_codes"),
            field=f"{metric_code}.applicability_reason_codes",
            required=True,
        )
        kind = (
            "WRONG_SENSOR_NOT_APPLICABLE"
            if "WRONG_SENSOR_TYPE" in reasons
            else "NOT_APPLICABLE"
        )
        label = (
            f"Wrong sensor · {system_type}"
            if kind == "WRONG_SENSOR_NOT_APPLICABLE"
            else f"Not applicable · {system_type}"
        )
        return M2MetricPresentationState(
            metric_code=metric_code,
            kind=kind,
            label=label,
            reason_codes=reasons,
            result_statuses=(),
            system_type=system_type,
            system_error_code=None,
            style_sheet=M2_PRESENTATION_STATE_STYLES[kind],
        )

    if applicable is not True:
        raise M2FoundationNavigationError(
            f"M2_GUI_STATE_APPLICABILITY_INVALID:{metric_code}"
        )
    if not isinstance(raw_instances, list) or not raw_instances:
        raise M2FoundationNavigationError(
            f"M2_GUI_STATE_INSTANCES_REQUIRED:{metric_code}"
        )

    statuses: list[str] = []
    reasons: set[str] = set()
    for index, raw in enumerate(raw_instances):
        if not isinstance(raw, Mapping):
            raise M2FoundationNavigationError(
                f"M2_GUI_STATE_INSTANCE_INVALID:{metric_code}:{index}"
            )
        status = raw.get("status")
        if not isinstance(status, str) or status not in M2_RESULT_STATUSES:
            raise M2FoundationNavigationError(
                f"M2_GUI_STATE_STATUS_INVALID:{metric_code}:{status!r}"
            )
        instance_reasons = _reason_codes(
            raw.get("reason_codes"),
            field=f"{metric_code}.instances[{index}].reason_codes",
            required=status in {"N_A", "INSUFFICIENT_DATA"},
        )
        statuses.append(status)
        reasons.update(instance_reasons)

    unique_statuses = tuple(sorted(set(statuses)))
    kind = (
        unique_statuses[0]
        if len(unique_statuses) == 1
        else "MIXED_RESULT_STATES"
    )
    label = (
        kind
        if kind != "MIXED_RESULT_STATES"
        else f"Mixed · {', '.join(unique_statuses)}"
    )
    return M2MetricPresentationState(
        metric_code=metric_code,
        kind=kind,
        label=label,
        reason_codes=tuple(sorted(reasons)),
        result_statuses=unique_statuses,
        system_type=None,
        system_error_code=None,
        style_sheet=M2_PRESENTATION_STATE_STYLES[kind],
    )


def build_m2_foundation_navigation_model(
    release_projection: Mapping[str, object],
) -> M2FoundationNavigationModel:
    """Validate one immutable Release projection for exact foundation navigation."""

    release_id = _string(release_projection.get("release_id"), field="release_id")
    manifest_hash = _string(
        release_projection.get("manifest_hash"),
        field="manifest_hash",
    )
    if len(manifest_hash) != 64:
        raise M2FoundationNavigationError(
            "M2_GUI_FOUNDATION_MANIFEST_HASH_INVALID"
        )
    raw_definitions = release_projection.get("definitions")
    if not isinstance(raw_definitions, list) or len(raw_definitions) != 32:
        raise M2FoundationNavigationError(
            "M2_GUI_FOUNDATION_MEMBERSHIP_INVALID"
        )

    items: list[M2FoundationNavigationItem] = []
    for raw in raw_definitions:
        if not isinstance(raw, dict):
            raise M2FoundationNavigationError(
                "M2_GUI_FOUNDATION_DEFINITION_INVALID"
            )
        definition = raw
        item = M2FoundationNavigationItem(
            metric_code=_string(definition.get("metric_code"), field="metric_code"),
            semantic_id=_string(definition.get("semantic_id"), field="semantic_id"),
            semantic_version=_integer(
                definition.get("semantic_version"),
                field="semantic_version",
            ),
            definition_hash=_string(
                definition.get("definition_hash"),
                field="definition_hash",
            ),
            subject_type=_string(
                definition.get("subject_type"),
                field="subject_type",
            ),
            value_kind=_string(definition.get("value_kind"), field="value_kind"),
            observation_lane=_string(
                definition.get("observation_lane"),
                field="observation_lane",
            ),
            publication_route=_string(
                definition.get("publication_route"),
                field="publication_route",
            ),
        )
        if len(item.definition_hash) != 64:
            raise M2FoundationNavigationError(
                f"M2_GUI_FOUNDATION_DEFINITION_HASH_INVALID:{item.metric_code}"
            )
        lane_contract = M2_OBSERVATION_LANE_PRESENTATION.get(
            item.observation_lane
        )
        if lane_contract is None:
            raise M2FoundationNavigationError(
                f"M2_GUI_OBSERVATION_LANE_UNKNOWN:{item.observation_lane}"
            )
        if item.publication_route != lane_contract[0]:
            raise M2FoundationNavigationError(
                "M2_GUI_OBSERVATION_ROUTE_LANE_MISMATCH:"
                f"{item.metric_code}:{item.publication_route}:"
                f"{item.observation_lane}"
            )
        items.append(item)

    codes = tuple(item.metric_code for item in items)
    if len(set(codes)) != 32 or set(codes) != M2_FOUNDATION_CODES:
        raise M2FoundationNavigationError(
            "M2_GUI_FOUNDATION_MEMBERSHIP_INVALID"
        )
    model = M2FoundationNavigationModel(
        release_id=release_id,
        manifest_hash=manifest_hash,
        items=tuple(items),
    )
    for namespace, expected_count in M2_NAMESPACE_COUNTS.items():
        if len(model.by_namespace(namespace)) != expected_count:
            raise M2FoundationNavigationError(
                f"M2_GUI_FOUNDATION_NAMESPACE_COUNT_INVALID:{namespace}"
            )
    for observation_lane, expected_count in M2_OBSERVATION_LANE_COUNTS.items():
        if len(model.by_observation_lane(observation_lane)) != expected_count:
            raise M2FoundationNavigationError(
                "M2_GUI_OBSERVATION_LANE_COUNT_INVALID:"
                f"{observation_lane}"
            )
    return model


def create_m2_foundation_workspace(
    qt_core: Any,
    qt_widgets: Any,
    parent: Any,
    *,
    release_projection: Mapping[str, object],
    presentation_states: Mapping[str, Mapping[str, object]] | None = None,
) -> Any:
    """Create the projection-only Basic Flight foundation navigator."""

    model = build_m2_foundation_navigation_model(release_projection)
    state_by_code: dict[str, M2MetricPresentationState] = {}
    if presentation_states is not None:
        unknown_codes = set(presentation_states) - set(model.metric_codes)
        if unknown_codes:
            raise M2FoundationNavigationError(
                "M2_GUI_STATE_METRIC_UNKNOWN:"
                f"{','.join(sorted(unknown_codes))}"
            )
        for metric_code, payload in presentation_states.items():
            state = build_m2_metric_presentation_state(payload)
            if state.metric_code != metric_code:
                raise M2FoundationNavigationError(
                    "M2_GUI_STATE_METRIC_KEY_MISMATCH:"
                    f"{metric_code}:{state.metric_code}"
                )
            state_by_code[metric_code] = state

    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaM2FoundationWorkspace")
    layout = qt_widgets.QVBoxLayout(root)

    header = qt_widgets.QLabel(
        f"Basic Flight Foundation · Release {model.release_id}",
        root,
    )
    header.setObjectName("tpaaM2FoundationHeader")
    count = qt_widgets.QLabel("Foundation metrics: 32", root)
    count.setObjectName("tpaaM2FoundationCount")
    layout.addWidget(header)
    layout.addWidget(count)

    filters = qt_widgets.QWidget(root)
    filters.setObjectName("tpaaM2FoundationFilters")
    filter_layout = qt_widgets.QHBoxLayout(filters)

    namespace = qt_widgets.QComboBox(filters)
    namespace.setObjectName("tpaaM2FoundationNamespace")
    namespace.addItems(["ALL", "QA", "AIR", "SNS"])
    filter_layout.addWidget(qt_widgets.QLabel("Metric family", filters))
    filter_layout.addWidget(namespace)

    lane = qt_widgets.QComboBox(filters)
    lane.setObjectName("tpaaM2ObservationLane")
    lane.addItems(["ALL", *M2_OBSERVATION_LANE_COUNTS])
    filter_layout.addWidget(qt_widgets.QLabel("Observation lane", filters))
    filter_layout.addWidget(lane)
    layout.addWidget(filters)

    lane_summary = qt_widgets.QLabel(
        "Observation lane: ALL · visible=32",
        root,
    )
    lane_summary.setObjectName("tpaaM2ObservationLaneSummary")
    layout.addWidget(lane_summary)

    navigator = qt_widgets.QListWidget(root)
    navigator.setObjectName("tpaaM2FoundationNavigator")
    detail = qt_widgets.QPlainTextEdit(root)
    detail.setObjectName("tpaaM2FoundationDetail")
    detail.setReadOnly(True)
    status = qt_widgets.QLabel("Navigation: READY", root)
    status.setObjectName("tpaaM2FoundationNavigationStatus")
    state_badge = qt_widgets.QLabel("State: UNAVAILABLE", root)
    state_badge.setObjectName("tpaaM2MetricState")
    state_reasons = qt_widgets.QLabel("Reasons: unavailable", root)
    state_reasons.setObjectName("tpaaM2MetricStateReasons")
    layout.addWidget(navigator)
    layout.addWidget(detail)
    layout.addWidget(status)
    layout.addWidget(state_badge)
    layout.addWidget(state_reasons)

    visible_items: list[M2FoundationNavigationItem] = []

    def render_detail(row: int) -> None:
        if row < 0 or row >= len(visible_items):
            detail.clear()
            return
        item = visible_items[row]
        presentation_state = state_by_code.get(item.metric_code)
        state_projection = (
            None
            if presentation_state is None
            else presentation_state.projection()
        )
        detail.setPlainText(
            json.dumps(
                {
                    "release_id": model.release_id,
                    "manifest_hash": model.manifest_hash,
                    "definition": item.projection(),
                    "observation_presentation": {
                        "lane": item.observation_lane,
                        "lane_label": item.lane_presentation_label,
                        "publication_route": item.publication_route,
                        "observation_record_expected": (
                            item.observation_record_expected
                        ),
                        "release_bound": True,
                    },
                    "metric_state": state_projection,
                },
                indent=2,
                sort_keys=True,
            )
        )
        if presentation_state is None:
            state_badge.setText("State: UNAVAILABLE")
            state_badge.setStyleSheet("")
            state_reasons.setText("Reasons: unavailable")
        else:
            state_badge.setText(
                f"State: {presentation_state.kind} · "
                f"{presentation_state.label}"
            )
            state_badge.setStyleSheet(presentation_state.style_sheet)
            reasons = (
                ", ".join(presentation_state.reason_codes)
                if presentation_state.reason_codes
                else "none"
            )
            state_reasons.setText(f"Reasons: {reasons}")
        status.setText(f"Navigation: SELECTED {item.metric_code}")

    def render_filters(_value: str = "") -> None:
        selected_namespace = str(namespace.currentText())
        selected_lane = str(lane.currentText())
        visible_items.clear()
        visible_items.extend(
            model.filtered(
                namespace=selected_namespace,
                observation_lane=selected_lane,
            )
        )
        navigator.clear()
        for item in visible_items:
            navigator.addItem(item.metric_code)
        lane_summary.setText(
            f"Observation lane: {selected_lane} · visible={len(visible_items)}"
        )
        if visible_items:
            navigator.setCurrentRow(0)
            render_detail(0)
        else:
            detail.clear()
            status.setText("Navigation: EMPTY")
            state_badge.setText("State: UNAVAILABLE")
            state_badge.setStyleSheet("")
            state_reasons.setText("Reasons: unavailable")

    namespace.currentTextChanged.connect(render_filters)
    lane.currentTextChanged.connect(render_filters)
    navigator.currentRowChanged.connect(render_detail)
    render_filters()
    root._tpaa_m2_foundation_model = model
    root._tpaa_m2_foundation_namespace = namespace
    root._tpaa_m2_observation_lane = lane
    root._tpaa_m2_observation_lane_summary = lane_summary
    root._tpaa_m2_foundation_navigator = navigator
    root._tpaa_m2_foundation_detail = detail
    root._tpaa_m2_metric_state = state_badge
    root._tpaa_m2_metric_state_reasons = state_reasons
    root._tpaa_m2_state_by_code = state_by_code
    return root
