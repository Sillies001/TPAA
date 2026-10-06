"""M6 P2 observed-vs-adjusted and diagnostics presentation adapter."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast

from .discovery import ProductDiscoveryError, product_items

M6_P2_STATUS_STYLES = {
    "P2_IDENTIFIABLE": "QLabel { border: 2px solid; padding: 4px; }",
    "P2_NOT_IDENTIFIABLE": (
        "QLabel { border: 3px dotted; padding: 4px; font-weight: bold; }"
    ),
    "P2_SYSTEM_ERROR": (
        "QLabel { border: 4px double; padding: 4px; font-weight: bold; }"
    ),
}


class M6WorkspacePresentationError(RuntimeError):
    """Fail-closed M6 GUI projection error."""


class M6DesktopTransport(Protocol):
    def m6_request_json(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, object] | None = None,
    ) -> tuple[int, Mapping[str, object]]:
        """Return one local-backend JSON response."""
        ...

    def product_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Mapping[str, object]]: ...


@dataclass(frozen=True, slots=True)
class M6ObservedPresentation:
    source_observation_id: str
    source_release_id: str
    capability_type: str
    metric_semantic_id: str
    metric_semantic_version: int
    observed_value: float
    unit: str
    coverage: float
    confidence: float
    evidence_set_id: str
    knowledge_time_utc: str


@dataclass(frozen=True, slots=True)
class M6AdjustedPresentation:
    estimate_id: str
    p2_release_id: str
    attribution_run_id: str
    attribution_spec_id: str
    attribution_spec_version: str
    model_plugin: str
    model_plugin_version: str
    reference_condition_id: str
    p2_published_at_utc: str
    status: str
    adjusted_value: float | None
    unit: str
    uncertainty_lower: float | None
    uncertainty_upper: float | None
    uncertainty_method: str
    uncertainty_level: str
    residual: float | None
    factor_effects: tuple[tuple[str, float], ...]
    factor_effect_semantics: str
    claim_level: str
    reason_codes: tuple[str, ...]
    evidence_set_id: str
    estimate_time: str
    presentation_kind: str
    style_sheet: str


@dataclass(frozen=True, slots=True)
class M6ComparisonWorkspaceModel:
    observed: M6ObservedPresentation
    adjusted: M6AdjustedPresentation
    logical_product_hash: str


@dataclass(frozen=True, slots=True)
class M6DiagnosticsWorkspaceModel:
    p2_release_id: str
    estimate_id: str
    source_release_id: str
    source_observation_id: str
    attribution_run_id: str
    reference_condition_id: str
    feature: Mapping[str, object]
    feature_spec: Mapping[str, object]
    reference: Mapping[str, object]
    cohort: Mapping[str, object]
    attribution: Mapping[str, object]
    model_artifact: Mapping[str, object] | None
    result: Mapping[str, object]
    p1_knowledge_time_utc: str
    p2_estimate_time: str
    as_of_utc: str
    logical_product_hash: str


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise M6WorkspacePresentationError(f"M6_GUI_MAPPING_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise M6WorkspacePresentationError(f"M6_GUI_TEXT_INVALID:{field}")
    return value


def _integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise M6WorkspacePresentationError(f"M6_GUI_INTEGER_INVALID:{field}")
    return value


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise M6WorkspacePresentationError(f"M6_GUI_NUMBER_INVALID:{field}")
    return float(value)


def _optional_number(value: object, field: str) -> float | None:
    if value is None:
        return None
    return _number(value, field)


def _strings(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise M6WorkspacePresentationError(f"M6_GUI_STRING_LIST_INVALID:{field}")
    return tuple(cast(list[str], value))


def _factor_effects(value: object) -> tuple[tuple[str, float], ...]:
    mapping = _mapping(value, "adjusted.factor_effects")
    items: list[tuple[str, float]] = []
    for key in sorted(mapping):
        items.append((key, _number(mapping[key], f"factor_effects.{key}")))
    return tuple(items)


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _verify_logical_hash(projection: Mapping[str, object]) -> str:
    expected = _text(
        projection.get("logical_product_hash"),
        "logical_product_hash",
    )
    material = {
        key: value
        for key, value in projection.items()
        if key != "logical_product_hash"
    }
    actual = _canonical_hash(material)
    if actual != expected:
        raise M6WorkspacePresentationError("M6_GUI_LOGICAL_HASH_MISMATCH")
    return expected


def build_m6_comparison_workspace_model(
    projection: Mapping[str, object],
    *,
    expected_p2_release_id: str,
    expected_estimate_id: str,
) -> M6ComparisonWorkspaceModel:
    logical_hash = _verify_logical_hash(projection)
    identity = _mapping(projection.get("identity"), "identity")
    observed = _mapping(projection.get("observed"), "observed")
    adjusted = _mapping(projection.get("adjusted"), "adjusted")

    p2_release_id = _text(identity.get("p2_release_id"), "identity.p2_release_id")
    estimate_id = _text(identity.get("estimate_id"), "identity.estimate_id")
    if p2_release_id != expected_p2_release_id:
        raise M6WorkspacePresentationError("M6_GUI_P2_RELEASE_MISMATCH")
    if estimate_id != expected_estimate_id:
        raise M6WorkspacePresentationError("M6_GUI_ESTIMATE_ID_MISMATCH")

    source_observation_id = _text(
        identity.get("source_observation_id"),
        "identity.source_observation_id",
    )
    source_release_id = _text(
        identity.get("source_release_id"),
        "identity.source_release_id",
    )
    attribution_run_id = _text(
        identity.get("attribution_run_id"),
        "identity.attribution_run_id",
    )
    reference_condition_id = _text(
        identity.get("reference_condition_id"),
        "identity.reference_condition_id",
    )

    if _text(observed.get("observation_id"), "observed.observation_id") != source_observation_id:
        raise M6WorkspacePresentationError("M6_GUI_SOURCE_OBSERVATION_MISMATCH")
    if _text(observed.get("release_id"), "observed.release_id") != source_release_id:
        raise M6WorkspacePresentationError("M6_GUI_SOURCE_RELEASE_MISMATCH")
    if _text(adjusted.get("estimate_id"), "adjusted.estimate_id") != estimate_id:
        raise M6WorkspacePresentationError("M6_GUI_ESTIMATE_ID_MISMATCH")
    if _text(adjusted.get("p2_release_id"), "adjusted.p2_release_id") != p2_release_id:
        raise M6WorkspacePresentationError("M6_GUI_P2_RELEASE_MISMATCH")
    if (
        _text(
            adjusted.get("attribution_run_id"),
            "adjusted.attribution_run_id",
        )
        != attribution_run_id
    ):
        raise M6WorkspacePresentationError("M6_GUI_RUN_MISMATCH")
    if (
        _text(
            adjusted.get("reference_condition_id"),
            "adjusted.reference_condition_id",
        )
        != reference_condition_id
    ):
        raise M6WorkspacePresentationError("M6_GUI_REFERENCE_MISMATCH")

    observed_model = M6ObservedPresentation(
        source_observation_id=source_observation_id,
        source_release_id=source_release_id,
        capability_type=_text(observed.get("capability_type"), "observed.capability_type"),
        metric_semantic_id=_text(
            observed.get("metric_semantic_id"),
            "observed.metric_semantic_id",
        ),
        metric_semantic_version=_integer(
            observed.get("metric_semantic_version"),
            "observed.metric_semantic_version",
        ),
        observed_value=_number(observed.get("observed_value"), "observed.observed_value"),
        unit=_text(observed.get("unit"), "observed.unit"),
        coverage=_number(observed.get("coverage"), "observed.coverage"),
        confidence=_number(observed.get("confidence"), "observed.confidence"),
        evidence_set_id=_text(
            observed.get("evidence_set_id"),
            "observed.evidence_set_id",
        ),
        knowledge_time_utc=_text(
            observed.get("knowledge_time_utc"),
            "observed.knowledge_time_utc",
        ),
    )

    status = _text(adjusted.get("status"), "adjusted.status")
    reasons = _strings(adjusted.get("reason_codes"), "adjusted.reason_codes")
    uncertainty = _mapping(adjusted.get("uncertainty"), "adjusted.uncertainty")
    effects = _factor_effects(adjusted.get("factor_effects"))
    adjusted_value = _optional_number(
        adjusted.get("adjusted_value"),
        "adjusted.adjusted_value",
    )
    residual = _optional_number(adjusted.get("residual"), "adjusted.residual")
    lower = _optional_number(uncertainty.get("lower"), "uncertainty.lower")
    upper = _optional_number(uncertainty.get("upper"), "uncertainty.upper")

    if _text(adjusted.get("unit"), "adjusted.unit") != observed_model.unit:
        raise M6WorkspacePresentationError("M6_GUI_UNIT_MISMATCH")
    if _text(
        adjusted.get("factor_effect_semantics"),
        "adjusted.factor_effect_semantics",
    ) != "MODEL_CONDITIONED_ASSOCIATION":
        raise M6WorkspacePresentationError("M6_GUI_FACTOR_EFFECT_SEMANTICS_INVALID")
    claim_level = _text(adjusted.get("claim_level"), "adjusted.claim_level")
    if claim_level != "ASSOCIATION_ONLY":
        raise M6WorkspacePresentationError("M6_GUI_CLAIM_LEVEL_INVALID")

    if status == "IDENTIFIABLE":
        if adjusted_value is None or reasons:
            raise M6WorkspacePresentationError("M6_GUI_IDENTIFIABLE_STATE_INVALID")
        kind = "P2_IDENTIFIABLE"
    elif status == "NOT_IDENTIFIABLE":
        if (
            adjusted_value is not None
            or lower is not None
            or upper is not None
            or residual is not None
            or effects
            or not reasons
        ):
            raise M6WorkspacePresentationError(
                "M6_GUI_NOT_IDENTIFIABLE_STATE_INVALID"
            )
        kind = "P2_NOT_IDENTIFIABLE"
    else:
        raise M6WorkspacePresentationError("M6_GUI_P2_STATUS_INVALID")

    adjusted_model = M6AdjustedPresentation(
        estimate_id=estimate_id,
        p2_release_id=p2_release_id,
        attribution_run_id=attribution_run_id,
        attribution_spec_id=_text(
            adjusted.get("attribution_spec_id"),
            "adjusted.attribution_spec_id",
        ),
        attribution_spec_version=_text(
            adjusted.get("attribution_spec_version"),
            "adjusted.attribution_spec_version",
        ),
        model_plugin=_text(
            adjusted.get("model_plugin"),
            "adjusted.model_plugin",
        ),
        model_plugin_version=_text(
            adjusted.get("model_plugin_version"),
            "adjusted.model_plugin_version",
        ),
        reference_condition_id=reference_condition_id,
        p2_published_at_utc=_text(
            adjusted.get("p2_published_at_utc"),
            "adjusted.p2_published_at_utc",
        ),
        status=status,
        adjusted_value=adjusted_value,
        unit=observed_model.unit,
        uncertainty_lower=lower,
        uncertainty_upper=upper,
        uncertainty_method=_text(
            uncertainty.get("method"),
            "uncertainty.method",
        ),
        uncertainty_level=_text(
            uncertainty.get("level"),
            "uncertainty.level",
        ),
        residual=residual,
        factor_effects=effects,
        factor_effect_semantics="MODEL_CONDITIONED_ASSOCIATION",
        claim_level=claim_level,
        reason_codes=reasons,
        evidence_set_id=_text(
            adjusted.get("evidence_set_id"),
            "adjusted.evidence_set_id",
        ),
        estimate_time=_text(
            adjusted.get("estimate_time"),
            "adjusted.estimate_time",
        ),
        presentation_kind=kind,
        style_sheet=M6_P2_STATUS_STYLES[kind],
    )
    return M6ComparisonWorkspaceModel(
        observed=observed_model,
        adjusted=adjusted_model,
        logical_product_hash=logical_hash,
    )


def build_m6_diagnostics_workspace_model(
    projection: Mapping[str, object],
    *,
    expected_p2_release_id: str,
    expected_estimate_id: str,
) -> M6DiagnosticsWorkspaceModel:
    logical_hash = _verify_logical_hash(projection)
    identity = _mapping(projection.get("identity"), "identity")
    p2_release_id = _text(identity.get("p2_release_id"), "identity.p2_release_id")
    estimate_id = _text(identity.get("estimate_id"), "identity.estimate_id")
    if p2_release_id != expected_p2_release_id:
        raise M6WorkspacePresentationError("M6_GUI_P2_RELEASE_MISMATCH")
    if estimate_id != expected_estimate_id:
        raise M6WorkspacePresentationError("M6_GUI_ESTIMATE_ID_MISMATCH")

    feature = _mapping(projection.get("feature"), "feature")
    reference = _mapping(projection.get("reference"), "reference")
    cohort = _mapping(projection.get("cohort"), "cohort")
    attribution = _mapping(projection.get("attribution"), "attribution")
    result = _mapping(projection.get("result"), "result")
    diagnostics = _mapping(attribution.get("diagnostics"), "attribution.diagnostics")
    source_observation_id = _text(
        identity.get("source_observation_id"),
        "identity.source_observation_id",
    )
    attribution_run_id = _text(
        identity.get("attribution_run_id"),
        "identity.attribution_run_id",
    )
    reference_condition_id = _text(
        identity.get("reference_condition_id"),
        "identity.reference_condition_id",
    )
    if _text(
        feature.get("source_observation_id"),
        "feature.source_observation_id",
    ) != source_observation_id:
        raise M6WorkspacePresentationError("M6_GUI_FEATURE_SOURCE_MISMATCH")
    if _text(
        reference.get("reference_condition_id"),
        "reference.reference_condition_id",
    ) != reference_condition_id:
        raise M6WorkspacePresentationError("M6_GUI_REFERENCE_MISMATCH")
    if _text(
        attribution.get("reference_condition_id"),
        "attribution.reference_condition_id",
    ) != reference_condition_id:
        raise M6WorkspacePresentationError("M6_GUI_RUN_REFERENCE_MISMATCH")
    if _text(
        attribution.get("attribution_run_id"),
        "attribution.attribution_run_id",
    ) != attribution_run_id:
        raise M6WorkspacePresentationError("M6_GUI_RUN_MISMATCH")
    if _text(
        attribution.get("training_dataset_snapshot_id"),
        "attribution.training_dataset_snapshot_id",
    ) != _text(cohort.get("dataset_snapshot_id"), "cohort.dataset_snapshot_id"):
        raise M6WorkspacePresentationError("M6_GUI_COHORT_RUN_MISMATCH")
    if _text(
        result.get("factor_effect_semantics"),
        "result.factor_effect_semantics",
    ) != "MODEL_CONDITIONED_ASSOCIATION":
        raise M6WorkspacePresentationError("M6_GUI_FACTOR_EFFECT_SEMANTICS_INVALID")
    if _text(result.get("claim_level"), "result.claim_level") != "ASSOCIATION_ONLY":
        raise M6WorkspacePresentationError("M6_GUI_CLAIM_LEVEL_INVALID")
    if _text(
        diagnostics.get("factor_effect_semantics"),
        "diagnostics.factor_effect_semantics",
    ) != "MODEL_CONDITIONED_ASSOCIATION":
        raise M6WorkspacePresentationError("M6_GUI_DIAGNOSTICS_SEMANTICS_INVALID")

    model_raw = projection.get("model_artifact")
    model_artifact = (
        None
        if model_raw is None
        else _mapping(model_raw, "model_artifact")
    )
    model_hash_raw = attribution.get("model_artifact_hash")
    if model_artifact is not None:
        model_hash = _text(model_hash_raw, "attribution.model_artifact_hash")
        if _canonical_hash(model_artifact) != model_hash:
            raise M6WorkspacePresentationError("M6_GUI_MODEL_ARTIFACT_HASH_MISMATCH")
    elif model_hash_raw is not None:
        raise M6WorkspacePresentationError("M6_GUI_MODEL_ARTIFACT_MISSING")

    return M6DiagnosticsWorkspaceModel(
        p2_release_id=p2_release_id,
        estimate_id=estimate_id,
        source_release_id=_text(
            identity.get("source_release_id"),
            "identity.source_release_id",
        ),
        source_observation_id=source_observation_id,
        attribution_run_id=attribution_run_id,
        reference_condition_id=reference_condition_id,
        feature=feature,
        feature_spec=_mapping(projection.get("feature_spec"), "feature_spec"),
        reference=reference,
        cohort=cohort,
        attribution=attribution,
        model_artifact=model_artifact,
        result=result,
        p1_knowledge_time_utc=_text(
            projection.get("p1_knowledge_time_utc"),
            "p1_knowledge_time_utc",
        ),
        p2_estimate_time=_text(
            projection.get("p2_estimate_time"),
            "p2_estimate_time",
        ),
        as_of_utc=_text(projection.get("as_of_utc"), "as_of_utc"),
        logical_product_hash=logical_hash,
    )


def _success(
    status: int,
    payload: Mapping[str, object],
) -> Mapping[str, object]:
    if status != 200:
        raise M6WorkspacePresentationError(
            f"M6_GUI_HTTP_ERROR:{status}:{payload!r}"
        )
    return payload


def create_m6_workspace(
    *,
    qt_widgets: Any,
    transport: M6DesktopTransport,
    parent: Any = None,
) -> Any:
    """Create a transport-only Qt P2 comparison/diagnostics workspace."""

    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaM6Workspace")
    layout = qt_widgets.QVBoxLayout(root)

    release_input = qt_widgets.QComboBox(root)
    release_input.setObjectName("tpaaM6P2ReleaseInput")
    estimate_input = qt_widgets.QComboBox(root)
    estimate_input.setObjectName("tpaaM6EstimateInput")
    refresh_button = qt_widgets.QPushButton("Refresh P2 discovery", root)
    refresh_button.setObjectName("tpaaM6DiscoveryRefresh")
    comparison_button = qt_widgets.QPushButton("Load P2 comparison", root)
    diagnostics_button = qt_widgets.QPushButton("Load P2 diagnostics", root)
    layout.addWidget(release_input)
    layout.addWidget(estimate_input)
    layout.addWidget(refresh_button)
    layout.addWidget(comparison_button)
    layout.addWidget(diagnostics_button)

    observed_label = qt_widgets.QLabel("Observed: unavailable", root)
    observed_label.setObjectName("tpaaM6Observed")
    adjusted_label = qt_widgets.QLabel("Adjusted: unavailable", root)
    adjusted_label.setObjectName("tpaaM6Adjusted")
    residual_label = qt_widgets.QLabel("Residual: unavailable", root)
    residual_label.setObjectName("tpaaM6Residual")
    uncertainty_label = qt_widgets.QLabel("Uncertainty: unavailable", root)
    uncertainty_label.setObjectName("tpaaM6Uncertainty")
    diagnostics_label = qt_widgets.QLabel("Diagnostics: unavailable", root)
    diagnostics_label.setObjectName("tpaaM6Diagnostics")
    for widget in (
        observed_label,
        adjusted_label,
        residual_label,
        uncertainty_label,
        diagnostics_label,
    ):
        layout.addWidget(widget)

    discovery_items: list[dict[str, object]] = []

    def update_estimates(_release: str = "") -> None:
        release_id = release_input.currentText().strip()
        estimate_input.clear()
        for item in discovery_items:
            metadata = item.get("metadata")
            if not isinstance(metadata, Mapping):
                continue
            if str(metadata.get("p2_release_id", "")) != release_id:
                continue
            estimate_input.addItem(str(item["exact_id"]))

    def refresh_discovery() -> None:
        nonlocal discovery_items
        try:
            discovery_items = product_items(transport, "P2_ESTIMATE")
        except ProductDiscoveryError as exc:
            diagnostics_label.setText(f"Discovery: ERROR · {exc}")
            return
        release_ids: set[str] = set()
        for item in discovery_items:
            metadata = item.get("metadata")
            if not isinstance(metadata, Mapping):
                continue
            p2_release_id = metadata.get("p2_release_id")
            if isinstance(p2_release_id, str):
                release_ids.add(p2_release_id)
        releases = sorted(release_ids)
        release_input.clear()
        release_input.addItems(releases)
        update_estimates()
        diagnostics_label.setText(
            f"Discovery: {len(discovery_items)} immutable P2 estimates"
        )

    effects_table = qt_widgets.QTableWidget(root)
    effects_table.setObjectName("tpaaM6FactorEffects")
    effects_table.setColumnCount(2)
    effects_table.setHorizontalHeaderLabels(["Factor", "Association contribution"])
    layout.addWidget(effects_table)

    def load_comparison() -> None:
        release_id = release_input.currentText().strip()
        estimate_id = estimate_input.currentText().strip()
        status, payload = transport.m6_request_json(
            "GET",
            f"/m6/p2/releases/{release_id}/estimates/{estimate_id}/comparison",
        )
        model = build_m6_comparison_workspace_model(
            _success(status, payload),
            expected_p2_release_id=release_id,
            expected_estimate_id=estimate_id,
        )
        observed_label.setText(
            f"OBSERVED · {model.observed.observed_value} {model.observed.unit} · "
            f"P1 Release {model.observed.source_release_id}"
        )
        adjusted_label.setText(
            f"{model.adjusted.presentation_kind} · "
            f"value={model.adjusted.adjusted_value} · "
            f"P2 Release {model.adjusted.p2_release_id} · "
            f"{model.adjusted.attribution_spec_id}@"
            f"{model.adjusted.attribution_spec_version} · "
            f"plugin={model.adjusted.model_plugin}@"
            f"{model.adjusted.model_plugin_version} · "
            f"reasons={','.join(model.adjusted.reason_codes) or '-'}"
        )
        adjusted_label.setStyleSheet(model.adjusted.style_sheet)
        residual_label.setText(
            f"Residual/unexplained={model.adjusted.residual} · "
            f"claim={model.adjusted.claim_level}"
        )
        uncertainty_label.setText(
            f"Uncertainty {model.adjusted.uncertainty_method} "
            f"level={model.adjusted.uncertainty_level} · "
            f"[{model.adjusted.uncertainty_lower}, "
            f"{model.adjusted.uncertainty_upper}]"
        )
        effects_table.setRowCount(len(model.adjusted.factor_effects))
        for row, (factor, effect) in enumerate(model.adjusted.factor_effects):
            effects_table.setItem(row, 0, qt_widgets.QTableWidgetItem(factor))
            effects_table.setItem(row, 1, qt_widgets.QTableWidgetItem(str(effect)))

    def load_diagnostics() -> None:
        release_id = release_input.currentText().strip()
        estimate_id = estimate_input.currentText().strip()
        status, payload = transport.m6_request_json(
            "GET",
            f"/m6/p2/releases/{release_id}/estimates/{estimate_id}/diagnostics",
        )
        model = build_m6_diagnostics_workspace_model(
            _success(status, payload),
            expected_p2_release_id=release_id,
            expected_estimate_id=estimate_id,
        )
        uncertainty = _mapping(
            model.result.get("uncertainty"),
            "result.uncertainty",
        )
        diagnostics_label.setText(
            f"run={model.attribution_run_id} · "
            f"reference={model.reference_condition_id} · "
            f"feature={model.feature.get('factor_feature_set_id')} · "
            f"feature_hash={model.feature.get('input_hash')} · "
            f"cohort={model.cohort.get('dataset_snapshot_id')} · "
            f"cohort_hash={model.cohort.get('data_hash')} · "
            f"model_hash={model.attribution.get('model_artifact_hash')} · "
            f"as-of={model.as_of_utc} · "
            f"residual={model.result.get('residual')} · "
            f"uncertainty={uncertainty.get('method')}@"
            f"{uncertainty.get('level')} · "
            "effects=MODEL_CONDITIONED_ASSOCIATION · "
            "claim=ASSOCIATION_ONLY"
        )

    release_input.currentTextChanged.connect(update_estimates)
    refresh_button.clicked.connect(refresh_discovery)
    comparison_button.clicked.connect(load_comparison)
    diagnostics_button.clicked.connect(load_diagnostics)
    return root
