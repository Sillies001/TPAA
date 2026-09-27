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

    namespace = qt_widgets.QComboBox(root)
    namespace.setObjectName("tpaaM2FoundationNamespace")
    namespace.addItems(["ALL", "QA", "AIR", "SNS"])
    layout.addWidget(namespace)

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
                },
                indent=2,
                sort_keys=True,
            )
        )
        status.setText(f"Navigation: SELECTED {item.metric_code}")

    def render_namespace(_value: str = "") -> None:
        selected = str(namespace.currentText())
        visible_items.clear()
        visible_items.extend(model.by_namespace(selected))
        navigator.clear()
        for item in visible_items:
            navigator.addItem(item.metric_code)
        if visible_items:
            navigator.setCurrentRow(0)
            render_detail(0)
        else:
            detail.clear()

    namespace.currentTextChanged.connect(render_namespace)
    navigator.currentRowChanged.connect(render_detail)
    render_namespace()
    root._tpaa_m2_foundation_model = model
    root._tpaa_m2_foundation_namespace = namespace
    root._tpaa_m2_foundation_navigator = navigator
    root._tpaa_m2_foundation_detail = detail
    return root
