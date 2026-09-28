"""M3 four-training Desktop navigation over release-bound API projections.

This module is a presentation adapter only. It consumes the already-qualified
M3 workspace projection and never imports persistence, World, Metric, or
Application implementation layers.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast

M3_GUI_TRAINING_KEYS = ("BASIC", "WVR", "BVR", "STRIKE")
M3_GUI_METRIC_COUNT = 116
M3_GUI_TRAINING_PRESENTATION = {
    "BASIC": "Basic Flight",
    "WVR": "WVR Engagement",
    "BVR": "BVR Kill Chain",
    "STRIKE": "Strike Mission",
}

M3_GUI_PRODUCT_FAMILY_CODES = (
    "P1-AIR-*",
    "P1-TRK-*",
    "P1-ID-*",
    "P1-PSV-*",
    "P1-ESM-*",
    "P1-DL-*",
    "P1-FUS-*",
)
M3_GUI_FAMILY_PRESENTATION: dict[str, tuple[str, str]] = {
    "P1-AIR-*": (
        "Aircraft performance",
        "aircraft observed flight/energy/control/handling/persistence performance",
    ),
    "P1-TRK-*": (
        "Local track product",
        "local track-processing product layer; applicability is by product capability, "
        "not by one physical sensor type",
    ),
    "P1-ID-*": (
        "Association / identification",
        "association/identity processing layer; applicability is by product capability",
    ),
    "P1-PSV-*": (
        "Passive sensor",
        "passive electro-optical/infrared sensing layer",
    ),
    "P1-ESM-*": (
        "RWR / ESM",
        "emitter sensing / warning / ESM layer",
    ),
    "P1-DL-*": (
        "Datalink",
        "datalink transport and remote-track delivery layer",
    ),
    "P1-FUS-*": (
        "Sensor fusion",
        "multi-source fused-track product layer",
    ),
}


class M3DesktopTransport(Protocol):
    """Narrow GUI-side M3 transport contract."""

    def m3_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        ...


class M3WorkspaceNavigationError(RuntimeError):
    """Fail-closed presentation-layer error for an invalid workspace projection."""


@dataclass(frozen=True)
class M3TrainingNavigation:
    training_key: str
    label: str
    episode_type: str
    stage_profile_id: str
    episode_id: str
    stage_id: str
    stage_code: str

    def projection(self) -> dict[str, object]:
        return {
            "training_key": self.training_key,
            "label": self.label,
            "episode_type": self.episode_type,
            "stage_profile_id": self.stage_profile_id,
            "episode_id": self.episode_id,
            "stage_id": self.stage_id,
            "stage_code": self.stage_code,
        }


@dataclass(frozen=True)
class M3FamilyNavigation:
    family_code: str
    metric_count: int
    applicable_count: int
    not_applicable_count: int

    def projection(self) -> dict[str, object]:
        return {
            "family_code": self.family_code,
            "metric_count": self.metric_count,
            "applicable_count": self.applicable_count,
            "not_applicable_count": self.not_applicable_count,
        }


@dataclass(frozen=True)
class M3MetricApplicabilityNavigation:
    metric_code: str
    family_code: str
    applicable: bool
    reason_codes: tuple[str, ...]
    system_type: str | None
    instance_count: int

    def projection(self) -> dict[str, object]:
        return {
            "metric_code": self.metric_code,
            "family_code": self.family_code,
            "applicable": self.applicable,
            "reason_codes": list(self.reason_codes),
            "system_type": self.system_type,
            "instance_count": self.instance_count,
        }


@dataclass(frozen=True)
class M3WorkspaceNavigationModel:
    release_id: str
    manifest_hash: str
    provenance_hash: str
    training: M3TrainingNavigation
    families: tuple[M3FamilyNavigation, ...]
    metric_codes: tuple[str, ...]
    metric_applicability: tuple[M3MetricApplicabilityNavigation, ...]

    def projection(self) -> dict[str, object]:
        return {
            "release_id": self.release_id,
            "manifest_hash": self.manifest_hash,
            "provenance_hash": self.provenance_hash,
            "training": self.training.projection(),
            "families": [family.projection() for family in self.families],
            "metric_count": len(self.metric_codes),
        }


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise M3WorkspaceNavigationError(f"M3_GUI_FIELD_INVALID:{field}")
    return value


def _count(value: object, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise M3WorkspaceNavigationError(f"M3_GUI_COUNT_INVALID:{field}")
    return value


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise M3WorkspaceNavigationError(f"M3_GUI_MAPPING_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _sequence(value: object, *, field: str) -> list[object]:
    if not isinstance(value, list):
        raise M3WorkspaceNavigationError(f"M3_GUI_LIST_INVALID:{field}")
    return value


def _string_tuple(
    value: object,
    *,
    field: str,
    required: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise M3WorkspaceNavigationError(f"M3_GUI_STRING_LIST_INVALID:{field}")
    result = tuple(cast(list[str], value))
    if required and not result:
        raise M3WorkspaceNavigationError(f"M3_GUI_STRING_LIST_REQUIRED:{field}")
    return result


def _require_hash(value: object, *, field: str) -> str:
    result = _text(value, field=field)
    if len(result) != 64:
        raise M3WorkspaceNavigationError(f"M3_GUI_HASH_INVALID:{field}")
    return result


def _training(
    payload: Mapping[str, object],
    *,
    expected_training_key: str | None,
) -> M3TrainingNavigation:
    training_key = _text(payload.get("training_key"), field="training.training_key")
    if training_key not in M3_GUI_TRAINING_KEYS:
        raise M3WorkspaceNavigationError(
            f"M3_GUI_TRAINING_KEY_INVALID:{training_key}"
        )
    if expected_training_key is not None and training_key != expected_training_key:
        raise M3WorkspaceNavigationError(
            "M3_GUI_TRAINING_KEY_MISMATCH:"
            f"{expected_training_key}:{training_key}"
        )

    return M3TrainingNavigation(
        training_key=training_key,
        label=M3_GUI_TRAINING_PRESENTATION[training_key],
        episode_type=_text(
            payload.get("episode_type"),
            field="training.episode_type",
        ),
        stage_profile_id=_text(
            payload.get("stage_profile_id"),
            field="training.stage_profile_id",
        ),
        episode_id=_text(payload.get("episode_id"), field="training.episode_id"),
        stage_id=_text(payload.get("stage_id"), field="training.stage_id"),
        stage_code=_text(payload.get("stage_code"), field="training.stage_code"),
    )


def build_m3_workspace_navigation_model(
    workspace_projection: Mapping[str, object],
    *,
    expected_training_key: str | None = None,
    expected_release_id: str | None = None,
) -> M3WorkspaceNavigationModel:
    """Validate one exact Release-bound workspace projection for navigation."""

    release_id = _text(workspace_projection.get("release_id"), field="release_id")
    if expected_release_id is not None and release_id != expected_release_id:
        raise M3WorkspaceNavigationError(
            f"M3_GUI_RELEASE_ID_MISMATCH:{expected_release_id}:{release_id}"
        )
    manifest_hash = _require_hash(
        workspace_projection.get("manifest_hash"),
        field="manifest_hash",
    )
    training = _training(
        _mapping(workspace_projection.get("training"), field="training"),
        expected_training_key=expected_training_key,
    )

    raw_metrics = _sequence(workspace_projection.get("metrics"), field="metrics")
    if len(raw_metrics) != M3_GUI_METRIC_COUNT:
        raise M3WorkspaceNavigationError("M3_GUI_METRIC_MEMBERSHIP_INVALID")
    metric_codes: list[str] = []
    metric_applicability: list[M3MetricApplicabilityNavigation] = []
    for index, raw_metric in enumerate(raw_metrics):
        metric = _mapping(raw_metric, field=f"metrics[{index}]")
        metric_release_id = _text(
            metric.get("release_id"),
            field=f"metrics[{index}].release_id",
        )
        if metric_release_id != release_id:
            raise M3WorkspaceNavigationError(
                f"M3_GUI_METRIC_RELEASE_DRIFT:{index}"
            )
        metric_code = _text(
            metric.get("metric_code"),
            field=f"metrics[{index}].metric_code",
        )
        family_code = _text(
            metric.get("family_code"),
            field=f"metrics[{index}].family_code",
        )
        applicability = _mapping(
            metric.get("applicability"),
            field=f"metrics[{index}].applicability",
        )
        applicable = applicability.get("applicable")
        if not isinstance(applicable, bool):
            raise M3WorkspaceNavigationError(
                f"M3_GUI_APPLICABILITY_INVALID:{metric_code}"
            )
        reason_codes = _string_tuple(
            applicability.get("reason_codes"),
            field=f"metrics[{index}].applicability.reason_codes",
            required=not applicable,
        )
        system_type_value = applicability.get("system_type")
        system_type = (
            None
            if system_type_value is None
            else _text(
                system_type_value,
                field=f"metrics[{index}].applicability.system_type",
            )
        )
        instances = _sequence(
            metric.get("instances"),
            field=f"metrics[{index}].instances",
        )
        if not applicable and instances:
            raise M3WorkspaceNavigationError(
                f"M3_GUI_NOT_APPLICABLE_INSTANCE_FORBIDDEN:{metric_code}"
            )
        if applicable and not instances:
            raise M3WorkspaceNavigationError(
                f"M3_GUI_APPLICABLE_INSTANCE_REQUIRED:{metric_code}"
            )
        metric_codes.append(metric_code)
        metric_applicability.append(
            M3MetricApplicabilityNavigation(
                metric_code=metric_code,
                family_code=family_code,
                applicable=applicable,
                reason_codes=reason_codes,
                system_type=system_type,
                instance_count=len(instances),
            )
        )
    if len(set(metric_codes)) != M3_GUI_METRIC_COUNT:
        raise M3WorkspaceNavigationError("M3_GUI_METRIC_MEMBERSHIP_INVALID")

    families: list[M3FamilyNavigation] = []
    family_codes: set[str] = set()
    for index, raw_family in enumerate(
        _sequence(workspace_projection.get("families"), field="families")
    ):
        family = _mapping(raw_family, field=f"families[{index}]")
        family_code = _text(
            family.get("family_code"),
            field=f"families[{index}].family_code",
        )
        if family_code in family_codes:
            raise M3WorkspaceNavigationError(
                f"M3_GUI_FAMILY_DUPLICATE:{family_code}"
            )
        family_codes.add(family_code)
        metric_count = _count(
            family.get("metric_count"),
            field=f"families[{index}].metric_count",
        )
        applicable_count = _count(
            family.get("applicable_count"),
            field=f"families[{index}].applicable_count",
        )
        not_applicable_count = _count(
            family.get("not_applicable_count"),
            field=f"families[{index}].not_applicable_count",
        )
        if applicable_count + not_applicable_count != metric_count:
            raise M3WorkspaceNavigationError(
                f"M3_GUI_FAMILY_PARTITION_INVALID:{family_code}"
            )
        families.append(
            M3FamilyNavigation(
                family_code=family_code,
                metric_count=metric_count,
                applicable_count=applicable_count,
                not_applicable_count=not_applicable_count,
            )
        )
    family_metric_count = sum(item.metric_count for item in families)
    if not families or family_metric_count != M3_GUI_METRIC_COUNT:
        raise M3WorkspaceNavigationError("M3_GUI_FAMILY_MEMBERSHIP_INVALID")

    if any(
        metric.family_code not in family_codes for metric in metric_applicability
    ):
        raise M3WorkspaceNavigationError("M3_GUI_METRIC_FAMILY_UNKNOWN")

    provenance = _mapping(
        workspace_projection.get("release_provenance"),
        field="release_provenance",
    )
    provenance_hash = _require_hash(
        provenance.get("provenance_hash"),
        field="release_provenance.provenance_hash",
    )

    return M3WorkspaceNavigationModel(
        release_id=release_id,
        manifest_hash=manifest_hash,
        provenance_hash=provenance_hash,
        training=training,
        families=tuple(families),
        metric_codes=tuple(metric_codes),
        metric_applicability=tuple(metric_applicability),
    )


def _require_success(status: int, payload: dict[str, Any]) -> dict[str, Any]:
    if 200 <= status < 300 and payload.get("outcome") != "SYSTEM_ERROR":
        return payload
    error = payload.get("error")
    code = error.get("code") if isinstance(error, dict) else None
    raise M3WorkspaceNavigationError(str(code or f"HTTP_{status}"))


def create_m3_workspace_navigation(
    qt_core: Any,
    qt_widgets: Any,
    parent: Any,
    *,
    transport: M3DesktopTransport,
    release_ids_by_training: Mapping[str, str],
) -> Any:
    """Create the four-training Release-ID-bound Desktop navigator."""

    if set(release_ids_by_training) != set(M3_GUI_TRAINING_KEYS):
        raise M3WorkspaceNavigationError("M3_GUI_RELEASE_SET_INVALID")
    release_ids = {
        key: _text(release_ids_by_training[key], field=f"release_ids.{key}")
        for key in M3_GUI_TRAINING_KEYS
    }
    if len(set(release_ids.values())) != len(M3_GUI_TRAINING_KEYS):
        raise M3WorkspaceNavigationError("M3_GUI_RELEASE_SET_INVALID")

    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaM3WorkspaceNavigation")
    layout = qt_widgets.QVBoxLayout(root)

    selector_row = qt_widgets.QWidget(root)
    selector_layout = qt_widgets.QHBoxLayout(selector_row)
    selector = qt_widgets.QComboBox(selector_row)
    selector.setObjectName("tpaaM3TrainingSelector")
    selector.addItems(list(M3_GUI_TRAINING_KEYS))
    selector_layout.addWidget(qt_widgets.QLabel("Training workspace", selector_row))
    selector_layout.addWidget(selector)
    layout.addWidget(selector_row)

    training_header = qt_widgets.QLabel("Training: unavailable", root)
    training_header.setObjectName("tpaaM3TrainingHeader")
    release_label = qt_widgets.QLabel("Release: unavailable", root)
    release_label.setObjectName("tpaaM3ReleaseIdentity")
    episode_label = qt_widgets.QLabel("Episode: unavailable", root)
    episode_label.setObjectName("tpaaM3EpisodeIdentity")
    stage_label = qt_widgets.QLabel("Stage: unavailable", root)
    stage_label.setObjectName("tpaaM3StageIdentity")
    provenance_label = qt_widgets.QLabel("Provenance: unavailable", root)
    provenance_label.setObjectName("tpaaM3ReleaseProvenance")
    layout.addWidget(training_header)
    layout.addWidget(release_label)
    layout.addWidget(episode_label)
    layout.addWidget(stage_label)
    layout.addWidget(provenance_label)

    family_table = qt_widgets.QTableWidget(root)
    family_table.setObjectName("tpaaM3FamilySummary")
    family_table.setColumnCount(4)
    family_table.setHorizontalHeaderLabels(
        ["Family", "Metrics", "Applicable", "Not applicable"]
    )
    family_table.setEditTriggers(
        qt_widgets.QAbstractItemView.EditTrigger.NoEditTriggers
    )
    layout.addWidget(family_table)

    product_table = qt_widgets.QTableWidget(root)
    product_table.setObjectName("tpaaM3ProductFamilyPresentation")
    product_table.setColumnCount(5)
    product_table.setHorizontalHeaderLabels(
        ["Family", "Product", "Meaning", "Applicable", "Not applicable"]
    )
    product_table.setEditTriggers(
        qt_widgets.QAbstractItemView.EditTrigger.NoEditTriggers
    )
    layout.addWidget(product_table)

    applicability_table = qt_widgets.QTableWidget(root)
    applicability_table.setObjectName("tpaaM3MetricApplicability")
    applicability_table.setColumnCount(7)
    applicability_table.setHorizontalHeaderLabels(
        [
            "Metric",
            "Family",
            "Product",
            "Applicable",
            "Applicability reasons",
            "System type",
            "Instances",
        ]
    )
    applicability_table.setEditTriggers(
        qt_widgets.QAbstractItemView.EditTrigger.NoEditTriggers
    )
    layout.addWidget(applicability_table)

    status_label = qt_widgets.QLabel("Navigation: IDLE", root)
    status_label.setObjectName("tpaaM3NavigationStatus")
    layout.addWidget(status_label)

    def render(training_key: str) -> None:
        release_id = release_ids.get(training_key)
        if release_id is None:
            status_label.setText("Navigation: SYSTEM_ERROR UNKNOWN_TRAINING")
            return
        try:
            status, payload = transport.m3_request_json(
                "GET",
                f"/m3/releases/{release_id}/workspace",
            )
            projection = _require_success(status, payload)
            model = build_m3_workspace_navigation_model(
                projection,
                expected_training_key=training_key,
                expected_release_id=release_id,
            )
        except Exception as exc:
            status_label.setText(
                f"Navigation: SYSTEM_ERROR {type(exc).__name__}:{exc}"
            )
            return

        identity = model.training
        training_header.setText(
            f"{identity.label} · {identity.episode_type} · "
            f"{identity.stage_profile_id}"
        )
        release_label.setText(f"Release: {model.release_id}")
        episode_label.setText(
            f"Episode: {identity.episode_id} · type={identity.episode_type}"
        )
        stage_label.setText(
            f"Stage: {identity.stage_id} · code={identity.stage_code}"
        )
        provenance_label.setText(
            f"Manifest: {model.manifest_hash} · "
            f"provenance_hash={model.provenance_hash}"
        )

        family_table.setRowCount(len(model.families))
        for row, family in enumerate(model.families):
            family_values = (
                family.family_code,
                family.metric_count,
                family.applicable_count,
                family.not_applicable_count,
            )
            for column, value in enumerate(family_values):
                family_table.setItem(
                    row,
                    column,
                    qt_widgets.QTableWidgetItem(str(value)),
                )

        product_families = [
            family
            for family in model.families
            if family.family_code in M3_GUI_FAMILY_PRESENTATION
        ]
        product_table.setRowCount(len(product_families))
        for row, family in enumerate(product_families):
            product_label, meaning = M3_GUI_FAMILY_PRESENTATION[family.family_code]
            product_values = (
                family.family_code,
                product_label,
                meaning,
                family.applicable_count,
                family.not_applicable_count,
            )
            for column, value in enumerate(product_values):
                product_table.setItem(
                    row,
                    column,
                    qt_widgets.QTableWidgetItem(str(value)),
                )

        product_metrics = [
            metric
            for metric in model.metric_applicability
            if metric.family_code in M3_GUI_FAMILY_PRESENTATION
        ]
        applicability_table.setRowCount(len(product_metrics))
        for row, metric in enumerate(product_metrics):
            product_label, _ = M3_GUI_FAMILY_PRESENTATION[metric.family_code]
            reason_text = (
                ", ".join(metric.reason_codes) if metric.reason_codes else "—"
            )
            system_type_text = metric.system_type or "—"
            instance_text = (
                str(metric.instance_count)
                if metric.applicable
                else "0 · no observation"
            )
            metric_values = (
                metric.metric_code,
                metric.family_code,
                product_label,
                "YES" if metric.applicable else "NO",
                reason_text,
                system_type_text,
                instance_text,
            )
            for column, value in enumerate(metric_values):
                applicability_table.setItem(
                    row,
                    column,
                    qt_widgets.QTableWidgetItem(str(value)),
                )

        status_label.setText(
            f"Navigation: READY · {identity.training_key} · "
            f"{len(model.metric_codes)} metrics"
        )

    selector.currentTextChanged.connect(render)
    render(selector.currentText())
    root.setProperty("tpaaM3NavigationMode", "RELEASE_BOUND")
    root.setProperty("tpaaM3ApplicabilityMode", "PROJECTED")
    return root
