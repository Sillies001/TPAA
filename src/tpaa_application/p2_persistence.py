"""PIQB B2 exact P2 mapping over canonical row and object-store ports."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from tpaa_assessment import (
    P1ObservationInput,
    P2AdjustedCapabilityEstimate,
    P2ArtifactBinding,
    P2AttributionRunProduct,
    P2AttributionSpec,
    P2CohortSnapshot,
    P2ExecutionProfile,
    P2FactorFeatureSet,
    P2InputBundle,
    P2ReferenceCondition,
    build_p2_input_bundle,
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


def _id_array(value: object, field: str) -> tuple[str, ...]:
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
        if not isinstance(item, (str, UUID)):
            raise P2PersistenceError("P2_DB_ARRAY_INVALID", field)
        result.append(str(item))
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


_P2_COHORT_WORKSPACE_SCHEMA = "TPAA_P2_COHORT_WORKSPACE_V1"


@dataclass(frozen=True, slots=True)
class P2DurableWorkspaceMaterial:
    """Exact DB/object material required to rebuild one M6 read workspace."""

    p2_release_id: str
    p2_release_status: str
    p2_release_sealed: bool
    p2_published_at_utc: str
    input_bundle: P2InputBundle
    target_feature_set: P2FactorFeatureSet
    attribution_run: P2AttributionRunProduct
    adjusted_estimate: P2AdjustedCapabilityEstimate
    model_artifact_json: str | None


def _required_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise P2PersistenceError("P2_DB_INTEGER_INVALID", field)
    return value


def _bool_value(value: object, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    raise P2PersistenceError("P2_DB_BOOLEAN_INVALID", field)


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

    def _artifact_binding(
        self,
        context_artifact_id: str,
    ) -> P2ArtifactBinding:
        row = self._rows.one(
            "registry.context_artifact",
            where={"context_artifact_id": context_artifact_id},
            columns=(
                "context_artifact_id",
                "artifact_kind",
                "logical_key",
                "artifact_version",
                "object_ref_id",
                "artifact_sha256",
                "schema_version",
                "status",
            ),
        )
        if row is None:
            raise P2PersistenceError(
                "P2_CONTEXT_ARTIFACT_NOT_FOUND",
                context_artifact_id,
            )
        object_ref_id = str(row["object_ref_id"])
        object_row = self._rows.one(
            "registry.object_reference",
            where={"object_ref_id": object_ref_id},
            columns=(
                "object_ref_id",
                "artifact_sha256",
                "sealed",
                "gc_state",
                "deleted_at",
            ),
        )
        if object_row is None:
            raise P2PersistenceError(
                "P2_CONTEXT_OBJECT_NOT_FOUND",
                object_ref_id,
            )
        artifact_sha256 = str(row["artifact_sha256"])
        if (
            str(object_row["artifact_sha256"]) != artifact_sha256
            or not _bool_value(object_row["sealed"], "object_reference.sealed")
            or str(object_row["gc_state"]) != "ACTIVE"
            or object_row["deleted_at"] is not None
        ):
            raise P2PersistenceError(
                "P2_CONTEXT_OBJECT_INVALID",
                object_ref_id,
            )
        return P2ArtifactBinding(
            context_artifact_id=str(row["context_artifact_id"]),
            object_ref_id=object_ref_id,
            artifact_kind=str(row["artifact_kind"]),
            logical_key=str(row["logical_key"]),
            artifact_version=str(row["artifact_version"]),
            schema_version=str(row["schema_version"]),
            artifact_sha256=artifact_sha256,
            status=str(row["status"]),
            sealed=True,
        )

    def _artifact_binding_by_logical_key(
        self,
        logical_key: str,
        artifact_version: str,
    ) -> P2ArtifactBinding:
        rows = self._rows.many(
            "registry.context_artifact",
            where={
                "logical_key": logical_key,
                "artifact_version": artifact_version,
            },
            columns=("context_artifact_id",),
            order_by=("context_artifact_id",),
        )
        if len(rows) != 1:
            raise P2PersistenceError(
                "P2_CONTEXT_ARTIFACT_CARDINALITY",
                f"{logical_key}:{artifact_version}:{len(rows)}",
            )
        return self._artifact_binding(str(rows[0]["context_artifact_id"]))

    def _p1_observation(self, observation_id: str) -> P1ObservationInput:
        row = self._rows.one(
            "metric.capability_observation",
            where={"observation_id": observation_id},
            columns=(
                "observation_id",
                "release_id",
                "episode_id",
                "subject_entity_id",
                "aircraft_id",
                "aircraft_model_id",
                "aircraft_configuration_snapshot_id",
                "context_id",
                "capability_type",
                "observed_metric_instance_id",
                "observed_value_numeric",
                "unit",
                "evidence_set_id",
                "coverage",
                "confidence",
                "eligibility_status",
                "comparison_key_hash",
                "created_at",
            ),
        )
        if row is None:
            raise P2PersistenceError(
                "P2_SOURCE_OBSERVATION_NOT_FOUND",
                observation_id,
            )
        metric_instance_id = str(row["observed_metric_instance_id"])
        instance = self._rows.one(
            "metric.metric_instance",
            where={"metric_instance_id": metric_instance_id},
            columns=("metric_definition_id",),
        )
        if instance is None:
            raise P2PersistenceError(
                "P2_SOURCE_METRIC_INSTANCE_NOT_FOUND",
                metric_instance_id,
            )
        definition = self._rows.one(
            "metric.metric_definition",
            where={"metric_definition_id": str(instance["metric_definition_id"])},
            columns=("metric_semantic_id", "metric_semantic_version"),
        )
        if definition is None:
            raise P2PersistenceError(
                "P2_SOURCE_METRIC_DEFINITION_NOT_FOUND",
                metric_instance_id,
            )
        release_id = str(row["release_id"])
        release = self._rows.one(
            "registry.analysis_release",
            where={"release_id": release_id},
            columns=("status", "manifest_hash", "published_at"),
        )
        if release is None or release["published_at"] is None:
            raise P2PersistenceError(
                "P2_SOURCE_RELEASE_NOT_FOUND",
                release_id,
            )
        manifest_hash = str(release["manifest_hash"])
        observed_value = _required_float(
            row["observed_value_numeric"],
            "capability_observation.observed_value_numeric",
        )
        return P1ObservationInput(
            observation_id=str(row["observation_id"]),
            release_id=release_id,
            release_status=str(release["status"]),
            release_sealed=(
                str(release["status"]) == "PUBLISHED"
                and len(manifest_hash) == 64
                and all(ch in "0123456789abcdef" for ch in manifest_hash)
            ),
            episode_id=str(row["episode_id"]),
            subject_entity_id=str(row["subject_entity_id"]),
            aircraft_id=str(row["aircraft_id"]),
            aircraft_model_id=str(row["aircraft_model_id"]),
            aircraft_configuration_snapshot_id=_optional_text(
                row["aircraft_configuration_snapshot_id"]
            ),
            context_id=str(row["context_id"]),
            capability_type=str(row["capability_type"]),
            metric_semantic_id=str(definition["metric_semantic_id"]),
            metric_semantic_version=_required_int(
                definition["metric_semantic_version"],
                "metric_definition.metric_semantic_version",
            ),
            comparison_key_hash=str(row["comparison_key_hash"]),
            evidence_set_id=str(row["evidence_set_id"]),
            observed_value=observed_value,
            unit=str(row["unit"]),
            coverage=_required_float(row["coverage"], "capability_observation.coverage"),
            confidence=_required_float(
                row["confidence"],
                "capability_observation.confidence",
            ),
            eligibility_status=str(row["eligibility_status"]),
            knowledge_time_utc=_time_text(row["created_at"]),
        )

    def register_workspace_inputs(
        self,
        bundle: P2InputBundle,
        target_feature_set: P2FactorFeatureSet,
    ) -> None:
        """Persist P2 workspace membership using existing DB 1.9 authorities."""

        if self._p1_observation(bundle.target.observation_id) != bundle.target:
            raise P2PersistenceError(
                "P2_WORKSPACE_TARGET_MISMATCH",
                bundle.target.observation_id,
            )
        for binding in (
            bundle.feature_spec,
            bundle.reference_condition.binding,
            bundle.attribution_spec.binding,
        ):
            if self._artifact_binding(binding.context_artifact_id) != binding:
                raise P2PersistenceError(
                    "P2_WORKSPACE_ARTIFACT_MISMATCH",
                    binding.context_artifact_id,
                )
        if target_feature_set.source_observation_id != bundle.target.observation_id:
            raise P2PersistenceError(
                "P2_WORKSPACE_FEATURE_SOURCE_MISMATCH",
                target_feature_set.factor_feature_set_id,
            )
        feature_row = self._rows.one(
            "assessment.factor_feature_set",
            where={"factor_feature_set_id": target_feature_set.factor_feature_set_id},
            columns=(
                "factor_feature_set_id",
                "feature_spec_id",
                "feature_spec_version",
                "source_observation_id",
                "reference_condition_id",
                "feature_values",
                "missing_mask",
                "world_refs",
                "coverage",
                "confidence",
                "input_hash",
                "created_at",
            ),
        )
        if feature_row is None:
            self._rows.insert(
                "assessment.factor_feature_set",
                target_feature_set.as_record(),
                field_kinds={
                    "feature_values": "json",
                    "missing_mask": "json",
                    "world_refs": "uuid_array",
                },
            )
        elif self.exact_factor_feature_set(
            target_feature_set.factor_feature_set_id
        ) != target_feature_set:
            raise P2PersistenceError(
                "P2_WORKSPACE_FEATURE_IMMUTABLE_CONFLICT",
                target_feature_set.factor_feature_set_id,
            )

        manifest = {
            "schema": _P2_COHORT_WORKSPACE_SCHEMA,
            "cohort_spec_id": bundle.cohort.cohort_spec_id,
            "cohort_spec_version": bundle.cohort.cohort_spec_version,
            "comparability_dimensions": [
                {"name": name, "value": value}
                for name, value in bundle.cohort.comparability_dimensions
            ],
            "knowledge_cutoff_utc": bundle.cohort.knowledge_cutoff_utc,
            "raw_record_count": bundle.cohort.raw_record_count,
            "observation_count": bundle.cohort.observation_count,
            "independent_subject_count": bundle.cohort.independent_subject_count,
            "effective_evidence_count": bundle.cohort.effective_evidence_count,
            "observation_ids": list(bundle.cohort.observation_ids),
            "episode_ids": list(bundle.cohort.episode_ids),
            "subject_ids": list(bundle.cohort.subject_ids),
            "workspace": {
                "target_observation_id": bundle.target.observation_id,
                "target_feature_set_id": target_feature_set.factor_feature_set_id,
                "feature_spec_context_artifact_id": bundle.feature_spec.context_artifact_id,
                "reference_condition_id": (
                    bundle.reference_condition.reference_condition_id
                ),
                "attribution_spec_context_artifact_id": (
                    bundle.attribution_spec.binding.context_artifact_id
                ),
                "as_of_utc": bundle.as_of_utc,
                "input_hash": bundle.input_hash,
            },
        }
        existing = self._rows.one(
            "registry.dataset_snapshot",
            where={"dataset_snapshot_id": bundle.cohort.dataset_snapshot_id},
            columns=(
                "snapshot_type",
                "query_or_manifest",
                "input_refs",
                "data_hash",
                "schema_version",
                "frozen",
            ),
        )
        if existing is None:
            self._rows.insert(
                "registry.dataset_snapshot",
                {
                    "dataset_snapshot_id": bundle.cohort.dataset_snapshot_id,
                    "snapshot_type": bundle.cohort.snapshot_type,
                    "query_or_manifest": manifest,
                    "input_refs": bundle.cohort.observation_ids,
                    "data_hash": bundle.cohort.data_hash,
                    "schema_version": bundle.cohort.schema_version,
                    "created_at": bundle.cohort.knowledge_cutoff_utc,
                    "frozen": bundle.cohort.frozen,
                },
                field_kinds={
                    "query_or_manifest": "json",
                    "input_refs": "uuid_array",
                },
            )
        else:
            if (
                str(existing["snapshot_type"]) != bundle.cohort.snapshot_type
                or _json_object(
                    existing["query_or_manifest"],
                    "dataset_snapshot.query_or_manifest",
                )
                != manifest
                or _text_array(
                    existing["input_refs"],
                    "dataset_snapshot.input_refs",
                )
                != bundle.cohort.observation_ids
                or str(existing["data_hash"]) != bundle.cohort.data_hash
                or str(existing["schema_version"]) != bundle.cohort.schema_version
                or _bool_value(existing["frozen"], "dataset_snapshot.frozen")
                != bundle.cohort.frozen
            ):
                raise P2PersistenceError(
                    "P2_WORKSPACE_COHORT_IMMUTABLE_CONFLICT",
                    bundle.cohort.dataset_snapshot_id,
                )

    def exact_factor_feature_set(
        self,
        factor_feature_set_id: str,
    ) -> P2FactorFeatureSet:
        row = self._rows.one(
            "assessment.factor_feature_set",
            where={"factor_feature_set_id": factor_feature_set_id},
            columns=(
                "factor_feature_set_id",
                "feature_spec_id",
                "feature_spec_version",
                "source_observation_id",
                "reference_condition_id",
                "feature_values",
                "missing_mask",
                "world_refs",
                "coverage",
                "confidence",
                "input_hash",
                "created_at",
            ),
        )
        if row is None:
            raise P2PersistenceError(
                "P2_FACTOR_FEATURE_SET_NOT_FOUND",
                factor_feature_set_id,
            )
        features = _json_object(
            row["feature_values"],
            "factor_feature_set.feature_values",
        )
        missing = _json_object(
            row["missing_mask"],
            "factor_feature_set.missing_mask",
        )
        if tuple(features) != tuple(missing):
            raise P2PersistenceError(
                "P2_FACTOR_FEATURE_SHAPE_MISMATCH",
                factor_feature_set_id,
            )
        feature_values: list[tuple[str, float | None]] = []
        missing_mask: list[tuple[str, bool]] = []
        for name, raw in features.items():
            feature_values.append((name, _optional_float(raw)))
            flag = missing[name]
            if not isinstance(flag, bool):
                raise P2PersistenceError(
                    "P2_FACTOR_FEATURE_MASK_INVALID",
                    name,
                )
            missing_mask.append((name, flag))
        return P2FactorFeatureSet(
            factor_feature_set_id=str(row["factor_feature_set_id"]),
            feature_spec_id=str(row["feature_spec_id"]),
            feature_spec_version=str(row["feature_spec_version"]),
            source_observation_id=str(row["source_observation_id"]),
            reference_condition_id=_optional_text(row["reference_condition_id"]),
            feature_values=tuple(feature_values),
            missing_mask=tuple(missing_mask),
            world_refs=_id_array(row["world_refs"], "factor_feature_set.world_refs"),
            coverage=_required_float(row["coverage"], "factor_feature_set.coverage"),
            confidence=_required_float(
                row["confidence"],
                "factor_feature_set.confidence",
            ),
            input_hash=str(row["input_hash"]),
            created_at=_time_text(row["created_at"]),
        )

    def _cohort_and_workspace(
        self,
        dataset_snapshot_id: str,
    ) -> tuple[P2CohortSnapshot, dict[str, object]]:
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
            raise P2PersistenceError(
                "P2_COHORT_SNAPSHOT_NOT_FOUND",
                dataset_snapshot_id,
            )
        manifest = _json_object(
            row["query_or_manifest"],
            "dataset_snapshot.query_or_manifest",
        )
        if manifest.get("schema") != _P2_COHORT_WORKSPACE_SCHEMA:
            raise P2PersistenceError(
                "P2_COHORT_WORKSPACE_MANIFEST_MISSING",
                dataset_snapshot_id,
            )
        raw_dimensions = manifest.get("comparability_dimensions")
        if not isinstance(raw_dimensions, list):
            raise P2PersistenceError(
                "P2_COHORT_WORKSPACE_MANIFEST_INVALID",
                "comparability_dimensions",
            )
        dimensions: list[tuple[str, str | int]] = []
        for raw in raw_dimensions:
            if not isinstance(raw, dict):
                raise P2PersistenceError(
                    "P2_COHORT_WORKSPACE_MANIFEST_INVALID",
                    "comparability_dimensions",
                )
            name = raw.get("name")
            value = raw.get("value")
            if (
                not isinstance(name, str)
                or not isinstance(value, (str, int))
                or isinstance(value, bool)
            ):
                raise P2PersistenceError(
                    "P2_COHORT_WORKSPACE_MANIFEST_INVALID",
                    "comparability_dimensions",
                )
            dimensions.append((name, value))
        def strings(field: str) -> tuple[str, ...]:
            raw = manifest.get(field)
            if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
                raise P2PersistenceError(
                    "P2_COHORT_WORKSPACE_MANIFEST_INVALID",
                    field,
                )
            return tuple(raw)
        cohort = P2CohortSnapshot(
            dataset_snapshot_id=str(row["dataset_snapshot_id"]),
            snapshot_type=str(row["snapshot_type"]),
            data_hash=str(row["data_hash"]),
            schema_version=str(row["schema_version"]),
            frozen=_bool_value(row["frozen"], "dataset_snapshot.frozen"),
            cohort_spec_id=str(manifest["cohort_spec_id"]),
            cohort_spec_version=str(manifest["cohort_spec_version"]),
            comparability_dimensions=tuple(dimensions),
            knowledge_cutoff_utc=str(manifest["knowledge_cutoff_utc"]),
            raw_record_count=_required_int(
                manifest["raw_record_count"],
                "cohort.raw_record_count",
            ),
            observation_count=_required_int(
                manifest["observation_count"],
                "cohort.observation_count",
            ),
            independent_subject_count=_required_int(
                manifest["independent_subject_count"],
                "cohort.independent_subject_count",
            ),
            effective_evidence_count=_required_float(
                manifest["effective_evidence_count"],
                "cohort.effective_evidence_count",
            ),
            observation_ids=strings("observation_ids"),
            episode_ids=strings("episode_ids"),
            subject_ids=strings("subject_ids"),
        )
        if _id_array(row["input_refs"], "dataset_snapshot.input_refs") != cohort.observation_ids:
            raise P2PersistenceError(
                "P2_COHORT_INPUT_REFS_MISMATCH",
                dataset_snapshot_id,
            )
        workspace = manifest.get("workspace")
        if not isinstance(workspace, dict):
            raise P2PersistenceError(
                "P2_COHORT_WORKSPACE_MANIFEST_INVALID",
                "workspace",
            )
        return cohort, {str(key): value for key, value in workspace.items()}

    def exact_workspace_material(
        self,
        estimate_id: str,
    ) -> P2DurableWorkspaceMaterial:
        estimate = self.exact_adjusted_estimate(estimate_id)
        run = self.exact_attribution_run(estimate.attribution_run_id)
        cohort, workspace = self._cohort_and_workspace(
            run.training_dataset_snapshot_id
        )
        target_id = workspace.get("target_observation_id")
        feature_set_id = workspace.get("target_feature_set_id")
        feature_artifact_id = workspace.get("feature_spec_context_artifact_id")
        reference_id = workspace.get("reference_condition_id")
        attribution_artifact_id = workspace.get(
            "attribution_spec_context_artifact_id"
        )
        as_of_utc = workspace.get("as_of_utc")
        input_hash = workspace.get("input_hash")
        if not all(
            isinstance(item, str) and item
            for item in (
                target_id,
                feature_set_id,
                feature_artifact_id,
                reference_id,
                attribution_artifact_id,
                as_of_utc,
                input_hash,
            )
        ):
            raise P2PersistenceError(
                "P2_COHORT_WORKSPACE_MANIFEST_INVALID",
                estimate_id,
            )
        assert isinstance(target_id, str)
        assert isinstance(feature_set_id, str)
        assert isinstance(feature_artifact_id, str)
        assert isinstance(reference_id, str)
        assert isinstance(attribution_artifact_id, str)
        assert isinstance(as_of_utc, str)
        assert isinstance(input_hash, str)

        target = self._p1_observation(target_id)
        if (
            target.observation_id != estimate.source_observation_id
            or target.release_id != estimate.source_release_id
        ):
            raise P2PersistenceError(
                "P2_WORKSPACE_TARGET_MISMATCH",
                estimate_id,
            )
        feature_spec = self._artifact_binding(feature_artifact_id)
        reference_binding = self._artifact_binding(reference_id)
        attribution_binding = self._artifact_binding(attribution_artifact_id)
        diagnostics = run.diagnostics()
        uncertainty_method = diagnostics.get("uncertainty_method")
        uncertainty_level = diagnostics.get("uncertainty_level")
        if not isinstance(uncertainty_method, str) or not isinstance(
            uncertainty_level,
            str,
        ):
            raise P2PersistenceError(
                "P2_RUN_DIAGNOSTICS_INCOMPLETE",
                run.attribution_run_id,
            )
        attribution_spec = P2AttributionSpec(
            attribution_spec_id=run.attribution_spec_id,
            attribution_spec_version=run.attribution_spec_version,
            model_plugin=run.model_plugin,
            model_plugin_version=run.model_plugin_version,
            uncertainty_method=uncertainty_method,
            uncertainty_level=uncertainty_level,
            binding=attribution_binding,
        )
        bundle = build_p2_input_bundle(
            target=target,
            feature_spec=feature_spec,
            reference_condition=P2ReferenceCondition(
                reference_condition_id=reference_id,
                binding=reference_binding,
            ),
            cohort=cohort,
            attribution_spec=attribution_spec,
            as_of_utc=as_of_utc,
        )
        if bundle.input_hash != input_hash:
            raise P2PersistenceError(
                "P2_WORKSPACE_INPUT_HASH_MISMATCH",
                estimate_id,
            )
        feature = self.exact_factor_feature_set(feature_set_id)
        if (
            feature.feature_spec_id != feature_spec.logical_key
            or feature.feature_spec_version != feature_spec.artifact_version
            or feature.reference_condition_id != reference_id
        ):
            raise P2PersistenceError(
                "P2_WORKSPACE_FEATURE_BINDING_MISMATCH",
                estimate_id,
            )
        release = self._rows.one(
            "registry.analysis_release",
            where={"release_id": estimate.p2_release_id},
            columns=("status", "manifest_hash", "published_at"),
        )
        if release is None or release["published_at"] is None:
            raise P2PersistenceError(
                "P2_RELEASE_NOT_FOUND",
                estimate.p2_release_id,
            )
        release_manifest = str(release["manifest_hash"])
        release_sealed = (
            str(release["status"]) == "PUBLISHED"
            and len(release_manifest) == 64
            and all(ch in "0123456789abcdef" for ch in release_manifest)
        )

        model_artifact_json: str | None = None
        if run.model_artifact_hash is not None:
            if run.model_artifact_uri is None or self._object_store is None:
                raise P2PersistenceError(
                    "P2_MODEL_ARTIFACT_REQUIRED",
                    run.attribution_run_id,
                )
            data = self._object_store.read_bytes(run.model_artifact_uri)
            if hashlib.sha256(data).hexdigest() != run.model_artifact_hash:
                raise P2PersistenceError(
                    "P2_MODEL_ARTIFACT_HASH_MISMATCH",
                    run.attribution_run_id,
                )
            try:
                model_artifact_json = data.decode("ascii")
                decoded: object = json.loads(model_artifact_json)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise P2PersistenceError(
                    "P2_MODEL_ARTIFACT_INVALID",
                    run.attribution_run_id,
                ) from exc
            if not isinstance(decoded, dict) or _canonical_json(decoded) != model_artifact_json:
                raise P2PersistenceError(
                    "P2_MODEL_ARTIFACT_INVALID",
                    run.attribution_run_id,
                )

        return P2DurableWorkspaceMaterial(
            p2_release_id=estimate.p2_release_id,
            p2_release_status=str(release["status"]),
            p2_release_sealed=release_sealed,
            p2_published_at_utc=_time_text(release["published_at"]),
            input_bundle=bundle,
            target_feature_set=feature,
            attribution_run=run,
            adjusted_estimate=estimate,
            model_artifact_json=model_artifact_json,
        )
