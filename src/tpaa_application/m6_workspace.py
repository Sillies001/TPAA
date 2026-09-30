"""M6 exact-release P2 comparison and diagnostics Application projections."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from tpaa_assessment import (
    P1ObservationInput,
    P2AdjustedCapabilityEstimate,
    P2ArtifactBinding,
    P2AttributionRunProduct,
    P2AttributionSpec,
    P2CohortSnapshot,
    P2FactorFeatureSet,
    P2InputBundle,
    P2ReferenceCondition,
)

P2_IDENTIFIABLE = "IDENTIFIABLE"
P2_NOT_IDENTIFIABLE = "NOT_IDENTIFIABLE"


class M6ApplicationError(RuntimeError):
    """Fail-closed M6 read-model contract error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}:{detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class M6P2ComparisonQuery:
    p2_release_id: str
    estimate_id: str


@dataclass(frozen=True, slots=True)
class M6P2DiagnosticsQuery:
    p2_release_id: str
    estimate_id: str


@dataclass(frozen=True, slots=True)
class M6P2WorkspaceSnapshot:
    p2_release_id: str
    p2_release_status: str
    p2_release_sealed: bool
    p2_published_at_utc: str
    input_bundle: P2InputBundle
    target_feature_set: P2FactorFeatureSet
    attribution_run: P2AttributionRunProduct
    adjusted_estimate: P2AdjustedCapabilityEstimate
    model_artifact_json: str | None


def _uuid(value: str, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise M6ApplicationError("M6_DTO_UUID_INVALID", field) from exc
    if str(parsed) != value or parsed.int == 0:
        raise M6ApplicationError("M6_DTO_UUID_INVALID", field)
    return value


def _hash64(value: str, field: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise M6ApplicationError("M6_DTO_HASH_INVALID", field)
    return value


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _artifact(binding: P2ArtifactBinding) -> dict[str, object]:
    return {
        "context_artifact_id": binding.context_artifact_id,
        "object_ref_id": binding.object_ref_id,
        "artifact_kind": binding.artifact_kind,
        "logical_key": binding.logical_key,
        "artifact_version": binding.artifact_version,
        "schema_version": binding.schema_version,
        "artifact_sha256": binding.artifact_sha256,
        "status": binding.status,
        "sealed": binding.sealed,
    }


def _reference(value: P2ReferenceCondition) -> dict[str, object]:
    return {
        "reference_condition_id": value.reference_condition_id,
        "binding": _artifact(value.binding),
    }


def _cohort(value: P2CohortSnapshot) -> dict[str, object]:
    return {
        "dataset_snapshot_id": value.dataset_snapshot_id,
        "snapshot_type": value.snapshot_type,
        "data_hash": value.data_hash,
        "schema_version": value.schema_version,
        "frozen": value.frozen,
        "cohort_spec_id": value.cohort_spec_id,
        "cohort_spec_version": value.cohort_spec_version,
        "comparability_dimensions": [
            {"name": name, "value": item}
            for name, item in value.comparability_dimensions
        ],
        "knowledge_cutoff_utc": value.knowledge_cutoff_utc,
        "raw_record_count": value.raw_record_count,
        "observation_count": value.observation_count,
        "independent_subject_count": value.independent_subject_count,
        "effective_evidence_count": value.effective_evidence_count,
        "observation_ids": list(value.observation_ids),
        "episode_ids": list(value.episode_ids),
        "subject_ids": list(value.subject_ids),
    }


def _spec(value: P2AttributionSpec) -> dict[str, object]:
    return {
        "attribution_spec_id": value.attribution_spec_id,
        "attribution_spec_version": value.attribution_spec_version,
        "model_plugin": value.model_plugin,
        "model_plugin_version": value.model_plugin_version,
        "uncertainty_method": value.uncertainty_method,
        "uncertainty_level": value.uncertainty_level,
        "binding": _artifact(value.binding),
    }


def _feature(value: P2FactorFeatureSet) -> dict[str, object]:
    return {
        "factor_feature_set_id": value.factor_feature_set_id,
        "feature_spec_id": value.feature_spec_id,
        "feature_spec_version": value.feature_spec_version,
        "source_observation_id": value.source_observation_id,
        "reference_condition_id": value.reference_condition_id,
        "factor_order": list(value.factor_order),
        "feature_values": value.feature_mapping(),
        "missing_mask": value.missing_mapping(),
        "world_refs": list(value.world_refs),
        "coverage": value.coverage,
        "confidence": value.confidence,
        "input_hash": value.input_hash,
        "created_at": value.created_at,
    }


def _validate_snapshot(value: M6P2WorkspaceSnapshot) -> None:
    estimate = value.adjusted_estimate
    run = value.attribution_run
    bundle = value.input_bundle
    feature = value.target_feature_set
    _uuid(value.p2_release_id, "p2_release_id")
    _uuid(estimate.estimate_id, "estimate_id")
    _uuid(bundle.target.observation_id, "source_observation_id")
    _uuid(bundle.target.release_id, "source_release_id")
    _uuid(run.attribution_run_id, "attribution_run_id")
    _hash64(feature.input_hash, "feature_input_hash")
    _hash64(estimate.logical_hash, "estimate_logical_hash")
    _hash64(run.run_request_hash, "run_request_hash")
    if value.p2_release_status != "PUBLISHED" or not value.p2_release_sealed:
        raise M6ApplicationError(
            "M6_P2_PUBLISHED_RELEASE_REQUIRED",
            value.p2_release_id,
        )
    if estimate.p2_release_id != value.p2_release_id:
        raise M6ApplicationError("M6_P2_RELEASE_MISMATCH", estimate.estimate_id)
    if estimate.source_observation_id != bundle.target.observation_id:
        raise M6ApplicationError("M6_P2_SOURCE_OBSERVATION_MISMATCH", estimate.estimate_id)
    if estimate.source_release_id != bundle.target.release_id:
        raise M6ApplicationError("M6_P2_SOURCE_RELEASE_MISMATCH", estimate.estimate_id)
    if estimate.attribution_run_id != run.attribution_run_id:
        raise M6ApplicationError("M6_P2_RUN_MISMATCH", estimate.estimate_id)
    if estimate.reference_condition_id != bundle.reference_condition.reference_condition_id:
        raise M6ApplicationError("M6_P2_REFERENCE_MISMATCH", estimate.estimate_id)
    if feature.source_observation_id != bundle.target.observation_id:
        raise M6ApplicationError("M6_P2_FEATURE_SOURCE_MISMATCH", estimate.estimate_id)
    if run.training_dataset_snapshot_id != bundle.cohort.dataset_snapshot_id:
        raise M6ApplicationError("M6_P2_COHORT_MISMATCH", estimate.estimate_id)
    if (
        run.attribution_spec_id != bundle.attribution_spec.attribution_spec_id
        or run.attribution_spec_version != bundle.attribution_spec.attribution_spec_version
        or run.model_plugin != bundle.attribution_spec.model_plugin
        or run.model_plugin_version != bundle.attribution_spec.model_plugin_version
    ):
        raise M6ApplicationError("M6_P2_SPEC_MISMATCH", estimate.estimate_id)
    if estimate.status not in {P2_IDENTIFIABLE, P2_NOT_IDENTIFIABLE}:
        raise M6ApplicationError("M6_P2_STATUS_INVALID", estimate.status)
    if estimate.status != run.status:
        raise M6ApplicationError("M6_P2_STATUS_MISMATCH", estimate.estimate_id)
    diagnostics = run.diagnostics()
    reason_codes = diagnostics.get("reason_codes")
    if (
        not isinstance(reason_codes, list)
        or not all(isinstance(item, str) and item for item in reason_codes)
        or tuple(reason_codes) != estimate.reason_codes
    ):
        raise M6ApplicationError("M6_P2_REASON_CODES_MISMATCH", estimate.estimate_id)
    if diagnostics.get("factor_effect_semantics") != "MODEL_CONDITIONED_ASSOCIATION":
        raise M6ApplicationError(
            "M6_P2_EFFECT_SEMANTICS_INVALID",
            estimate.estimate_id,
        )
    if diagnostics.get("claim_level") != estimate.claim_level:
        raise M6ApplicationError("M6_P2_CLAIM_LEVEL_MISMATCH", estimate.estimate_id)
    if estimate.claim_level != "ASSOCIATION_ONLY":
        raise M6ApplicationError("M6_P2_CLAIM_LEVEL_INVALID", estimate.estimate_id)
    if estimate.status == P2_IDENTIFIABLE:
        if estimate.adjusted_value is None or not run.model_artifact_hash:
            raise M6ApplicationError("M6_P2_IDENTIFIABLE_PRODUCT_INCOMPLETE", estimate.estimate_id)
        if value.model_artifact_json is None:
            raise M6ApplicationError("M6_P2_MODEL_ARTIFACT_REQUIRED", estimate.estimate_id)
        if run.model_artifact_hash is None:
            raise M6ApplicationError("M6_P2_MODEL_ARTIFACT_REQUIRED", estimate.estimate_id)
        _hash64(run.model_artifact_hash, "model_artifact_hash")
        try:
            artifact_value: object = json.loads(value.model_artifact_json)
        except json.JSONDecodeError as exc:
            raise M6ApplicationError(
                "M6_P2_MODEL_ARTIFACT_INVALID",
                estimate.estimate_id,
            ) from exc
        if not isinstance(artifact_value, dict):
            raise M6ApplicationError(
                "M6_P2_MODEL_ARTIFACT_INVALID",
                estimate.estimate_id,
            )
        artifact_hash = hashlib.sha256(
            value.model_artifact_json.encode("ascii")
        ).hexdigest()
        if artifact_hash != run.model_artifact_hash:
            raise M6ApplicationError("M6_P2_MODEL_ARTIFACT_HASH_MISMATCH", estimate.estimate_id)
    else:
        if (
            estimate.adjusted_value is not None
            or estimate.uncertainty_lower is not None
            or estimate.uncertainty_upper is not None
            or estimate.residual is not None
            or estimate.factor_effects
            or not estimate.reason_codes
            or run.model_artifact_hash is not None
            or value.model_artifact_json is not None
        ):
            raise M6ApplicationError("M6_P2_NOT_IDENTIFIABLE_INVALID", estimate.estimate_id)


class InMemoryM6P2WorkspaceRepository:
    """Exact-identity in-memory read repository used by Application/transport tests."""

    def __init__(self) -> None:
        self._snapshots: dict[str, M6P2WorkspaceSnapshot] = {}

    def register(self, snapshot: M6P2WorkspaceSnapshot) -> None:
        _validate_snapshot(snapshot)
        estimate_id = snapshot.adjusted_estimate.estimate_id
        existing = self._snapshots.get(estimate_id)
        if existing is not None and existing != snapshot:
            raise M6ApplicationError("M6_P2_IMMUTABLE_CONFLICT", estimate_id)
        self._snapshots[estimate_id] = snapshot

    def exact(self, estimate_id: str) -> M6P2WorkspaceSnapshot:
        _uuid(estimate_id, "estimate_id")
        try:
            return self._snapshots[estimate_id]
        except KeyError as exc:
            raise M6ApplicationError("M6_P2_ESTIMATE_NOT_FOUND", estimate_id) from exc


class M6WorkspaceService:
    """Release-bound P2 read projections; never executes attribution."""

    def __init__(self, repository: InMemoryM6P2WorkspaceRepository) -> None:
        self._repository = repository

    def _snapshot(
        self,
        p2_release_id: str,
        estimate_id: str,
    ) -> M6P2WorkspaceSnapshot:
        _uuid(p2_release_id, "p2_release_id")
        snapshot = self._repository.exact(estimate_id)
        if snapshot.p2_release_id != p2_release_id:
            raise M6ApplicationError(
                "M6_P2_RELEASE_MISMATCH",
                f"{p2_release_id}:{estimate_id}",
            )
        _validate_snapshot(snapshot)
        return snapshot

    def comparison(self, query: M6P2ComparisonQuery) -> dict[str, object]:
        snapshot = self._snapshot(query.p2_release_id, query.estimate_id)
        target: P1ObservationInput = snapshot.input_bundle.target
        estimate = snapshot.adjusted_estimate
        observed = target.projection()
        run_diagnostics = snapshot.attribution_run.diagnostics()
        factor_effect_semantics = run_diagnostics.get("factor_effect_semantics")
        if not isinstance(factor_effect_semantics, str) or not factor_effect_semantics:
            raise M6ApplicationError(
                "M6_P2_DIAGNOSTICS_INVALID",
                "factor_effect_semantics",
            )
        adjusted = {
            "estimate_id": estimate.estimate_id,
            "p2_release_id": estimate.p2_release_id,
            "attribution_run_id": estimate.attribution_run_id,
            "attribution_spec_id": snapshot.attribution_run.attribution_spec_id,
            "attribution_spec_version": (
                snapshot.attribution_run.attribution_spec_version
            ),
            "model_plugin": snapshot.attribution_run.model_plugin,
            "model_plugin_version": snapshot.attribution_run.model_plugin_version,
            "reference_condition_id": estimate.reference_condition_id,
            "p2_published_at_utc": snapshot.p2_published_at_utc,
            "status": estimate.status,
            "adjusted_value": estimate.adjusted_value,
            "unit": estimate.unit,
            "uncertainty": {
                "lower": estimate.uncertainty_lower,
                "upper": estimate.uncertainty_upper,
                "method": estimate.uncertainty_method,
                "level": estimate.uncertainty_level,
            },
            "residual": estimate.residual,
            "factor_effects": estimate.factor_effect_mapping(),
            "factor_effect_semantics": factor_effect_semantics,
            "claim_level": estimate.claim_level,
            "reason_codes": list(estimate.reason_codes),
            "evidence_set_id": estimate.evidence_set_id,
            "estimate_time": estimate.estimate_time,
        }
        identity = {
            "p2_release_id": snapshot.p2_release_id,
            "p2_release_status": snapshot.p2_release_status,
            "p2_published_at_utc": snapshot.p2_published_at_utc,
            "estimate_id": estimate.estimate_id,
            "source_observation_id": target.observation_id,
            "source_release_id": target.release_id,
            "attribution_run_id": snapshot.attribution_run.attribution_run_id,
            "reference_condition_id": (
                snapshot.input_bundle.reference_condition.reference_condition_id
            ),
        }
        product = {
            "identity": identity,
            "observed": observed,
            "adjusted": adjusted,
        }
        return {
            **product,
            "logical_product_hash": _canonical_hash(product),
        }

    def diagnostics(self, query: M6P2DiagnosticsQuery) -> dict[str, object]:
        snapshot = self._snapshot(query.p2_release_id, query.estimate_id)
        run = snapshot.attribution_run
        bundle = snapshot.input_bundle
        run_diagnostics = run.diagnostics()
        factor_effect_semantics = run_diagnostics.get("factor_effect_semantics")
        if not isinstance(factor_effect_semantics, str) or not factor_effect_semantics:
            raise M6ApplicationError(
                "M6_P2_DIAGNOSTICS_INVALID",
                "factor_effect_semantics",
            )
        model_artifact: object = None
        if snapshot.model_artifact_json is not None:
            model_artifact = json.loads(snapshot.model_artifact_json)
        attribution = {
            **_spec(bundle.attribution_spec),
            "attribution_run_id": run.attribution_run_id,
            "training_dataset_snapshot_id": run.training_dataset_snapshot_id,
            "reference_condition_id": run.reference_condition_id,
            "status": run.status,
            "run_request_hash": run.run_request_hash,
            "model_artifact_uri": run.model_artifact_uri,
            "model_artifact_hash": run.model_artifact_hash,
            "diagnostics": run_diagnostics,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
        }
        identity = {
            "p2_release_id": snapshot.p2_release_id,
            "estimate_id": snapshot.adjusted_estimate.estimate_id,
            "source_release_id": bundle.target.release_id,
            "source_observation_id": bundle.target.observation_id,
            "attribution_run_id": run.attribution_run_id,
            "reference_condition_id": bundle.reference_condition.reference_condition_id,
        }
        evidence = {
            "identity": identity,
            "p2_release_id": snapshot.p2_release_id,
            "source_release_id": bundle.target.release_id,
            "source_observation_id": bundle.target.observation_id,
            "p1_knowledge_time_utc": bundle.target.knowledge_time_utc,
            "p2_estimate_time": snapshot.adjusted_estimate.estimate_time,
            "as_of_utc": bundle.as_of_utc,
            "feature": _feature(snapshot.target_feature_set),
            "feature_spec": _artifact(bundle.feature_spec),
            "reference": _reference(bundle.reference_condition),
            "cohort": _cohort(bundle.cohort),
            "attribution": attribution,
            "model_artifact": model_artifact,
            "result": {
                "status": snapshot.adjusted_estimate.status,
                "reason_codes": list(snapshot.adjusted_estimate.reason_codes),
                "factor_effects": snapshot.adjusted_estimate.factor_effect_mapping(),
                "factor_effect_semantics": factor_effect_semantics,
                "claim_level": snapshot.adjusted_estimate.claim_level,
                "residual": snapshot.adjusted_estimate.residual,
                "uncertainty": {
                    "lower": snapshot.adjusted_estimate.uncertainty_lower,
                    "upper": snapshot.adjusted_estimate.uncertainty_upper,
                    "method": snapshot.adjusted_estimate.uncertainty_method,
                    "level": snapshot.adjusted_estimate.uncertainty_level,
                },
            },
        }
        return {
            **evidence,
            "logical_product_hash": _canonical_hash(evidence),
        }
