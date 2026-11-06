"""W7 fail-closed presentation contracts for P11 and external capabilities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast
from uuid import UUID


class W7ProjectionError(RuntimeError):
    """Stable W7 presentation-boundary failure."""


@dataclass(frozen=True, slots=True)
class UpperProductProjection:
    snapshot_id: str
    kind: str
    source_release_ids: tuple[str, ...]
    as_of_utc: str
    logical_content_hash: str
    payload: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class CapabilityGate:
    capability: str
    state: str
    action_enabled: bool
    reason_code: str
    endpoint_ref: str | None = None
    acceptance_evidence_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ModelRegistryProjection:
    model_id: str
    status: str
    validation_state: str
    applicability_status: str
    calibration_status: str
    release_state: str
    plugin_identity: str
    artifact_hash: str


_GATED_STATES = frozenset(
    {
        "NOT_CONFIGURED",
        "DEPENDENCY_MISSING",
        "NOT_ACCEPTED",
        "UNAVAILABLE",
        "AVAILABLE",
    }
)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise W7ProjectionError(f"W7_TEXT_INVALID:{field}")
    return value


def _uuid(value: object, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = UUID(text)
    except ValueError as exc:
        raise W7ProjectionError(f"W7_UUID_INVALID:{field}") from exc
    if parsed.int == 0 or str(parsed) != text:
        raise W7ProjectionError(f"W7_UUID_INVALID:{field}")
    return text


def _hash(value: object, field: str) -> str:
    text = _text(value, field)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise W7ProjectionError(f"W7_SHA256_INVALID:{field}")
    return text


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise W7ProjectionError(f"W7_MAPPING_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _strings(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise W7ProjectionError(f"W7_STRINGS_INVALID:{field}")
    if not all(isinstance(item, str) and item for item in value):
        raise W7ProjectionError(f"W7_STRINGS_INVALID:{field}")
    return tuple(cast(Sequence[str], value))


def build_upper_product_projection(
    projection: Mapping[str, object],
    *,
    expected_snapshot_id: str,
    expected_kind: str,
) -> UpperProductProjection:
    """Validate one exact immutable upper-product DTO at the GUI boundary."""

    if expected_snapshot_id.lower() in {"current", "latest"}:
        raise W7ProjectionError("W7_MUTABLE_ALIAS_FORBIDDEN")
    if projection.get("schema") != "TPAA_ED2_UPPER_PRODUCT_PROJECTION_V1":
        raise W7ProjectionError("W7_UPPER_SCHEMA_INVALID")
    snapshot_id = _uuid(projection.get("snapshot_id"), "snapshot_id")
    if snapshot_id != expected_snapshot_id:
        raise W7ProjectionError("W7_UPPER_EXACT_ID_MISMATCH")
    kind = _text(projection.get("kind"), "kind")
    if kind != expected_kind:
        raise W7ProjectionError("W7_UPPER_KIND_MISMATCH")
    if projection.get("frozen") is not True:
        raise W7ProjectionError("W7_UPPER_FROZEN_REQUIRED")
    if projection.get("mutable_alias_resolution") is not False:
        raise W7ProjectionError("W7_MUTABLE_ALIAS_FORBIDDEN")
    source_release_ids = _strings(projection.get("source_release_ids"), "source_release_ids")
    if not source_release_ids:
        raise W7ProjectionError("W7_SOURCE_RELEASE_REQUIRED")
    payload = _mapping(projection.get("payload"), "payload")
    _validate_kind_payload(kind, payload, source_release_ids)
    return UpperProductProjection(
        snapshot_id=snapshot_id,
        kind=kind,
        source_release_ids=source_release_ids,
        as_of_utc=_text(projection.get("as_of_utc"), "as_of_utc"),
        logical_content_hash=_hash(projection.get("logical_content_hash"), "logical_content_hash"),
        payload=payload,
    )


def _validate_kind_payload(
    kind: str,
    payload: Mapping[str, object],
    source_release_ids: tuple[str, ...],
) -> None:
    if kind == "COURSE_UNIT_ANALYTICS":
        if payload.get("scope_kind") not in {"COURSE", "UNIT"}:
            raise W7ProjectionError("W7_COURSE_SCOPE_INVALID")
        if payload.get("privacy_mode") != "AGGREGATED":
            raise W7ProjectionError("W7_COURSE_PRIVACY_INVALID")
        if payload.get("suppressed_below_minimum") is not True:
            raise W7ProjectionError("W7_COURSE_SUPPRESSION_REQUIRED")
        cohort_size = payload.get("cohort_size")
        minimum = payload.get("minimum_cohort_size")
        if (
            isinstance(cohort_size, bool)
            or not isinstance(cohort_size, int)
            or isinstance(minimum, bool)
            or not isinstance(minimum, int)
            or minimum < 2
        ):
            raise W7ProjectionError("W7_COURSE_COHORT_INVALID")
        expected = "PUBLISHED" if cohort_size >= minimum else "SUPPRESSED"
        if payload.get("result_state") != expected:
            raise W7ProjectionError("W7_COURSE_SUPPRESSION_MISMATCH")
    elif kind == "JOINT_LVC_GATEWAY":
        if (
            payload.get("external_protocol_boundary") is not True
            or payload.get("session_type") != "LVC"
            or payload.get("mapping_lossless") is not True
            or payload.get("fact_projection_separated") is not True
            or payload.get("operational_optimization") is not False
        ):
            raise W7ProjectionError("W7_GATEWAY_CONTRACT_INVALID")
        _hash(payload.get("mapping_profile_sha256"), "mapping_profile_sha256")
        _text(payload.get("interop_snapshot_id"), "interop_snapshot_id")
    elif kind == "TRAINING_PLUGIN_COMPOSITION":
        if payload.get("untrusted_dynamic_loading") is not False:
            raise W7ProjectionError("W7_PLUGIN_DYNAMIC_LOAD_FORBIDDEN")
        components = payload.get("components")
        if not isinstance(components, Sequence) or isinstance(components, (str, bytes)):
            raise W7ProjectionError("W7_PLUGIN_COMPONENTS_INVALID")
        for index, raw in enumerate(components):
            item = _mapping(raw, f"components[{index}]")
            if item.get("distribution_kind") != "BUILTIN_FROZEN":
                raise W7ProjectionError("W7_PLUGIN_EXTERNAL_NOT_ACCEPTED")
            if item.get("approval_state") != "BASELINE_AUTHORIZED":
                raise W7ProjectionError("W7_PLUGIN_APPROVAL_REQUIRED")
            _hash(item.get("authority_hash"), f"components[{index}].authority_hash")
    elif kind == "MEDIA_DEBRIEF":
        release_id = _uuid(payload.get("release_id"), "payload.release_id")
        if release_id not in source_release_ids:
            raise W7ProjectionError("W7_MEDIA_RELEASE_MISMATCH")
        if payload.get("business_recompute") is not False:
            raise W7ProjectionError("W7_MEDIA_RECOMPUTE_FORBIDDEN")
        if not all(payload.get(field) is True for field in ("cesium_linked", "view_2d", "view_3d")):
            raise W7ProjectionError("W7_MEDIA_VIEW_BINDING_INVALID")
    else:
        raise W7ProjectionError(f"W7_UPPER_KIND_UNSUPPORTED:{kind}")


def build_capability_gate(value: Mapping[str, object]) -> CapabilityGate:
    """Only accepted endpoint evidence can enable an external action."""

    capability = _text(value.get("capability"), "capability")
    state = _text(value.get("state"), "state")
    if state not in _GATED_STATES:
        raise W7ProjectionError("W7_GATE_STATE_INVALID")
    reason = _text(value.get("reason_code"), "reason_code")
    endpoint = value.get("endpoint_ref")
    evidence = value.get("acceptance_evidence_sha256")
    if state == "AVAILABLE":
        endpoint_text = _text(endpoint, "endpoint_ref")
        evidence_hash = _hash(evidence, "acceptance_evidence_sha256")
        return CapabilityGate(
            capability=capability,
            state=state,
            action_enabled=True,
            reason_code=reason,
            endpoint_ref=endpoint_text,
            acceptance_evidence_sha256=evidence_hash,
        )
    if endpoint is not None or evidence is not None:
        raise W7ProjectionError("W7_GATE_UNACCEPTED_EVIDENCE_FORBIDDEN")
    return CapabilityGate(
        capability=capability,
        state=state,
        action_enabled=False,
        reason_code=reason,
    )


def local_external_capability_gates() -> tuple[CapabilityGate, ...]:
    """Development-default gates; no external acceptance is inferred locally."""

    return tuple(
        build_capability_gate(value)
        for value in (
            {
                "capability": "JOINT_LVC_LIVE_GATEWAY",
                "state": "NOT_CONFIGURED",
                "reason_code": "APPROVED_STAGING_ENDPOINT_REQUIRED",
            },
            {
                "capability": "EXTERNAL_PLUGIN_EXECUTION",
                "state": "NOT_CONFIGURED",
                "reason_code": "TRUST_ROOT_AND_SANDBOX_REQUIRED",
            },
            {
                "capability": "MEDIA_OBJECT_DELIVERY_EXPORT",
                "state": "NOT_CONFIGURED",
                "reason_code": "OBJECT_STORE_AND_REDACTION_POLICY_REQUIRED",
            },
            {
                "capability": "MODEL_ONLINE_MONITORING_ROLLBACK",
                "state": "NOT_CONFIGURED",
                "reason_code": "MONITORING_ENDPOINT_AND_APPROVAL_REQUIRED",
            },
        )
    )


def build_model_registry_projection(
    payload: Mapping[str, object], *, expected_model_id: str
) -> ModelRegistryProjection:
    """Project the exact M9 model registry record without deriving status."""

    if expected_model_id.lower() in {"current", "latest"}:
        raise W7ProjectionError("W7_MUTABLE_ALIAS_FORBIDDEN")
    model_id = _text(payload.get("capability_model_id"), "capability_model_id")
    if model_id != expected_model_id:
        raise W7ProjectionError("W7_MODEL_EXACT_ID_MISMATCH")
    plugin_name = _text(payload.get("plugin_name"), "plugin_name")
    plugin_version = _text(payload.get("plugin_version"), "plugin_version")
    return ModelRegistryProjection(
        model_id=model_id,
        status=_text(payload.get("status"), "status"),
        validation_state=_text(payload.get("validation_status"), "validation_status"),
        applicability_status=_text(payload.get("applicability_status"), "applicability_status"),
        calibration_status=_text(payload.get("calibration_status"), "calibration_status"),
        release_state=_text(payload.get("release_state"), "release_state"),
        plugin_identity=f"{plugin_name}@{plugin_version}",
        artifact_hash=_hash(payload.get("model_artifact_hash"), "model_artifact_hash"),
    )


__all__ = [
    "CapabilityGate",
    "ModelRegistryProjection",
    "UpperProductProjection",
    "W7ProjectionError",
    "build_capability_gate",
    "build_model_registry_projection",
    "build_upper_product_projection",
    "local_external_capability_gates",
]
