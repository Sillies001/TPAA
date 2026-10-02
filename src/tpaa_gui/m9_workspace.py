"""M9 presentation-only fact/P6 projection workspace."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast


class M9WorkspacePresentationError(RuntimeError):
    """Fail-closed M9 GUI projection error."""


class M9DesktopTransport(Protocol):
    def m9_request_json(
        self,
        method: str,
        path: str,
    ) -> tuple[int, Mapping[str, object]]: ...


@dataclass(frozen=True, slots=True)
class M9ProjectionPresentation:
    product_id: str
    projection_class: str
    applicability_status: str
    uncertainty: Mapping[str, object]
    exact_refs: tuple[str, ...]
    release_state: str


@dataclass(frozen=True, slots=True)
class M9RecommendationPresentation:
    recommendation_id: str
    projection_class: str
    approval_state: str
    applicability_status: str
    uncertainty: Mapping[str, object]
    source_forecast_result_ids: tuple[str, ...]
    source_counterfactual_run_ids: tuple[str, ...]
    release_state: str


@dataclass(frozen=True, slots=True)
class M9LayeredWorkspaceModel:
    factual_layer: str
    exact_fact_refs: tuple[str, ...]
    forecast: M9ProjectionPresentation
    counterfactual: M9ProjectionPresentation
    recommendation: M9RecommendationPresentation
    business_recompute: bool
    persistence_access: bool
    projection_to_fact_upgrade: bool
    logical_product_hash: str


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise M9WorkspacePresentationError(f"M9_GUI_MAPPING_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise M9WorkspacePresentationError(f"M9_GUI_TEXT_INVALID:{field}")
    return value


def _strings(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise M9WorkspacePresentationError(f"M9_GUI_STRINGS_INVALID:{field}")
    return tuple(cast(list[str], value))


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def build_m9_layered_workspace_model(
    projection: Mapping[str, object],
    *,
    expected_forecast_result_id: str,
    expected_counterfactual_run_id: str,
    expected_recommendation_id: str,
) -> M9LayeredWorkspaceModel:
    expected_hash = _text(
        projection.get("logical_product_hash"),
        "logical_product_hash",
    )
    material = {
        key: value
        for key, value in projection.items()
        if key != "logical_product_hash"
    }
    if _canonical_hash(material) != expected_hash:
        raise M9WorkspacePresentationError("M9_GUI_LOGICAL_HASH_MISMATCH")
    fact = _mapping(projection.get("fact_layer"), "fact_layer")
    forecast = _mapping(projection.get("forecast"), "forecast")
    counterfactual = _mapping(
        projection.get("counterfactual"),
        "counterfactual",
    )
    recommendation = _mapping(
        projection.get("recommendation"),
        "recommendation",
    )
    contract = _mapping(
        projection.get("presentation_contract"),
        "presentation_contract",
    )
    if _text(fact.get("layer"), "fact_layer.layer") != "P1_P5_FACTUAL_HISTORY":
        raise M9WorkspacePresentationError("M9_GUI_FACT_LAYER_MISMATCH")
    if fact.get("immutable") is not True:
        raise M9WorkspacePresentationError("M9_GUI_FACT_MUTATION_RISK")
    if (
        _text(
            forecast.get("projection_class"),
            "forecast.projection_class",
        )
        != "P6_FORECAST_PROJECTION"
        or _text(
            counterfactual.get("projection_class"),
            "counterfactual.projection_class",
        )
        != "P6_COUNTERFACTUAL_PROJECTION"
        or _text(
            recommendation.get("projection_class"),
            "recommendation.projection_class",
        )
        != "P6_TRAINING_ADVISORY"
    ):
        raise M9WorkspacePresentationError(
            "M9_GUI_FACT_PROJECTION_CONFLATION"
        )
    forecast_id = _text(
        forecast.get("forecast_result_id"),
        "forecast.forecast_result_id",
    )
    counterfactual_id = _text(
        counterfactual.get("counterfactual_run_id"),
        "counterfactual.counterfactual_run_id",
    )
    recommendation_id = _text(
        recommendation.get("recommendation_id"),
        "recommendation.recommendation_id",
    )
    if (
        forecast_id != expected_forecast_result_id
        or counterfactual_id != expected_counterfactual_run_id
        or recommendation_id != expected_recommendation_id
    ):
        raise M9WorkspacePresentationError("M9_GUI_EXACT_REVISION_MISMATCH")
    forecast_uncertainty = _mapping(
        forecast.get("uncertainty"),
        "forecast.uncertainty",
    )
    counterfactual_uncertainty = _mapping(
        counterfactual.get("uncertainty"),
        "counterfactual.uncertainty",
    )
    recommendation_uncertainty = _mapping(
        recommendation.get("uncertainty"),
        "recommendation.uncertainty",
    )
    factual_refs = _strings(
        fact.get("exact_source_refs"),
        "fact_layer.exact_source_refs",
    )
    model_ref = _text(
        forecast.get("model_revision_id"),
        "forecast.model_revision_id",
    )
    counterfactual_models = _strings(
        counterfactual.get("model_refs"),
        "counterfactual.model_refs",
    )
    if contract.get("business_recompute") is not False:
        raise M9WorkspacePresentationError("M9_GUI_RECOMPUTE_FORBIDDEN")
    if contract.get("persistence_access") is not False:
        raise M9WorkspacePresentationError("M9_GUI_PERSISTENCE_FORBIDDEN")
    if contract.get("projection_to_fact_upgrade") is not False:
        raise M9WorkspacePresentationError(
            "M9_GUI_PROJECTION_TO_FACT_FORBIDDEN"
        )
    return M9LayeredWorkspaceModel(
        factual_layer="P1_P5_FACTUAL_HISTORY",
        exact_fact_refs=factual_refs,
        forecast=M9ProjectionPresentation(
            product_id=forecast_id,
            projection_class="P6_FORECAST_PROJECTION",
            applicability_status=_text(
                forecast.get("applicability_status"),
                "forecast.applicability_status",
            ),
            uncertainty=forecast_uncertainty,
            exact_refs=(model_ref, *factual_refs),
            release_state=_text(
                forecast.get("release_state"),
                "forecast.release_state",
            ),
        ),
        counterfactual=M9ProjectionPresentation(
            product_id=counterfactual_id,
            projection_class="P6_COUNTERFACTUAL_PROJECTION",
            applicability_status=_text(
                counterfactual.get("applicability_status"),
                "counterfactual.applicability_status",
            ),
            uncertainty=counterfactual_uncertainty,
            exact_refs=counterfactual_models,
            release_state=_text(
                counterfactual.get("release_state"),
                "counterfactual.release_state",
            ),
        ),
        recommendation=M9RecommendationPresentation(
            recommendation_id=recommendation_id,
            projection_class="P6_TRAINING_ADVISORY",
            approval_state=_text(
                recommendation.get("approval_state"),
                "recommendation.approval_state",
            ),
            applicability_status=_text(
                recommendation.get("applicability_status"),
                "recommendation.applicability_status",
            ),
            uncertainty=recommendation_uncertainty,
            source_forecast_result_ids=_strings(
                recommendation.get("source_forecast_result_ids"),
                "recommendation.source_forecast_result_ids",
            ),
            source_counterfactual_run_ids=_strings(
                recommendation.get("source_counterfactual_run_ids"),
                "recommendation.source_counterfactual_run_ids",
            ),
            release_state=_text(
                recommendation.get("release_state"),
                "recommendation.release_state",
            ),
        ),
        business_recompute=False,
        persistence_access=False,
        projection_to_fact_upgrade=False,
        logical_product_hash=expected_hash,
    )


def create_m9_workspace(
    qt_widgets: Any,
    transport: M9DesktopTransport,
    parent: Any = None,
) -> Any:
    """Create a transport-only fact/P6 workspace with visible separation."""
    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaM9Workspace")
    layout = qt_widgets.QVBoxLayout(root)
    forecast_input = qt_widgets.QLineEdit(root)
    forecast_input.setObjectName("tpaaM9ForecastRevisionInput")
    counterfactual_input = qt_widgets.QLineEdit(root)
    counterfactual_input.setObjectName("tpaaM9CounterfactualRevisionInput")
    recommendation_input = qt_widgets.QLineEdit(root)
    recommendation_input.setObjectName("tpaaM9RecommendationRevisionInput")
    load_button = qt_widgets.QPushButton("Load exact P6 workspace", root)
    for widget in (
        forecast_input,
        counterfactual_input,
        recommendation_input,
        load_button,
    ):
        layout.addWidget(widget)
    fact_label = qt_widgets.QLabel("FACT P1-P5: unavailable", root)
    forecast_label = qt_widgets.QLabel("P6 FORECAST: unavailable", root)
    counterfactual_label = qt_widgets.QLabel(
        "P6 COUNTERFACTUAL: unavailable",
        root,
    )
    recommendation_label = qt_widgets.QLabel(
        "P6 ADVISORY: unavailable",
        root,
    )
    for widget in (
        fact_label,
        forecast_label,
        counterfactual_label,
        recommendation_label,
    ):
        layout.addWidget(widget)

    def load_workspace() -> None:
        forecast_id = forecast_input.text().strip()
        counterfactual_id = counterfactual_input.text().strip()
        recommendation_id = recommendation_input.text().strip()
        path = (
            f"/m9/workspace/forecast/{forecast_id}"
            f"/counterfactual/{counterfactual_id}"
            f"/recommendation/{recommendation_id}"
        )
        status, payload = transport.m9_request_json("GET", path)
        if status != 200:
            raise M9WorkspacePresentationError(
                f"M9_GUI_HTTP_ERROR:{status}:{payload!r}"
            )
        model = build_m9_layered_workspace_model(
            payload,
            expected_forecast_result_id=forecast_id,
            expected_counterfactual_run_id=counterfactual_id,
            expected_recommendation_id=recommendation_id,
        )
        fact_label.setText(
            "FACT P1-P5 · immutable · refs="
            + ",".join(model.exact_fact_refs)
        )
        forecast_label.setText(
            "P6 FORECAST · "
            f"revision={model.forecast.product_id} · "
            f"applicability={model.forecast.applicability_status}"
        )
        counterfactual_label.setText(
            "P6 COUNTERFACTUAL · "
            f"revision={model.counterfactual.product_id} · "
            f"applicability={model.counterfactual.applicability_status}"
        )
        recommendation_label.setText(
            "P6 ADVISORY · "
            f"revision={model.recommendation.recommendation_id} · "
            f"approval={model.recommendation.approval_state}"
        )

    load_button.clicked.connect(load_workspace)
    return root
