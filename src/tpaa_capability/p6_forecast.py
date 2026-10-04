"""M9 Batch 2 deterministic P6 model, applicability and forecast products."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid5

from tpaa_assessment.p4_revision import P4AssessmentRevision
from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader
from tpaa_context.p6_governance import (
    P6AuthorityPolicy,
    P6GovernanceError,
    canonical_hash,
    exact_hash64,
    exact_text,
    exact_uuid,
    utc,
)

from .p3_twin import P3CapabilityEstimate
from .p6_input import (
    P6ForecastRequestBinding,
    P6InputSnapshot,
    assert_p6_input_snapshot_identity,
)

_PROFILE_ARTIFACT_ID = "P6_P3_CAPABILITY_OLS_MAD_FORECAST_PROFILE"
_EXPECTED_PROFILE_SHA256 = (
    "6a064762b4edde3448b25e5b74384708745793acc863a8adfbfad40fc7651394"
)
_DATASET_NAMESPACE = UUID("38ea2978-72d8-5782-8357-6e9d4084433b")
_MODEL_NAMESPACE = UUID("d9521184-b019-51ea-9a22-0dd80ad82cab")
_OBJECT_NAMESPACE = UUID("f04a59c0-2c92-59bd-9308-d2a3ed1a3066")
_FORECAST_RUN_NAMESPACE = UUID("a19e6794-d21c-5b71-8118-d7f428a2cc31")
_FORECAST_RESULT_NAMESPACE = UUID("91bd01db-d727-5212-a5e5-728a4cbb23dc")


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise P6GovernanceError("FAIL_CLOSED_P6_AUTHORITY_REQUIRED", field)
    return {str(key): item for key, item in value.items()}


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise P6GovernanceError("FAIL_CLOSED_P6_AUTHORITY_REQUIRED", field)
    return value


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise P6GovernanceError("FAIL_CLOSED_P6_AUTHORITY_REQUIRED", field)
    return value


def _finite(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise P6GovernanceError("FAIL_CLOSED_P6_UNCERTAINTY_REQUIRED", field)
    result = float(value)
    if not math.isfinite(result):
        raise P6GovernanceError("FAIL_CLOSED_P6_UNCERTAINTY_REQUIRED", field)
    return result


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
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            f"canonical json: {type(exc).__name__}",
        ) from exc


def _float_hex(value: float) -> str:
    if not math.isfinite(value):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_UNCERTAINTY_REQUIRED",
            "non-finite computed float",
        )
    return struct.pack(">d", value).hex()


def _condition(estimate: P3CapabilityEstimate) -> tuple[int, str]:
    condition = dict(estimate.condition_point)
    if set(condition) != {"session_order", "reference_condition_id"}:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            "P3 estimate condition_point fields",
        )
    session_order = condition.get("session_order")
    reference = condition.get("reference_condition_id")
    if (
        isinstance(session_order, bool)
        or not isinstance(session_order, int)
        or session_order < 0
    ):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            "condition_point.session_order",
        )
    if not isinstance(reference, str):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            "condition_point.reference_condition_id",
        )
    return session_order, reference


@dataclass(frozen=True, slots=True)
class P6ForecastExecutionProfile:
    profile_id: str
    profile_version: str
    profile_sha256: str
    model_spec_id: str
    model_spec_version: str
    plugin_name: str
    plugin_version: str
    target_code: str
    required_claim_level: str
    required_p4_approval_state: str
    minimum_total_points: int
    training_prefix_min_points: int
    training_prefix_max_points: int
    final_refit_max_points: int
    calibration_profile: str
    applicability_states: tuple[str, ...]
    applicability_profile_ref: str
    uncertainty_profile_ref: str
    horizon_type: str
    horizon_steps: int

    @classmethod
    def from_canonical(
        cls,
        loader: CanonicalArtifactLoader | None = None,
    ) -> P6ForecastExecutionProfile:
        canonical = loader or CanonicalArtifactLoader()
        try:
            artifact = canonical.load(
                _PROFILE_ARTIFACT_ID,
                expectation=ArtifactExpectation(
                    version="1.0.0",
                    schema_version="1.6.0",
                    required_top_level_keys=(
                        "runtime_binding",
                        "scope",
                        "source_eligibility_contract",
                        "ordering_contract",
                        "arithmetic_contract",
                        "training_validation_contract",
                        "uncertainty_calibration_contract",
                        "applicability_contract",
                        "forecast_contract",
                        "safety_boundary",
                        "contract_hashes",
                    ),
                ),
            )
        except Exception as exc:
            if isinstance(exc, P6GovernanceError):
                raise
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_MODEL_PROFILE_REQUIRED",
                str(exc),
            ) from exc
        root = dict(artifact.payload)
        runtime = _mapping(root["runtime_binding"], field="runtime_binding")
        scope = _mapping(root["scope"], field="scope")
        source = _mapping(
            root["source_eligibility_contract"],
            field="source_eligibility_contract",
        )
        ordering = _mapping(root["ordering_contract"], field="ordering_contract")
        arithmetic = _mapping(root["arithmetic_contract"], field="arithmetic_contract")
        validation = _mapping(
            root["training_validation_contract"],
            field="training_validation_contract",
        )
        uncertainty = _mapping(
            root["uncertainty_calibration_contract"],
            field="uncertainty_calibration_contract",
        )
        applicability = _mapping(
            root["applicability_contract"],
            field="applicability_contract",
        )
        forecast = _mapping(root["forecast_contract"], field="forecast_contract")
        safety = _mapping(root["safety_boundary"], field="safety_boundary")
        hashes = _mapping(root["contract_hashes"], field="contract_hashes")
        states_raw = applicability.get("states")
        if not isinstance(states_raw, list) or not all(
            isinstance(item, str) and item for item in states_raw
        ):
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_MODEL_PROFILE_REQUIRED",
                "applicability states",
            )
        states = tuple(cast(list[str], states_raw))
        if (
            artifact.sha256 != _EXPECTED_PROFILE_SHA256
            or root.get("profile_id") != "P6_P3_CAPABILITY_OLS_MAD_FORECAST"
            or root.get("version") != "1.0.0"
            or scope.get("domain") != "TRAINING_EVALUATION"
            or scope.get("target_kind")
            != "P3_REFERENCE_CONDITION_CAPABILITY_ESTIMATE"
            or scope.get("p4_context_required_for_every_training_row") is not True
            or source.get("p3_required_validity_domain_status") != "IN_DOMAIN"
            or source.get("p4_required_approval_state") != "APPROVED"
            or arithmetic.get("estimator") != "ORDINARY_LEAST_SQUARES"
            or arithmetic.get("residual_statistic")
            != "UNSCALED_MEDIAN_ABSOLUTE_DEVIATION"
            or arithmetic.get("no_rng") is not True
            or validation.get("strategy")
            != "TEMPORAL_LAST_POINT_HOLDOUT_THEN_FINAL_REFIT"
            or validation.get("holdout_count") != 1
            or validation.get("accuracy_threshold_or_multiplier") is not None
            or forecast.get("horizon_type") != "NEXT_SESSION_ORDER"
            or forecast.get("horizon_steps") != 1
            or forecast.get("multi_step_recursive_forecast_forbidden") is not True
            or safety.get("operational_or_tactical_optimization_forbidden")
            is not True
            or safety.get("weapon_or_targeting_recommendation_forbidden") is not True
        ):
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_MODEL_PROFILE_REQUIRED",
                "protected-main P6 execution profile contract drift",
            )
        final_window = _text(
            ordering.get("final_refit_window_selection"),
            field="ordering.final_refit_window_selection",
        )
        if "LAST_UP_TO_5" not in final_window:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_MODEL_PROFILE_REQUIRED",
                "final refit window drift",
            )
        app_hash = _text(
            hashes.get("applicability_contract_sha256"),
            field="contract_hashes.applicability_contract_sha256",
        )
        uncertainty_hash = _text(
            hashes.get("uncertainty_calibration_contract_sha256"),
            field="contract_hashes.uncertainty_calibration_contract_sha256",
        )
        return cls(
            profile_id=_text(root.get("profile_id"), field="profile_id"),
            profile_version=_text(root.get("version"), field="version"),
            profile_sha256=artifact.sha256,
            model_spec_id=_text(
                runtime.get("model_spec_id"),
                field="runtime.model_spec_id",
            ),
            model_spec_version=_text(
                runtime.get("model_spec_version"),
                field="runtime.model_spec_version",
            ),
            plugin_name=_text(
                runtime.get("plugin_name"),
                field="runtime.plugin_name",
            ),
            plugin_version=_text(
                runtime.get("plugin_version"),
                field="runtime.plugin_version",
            ),
            target_code=_text(scope.get("target_kind"), field="scope.target_kind"),
            required_claim_level=_text(
                source.get("p3_required_claim_level"),
                field="source.p3_required_claim_level",
            ),
            required_p4_approval_state=_text(
                source.get("p4_required_approval_state"),
                field="source.p4_required_approval_state",
            ),
            minimum_total_points=_integer(
                validation.get("minimum_total_eligible_points"),
                field="validation.minimum_total_eligible_points",
            ),
            training_prefix_min_points=_integer(
                validation.get("training_prefix_min_points"),
                field="validation.training_prefix_min_points",
            ),
            training_prefix_max_points=_integer(
                validation.get("training_prefix_max_points"),
                field="validation.training_prefix_max_points",
            ),
            final_refit_max_points=5,
            calibration_profile=_text(
                uncertainty.get("calibration_profile"),
                field="uncertainty.calibration_profile",
            ),
            applicability_states=states,
            applicability_profile_ref=(
                f"{root['profile_id']}:{root['version']}:APPLICABILITY:{app_hash}"
            ),
            uncertainty_profile_ref=(
                f"{root['profile_id']}:{root['version']}:UNCERTAINTY:"
                f"{uncertainty_hash}"
            ),
            horizon_type=_text(
                forecast.get("horizon_type"),
                field="forecast.horizon_type",
            ),
            horizon_steps=_integer(
                forecast.get("horizon_steps"),
                field="forecast.horizon_steps",
            ),
        )


@dataclass(frozen=True, slots=True)
class P6CapabilityTrainingRow:
    estimate: P3CapabilityEstimate
    p4_revision: P4AssessmentRevision
    aircraft_id: str
    configuration_snapshot_id: str
    session_order_assignment_id: str
    session_order: int


@dataclass(frozen=True, slots=True)
class P6ApplicabilityEvidence:
    applicability_evidence_id: str
    profile_id: str
    profile_version: str
    status: str
    reason_codes: tuple[str, ...]
    eligible_p3_estimate_ids: tuple[str, ...]
    excluded_p3_estimate_ids: tuple[str, ...]
    domain: Mapping[str, object]
    as_of_utc: str
    data_hash: str


@dataclass(frozen=True, slots=True)
class P6ModelDatasetSnapshot:
    dataset_snapshot_id: str
    snapshot_type: str
    row_ids: tuple[str, ...]
    p3_estimate_ids: tuple[str, ...]
    p4_revision_ids: tuple[str, ...]
    as_of_utc: str
    data_hash: str
    frozen: bool = True

    def projection(self) -> dict[str, object]:
        return {
            "dataset_snapshot_id": self.dataset_snapshot_id,
            "snapshot_type": self.snapshot_type,
            "row_ids": list(self.row_ids),
            "p3_estimate_ids": list(self.p3_estimate_ids),
            "p4_revision_ids": list(self.p4_revision_ids),
            "as_of_utc": self.as_of_utc,
            "data_hash": self.data_hash,
            "frozen": self.frozen,
        }


@dataclass(frozen=True, slots=True)
class P6ModelDatasetBundle:
    applicability: P6ApplicabilityEvidence
    training: P6ModelDatasetSnapshot
    validation: P6ModelDatasetSnapshot
    eligible_rows: tuple[P6CapabilityTrainingRow, ...]
    training_rows: tuple[P6CapabilityTrainingRow, ...]
    validation_row: P6CapabilityTrainingRow
    final_refit_rows: tuple[P6CapabilityTrainingRow, ...]


@dataclass(frozen=True, slots=True)
class P6UncertaintyCalibrationEvidence:
    calibration_evidence_id: str
    profile_ref: str
    p3_input_half_width_max: float
    holdout_absolute_error: float
    final_refit_residual_mad: float
    half_width: float
    status: str
    data_hash: str

    def projection(self) -> dict[str, object]:
        return {
            "calibration_evidence_id": self.calibration_evidence_id,
            "profile_ref": self.profile_ref,
            "p3_input_half_width_max": self.p3_input_half_width_max,
            "holdout_absolute_error": self.holdout_absolute_error,
            "final_refit_residual_mad": self.final_refit_residual_mad,
            "half_width": self.half_width,
            "status": self.status,
            "data_hash": self.data_hash,
        }


@dataclass(frozen=True, slots=True)
class P6ModelRevision:
    capability_model_id: str
    model_spec_id: str
    model_spec_version: str
    subject_type: str
    subject_id: str
    capability_type: str
    training_dataset_snapshot_id: str
    validation_dataset_snapshot_id: str
    plugin_name: str
    plugin_version: str
    model_artifact_uri: str
    model_artifact_hash: str
    model_object_ref_id: str
    validity_domain: Mapping[str, object]
    validation_metrics: Mapping[str, object]
    applicability_profile_ref: str
    uncertainty_profile_ref: str
    status: str
    trained_at: str
    published_at: str | None
    supersedes_model_id: str | None

    def projection(self) -> dict[str, object]:
        return {
            "capability_model_id": self.capability_model_id,
            "model_spec_id": self.model_spec_id,
            "model_spec_version": self.model_spec_version,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "capability_type": self.capability_type,
            "training_dataset_snapshot_id": self.training_dataset_snapshot_id,
            "validation_dataset_snapshot_id": self.validation_dataset_snapshot_id,
            "plugin_name": self.plugin_name,
            "plugin_version": self.plugin_version,
            "model_artifact_uri": self.model_artifact_uri,
            "model_artifact_hash": self.model_artifact_hash,
            "model_object_ref_id": self.model_object_ref_id,
            "validity_domain": dict(self.validity_domain),
            "validation_metrics": dict(self.validation_metrics),
            "applicability_profile_ref": self.applicability_profile_ref,
            "uncertainty_profile_ref": self.uncertainty_profile_ref,
            "status": self.status,
            "trained_at": self.trained_at,
            "published_at": self.published_at,
            "supersedes_model_id": self.supersedes_model_id,
        }


@dataclass(frozen=True, slots=True)
class P6ManagedModelObject:
    object_ref_id: str
    managed_uri: str
    artifact_sha256: str
    sealed: bool
    gc_state: str
    deleted_at: str | None
    sealed_at_utc: str


@dataclass(frozen=True, slots=True)
class P6ModelBuild:
    model: P6ModelRevision
    artifact: Mapping[str, object]
    artifact_bytes: bytes
    datasets: P6ModelDatasetBundle
    applicability: P6ApplicabilityEvidence
    uncertainty: P6UncertaintyCalibrationEvidence
    intercept: float
    slope: float
    session_order_origin: int
    target_session_order: int
    fit_row_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class P6ForecastRevision:
    forecast_result_id: str
    forecast_identity: str
    forecast_run_id: str
    forecast_request_id: str
    target_code: str
    target_time: str | None
    target_session_order: int | None
    distribution: Mapping[str, object]
    threshold_probabilities: Mapping[str, object]
    applicability_status: str
    uncertainty: Mapping[str, object]
    status: str
    factual_source_refs: tuple[str, ...]
    model_revision_id: str
    model_artifact_hash: str
    as_of_utc: str
    forecast_origin_utc: str
    published_at_utc: str
    supersedes_forecast_result_id: str | None
    logical_content_hash: str

    def projection(self) -> dict[str, object]:
        return {
            "forecast_result_id": self.forecast_result_id,
            "forecast_run_id": self.forecast_run_id,
            "target_code": self.target_code,
            "target_time": self.target_time,
            "distribution": dict(self.distribution),
            "threshold_probabilities": dict(self.threshold_probabilities),
            "applicability_status": self.applicability_status,
            "uncertainty": dict(self.uncertainty),
            "status": self.status,
            "factual_source_refs": list(self.factual_source_refs),
            "model_revision_id": self.model_revision_id,
            "as_of_utc": self.as_of_utc,
            "logical_content_hash": self.logical_content_hash,
        }


def _row_projection(
    row: P6CapabilityTrainingRow,
    *,
    policy: P6AuthorityPolicy,
    profile: P6ForecastExecutionProfile,
    as_of_utc: str,
) -> tuple[dict[str, object], bool]:
    exact_uuid(row.aircraft_id, field="row.aircraft_id", policy=policy)
    exact_uuid(
        row.configuration_snapshot_id,
        field="row.configuration_snapshot_id",
        policy=policy,
    )
    exact_uuid(
        row.session_order_assignment_id,
        field="row.session_order_assignment_id",
        policy=policy,
    )
    exact_uuid(row.estimate.estimate_id, field="estimate_id", policy=policy)
    exact_uuid(
        row.estimate.twin_revision_id,
        field="estimate.twin_revision_id",
        policy=policy,
    )
    exact_uuid(
        row.p4_revision.actor_assessment_id,
        field="p4.actor_assessment_id",
        policy=policy,
    )
    exact_uuid(
        row.p4_revision.session_id,
        field="p4.session_id",
        policy=policy,
    )
    if row.p4_revision.aircraft_id is None:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
            "P4 aircraft_id is required",
        )
    exact_uuid(
        row.p4_revision.aircraft_id,
        field="p4.aircraft_id",
        policy=policy,
    )
    session_order, reference_id = _condition(row.estimate)
    exact_uuid(
        reference_id,
        field="estimate.reference_condition_id",
        policy=policy,
    )
    if row.session_order != session_order:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            "P4/P3 session_order assignment mismatch",
        )
    if (
        row.p4_revision.approval_state != profile.required_p4_approval_state
        or row.p4_revision.status != profile.required_p4_approval_state
    ):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
            row.p4_revision.actor_assessment_id,
        )
    if (
        row.p4_revision.p3_estimate_id != row.estimate.estimate_id
        or row.p4_revision.aircraft_id != row.aircraft_id
        or row.p4_revision.twin_revision_id != row.estimate.twin_revision_id
        or row.p4_revision.p3_claim_level != row.estimate.claim_level
        or row.p4_revision.p3_validity_status
        != row.estimate.validity_domain_status
        or row.p4_revision.p3_as_of_utc != row.estimate.as_of_time
    ):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
            "P4 context does not bind exact P3 estimate",
        )
    if row.p4_revision.score is not None or row.p4_revision.grade is not None:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_P1_P5_MUTATION_FORBIDDEN",
            "P4 score/grade must remain evidence-only",
        )
    if row.estimate.claim_level != profile.required_claim_level:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_MODEL_PROFILE_REQUIRED",
            f"P3 claim={row.estimate.claim_level!r}",
        )
    cutoff = utc(as_of_utc, field="as_of_utc")
    estimate_created = utc(row.estimate.created_at, field="estimate.created_at")
    estimate_as_of = utc(row.estimate.as_of_time, field="estimate.as_of_time")
    p4_created = utc(row.p4_revision.created_at_utc, field="p4.created_at_utc")
    if (
        estimate_created > cutoff
        or estimate_as_of > cutoff
        or p4_created > cutoff
        or estimate_created > p4_created
    ):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_FUTURE_INFORMATION",
            row.estimate.estimate_id,
        )
    if (
        row.estimate.validity_domain_status != "IN_DOMAIN"
        or row.estimate.value is None
    ):
        payload = {
            "p3_estimate_id": row.estimate.estimate_id,
            "p4_assessment_revision_id": row.p4_revision.actor_assessment_id,
            "session_order_assignment_id": row.session_order_assignment_id,
            "session_order": row.session_order,
            "aircraft_id": row.aircraft_id,
            "twin_revision_id": row.estimate.twin_revision_id,
            "capability_type": row.estimate.capability_type,
            "reference_condition_id": reference_id,
            "unit": row.estimate.unit,
            "configuration_snapshot_id": row.configuration_snapshot_id,
            "value": None,
            "uncertainty_lower": None,
            "uncertainty_upper": None,
            "p3_as_of_utc": row.estimate.as_of_time,
            "p3_created_at_utc": row.estimate.created_at,
            "p4_created_at_utc": row.p4_revision.created_at_utc,
        }
        return payload, False
    value = _finite(row.estimate.value, field="estimate.value")
    uncertainty = dict(row.estimate.uncertainty)
    lower = _finite(uncertainty.get("lower"), field="estimate.uncertainty.lower")
    upper = _finite(uncertainty.get("upper"), field="estimate.uncertainty.upper")
    if lower > value or upper < value:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_UNCERTAINTY_REQUIRED",
            "P3 uncertainty interval does not contain value",
        )
    if (
        row.p4_revision.uncertainty_lower != lower
        or row.p4_revision.uncertainty_upper != upper
    ):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
            "P4 uncertainty does not preserve exact P3 uncertainty",
        )
    payload = {
        "p3_estimate_id": row.estimate.estimate_id,
        "p4_assessment_revision_id": row.p4_revision.actor_assessment_id,
        "session_order_assignment_id": row.session_order_assignment_id,
        "session_order": row.session_order,
        "aircraft_id": row.aircraft_id,
        "twin_revision_id": row.estimate.twin_revision_id,
        "capability_type": row.estimate.capability_type,
        "reference_condition_id": reference_id,
        "unit": row.estimate.unit,
        "configuration_snapshot_id": row.configuration_snapshot_id,
        "value": value,
        "uncertainty_lower": lower,
        "uncertainty_upper": upper,
        "p3_as_of_utc": row.estimate.as_of_time,
        "p3_created_at_utc": row.estimate.created_at,
        "p4_created_at_utc": row.p4_revision.created_at_utc,
    }
    return payload, True


def _row_id(payload: Mapping[str, object]) -> str:
    return f"P6_MODEL_ROW_SHA256:{canonical_hash(dict(payload))}"


def p6_capability_training_row_id(
    row: P6CapabilityTrainingRow,
    *,
    as_of_utc: str,
    policy: P6AuthorityPolicy | None = None,
    profile: P6ForecastExecutionProfile | None = None,
) -> str:
    """Return the canonical row identity without rebuilding a model product."""
    p = policy or P6AuthorityPolicy.from_canonical()
    q = profile or P6ForecastExecutionProfile.from_canonical()
    payload, _ = _row_projection(
        row,
        policy=p,
        profile=q,
        as_of_utc=as_of_utc,
    )
    return _row_id(payload)


def assess_p6_training_applicability(
    rows: Sequence[P6CapabilityTrainingRow],
    *,
    as_of_utc: str,
    policy: P6AuthorityPolicy | None = None,
    profile: P6ForecastExecutionProfile | None = None,
) -> P6ApplicabilityEvidence:
    p = policy or P6AuthorityPolicy.from_canonical()
    q = profile or P6ForecastExecutionProfile.from_canonical()
    utc(as_of_utc, field="as_of_utc")
    normalized: list[tuple[P6CapabilityTrainingRow, dict[str, object]]] = []
    excluded: list[str] = []
    all_row_ids: list[str] = []
    for row in rows:
        payload, eligible = _row_projection(
            row,
            policy=p,
            profile=q,
            as_of_utc=as_of_utc,
        )
        all_row_ids.append(_row_id(payload))
        if eligible:
            normalized.append((row, payload))
        else:
            excluded.append(row.estimate.estimate_id)
    normalized.sort(
        key=lambda item: (
            cast(int, item[1]["session_order"]),
            cast(str, item[1]["p3_estimate_id"]),
        )
    )
    reason_codes: list[str] = []
    status = "APPLICABLE"
    domain: dict[str, object] = {}
    if normalized:
        first = normalized[0][1]
        domain = {
            "aircraft_id": first["aircraft_id"],
            "capability_type": first["capability_type"],
            "reference_condition_id": first["reference_condition_id"],
            "unit": first["unit"],
            "configuration_snapshot_id": first["configuration_snapshot_id"],
        }
        for _, payload in normalized[1:]:
            for key, expected in domain.items():
                if payload[key] != expected:
                    status = "OUT_OF_DOMAIN"
                    reason_codes.append(f"DOMAIN_DRIFT:{key}")
        session_orders = [cast(int, item[1]["session_order"]) for item in normalized]
        if len(set(session_orders)) != len(session_orders):
            status = "NOT_IDENTIFIABLE"
            reason_codes.append("DUPLICATE_SESSION_ORDER")
    if len(normalized) < q.minimum_total_points:
        if status == "APPLICABLE":
            status = "INSUFFICIENT_EVIDENCE"
        reason_codes.append("MINIMUM_ELIGIBLE_POINTS_NOT_MET")
    if excluded:
        reason_codes.extend(
            f"ROW_INELIGIBLE_P3_OUT_OF_DOMAIN:{estimate_id}"
            for estimate_id in sorted(excluded)
        )
    if status not in q.applicability_states:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_APPLICABILITY_REQUIRED",
            f"status={status!r}",
        )
    eligible_ids = tuple(item[0].estimate.estimate_id for item in normalized)
    excluded_ids = tuple(sorted(excluded))
    material = {
        "profile_id": q.profile_id,
        "profile_version": q.profile_version,
        "profile_sha256": q.profile_sha256,
        "status": status,
        "reason_codes": sorted(set(reason_codes)),
        "eligible_p3_estimate_ids": list(eligible_ids),
        "excluded_p3_estimate_ids": list(excluded_ids),
        "domain": domain,
        "input_row_ids": sorted(all_row_ids),
        "as_of_utc": as_of_utc,
    }
    digest = canonical_hash(material)
    return P6ApplicabilityEvidence(
        applicability_evidence_id=f"P6_APPLICABILITY_SHA256:{digest}",
        profile_id=q.profile_id,
        profile_version=q.profile_version,
        status=status,
        reason_codes=tuple(sorted(set(reason_codes))),
        eligible_p3_estimate_ids=eligible_ids,
        excluded_p3_estimate_ids=excluded_ids,
        domain=domain,
        as_of_utc=as_of_utc,
        data_hash=digest,
    )


def _dataset_snapshot(
    *,
    snapshot_type: str,
    rows: Sequence[P6CapabilityTrainingRow],
    as_of_utc: str,
    policy: P6AuthorityPolicy,
    profile: P6ForecastExecutionProfile,
) -> P6ModelDatasetSnapshot:
    row_payloads = [
        _row_projection(
            row,
            policy=policy,
            profile=profile,
            as_of_utc=as_of_utc,
        )[0]
        for row in rows
    ]
    row_ids = tuple(_row_id(payload) for payload in row_payloads)
    material = {
        "profile_id": profile.profile_id,
        "profile_version": profile.profile_version,
        "profile_sha256": profile.profile_sha256,
        "snapshot_type": snapshot_type,
        "row_ids": list(row_ids),
        "p3_estimate_ids": [row.estimate.estimate_id for row in rows],
        "p4_revision_ids": [row.p4_revision.actor_assessment_id for row in rows],
        "as_of_utc": as_of_utc,
        "frozen": True,
    }
    digest = canonical_hash(material)
    return P6ModelDatasetSnapshot(
        dataset_snapshot_id=str(uuid5(_DATASET_NAMESPACE, digest)),
        snapshot_type=snapshot_type,
        row_ids=row_ids,
        p3_estimate_ids=tuple(row.estimate.estimate_id for row in rows),
        p4_revision_ids=tuple(
            row.p4_revision.actor_assessment_id for row in rows
        ),
        as_of_utc=as_of_utc,
        data_hash=digest,
    )


def materialize_p6_model_datasets(
    rows: Sequence[P6CapabilityTrainingRow],
    *,
    as_of_utc: str,
    policy: P6AuthorityPolicy | None = None,
    profile: P6ForecastExecutionProfile | None = None,
) -> P6ModelDatasetBundle:
    p = policy or P6AuthorityPolicy.from_canonical()
    q = profile or P6ForecastExecutionProfile.from_canonical()
    applicability = assess_p6_training_applicability(
        rows,
        as_of_utc=as_of_utc,
        policy=p,
        profile=q,
    )
    if applicability.status != "APPLICABLE":
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_APPLICABILITY_REQUIRED",
            applicability.status,
        )
    eligible_set = set(applicability.eligible_p3_estimate_ids)
    eligible = tuple(
        sorted(
            (row for row in rows if row.estimate.estimate_id in eligible_set),
            key=lambda item: (item.session_order, item.estimate.estimate_id),
        )
    )
    validation_row = eligible[-1]
    training_rows = eligible[:-1][-q.training_prefix_max_points :]
    if len(training_rows) < q.training_prefix_min_points:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_TRAINING_VALIDATION_LEAKAGE",
            "training prefix minimum not met",
        )
    if {
        row.estimate.estimate_id for row in training_rows
    } & {validation_row.estimate.estimate_id}:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_TRAINING_VALIDATION_LEAKAGE",
            "training/validation estimate overlap",
        )
    final_refit = eligible[-q.final_refit_max_points :]
    training = _dataset_snapshot(
        snapshot_type="P6_MODEL_TRAINING",
        rows=training_rows,
        as_of_utc=as_of_utc,
        policy=p,
        profile=q,
    )
    validation = _dataset_snapshot(
        snapshot_type="P6_MODEL_VALIDATION",
        rows=(validation_row,),
        as_of_utc=as_of_utc,
        policy=p,
        profile=q,
    )
    return P6ModelDatasetBundle(
        applicability=applicability,
        training=training,
        validation=validation,
        eligible_rows=eligible,
        training_rows=training_rows,
        validation_row=validation_row,
        final_refit_rows=final_refit,
    )


def _ols(
    rows: Sequence[P6CapabilityTrainingRow],
) -> tuple[int, float, float]:
    if len(rows) < 2:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_MODEL_PROFILE_REQUIRED",
            "OLS requires at least two rows",
        )
    origin = rows[0].session_order
    xs = [row.session_order - origin for row in rows]
    ys = [
        _finite(row.estimate.value, field="estimate.value")
        for row in rows
    ]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    if denominator == 0:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_APPLICABILITY_REQUIRED",
            "zero OLS denominator",
        )
    slope = sum(
        (x_value - mean_x) * (y_value - mean_y)
        for x_value, y_value in zip(xs, ys, strict=True)
    ) / denominator
    intercept = mean_y - slope * mean_x
    return origin, float(intercept), float(slope)


def _residual_mad(
    rows: Sequence[P6CapabilityTrainingRow],
    *,
    origin: int,
    intercept: float,
    slope: float,
) -> float:
    residuals = [
        _finite(row.estimate.value, field="estimate.value")
        - (intercept + slope * (row.session_order - origin))
        for row in rows
    ]
    center = float(statistics.median(residuals))
    return float(statistics.median(abs(value - center) for value in residuals))


def _p3_half_width(row: P6CapabilityTrainingRow) -> float:
    value = _finite(row.estimate.value, field="estimate.value")
    uncertainty = dict(row.estimate.uncertainty)
    lower = _finite(uncertainty.get("lower"), field="uncertainty.lower")
    upper = _finite(uncertainty.get("upper"), field="uncertainty.upper")
    return max(value - lower, upper - value)


def execute_p6_model_training(
    rows: Sequence[P6CapabilityTrainingRow],
    *,
    as_of_utc: str,
    trained_at_utc: str,
    supersedes_model_id: str | None = None,
    policy: P6AuthorityPolicy | None = None,
    profile: P6ForecastExecutionProfile | None = None,
) -> P6ModelBuild:
    p = policy or P6AuthorityPolicy.from_canonical()
    q = profile or P6ForecastExecutionProfile.from_canonical()
    datasets = materialize_p6_model_datasets(
        rows,
        as_of_utc=as_of_utc,
        policy=p,
        profile=q,
    )
    trained = utc(trained_at_utc, field="trained_at_utc")
    cutoff = utc(as_of_utc, field="as_of_utc")
    if trained < cutoff:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_FUTURE_INFORMATION",
            "trained_at_utc precedes model knowledge cutoff",
        )
    if supersedes_model_id is not None:
        exact_uuid(
            supersedes_model_id,
            field="supersedes_model_id",
            policy=p,
        )
    holdout_origin, holdout_intercept, holdout_slope = _ols(
        datasets.training_rows
    )
    heldout = datasets.validation_row
    predicted = holdout_intercept + holdout_slope * (
        heldout.session_order - holdout_origin
    )
    observed = _finite(heldout.estimate.value, field="heldout.value")
    holdout_error = abs(predicted - observed)
    origin, intercept, slope = _ols(datasets.final_refit_rows)
    residual_mad = _residual_mad(
        datasets.final_refit_rows,
        origin=origin,
        intercept=intercept,
        slope=slope,
    )
    input_half_width = max(
        _p3_half_width(row) for row in datasets.final_refit_rows
    )
    uncertainty_half_width = max(
        input_half_width,
        holdout_error,
        residual_mad,
    )
    calibration_material = {
        "profile_ref": q.uncertainty_profile_ref,
        "training_dataset_snapshot_id": datasets.training.dataset_snapshot_id,
        "validation_dataset_snapshot_id": datasets.validation.dataset_snapshot_id,
        "p3_input_half_width_max": _float_hex(input_half_width),
        "holdout_absolute_error": _float_hex(holdout_error),
        "final_refit_residual_mad": _float_hex(residual_mad),
        "half_width": _float_hex(uncertainty_half_width),
        "status": "CALIBRATED",
    }
    calibration_hash = canonical_hash(calibration_material)
    uncertainty = P6UncertaintyCalibrationEvidence(
        calibration_evidence_id=f"P6_UNCERTAINTY_SHA256:{calibration_hash}",
        profile_ref=q.uncertainty_profile_ref,
        p3_input_half_width_max=input_half_width,
        holdout_absolute_error=holdout_error,
        final_refit_residual_mad=residual_mad,
        half_width=uncertainty_half_width,
        status="CALIBRATED",
        data_hash=calibration_hash,
    )
    domain = dict(datasets.applicability.domain)
    domain.update(
        {
            "axis": "SESSION_ORDER",
            "session_order_min": datasets.final_refit_rows[0].session_order,
            "session_order_max": datasets.final_refit_rows[-1].session_order,
            "forecast_horizon": q.horizon_type,
            "forecast_horizon_steps": q.horizon_steps,
            "extrapolation": "NEXT_SESSION_ORDER_ONLY",
        }
    )
    validation_metrics = {
        "strategy": "TEMPORAL_LAST_POINT_HOLDOUT_THEN_FINAL_REFIT",
        "status": "VALIDATED",
        "training_row_ids": list(datasets.training.row_ids),
        "validation_row_id": datasets.validation.row_ids[0],
        "holdout_predicted_value": predicted,
        "holdout_observed_value": observed,
        "holdout_absolute_error": holdout_error,
        "final_refit_residual_mad": residual_mad,
        "p3_input_half_width_max": input_half_width,
        "uncertainty_half_width": uncertainty_half_width,
        "calibration_evidence_id": uncertainty.calibration_evidence_id,
        "applicability_evidence_id": (
            datasets.applicability.applicability_evidence_id
        ),
    }
    fit_row_ids = tuple(
        _row_id(
            _row_projection(
                row,
                policy=p,
                profile=q,
                as_of_utc=as_of_utc,
            )[0]
        )
        for row in datasets.final_refit_rows
    )
    target_session_order = datasets.final_refit_rows[-1].session_order + 1
    artifact = {
        "schema": "TPAA_P6_P3_CAPABILITY_OLS_MAD_MODEL_V1",
        "profile_id": q.profile_id,
        "profile_version": q.profile_version,
        "profile_sha256": q.profile_sha256,
        "model_spec_id": q.model_spec_id,
        "model_spec_version": q.model_spec_version,
        "plugin_name": q.plugin_name,
        "plugin_version": q.plugin_version,
        "subject_type": "AIRCRAFT",
        "subject_id": domain["aircraft_id"],
        "capability_type": domain["capability_type"],
        "reference_condition_id": domain["reference_condition_id"],
        "unit": domain["unit"],
        "configuration_snapshot_id": domain["configuration_snapshot_id"],
        "training_dataset_snapshot_id": datasets.training.dataset_snapshot_id,
        "training_dataset_hash": datasets.training.data_hash,
        "validation_dataset_snapshot_id": datasets.validation.dataset_snapshot_id,
        "validation_dataset_hash": datasets.validation.data_hash,
        "fit_row_ids": list(fit_row_ids),
        "session_order_origin": origin,
        "target_session_order": target_session_order,
        "intercept": intercept,
        "slope": slope,
        "uncertainty_half_width": uncertainty_half_width,
        "validation_metrics": validation_metrics,
        "validity_domain": domain,
        "applicability_profile_ref": q.applicability_profile_ref,
        "uncertainty_profile_ref": q.uncertainty_profile_ref,
    }
    artifact_bytes = _canonical_bytes(artifact)
    artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()
    numeric_identity = {
        "intercept": _float_hex(intercept),
        "slope": _float_hex(slope),
        "uncertainty_half_width": _float_hex(uncertainty_half_width),
        "holdout_absolute_error": _float_hex(holdout_error),
        "final_refit_residual_mad": _float_hex(residual_mad),
    }
    identity_hash = canonical_hash(
        {
            "model_spec_id": q.model_spec_id,
            "model_spec_version": q.model_spec_version,
            "subject_id": domain["aircraft_id"],
            "training_dataset_snapshot_id": datasets.training.dataset_snapshot_id,
            "validation_dataset_snapshot_id": (
                datasets.validation.dataset_snapshot_id
            ),
            "plugin_name": q.plugin_name,
            "plugin_version": q.plugin_version,
            "model_artifact_hash": artifact_hash,
            "numeric_identity": numeric_identity,
        }
    )
    model_id = str(uuid5(_MODEL_NAMESPACE, identity_hash))
    if supersedes_model_id == model_id:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            "model cannot supersede itself",
        )
    model_uri = f"tpaa-object://p6-capability/models/{model_id}.json"
    object_ref_id = str(uuid5(_OBJECT_NAMESPACE, artifact_hash))
    model = P6ModelRevision(
        capability_model_id=model_id,
        model_spec_id=q.model_spec_id,
        model_spec_version=q.model_spec_version,
        subject_type="AIRCRAFT",
        subject_id=cast(str, domain["aircraft_id"]),
        capability_type=cast(str, domain["capability_type"]),
        training_dataset_snapshot_id=datasets.training.dataset_snapshot_id,
        validation_dataset_snapshot_id=datasets.validation.dataset_snapshot_id,
        plugin_name=q.plugin_name,
        plugin_version=q.plugin_version,
        model_artifact_uri=model_uri,
        model_artifact_hash=artifact_hash,
        model_object_ref_id=object_ref_id,
        validity_domain=domain,
        validation_metrics=validation_metrics,
        applicability_profile_ref=q.applicability_profile_ref,
        uncertainty_profile_ref=q.uncertainty_profile_ref,
        status="VALIDATED",
        trained_at=trained_at_utc,
        published_at=None,
        supersedes_model_id=supersedes_model_id,
    )
    return P6ModelBuild(
        model=model,
        artifact=artifact,
        artifact_bytes=artifact_bytes,
        datasets=datasets,
        applicability=datasets.applicability,
        uncertainty=uncertainty,
        intercept=intercept,
        slope=slope,
        session_order_origin=origin,
        target_session_order=target_session_order,
        fit_row_ids=fit_row_ids,
    )


def validate_p6_managed_model_object(
    model: P6ModelRevision,
    value: P6ManagedModelObject,
    *,
    as_of_utc: str | None = None,
    policy: P6AuthorityPolicy | None = None,
) -> P6ManagedModelObject:
    p = policy or P6AuthorityPolicy.from_canonical()
    exact_uuid(value.object_ref_id, field="object_ref_id", policy=p)
    exact_hash64(value.artifact_sha256, field="artifact_sha256")
    exact_text(value.managed_uri, field="managed_uri", policy=p)
    if value.managed_uri.startswith("file://"):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_MANAGED_OBJECT_REQUIRED",
            "file URI is not a sealed managed object",
        )
    if value.artifact_sha256 != model.model_artifact_hash:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_MODEL_HASH_MISMATCH",
            model.capability_model_id,
        )
    if (
        value.object_ref_id != model.model_object_ref_id
        or value.managed_uri != model.model_artifact_uri
        or not value.sealed
        or value.gc_state != "ACTIVE"
        or value.deleted_at is not None
    ):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_MANAGED_OBJECT_REQUIRED",
            model.capability_model_id,
        )
    sealed_at = utc(value.sealed_at_utc, field="sealed_at_utc")
    if as_of_utc is not None and sealed_at > utc(as_of_utc, field="as_of_utc"):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_FUTURE_INFORMATION",
            value.object_ref_id,
        )
    return value


def _non_numeric_forecast(
    *,
    request: P6ForecastRequestBinding,
    input_snapshot: P6InputSnapshot,
    model: P6ModelRevision,
    applicability_status: str,
    reason_codes: Sequence[str],
    published_at_utc: str,
    target_session_order: int | None,
    supersedes_forecast_result_id: str | None,
    policy: P6AuthorityPolicy,
) -> P6ForecastRevision:
    if applicability_status not in {
        "OUT_OF_DOMAIN",
        "INSUFFICIENT_EVIDENCE",
        "NOT_IDENTIFIABLE",
    }:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_APPLICABILITY_REQUIRED",
            applicability_status,
        )
    reasons = tuple(sorted(set(reason_codes)))
    distribution: dict[str, object] = {
        "projection_class": "P6_PROJECTION",
        "point": None,
        "lower": None,
        "upper": None,
        "unit": model.validity_domain.get("unit"),
        "target_session_order": target_session_order,
    }
    uncertainty: dict[str, object] = {
        "status": "UNAVAILABLE",
        "half_width": None,
        "reason_codes": list(reasons),
        "profile_ref": model.uncertainty_profile_ref,
    }
    return _forecast_revision(
        request=request,
        input_snapshot=input_snapshot,
        model=model,
        applicability_status=applicability_status,
        distribution=distribution,
        uncertainty=uncertainty,
        published_at_utc=published_at_utc,
        target_session_order=target_session_order,
        supersedes_forecast_result_id=supersedes_forecast_result_id,
        status="NON_NUMERIC",
        policy=policy,
    )


def _forecast_revision(
    *,
    request: P6ForecastRequestBinding,
    input_snapshot: P6InputSnapshot,
    model: P6ModelRevision,
    applicability_status: str,
    distribution: Mapping[str, object],
    uncertainty: Mapping[str, object],
    published_at_utc: str,
    target_session_order: int | None,
    supersedes_forecast_result_id: str | None,
    status: str,
    policy: P6AuthorityPolicy,
) -> P6ForecastRevision:
    published = utc(published_at_utc, field="published_at_utc")
    if published < utc(request.as_of_utc, field="request.as_of_utc"):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_FUTURE_INFORMATION",
            "forecast published before request as_of",
        )
    if supersedes_forecast_result_id is not None:
        exact_uuid(
            supersedes_forecast_result_id,
            field="supersedes_forecast_result_id",
            policy=policy,
        )
    run_hash = canonical_hash(
        {
            "forecast_request_id": request.forecast_request_id,
            "capability_model_id": model.capability_model_id,
            "model_artifact_hash": model.model_artifact_hash,
            "input_snapshot_id": input_snapshot.input_snapshot_id,
        }
    )
    forecast_run_id = str(uuid5(_FORECAST_RUN_NAMESPACE, run_hash))
    result_material = {
        "forecast_request_id": request.forecast_request_id,
        "forecast_run_id": forecast_run_id,
        "model_revision_id": model.capability_model_id,
        "model_artifact_hash": model.model_artifact_hash,
        "target_code": request.target_code,
        "target_time": None,
        "target_session_order": target_session_order,
        "distribution": dict(distribution),
        "threshold_probabilities": {},
        "applicability_status": applicability_status,
        "uncertainty": dict(uncertainty),
        "factual_source_refs": list(input_snapshot.factual_source_refs),
        "as_of_utc": request.as_of_utc,
        "forecast_origin_utc": request.forecast_origin_utc,
        "supersedes_forecast_result_id": supersedes_forecast_result_id,
    }
    digest = canonical_hash(result_material)
    result_id = str(uuid5(_FORECAST_RESULT_NAMESPACE, digest))
    if supersedes_forecast_result_id == result_id:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            "forecast cannot supersede itself",
        )
    return P6ForecastRevision(
        forecast_result_id=result_id,
        forecast_identity=f"P6_FORECAST_RESULT_SHA256:{digest}",
        forecast_run_id=forecast_run_id,
        forecast_request_id=request.forecast_request_id,
        target_code=request.target_code,
        target_time=None,
        target_session_order=target_session_order,
        distribution=dict(distribution),
        threshold_probabilities={},
        applicability_status=applicability_status,
        uncertainty=dict(uncertainty),
        status=status,
        factual_source_refs=input_snapshot.factual_source_refs,
        model_revision_id=model.capability_model_id,
        model_artifact_hash=model.model_artifact_hash,
        as_of_utc=request.as_of_utc,
        forecast_origin_utc=request.forecast_origin_utc,
        published_at_utc=published_at_utc,
        supersedes_forecast_result_id=supersedes_forecast_result_id,
        logical_content_hash=digest,
    )


def execute_p6_forecast(
    *,
    request: P6ForecastRequestBinding,
    input_snapshot: P6InputSnapshot,
    model_build: P6ModelBuild,
    managed_object: P6ManagedModelObject,
    published_at_utc: str,
    supersedes_forecast_result_id: str | None = None,
    policy: P6AuthorityPolicy | None = None,
    profile: P6ForecastExecutionProfile | None = None,
) -> P6ForecastRevision:
    p = policy or P6AuthorityPolicy.from_canonical()
    q = profile or P6ForecastExecutionProfile.from_canonical()
    assert_p6_input_snapshot_identity(input_snapshot)
    model = model_build.model
    if (
        request.input_snapshot_id != input_snapshot.input_snapshot_id
        or request.capability_model_id != model.capability_model_id
        or request.model_profile_id != q.profile_id
        or request.model_profile_version != q.profile_version
        or request.training_dataset_snapshot_id
        != model.training_dataset_snapshot_id
        or request.validation_dataset_snapshot_id
        != model.validation_dataset_snapshot_id
    ):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_MODEL_PROFILE_REQUIRED",
            "forecast request/model exact binding drift",
        )
    if model.status not in {"VALIDATED", "PUBLISHED"}:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_MODEL_PROFILE_REQUIRED",
            f"model status={model.status!r}",
        )
    validate_p6_managed_model_object(
        model,
        managed_object,
        as_of_utc=request.as_of_utc,
        policy=p,
    )
    if utc(model.trained_at, field="model.trained_at") > utc(
        request.as_of_utc,
        field="request.as_of_utc",
    ):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_FUTURE_INFORMATION",
            model.capability_model_id,
        )
    if request.subject_ref != model.subject_id:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            "request subject does not match model subject",
        )
    horizon = dict(request.horizon_spec)
    target_order_value = horizon.get("target_session_order")
    target_order = (
        target_order_value
        if isinstance(target_order_value, int)
        and not isinstance(target_order_value, bool)
        else None
    )
    if input_snapshot.availability_status != "AVAILABLE":
        mapped = {
            "OUT_OF_DOMAIN": "OUT_OF_DOMAIN",
            "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE",
            "NOT_IDENTIFIABLE": "NOT_IDENTIFIABLE",
            "UNAVAILABLE": "INSUFFICIENT_EVIDENCE",
        }.get(input_snapshot.availability_status)
        if mapped is None:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_APPLICABILITY_REQUIRED",
                input_snapshot.availability_status,
            )
        return _non_numeric_forecast(
            request=request,
            input_snapshot=input_snapshot,
            model=model,
            applicability_status=mapped,
            reason_codes=(
                f"INPUT_{input_snapshot.availability_status}",
                *input_snapshot.reason_codes,
            ),
            published_at_utc=published_at_utc,
            target_session_order=target_order,
            supersedes_forecast_result_id=supersedes_forecast_result_id,
            policy=p,
        )
    if request.target_code != q.target_code:
        return _non_numeric_forecast(
            request=request,
            input_snapshot=input_snapshot,
            model=model,
            applicability_status="OUT_OF_DOMAIN",
            reason_codes=("TARGET_CODE_OUT_OF_DOMAIN",),
            published_at_utc=published_at_utc,
            target_session_order=target_order,
            supersedes_forecast_result_id=supersedes_forecast_result_id,
            policy=p,
        )
    if (
        horizon.get("type") != q.horizon_type
        or horizon.get("steps") != q.horizon_steps
    ):
        return _non_numeric_forecast(
            request=request,
            input_snapshot=input_snapshot,
            model=model,
            applicability_status="OUT_OF_DOMAIN",
            reason_codes=("HORIZON_OUT_OF_DOMAIN",),
            published_at_utc=published_at_utc,
            target_session_order=target_order,
            supersedes_forecast_result_id=supersedes_forecast_result_id,
            policy=p,
        )
    if target_order is None:
        return _non_numeric_forecast(
            request=request,
            input_snapshot=input_snapshot,
            model=model,
            applicability_status="NOT_IDENTIFIABLE",
            reason_codes=("TARGET_SESSION_ORDER_NOT_IDENTIFIABLE",),
            published_at_utc=published_at_utc,
            target_session_order=None,
            supersedes_forecast_result_id=supersedes_forecast_result_id,
            policy=p,
        )
    if target_order != model_build.target_session_order:
        return _non_numeric_forecast(
            request=request,
            input_snapshot=input_snapshot,
            model=model,
            applicability_status="OUT_OF_DOMAIN",
            reason_codes=("TARGET_SESSION_ORDER_OUT_OF_DOMAIN",),
            published_at_utc=published_at_utc,
            target_session_order=target_order,
            supersedes_forecast_result_id=supersedes_forecast_result_id,
            policy=p,
        )
    value = model_build.intercept + model_build.slope * (
        target_order - model_build.session_order_origin
    )
    half_width = model_build.uncertainty.half_width
    value = _finite(value, field="forecast.value")
    half_width = _finite(half_width, field="forecast.uncertainty_half_width")
    distribution: dict[str, object] = {
        "projection_class": "P6_PROJECTION",
        "point": value,
        "lower": value - half_width,
        "upper": value + half_width,
        "unit": model.validity_domain["unit"],
        "target_session_order": target_order,
    }
    uncertainty: dict[str, object] = {
        "status": "CALIBRATED",
        "half_width": half_width,
        "profile_ref": model.uncertainty_profile_ref,
        "calibration_evidence_id": (
            model_build.uncertainty.calibration_evidence_id
        ),
        "components": {
            "p3_input_half_width_max": (
                model_build.uncertainty.p3_input_half_width_max
            ),
            "holdout_absolute_error": (
                model_build.uncertainty.holdout_absolute_error
            ),
            "final_refit_residual_mad": (
                model_build.uncertainty.final_refit_residual_mad
            ),
        },
    }
    return _forecast_revision(
        request=request,
        input_snapshot=input_snapshot,
        model=model,
        applicability_status="APPLICABLE",
        distribution=distribution,
        uncertainty=uncertainty,
        published_at_utc=published_at_utc,
        target_session_order=target_order,
        supersedes_forecast_result_id=supersedes_forecast_result_id,
        status="PUBLISHED_PROJECTION",
        policy=p,
    )
