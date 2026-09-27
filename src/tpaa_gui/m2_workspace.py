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


class M2FoundationNavigationError(RuntimeError):
    """Stable presentation-layer failure for invalid release projections."""


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
) -> Any:
    """Create the projection-only Basic Flight foundation navigator."""

    model = build_m2_foundation_navigation_model(release_projection)

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
    layout.addWidget(navigator)
    layout.addWidget(detail)
    layout.addWidget(status)

    visible_items: list[M2FoundationNavigationItem] = []

    def render_detail(row: int) -> None:
        if row < 0 or row >= len(visible_items):
            detail.clear()
            return
        item = visible_items[row]
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
                },
                indent=2,
                sort_keys=True,
            )
        )
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
    return root
