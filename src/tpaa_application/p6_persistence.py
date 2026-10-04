"""PIQB B2 durable P6 substrate over adopted DB 1.8 canonical relations."""

from __future__ import annotations

import hashlib
import json
import math
import struct
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid5

from tpaa_assessment.p6_recommendation import P6RecommendationRevision
from tpaa_capability import (
    P6ApplicabilityEvidence,
    P6CapabilityTrainingRow,
    P6ContextRef,
    P6CounterfactualRequestBinding,
    P6CounterfactualRevision,
    P6FactualSourceRevision,
    P6ForecastExecutionProfile,
    P6ForecastRequestBinding,
    P6ForecastRevision,
    P6InputSnapshot,
    P6ManagedModelObject,
    P6ModelBuild,
    P6ModelDatasetBundle,
    P6ModelDatasetSnapshot,
    P6ModelRevision,
    P6P3ModelRef,
    P6UncertaintyCalibrationEvidence,
    assert_p6_input_snapshot_identity,
    assess_p6_training_applicability,
    p6_capability_training_row_id,
    validate_p6_managed_model_object,
)
from tpaa_context.p6_governance import canonical_hash
from tpaa_storage.canonical_rows import CanonicalRowRepository

from .p3_persistence import P3PersistenceRepository
from .p4_p5_persistence import P4P5PersistenceRepository

_INPUT_NAMESPACE = UUID("7256bfa5-8cb5-54c4-9174-1324fe77f4db")
_FORECAST_REQUEST_NAMESPACE = UUID("55585db6-8d47-5fcb-8b92-cfbe1b468592")
_COUNTERFACTUAL_REQUEST_NAMESPACE = UUID("3a205859-8096-5d99-bf08-1d89d16442b0")
_FORECAST_RUN_NAMESPACE = UUID("a19e6794-d21c-5b71-8118-d7f428a2cc31")
_FORECAST_RESULT_NAMESPACE = UUID("91bd01db-d727-5212-a5e5-728a4cbb23dc")
_COUNTERFACTUAL_NAMESPACE = UUID("454034a4-9098-55b4-812b-a1c83f6bea73")
_RECOMMENDATION_NAMESPACE = UUID("b0a421cb-b6bc-5659-bf37-aa298bdf360c")
_INPUT_PREFIX = "P6_INPUT_SHA256:"
_FORECAST_REQUEST_PREFIX = "P6_FORECAST_REQUEST_SHA256:"
_COUNTERFACTUAL_REQUEST_PREFIX = "P6_COUNTERFACTUAL_REQUEST_SHA256:"
_INPUT_SCHEMA = "TPAA_P6_INPUT_SNAPSHOT_MANIFEST_V1"
_MODEL_DATASET_SCHEMA = "TPAA_P6_MODEL_DATASET_MANIFEST_V1"
_COUNTERFACTUAL_SPEC_ID = "P6_COUNTERFACTUAL_PROJECTION"
_COUNTERFACTUAL_SPEC_VERSION = "1.0.0"


class P6PersistenceError(RuntimeError):
    """Fail-closed exact persistence error for P6 durable products."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


class P6ObjectStore(Protocol):
    """Minimal managed-object port required by durable P6 model persistence."""

    def put_bytes(self, logical_uri: str, data: bytes) -> object: ...

    def read_bytes(self, logical_uri: str) -> bytes: ...


class P6ModelBuildResolver(Protocol):
    """Rehydrate training rows from durable P3/P4 authority, never model JSON."""

    def rebuild(
        self,
        *,
        model: P6ModelRevision,
        artifact: Mapping[str, object],
        artifact_bytes: bytes,
        training: P6ModelDatasetSnapshot,
        validation: P6ModelDatasetSnapshot,
    ) -> P6ModelBuild: ...


def _time_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        normalized = value
        if normalized.tzinfo is not None:
            normalized = normalized.astimezone(UTC)
        return normalized.isoformat().replace("+00:00", "Z")
    raise P6PersistenceError("P6_DB_TIME_INVALID", type(value).__name__)


def _mapping(value: object, field: str) -> dict[str, object]:
    decoded: object = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise P6PersistenceError("P6_DB_JSON_INVALID", field) from exc
    if not isinstance(decoded, Mapping):
        raise P6PersistenceError("P6_DB_JSON_INVALID", field)
    return {str(key): item for key, item in decoded.items()}


def _strings(value: object, field: str) -> tuple[str, ...]:
    decoded: object = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise P6PersistenceError("P6_DB_ARRAY_INVALID", field) from exc
    if not isinstance(decoded, (list, tuple)):
        raise P6PersistenceError("P6_DB_ARRAY_INVALID", field)
    result: list[str] = []
    for item in decoded:
        if isinstance(item, UUID):
            result.append(str(item))
        elif isinstance(item, str):
            result.append(item)
        else:
            raise P6PersistenceError("P6_DB_ARRAY_INVALID", field)
    return tuple(result)


def _manifest_strings(manifest: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = manifest.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise P6PersistenceError("P6_MANIFEST_INVALID", key)
    return tuple(value)


def _bool(value: object, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    raise P6PersistenceError("P6_DB_BOOLEAN_INVALID", field)


def _digest(logical_id: str, prefix: str) -> str:
    if not logical_id.startswith(prefix):
        raise P6PersistenceError("P6_LOGICAL_ID_INVALID", logical_id)
    value = logical_id[len(prefix) :]
    if len(value) != 64:
        raise P6PersistenceError("P6_LOGICAL_ID_INVALID", logical_id)
    try:
        int(value, 16)
    except ValueError as exc:
        raise P6PersistenceError("P6_LOGICAL_ID_INVALID", logical_id) from exc
    return value.lower()


def _physical(namespace: UUID, logical_id: str, prefix: str) -> str:
    _digest(logical_id, prefix)
    return str(uuid5(namespace, logical_id))


def _input_manifest(value: P6InputSnapshot) -> dict[str, object]:
    return {
        "schema": _INPUT_SCHEMA,
        "factual_source_refs": list(value.factual_source_refs),
        "p3_model_refs": list(value.p3_model_refs),
        "scenario_context_refs": list(value.scenario_context_refs),
        "target_scope": value.target_scope,
        "subject_or_composition_ref": value.subject_or_composition_ref,
        "forecast_origin_utc": value.forecast_origin_utc,
        "as_of_utc": value.as_of_utc,
        "availability_status": value.availability_status,
        "reason_codes": list(value.reason_codes),
        "source_bindings": [
            {
                "phase": item.phase,
                "revision_id": item.revision_id,
                "publication_status": item.publication_status,
                "knowledge_time_utc": item.knowledge_time_utc,
                "is_target_outcome": item.is_target_outcome,
                "is_post_horizon_outcome": item.is_post_horizon_outcome,
            }
            for item in value.source_bindings
        ],
        "p3_bindings": [
            {
                "model_ref_id": item.model_ref_id,
                "publication_status": item.publication_status,
                "knowledge_time_utc": item.knowledge_time_utc,
            }
            for item in value.p3_bindings
        ],
        "context_bindings": [
            {
                "context_ref_id": item.context_ref_id,
                "status": item.status,
                "knowledge_time_utc": item.knowledge_time_utc,
            }
            for item in value.context_bindings
        ],
    }


def _forecast_request_hash(value: P6ForecastRequestBinding) -> str:
    return canonical_hash(
        {
            "input_snapshot_id": value.input_snapshot_id,
            "forecast_spec_id": value.forecast_spec_id,
            "forecast_spec_version": value.forecast_spec_version,
            "target_scope": value.target_scope,
            "subject_ref": value.subject_ref,
            "target_code": value.target_code,
            "forecast_origin_utc": value.forecast_origin_utc,
            "horizon_spec": dict(value.horizon_spec),
            "capability_model_id": value.capability_model_id,
            "model_profile_id": value.model_profile_id,
            "model_profile_version": value.model_profile_version,
            "training_dataset_snapshot_id": value.training_dataset_snapshot_id,
            "validation_dataset_snapshot_id": value.validation_dataset_snapshot_id,
            "assumption_profile_id": value.assumption_profile_id,
            "assumption_profile_version": value.assumption_profile_version,
            "as_of_utc": value.as_of_utc,
        }
    )


def _counterfactual_request_hash(value: P6CounterfactualRequestBinding) -> str:
    return canonical_hash(
        {
            "input_snapshot_id": value.input_snapshot_id,
            "base_product_refs": list(value.base_product_refs),
            "scenario_definition_id": value.scenario_definition_id,
            "interventions": dict(value.interventions),
            "held_fixed_assumptions": dict(value.held_fixed_assumptions),
            "model_refs": list(value.model_refs),
            "applicability_profile_ref": value.applicability_profile_ref,
            "as_of_utc": value.as_of_utc,
        }
    )


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: object, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise P6PersistenceError("P6_DB_INTEGER_INVALID", field)
    return value


def _uuid_text(value: object, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise P6PersistenceError("P6_DB_UUID_INVALID", field) from exc


def _forecast_result_hash(value: P6ForecastRevision) -> str:
    return canonical_hash(
        {
            "forecast_request_id": value.forecast_request_id,
            "forecast_run_id": value.forecast_run_id,
            "model_revision_id": value.model_revision_id,
            "model_artifact_hash": value.model_artifact_hash,
            "target_code": value.target_code,
            "target_time": value.target_time,
            "target_session_order": value.target_session_order,
            "distribution": dict(value.distribution),
            "threshold_probabilities": dict(value.threshold_probabilities),
            "applicability_status": value.applicability_status,
            "uncertainty": dict(value.uncertainty),
            "factual_source_refs": list(value.factual_source_refs),
            "as_of_utc": value.as_of_utc,
            "forecast_origin_utc": value.forecast_origin_utc,
            "supersedes_forecast_result_id": (
                value.supersedes_forecast_result_id
            ),
        }
    )


def _forecast_run_id(
    request: P6ForecastRequestBinding,
    model: P6ModelRevision,
) -> str:
    digest = canonical_hash(
        {
            "forecast_request_id": request.forecast_request_id,
            "capability_model_id": model.capability_model_id,
            "model_artifact_hash": model.model_artifact_hash,
            "input_snapshot_id": request.input_snapshot_id,
        }
    )
    return str(uuid5(_FORECAST_RUN_NAMESPACE, digest))


def _counterfactual_result_hash(value: P6CounterfactualRevision) -> str:
    return canonical_hash(
        {
            "counterfactual_run_id": value.counterfactual_run_id,
            "counterfactual_request_id": value.counterfactual_request_id,
            "projection_dataset_hash": value.projection_dataset_hash,
            "applicability_status": value.applicability_status,
            "identifiability_status": value.identifiability_status,
            "causal_claim_level": value.causal_claim_level,
            "uncertainty": dict(value.uncertainty),
            "as_of_utc": value.as_of_utc,
        }
    )


def _counterfactual_run_id(
    request: P6CounterfactualRequestBinding,
    value: P6CounterfactualRevision,
) -> str:
    digest = canonical_hash(
        {
            "request_hash": request.request_hash,
            "projection_dataset_hash": value.projection_dataset_hash,
            "applicability_status": value.applicability_status,
            "identifiability_status": value.identifiability_status,
            "causal_claim_level": value.causal_claim_level,
            "as_of_utc": value.as_of_utc,
            "supersedes_counterfactual_run_id": (
                value.supersedes_counterfactual_run_id
            ),
        }
    )
    return str(uuid5(_COUNTERFACTUAL_NAMESPACE, digest))


def _draft_recommendation_hash(value: P6RecommendationRevision) -> str:
    return canonical_hash(
        {
            "subject_key": value.subject_key,
            "subject_id": value.subject_id,
            "recommendation_spec_id": value.recommendation_spec_id,
            "recommendation_spec_version": value.recommendation_spec_version,
            "source_forecast_result_ids": list(
                value.source_forecast_result_ids
            ),
            "source_counterfactual_run_ids": list(
                value.source_counterfactual_run_ids
            ),
            "objective_constraints": dict(value.objective_constraints),
            "allowed_action_space": dict(value.allowed_action_space),
            "rationale": dict(value.rationale),
            "source_gap_refs": list(value.source_gap_refs),
            "proposed_training_items": dict(value.proposed_training_items),
            "applicability_status": value.applicability_status,
            "uncertainty": dict(value.uncertainty),
            "status": value.status,
            "approval_state": value.approval_state,
            "created_at": value.created_at,
            "supersedes_recommendation_id": (
                value.supersedes_recommendation_id
            ),
        }
    )


class DurableP6ModelBuildResolver:
    """Rehydrate a P6 model build from exact durable P3/P4 membership."""

    def __init__(self, rows: CanonicalRowRepository) -> None:
        self._rows = rows
        self._p3 = P3PersistenceRepository(rows)
        self._p4 = P4P5PersistenceRepository(rows)

    @staticmethod
    def _mismatch(detail: str) -> P6PersistenceError:
        return P6PersistenceError(
            "P6_MODEL_BUILD_RECONSTRUCTION_MISMATCH",
            detail,
        )

    @staticmethod
    def _number(value: object, field: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DurableP6ModelBuildResolver._mismatch(field)
        result = float(value)
        if not math.isfinite(result):
            raise DurableP6ModelBuildResolver._mismatch(field)
        return result

    @staticmethod
    def _integer(value: object, field: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise DurableP6ModelBuildResolver._mismatch(field)
        return value

    @staticmethod
    def _float_hex(value: float) -> str:
        return struct.pack(">d", value).hex()

    def _assignment_id(self, *, session_id: str, session_order: int) -> str:
        session = self._rows.one(
            "registry.training_session",
            where={"session_id": session_id},
            columns=(
                "session_order",
                "session_order_scope_id",
            ),
        )
        if session is None:
            raise self._mismatch(f"training_session:{session_id}")
        scope_raw = session["session_order_scope_id"]
        order_raw = session["session_order"]
        if (
            scope_raw is None
            or isinstance(order_raw, bool)
            or not isinstance(order_raw, int)
            or order_raw != session_order
        ):
            raise self._mismatch(f"session_order:{session_id}")
        scope_id = str(scope_raw)
        assignments = self._rows.many(
            "registry.session_order_assignment",
            where={
                "session_order_scope_id": scope_id,
                "session_id": session_id,
                "order_value": session_order,
                "is_current": True,
            },
            columns=("assignment_id", "revision_no"),
            order_by=("revision_no",),
        )
        if len(assignments) != 1:
            raise self._mismatch(
                f"session_order_assignment:{session_id}:{session_order}"
            )
        return str(assignments[0]["assignment_id"])

    def _training_row(
        self,
        *,
        p3_estimate_id: str,
        p4_revision_id: str,
    ) -> P6CapabilityTrainingRow:
        estimate = self._p3.exact_capability_estimate(p3_estimate_id)
        revision = self._p4.exact_p4_revision(p4_revision_id)
        twin = self._p3.exact_twin_revision(estimate.twin_revision_id)
        condition = dict(estimate.condition_point)
        session_order = condition.get("session_order")
        if (
            isinstance(session_order, bool)
            or not isinstance(session_order, int)
            or revision.p3_estimate_id != estimate.estimate_id
            or revision.twin_revision_id != twin.twin_revision_id
            or revision.aircraft_id != twin.aircraft_id
        ):
            raise self._mismatch(
                f"training_row_binding:{p3_estimate_id}:{p4_revision_id}"
            )
        assignment_id = self._assignment_id(
            session_id=revision.session_id,
            session_order=session_order,
        )
        return P6CapabilityTrainingRow(
            estimate=estimate,
            p4_revision=revision,
            aircraft_id=twin.aircraft_id,
            configuration_snapshot_id=twin.config_snapshot_id,
            session_order_assignment_id=assignment_id,
            session_order=session_order,
        )

    def _rows_for_snapshot(
        self,
        snapshot: P6ModelDatasetSnapshot,
    ) -> tuple[P6CapabilityTrainingRow, ...]:
        if (
            not snapshot.frozen
            or len(snapshot.row_ids) != len(snapshot.p3_estimate_ids)
            or len(snapshot.row_ids) != len(snapshot.p4_revision_ids)
        ):
            raise self._mismatch(snapshot.dataset_snapshot_id)
        rows = tuple(
            self._training_row(
                p3_estimate_id=estimate_id,
                p4_revision_id=revision_id,
            )
            for estimate_id, revision_id in zip(
                snapshot.p3_estimate_ids,
                snapshot.p4_revision_ids,
                strict=True,
            )
        )
        actual_ids = tuple(
            p6_capability_training_row_id(
                row,
                as_of_utc=snapshot.as_of_utc,
            )
            for row in rows
        )
        if actual_ids != snapshot.row_ids:
            raise self._mismatch(
                f"dataset_membership:{snapshot.dataset_snapshot_id}"
            )
        return rows

    def rebuild(
        self,
        *,
        model: P6ModelRevision,
        artifact: Mapping[str, object],
        artifact_bytes: bytes,
        training: P6ModelDatasetSnapshot,
        validation: P6ModelDatasetSnapshot,
    ) -> P6ModelBuild:
        profile = P6ForecastExecutionProfile.from_canonical()
        if (
            training.snapshot_type != "P6_MODEL_TRAINING"
            or validation.snapshot_type != "P6_MODEL_VALIDATION"
            or training.as_of_utc != validation.as_of_utc
            or len(validation.row_ids) != 1
        ):
            raise self._mismatch("dataset_snapshot_contract")

        try:
            canonical_bytes = json.dumps(
                dict(artifact),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
        except (TypeError, ValueError) as exc:
            raise self._mismatch("artifact_canonical_json") from exc
        if canonical_bytes != artifact_bytes:
            raise self._mismatch("artifact_bytes")

        validation_metrics = _mapping(
            artifact.get("validation_metrics"),
            "model_artifact.validation_metrics",
        )
        validity_domain = _mapping(
            artifact.get("validity_domain"),
            "model_artifact.validity_domain",
        )
        scalar_bindings = {
            "schema": "TPAA_P6_P3_CAPABILITY_OLS_MAD_MODEL_V1",
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
            "profile_sha256": profile.profile_sha256,
            "model_spec_id": model.model_spec_id,
            "model_spec_version": model.model_spec_version,
            "plugin_name": model.plugin_name,
            "plugin_version": model.plugin_version,
            "subject_type": model.subject_type,
            "subject_id": model.subject_id,
            "capability_type": model.capability_type,
            "training_dataset_snapshot_id": training.dataset_snapshot_id,
            "training_dataset_hash": training.data_hash,
            "validation_dataset_snapshot_id": validation.dataset_snapshot_id,
            "validation_dataset_hash": validation.data_hash,
            "applicability_profile_ref": model.applicability_profile_ref,
            "uncertainty_profile_ref": model.uncertainty_profile_ref,
        }
        for field, expected in scalar_bindings.items():
            if artifact.get(field) != expected:
                raise self._mismatch(f"artifact_binding:{field}")
        if (
            dict(model.validation_metrics) != validation_metrics
            or dict(model.validity_domain) != validity_domain
            or model.model_spec_id != profile.model_spec_id
            or model.model_spec_version != profile.model_spec_version
            or model.plugin_name != profile.plugin_name
            or model.plugin_version != profile.plugin_version
            or model.applicability_profile_ref
            != profile.applicability_profile_ref
            or model.uncertainty_profile_ref
            != profile.uncertainty_profile_ref
        ):
            raise self._mismatch("model_metadata")

        training_rows = self._rows_for_snapshot(training)
        validation_rows = self._rows_for_snapshot(validation)
        eligible_rows = tuple(
            sorted(
                (*training_rows, *validation_rows),
                key=lambda item: (
                    item.session_order,
                    item.estimate.estimate_id,
                ),
            )
        )
        applicability = assess_p6_training_applicability(
            eligible_rows,
            as_of_utc=training.as_of_utc,
            profile=profile,
        )
        if (
            applicability.status != "APPLICABLE"
            or validation_metrics.get("applicability_evidence_id")
            != applicability.applicability_evidence_id
        ):
            raise self._mismatch("applicability_evidence")

        fit_raw = artifact.get("fit_row_ids")
        if not isinstance(fit_raw, list) or not all(
            isinstance(item, str) for item in fit_raw
        ):
            raise self._mismatch("fit_row_ids")
        fit_row_ids = tuple(fit_raw)
        by_row_id = {
            p6_capability_training_row_id(
                row,
                as_of_utc=training.as_of_utc,
                profile=profile,
            ): row
            for row in eligible_rows
        }
        if len(by_row_id) != len(eligible_rows) or any(
            row_id not in by_row_id for row_id in fit_row_ids
        ):
            raise self._mismatch("fit_row_membership")
        final_refit_rows = tuple(by_row_id[row_id] for row_id in fit_row_ids)

        input_half_width = self._number(
            validation_metrics.get("p3_input_half_width_max"),
            "p3_input_half_width_max",
        )
        holdout_error = self._number(
            validation_metrics.get("holdout_absolute_error"),
            "holdout_absolute_error",
        )
        residual_mad = self._number(
            validation_metrics.get("final_refit_residual_mad"),
            "final_refit_residual_mad",
        )
        half_width = self._number(
            validation_metrics.get("uncertainty_half_width"),
            "uncertainty_half_width",
        )
        calibration_material = {
            "profile_ref": profile.uncertainty_profile_ref,
            "training_dataset_snapshot_id": training.dataset_snapshot_id,
            "validation_dataset_snapshot_id": validation.dataset_snapshot_id,
            "p3_input_half_width_max": self._float_hex(input_half_width),
            "holdout_absolute_error": self._float_hex(holdout_error),
            "final_refit_residual_mad": self._float_hex(residual_mad),
            "half_width": self._float_hex(half_width),
            "status": "CALIBRATED",
        }
        calibration_hash = canonical_hash(calibration_material)
        calibration_id = f"P6_UNCERTAINTY_SHA256:{calibration_hash}"
        if validation_metrics.get("calibration_evidence_id") != calibration_id:
            raise self._mismatch("uncertainty_calibration")
        uncertainty = P6UncertaintyCalibrationEvidence(
            calibration_evidence_id=calibration_id,
            profile_ref=profile.uncertainty_profile_ref,
            p3_input_half_width_max=input_half_width,
            holdout_absolute_error=holdout_error,
            final_refit_residual_mad=residual_mad,
            half_width=half_width,
            status="CALIBRATED",
            data_hash=calibration_hash,
        )

        intercept = self._number(artifact.get("intercept"), "intercept")
        slope = self._number(artifact.get("slope"), "slope")
        session_order_origin = self._integer(
            artifact.get("session_order_origin"),
            "session_order_origin",
        )
        target_session_order = self._integer(
            artifact.get("target_session_order"),
            "target_session_order",
        )
        datasets = P6ModelDatasetBundle(
            applicability=applicability,
            training=training,
            validation=validation,
            eligible_rows=eligible_rows,
            training_rows=training_rows,
            validation_row=validation_rows[0],
            final_refit_rows=final_refit_rows,
        )
        return P6ModelBuild(
            model=model,
            artifact=dict(artifact),
            artifact_bytes=artifact_bytes,
            datasets=datasets,
            applicability=applicability,
            uncertainty=uncertainty,
            intercept=intercept,
            slope=slope,
            session_order_origin=session_order_origin,
            target_session_order=target_session_order,
            fit_row_ids=fit_row_ids,
        )


class P6PersistenceRepository:
    """DB 1.8 exact P6 substrate shared by SQLite and PostgreSQL."""

    def __init__(
        self,
        rows: CanonicalRowRepository,
        *,
        object_store: P6ObjectStore | None = None,
        model_build_resolver: P6ModelBuildResolver | None = None,
    ) -> None:
        self._rows = rows
        self._object_store = object_store
        self._model_build_resolver = model_build_resolver

    def register_input(self, value: P6InputSnapshot) -> None:
        current = self._try_input(value.input_snapshot_id)
        if current is not None:
            if current != value:
                raise P6PersistenceError("P6_IMMUTABLE_CONFLICT", value.input_snapshot_id)
            return
        assert_p6_input_snapshot_identity(value)
        refs = tuple(
            dict.fromkeys(
                value.factual_source_refs
                + value.p3_model_refs
                + value.scenario_context_refs
            )
        )
        self._rows.insert(
            "registry.dataset_snapshot",
            {
                "dataset_snapshot_id": _physical(
                    _INPUT_NAMESPACE,
                    value.input_snapshot_id,
                    _INPUT_PREFIX,
                ),
                "snapshot_type": value.snapshot_type,
                "query_or_manifest": _input_manifest(value),
                "input_refs": refs,
                "data_hash": value.data_hash,
                "schema_version": _INPUT_SCHEMA,
                "frozen": value.frozen,
            },
            field_kinds={
                "query_or_manifest": "json",
                "input_refs": "uuid_array",
            },
        )

    def _input_from_row(self, row: dict[str, object]) -> P6InputSnapshot:
        if str(row["schema_version"]) != _INPUT_SCHEMA:
            raise P6PersistenceError("P6_INPUT_SCHEMA_INVALID", str(row["schema_version"]))
        manifest = _mapping(row["query_or_manifest"], "dataset_snapshot.query_or_manifest")
        raw_sources = manifest.get("source_bindings")
        raw_p3 = manifest.get("p3_bindings")
        raw_context = manifest.get("context_bindings")
        if not isinstance(raw_sources, list) or not isinstance(raw_p3, list) or not isinstance(raw_context, list):
            raise P6PersistenceError("P6_MANIFEST_INVALID", "bindings")
        sources: list[P6FactualSourceRevision] = []
        for raw in raw_sources:
            item = _mapping(raw, "source_binding")
            sources.append(
                P6FactualSourceRevision(
                    phase=str(item["phase"]),
                    revision_id=str(item["revision_id"]),
                    publication_status=str(item["publication_status"]),
                    knowledge_time_utc=str(item["knowledge_time_utc"]),
                    is_target_outcome=bool(item.get("is_target_outcome", False)),
                    is_post_horizon_outcome=bool(
                        item.get("is_post_horizon_outcome", False)
                    ),
                )
            )
        p3_bindings: list[P6P3ModelRef] = []
        for raw in raw_p3:
            item = _mapping(raw, "p3_binding")
            p3_bindings.append(
                P6P3ModelRef(
                    model_ref_id=str(item["model_ref_id"]),
                    publication_status=str(item["publication_status"]),
                    knowledge_time_utc=str(item["knowledge_time_utc"]),
                )
            )
        context_bindings: list[P6ContextRef] = []
        for raw in raw_context:
            item = _mapping(raw, "context_binding")
            context_bindings.append(
                P6ContextRef(
                    context_ref_id=str(item["context_ref_id"]),
                    status=str(item["status"]),
                    knowledge_time_utc=str(item["knowledge_time_utc"]),
                )
            )
        data_hash = str(row["data_hash"])
        logical_id = f"{_INPUT_PREFIX}{data_hash}"
        if str(row["dataset_snapshot_id"]) != _physical(
            _INPUT_NAMESPACE,
            logical_id,
            _INPUT_PREFIX,
        ):
            raise P6PersistenceError("P6_PHYSICAL_ID_MISMATCH", logical_id)
        value = P6InputSnapshot(
            input_snapshot_id=logical_id,
            snapshot_type=str(row["snapshot_type"]),
            factual_source_refs=_manifest_strings(manifest, "factual_source_refs"),
            p3_model_refs=_manifest_strings(manifest, "p3_model_refs"),
            scenario_context_refs=_manifest_strings(
                manifest,
                "scenario_context_refs",
            ),
            target_scope=str(manifest["target_scope"]),
            subject_or_composition_ref=str(manifest["subject_or_composition_ref"]),
            forecast_origin_utc=str(manifest["forecast_origin_utc"]),
            as_of_utc=str(manifest["as_of_utc"]),
            data_hash=data_hash,
            availability_status=str(manifest["availability_status"]),
            reason_codes=_manifest_strings(manifest, "reason_codes"),
            source_bindings=tuple(sources),
            p3_bindings=tuple(p3_bindings),
            context_bindings=tuple(context_bindings),
            frozen=_bool(row["frozen"], "dataset_snapshot.frozen"),
        )
        assert_p6_input_snapshot_identity(value)
        expected_refs = tuple(
            dict.fromkeys(
                value.factual_source_refs
                + value.p3_model_refs
                + value.scenario_context_refs
            )
        )
        if _strings(row["input_refs"], "dataset_snapshot.input_refs") != expected_refs:
            raise P6PersistenceError("P6_INPUT_REF_PROJECTION_MISMATCH", logical_id)
        return value

    def _try_input(self, object_id: str) -> P6InputSnapshot | None:
        row = self._rows.one(
            "registry.dataset_snapshot",
            where={
                "dataset_snapshot_id": _physical(
                    _INPUT_NAMESPACE,
                    object_id,
                    _INPUT_PREFIX,
                )
            },
            columns=(
                "dataset_snapshot_id",
                "snapshot_type",
                "query_or_manifest",
                "input_refs",
                "data_hash",
                "schema_version",
                "frozen",
            ),
        )
        return None if row is None else self._input_from_row(row)

    def exact_input(self, object_id: str) -> P6InputSnapshot:
        value = self._try_input(object_id)
        if value is None:
            raise P6PersistenceError("M9_INPUT_NOT_FOUND", object_id)
        return value

    def _register_model_dataset(self, value: P6ModelDatasetSnapshot) -> None:
        current = self._try_model_dataset(value.dataset_snapshot_id)
        if current is not None:
            if current != value:
                raise P6PersistenceError(
                    "P6_IMMUTABLE_CONFLICT",
                    value.dataset_snapshot_id,
                )
            return
        profile = P6ForecastExecutionProfile.from_canonical()
        material = {
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
            "profile_sha256": profile.profile_sha256,
            "snapshot_type": value.snapshot_type,
            "row_ids": list(value.row_ids),
            "p3_estimate_ids": list(value.p3_estimate_ids),
            "p4_revision_ids": list(value.p4_revision_ids),
            "as_of_utc": value.as_of_utc,
            "frozen": value.frozen,
        }
        if canonical_hash(material) != value.data_hash:
            raise P6PersistenceError(
                "P6_MODEL_DATASET_HASH_MISMATCH",
                value.dataset_snapshot_id,
            )
        self._rows.insert(
            "registry.dataset_snapshot",
            {
                "dataset_snapshot_id": value.dataset_snapshot_id,
                "snapshot_type": value.snapshot_type,
                "query_or_manifest": {
                    "schema": _MODEL_DATASET_SCHEMA,
                    **material,
                },
                "input_refs": value.p3_estimate_ids + value.p4_revision_ids,
                "data_hash": value.data_hash,
                "schema_version": _MODEL_DATASET_SCHEMA,
                "frozen": value.frozen,
            },
            field_kinds={
                "query_or_manifest": "json",
                "input_refs": "uuid_array",
            },
        )

    def _try_model_dataset(
        self,
        dataset_snapshot_id: str,
    ) -> P6ModelDatasetSnapshot | None:
        row = self._rows.one(
            "registry.dataset_snapshot",
            where={"dataset_snapshot_id": dataset_snapshot_id},
            columns=(
                "dataset_snapshot_id",
                "snapshot_type",
                "query_or_manifest",
                "input_refs",
                "data_hash",
                "schema_version",
                "frozen",
            ),
        )
        if row is None:
            return None
        if str(row["schema_version"]) != _MODEL_DATASET_SCHEMA:
            raise P6PersistenceError(
                "P6_MODEL_DATASET_SCHEMA_INVALID",
                dataset_snapshot_id,
            )
        manifest = _mapping(row["query_or_manifest"], "dataset_snapshot.query_or_manifest")
        profile = P6ForecastExecutionProfile.from_canonical()
        value = P6ModelDatasetSnapshot(
            dataset_snapshot_id=str(row["dataset_snapshot_id"]),
            snapshot_type=str(row["snapshot_type"]),
            row_ids=_manifest_strings(manifest, "row_ids"),
            p3_estimate_ids=_manifest_strings(manifest, "p3_estimate_ids"),
            p4_revision_ids=_manifest_strings(manifest, "p4_revision_ids"),
            as_of_utc=str(manifest["as_of_utc"]),
            data_hash=str(row["data_hash"]),
            frozen=_bool(row["frozen"], "dataset_snapshot.frozen"),
        )
        material = {
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
            "profile_sha256": profile.profile_sha256,
            "snapshot_type": value.snapshot_type,
            "row_ids": list(value.row_ids),
            "p3_estimate_ids": list(value.p3_estimate_ids),
            "p4_revision_ids": list(value.p4_revision_ids),
            "as_of_utc": value.as_of_utc,
            "frozen": value.frozen,
        }
        if canonical_hash(material) != value.data_hash:
            raise P6PersistenceError(
                "P6_MODEL_DATASET_HASH_MISMATCH",
                dataset_snapshot_id,
            )
        if _strings(row["input_refs"], "dataset_snapshot.input_refs") != (
            value.p3_estimate_ids + value.p4_revision_ids
        ):
            raise P6PersistenceError(
                "P6_MODEL_DATASET_REF_MISMATCH",
                dataset_snapshot_id,
            )
        return value

    def exact_model_dataset(self, dataset_snapshot_id: str) -> P6ModelDatasetSnapshot:
        value = self._try_model_dataset(dataset_snapshot_id)
        if value is None:
            raise P6PersistenceError("P6_MODEL_DATASET_NOT_FOUND", dataset_snapshot_id)
        return value

    def register_model_build(
        self,
        build: P6ModelBuild,
        managed_object: P6ManagedModelObject,
    ) -> None:
        model = build.model
        current = self._try_model(model.capability_model_id)
        if current is not None:
            if current != model or self.exact_managed_object(model.capability_model_id) != managed_object:
                raise P6PersistenceError(
                    "P6_IMMUTABLE_CONFLICT",
                    model.capability_model_id,
                )
            return
        self._register_model_dataset(build.datasets.training)
        self._register_model_dataset(build.datasets.validation)
        artifact_hash = hashlib.sha256(build.artifact_bytes).hexdigest()
        if artifact_hash != model.model_artifact_hash:
            raise P6PersistenceError("P6_MODEL_HASH_MISMATCH", model.capability_model_id)
        if _mapping(build.artifact_bytes.decode("ascii"), "model_artifact") != dict(build.artifact):
            raise P6PersistenceError(
                "P6_MODEL_ARTIFACT_PROJECTION_MISMATCH",
                model.capability_model_id,
            )
        validate_p6_managed_model_object(model, managed_object)
        if self._object_store is None:
            raise P6PersistenceError(
                "P6_MODEL_OBJECT_STORE_REQUIRED",
                model.capability_model_id,
            )
        self._object_store.put_bytes(model.model_artifact_uri, build.artifact_bytes)
        if hashlib.sha256(
            self._object_store.read_bytes(model.model_artifact_uri)
        ).hexdigest() != model.model_artifact_hash:
            raise P6PersistenceError("P6_MODEL_HASH_MISMATCH", model.capability_model_id)
        self._rows.insert(
            "registry.object_reference",
            {
                "object_ref_id": managed_object.object_ref_id,
                "managed_uri": managed_object.managed_uri,
                "media_type": "application/json",
                "size_bytes": len(build.artifact_bytes),
                "artifact_sha256": managed_object.artifact_sha256,
                "logical_content_hash": managed_object.artifact_sha256,
                "storage_backend": "LOCAL_OBJECT_STORE",
                "sealed": managed_object.sealed,
                "gc_state": managed_object.gc_state,
                "gc_state_version": 0,
                "created_at": managed_object.sealed_at_utc,
                "deleted_at": managed_object.deleted_at,
            },
        )
        self._rows.insert(
            "capability.capability_model",
            {
                "capability_model_id": model.capability_model_id,
                "model_spec_id": model.model_spec_id,
                "model_spec_version": model.model_spec_version,
                "subject_type": model.subject_type,
                "subject_id": model.subject_id,
                "capability_type": model.capability_type,
                "training_dataset_snapshot_id": model.training_dataset_snapshot_id,
                "plugin_name": model.plugin_name,
                "plugin_version": model.plugin_version,
                "model_artifact_uri": model.model_artifact_uri,
                "model_artifact_hash": model.model_artifact_hash,
                "validity_domain": dict(model.validity_domain),
                "validation_metrics": dict(model.validation_metrics),
                "status": model.status,
                "trained_at": model.trained_at,
                "published_at": model.published_at,
                "supersedes_model_id": model.supersedes_model_id,
            },
            field_kinds={
                "validity_domain": "json",
                "validation_metrics": "json",
            },
        )
        self._rows.insert(
            "capability.p6_model_revision",
            {
                "capability_model_id": model.capability_model_id,
                "validation_dataset_snapshot_id": model.validation_dataset_snapshot_id,
                "applicability_profile_ref": model.applicability_profile_ref,
                "uncertainty_profile_ref": model.uncertainty_profile_ref,
            },
        )

    def _try_model(self, model_id: str) -> P6ModelRevision | None:
        base = self._rows.one(
            "capability.capability_model",
            where={"capability_model_id": model_id},
            columns=(
                "capability_model_id",
                "model_spec_id",
                "model_spec_version",
                "subject_type",
                "subject_id",
                "capability_type",
                "training_dataset_snapshot_id",
                "plugin_name",
                "plugin_version",
                "model_artifact_uri",
                "model_artifact_hash",
                "validity_domain",
                "validation_metrics",
                "status",
                "trained_at",
                "published_at",
                "supersedes_model_id",
            ),
        )
        if base is None:
            return None
        revision = self._rows.one(
            "capability.p6_model_revision",
            where={"capability_model_id": model_id},
            columns=(
                "validation_dataset_snapshot_id",
                "applicability_profile_ref",
                "uncertainty_profile_ref",
            ),
        )
        if revision is None:
            raise P6PersistenceError("P6_MODEL_REVISION_METADATA_MISSING", model_id)
        object_row = self._rows.one(
            "registry.object_reference",
            where={"managed_uri": str(base["model_artifact_uri"])},
            columns=(
                "object_ref_id",
                "artifact_sha256",
                "sealed",
                "gc_state",
                "deleted_at",
            ),
        )
        if object_row is None or base["subject_id"] is None:
            raise P6PersistenceError("P6_MODEL_OBJECT_NOT_FOUND", model_id)
        value = P6ModelRevision(
            capability_model_id=str(base["capability_model_id"]),
            model_spec_id=str(base["model_spec_id"]),
            model_spec_version=str(base["model_spec_version"]),
            subject_type=str(base["subject_type"]),
            subject_id=str(base["subject_id"]),
            capability_type=str(base["capability_type"]),
            training_dataset_snapshot_id=str(base["training_dataset_snapshot_id"]),
            validation_dataset_snapshot_id=str(
                revision["validation_dataset_snapshot_id"]
            ),
            plugin_name=str(base["plugin_name"]),
            plugin_version=str(base["plugin_version"]),
            model_artifact_uri=str(base["model_artifact_uri"]),
            model_artifact_hash=str(base["model_artifact_hash"]),
            model_object_ref_id=str(object_row["object_ref_id"]),
            validity_domain=_mapping(base["validity_domain"], "capability_model.validity_domain"),
            validation_metrics=_mapping(
                base["validation_metrics"],
                "capability_model.validation_metrics",
            ),
            applicability_profile_ref=str(revision["applicability_profile_ref"]),
            uncertainty_profile_ref=str(revision["uncertainty_profile_ref"]),
            status=str(base["status"]),
            trained_at=_time_text(base["trained_at"]),
            published_at=(
                None if base["published_at"] is None else _time_text(base["published_at"])
            ),
            supersedes_model_id=(
                None if base["supersedes_model_id"] is None else str(base["supersedes_model_id"])
            ),
        )
        if (
            str(object_row["artifact_sha256"]) != value.model_artifact_hash
            or not _bool(object_row["sealed"], "object_reference.sealed")
            or str(object_row["gc_state"]) != "ACTIVE"
            or object_row["deleted_at"] is not None
        ):
            raise P6PersistenceError("P6_MODEL_OBJECT_INVALID", model_id)
        self.exact_model_dataset(value.training_dataset_snapshot_id)
        self.exact_model_dataset(value.validation_dataset_snapshot_id)
        return value

    def exact_model_revision(self, model_id: str) -> P6ModelRevision:
        value = self._try_model(model_id)
        if value is None:
            raise P6PersistenceError("M9_MODEL_NOT_FOUND", model_id)
        return value

    def exact_managed_object(self, model_id: str) -> P6ManagedModelObject:
        model = self.exact_model_revision(model_id)
        row = self._rows.one(
            "registry.object_reference",
            where={"object_ref_id": model.model_object_ref_id},
            columns=(
                "object_ref_id",
                "managed_uri",
                "artifact_sha256",
                "sealed",
                "gc_state",
                "deleted_at",
                "created_at",
            ),
        )
        if row is None:
            raise P6PersistenceError("M9_MODEL_OBJECT_NOT_FOUND", model_id)
        value = P6ManagedModelObject(
            object_ref_id=str(row["object_ref_id"]),
            managed_uri=str(row["managed_uri"]),
            artifact_sha256=str(row["artifact_sha256"]),
            sealed=_bool(row["sealed"], "object_reference.sealed"),
            gc_state=str(row["gc_state"]),
            deleted_at=(
                None if row["deleted_at"] is None else _time_text(row["deleted_at"])
            ),
            sealed_at_utc=_time_text(row["created_at"]),
        )
        validate_p6_managed_model_object(model, value)
        return value

    def exact_model_build(self, object_id: str) -> P6ModelBuild:
        model = self.exact_model_revision(object_id)
        if self._object_store is None or self._model_build_resolver is None:
            raise P6PersistenceError(
                "P6_MODEL_BUILD_DEPENDENCY_BLOCKED",
                object_id,
            )
        artifact_bytes = self._object_store.read_bytes(model.model_artifact_uri)
        if hashlib.sha256(artifact_bytes).hexdigest() != model.model_artifact_hash:
            raise P6PersistenceError("P6_MODEL_HASH_MISMATCH", object_id)
        artifact = _mapping(artifact_bytes.decode("ascii"), "model_artifact")
        build = self._model_build_resolver.rebuild(
            model=model,
            artifact=artifact,
            artifact_bytes=artifact_bytes,
            training=self.exact_model_dataset(model.training_dataset_snapshot_id),
            validation=self.exact_model_dataset(model.validation_dataset_snapshot_id),
        )
        if build.model != model or build.artifact_bytes != artifact_bytes:
            raise P6PersistenceError(
                "P6_MODEL_BUILD_RECONSTRUCTION_MISMATCH",
                object_id,
            )
        return build

    def replace_model_release(self, model: P6ModelRevision) -> None:
        current = self.exact_model_revision(model.capability_model_id)
        before = current.projection()
        after = model.projection()
        for key in ("status", "published_at"):
            before.pop(key)
            after.pop(key)
        if before != after:
            raise P6PersistenceError(
                "P6_IMMUTABLE_CONFLICT",
                model.capability_model_id,
            )
        if current.status == model.status and current.published_at == model.published_at:
            return
        self._rows.update_exact(
            "capability.capability_model",
            where={"capability_model_id": model.capability_model_id},
            values={
                "status": model.status,
                "published_at": model.published_at,
            },
        )

    def register_forecast_request(self, value: P6ForecastRequestBinding) -> None:
        current = self._try_forecast_request(value.forecast_request_id)
        if current is not None:
            if current != value:
                raise P6PersistenceError(
                    "P6_IMMUTABLE_CONFLICT",
                    value.forecast_request_id,
                )
            return
        if (
            _forecast_request_hash(value) != value.request_hash
            or value.forecast_request_id
            != f"{_FORECAST_REQUEST_PREFIX}{value.request_hash}"
        ):
            raise P6PersistenceError(
                "P6_FORECAST_REQUEST_HASH_MISMATCH",
                value.forecast_request_id,
            )
        input_snapshot = self.exact_input(value.input_snapshot_id)
        model = self.exact_model_revision(value.capability_model_id)
        if (
            input_snapshot.target_scope != value.target_scope
            or input_snapshot.subject_or_composition_ref != value.subject_ref
            or model.training_dataset_snapshot_id != value.training_dataset_snapshot_id
            or model.validation_dataset_snapshot_id != value.validation_dataset_snapshot_id
        ):
            raise P6PersistenceError(
                "P6_FORECAST_REQUEST_BINDING_MISMATCH",
                value.forecast_request_id,
            )
        self._rows.insert(
            "intelligence.forecast_request",
            {
                "forecast_request_id": _physical(
                    _FORECAST_REQUEST_NAMESPACE,
                    value.forecast_request_id,
                    _FORECAST_REQUEST_PREFIX,
                ),
                "input_snapshot_id": _physical(
                    _INPUT_NAMESPACE,
                    value.input_snapshot_id,
                    _INPUT_PREFIX,
                ),
                "forecast_spec_id": value.forecast_spec_id,
                "forecast_spec_version": value.forecast_spec_version,
                "target_scope": value.target_scope,
                "subject_ref": value.subject_ref,
                "target_code": value.target_code,
                "forecast_origin_utc": value.forecast_origin_utc,
                "horizon_spec": dict(value.horizon_spec),
                "capability_model_id": value.capability_model_id,
                "model_profile_id": value.model_profile_id,
                "model_profile_version": value.model_profile_version,
                "training_dataset_snapshot_id": value.training_dataset_snapshot_id,
                "validation_dataset_snapshot_id": value.validation_dataset_snapshot_id,
                "assumption_profile_id": value.assumption_profile_id,
                "assumption_profile_version": value.assumption_profile_version,
                "as_of_utc": value.as_of_utc,
                "request_hash": value.request_hash,
            },
            field_kinds={"horizon_spec": "json"},
        )

    def _try_forecast_request(
        self,
        object_id: str,
    ) -> P6ForecastRequestBinding | None:
        row = self._rows.one(
            "intelligence.forecast_request",
            where={
                "forecast_request_id": _physical(
                    _FORECAST_REQUEST_NAMESPACE,
                    object_id,
                    _FORECAST_REQUEST_PREFIX,
                )
            },
            columns=(
                "input_snapshot_id",
                "forecast_spec_id",
                "forecast_spec_version",
                "target_scope",
                "subject_ref",
                "target_code",
                "forecast_origin_utc",
                "horizon_spec",
                "capability_model_id",
                "model_profile_id",
                "model_profile_version",
                "training_dataset_snapshot_id",
                "validation_dataset_snapshot_id",
                "assumption_profile_id",
                "assumption_profile_version",
                "as_of_utc",
                "request_hash",
            ),
        )
        if row is None:
            return None
        request_hash = str(row["request_hash"])
        if object_id != f"{_FORECAST_REQUEST_PREFIX}{request_hash}":
            raise P6PersistenceError("P6_LOGICAL_ID_MISMATCH", object_id)
        input_snapshot = self._input_by_physical(str(row["input_snapshot_id"]))
        value = P6ForecastRequestBinding(
            forecast_request_id=object_id,
            input_snapshot_id=input_snapshot.input_snapshot_id,
            forecast_spec_id=str(row["forecast_spec_id"]),
            forecast_spec_version=str(row["forecast_spec_version"]),
            target_scope=str(row["target_scope"]),
            subject_ref=str(row["subject_ref"]),
            target_code=str(row["target_code"]),
            forecast_origin_utc=_time_text(row["forecast_origin_utc"]),
            horizon_spec=_mapping(row["horizon_spec"], "forecast_request.horizon_spec"),
            capability_model_id=str(row["capability_model_id"]),
            model_profile_id=str(row["model_profile_id"]),
            model_profile_version=str(row["model_profile_version"]),
            training_dataset_snapshot_id=str(row["training_dataset_snapshot_id"]),
            validation_dataset_snapshot_id=str(row["validation_dataset_snapshot_id"]),
            assumption_profile_id=str(row["assumption_profile_id"]),
            assumption_profile_version=str(row["assumption_profile_version"]),
            as_of_utc=_time_text(row["as_of_utc"]),
            request_hash=request_hash,
        )
        if _forecast_request_hash(value) != request_hash:
            raise P6PersistenceError("P6_FORECAST_REQUEST_HASH_MISMATCH", object_id)
        return value

    def exact_forecast_request(self, object_id: str) -> P6ForecastRequestBinding:
        value = self._try_forecast_request(object_id)
        if value is None:
            raise P6PersistenceError("M9_FORECAST_REQUEST_NOT_FOUND", object_id)
        return value

    def register_counterfactual_request(
        self,
        value: P6CounterfactualRequestBinding,
    ) -> None:
        current = self._try_counterfactual_request(value.counterfactual_request_id)
        if current is not None:
            if current != value:
                raise P6PersistenceError(
                    "P6_IMMUTABLE_CONFLICT",
                    value.counterfactual_request_id,
                )
            return
        if (
            _counterfactual_request_hash(value) != value.request_hash
            or value.counterfactual_request_id
            != f"{_COUNTERFACTUAL_REQUEST_PREFIX}{value.request_hash}"
        ):
            raise P6PersistenceError(
                "P6_COUNTERFACTUAL_REQUEST_HASH_MISMATCH",
                value.counterfactual_request_id,
            )
        self.exact_input(value.input_snapshot_id)
        for model_id in value.model_refs:
            self.exact_model_revision(model_id)
        self._rows.insert(
            "intelligence.counterfactual_request",
            {
                "counterfactual_request_id": _physical(
                    _COUNTERFACTUAL_REQUEST_NAMESPACE,
                    value.counterfactual_request_id,
                    _COUNTERFACTUAL_REQUEST_PREFIX,
                ),
                "input_snapshot_id": _physical(
                    _INPUT_NAMESPACE,
                    value.input_snapshot_id,
                    _INPUT_PREFIX,
                ),
                "base_product_refs": value.base_product_refs,
                "scenario_definition_id": value.scenario_definition_id,
                "interventions": dict(value.interventions),
                "held_fixed_assumptions": dict(value.held_fixed_assumptions),
                "model_refs": value.model_refs,
                "applicability_profile_ref": value.applicability_profile_ref,
                "as_of_utc": value.as_of_utc,
                "request_hash": value.request_hash,
            },
            field_kinds={
                "base_product_refs": "text_array",
                "interventions": "json",
                "held_fixed_assumptions": "json",
                "model_refs": "text_array",
            },
        )

    def _try_counterfactual_request(
        self,
        object_id: str,
    ) -> P6CounterfactualRequestBinding | None:
        row = self._rows.one(
            "intelligence.counterfactual_request",
            where={
                "counterfactual_request_id": _physical(
                    _COUNTERFACTUAL_REQUEST_NAMESPACE,
                    object_id,
                    _COUNTERFACTUAL_REQUEST_PREFIX,
                )
            },
            columns=(
                "input_snapshot_id",
                "base_product_refs",
                "scenario_definition_id",
                "interventions",
                "held_fixed_assumptions",
                "model_refs",
                "applicability_profile_ref",
                "as_of_utc",
                "request_hash",
            ),
        )
        if row is None:
            return None
        request_hash = str(row["request_hash"])
        if object_id != f"{_COUNTERFACTUAL_REQUEST_PREFIX}{request_hash}":
            raise P6PersistenceError("P6_LOGICAL_ID_MISMATCH", object_id)
        input_snapshot = self._input_by_physical(str(row["input_snapshot_id"]))
        value = P6CounterfactualRequestBinding(
            counterfactual_request_id=object_id,
            input_snapshot_id=input_snapshot.input_snapshot_id,
            base_product_refs=_strings(
                row["base_product_refs"],
                "counterfactual_request.base_product_refs",
            ),
            scenario_definition_id=str(row["scenario_definition_id"]),
            interventions=_mapping(
                row["interventions"],
                "counterfactual_request.interventions",
            ),
            held_fixed_assumptions=_mapping(
                row["held_fixed_assumptions"],
                "counterfactual_request.held_fixed_assumptions",
            ),
            model_refs=_strings(
                row["model_refs"],
                "counterfactual_request.model_refs",
            ),
            applicability_profile_ref=str(row["applicability_profile_ref"]),
            as_of_utc=_time_text(row["as_of_utc"]),
            request_hash=request_hash,
        )
        if _counterfactual_request_hash(value) != request_hash:
            raise P6PersistenceError(
                "P6_COUNTERFACTUAL_REQUEST_HASH_MISMATCH",
                object_id,
            )
        return value

    def exact_counterfactual_request(
        self,
        object_id: str,
    ) -> P6CounterfactualRequestBinding:
        value = self._try_counterfactual_request(object_id)
        if value is None:
            raise P6PersistenceError(
                "M9_COUNTERFACTUAL_REQUEST_NOT_FOUND",
                object_id,
            )
        return value

    def _input_by_physical(self, physical_id: str) -> P6InputSnapshot:
        row = self._rows.one(
            "registry.dataset_snapshot",
            where={"dataset_snapshot_id": physical_id},
            columns=(
                "dataset_snapshot_id",
                "snapshot_type",
                "query_or_manifest",
                "input_refs",
                "data_hash",
                "schema_version",
                "frozen",
            ),
        )
        if row is None:
            raise P6PersistenceError("M9_INPUT_NOT_FOUND", physical_id)
        return self._input_from_row(row)

    def _forecast_request_by_physical(
        self,
        physical_id: object,
    ) -> P6ForecastRequestBinding:
        row = self._rows.one(
            "intelligence.forecast_request",
            where={"forecast_request_id": str(physical_id)},
            columns=("request_hash",),
        )
        if row is None:
            raise P6PersistenceError(
                "M9_FORECAST_REQUEST_NOT_FOUND",
                str(physical_id),
            )
        logical_id = f"{_FORECAST_REQUEST_PREFIX}{row['request_hash']}"
        if str(physical_id) != _physical(
            _FORECAST_REQUEST_NAMESPACE,
            logical_id,
            _FORECAST_REQUEST_PREFIX,
        ):
            raise P6PersistenceError(
                "P6_PHYSICAL_ID_MISMATCH",
                logical_id,
            )
        return self.exact_forecast_request(logical_id)

    def _counterfactual_request_by_physical(
        self,
        physical_id: object,
    ) -> P6CounterfactualRequestBinding:
        row = self._rows.one(
            "intelligence.counterfactual_request",
            where={"counterfactual_request_id": str(physical_id)},
            columns=("request_hash",),
        )
        if row is None:
            raise P6PersistenceError(
                "M9_COUNTERFACTUAL_REQUEST_NOT_FOUND",
                str(physical_id),
            )
        logical_id = f"{_COUNTERFACTUAL_REQUEST_PREFIX}{row['request_hash']}"
        if str(physical_id) != _physical(
            _COUNTERFACTUAL_REQUEST_NAMESPACE,
            logical_id,
            _COUNTERFACTUAL_REQUEST_PREFIX,
        ):
            raise P6PersistenceError(
                "P6_PHYSICAL_ID_MISMATCH",
                logical_id,
            )
        return self.exact_counterfactual_request(logical_id)

    def _ensure_forecast_run(
        self,
        value: P6ForecastRevision,
        request: P6ForecastRequestBinding,
        model: P6ModelRevision,
    ) -> None:
        if value.forecast_run_id != _forecast_run_id(request, model):
            raise P6PersistenceError(
                "P6_FORECAST_RUN_IDENTITY_MISMATCH",
                value.forecast_result_id,
            )
        subject_id = _uuid_text(
            request.subject_ref,
            "forecast_request.subject_ref",
        )
        current = self._rows.one(
            "intelligence.forecast_run",
            where={"forecast_run_id": value.forecast_run_id},
            columns=(
                "forecast_spec_id",
                "forecast_spec_version",
                "subject_type",
                "subject_id",
                "input_snapshot_id",
                "model_artifact_uri",
                "model_artifact_hash",
                "horizon_spec",
                "status",
            ),
        )
        if current is not None:
            if (
                str(current["forecast_spec_id"]) != request.forecast_spec_id
                or str(current["forecast_spec_version"])
                != request.forecast_spec_version
                or str(current["subject_type"]) != model.subject_type
                or str(current["subject_id"]) != subject_id
                or str(current["input_snapshot_id"])
                != _physical(
                    _INPUT_NAMESPACE,
                    request.input_snapshot_id,
                    _INPUT_PREFIX,
                )
                or str(current["model_artifact_uri"])
                != model.model_artifact_uri
                or str(current["model_artifact_hash"])
                != model.model_artifact_hash
                or _mapping(
                    current["horizon_spec"],
                    "forecast_run.horizon_spec",
                )
                != dict(request.horizon_spec)
                or str(current["status"]) != "SUCCEEDED"
            ):
                raise P6PersistenceError(
                    "P6_IMMUTABLE_CONFLICT",
                    value.forecast_run_id,
                )
            return
        self._rows.insert(
            "intelligence.forecast_run",
            {
                "forecast_run_id": value.forecast_run_id,
                "forecast_spec_id": request.forecast_spec_id,
                "forecast_spec_version": request.forecast_spec_version,
                "subject_type": model.subject_type,
                "subject_id": subject_id,
                "input_snapshot_id": _physical(
                    _INPUT_NAMESPACE,
                    request.input_snapshot_id,
                    _INPUT_PREFIX,
                ),
                "model_artifact_uri": model.model_artifact_uri,
                "model_artifact_hash": model.model_artifact_hash,
                "horizon_spec": dict(request.horizon_spec),
                "backtest_metrics": {},
                "status": "SUCCEEDED",
                "created_at": request.as_of_utc,
            },
            field_kinds={
                "horizon_spec": "json",
                "backtest_metrics": "json",
            },
        )

    def register_forecast(self, value: P6ForecastRevision) -> None:
        current = self._try_forecast(value.forecast_result_id)
        if current is not None:
            if current != value:
                raise P6PersistenceError(
                    "P6_IMMUTABLE_CONFLICT",
                    value.forecast_result_id,
                )
            return
        request = self.exact_forecast_request(value.forecast_request_id)
        model = self.exact_model_revision(value.model_revision_id)
        input_snapshot = self.exact_input(request.input_snapshot_id)
        digest = _forecast_result_hash(value)
        if (
            request.capability_model_id != value.model_revision_id
            or request.subject_ref != model.subject_id
            or request.target_code != value.target_code
            or request.forecast_origin_utc != value.forecast_origin_utc
            or request.as_of_utc != value.as_of_utc
            or model.model_artifact_hash != value.model_artifact_hash
            or input_snapshot.factual_source_refs
            != value.factual_source_refs
            or value.logical_content_hash != digest
            or value.forecast_identity
            != f"P6_FORECAST_RESULT_SHA256:{digest}"
            or value.forecast_result_id
            != str(uuid5(_FORECAST_RESULT_NAMESPACE, digest))
        ):
            raise P6PersistenceError(
                "P6_FORECAST_IDENTITY_MISMATCH",
                value.forecast_result_id,
            )
        self._ensure_forecast_run(value, request, model)
        self._rows.insert(
            "intelligence.forecast_result",
            {
                "forecast_result_id": value.forecast_result_id,
                "forecast_run_id": value.forecast_run_id,
                "target_code": value.target_code,
                "target_time": value.target_time,
                "distribution": dict(value.distribution),
                "threshold_probabilities": dict(
                    value.threshold_probabilities
                ),
                "status": value.status,
            },
            field_kinds={
                "distribution": "json",
                "threshold_probabilities": "json",
            },
        )
        self._rows.insert(
            "intelligence.forecast_result_revision",
            {
                "forecast_result_id": value.forecast_result_id,
                "forecast_identity": value.forecast_identity,
                "forecast_request_id": _physical(
                    _FORECAST_REQUEST_NAMESPACE,
                    value.forecast_request_id,
                    _FORECAST_REQUEST_PREFIX,
                ),
                "target_session_order": value.target_session_order,
                "applicability_status": value.applicability_status,
                "uncertainty": dict(value.uncertainty),
                "factual_source_refs": value.factual_source_refs,
                "model_revision_id": value.model_revision_id,
                "model_artifact_hash": value.model_artifact_hash,
                "as_of_utc": value.as_of_utc,
                "forecast_origin_utc": value.forecast_origin_utc,
                "published_at_utc": value.published_at_utc,
                "supersedes_forecast_result_id": (
                    value.supersedes_forecast_result_id
                ),
                "logical_content_hash": value.logical_content_hash,
            },
            field_kinds={
                "uncertainty": "json",
                "factual_source_refs": "text_array",
            },
        )

    def _try_forecast(self, object_id: str) -> P6ForecastRevision | None:
        base = self._rows.one(
            "intelligence.forecast_result",
            where={"forecast_result_id": object_id},
            columns=(
                "forecast_result_id",
                "forecast_run_id",
                "target_code",
                "target_time",
                "distribution",
                "threshold_probabilities",
                "status",
            ),
        )
        if base is None:
            return None
        revision = self._rows.one(
            "intelligence.forecast_result_revision",
            where={"forecast_result_id": object_id},
            columns=(
                "forecast_identity",
                "forecast_request_id",
                "target_session_order",
                "applicability_status",
                "uncertainty",
                "factual_source_refs",
                "model_revision_id",
                "model_artifact_hash",
                "as_of_utc",
                "forecast_origin_utc",
                "published_at_utc",
                "supersedes_forecast_result_id",
                "logical_content_hash",
            ),
        )
        if revision is None:
            raise P6PersistenceError(
                "P6_FORECAST_REVISION_METADATA_MISSING",
                object_id,
            )
        request = self._forecast_request_by_physical(
            revision["forecast_request_id"]
        )
        value = P6ForecastRevision(
            forecast_result_id=str(base["forecast_result_id"]),
            forecast_identity=str(revision["forecast_identity"]),
            forecast_run_id=str(base["forecast_run_id"]),
            forecast_request_id=request.forecast_request_id,
            target_code=str(base["target_code"]),
            target_time=(
                None
                if base["target_time"] is None
                else _time_text(base["target_time"])
            ),
            target_session_order=_optional_int(
                revision["target_session_order"],
                "forecast_result_revision.target_session_order",
            ),
            distribution=_mapping(
                base["distribution"],
                "forecast_result.distribution",
            ),
            threshold_probabilities=_mapping(
                base["threshold_probabilities"],
                "forecast_result.threshold_probabilities",
            ),
            applicability_status=str(revision["applicability_status"]),
            uncertainty=_mapping(
                revision["uncertainty"],
                "forecast_result_revision.uncertainty",
            ),
            status=str(base["status"]),
            factual_source_refs=_strings(
                revision["factual_source_refs"],
                "forecast_result_revision.factual_source_refs",
            ),
            model_revision_id=str(revision["model_revision_id"]),
            model_artifact_hash=str(revision["model_artifact_hash"]),
            as_of_utc=_time_text(revision["as_of_utc"]),
            forecast_origin_utc=_time_text(
                revision["forecast_origin_utc"]
            ),
            published_at_utc=_time_text(revision["published_at_utc"]),
            supersedes_forecast_result_id=_optional_text(
                revision["supersedes_forecast_result_id"]
            ),
            logical_content_hash=str(revision["logical_content_hash"]),
        )
        model = self.exact_model_revision(value.model_revision_id)
        run = self._rows.one(
            "intelligence.forecast_run",
            where={"forecast_run_id": value.forecast_run_id},
            columns=(
                "subject_id",
                "input_snapshot_id",
                "model_artifact_uri",
                "model_artifact_hash",
                "horizon_spec",
                "status",
            ),
        )
        digest = _forecast_result_hash(value)
        if (
            run is None
            or str(run["subject_id"]) != request.subject_ref
            or str(run["input_snapshot_id"])
            != _physical(
                _INPUT_NAMESPACE,
                request.input_snapshot_id,
                _INPUT_PREFIX,
            )
            or str(run["model_artifact_uri"])
            != model.model_artifact_uri
            or str(run["model_artifact_hash"])
            != model.model_artifact_hash
            or _mapping(run["horizon_spec"], "forecast_run.horizon_spec")
            != dict(request.horizon_spec)
            or str(run["status"]) != "SUCCEEDED"
            or value.forecast_run_id != _forecast_run_id(request, model)
            or value.logical_content_hash != digest
            or value.forecast_identity
            != f"P6_FORECAST_RESULT_SHA256:{digest}"
            or value.forecast_result_id
            != str(uuid5(_FORECAST_RESULT_NAMESPACE, digest))
        ):
            raise P6PersistenceError(
                "P6_FORECAST_IDENTITY_MISMATCH",
                object_id,
            )
        return value

    def exact_forecast(self, object_id: str) -> P6ForecastRevision:
        value = self._try_forecast(object_id)
        if value is None:
            raise P6PersistenceError("M9_FORECAST_NOT_FOUND", object_id)
        return value

    def register_counterfactual(
        self,
        value: P6CounterfactualRevision,
    ) -> None:
        current = self._try_counterfactual(value.counterfactual_run_id)
        if current is not None:
            if current != value:
                raise P6PersistenceError(
                    "P6_IMMUTABLE_CONFLICT",
                    value.counterfactual_run_id,
                )
            return
        request = self.exact_counterfactual_request(
            value.counterfactual_request_id
        )
        expected_assumptions = {
            "held_fixed": dict(value.held_fixed_assumptions),
            "interventions": dict(value.interventions),
        }
        if (
            value.base_product_refs != request.base_product_refs
            or value.scenario_definition_id
            != request.scenario_definition_id
            or dict(value.interventions) != dict(request.interventions)
            or dict(value.held_fixed_assumptions)
            != dict(request.held_fixed_assumptions)
            or value.model_refs != request.model_refs
            or value.applicability_profile_ref
            != request.applicability_profile_ref
            or value.as_of_utc != request.as_of_utc
            or dict(value.assumptions) != expected_assumptions
            or value.counterfactual_run_id
            != _counterfactual_run_id(request, value)
            or value.logical_content_hash
            != _counterfactual_result_hash(value)
        ):
            raise P6PersistenceError(
                "P6_COUNTERFACTUAL_IDENTITY_MISMATCH",
                value.counterfactual_run_id,
            )
        self._rows.insert(
            "intelligence.counterfactual_run",
            {
                "counterfactual_run_id": value.counterfactual_run_id,
                "spec_id": _COUNTERFACTUAL_SPEC_ID,
                "spec_version": _COUNTERFACTUAL_SPEC_VERSION,
                "base_product_refs": value.base_product_refs,
                "scenario_definition_id": value.scenario_definition_id,
                "assumptions": expected_assumptions,
                "model_refs": value.model_refs,
                "projection_dataset_uri": value.projection_dataset_uri,
                "projection_dataset_hash": value.projection_dataset_hash,
                "status": value.status,
                "created_at": value.created_at_utc,
            },
            field_kinds={
                "base_product_refs": "uuid_array",
                "assumptions": "json",
                "model_refs": "uuid_array",
            },
        )
        self._rows.insert(
            "intelligence.counterfactual_revision",
            {
                "counterfactual_run_id": value.counterfactual_run_id,
                "counterfactual_request_id": _physical(
                    _COUNTERFACTUAL_REQUEST_NAMESPACE,
                    value.counterfactual_request_id,
                    _COUNTERFACTUAL_REQUEST_PREFIX,
                ),
                "interventions": dict(value.interventions),
                "held_fixed_assumptions": dict(
                    value.held_fixed_assumptions
                ),
                "applicability_profile_ref": (
                    value.applicability_profile_ref
                ),
                "applicability_status": value.applicability_status,
                "identifiability_status": value.identifiability_status,
                "causal_claim_level": value.causal_claim_level,
                "uncertainty": dict(value.uncertainty),
                "as_of_utc": value.as_of_utc,
                "supersedes_counterfactual_run_id": (
                    value.supersedes_counterfactual_run_id
                ),
                "logical_content_hash": value.logical_content_hash,
            },
            field_kinds={
                "interventions": "json",
                "held_fixed_assumptions": "json",
                "uncertainty": "json",
            },
        )

    def _try_counterfactual(
        self,
        object_id: str,
    ) -> P6CounterfactualRevision | None:
        base = self._rows.one(
            "intelligence.counterfactual_run",
            where={"counterfactual_run_id": object_id},
            columns=(
                "counterfactual_run_id",
                "spec_id",
                "spec_version",
                "base_product_refs",
                "scenario_definition_id",
                "assumptions",
                "model_refs",
                "projection_dataset_uri",
                "projection_dataset_hash",
                "status",
                "created_at",
            ),
        )
        if base is None:
            return None
        revision = self._rows.one(
            "intelligence.counterfactual_revision",
            where={"counterfactual_run_id": object_id},
            columns=(
                "counterfactual_request_id",
                "interventions",
                "held_fixed_assumptions",
                "applicability_profile_ref",
                "applicability_status",
                "identifiability_status",
                "causal_claim_level",
                "uncertainty",
                "as_of_utc",
                "supersedes_counterfactual_run_id",
                "logical_content_hash",
            ),
        )
        if revision is None:
            raise P6PersistenceError(
                "P6_COUNTERFACTUAL_REVISION_METADATA_MISSING",
                object_id,
            )
        if (
            str(base["spec_id"]) != _COUNTERFACTUAL_SPEC_ID
            or str(base["spec_version"])
            != _COUNTERFACTUAL_SPEC_VERSION
            or base["projection_dataset_uri"] is None
            or base["projection_dataset_hash"] is None
        ):
            raise P6PersistenceError(
                "P6_COUNTERFACTUAL_RUN_INVALID",
                object_id,
            )
        request = self._counterfactual_request_by_physical(
            revision["counterfactual_request_id"]
        )
        value = P6CounterfactualRevision(
            counterfactual_run_id=str(base["counterfactual_run_id"]),
            counterfactual_request_id=request.counterfactual_request_id,
            base_product_refs=_strings(
                base["base_product_refs"],
                "counterfactual_run.base_product_refs",
            ),
            scenario_definition_id=str(base["scenario_definition_id"]),
            interventions=_mapping(
                revision["interventions"],
                "counterfactual_revision.interventions",
            ),
            held_fixed_assumptions=_mapping(
                revision["held_fixed_assumptions"],
                "counterfactual_revision.held_fixed_assumptions",
            ),
            model_refs=_strings(
                base["model_refs"],
                "counterfactual_run.model_refs",
            ),
            applicability_profile_ref=str(
                revision["applicability_profile_ref"]
            ),
            projection_dataset_uri=str(base["projection_dataset_uri"]),
            projection_dataset_hash=str(
                base["projection_dataset_hash"]
            ),
            applicability_status=str(revision["applicability_status"]),
            identifiability_status=str(
                revision["identifiability_status"]
            ),
            causal_claim_level=str(revision["causal_claim_level"]),
            uncertainty=_mapping(
                revision["uncertainty"],
                "counterfactual_revision.uncertainty",
            ),
            assumptions=_mapping(
                base["assumptions"],
                "counterfactual_run.assumptions",
            ),
            status=str(base["status"]),
            as_of_utc=_time_text(revision["as_of_utc"]),
            created_at_utc=_time_text(base["created_at"]),
            supersedes_counterfactual_run_id=_optional_text(
                revision["supersedes_counterfactual_run_id"]
            ),
            logical_content_hash=str(revision["logical_content_hash"]),
        )
        expected_assumptions = {
            "held_fixed": dict(value.held_fixed_assumptions),
            "interventions": dict(value.interventions),
        }
        if (
            value.base_product_refs != request.base_product_refs
            or value.scenario_definition_id
            != request.scenario_definition_id
            or dict(value.interventions) != dict(request.interventions)
            or dict(value.held_fixed_assumptions)
            != dict(request.held_fixed_assumptions)
            or value.model_refs != request.model_refs
            or dict(value.assumptions) != expected_assumptions
            or value.counterfactual_run_id
            != _counterfactual_run_id(request, value)
            or value.logical_content_hash
            != _counterfactual_result_hash(value)
        ):
            raise P6PersistenceError(
                "P6_COUNTERFACTUAL_IDENTITY_MISMATCH",
                object_id,
            )
        return value

    def exact_counterfactual(
        self,
        object_id: str,
    ) -> P6CounterfactualRevision:
        value = self._try_counterfactual(object_id)
        if value is None:
            raise P6PersistenceError(
                "M9_COUNTERFACTUAL_NOT_FOUND",
                object_id,
            )
        return value

    def _assert_recommendation_identity(
        self,
        value: P6RecommendationRevision,
        visited: frozenset[str] = frozenset(),
    ) -> None:
        if value.recommendation_id in visited:
            raise P6PersistenceError(
                "P6_RECOMMENDATION_SUPERSESSION_CYCLE",
                value.recommendation_id,
            )
        if value.approval_state == "DRAFT":
            digest = _draft_recommendation_hash(value)
        else:
            previous_id = value.supersedes_recommendation_id
            if previous_id is None:
                raise P6PersistenceError(
                    "P6_RECOMMENDATION_SUPERSESSION_MISSING",
                    value.recommendation_id,
                )
            previous = self._exact_recommendation_checked(
                previous_id,
                visited | {value.recommendation_id},
            )
            material = {
                **previous.projection(),
                "subject_id": previous.subject_id,
                "approval_state": value.approval_state,
                "reviewer_subject_key": value.reviewer_subject_key,
                "audit_ref": value.audit_ref,
                "created_at": value.created_at,
                "supersedes_recommendation_id": (
                    previous.recommendation_id
                ),
            }
            digest = canonical_hash(material)
            expected = replace(
                previous,
                recommendation_id=value.recommendation_id,
                approval_state=value.approval_state,
                reviewer_subject_key=value.reviewer_subject_key,
                audit_ref=value.audit_ref,
                created_at=value.created_at,
                supersedes_recommendation_id=previous.recommendation_id,
                logical_content_hash=value.logical_content_hash,
            )
            if expected != value:
                raise P6PersistenceError(
                    "P6_RECOMMENDATION_SUPERSESSION_MISMATCH",
                    value.recommendation_id,
                )
        if (
            value.logical_content_hash != digest
            or value.recommendation_id
            != str(uuid5(_RECOMMENDATION_NAMESPACE, digest))
        ):
            raise P6PersistenceError(
                "P6_RECOMMENDATION_IDENTITY_MISMATCH",
                value.recommendation_id,
            )

    def register_recommendation(
        self,
        value: P6RecommendationRevision,
    ) -> None:
        current = self._try_recommendation(value.recommendation_id)
        if current is not None:
            self._assert_recommendation_identity(current)
            if current != value:
                raise P6PersistenceError(
                    "P6_IMMUTABLE_CONFLICT",
                    value.recommendation_id,
                )
            return
        for forecast_id in value.source_forecast_result_ids:
            self.exact_forecast(forecast_id)
        for counterfactual_id in value.source_counterfactual_run_ids:
            self.exact_counterfactual(counterfactual_id)
        if value.supersedes_recommendation_id is not None:
            self.exact_recommendation(value.supersedes_recommendation_id)
        self._assert_recommendation_identity(value)
        self._rows.insert(
            "intelligence.training_recommendation",
            {
                "recommendation_id": value.recommendation_id,
                "subject_id": value.subject_id,
                "recommendation_spec_id": value.recommendation_spec_id,
                "recommendation_spec_version": (
                    value.recommendation_spec_version
                ),
                "rationale": dict(value.rationale),
                "source_gap_refs": value.source_gap_refs,
                "proposed_training_items": dict(
                    value.proposed_training_items
                ),
                "status": value.status,
                "approval_state": value.approval_state,
                "created_at": value.created_at,
            },
            field_kinds={
                "rationale": "json",
                "source_gap_refs": "uuid_array",
                "proposed_training_items": "json",
            },
        )
        self._rows.insert(
            "intelligence.training_recommendation_revision",
            {
                "recommendation_id": value.recommendation_id,
                "subject_key": value.subject_key,
                "source_forecast_result_ids": (
                    value.source_forecast_result_ids
                ),
                "source_counterfactual_run_ids": (
                    value.source_counterfactual_run_ids
                ),
                "objective_constraints": dict(
                    value.objective_constraints
                ),
                "allowed_action_space": dict(value.allowed_action_space),
                "applicability_status": value.applicability_status,
                "uncertainty": dict(value.uncertainty),
                "reviewer_subject_key": value.reviewer_subject_key,
                "audit_ref": value.audit_ref,
                "supersedes_recommendation_id": (
                    value.supersedes_recommendation_id
                ),
                "logical_content_hash": value.logical_content_hash,
            },
            field_kinds={
                "source_forecast_result_ids": "uuid_array",
                "source_counterfactual_run_ids": "uuid_array",
                "objective_constraints": "json",
                "allowed_action_space": "json",
                "uncertainty": "json",
            },
        )

    def _try_recommendation(
        self,
        object_id: str,
    ) -> P6RecommendationRevision | None:
        base = self._rows.one(
            "intelligence.training_recommendation",
            where={"recommendation_id": object_id},
            columns=(
                "recommendation_id",
                "subject_id",
                "recommendation_spec_id",
                "recommendation_spec_version",
                "rationale",
                "source_gap_refs",
                "proposed_training_items",
                "status",
                "approval_state",
                "created_at",
            ),
        )
        if base is None:
            return None
        revision = self._rows.one(
            "intelligence.training_recommendation_revision",
            where={"recommendation_id": object_id},
            columns=(
                "subject_key",
                "source_forecast_result_ids",
                "source_counterfactual_run_ids",
                "objective_constraints",
                "allowed_action_space",
                "applicability_status",
                "uncertainty",
                "reviewer_subject_key",
                "audit_ref",
                "supersedes_recommendation_id",
                "logical_content_hash",
            ),
        )
        if revision is None:
            raise P6PersistenceError(
                "P6_RECOMMENDATION_REVISION_METADATA_MISSING",
                object_id,
            )
        return P6RecommendationRevision(
            recommendation_id=str(base["recommendation_id"]),
            subject_key=str(revision["subject_key"]),
            subject_id=str(base["subject_id"]),
            recommendation_spec_id=str(
                base["recommendation_spec_id"]
            ),
            recommendation_spec_version=str(
                base["recommendation_spec_version"]
            ),
            source_forecast_result_ids=_strings(
                revision["source_forecast_result_ids"],
                "training_recommendation_revision."
                "source_forecast_result_ids",
            ),
            source_counterfactual_run_ids=_strings(
                revision["source_counterfactual_run_ids"],
                "training_recommendation_revision."
                "source_counterfactual_run_ids",
            ),
            objective_constraints=_mapping(
                revision["objective_constraints"],
                "training_recommendation_revision."
                "objective_constraints",
            ),
            allowed_action_space=_mapping(
                revision["allowed_action_space"],
                "training_recommendation_revision."
                "allowed_action_space",
            ),
            rationale=_mapping(
                base["rationale"],
                "training_recommendation.rationale",
            ),
            source_gap_refs=_strings(
                base["source_gap_refs"],
                "training_recommendation.source_gap_refs",
            ),
            proposed_training_items=_mapping(
                base["proposed_training_items"],
                "training_recommendation.proposed_training_items",
            ),
            applicability_status=str(
                revision["applicability_status"]
            ),
            uncertainty=_mapping(
                revision["uncertainty"],
                "training_recommendation_revision.uncertainty",
            ),
            status=str(base["status"]),
            approval_state=str(base["approval_state"]),
            reviewer_subject_key=_optional_text(
                revision["reviewer_subject_key"]
            ),
            audit_ref=_optional_text(revision["audit_ref"]),
            created_at=_time_text(base["created_at"]),
            supersedes_recommendation_id=_optional_text(
                revision["supersedes_recommendation_id"]
            ),
            logical_content_hash=str(revision["logical_content_hash"]),
        )

    def _exact_recommendation_checked(
        self,
        object_id: str,
        visited: frozenset[str],
    ) -> P6RecommendationRevision:
        value = self._try_recommendation(object_id)
        if value is None:
            raise P6PersistenceError(
                "M9_RECOMMENDATION_NOT_FOUND",
                object_id,
            )
        self._assert_recommendation_identity(value, visited)
        return value

    def exact_recommendation(
        self,
        object_id: str,
    ) -> P6RecommendationRevision:
        return self._exact_recommendation_checked(
            object_id,
            frozenset(),
        )

