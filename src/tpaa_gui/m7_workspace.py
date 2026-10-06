"""M7 P1/P2/P3 three-layer exact-revision GUI presentation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast

from .discovery import ProductDiscoveryError, product_items


class M7WorkspacePresentationError(RuntimeError):
    """Fail-closed M7 GUI projection error."""


class M7DesktopTransport(Protocol):
    def m7_request_json(
        self,
        method: str,
        path: str,
    ) -> tuple[int, Mapping[str, object]]: ...

    def product_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Mapping[str, object]]: ...


@dataclass(frozen=True, slots=True)
class M7LayerPresentation:
    layer: str
    release_id: str
    logical_hash: str
    projection: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class M7ReferenceConditionPresentation:
    twin_revision_id: str
    estimate_id: str
    capability_type: str
    component_model_refs: tuple[str, ...]
    reference_condition_id: str
    session_order: int
    value: float | None
    unit: str
    uncertainty_lower: float | None
    uncertainty_upper: float | None
    validity_domain_status: str
    claim_level: str
    as_of_time: str
    revision_no: int


@dataclass(frozen=True, slots=True)
class M7ThreeLayerWorkspaceModel:
    observed: M7LayerPresentation
    adjusted: M7LayerPresentation
    p3: M7ReferenceConditionPresentation
    logical_product_hash: str


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise M7WorkspacePresentationError(f"M7_GUI_MAPPING_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise M7WorkspacePresentationError(f"M7_GUI_TEXT_INVALID:{field}")
    return value


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise M7WorkspacePresentationError(f"M7_GUI_INTEGER_INVALID:{field}")
    return value


def _optional_number(value: object, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise M7WorkspacePresentationError(f"M7_GUI_NUMBER_INVALID:{field}")
    return float(value)


def _strings(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise M7WorkspacePresentationError(f"M7_GUI_STRINGS_INVALID:{field}")
    return tuple(cast(list[str], value))


def _canonical_hash(value: object) -> str:
    try:
        raw = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise M7WorkspacePresentationError(
            f"M7_GUI_CANONICAL_JSON_INVALID:{type(exc).__name__}"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def _verify_transport_hash(projection: Mapping[str, object]) -> str:
    expected = _text(
        projection.get("logical_product_hash"),
        "logical_product_hash",
    )
    material = {
        key: value
        for key, value in projection.items()
        if key != "logical_product_hash"
    }
    if _canonical_hash(material) != expected:
        raise M7WorkspacePresentationError("M7_GUI_LOGICAL_HASH_MISMATCH")
    return expected


def _layer(
    value: object,
    *,
    expected_layer: str,
) -> M7LayerPresentation:
    layer = _mapping(value, expected_layer)
    actual_layer = _text(layer.get("layer"), f"{expected_layer}.layer")
    if actual_layer != expected_layer:
        raise M7WorkspacePresentationError("M7_GUI_LAYER_IDENTITY_MISMATCH")
    release_id = _text(layer.get("release_id"), f"{expected_layer}.release_id")
    logical_hash = _text(
        layer.get("logical_hash"),
        f"{expected_layer}.logical_hash",
    )
    projection = _mapping(
        layer.get("projection"),
        f"{expected_layer}.projection",
    )
    if _canonical_hash(dict(projection)) != logical_hash:
        raise M7WorkspacePresentationError("M7_GUI_LAYER_HASH_MISMATCH")
    return M7LayerPresentation(
        layer=actual_layer,
        release_id=release_id,
        logical_hash=logical_hash,
        projection=dict(projection),
    )


def build_m7_three_layer_workspace_model(
    projection: Mapping[str, object],
    *,
    expected_twin_revision_id: str,
    expected_estimate_id: str,
) -> M7ThreeLayerWorkspaceModel:
    logical_hash = _verify_transport_hash(projection)
    identity = _mapping(projection.get("identity"), "identity")
    if (
        _text(identity.get("twin_revision_id"), "identity.twin_revision_id")
        != expected_twin_revision_id
    ):
        raise M7WorkspacePresentationError("M7_GUI_TWIN_REVISION_MISMATCH")
    if (
        _text(identity.get("estimate_id"), "identity.estimate_id")
        != expected_estimate_id
    ):
        raise M7WorkspacePresentationError("M7_GUI_ESTIMATE_ID_MISMATCH")

    observed = _layer(
        projection.get("observed"),
        expected_layer="P1_OBSERVED",
    )
    adjusted = _layer(
        projection.get("adjusted"),
        expected_layer="P2_ADJUSTED",
    )
    p3 = _mapping(projection.get("p3"), "p3")
    if (
        _text(p3.get("layer"), "p3.layer")
        != "P3_REFERENCE_CONDITION_LONGITUDINAL"
    ):
        raise M7WorkspacePresentationError("M7_GUI_P3_LAYER_INVALID")
    twin = _mapping(p3.get("twin"), "p3.twin")
    estimate = _mapping(p3.get("estimate"), "p3.estimate")
    twin_revision_id = _text(
        twin.get("twin_revision_id"),
        "p3.twin.twin_revision_id",
    )
    estimate_id = _text(estimate.get("estimate_id"), "p3.estimate.estimate_id")
    if twin_revision_id != expected_twin_revision_id:
        raise M7WorkspacePresentationError("M7_GUI_TWIN_REVISION_MISMATCH")
    if estimate_id != expected_estimate_id:
        raise M7WorkspacePresentationError("M7_GUI_ESTIMATE_ID_MISMATCH")
    if (
        _text(
            estimate.get("twin_revision_id"),
            "p3.estimate.twin_revision_id",
        )
        != twin_revision_id
    ):
        raise M7WorkspacePresentationError("M7_GUI_TWIN_ESTIMATE_MISMATCH")
    claim_level = _text(estimate.get("claim_level"), "p3.estimate.claim_level")
    if claim_level != "REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE":
        raise M7WorkspacePresentationError("M7_GUI_CLAIM_LEVEL_INVALID")
    condition = _mapping(
        estimate.get("condition_point"),
        "p3.estimate.condition_point",
    )
    uncertainty = _mapping(
        estimate.get("uncertainty"),
        "p3.estimate.uncertainty",
    )
    status = _text(
        estimate.get("validity_domain_status"),
        "p3.estimate.validity_domain_status",
    )
    value = _optional_number(estimate.get("value"), "p3.estimate.value")
    lower = _optional_number(uncertainty.get("lower"), "p3.uncertainty.lower")
    upper = _optional_number(uncertainty.get("upper"), "p3.uncertainty.upper")
    if status == "IN_DOMAIN":
        if value is None or lower is None or upper is None:
            raise M7WorkspacePresentationError("M7_GUI_P3_DOMAIN_STATE_INVALID")
    elif status == "OUT_OF_DOMAIN":
        if value is not None or lower is not None or upper is not None:
            raise M7WorkspacePresentationError("M7_GUI_P3_DOMAIN_STATE_INVALID")
    else:
        raise M7WorkspacePresentationError("M7_GUI_P3_DOMAIN_STATUS_INVALID")
    p3_model = M7ReferenceConditionPresentation(
        twin_revision_id=twin_revision_id,
        estimate_id=estimate_id,
        capability_type=_text(
            estimate.get("capability_type"),
            "p3.estimate.capability_type",
        ),
        component_model_refs=_strings(
            twin.get("component_model_refs"),
            "p3.twin.component_model_refs",
        ),
        reference_condition_id=_text(
            condition.get("reference_condition_id"),
            "p3.condition.reference_condition_id",
        ),
        session_order=_integer(
            condition.get("session_order"),
            "p3.condition.session_order",
        ),
        value=value,
        unit=_text(estimate.get("unit"), "p3.estimate.unit"),
        uncertainty_lower=lower,
        uncertainty_upper=upper,
        validity_domain_status=status,
        claim_level=claim_level,
        as_of_time=_text(
            estimate.get("as_of_time"),
            "p3.estimate.as_of_time",
        ),
        revision_no=_integer(twin.get("revision_no"), "p3.twin.revision_no"),
    )
    return M7ThreeLayerWorkspaceModel(
        observed=observed,
        adjusted=adjusted,
        p3=p3_model,
        logical_product_hash=logical_hash,
    )


def _success(
    status: int,
    payload: Mapping[str, object],
) -> Mapping[str, object]:
    if status != 200:
        raise M7WorkspacePresentationError(
            f"M7_GUI_HTTP_ERROR:{status}:{payload!r}"
        )
    return payload


def create_m7_workspace(
    *,
    qt_widgets: Any,
    transport: M7DesktopTransport,
    parent: Any = None,
) -> Any:
    """Create a transport-only P1/P2/P3 exact-revision workspace."""

    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaM7Workspace")
    layout = qt_widgets.QVBoxLayout(root)

    twin_input = qt_widgets.QComboBox(root)
    twin_input.setObjectName("tpaaM7TwinRevisionInput")
    estimate_input = qt_widgets.QComboBox(root)
    estimate_input.setObjectName("tpaaM7EstimateInput")
    refresh_button = qt_widgets.QPushButton("Refresh P3 discovery", root)
    refresh_button.setObjectName("tpaaM7DiscoveryRefresh")
    load_button = qt_widgets.QPushButton("Load exact P3 workspace", root)
    layout.addWidget(twin_input)
    layout.addWidget(estimate_input)
    layout.addWidget(refresh_button)
    layout.addWidget(load_button)

    observed_label = qt_widgets.QLabel("P1 OBSERVED: unavailable", root)
    observed_label.setObjectName("tpaaM7Observed")
    adjusted_label = qt_widgets.QLabel("P2 ADJUSTED: unavailable", root)
    adjusted_label.setObjectName("tpaaM7Adjusted")
    p3_label = qt_widgets.QLabel(
        "P3 REFERENCE-CONDITION LONGITUDINAL: unavailable",
        root,
    )
    p3_label.setObjectName("tpaaM7ReferenceCondition")
    for widget in (observed_label, adjusted_label, p3_label):
        layout.addWidget(widget)

    estimate_items: list[dict[str, object]] = []

    def update_estimates(_twin: str = "") -> None:
        twin_id = twin_input.currentText().strip()
        estimate_input.clear()
        for item in estimate_items:
            metadata = item.get("metadata")
            if not isinstance(metadata, Mapping):
                continue
            if str(metadata.get("twin_revision_id", "")) != twin_id:
                continue
            estimate_input.addItem(str(item["exact_id"]))

    def refresh_discovery() -> None:
        nonlocal estimate_items
        try:
            twins = product_items(transport, "P3_TWIN")
            estimate_items = product_items(transport, "P3_ESTIMATE")
        except ProductDiscoveryError as exc:
            p3_label.setText(f"P3 discovery: ERROR · {exc}")
            return
        twin_input.clear()
        twin_input.addItems([str(item["exact_id"]) for item in twins])
        update_estimates()
        p3_label.setText(
            f"P3 discovery: {len(twins)} twins / "
            f"{len(estimate_items)} estimates"
        )

    def load_workspace() -> None:
        twin_revision_id = twin_input.currentText().strip()
        estimate_id = estimate_input.currentText().strip()
        status, payload = transport.m7_request_json(
            "GET",
            (
                f"/m7/p3/twins/{twin_revision_id}/estimates/"
                f"{estimate_id}/workspace"
            ),
        )
        model = build_m7_three_layer_workspace_model(
            _success(status, payload),
            expected_twin_revision_id=twin_revision_id,
            expected_estimate_id=estimate_id,
        )
        observed_label.setText(
            f"P1 OBSERVED · release={model.observed.release_id} · "
            f"hash={model.observed.logical_hash}"
        )
        adjusted_label.setText(
            f"P2 ADJUSTED · release={model.adjusted.release_id} · "
            f"hash={model.adjusted.logical_hash}"
        )
        p3_label.setText(
            "P3 REFERENCE-CONDITION LONGITUDINAL · "
            f"twin={model.p3.twin_revision_id} · "
            f"revision={model.p3.revision_no} · "
            f"value={model.p3.value} {model.p3.unit} · "
            f"validity={model.p3.validity_domain_status} · "
            f"claim={model.p3.claim_level} · "
            f"as-of={model.p3.as_of_time}"
        )

    twin_input.currentTextChanged.connect(update_estimates)
    refresh_button.clicked.connect(refresh_discovery)
    load_button.clicked.connect(load_workspace)
    return root
