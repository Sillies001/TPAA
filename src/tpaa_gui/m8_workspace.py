"""M8 presentation-only P1-P5 layered workspace."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast


class M8WorkspacePresentationError(RuntimeError):
    """Fail-closed M8 GUI projection error."""


class M8DesktopTransport(Protocol):
    def m8_request_json(
        self,
        method: str,
        path: str,
    ) -> tuple[int, Mapping[str, object]]: ...


@dataclass(frozen=True)
class M8IndividualPresentation:
    actor_assessment_id: str
    subject_key: str
    direct_actor_id: str | None
    approval_state: str
    p3_claim_level: str
    p3_validity_status: str
    p3_as_of_utc: str
    uncertainty_lower: float | None
    uncertainty_upper: float | None
    score: None
    grade: None


@dataclass(frozen=True)
class M8TeamMissionPresentation:
    mission_assessment_id: str
    composition_id: str
    participant_subject_keys: tuple[str, ...]
    approval_state: str
    claim_level: str
    validity_status: str
    as_of_utc: str
    objective_result_refs: tuple[str, ...]
    overall_score: None
    grade: None


@dataclass(frozen=True)
class M8LayeredWorkspaceModel:
    aircraft_layers: tuple[str, ...]
    p4: M8IndividualPresentation
    p5: M8TeamMissionPresentation
    logical_product_hash: str


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise M8WorkspacePresentationError(f"M8_GUI_MAPPING_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise M8WorkspacePresentationError(f"M8_GUI_TEXT_INVALID:{field}")
    return value


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field)


def _optional_number(value: object, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise M8WorkspacePresentationError(f"M8_GUI_NUMBER_INVALID:{field}")
    return float(value)


def _strings(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise M8WorkspacePresentationError(f"M8_GUI_STRINGS_INVALID:{field}")
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


def build_m8_layered_workspace_model(
    projection: Mapping[str, object],
    *,
    expected_p4_revision_id: str,
    expected_p5_revision_id: str,
) -> M8LayeredWorkspaceModel:
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
        raise M8WorkspacePresentationError("M8_GUI_LOGICAL_HASH_MISMATCH")

    aircraft = _mapping(
        projection.get("aircraft_capability_context"),
        "aircraft_capability_context",
    )
    layers: list[str] = []
    observed = _mapping(aircraft.get("observed"), "aircraft.observed")
    adjusted = _mapping(aircraft.get("adjusted"), "aircraft.adjusted")
    p3 = _mapping(aircraft.get("p3"), "aircraft.p3")
    layers.append(_text(observed.get("layer"), "aircraft.observed.layer"))
    layers.append(_text(adjusted.get("layer"), "aircraft.adjusted.layer"))
    layers.append(_text(p3.get("layer"), "aircraft.p3.layer"))
    if tuple(layers) != (
        "P1_OBSERVED",
        "P2_ADJUSTED",
        "P3_REFERENCE_CONDITION_LONGITUDINAL",
    ):
        raise M8WorkspacePresentationError("M8_GUI_AIRCRAFT_LAYER_MISMATCH")

    p4 = _mapping(projection.get("p4"), "p4")
    p5 = _mapping(projection.get("p5"), "p5")
    p4_id = _text(p4.get("actor_assessment_id"), "p4.actor_assessment_id")
    p5_id = _text(
        p5.get("mission_assessment_id"),
        "p5.mission_assessment_id",
    )
    if p4_id != expected_p4_revision_id:
        raise M8WorkspacePresentationError("M8_GUI_P4_REVISION_MISMATCH")
    if p5_id != expected_p5_revision_id:
        raise M8WorkspacePresentationError("M8_GUI_P5_REVISION_MISMATCH")
    if p4.get("score") is not None or p4.get("grade") is not None:
        raise M8WorkspacePresentationError("M8_GUI_P4_SCORE_NOT_AUTHORIZED")
    if p5.get("overall_score") is not None or p5.get("grade") is not None:
        raise M8WorkspacePresentationError("M8_GUI_P5_SCORE_NOT_AUTHORIZED")

    uncertainty = _mapping(p4.get("uncertainty"), "p4.uncertainty")
    p4_model = M8IndividualPresentation(
        actor_assessment_id=p4_id,
        subject_key=_text(p4.get("subject_key"), "p4.subject_key"),
        direct_actor_id=_optional_text(p4.get("actor_id"), "p4.actor_id"),
        approval_state=_text(
            p4.get("approval_state"),
            "p4.approval_state",
        ),
        p3_claim_level=_text(
            p4.get("p3_claim_level"),
            "p4.p3_claim_level",
        ),
        p3_validity_status=_text(
            p4.get("p3_validity_status"),
            "p4.p3_validity_status",
        ),
        p3_as_of_utc=_text(p4.get("p3_as_of_utc"), "p4.p3_as_of_utc"),
        uncertainty_lower=_optional_number(
            uncertainty.get("lower"),
            "p4.uncertainty.lower",
        ),
        uncertainty_upper=_optional_number(
            uncertainty.get("upper"),
            "p4.uncertainty.upper",
        ),
        score=None,
        grade=None,
    )
    p5_model = M8TeamMissionPresentation(
        mission_assessment_id=p5_id,
        composition_id=_text(
            p5.get("composition_id"),
            "p5.composition_id",
        ),
        participant_subject_keys=_strings(
            p5.get("participant_subject_keys"),
            "p5.participant_subject_keys",
        ),
        approval_state=_text(
            p5.get("approval_state"),
            "p5.approval_state",
        ),
        claim_level=_text(p5.get("claim_level"), "p5.claim_level"),
        validity_status=_text(
            p5.get("validity_status"),
            "p5.validity_status",
        ),
        as_of_utc=_text(p5.get("as_of_utc"), "p5.as_of_utc"),
        objective_result_refs=_strings(
            p5.get("objective_result_refs"),
            "p5.objective_result_refs",
        ),
        overall_score=None,
        grade=None,
    )
    return M8LayeredWorkspaceModel(
        aircraft_layers=tuple(layers),
        p4=p4_model,
        p5=p5_model,
        logical_product_hash=expected_hash,
    )


def create_m8_workspace(
    *,
    qt_widgets: Any,
    transport: M8DesktopTransport,
    parent: Any = None,
) -> Any:
    """Create a transport-only P1-P5 workspace with visible scope separation."""

    root = qt_widgets.QWidget(parent)
    root.setObjectName("tpaaM8Workspace")
    layout = qt_widgets.QVBoxLayout(root)

    p4_input = qt_widgets.QLineEdit(root)
    p4_input.setObjectName("tpaaM8P4RevisionInput")
    p5_input = qt_widgets.QLineEdit(root)
    p5_input.setObjectName("tpaaM8P5RevisionInput")
    load_button = qt_widgets.QPushButton("Load exact P4/P5 workspace", root)
    layout.addWidget(p4_input)
    layout.addWidget(p5_input)
    layout.addWidget(load_button)

    aircraft_label = qt_widgets.QLabel(
        "AIRCRAFT P1/P2/P3: unavailable",
        root,
    )
    p4_label = qt_widgets.QLabel("P4 INDIVIDUAL: unavailable", root)
    p5_label = qt_widgets.QLabel("P5 TEAM/MISSION: unavailable", root)
    for widget in (aircraft_label, p4_label, p5_label):
        layout.addWidget(widget)

    def load_workspace() -> None:
        p4_id = p4_input.text().strip()
        p5_id = p5_input.text().strip()
        status, payload = transport.m8_request_json(
            "GET",
            f"/m8/workspace/p4/{p4_id}/p5/{p5_id}",
        )
        if status != 200:
            raise M8WorkspacePresentationError(
                f"M8_GUI_HTTP_ERROR:{status}:{payload!r}"
            )
        model = build_m8_layered_workspace_model(
            payload,
            expected_p4_revision_id=p4_id,
            expected_p5_revision_id=p5_id,
        )
        aircraft_label.setText(
            "AIRCRAFT · " + " / ".join(model.aircraft_layers)
        )
        p4_label.setText(
            "P4 INDIVIDUAL · "
            f"revision={model.p4.actor_assessment_id} · "
            f"approval={model.p4.approval_state} · "
            f"validity={model.p4.p3_validity_status} · "
            f"claim={model.p4.p3_claim_level}"
        )
        p5_label.setText(
            "P5 TEAM/MISSION · "
            f"revision={model.p5.mission_assessment_id} · "
            f"composition={model.p5.composition_id} · "
            f"approval={model.p5.approval_state} · "
            f"validity={model.p5.validity_status}"
        )

    load_button.clicked.connect(load_workspace)
    return root
