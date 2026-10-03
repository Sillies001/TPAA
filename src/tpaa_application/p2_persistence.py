"""PIQB B2 exact P2 mapping over canonical row and object-store ports."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

from tpaa_assessment import (
    P2AdjustedCapabilityEstimate,
    P2AttributionRunProduct,
    P2ExecutionProfile,
)
from tpaa_storage.canonical_rows import CanonicalRowRepository
from tpaa_storage.object_store import LocalObjectStore


class P2PersistenceError(RuntimeError):
    """Fail-closed P2 exact persistence error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("ascii")).hexdigest()


def _json_object(value: object, field: str) -> dict[str, object]:
    decoded: object = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise P2PersistenceError("P2_DB_JSON_INVALID", field) from exc
    if not isinstance(decoded, dict):
        raise P2PersistenceError("P2_DB_JSON_INVALID", field)
    return {str(key): item for key, item in decoded.items()}


def _text_array(value: object, field: str) -> tuple[str, ...]:
    decoded: object = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise P2PersistenceError("P2_DB_ARRAY_INVALID", field) from exc
    if not isinstance(decoded, (list, tuple)):
        raise P2PersistenceError("P2_DB_ARRAY_INVALID", field)
    result: list[str] = []
    for item in decoded:
        if not isinstance(item, str):
            raise P2PersistenceError("P2_DB_ARRAY_INVALID", field)
        result.append(item)
    return tuple(result)


def _time_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        normalized = value
        if normalized.tzinfo is not None:
            normalized = normalized.astimezone(UTC)
        return normalized.isoformat().replace("+00:00", "Z")
    raise P2PersistenceError("P2_DB_TIME_INVALID", type(value).__name__)


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise P2PersistenceError("P2_DB_NUMERIC_INVALID", "bool")
    if isinstance(value, (int, float, Decimal, str)):
        return float(value)
    raise P2PersistenceError("P2_DB_NUMERIC_INVALID", type(value).__name__)


def _required_float(value: object, field: str) -> float:
    result = _optional_float(value)
    if result is None:
        raise P2PersistenceError("P2_DB_NUMERIC_INVALID", field)
    return result


def _estimate_logical_hash(
    estimate: P2AdjustedCapabilityEstimate,
    *,
    model_artifact_hash: str | None,
    profile: P2ExecutionProfile,
) -> str:
    if estimate.status == "NOT_IDENTIFIABLE":
        return _canonical_hash(
            {
                "source_observation_id": estimate.source_observation_id,
                "source_release_id": estimate.source_release_id,
                "p2_release_id": estimate.p2_release_id,
                "attribution_run_id": estimate.attribution_run_id,
                "reference_condition_id": estimate.reference_condition_id,
                "status": estimate.status,
                "reason_codes": list(estimate.reason_codes),
                "claim_level": estimate.claim_level,
                "evidence_set_id": estimate.evidence_set_id,
            }
        )
    if estimate.status != "IDENTIFIABLE" or model_artifact_hash is None:
        raise P2PersistenceError(
            "P2_IDENTIFIABLE_ESTIMATE_INCOMPLETE",
            estimate.estimate_id,
        )

    def q(value: float | None) -> str:
        if value is None:
            raise P2PersistenceError(
                "P2_IDENTIFIABLE_ESTIMATE_INCOMPLETE",
                estimate.estimate_id,
            )
        return profile.qstr(Decimal(str(value)))

    return _canonical_hash(
        {
            "source_observation_id": estimate.source_observation_id,
            "source_release_id": estimate.source_release_id,
            "p2_release_id": estimate.p2_release_id,
            "attribution_run_id": estimate.attribution_run_id,
            "reference_condition_id": estimate.reference_condition_id,
            "adjusted_value": q(estimate.adjusted_value),
            "unit": estimate.unit,
            "uncertainty_lower": q(estimate.uncertainty_lower),
            "uncertainty_upper": q(estimate.uncertainty_upper),
            "residual": q(estimate.residual),
            "factor_effects": [
                {"factor": factor, "effect": q(value)}
                for factor, value in estimate.factor_effects
            ],
            "claim_level": estimate.claim_level,
            "status": estimate.status,
            "reason_codes": list(estimate.reason_codes),
            "evidence_set_id": estimate.evidence_set_id,
            "model_artifact_hash": model_artifact_hash,
        }
    )


class P2PersistenceRepository:
    """Engine-neutral P2 mapper; SQL/driver behavior remains in Storage."""

    def __init__(
        self,
        rows: CanonicalRowRepository,
        *,
        object_store: LocalObjectStore | None = None,
    ) -> None:
        self._rows = rows
        self._object_store = object_store

    def _artifact_factor_order(
        self,
        run: P2AttributionRunProduct,
        factor_effects: dict[str, object],
    ) -> tuple[str, ...]:
        if not factor_effects:
            return ()
        if run.model_artifact_uri is None or run.model_artifact_hash is None:
            raise P2PersistenceError(
                "P2_MODEL_ARTIFACT_REQUIRED",
                run.attribution_run_id,
            )
        if self._object_store is None:
            raise P2PersistenceError(
                "P2_OBJECT_STORE_REQUIRED",
                run.attribution_run_id,
            )
        data = self._object_store.read_bytes(run.model_artifact_uri)
        if hashlib.sha256(data).hexdigest() != run.model_artifact_hash:
            raise P2PersistenceError(
                "P2_MODEL_ARTIFACT_HASH_MISMATCH",
                run.attribution_run_id,
            )
        try:
            payload: object = json.loads(data.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise P2PersistenceError(
                "P2_MODEL_ARTIFACT_INVALID",
                run.attribution_run_id,
            ) from exc
        if not isinstance(payload, dict):
            raise P2PersistenceError(
                "P2_MODEL_ARTIFACT_INVALID",
                run.attribution_run_id,
            )
        order = payload.get("factor_order")
        if not isinstance(order, list):
            raise P2PersistenceError(
                "P2_MODEL_FACTOR_ORDER_MISMATCH",
                run.attribution_run_id,
            )
        result: list[str] = []
        for item in order:
            if not isinstance(item, str):
                raise P2PersistenceError(
                    "P2_MODEL_FACTOR_ORDER_MISMATCH",
                    run.attribution_run_id,
                )
            result.append(item)
        if set(result) != set(factor_effects) or len(result) != len(factor_effects):
            raise P2PersistenceError(
                "P2_MODEL_FACTOR_ORDER_MISMATCH",
                run.attribution_run_id,
            )
        return tuple(result)

    def register_attribution_run(
        self,
        value: P2AttributionRunProduct,
        *,
        compute_job_id: str | None = None,
    ) -> None:
        current = self._try_exact_attribution_run(value.attribution_run_id)
        if current is not None:
            if current != value:
                raise P2PersistenceError(
                    "P2_IMMUTABLE_CONFLICT",
                    value.attribution_run_id,
                )
            return
        diagnostics = value.diagnostics()
        if diagnostics.get("run_request_hash") != value.run_request_hash:
            raise P2PersistenceError(
                "P2_RUN_REQUEST_HASH_MISMATCH",
                value.attribution_run_id,
            )
        self._rows.insert(
            "assessment.attribution_run",
            {
                "attribution_run_id": value.attribution_run_id,
                "attribution_spec_id": value.attribution_spec_id,
                "attribution_spec_version": value.attribution_spec_version,
                "model_plugin": value.model_plugin,
                "model_plugin_version": value.model_plugin_version,
                "training_dataset_snapshot_id": value.training_dataset_snapshot_id,
                "reference_condition_id": value.reference_condition_id,
                "status": value.status,
                "diagnostics": diagnostics,
                "model_artifact_uri": value.model_artifact_uri,
                "model_artifact_hash": value.model_artifact_hash,
                "started_at": value.started_at,
                "completed_at": value.completed_at,
                "created_by": value.created_by,
            },
            field_kinds={"diagnostics": "json"},
        )
        self._rows.insert(
            "assessment.attribution_run_request_binding",
            {
                "attribution_run_id": value.attribution_run_id,
                "run_request_hash": value.run_request_hash,
                "compute_job_id": compute_job_id,
            },
        )

    def _try_exact_attribution_run(
        self,
        attribution_run_id: str,
    ) -> P2AttributionRunProduct | None:
        columns = (
            "attribution_run_id",
            "attribution_spec_id",
            "attribution_spec_version",
            "model_plugin",
            "model_plugin_version",
            "training_dataset_snapshot_id",
            "reference_condition_id",
            "status",
            "diagnostics",
            "model_artifact_uri",
            "model_artifact_hash",
            "started_at",
            "completed_at",
            "created_by",
        )
        row = self._rows.one(
            "assessment.attribution_run",
            where={"attribution_run_id": attribution_run_id},
            columns=columns,
        )
        if row is None:
            return None
        binding = self._rows.one(
            "assessment.attribution_run_request_binding",
            where={"attribution_run_id": attribution_run_id},
            columns=("run_request_hash",),
        )
        if binding is None:
            raise P2PersistenceError(
                "P2_RUN_REQUEST_BINDING_MISSING",
                attribution_run_id,
            )
        diagnostics = _json_object(row["diagnostics"], "attribution_run.diagnostics")
        value = P2AttributionRunProduct(
            attribution_run_id=str(row["attribution_run_id"]),
            attribution_spec_id=str(row["attribution_spec_id"]),
            attribution_spec_version=str(row["attribution_spec_version"]),
            model_plugin=str(row["model_plugin"]),
            model_plugin_version=str(row["model_plugin_version"]),
            training_dataset_snapshot_id=str(row["training_dataset_snapshot_id"]),
            reference_condition_id=str(row["reference_condition_id"]),
            status=str(row["status"]),
            diagnostics_json=_canonical_json(diagnostics),
            model_artifact_uri=_optional_text(row["model_artifact_uri"]),
            model_artifact_hash=_optional_text(row["model_artifact_hash"]),
            started_at=_time_text(row["started_at"]),
            completed_at=_time_text(row["completed_at"]),
            created_by=_optional_text(row["created_by"]),
            run_request_hash=str(binding["run_request_hash"]),
        )
        if diagnostics.get("run_request_hash") != value.run_request_hash:
            raise P2PersistenceError(
                "P2_RUN_REQUEST_HASH_MISMATCH",
                attribution_run_id,
            )
        return value

    def exact_attribution_run(
        self,
        attribution_run_id: str,
    ) -> P2AttributionRunProduct:
        value = self._try_exact_attribution_run(attribution_run_id)
        if value is None:
            raise P2PersistenceError(
                "P2_ATTRIBUTION_RUN_NOT_FOUND",
                attribution_run_id,
            )
        return value

    def register_adjusted_estimate(
        self,
        value: P2AdjustedCapabilityEstimate,
    ) -> None:
        current = self._try_exact_adjusted_estimate(value.estimate_id)
        if current is not None:
            if current != value:
                raise P2PersistenceError("P2_IMMUTABLE_CONFLICT", value.estimate_id)
            return
        profile = P2ExecutionProfile.from_canonical()
        if (
            value.uncertainty_method != profile.uncertainty_method
            or value.uncertainty_level != profile.uncertainty_level
        ):
            raise P2PersistenceError(
                "P2_UNCERTAINTY_PROFILE_MISMATCH",
                value.estimate_id,
            )
        run = self.exact_attribution_run(value.attribution_run_id)
        diagnostics = run.diagnostics()
        reasons = _text_array(
            diagnostics.get("reason_codes", []),
            "run.reason_codes",
        )
        if run.status != value.status or reasons != value.reason_codes:
            raise P2PersistenceError(
                "P2_RUN_ESTIMATE_SEMANTICS_MISMATCH",
                value.estimate_id,
            )
        observation = self._rows.one(
            "metric.capability_observation",
            where={"observation_id": value.source_observation_id},
            columns=("release_id",),
        )
        if observation is None or str(observation["release_id"]) != value.source_release_id:
            raise P2PersistenceError(
                "P2_SOURCE_RELEASE_MISMATCH",
                value.estimate_id,
            )
        if _estimate_logical_hash(
            value,
            model_artifact_hash=run.model_artifact_hash,
            profile=profile,
        ) != value.logical_hash:
            raise P2PersistenceError(
                "P2_LOGICAL_HASH_MISMATCH",
                value.estimate_id,
            )
        self._rows.insert(
            "capability.adjusted_capability_estimate",
            {
                "estimate_id": value.estimate_id,
                "source_observation_id": value.source_observation_id,
                "attribution_run_id": value.attribution_run_id,
                "aircraft_id": value.aircraft_id,
                "capability_type": value.capability_type,
                "reference_condition_id": value.reference_condition_id,
                "adjusted_value": value.adjusted_value,
                "unit": value.unit,
                "uncertainty_lower": value.uncertainty_lower,
                "uncertainty_upper": value.uncertainty_upper,
                "residual": value.residual,
                "factor_effects": dict(value.factor_effects),
                "claim_level": value.claim_level,
                "status": value.status,
                "evidence_set_id": value.evidence_set_id,
                "estimate_time": value.estimate_time,
                "created_at": value.created_at,
                "supersedes_estimate_id": value.supersedes_estimate_id,
            },
            field_kinds={"factor_effects": "json"},
        )
        self._rows.insert(
            "capability.adjusted_capability_estimate_revision",
            {
                "estimate_id": value.estimate_id,
                "p2_release_id": value.p2_release_id,
                "reason_codes": value.reason_codes,
            },
            field_kinds={"reason_codes": "text_array"},
        )

    def _try_exact_adjusted_estimate(
        self,
        estimate_id: str,
    ) -> P2AdjustedCapabilityEstimate | None:
        columns = (
            "estimate_id",
            "source_observation_id",
            "attribution_run_id",
            "aircraft_id",
            "capability_type",
            "reference_condition_id",
            "adjusted_value",
            "unit",
            "uncertainty_lower",
            "uncertainty_upper",
            "residual",
            "factor_effects",
            "claim_level",
            "status",
            "evidence_set_id",
            "estimate_time",
            "created_at",
            "supersedes_estimate_id",
        )
        row = self._rows.one(
            "capability.adjusted_capability_estimate",
            where={"estimate_id": estimate_id},
            columns=columns,
        )
        if row is None:
            return None
        revision = self._rows.one(
            "capability.adjusted_capability_estimate_revision",
            where={"estimate_id": estimate_id},
            columns=("p2_release_id", "reason_codes"),
        )
        if revision is None:
            raise P2PersistenceError(
                "P2_ESTIMATE_REVISION_MISSING",
                estimate_id,
            )
        observation = self._rows.one(
            "metric.capability_observation",
            where={"observation_id": row["source_observation_id"]},
            columns=("release_id",),
        )
        if observation is None:
            raise P2PersistenceError("P2_SOURCE_OBSERVATION_MISSING", estimate_id)
        run = self.exact_attribution_run(str(row["attribution_run_id"]))
        effects_raw = _json_object(row["factor_effects"], "estimate.factor_effects")
        order = self._artifact_factor_order(run, effects_raw)
        factor_effects = tuple(
            (factor, _required_float(effects_raw[factor], factor))
            for factor in order
        )
        profile = P2ExecutionProfile.from_canonical()
        draft = P2AdjustedCapabilityEstimate(
            estimate_id=str(row["estimate_id"]),
            source_observation_id=str(row["source_observation_id"]),
            source_release_id=str(observation["release_id"]),
            p2_release_id=str(revision["p2_release_id"]),
            attribution_run_id=str(row["attribution_run_id"]),
            aircraft_id=str(row["aircraft_id"]),
            capability_type=str(row["capability_type"]),
            reference_condition_id=str(row["reference_condition_id"]),
            adjusted_value=_optional_float(row["adjusted_value"]),
            unit=str(row["unit"]),
            uncertainty_lower=_optional_float(row["uncertainty_lower"]),
            uncertainty_upper=_optional_float(row["uncertainty_upper"]),
            uncertainty_method=profile.uncertainty_method,
            uncertainty_level=profile.uncertainty_level,
            residual=_optional_float(row["residual"]),
            factor_effects=factor_effects,
            claim_level=str(row["claim_level"]),
            status=str(row["status"]),
            reason_codes=_text_array(revision["reason_codes"], "estimate.reason_codes"),
            evidence_set_id=str(row["evidence_set_id"]),
            estimate_time=_time_text(row["estimate_time"]),
            created_at=_time_text(row["created_at"]),
            supersedes_estimate_id=_optional_text(row["supersedes_estimate_id"]),
            logical_hash="",
        )
        logical_hash = _estimate_logical_hash(
            draft,
            model_artifact_hash=run.model_artifact_hash,
            profile=profile,
        )
        return P2AdjustedCapabilityEstimate(
            estimate_id=draft.estimate_id,
            source_observation_id=draft.source_observation_id,
            source_release_id=draft.source_release_id,
            p2_release_id=draft.p2_release_id,
            attribution_run_id=draft.attribution_run_id,
            aircraft_id=draft.aircraft_id,
            capability_type=draft.capability_type,
            reference_condition_id=draft.reference_condition_id,
            adjusted_value=draft.adjusted_value,
            unit=draft.unit,
            uncertainty_lower=draft.uncertainty_lower,
            uncertainty_upper=draft.uncertainty_upper,
            uncertainty_method=draft.uncertainty_method,
            uncertainty_level=draft.uncertainty_level,
            residual=draft.residual,
            factor_effects=draft.factor_effects,
            claim_level=draft.claim_level,
            status=draft.status,
            reason_codes=draft.reason_codes,
            evidence_set_id=draft.evidence_set_id,
            estimate_time=draft.estimate_time,
            created_at=draft.created_at,
            supersedes_estimate_id=draft.supersedes_estimate_id,
            logical_hash=logical_hash,
        )

    def exact_adjusted_estimate(
        self,
        estimate_id: str,
    ) -> P2AdjustedCapabilityEstimate:
        value = self._try_exact_adjusted_estimate(estimate_id)
        if value is None:
            raise P2PersistenceError("P2_ADJUSTED_ESTIMATE_NOT_FOUND", estimate_id)
        return value
