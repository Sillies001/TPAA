"""M7 Batch 2 deterministic P3 capability-model and surface engine."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import struct
from collections.abc import Mapping, Sequence
from datetime import datetime
from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid5

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader
from tpaa_longitudinal import (
    P3AdjustedEstimateInput,
    P3AuthorityPolicy,
    P3GovernanceError,
    P3LifecycleSegment,
    P3ModelValidationSnapshot,
    project_p2_adjusted_estimate,
)

_PROFILE_ARTIFACT_ID = "P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL_PROFILE"
_MODEL_NAMESPACE = UUID("ce91d78b-2d09-5d58-9362-2b7c7009fe67")
_SURFACE_NAMESPACE = UUID("2db788b7-5d85-58a6-b370-f087ec67ff64")


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


def _float_hex(value: float) -> str:
    if not math.isfinite(value):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_AUTHORITY_REQUIRED",
            "non-finite computed float",
        )
    return struct.pack(">d", value).hex()


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise P3GovernanceError("FAIL_CLOSED_P3_AUTHORITY_REQUIRED", field)
    return {str(key): item for key, item in value.items()}


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise P3GovernanceError("FAIL_CLOSED_P3_AUTHORITY_REQUIRED", field)
    return value


def _number(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise P3GovernanceError("FAIL_CLOSED_P3_AUTHORITY_REQUIRED", field)
    result = float(value)
    if not math.isfinite(result):
        raise P3GovernanceError("FAIL_CLOSED_P3_AUTHORITY_REQUIRED", field)
    return result


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise P3GovernanceError("FAIL_CLOSED_P3_AUTHORITY_REQUIRED", field)
    return value


def _utc_text(value: str, *, field: str) -> str:
    if not value.endswith("Z") or "T" not in value:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        ) from exc
    return value


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


@dataclass(frozen=True, slots=True)
class P3ModelExecutionProfile:
    profile_id: str
    profile_version: str
    profile_sha256: str
    model_spec_id: str
    model_spec_version: str
    plugin_name: str
    plugin_version: str
    subject_type: str
    minimum_total_points: int
    training_prefix_min_points: int
    training_prefix_max_points: int
    final_refit_max_points: int
    ewma_alpha: float
    surface_semantics: str
    estimate_claim_level: str

    @classmethod
    def from_canonical(
        cls,
        loader: CanonicalArtifactLoader | None = None,
    ) -> P3ModelExecutionProfile:
        canonical = loader or CanonicalArtifactLoader()
        artifact = canonical.load(
            _PROFILE_ARTIFACT_ID,
            expectation=ArtifactExpectation(
                version="1.0.0",
                schema_version="1.6.0",
                required_top_level_keys=(
                    "scope",
                    "runtime_binding",
                    "longitudinal_core",
                    "validation_contract",
                    "output_contract",
                ),
            ),
        )
        root = dict(artifact.payload)
        scope = _mapping(root["scope"], field="scope")
        runtime = _mapping(root["runtime_binding"], field="runtime_binding")
        core = _mapping(root["longitudinal_core"], field="longitudinal_core")
        validation = _mapping(
            root["validation_contract"],
            field="validation_contract",
        )
        output = _mapping(root["output_contract"], field="output_contract")
        ewma = _mapping(core["ewma"], field="longitudinal_core.ewma")
        slope = _mapping(core["slope"], field="longitudinal_core.slope")
        stability = _mapping(
            core["stability"],
            field="longitudinal_core.stability",
        )
        if (
            scope.get("subject_type") != "AIRCRAFT"
            or scope.get("aircraft_model_level_supported") is not False
            or scope.get("stronger_intrinsic_claim_supported") is not False
            or core.get("x_axis_semantics") != "SESSION_ORDER"
            or slope.get("estimator") != "ORDINARY_LEAST_SQUARES"
            or stability.get("statistic")
            != "UNSCALED_MEDIAN_ABSOLUTE_DEVIATION"
            or validation.get("strategy")
            != "TEMPORAL_LAST_POINT_HOLDOUT_THEN_FINAL_REFIT"
            or validation.get("holdout_count") != 1
            or validation.get(
                "implementation_selected_tolerance_or_multiplier_forbidden"
            )
            is not True
            or output.get("surface_extrapolation_forbidden") is not True
        ):
            raise P3GovernanceError(
                "FAIL_CLOSED_P3_AUTHORITY_REQUIRED",
                "P3 execution profile contract drift",
            )
        numerator = _integer(
            ewma.get("alpha_numerator"),
            field="ewma.alpha_numerator",
        )
        denominator = _integer(
            ewma.get("alpha_denominator"),
            field="ewma.alpha_denominator",
        )
        if denominator <= 0:
            raise P3GovernanceError(
                "FAIL_CLOSED_P3_AUTHORITY_REQUIRED",
                "ewma denominator",
            )
        alpha = numerator / denominator
        declared_alpha = _number(ewma.get("alpha"), field="ewma.alpha")
        if not math.isclose(alpha, declared_alpha, rel_tol=0.0, abs_tol=1e-15):
            raise P3GovernanceError(
                "FAIL_CLOSED_P3_AUTHORITY_REQUIRED",
                "ewma alpha drift",
            )
        final_window = _text(
            validation.get("final_refit_window"),
            field="validation.final_refit_window",
        )
        max_points = _integer(
            slope.get("max_valid_points"),
            field="slope.max_valid_points",
        )
        if "last up to 5" not in final_window or max_points != 5:
            raise P3GovernanceError(
                "FAIL_CLOSED_P3_AUTHORITY_REQUIRED",
                "final refit window drift",
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
            subject_type="AIRCRAFT",
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
            final_refit_max_points=max_points,
            ewma_alpha=alpha,
            surface_semantics=_text(
                output.get("surface_semantics"),
                field="output.surface_semantics",
            ),
            estimate_claim_level=_text(
                output.get("estimate_claim_level"),
                field="output.estimate_claim_level",
            ),
        )


@dataclass(frozen=True, slots=True)
class P3TrainingDatasetSnapshot:
    dataset_snapshot_id: str
    snapshot_type: str
    query_or_manifest: Mapping[str, object]
    input_refs: tuple[str, ...]
    data_hash: str
    schema_version: str
    created_at: str
    frozen: bool
    estimate_ids: tuple[str, ...]
    session_orders: tuple[int, ...]
    segment_snapshot_id: str
    validation_snapshot_id: str
    as_of_utc: str

    def projection(self) -> dict[str, object]:
        return {
            "dataset_snapshot_id": self.dataset_snapshot_id,
            "snapshot_type": self.snapshot_type,
            "query_or_manifest": dict(self.query_or_manifest),
            "input_refs": list(self.input_refs),
            "data_hash": self.data_hash,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "frozen": self.frozen,
        }


@dataclass(frozen=True, slots=True)
class P3ModelValidationResult:
    status: str
    training_estimate_ids: tuple[str, ...]
    validation_estimate_id: str
    predicted_value: float
    observed_value: float
    absolute_error: float
    training_mad: float
    heldout_p2_half_width: float
    acceptance_limit: float

    @property
    def passed(self) -> bool:
        return self.status == "VALIDATED"

    def projection(self) -> dict[str, object]:
        return {
            "status": self.status,
            "training_estimate_ids": list(self.training_estimate_ids),
            "validation_estimate_id": self.validation_estimate_id,
            "predicted_value": self.predicted_value,
            "observed_value": self.observed_value,
            "absolute_error": self.absolute_error,
            "training_mad": self.training_mad,
            "heldout_p2_half_width": self.heldout_p2_half_width,
            "acceptance_limit": self.acceptance_limit,
        }


@dataclass(frozen=True, slots=True)
class P3CapabilityModelProduct:
    capability_model_id: str
    model_spec_id: str
    model_spec_version: str
    subject_type: str
    subject_id: str
    capability_type: str
    training_dataset_snapshot_id: str
    plugin_name: str
    plugin_version: str
    model_artifact_uri: str
    model_artifact_hash: str
    validity_domain: Mapping[str, object]
    validation_metrics: Mapping[str, object]
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
            "plugin_name": self.plugin_name,
            "plugin_version": self.plugin_version,
            "model_artifact_uri": self.model_artifact_uri,
            "model_artifact_hash": self.model_artifact_hash,
            "validity_domain": dict(self.validity_domain),
            "validation_metrics": dict(self.validation_metrics),
            "status": self.status,
            "trained_at": self.trained_at,
            "published_at": self.published_at,
            "supersedes_model_id": self.supersedes_model_id,
        }


@dataclass(frozen=True, slots=True)
class P3CapabilityModelBuild:
    model: P3CapabilityModelProduct
    artifact: Mapping[str, object]
    artifact_bytes: bytes
    intercept: float
    slope: float
    current_value: float
    ewma_value: float
    stability_mad: float
    p3_uncertainty_half_width: float
    session_order_origin: int
    fit_estimate_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class P3CapabilitySurfaceProduct:
    surface_id: str
    capability_model_id: str
    surface_semantics: str
    axes: Mapping[str, object]
    dataset_uri: str
    dataset_hash: str
    uncertainty_dataset_uri: str | None
    validity_domain: Mapping[str, object]
    created_at: str

    def projection(self) -> dict[str, object]:
        return {
            "surface_id": self.surface_id,
            "capability_model_id": self.capability_model_id,
            "surface_semantics": self.surface_semantics,
            "axes": dict(self.axes),
            "dataset_uri": self.dataset_uri,
            "dataset_hash": self.dataset_hash,
            "uncertainty_dataset_uri": self.uncertainty_dataset_uri,
            "validity_domain": dict(self.validity_domain),
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class P3CapabilitySurfaceBuild:
    surface: P3CapabilitySurfaceProduct
    dataset: Mapping[str, object]
    dataset_bytes: bytes


@dataclass(frozen=True, slots=True)
class P3SurfaceEvaluation:
    validity_domain_status: str
    session_order: int
    value: float | None
    uncertainty_lower: float | None
    uncertainty_upper: float | None


def _ordered_estimates(
    *,
    estimates: Sequence[P3AdjustedEstimateInput],
    as_of_utc: str,
    policy: P3AuthorityPolicy,
) -> tuple[P3AdjustedEstimateInput, ...]:
    ordered = tuple(
        sorted(
            (
                project_p2_adjusted_estimate(
                    item,
                    as_of_utc=as_of_utc,
                    policy=policy,
                )
                for item in estimates
            ),
            key=lambda item: (item.session_order, item.estimate_id),
        )
    )
    if len({item.estimate_id for item in ordered}) != len(ordered):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            "duplicate estimate_id",
        )
    if len({item.session_order for item in ordered}) != len(ordered):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_SESSION_ORDER_REQUIRED",
            "duplicate session_order",
        )
    return ordered


def materialize_training_dataset(
    *,
    segment: P3LifecycleSegment,
    validation: P3ModelValidationSnapshot,
    estimates: Sequence[P3AdjustedEstimateInput],
    created_at_utc: str,
    policy: P3AuthorityPolicy | None = None,
    profile: P3ModelExecutionProfile | None = None,
) -> P3TrainingDatasetSnapshot:
    p = policy or P3AuthorityPolicy.from_canonical()
    q = profile or P3ModelExecutionProfile.from_canonical()
    if q.profile_sha256 != p.profile_sha256:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_AUTHORITY_REQUIRED",
            "profile hash does not match adopted P3 authority",
        )
    _utc_text(created_at_utc, field="created_at_utc")
    _uuid(validation.training_dataset_snapshot_id, field="training_dataset_snapshot_id")
    if (
        not segment.frozen
        or segment.snapshot_type != p.segment_snapshot_type
        or not validation.frozen
        or validation.snapshot_type != p.validation_snapshot_type
        or validation.segment_snapshot_id != segment.segment_snapshot_id
        or validation.training_dataset_snapshot_id
        == validation.validation_snapshot_id
    ):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            "segment/validation snapshot identity mismatch",
        )
    ordered = _ordered_estimates(
        estimates=estimates,
        as_of_utc=validation.as_of_utc,
        policy=p,
    )
    estimate_ids = tuple(item.estimate_id for item in ordered)
    if estimate_ids != segment.estimate_ids:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            "training dataset membership differs from lifecycle segment",
        )
    if len(ordered) < q.minimum_total_points:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            "training dataset minimum total points not met",
        )
    if validation.validation_estimate_ids != estimate_ids[-1:]:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_TRAINING_VALIDATION_LEAKAGE",
            "validation holdout is not exact final session-order point",
        )
    manifest = {
        "schema": "TPAA_P3_MODEL_TRAINING_V1",
        "authority_sha256": p.authority_sha256,
        "profile_sha256": p.profile_sha256,
        "segment_snapshot_id": segment.segment_snapshot_id,
        "segment_hash": segment.segment_hash,
        "validation_snapshot_id": validation.validation_snapshot_id,
        "validation_snapshot_hash": validation.data_hash,
        "aircraft_id": segment.aircraft_id,
        "capability_type": segment.capability_type,
        "configuration_key": segment.configuration_key,
        "reference_condition_id": segment.reference_condition_id,
        "metric_semantic_id": segment.metric_semantic_id,
        "metric_semantic_version": segment.metric_semantic_version,
        "unit": segment.unit,
        "as_of_utc": validation.as_of_utc,
        "members": [
            {
                "estimate_id": item.estimate_id,
                "p2_release_id": item.p2_release_id,
                "source_release_id": item.source_release_id,
                "source_observation_id": item.source_observation_id,
                "attribution_run_id": item.attribution_run_id,
                "configuration_snapshot_id": item.configuration_snapshot_id,
                "configuration_snapshot_hash": item.configuration_snapshot_hash,
                "session_id": item.session_id,
                "episode_id": item.episode_id,
                "session_order": item.session_order,
                "adjusted_value": item.adjusted_value,
                "uncertainty_lower": item.uncertainty_lower,
                "uncertainty_upper": item.uncertainty_upper,
                "knowledge_time_utc": item.knowledge_time_utc,
            }
            for item in ordered
        ],
    }
    data_hash = _canonical_hash(manifest)
    input_refs = (
        segment.segment_snapshot_id,
        validation.validation_snapshot_id,
        *estimate_ids,
    )
    return P3TrainingDatasetSnapshot(
        dataset_snapshot_id=validation.training_dataset_snapshot_id,
        snapshot_type=p.training_snapshot_type,
        query_or_manifest=manifest,
        input_refs=input_refs,
        data_hash=data_hash,
        schema_version="TPAA_P3_MODEL_TRAINING_V1",
        created_at=created_at_utc,
        frozen=True,
        estimate_ids=estimate_ids,
        session_orders=tuple(item.session_order for item in ordered),
        segment_snapshot_id=segment.segment_snapshot_id,
        validation_snapshot_id=validation.validation_snapshot_id,
        as_of_utc=validation.as_of_utc,
    )


def _ols(
    rows: Sequence[P3AdjustedEstimateInput],
) -> tuple[int, float, float]:
    if len(rows) < 2:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            "OLS requires at least two points",
        )
    origin = rows[0].session_order
    xs = [item.session_order - origin for item in rows]
    ys = [cast(float, item.adjusted_value) for item in rows]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    if denominator == 0:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_SESSION_ORDER_REQUIRED",
            "zero OLS denominator",
        )
    slope = sum(
        (x_value - mean_x) * (y_value - mean_y)
        for x_value, y_value in zip(xs, ys, strict=True)
    ) / denominator
    intercept = mean_y - slope * mean_x
    return origin, intercept, slope


def _mad(rows: Sequence[P3AdjustedEstimateInput]) -> float:
    values = [cast(float, item.adjusted_value) for item in rows]
    center = statistics.median(values)
    return float(statistics.median(abs(value - center) for value in values))


def _ewma(
    rows: Sequence[P3AdjustedEstimateInput],
    *,
    alpha: float,
) -> float:
    value: float | None = None
    for row in rows:
        current = cast(float, row.adjusted_value)
        value = current if value is None else alpha * current + (1.0 - alpha) * value
    if value is None:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            "EWMA input empty",
        )
    return value


def evaluate_temporal_holdout(
    *,
    validation: P3ModelValidationSnapshot,
    estimates: Sequence[P3AdjustedEstimateInput],
    policy: P3AuthorityPolicy | None = None,
    profile: P3ModelExecutionProfile | None = None,
) -> P3ModelValidationResult:
    p = policy or P3AuthorityPolicy.from_canonical()
    q = profile or P3ModelExecutionProfile.from_canonical()
    ordered = _ordered_estimates(
        estimates=estimates,
        as_of_utc=validation.as_of_utc,
        policy=p,
    )
    if tuple(item.estimate_id for item in ordered[-1:]) != validation.validation_estimate_ids:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_TRAINING_VALIDATION_LEAKAGE",
            "holdout identity drift",
        )
    training_all = ordered[:-1]
    training = training_all[-q.training_prefix_max_points :]
    if len(training) < q.training_prefix_min_points:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            "training prefix minimum not met",
        )
    if tuple(item.estimate_id for item in training) != validation.training_estimate_ids:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_TRAINING_VALIDATION_LEAKAGE",
            "training prefix identity drift",
        )
    heldout = ordered[-1]
    origin, intercept, slope = _ols(training)
    predicted = intercept + slope * (heldout.session_order - origin)
    observed = cast(float, heldout.adjusted_value)
    lower = cast(float, heldout.uncertainty_lower)
    upper = cast(float, heldout.uncertainty_upper)
    half_width = max(observed - lower, upper - observed)
    mad = _mad(training)
    error = abs(predicted - observed)
    limit = mad + half_width
    status = "VALIDATED" if error <= limit else "VALIDATION_FAILED"
    return P3ModelValidationResult(
        status=status,
        training_estimate_ids=tuple(item.estimate_id for item in training),
        validation_estimate_id=heldout.estimate_id,
        predicted_value=predicted,
        observed_value=observed,
        absolute_error=error,
        training_mad=mad,
        heldout_p2_half_width=half_width,
        acceptance_limit=limit,
    )


def execute_capability_model(
    *,
    training: P3TrainingDatasetSnapshot,
    validation: P3ModelValidationSnapshot,
    segment: P3LifecycleSegment,
    estimates: Sequence[P3AdjustedEstimateInput],
    trained_at_utc: str,
    supersedes_model_id: str | None = None,
    policy: P3AuthorityPolicy | None = None,
    profile: P3ModelExecutionProfile | None = None,
) -> P3CapabilityModelBuild:
    p = policy or P3AuthorityPolicy.from_canonical()
    q = profile or P3ModelExecutionProfile.from_canonical()
    if q.profile_sha256 != p.profile_sha256:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_AUTHORITY_REQUIRED",
            "profile hash does not match adopted P3 authority",
        )
    _utc_text(trained_at_utc, field="trained_at_utc")
    if (
        training.snapshot_type != p.training_snapshot_type
        or training.dataset_snapshot_id != validation.training_dataset_snapshot_id
        or training.validation_snapshot_id != validation.validation_snapshot_id
        or training.segment_snapshot_id != segment.segment_snapshot_id
        or training.estimate_ids != segment.estimate_ids
        or not training.frozen
    ):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            "training/model snapshot identity mismatch",
        )
    if supersedes_model_id is not None:
        _uuid(supersedes_model_id, field="supersedes_model_id")
    ordered = _ordered_estimates(
        estimates=estimates,
        as_of_utc=training.as_of_utc,
        policy=p,
    )
    if tuple(item.estimate_id for item in ordered) != training.estimate_ids:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            "model execution membership drift",
        )
    validation_result = evaluate_temporal_holdout(
        validation=validation,
        estimates=ordered,
        policy=p,
        profile=q,
    )
    if not validation_result.passed:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            "temporal holdout validation failed",
        )
    fit = ordered[-q.final_refit_max_points :]
    origin, intercept, slope = _ols(fit)
    stability_mad = _mad(fit)
    current_value = cast(float, fit[-1].adjusted_value)
    ewma_value = _ewma(fit, alpha=q.ewma_alpha)
    p2_half_widths = [
        max(
            cast(float, item.adjusted_value) - cast(float, item.uncertainty_lower),
            cast(float, item.uncertainty_upper) - cast(float, item.adjusted_value),
        )
        for item in fit
    ]
    p2_half_width_max = max(p2_half_widths)
    p3_half_width = max(stability_mad, p2_half_width_max)
    validity_domain = {
        "axis": "SESSION_ORDER",
        "session_order_min": fit[0].session_order,
        "session_order_max": fit[-1].session_order,
        "segment_snapshot_id": segment.segment_snapshot_id,
        "segment_hash": segment.segment_hash,
        "configuration_key": segment.configuration_key,
        "reference_condition_id": segment.reference_condition_id,
        "extrapolation": "FORBIDDEN",
    }
    validation_metrics = validation_result.projection()
    artifact = {
        "schema": "TPAA_P3_REFERENCE_CONDITION_OLS_MAD_MODEL_V1",
        "profile_id": q.profile_id,
        "profile_version": q.profile_version,
        "segment_snapshot_id": segment.segment_snapshot_id,
        "training_dataset_snapshot_id": training.dataset_snapshot_id,
        "validation_snapshot_id": validation.validation_snapshot_id,
        "aircraft_id": segment.aircraft_id,
        "capability_type": segment.capability_type,
        "reference_condition_id": segment.reference_condition_id,
        "unit": segment.unit,
        "configuration_key": segment.configuration_key,
        "fit_window_estimate_ids": [item.estimate_id for item in fit],
        "session_order_min": fit[0].session_order,
        "session_order_max": fit[-1].session_order,
        "intercept": intercept,
        "slope": slope,
        "current_value": current_value,
        "ewma_value": ewma_value,
        "stability_mad": stability_mad,
        "p2_uncertainty_half_width_max": p2_half_width_max,
        "p3_uncertainty_half_width": p3_half_width,
        "validation_metrics": validation_metrics,
        "validity_domain": validity_domain,
    }
    artifact_bytes = _canonical_bytes(artifact)
    artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()
    numeric_identity = {
        "intercept": _float_hex(intercept),
        "slope": _float_hex(slope),
        "current_value": _float_hex(current_value),
        "ewma_value": _float_hex(ewma_value),
        "stability_mad": _float_hex(stability_mad),
        "p2_uncertainty_half_width_max": _float_hex(p2_half_width_max),
        "p3_uncertainty_half_width": _float_hex(p3_half_width),
    }
    identity_hash = _canonical_hash(
        {
            "profile_id": q.profile_id,
            "profile_version": q.profile_version,
            "profile_sha256": q.profile_sha256,
            "model_spec_id": q.model_spec_id,
            "model_spec_version": q.model_spec_version,
            "segment_snapshot_id": segment.segment_snapshot_id,
            "segment_hash": segment.segment_hash,
            "training_dataset_snapshot_id": training.dataset_snapshot_id,
            "training_dataset_hash": training.data_hash,
            "validation_snapshot_id": validation.validation_snapshot_id,
            "validation_snapshot_hash": validation.data_hash,
            "numeric_identity": numeric_identity,
            "model_artifact_hash": artifact_hash,
        }
    )
    model_id = str(uuid5(_MODEL_NAMESPACE, identity_hash))
    model_uri = f"tpaa-object://p3-capability/models/{model_id}.json"
    model = P3CapabilityModelProduct(
        capability_model_id=model_id,
        model_spec_id=q.model_spec_id,
        model_spec_version=q.model_spec_version,
        subject_type=q.subject_type,
        subject_id=segment.aircraft_id,
        capability_type=segment.capability_type,
        training_dataset_snapshot_id=training.dataset_snapshot_id,
        plugin_name=q.plugin_name,
        plugin_version=q.plugin_version,
        model_artifact_uri=model_uri,
        model_artifact_hash=artifact_hash,
        validity_domain=validity_domain,
        validation_metrics=validation_metrics,
        status="VALIDATED",
        trained_at=trained_at_utc,
        published_at=None,
        supersedes_model_id=supersedes_model_id,
    )
    return P3CapabilityModelBuild(
        model=model,
        artifact=artifact,
        artifact_bytes=artifact_bytes,
        intercept=intercept,
        slope=slope,
        current_value=current_value,
        ewma_value=ewma_value,
        stability_mad=stability_mad,
        p3_uncertainty_half_width=p3_half_width,
        session_order_origin=origin,
        fit_estimate_ids=tuple(item.estimate_id for item in fit),
    )


def build_capability_surface(
    *,
    model_build: P3CapabilityModelBuild,
    created_at_utc: str,
    profile: P3ModelExecutionProfile | None = None,
) -> P3CapabilitySurfaceBuild:
    q = profile or P3ModelExecutionProfile.from_canonical()
    _utc_text(created_at_utc, field="created_at_utc")
    domain = dict(model_build.model.validity_domain)
    minimum = _integer(domain.get("session_order_min"), field="domain.session_order_min")
    maximum = _integer(domain.get("session_order_max"), field="domain.session_order_max")
    if maximum < minimum:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            "invalid model validity domain",
        )
    rows = []
    for session_order in range(minimum, maximum + 1):
        value = model_build.intercept + model_build.slope * (
            session_order - model_build.session_order_origin
        )
        rows.append(
            {
                "session_order": session_order,
                "value": value,
                "uncertainty_lower": value - model_build.p3_uncertainty_half_width,
                "uncertainty_upper": value + model_build.p3_uncertainty_half_width,
                "value_ieee754_hex": _float_hex(value),
            }
        )
    dataset = {
        "schema": "TPAA_P3_CAPABILITY_SURFACE_V1",
        "capability_model_id": model_build.model.capability_model_id,
        "model_artifact_hash": model_build.model.model_artifact_hash,
        "surface_semantics": q.surface_semantics,
        "axis": "SESSION_ORDER",
        "rows": rows,
        "validity_domain": domain,
    }
    dataset_bytes = _canonical_bytes(dataset)
    dataset_hash = hashlib.sha256(dataset_bytes).hexdigest()
    identity_hash = _canonical_hash(
        {
            "capability_model_id": model_build.model.capability_model_id,
            "surface_semantics": q.surface_semantics,
            "dataset_hash": dataset_hash,
        }
    )
    surface_id = str(uuid5(_SURFACE_NAMESPACE, identity_hash))
    dataset_uri = f"tpaa-object://p3-capability/surfaces/{surface_id}.json"
    surface = P3CapabilitySurfaceProduct(
        surface_id=surface_id,
        capability_model_id=model_build.model.capability_model_id,
        surface_semantics=q.surface_semantics,
        axes={
            "x": "SESSION_ORDER",
            "min": minimum,
            "max": maximum,
            "step": 1,
        },
        dataset_uri=dataset_uri,
        dataset_hash=dataset_hash,
        uncertainty_dataset_uri=None,
        validity_domain=domain,
        created_at=created_at_utc,
    )
    return P3CapabilitySurfaceBuild(
        surface=surface,
        dataset=dataset,
        dataset_bytes=dataset_bytes,
    )


def evaluate_surface(
    surface_build: P3CapabilitySurfaceBuild,
    *,
    session_order: int,
) -> P3SurfaceEvaluation:
    domain = dict(surface_build.surface.validity_domain)
    minimum = _integer(domain.get("session_order_min"), field="domain.session_order_min")
    maximum = _integer(domain.get("session_order_max"), field="domain.session_order_max")
    if session_order < minimum or session_order > maximum:
        return P3SurfaceEvaluation(
            validity_domain_status="OUT_OF_DOMAIN",
            session_order=session_order,
            value=None,
            uncertainty_lower=None,
            uncertainty_upper=None,
        )
    rows = surface_build.dataset.get("rows")
    if not isinstance(rows, list):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            "surface rows invalid",
        )
    match = next(
        (
            row
            for row in rows
            if isinstance(row, Mapping)
            and row.get("session_order") == session_order
        ),
        None,
    )
    if not isinstance(match, Mapping):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            "in-domain surface point missing",
        )
    return P3SurfaceEvaluation(
        validity_domain_status="IN_DOMAIN",
        session_order=session_order,
        value=_number(match.get("value"), field="surface.value"),
        uncertainty_lower=_number(
            match.get("uncertainty_lower"),
            field="surface.uncertainty_lower",
        ),
        uncertainty_upper=_number(
            match.get("uncertainty_upper"),
            field="surface.uncertainty_upper",
        ),
    )
