"""Deterministic M6 P2 reference-adjustment execution engine.

This module implements only the protected-main adopted
P2_LINEAR_REFERENCE_ADJUSTMENT:1.0.0 profile. Canonical assets remain the
authority; unsupported profile drift fails closed instead of silently changing
algorithm semantics.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from typing import cast
from uuid import UUID, uuid5

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

from .p2_substrate import (
    P1ObservationInput,
    P2ArtifactBinding,
    P2AuthorityPolicy,
    P2GovernanceError,
    P2InputBundle,
    project_p1_observation,
    validate_factor_effect_semantics,
)

type Numeric = int | float
type FactorInput = Mapping[str, Numeric | None]
type CompleteFactorInput = Mapping[str, Numeric]


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


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_ATTRIBUTION_SPEC_REQUIRED",
            f"{field} must be an object",
        )
    return cast(dict[str, object], value)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_ATTRIBUTION_SPEC_REQUIRED",
            f"{field} must be a non-empty string",
        )
    return value


def _integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_ATTRIBUTION_SPEC_REQUIRED",
            f"{field} must be an integer",
        )
    return value


def _uuid(value: str, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        ) from exc
    if str(parsed) != value or parsed.int == 0:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    return value


def _utc(value: str, field: str) -> datetime:
    if not value.endswith("Z") or "T" not in value:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        ) from exc
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EXACT_IDENTITY_REQUIRED",
            f"{field} must be UTC",
        )
    return parsed


def _hash64(value: str, field: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    return value


def _exact_identity(value: str, field: str, forbidden: frozenset[str]) -> str:
    if not value.strip():
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EXACT_IDENTITY_REQUIRED",
            field,
        )
    if value.strip().upper() in forbidden:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_CURRENT_LATEST_FORBIDDEN",
            f"{field}={value!r}",
        )
    return value


def _decimal(value: Numeric | str | Decimal, field: str) -> Decimal:
    if isinstance(value, bool):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_FEATURE_SPEC_REQUIRED",
            f"{field} must be finite numeric",
        )
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_FEATURE_SPEC_REQUIRED",
            f"{field} must be finite numeric",
        ) from exc
    if not result.is_finite():
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_FEATURE_SPEC_REQUIRED",
            f"{field} must be finite numeric",
        )
    return result


def _decimal_identity(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


@dataclass(frozen=True, slots=True)
class P2ExecutionProfile:
    profile_id: str
    profile_version: str
    profile_sha256: str
    attribution_spec_id: str
    attribution_spec_version: str
    model_plugin: str
    model_plugin_version: str
    required_coverage: Decimal
    decimal_precision: int
    output_quantum: Decimal
    zero_scale_tolerance: Decimal
    rank_ratio_minimum: Decimal
    uncertainty_method: str
    uncertainty_level: str
    uncertainty_z: Decimal
    factor_effect_semantics: str
    claim_level: str
    feature_namespace: UUID
    run_namespace: UUID
    estimate_namespace: UUID

    @classmethod
    def from_canonical(
        cls,
        loader: CanonicalArtifactLoader | None = None,
    ) -> P2ExecutionProfile:
        canonical = loader or CanonicalArtifactLoader()
        artifact = canonical.load(
            "P2_LINEAR_REFERENCE_ADJUSTMENT_PROFILE",
            expectation=ArtifactExpectation(
                version="1.0.0",
                schema_version="1.6.0",
                required_top_level_keys=(
                    "runtime_binding",
                    "eligibility_contract",
                    "ordering_contract",
                    "subject_balancing_contract",
                    "arithmetic_contract",
                    "scaling_contract",
                    "solver_contract",
                    "support_contract",
                    "adjustment_contract",
                    "uncertainty_contract",
                    "identifiability_contract",
                    "artifact_replay_contract",
                    "identity_contract",
                ),
            ),
        )
        payload = artifact.payload
        runtime = _mapping(payload.get("runtime_binding"), "runtime_binding")
        eligibility = _mapping(payload.get("eligibility_contract"), "eligibility_contract")
        ordering = _mapping(payload.get("ordering_contract"), "ordering_contract")
        balancing = _mapping(
            payload.get("subject_balancing_contract"),
            "subject_balancing_contract",
        )
        arithmetic = _mapping(payload.get("arithmetic_contract"), "arithmetic_contract")
        scaling = _mapping(payload.get("scaling_contract"), "scaling_contract")
        solver = _mapping(payload.get("solver_contract"), "solver_contract")
        support = _mapping(payload.get("support_contract"), "support_contract")
        adjustment = _mapping(payload.get("adjustment_contract"), "adjustment_contract")
        uncertainty = _mapping(payload.get("uncertainty_contract"), "uncertainty_contract")
        replay = _mapping(payload.get("artifact_replay_contract"), "artifact_replay_contract")
        identity = _mapping(payload.get("identity_contract"), "identity_contract")

        exact_expected: tuple[tuple[object, object, str], ...] = (
            (
                runtime.get("logical_key"),
                "P2_ATTRIBUTION_SPEC:P2_LINEAR_REFERENCE_ADJUSTMENT",
                "runtime logical key",
            ),
            (runtime.get("artifact_version"), "1.0.0", "runtime artifact version"),
            (runtime.get("model_plugin"), "LINEAR_REFERENCE_ADJUSTMENT", "model plugin"),
            (runtime.get("model_plugin_version"), "1.0.0", "model plugin version"),
            (runtime.get("exact_identity_only"), True, "exact identity"),
            (runtime.get("current_latest_default_forbidden"), True, "current/latest guard"),
            (ordering.get("factor_order"), "EXACT_SEALED_FEATURE_SPEC_ORDER", "factor ordering"),
            (ordering.get("cohort_row_order"), "SOURCE_OBSERVATION_ID_ASC", "row ordering"),
            (
                ordering.get("independent_subject_order"),
                "SUBJECT_ENTITY_ID_ASC",
                "subject ordering",
            ),
            (ordering.get("jackknife_fold_order"), "SUBJECT_ENTITY_ID_ASC", "jackknife ordering"),
            (
                balancing.get("row_weight_formula"),
                "1 / eligible_observation_count_for_subject",
                "row weighting",
            ),
            (
                balancing.get("full_fit_min_independent_subjects"),
                "factor_count + 3",
                "full subject minimum",
            ),
            (
                balancing.get("leave_one_out_min_independent_subjects"),
                "factor_count + 2",
                "jackknife subject minimum",
            ),
            (arithmetic.get("backend"), "PYTHON_DECIMAL", "arithmetic backend"),
            (arithmetic.get("rounding_mode"), "ROUND_HALF_EVEN", "rounding"),
            (arithmetic.get("external_blas_backend_forbidden"), True, "BLAS guard"),
            (arithmetic.get("random_sampling_forbidden"), True, "RNG guard"),
            (solver.get("algorithm"), "DECIMAL_MODIFIED_GRAM_SCHMIDT_QR2", "solver"),
            (solver.get("reorthogonalization_passes"), 2, "solver passes"),
            (solver.get("regularization_forbidden"), True, "regularization guard"),
            (solver.get("factor_dropping_fallback_forbidden"), True, "factor drop guard"),
            (solver.get("alternate_solver_fallback_forbidden"), True, "solver fallback guard"),
            (support.get("tolerance"), "0", "support tolerance"),
            (support.get("target_must_be_in_support"), True, "target support"),
            (support.get("reference_must_be_in_support"), True, "reference support"),
            (
                adjustment.get("factor_effect_semantics"),
                "MODEL_CONDITIONED_ASSOCIATION",
                "effect semantics",
            ),
            (adjustment.get("claim_level"), "ASSOCIATION_ONLY", "claim level"),
            (adjustment.get("causal_upgrade_supported"), False, "causal upgrade"),
            (
                uncertainty.get("method"),
                "JACKKNIFE_LEAVE_ONE_INDEPENDENT_SUBJECT_OUT",
                "uncertainty method",
            ),
            (
                uncertainty.get("alternate_uncertainty_fallback_forbidden"),
                True,
                "uncertainty fallback",
            ),
            (
                replay.get("historical_current_latest_fallback_forbidden"),
                True,
                "replay current/latest guard",
            ),
        )
        for actual, expected, field in exact_expected:
            if actual != expected:
                raise P2GovernanceError(
                    "FAIL_CLOSED_P2_ATTRIBUTION_SPEC_REQUIRED",
                    f"unsupported adopted profile drift: {field}",
                )

        feature_identity = _mapping(
            identity.get("factor_feature_set"),
            "identity.factor_feature_set",
        )
        run_identity = _mapping(identity.get("attribution_run"), "identity.attribution_run")
        estimate_identity = _mapping(
            identity.get("adjusted_estimate"),
            "identity.adjusted_estimate",
        )
        if _text(identity.get("namespace_url"), "identity.namespace_url") != (
            "6ba7b811-9dad-11d1-80b4-00c04fd430c8"
        ):
            raise P2GovernanceError(
                "FAIL_CLOSED_P2_ATTRIBUTION_SPEC_REQUIRED",
                "unsupported UUID namespace root",
            )
        return cls(
            profile_id=_text(payload.get("profile_id"), "profile_id"),
            profile_version=_text(payload.get("version"), "version"),
            profile_sha256=artifact.sha256,
            attribution_spec_id=_text(runtime.get("attribution_spec_id"), "attribution_spec_id"),
            attribution_spec_version=_text(
                runtime.get("attribution_spec_version"),
                "attribution_spec_version",
            ),
            model_plugin=_text(runtime.get("model_plugin"), "model_plugin"),
            model_plugin_version=_text(
                runtime.get("model_plugin_version"),
                "model_plugin_version",
            ),
            required_coverage=_decimal(
                _text(
                    eligibility.get("feature_set_required_coverage"),
                    "feature_set_required_coverage",
                ),
                "feature_set_required_coverage",
            ),
            decimal_precision=_integer(
                arithmetic.get("decimal_precision"),
                "decimal_precision",
            ),
            output_quantum=_decimal(
                _text(arithmetic.get("output_quantum"), "output_quantum"),
                "output_quantum",
            ),
            zero_scale_tolerance=_decimal(
                _text(scaling.get("zero_scale_tolerance"), "zero_scale_tolerance"),
                "zero_scale_tolerance",
            ),
            rank_ratio_minimum=_decimal(
                _text(solver.get("rank_ratio_minimum"), "rank_ratio_minimum"),
                "rank_ratio_minimum",
            ),
            uncertainty_method=_text(uncertainty.get("method"), "uncertainty.method"),
            uncertainty_level=_text(uncertainty.get("level"), "uncertainty.level"),
            uncertainty_z=_decimal(
                _text(uncertainty.get("z_value"), "uncertainty.z_value"),
                "uncertainty.z_value",
            ),
            factor_effect_semantics=_text(
                adjustment.get("factor_effect_semantics"),
                "factor_effect_semantics",
            ),
            claim_level=_text(adjustment.get("claim_level"), "claim_level"),
            feature_namespace=UUID(
                _text(feature_identity.get("namespace_uuid"), "feature namespace")
            ),
            run_namespace=UUID(_text(run_identity.get("namespace_uuid"), "run namespace")),
            estimate_namespace=UUID(
                _text(estimate_identity.get("namespace_uuid"), "estimate namespace")
            ),
        )

    def quantize(self, value: Decimal) -> Decimal:
        with localcontext() as context:
            context.prec = self.decimal_precision
            context.rounding = ROUND_HALF_EVEN
            quantized = value.quantize(self.output_quantum)
        return abs(quantized) if quantized == 0 else quantized

    def qstr(self, value: Decimal) -> str:
        return format(self.quantize(value), "f")


@dataclass(frozen=True, slots=True)
class P2FactorFeatureSet:
    factor_feature_set_id: str
    feature_spec_id: str
    feature_spec_version: str
    source_observation_id: str
    reference_condition_id: str | None
    feature_values: tuple[tuple[str, float | None], ...]
    missing_mask: tuple[tuple[str, bool], ...]
    world_refs: tuple[str, ...]
    coverage: float
    confidence: float
    input_hash: str
    created_at: str

    @property
    def factor_order(self) -> tuple[str, ...]:
        return tuple(name for name, _value in self.feature_values)

    def feature_mapping(self) -> dict[str, float | None]:
        return dict(self.feature_values)

    def missing_mapping(self) -> dict[str, bool]:
        return dict(self.missing_mask)

    def as_record(self) -> dict[str, object]:
        return {
            "factor_feature_set_id": self.factor_feature_set_id,
            "feature_spec_id": self.feature_spec_id,
            "feature_spec_version": self.feature_spec_version,
            "source_observation_id": self.source_observation_id,
            "reference_condition_id": self.reference_condition_id,
            "feature_values": self.feature_mapping(),
            "missing_mask": self.missing_mapping(),
            "world_refs": list(self.world_refs),
            "coverage": self.coverage,
            "confidence": self.confidence,
            "input_hash": self.input_hash,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class P2CohortRow:
    observation: P1ObservationInput
    feature_set: P2FactorFeatureSet


@dataclass(frozen=True, slots=True)
class P2AttributionRunProduct:
    attribution_run_id: str
    attribution_spec_id: str
    attribution_spec_version: str
    model_plugin: str
    model_plugin_version: str
    training_dataset_snapshot_id: str
    reference_condition_id: str
    status: str
    diagnostics_json: str
    model_artifact_uri: str | None
    model_artifact_hash: str | None
    started_at: str
    completed_at: str
    created_by: str | None
    run_request_hash: str

    def diagnostics(self) -> dict[str, object]:
        value: object = json.loads(self.diagnostics_json)
        return _mapping(value, "attribution_run.diagnostics")

    def as_record(self) -> dict[str, object]:
        return {
            "attribution_run_id": self.attribution_run_id,
            "attribution_spec_id": self.attribution_spec_id,
            "attribution_spec_version": self.attribution_spec_version,
            "model_plugin": self.model_plugin,
            "model_plugin_version": self.model_plugin_version,
            "training_dataset_snapshot_id": self.training_dataset_snapshot_id,
            "reference_condition_id": self.reference_condition_id,
            "status": self.status,
            "diagnostics": self.diagnostics(),
            "model_artifact_uri": self.model_artifact_uri,
            "model_artifact_hash": self.model_artifact_hash,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "created_by": self.created_by,
        }


@dataclass(frozen=True, slots=True)
class P2AdjustedCapabilityEstimate:
    estimate_id: str
    source_observation_id: str
    source_release_id: str
    p2_release_id: str
    attribution_run_id: str
    aircraft_id: str
    capability_type: str
    reference_condition_id: str
    adjusted_value: float | None
    unit: str
    uncertainty_lower: float | None
    uncertainty_upper: float | None
    uncertainty_method: str
    uncertainty_level: str
    residual: float | None
    factor_effects: tuple[tuple[str, float], ...]
    claim_level: str
    status: str
    reason_codes: tuple[str, ...]
    evidence_set_id: str
    estimate_time: str
    created_at: str
    supersedes_estimate_id: str | None
    logical_hash: str

    def factor_effect_mapping(self) -> dict[str, float]:
        return dict(self.factor_effects)

    def as_record(self) -> dict[str, object]:
        return {
            "estimate_id": self.estimate_id,
            "source_observation_id": self.source_observation_id,
            "attribution_run_id": self.attribution_run_id,
            "aircraft_id": self.aircraft_id,
            "capability_type": self.capability_type,
            "reference_condition_id": self.reference_condition_id,
            "adjusted_value": self.adjusted_value,
            "unit": self.unit,
            "uncertainty_lower": self.uncertainty_lower,
            "uncertainty_upper": self.uncertainty_upper,
            "residual": self.residual,
            "factor_effects": self.factor_effect_mapping(),
            "claim_level": self.claim_level,
            "status": self.status,
            "evidence_set_id": self.evidence_set_id,
            "estimate_time": self.estimate_time,
            "created_at": self.created_at,
            "supersedes_estimate_id": self.supersedes_estimate_id,
        }


@dataclass(frozen=True, slots=True)
class P2AttributionExecution:
    target_feature_set: P2FactorFeatureSet
    attribution_run: P2AttributionRunProduct
    adjusted_estimate: P2AdjustedCapabilityEstimate
    model_artifact_json: str | None


@dataclass(frozen=True, slots=True)
class _Fit:
    means: tuple[Decimal, ...]
    scales: tuple[Decimal, ...]
    standardized_coefficients: tuple[Decimal, ...]
    raw_coefficients: tuple[Decimal, ...]
    intercept: Decimal
    rank_ratio: Decimal


def materialize_factor_feature_set(
    *,
    source: P1ObservationInput,
    feature_spec: P2ArtifactBinding,
    factor_order: Sequence[str],
    factor_values: FactorInput,
    world_refs: Sequence[str],
    confidence: float,
    created_at: str,
    reference_condition_id: str | None = None,
    profile: P2ExecutionProfile | None = None,
) -> P2FactorFeatureSet:
    active = profile or P2ExecutionProfile.from_canonical()
    project_p1_observation(source)
    _utc(created_at, "factor_feature_set.created_at")
    policy = P2AuthorityPolicy.from_canonical()
    _uuid(feature_spec.context_artifact_id, "feature_spec.context_artifact_id")
    _uuid(feature_spec.object_ref_id, "feature_spec.object_ref_id")
    _exact_identity(
        feature_spec.logical_key,
        "feature_spec.logical_key",
        policy.forbidden_pointer_tokens,
    )
    _exact_identity(
        feature_spec.artifact_version,
        "feature_spec.artifact_version",
        policy.forbidden_pointer_tokens,
    )
    _hash64(feature_spec.artifact_sha256, "feature_spec.artifact_sha256")
    if (
        feature_spec.artifact_kind != policy.feature_artifact_kind
        or not feature_spec.logical_key.startswith(policy.feature_logical_key_prefix)
        or feature_spec.schema_version != policy.feature_schema_version
        or feature_spec.status != "ACTIVE"
        or not feature_spec.sealed
    ):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_FEATURE_SPEC_REQUIRED",
            feature_spec.logical_key,
        )
    order = tuple(factor_order)
    if not order or len(set(order)) != len(order) or any(not name.strip() for name in order):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_FEATURE_SPEC_REQUIRED",
            "factor order must be non-empty and unique",
        )
    if set(factor_values) != set(order):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_FEATURE_SPEC_REQUIRED",
            "factor values must exactly match governed factor order",
        )
    ordered_values: list[tuple[str, float | None]] = []
    missing: list[tuple[str, bool]] = []
    hash_values: list[dict[str, object]] = []
    present = 0
    for name in order:
        raw = factor_values[name]
        is_missing = raw is None
        missing.append((name, is_missing))
        if is_missing:
            ordered_values.append((name, None))
            hash_values.append({"factor": name, "value": None})
            continue
        decimal_value = _decimal(cast(Numeric, raw), f"factor.{name}")
        numeric_value = float(decimal_value)
        ordered_values.append((name, numeric_value))
        hash_values.append({"factor": name, "value": _decimal_identity(decimal_value)})
        present += 1
    if (
        isinstance(confidence, bool)
        or not math.isfinite(confidence)
        or not 0.0 <= confidence <= 1.0
    ):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_FEATURE_SPEC_REQUIRED",
            "confidence outside [0,1]",
        )
    refs = tuple(sorted(_uuid(value, "world_ref") for value in world_refs))
    if len(set(refs)) != len(refs):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_FEATURE_SPEC_REQUIRED",
            "world_refs must be unique",
        )
    reference_id = (
        _uuid(reference_condition_id, "reference_condition_id")
        if reference_condition_id is not None
        else None
    )
    with localcontext() as context:
        context.prec = active.decimal_precision
        context.rounding = ROUND_HALF_EVEN
        coverage_decimal = Decimal(present) / Decimal(len(order))
    coverage = float(coverage_decimal)
    material = {
        "profile_id": active.profile_id,
        "profile_version": active.profile_version,
        "source_observation_id": source.observation_id,
        "source_release_id": source.release_id,
        "feature_spec_id": feature_spec.logical_key,
        "feature_spec_version": feature_spec.artifact_version,
        "feature_spec_sha256": feature_spec.artifact_sha256,
        "reference_condition_id": reference_id,
        "factor_order": list(order),
        "feature_values": hash_values,
        "world_refs": list(refs),
        "coverage": _decimal_identity(coverage_decimal),
        "confidence": _decimal_identity(_decimal(confidence, "confidence")),
    }
    input_hash = _canonical_hash(material)
    feature_set_id = str(uuid5(active.feature_namespace, input_hash))
    return P2FactorFeatureSet(
        factor_feature_set_id=feature_set_id,
        feature_spec_id=feature_spec.logical_key,
        feature_spec_version=feature_spec.artifact_version,
        source_observation_id=source.observation_id,
        reference_condition_id=reference_id,
        feature_values=tuple(ordered_values),
        missing_mask=tuple(missing),
        world_refs=refs,
        coverage=coverage,
        confidence=confidence,
        input_hash=input_hash,
        created_at=created_at,
    )


def _complete_vector(
    feature_set: P2FactorFeatureSet,
    factor_order: tuple[str, ...],
    profile: P2ExecutionProfile,
) -> tuple[Decimal, ...] | None:
    if feature_set.factor_order != factor_order:
        return None
    if _decimal(feature_set.coverage, "feature coverage") != profile.required_coverage:
        return None
    values = feature_set.feature_mapping()
    result: list[Decimal] = []
    for name in factor_order:
        value = values[name]
        if value is None:
            return None
        result.append(_decimal(value, f"feature.{name}"))
    return tuple(result)


def _reference_vector(
    values: CompleteFactorInput,
    factor_order: tuple[str, ...],
) -> tuple[Decimal, ...]:
    if set(values) != set(factor_order):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_REFERENCE_CONDITION_REQUIRED",
            "reference factor values must exactly match factor order",
        )
    return tuple(_decimal(values[name], f"reference.{name}") for name in factor_order)


def _subject_weights(
    rows: Sequence[P2CohortRow],
    profile: P2ExecutionProfile,
) -> tuple[Decimal, ...]:
    counts: dict[str, int] = {}
    for row in rows:
        subject = row.observation.subject_entity_id
        counts[subject] = counts.get(subject, 0) + 1
    with localcontext() as context:
        context.prec = profile.decimal_precision
        context.rounding = ROUND_HALF_EVEN
        return tuple(
            Decimal(1) / Decimal(counts[row.observation.subject_entity_id])
            for row in rows
        )


def _dot(left: Sequence[Decimal], right: Sequence[Decimal]) -> Decimal:
    return sum((a * b for a, b in zip(left, right, strict=True)), Decimal(0))


def _fit(
    rows: Sequence[P2CohortRow],
    vectors: Sequence[tuple[Decimal, ...]],
    factor_order: tuple[str, ...],
    profile: P2ExecutionProfile,
) -> _Fit | str:
    subject_count = len({row.observation.subject_entity_id for row in rows})
    if subject_count < len(factor_order) + 2:
        return "INSUFFICIENT_EFFECTIVE_EVIDENCE"
    weights = _subject_weights(rows, profile)
    total_weight = sum(weights, Decimal(0))
    with localcontext() as context:
        context.prec = profile.decimal_precision
        context.rounding = ROUND_HALF_EVEN
        means: list[Decimal] = []
        scales: list[Decimal] = []
        for index in range(len(factor_order)):
            mean = (
                sum(
                    (
                        weight * vector[index]
                        for weight, vector in zip(weights, vectors, strict=True)
                    ),
                    Decimal(0),
                )
                / total_weight
            )
            variance = (
                sum(
                    (
                        weight * (vector[index] - mean) ** 2
                        for weight, vector in zip(weights, vectors, strict=True)
                    ),
                    Decimal(0),
                )
                / total_weight
            )
            scale = variance.sqrt()
            if scale <= profile.zero_scale_tolerance:
                return "FEATURE_COVERAGE_INSUFFICIENT"
            means.append(mean)
            scales.append(scale)

        design_rows: list[list[Decimal]] = []
        outcome: list[Decimal] = []
        for row, vector, weight in zip(rows, vectors, weights, strict=True):
            root_weight = weight.sqrt()
            standardized = [
                (vector[index] - means[index]) / scales[index]
                for index in range(len(factor_order))
            ]
            design_rows.append(
                [root_weight] + [root_weight * value for value in standardized]
            )
            outcome.append(root_weight * _decimal(row.observation.observed_value, "outcome"))

        column_count = len(factor_order) + 1
        columns = [
            [design_rows[row_index][column_index] for row_index in range(len(rows))]
            for column_index in range(column_count)
        ]
        q_columns: list[list[Decimal]] = []
        upper = [
            [Decimal(0) for _column in range(column_count)]
            for _row in range(column_count)
        ]
        diagonal: list[Decimal] = []
        for column_index, original in enumerate(columns):
            vector = list(original)
            for _pass in range(2):
                for previous in range(column_index):
                    coefficient = _dot(q_columns[previous], vector)
                    upper[previous][column_index] += coefficient
                    vector = [
                        value - coefficient * basis
                        for value, basis in zip(
                            vector,
                            q_columns[previous],
                            strict=True,
                        )
                    ]
            norm_squared = _dot(vector, vector)
            if norm_squared <= 0:
                return "MODEL_SPEC_DIAGNOSTIC_FAILURE"
            norm = norm_squared.sqrt()
            upper[column_index][column_index] = norm
            diagonal.append(abs(norm))
            q_columns.append([value / norm for value in vector])

        maximum = max(diagonal)
        minimum = min(diagonal)
        if maximum == 0:
            return "MODEL_SPEC_DIAGNOSTIC_FAILURE"
        rank_ratio = minimum / maximum
        if rank_ratio < profile.rank_ratio_minimum:
            return "MODEL_SPEC_DIAGNOSTIC_FAILURE"

        qtb = [_dot(column, outcome) for column in q_columns]
        coefficients = [Decimal(0) for _index in range(column_count)]
        for row_index in range(column_count - 1, -1, -1):
            residual = qtb[row_index] - sum(
                (
                    upper[row_index][column_index] * coefficients[column_index]
                    for column_index in range(row_index + 1, column_count)
                ),
                Decimal(0),
            )
            coefficients[row_index] = residual / upper[row_index][row_index]
        raw = tuple(
            coefficients[index + 1] / scales[index]
            for index in range(len(factor_order))
        )
        return _Fit(
            means=tuple(means),
            scales=tuple(scales),
            standardized_coefficients=tuple(coefficients[1:]),
            raw_coefficients=raw,
            intercept=coefficients[0],
            rank_ratio=rank_ratio,
        )


def _in_support(
    vectors: Sequence[tuple[Decimal, ...]],
    target: tuple[Decimal, ...],
    reference: tuple[Decimal, ...],
) -> bool:
    for index in range(len(target)):
        minimum = min(vector[index] for vector in vectors)
        maximum = max(vector[index] for vector in vectors)
        if not minimum <= target[index] <= maximum:
            return False
        if not minimum <= reference[index] <= maximum:
            return False
    return True


def _prediction(fit: _Fit, vector: tuple[Decimal, ...]) -> Decimal:
    standardized = tuple(
        (value - mean) / scale
        for value, mean, scale in zip(
            vector,
            fit.means,
            fit.scales,
            strict=True,
        )
    )
    return fit.intercept + _dot(fit.standardized_coefficients, standardized)


def _adjusted(
    observed: Decimal,
    target: tuple[Decimal, ...],
    reference: tuple[Decimal, ...],
    fit: _Fit,
) -> tuple[Decimal, tuple[Decimal, ...]]:
    effects = tuple(
        coefficient * (reference_value - target_value)
        for coefficient, reference_value, target_value in zip(
            fit.raw_coefficients,
            reference,
            target,
            strict=True,
        )
    )
    return observed + sum(effects, Decimal(0)), effects


def _validate_feature_set_integrity(
    *,
    feature_set: P2FactorFeatureSet,
    source: P1ObservationInput,
    feature_spec: P2ArtifactBinding,
    reference_condition_id: str,
    profile: P2ExecutionProfile,
) -> None:
    if feature_set.reference_condition_id not in {None, reference_condition_id}:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_REFERENCE_CONDITION_REQUIRED",
            "feature-set reference condition mismatch",
        )
    rebuilt = materialize_factor_feature_set(
        source=source,
        feature_spec=feature_spec,
        factor_order=feature_set.factor_order,
        factor_values=feature_set.feature_mapping(),
        world_refs=feature_set.world_refs,
        confidence=feature_set.confidence,
        created_at=feature_set.created_at,
        reference_condition_id=feature_set.reference_condition_id,
        profile=profile,
    )
    if (
        rebuilt.input_hash != feature_set.input_hash
        or rebuilt.factor_feature_set_id != feature_set.factor_feature_set_id
        or rebuilt.missing_mask != feature_set.missing_mask
        or rebuilt.coverage != feature_set.coverage
    ):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_FEATURE_SPEC_REQUIRED",
            "factor feature-set integrity mismatch",
        )


def _validate_execution_inputs(
    *,
    bundle: P2InputBundle,
    target_feature_set: P2FactorFeatureSet,
    cohort_rows: Sequence[P2CohortRow],
    factor_order: tuple[str, ...],
    profile: P2ExecutionProfile,
) -> str | None:
    spec = bundle.attribution_spec
    if (
        spec.attribution_spec_id != profile.attribution_spec_id
        or spec.attribution_spec_version != profile.attribution_spec_version
        or spec.model_plugin != profile.model_plugin
        or spec.model_plugin_version != profile.model_plugin_version
        or spec.uncertainty_method != profile.uncertainty_method
        or spec.uncertainty_level != profile.uncertainty_level
    ):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_ATTRIBUTION_SPEC_REQUIRED",
            "runtime spec does not equal protected-main execution profile",
        )
    if target_feature_set.source_observation_id != bundle.target.observation_id:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_FEATURE_SPEC_REQUIRED",
            "target feature source mismatch",
        )
    _validate_feature_set_integrity(
        feature_set=target_feature_set,
        source=bundle.target,
        feature_spec=bundle.feature_spec,
        reference_condition_id=bundle.reference_condition.reference_condition_id,
        profile=profile,
    )
    if (
        target_feature_set.feature_spec_id != bundle.feature_spec.logical_key
        or target_feature_set.feature_spec_version != bundle.feature_spec.artifact_version
    ):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_FEATURE_SPEC_REQUIRED",
            "target feature spec mismatch",
        )
    expected_observations = tuple(sorted(bundle.cohort.observation_ids))
    actual_observations = tuple(sorted(row.observation.observation_id for row in cohort_rows))
    if expected_observations != actual_observations:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_COHORT_SNAPSHOT_REQUIRED",
            "cohort row identities differ from frozen snapshot",
        )
    actual_episodes = {row.observation.episode_id for row in cohort_rows}
    if set(bundle.cohort.episode_ids) != actual_episodes:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_COHORT_SNAPSHOT_REQUIRED",
            "cohort episode identities differ from frozen snapshot",
        )
    actual_subjects = {row.observation.subject_entity_id for row in cohort_rows}
    if set(bundle.cohort.subject_ids) != actual_subjects:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_COHORT_SNAPSHOT_REQUIRED",
            "cohort subject identities differ from frozen snapshot",
        )
    target = bundle.target
    for row in cohort_rows:
        project_p1_observation(row.observation)
        if _utc(row.observation.knowledge_time_utc, "cohort.knowledge_time_utc") > _utc(
            bundle.as_of_utc,
            "as_of_utc",
        ):
            raise P2GovernanceError(
                "FAIL_CLOSED_P2_FUTURE_INFORMATION",
                row.observation.observation_id,
            )
        if row.observation.episode_id == target.episode_id:
            raise P2GovernanceError(
                "FAIL_CLOSED_P2_SAME_EPISODE_LEAKAGE",
                row.observation.observation_id,
            )
        if row.feature_set.source_observation_id != row.observation.observation_id:
            raise P2GovernanceError(
                "FAIL_CLOSED_P2_FEATURE_SPEC_REQUIRED",
                "cohort feature source mismatch",
            )
        _validate_feature_set_integrity(
            feature_set=row.feature_set,
            source=row.observation,
            feature_spec=bundle.feature_spec,
            reference_condition_id=bundle.reference_condition.reference_condition_id,
            profile=profile,
        )
        if (
            row.feature_set.feature_spec_id != bundle.feature_spec.logical_key
            or row.feature_set.feature_spec_version != bundle.feature_spec.artifact_version
        ):
            raise P2GovernanceError(
                "FAIL_CLOSED_P2_FEATURE_SPEC_REQUIRED",
                "cohort feature spec mismatch",
            )
        comparable = (
            row.observation.capability_type == target.capability_type
            and row.observation.metric_semantic_id == target.metric_semantic_id
            and row.observation.metric_semantic_version == target.metric_semantic_version
            and row.observation.unit == target.unit
            and row.observation.aircraft_model_id == target.aircraft_model_id
            and row.observation.comparison_key_hash == target.comparison_key_hash
        )
        if not comparable:
            return "COHORT_NOT_COMPARABLE"
        if _complete_vector(row.feature_set, factor_order, profile) is None:
            return "FEATURE_COVERAGE_INSUFFICIENT"
    if _complete_vector(target_feature_set, factor_order, profile) is None:
        return "FEATURE_COVERAGE_INSUFFICIENT"
    if len(actual_subjects) < len(factor_order) + 3:
        return "INSUFFICIENT_EFFECTIVE_EVIDENCE"
    return None


def _run_request_hash(
    *,
    bundle: P2InputBundle,
    target_feature_set: P2FactorFeatureSet,
    cohort_rows: Sequence[P2CohortRow],
    factor_order: tuple[str, ...],
    reference: tuple[Decimal, ...],
    profile: P2ExecutionProfile,
    factor_effect_semantics: str,
) -> str:
    rows = sorted(cohort_rows, key=lambda row: row.observation.observation_id)
    return _canonical_hash(
        {
            "profile_sha256": profile.profile_sha256,
            "bundle_input_hash": bundle.input_hash,
            "target_feature_input_hash": target_feature_set.input_hash,
            "cohort_snapshot_id": bundle.cohort.dataset_snapshot_id,
            "cohort_data_hash": bundle.cohort.data_hash,
            "cohort_rows": [
                {
                    "observation_id": row.observation.observation_id,
                    "release_id": row.observation.release_id,
                    "feature_input_hash": row.feature_set.input_hash,
                }
                for row in rows
            ],
            "reference_condition_id": bundle.reference_condition.reference_condition_id,
            "reference_artifact_sha256": bundle.reference_condition.binding.artifact_sha256,
            "factor_order": list(factor_order),
            "reference_values": [
                {"factor": factor, "value": _decimal_identity(value)}
                for factor, value in zip(factor_order, reference, strict=True)
            ],
            "attribution_spec_id": bundle.attribution_spec.attribution_spec_id,
            "attribution_spec_version": bundle.attribution_spec.attribution_spec_version,
            "model_plugin": bundle.attribution_spec.model_plugin,
            "model_plugin_version": bundle.attribution_spec.model_plugin_version,
            "factor_effect_semantics": factor_effect_semantics,
            "as_of_utc": bundle.as_of_utc,
        }
    )


def _not_identifiable(
    *,
    reason: str,
    bundle: P2InputBundle,
    target_feature_set: P2FactorFeatureSet,
    p2_release_id: str,
    evidence_set_id: str,
    execution_time_utc: str,
    created_by: str | None,
    supersedes_estimate_id: str | None,
    run_request_hash: str,
    profile: P2ExecutionProfile,
) -> P2AttributionExecution:
    policy = P2AuthorityPolicy.from_canonical()
    if reason not in policy.not_identifiable_reason_codes:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_AUTHORITY_REQUIRED",
            f"ungoverned NOT_IDENTIFIABLE reason {reason!r}",
        )
    status_payload = {
        "status": "NOT_IDENTIFIABLE",
        "reason_codes": [reason],
        "run_request_hash": run_request_hash,
    }
    status_hash = _canonical_hash(status_payload)
    run_id = str(
        uuid5(
            profile.run_namespace,
            f"{run_request_hash}|{status_hash}",
        )
    )
    diagnostics = {
        "reason_codes": [reason],
        "run_request_hash": run_request_hash,
        "uncertainty_method": profile.uncertainty_method,
        "uncertainty_level": profile.uncertainty_level,
        "factor_effect_semantics": profile.factor_effect_semantics,
        "claim_level": profile.claim_level,
    }
    run = P2AttributionRunProduct(
        attribution_run_id=run_id,
        attribution_spec_id=profile.attribution_spec_id,
        attribution_spec_version=profile.attribution_spec_version,
        model_plugin=profile.model_plugin,
        model_plugin_version=profile.model_plugin_version,
        training_dataset_snapshot_id=bundle.cohort.dataset_snapshot_id,
        reference_condition_id=bundle.reference_condition.reference_condition_id,
        status="NOT_IDENTIFIABLE",
        diagnostics_json=_canonical_json(diagnostics),
        model_artifact_uri=None,
        model_artifact_hash=None,
        started_at=execution_time_utc,
        completed_at=execution_time_utc,
        created_by=created_by,
        run_request_hash=run_request_hash,
    )
    logical = {
        "source_observation_id": bundle.target.observation_id,
        "source_release_id": bundle.target.release_id,
        "p2_release_id": p2_release_id,
        "attribution_run_id": run_id,
        "reference_condition_id": bundle.reference_condition.reference_condition_id,
        "status": "NOT_IDENTIFIABLE",
        "reason_codes": [reason],
        "claim_level": profile.claim_level,
        "evidence_set_id": evidence_set_id,
    }
    logical_hash = _canonical_hash(logical)
    estimate_id = str(
        uuid5(
            profile.estimate_namespace,
            "|".join(
                (
                    p2_release_id,
                    bundle.target.observation_id,
                    run_id,
                    logical_hash,
                )
            ),
        )
    )
    estimate = P2AdjustedCapabilityEstimate(
        estimate_id=estimate_id,
        source_observation_id=bundle.target.observation_id,
        source_release_id=bundle.target.release_id,
        p2_release_id=p2_release_id,
        attribution_run_id=run_id,
        aircraft_id=bundle.target.aircraft_id,
        capability_type=bundle.target.capability_type,
        reference_condition_id=bundle.reference_condition.reference_condition_id,
        adjusted_value=None,
        unit=bundle.target.unit,
        uncertainty_lower=None,
        uncertainty_upper=None,
        uncertainty_method=profile.uncertainty_method,
        uncertainty_level=profile.uncertainty_level,
        residual=None,
        factor_effects=(),
        claim_level=profile.claim_level,
        status="NOT_IDENTIFIABLE",
        reason_codes=(reason,),
        evidence_set_id=evidence_set_id,
        estimate_time=execution_time_utc,
        created_at=execution_time_utc,
        supersedes_estimate_id=supersedes_estimate_id,
        logical_hash=logical_hash,
    )
    return P2AttributionExecution(
        target_feature_set=target_feature_set,
        attribution_run=run,
        adjusted_estimate=estimate,
        model_artifact_json=None,
    )


def execute_p2_attribution(
    *,
    bundle: P2InputBundle,
    target_feature_set: P2FactorFeatureSet,
    cohort_rows: Sequence[P2CohortRow],
    reference_factor_values: CompleteFactorInput,
    p2_release_id: str,
    evidence_set_id: str,
    execution_time_utc: str,
    created_by: str | None = None,
    supersedes_estimate_id: str | None = None,
    factor_effect_semantics: str | None = None,
    profile: P2ExecutionProfile | None = None,
) -> P2AttributionExecution:
    active = profile or P2ExecutionProfile.from_canonical()
    _uuid(p2_release_id, "p2_release_id")
    _uuid(evidence_set_id, "evidence_set_id")
    _utc(execution_time_utc, "execution_time_utc")
    if supersedes_estimate_id is not None:
        _uuid(supersedes_estimate_id, "supersedes_estimate_id")
    semantics = (
        active.factor_effect_semantics
        if factor_effect_semantics is None
        else factor_effect_semantics
    )
    validate_factor_effect_semantics(
        semantics=semantics,
        causal_evidence_set_id=None,
    )
    if semantics != active.factor_effect_semantics:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_CAUSAL_EVIDENCE_REQUIRED",
            factor_effect_semantics,
        )
    factor_order = target_feature_set.factor_order
    reference = _reference_vector(reference_factor_values, factor_order)
    validation_reason = _validate_execution_inputs(
        bundle=bundle,
        target_feature_set=target_feature_set,
        cohort_rows=cohort_rows,
        factor_order=factor_order,
        profile=active,
    )
    run_request_hash = _run_request_hash(
        bundle=bundle,
        target_feature_set=target_feature_set,
        cohort_rows=cohort_rows,
        factor_order=factor_order,
        reference=reference,
        profile=active,
        factor_effect_semantics=factor_effect_semantics,
    )
    if validation_reason is not None:
        return _not_identifiable(
            reason=validation_reason,
            bundle=bundle,
            target_feature_set=target_feature_set,
            p2_release_id=p2_release_id,
            evidence_set_id=evidence_set_id,
            execution_time_utc=execution_time_utc,
            created_by=created_by,
            supersedes_estimate_id=supersedes_estimate_id,
            run_request_hash=run_request_hash,
            profile=active,
        )

    ordered_rows = tuple(
        sorted(cohort_rows, key=lambda row: row.observation.observation_id)
    )
    target_vector = _complete_vector(target_feature_set, factor_order, active)
    if target_vector is None:
        raise AssertionError("validated target feature set unexpectedly incomplete")
    complete_vectors: list[tuple[Decimal, ...]] = []
    for row in ordered_rows:
        vector = _complete_vector(row.feature_set, factor_order, active)
        if vector is None:
            raise AssertionError("validated cohort feature set unexpectedly incomplete")
        complete_vectors.append(vector)
    vectors = tuple(complete_vectors)
    if not _in_support(vectors, target_vector, reference):
        return _not_identifiable(
            reason="REFERENCE_CONDITION_OUT_OF_SUPPORT",
            bundle=bundle,
            target_feature_set=target_feature_set,
            p2_release_id=p2_release_id,
            evidence_set_id=evidence_set_id,
            execution_time_utc=execution_time_utc,
            created_by=created_by,
            supersedes_estimate_id=supersedes_estimate_id,
            run_request_hash=run_request_hash,
            profile=active,
        )

    full_fit = _fit(ordered_rows, vectors, factor_order, active)
    if isinstance(full_fit, str):
        return _not_identifiable(
            reason=full_fit,
            bundle=bundle,
            target_feature_set=target_feature_set,
            p2_release_id=p2_release_id,
            evidence_set_id=evidence_set_id,
            execution_time_utc=execution_time_utc,
            created_by=created_by,
            supersedes_estimate_id=supersedes_estimate_id,
            run_request_hash=run_request_hash,
            profile=active,
        )
    target_observed = _decimal(bundle.target.observed_value, "target observed value")
    adjusted, effects = _adjusted(
        target_observed,
        target_vector,
        reference,
        full_fit,
    )
    residual = target_observed - _prediction(full_fit, target_vector)

    subjects = tuple(sorted({row.observation.subject_entity_id for row in ordered_rows}))
    jackknife: list[tuple[str, Decimal]] = []
    for subject in subjects:
        fold_rows = tuple(
            row for row in ordered_rows if row.observation.subject_entity_id != subject
        )
        if len({row.observation.subject_entity_id for row in fold_rows}) < len(factor_order) + 2:
            return _not_identifiable(
                reason="UNCERTAINTY_NOT_ESTIMABLE",
                bundle=bundle,
                target_feature_set=target_feature_set,
                p2_release_id=p2_release_id,
                evidence_set_id=evidence_set_id,
                execution_time_utc=execution_time_utc,
                created_by=created_by,
                supersedes_estimate_id=supersedes_estimate_id,
                run_request_hash=run_request_hash,
                profile=active,
            )
        fold_vectors = tuple(
            cast(tuple[Decimal, ...], _complete_vector(row.feature_set, factor_order, active))
            for row in fold_rows
        )
        if not _in_support(fold_vectors, target_vector, reference):
            return _not_identifiable(
                reason="UNCERTAINTY_NOT_ESTIMABLE",
                bundle=bundle,
                target_feature_set=target_feature_set,
                p2_release_id=p2_release_id,
                evidence_set_id=evidence_set_id,
                execution_time_utc=execution_time_utc,
                created_by=created_by,
                supersedes_estimate_id=supersedes_estimate_id,
                run_request_hash=run_request_hash,
                profile=active,
            )
        fold_fit = _fit(fold_rows, fold_vectors, factor_order, active)
        if isinstance(fold_fit, str):
            return _not_identifiable(
                reason="UNCERTAINTY_NOT_ESTIMABLE",
                bundle=bundle,
                target_feature_set=target_feature_set,
                p2_release_id=p2_release_id,
                evidence_set_id=evidence_set_id,
                execution_time_utc=execution_time_utc,
                created_by=created_by,
                supersedes_estimate_id=supersedes_estimate_id,
                run_request_hash=run_request_hash,
                profile=active,
            )
        fold_adjusted, _fold_effects = _adjusted(
            target_observed,
            target_vector,
            reference,
            fold_fit,
        )
        jackknife.append((subject, fold_adjusted))

    with localcontext() as context:
        context.prec = active.decimal_precision
        context.rounding = ROUND_HALF_EVEN
        subject_total = Decimal(len(jackknife))
        theta_bar = sum((value for _subject, value in jackknife), Decimal(0)) / subject_total
        variance_sum = sum(
            ((value - theta_bar) ** 2 for _subject, value in jackknife),
            Decimal(0),
        )
        standard_error = (
            (subject_total - Decimal(1)) / subject_total * variance_sum
        ).sqrt()
        uncertainty_lower = adjusted - active.uncertainty_z * standard_error
        uncertainty_upper = adjusted + active.uncertainty_z * standard_error

    diagnostics = {
        "reason_codes": [],
        "run_request_hash": run_request_hash,
        "rank_ratio": active.qstr(full_fit.rank_ratio),
        "observation_count": len(ordered_rows),
        "independent_subject_count": len(subjects),
        "uncertainty_method": active.uncertainty_method,
        "uncertainty_level": active.uncertainty_level,
        "factor_effect_semantics": active.factor_effect_semantics,
        "claim_level": active.claim_level,
    }
    model_artifact = {
        "profile_id": active.profile_id,
        "profile_version": active.profile_version,
        "attribution_spec_id": active.attribution_spec_id,
        "attribution_spec_version": active.attribution_spec_version,
        "model_plugin": active.model_plugin,
        "model_plugin_version": active.model_plugin_version,
        "factor_order": list(factor_order),
        "cohort_snapshot_id": bundle.cohort.dataset_snapshot_id,
        "cohort_data_hash": bundle.cohort.data_hash,
        "reference_condition_id": bundle.reference_condition.reference_condition_id,
        "reference_artifact_sha256": bundle.reference_condition.binding.artifact_sha256,
        "feature_spec_id": bundle.feature_spec.logical_key,
        "feature_spec_version": bundle.feature_spec.artifact_version,
        "feature_spec_sha256": bundle.feature_spec.artifact_sha256,
        "as_of_utc": bundle.as_of_utc,
        "scaling": {
            factor: {
                "mean": active.qstr(mean),
                "rms": active.qstr(scale),
            }
            for factor, mean, scale in zip(
                factor_order,
                full_fit.means,
                full_fit.scales,
                strict=True,
            )
        },
        "coefficients": {
            "intercept_standardized": active.qstr(full_fit.intercept),
            "standardized": {
                factor: active.qstr(value)
                for factor, value in zip(
                    factor_order,
                    full_fit.standardized_coefficients,
                    strict=True,
                )
            },
            "raw": {
                factor: active.qstr(value)
                for factor, value in zip(
                    factor_order,
                    full_fit.raw_coefficients,
                    strict=True,
                )
            },
        },
        "diagnostics": diagnostics,
        "jackknife_adjusted_values": [
            {
                "subject_entity_id": subject,
                "adjusted_value": active.qstr(value),
            }
            for subject, value in jackknife
        ],
    }
    model_artifact_json = _canonical_json(model_artifact)
    model_artifact_hash = hashlib.sha256(model_artifact_json.encode("ascii")).hexdigest()
    run_id = str(
        uuid5(
            active.run_namespace,
            f"{run_request_hash}|{model_artifact_hash}",
        )
    )
    run = P2AttributionRunProduct(
        attribution_run_id=run_id,
        attribution_spec_id=active.attribution_spec_id,
        attribution_spec_version=active.attribution_spec_version,
        model_plugin=active.model_plugin,
        model_plugin_version=active.model_plugin_version,
        training_dataset_snapshot_id=bundle.cohort.dataset_snapshot_id,
        reference_condition_id=bundle.reference_condition.reference_condition_id,
        status="IDENTIFIABLE",
        diagnostics_json=_canonical_json(diagnostics),
        model_artifact_uri=None,
        model_artifact_hash=model_artifact_hash,
        started_at=execution_time_utc,
        completed_at=execution_time_utc,
        created_by=created_by,
        run_request_hash=run_request_hash,
    )

    quantized_adjusted = active.quantize(adjusted)
    quantized_residual = active.quantize(residual)
    quantized_effects = tuple(
        (factor, float(active.quantize(value)))
        for factor, value in zip(factor_order, effects, strict=True)
    )
    lower = active.quantize(uncertainty_lower)
    upper = active.quantize(uncertainty_upper)
    logical = {
        "source_observation_id": bundle.target.observation_id,
        "source_release_id": bundle.target.release_id,
        "p2_release_id": p2_release_id,
        "attribution_run_id": run_id,
        "reference_condition_id": bundle.reference_condition.reference_condition_id,
        "adjusted_value": active.qstr(quantized_adjusted),
        "unit": bundle.target.unit,
        "uncertainty_lower": active.qstr(lower),
        "uncertainty_upper": active.qstr(upper),
        "residual": active.qstr(quantized_residual),
        "factor_effects": [
            {"factor": factor, "effect": active.qstr(value)}
            for factor, value in zip(factor_order, effects, strict=True)
        ],
        "claim_level": active.claim_level,
        "status": "IDENTIFIABLE",
        "reason_codes": [],
        "evidence_set_id": evidence_set_id,
        "model_artifact_hash": model_artifact_hash,
    }
    logical_hash = _canonical_hash(logical)
    estimate_id = str(
        uuid5(
            active.estimate_namespace,
            "|".join(
                (
                    p2_release_id,
                    bundle.target.observation_id,
                    run_id,
                    logical_hash,
                )
            ),
        )
    )
    estimate = P2AdjustedCapabilityEstimate(
        estimate_id=estimate_id,
        source_observation_id=bundle.target.observation_id,
        source_release_id=bundle.target.release_id,
        p2_release_id=p2_release_id,
        attribution_run_id=run_id,
        aircraft_id=bundle.target.aircraft_id,
        capability_type=bundle.target.capability_type,
        reference_condition_id=bundle.reference_condition.reference_condition_id,
        adjusted_value=float(quantized_adjusted),
        unit=bundle.target.unit,
        uncertainty_lower=float(lower),
        uncertainty_upper=float(upper),
        uncertainty_method=active.uncertainty_method,
        uncertainty_level=active.uncertainty_level,
        residual=float(quantized_residual),
        factor_effects=quantized_effects,
        claim_level=active.claim_level,
        status="IDENTIFIABLE",
        reason_codes=(),
        evidence_set_id=evidence_set_id,
        estimate_time=execution_time_utc,
        created_at=execution_time_utc,
        supersedes_estimate_id=supersedes_estimate_id,
        logical_hash=logical_hash,
    )
    return P2AttributionExecution(
        target_feature_set=target_feature_set,
        attribution_run=run,
        adjusted_estimate=estimate,
        model_artifact_json=model_artifact_json,
    )
