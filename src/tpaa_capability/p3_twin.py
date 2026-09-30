"""M7 Batch 3 immutable P3 aircraft-twin revision and estimate products."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid5

from tpaa_longitudinal import (
    P3AuthorityPolicy,
    P3GovernanceError,
    assert_p3_claim_level,
)

from .p3_model import (
    P3CapabilityModelBuild,
    P3CapabilitySurfaceBuild,
    P3ModelExecutionProfile,
    evaluate_surface,
)

_TWIN_NAMESPACE = UUID("7bd94857-2cd6-5acf-a6f3-1129132edeb2")
_ESTIMATE_NAMESPACE = UUID("1b866e45-e949-575f-a4dc-03a2bc1a1d82")


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_AUTHORITY_REQUIRED",
            f"canonical json: {type(exc).__name__}",
        ) from exc


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _uuid(value: str, *, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        ) from exc
    if str(parsed) != value or parsed.int == 0:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    return value


def _utc(value: str, *, field: str) -> datetime:
    if not value.endswith("Z") or "T" not in value:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        ) from exc


def _finite(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise P3GovernanceError("FAIL_CLOSED_P3_AUTHORITY_REQUIRED", field)
    result = float(value)
    if not math.isfinite(result):
        raise P3GovernanceError("FAIL_CLOSED_P3_AUTHORITY_REQUIRED", field)
    return result


@dataclass(frozen=True, slots=True)
class P3TwinComponentBinding:
    model_build: P3CapabilityModelBuild
    surface_build: P3CapabilitySurfaceBuild
    model_object_ref_id: str
    surface_object_ref_id: str

    def projection(self) -> dict[str, object]:
        return {
            "capability_model_id": self.model_build.model.capability_model_id,
            "capability_type": self.model_build.model.capability_type,
            "model_artifact_hash": self.model_build.model.model_artifact_hash,
            "surface_id": self.surface_build.surface.surface_id,
            "surface_dataset_hash": self.surface_build.surface.dataset_hash,
            "model_object_ref_id": self.model_object_ref_id,
            "surface_object_ref_id": self.surface_object_ref_id,
        }


@dataclass(frozen=True, slots=True)
class P3AircraftTwinRevision:
    twin_revision_id: str
    aircraft_id: str
    revision_no: int
    component_model_refs: tuple[str, ...]
    config_snapshot_id: str
    valid_from: str
    valid_to: str | None
    as_of_data_time: str
    published_at: str
    status: str
    uncertainty_summary: Mapping[str, object]
    evidence_snapshot_id: str
    supersedes_twin_revision_id: str | None

    def projection(self) -> dict[str, object]:
        return {
            "twin_revision_id": self.twin_revision_id,
            "aircraft_id": self.aircraft_id,
            "revision_no": self.revision_no,
            "component_model_refs": list(self.component_model_refs),
            "config_snapshot_id": self.config_snapshot_id,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "as_of_data_time": self.as_of_data_time,
            "published_at": self.published_at,
            "status": self.status,
            "uncertainty_summary": dict(self.uncertainty_summary),
            "evidence_snapshot_id": self.evidence_snapshot_id,
            "supersedes_twin_revision_id": self.supersedes_twin_revision_id,
        }


@dataclass(frozen=True, slots=True)
class P3CapabilityEstimate:
    estimate_id: str
    twin_revision_id: str
    capability_type: str
    condition_point: Mapping[str, object]
    value: float | None
    unit: str
    uncertainty: Mapping[str, object]
    validity_domain_status: str
    claim_level: str
    as_of_time: str
    created_at: str

    def projection(self) -> dict[str, object]:
        return {
            "estimate_id": self.estimate_id,
            "twin_revision_id": self.twin_revision_id,
            "capability_type": self.capability_type,
            "condition_point": dict(self.condition_point),
            "value": self.value,
            "unit": self.unit,
            "uncertainty": dict(self.uncertainty),
            "validity_domain_status": self.validity_domain_status,
            "claim_level": self.claim_level,
            "as_of_time": self.as_of_time,
            "created_at": self.created_at,
        }


def _validate_component(
    component: P3TwinComponentBinding,
    *,
    aircraft_id: str,
) -> None:
    model = component.model_build.model
    surface = component.surface_build.surface
    _uuid(component.model_object_ref_id, field="model_object_ref_id")
    _uuid(component.surface_object_ref_id, field="surface_object_ref_id")
    if (
        model.subject_type != "AIRCRAFT"
        or model.subject_id != aircraft_id
        or model.status != "VALIDATED"
        or surface.capability_model_id != model.capability_model_id
    ):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_AUTHORITY_REQUIRED",
            f"component={model.capability_model_id}",
        )
    if (
        hashlib.sha256(component.model_build.artifact_bytes).hexdigest()
        != model.model_artifact_hash
        or hashlib.sha256(component.surface_build.dataset_bytes).hexdigest()
        != surface.dataset_hash
    ):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_MANAGED_OBJECT_HASH_MISMATCH",
            model.capability_model_id,
        )


def publish_aircraft_twin_revision(
    *,
    aircraft_id: str,
    components: Sequence[P3TwinComponentBinding],
    config_snapshot_id: str,
    evidence_snapshot_id: str,
    valid_from_utc: str,
    valid_to_utc: str | None,
    as_of_data_time_utc: str,
    published_at_utc: str,
    previous_revision: P3AircraftTwinRevision | None = None,
    profile: P3ModelExecutionProfile | None = None,
) -> P3AircraftTwinRevision:
    q = profile or P3ModelExecutionProfile.from_canonical()
    _uuid(aircraft_id, field="aircraft_id")
    _uuid(config_snapshot_id, field="config_snapshot_id")
    _uuid(evidence_snapshot_id, field="evidence_snapshot_id")
    valid_from = _utc(valid_from_utc, field="valid_from_utc")
    valid_to = (
        _utc(valid_to_utc, field="valid_to_utc")
        if valid_to_utc is not None
        else None
    )
    as_of = _utc(as_of_data_time_utc, field="as_of_data_time_utc")
    published = _utc(published_at_utc, field="published_at_utc")
    if valid_to is not None and valid_to <= valid_from:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            "valid_to must be greater than valid_from",
        )
    if as_of > published or valid_from > published:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_LIFECYCLE_FUTURE_INFORMATION",
            "twin publication time boundary",
        )
    if not components:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_AUTHORITY_REQUIRED",
            "twin component list is empty",
        )
    for component in components:
        _validate_component(component, aircraft_id=aircraft_id)
    component_model_refs = tuple(
        component.model_build.model.capability_model_id
        for component in components
    )
    if len(set(component_model_refs)) != len(component_model_refs):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            "duplicate component model ref",
        )
    capability_types = tuple(
        component.model_build.model.capability_type
        for component in components
    )
    if len(set(capability_types)) != len(capability_types):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_AUTHORITY_REQUIRED",
            "duplicate component capability type",
        )
    if previous_revision is None:
        revision_no = 1
        supersedes = None
    else:
        if previous_revision.aircraft_id != aircraft_id:
            raise P3GovernanceError(
                "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
                "superseded twin aircraft mismatch",
            )
        if valid_from <= _utc(previous_revision.valid_from, field="previous.valid_from"):
            raise P3GovernanceError(
                "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
                "successor valid_from must increase",
            )
        revision_no = previous_revision.revision_no + 1
        supersedes = previous_revision.twin_revision_id
    uncertainty_summary: dict[str, object] = {
        "claim_level": q.estimate_claim_level,
        "components": [
            {
                "capability_model_id": component.model_build.model.capability_model_id,
                "capability_type": component.model_build.model.capability_type,
                "p3_uncertainty_half_width": (
                    component.model_build.p3_uncertainty_half_width
                ),
            }
            for component in components
        ],
    }
    component_identity = [
        {
            **component.projection(),
            "profile_id": q.profile_id,
            "profile_version": q.profile_version,
        }
        for component in components
    ]
    identity_hash = _canonical_hash(
        {
            "aircraft_id": aircraft_id,
            "revision_no": revision_no,
            "components": component_identity,
            "config_snapshot_id": config_snapshot_id,
            "evidence_snapshot_id": evidence_snapshot_id,
            "valid_from": valid_from_utc,
            "valid_to": valid_to_utc,
            "as_of_data_time": as_of_data_time_utc,
            "published_at": published_at_utc,
            "supersedes_twin_revision_id": supersedes,
        }
    )
    twin_revision_id = str(uuid5(_TWIN_NAMESPACE, identity_hash))
    return P3AircraftTwinRevision(
        twin_revision_id=twin_revision_id,
        aircraft_id=aircraft_id,
        revision_no=revision_no,
        component_model_refs=component_model_refs,
        config_snapshot_id=config_snapshot_id,
        valid_from=valid_from_utc,
        valid_to=valid_to_utc,
        as_of_data_time=as_of_data_time_utc,
        published_at=published_at_utc,
        status="PUBLISHED",
        uncertainty_summary=uncertainty_summary,
        evidence_snapshot_id=evidence_snapshot_id,
        supersedes_twin_revision_id=supersedes,
    )


def evaluate_twin_capability_estimate(
    *,
    twin: P3AircraftTwinRevision,
    components: Sequence[P3TwinComponentBinding],
    capability_type: str,
    condition_point: Mapping[str, object],
    as_of_time_utc: str,
    created_at_utc: str,
    claim_level: str | None = None,
    policy: P3AuthorityPolicy | None = None,
    profile: P3ModelExecutionProfile | None = None,
) -> P3CapabilityEstimate:
    p = policy or P3AuthorityPolicy.from_canonical()
    q = profile or P3ModelExecutionProfile.from_canonical()
    requested_claim = claim_level or q.estimate_claim_level
    assert_p3_claim_level(requested_claim, policy=p)
    as_of = _utc(as_of_time_utc, field="as_of_time_utc")
    created = _utc(created_at_utc, field="created_at_utc")
    if as_of_time_utc != twin.as_of_data_time:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            "estimate as_of must equal exact twin as_of_data_time",
        )
    if created < _utc(twin.published_at, field="twin.published_at") or as_of > created:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_LIFECYCLE_FUTURE_INFORMATION",
            "estimate time boundary",
        )
    if set(condition_point) != {"session_order", "reference_condition_id"}:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            "condition_point fields",
        )
    session_order_value = condition_point.get("session_order")
    if isinstance(session_order_value, bool) or not isinstance(session_order_value, int):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            "condition_point.session_order",
        )
    reference_value = condition_point.get("reference_condition_id")
    if not isinstance(reference_value, str):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            "condition_point.reference_condition_id",
        )
    _uuid(reference_value, field="condition_point.reference_condition_id")
    matches = [
        component
        for component in components
        if component.model_build.model.capability_type == capability_type
    ]
    if len(matches) != 1:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            f"capability_type={capability_type!r}",
        )
    component = matches[0]
    _validate_component(component, aircraft_id=twin.aircraft_id)
    model = component.model_build.model
    if model.capability_model_id not in twin.component_model_refs:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            "component model not bound to twin revision",
        )
    domain_reference = model.validity_domain.get("reference_condition_id")
    if domain_reference != reference_value:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            "condition reference mismatch",
        )
    surface_value = evaluate_surface(
        component.surface_build,
        session_order=session_order_value,
    )
    unit_value = component.model_build.artifact.get("unit")
    if not isinstance(unit_value, str) or not unit_value:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_AUTHORITY_REQUIRED",
            "model unit missing",
        )
    if surface_value.validity_domain_status == "IN_DOMAIN":
        value = _finite(surface_value.value, field="surface.value")
        lower = _finite(
            surface_value.uncertainty_lower,
            field="surface.uncertainty_lower",
        )
        upper = _finite(
            surface_value.uncertainty_upper,
            field="surface.uncertainty_upper",
        )
    elif surface_value.validity_domain_status == "OUT_OF_DOMAIN":
        value = None
        lower = None
        upper = None
    else:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            surface_value.validity_domain_status,
        )
    uncertainty: dict[str, object] = {
        "lower": lower,
        "upper": upper,
        "surface_id": component.surface_build.surface.surface_id,
        "surface_dataset_hash": component.surface_build.surface.dataset_hash,
    }
    normalized_condition = {
        "session_order": session_order_value,
        "reference_condition_id": reference_value,
    }
    identity_hash = _canonical_hash(
        {
            "twin_revision_id": twin.twin_revision_id,
            "capability_model_id": model.capability_model_id,
            "surface_id": component.surface_build.surface.surface_id,
            "capability_type": capability_type,
            "condition_point": normalized_condition,
            "value": value,
            "unit": unit_value,
            "uncertainty": uncertainty,
            "validity_domain_status": surface_value.validity_domain_status,
            "claim_level": requested_claim,
            "as_of_time": as_of_time_utc,
        }
    )
    estimate_id = str(uuid5(_ESTIMATE_NAMESPACE, identity_hash))
    return P3CapabilityEstimate(
        estimate_id=estimate_id,
        twin_revision_id=twin.twin_revision_id,
        capability_type=capability_type,
        condition_point=normalized_condition,
        value=value,
        unit=unit_value,
        uncertainty=uncertainty,
        validity_domain_status=surface_value.validity_domain_status,
        claim_level=requested_claim,
        as_of_time=as_of_time_utc,
        created_at=created_at_utc,
    )
