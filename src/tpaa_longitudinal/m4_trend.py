"""M4 Batch 2 governed observed-performance trend engine."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID, uuid5

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

from .m4_sample import (
    M4LongitudinalError,
    M4LongitudinalSample,
    M4LongitudinalScope,
)

M4_TREND_SEMANTICS = "OBSERVED_PERFORMANCE"
M4_TREND_PROFILE_ID = "M4_P1_OBSERVED_TREND_V1"
M4_TREND_PROFILE_VERSION = "1.0.0"
M4_TREND_NAMESPACE = UUID("4d3f3d75-9cf5-5f0a-9a5a-3e47f54df9a6")


@dataclass(frozen=True)
class M4TrendAuthority:
    profile_id: str
    profile_version: str
    profile_hash: str
    x_axis_semantics: str
    valid_sample_status: str
    ewma_alpha: float
    slope_max_valid_points: int
    slope_min_valid_points: int
    stability_max_valid_points: int
    stability_min_valid_points: int
    trend_status_values: tuple[str, ...]
    no_valid_series_status: str
    valid_series_status: str
    insufficient_trend_reason: str
    no_valid_reason: str
    input_manifest_schema: str


@dataclass(frozen=True)
class M4TrendBridge:
    trend_bridge_id: str
    bridge_code: str
    bridge_version: str
    from_metric_semantic_id: str
    from_metric_semantic_version: int
    to_metric_semantic_id: str
    to_metric_semantic_version: int
    conversion_kind: str
    conversion_spec_json: str
    applicability_json: str
    validation_dataset_snapshot_id: str
    validation_result_hash: str
    approved_by: str
    approved_at_utc: str
    bridge_hash: str
    status: str

    def __post_init__(self) -> None:
        _uuid(self.trend_bridge_id, field="trend_bridge_id")
        _uuid(
            self.validation_dataset_snapshot_id,
            field="validation_dataset_snapshot_id",
        )
        if not self.bridge_code.strip() or not self.bridge_version.strip():
            raise M4LongitudinalError(
                "M4_TREND_BRIDGE_IDENTITY_INVALID",
                self.bridge_code,
            )
        if (
            self.from_metric_semantic_version < 1
            or self.to_metric_semantic_version < 1
        ):
            raise M4LongitudinalError(
                "M4_TREND_BRIDGE_SEMANTIC_VERSION_INVALID",
                self.bridge_code,
            )
        if self.conversion_kind not in {
            "IDENTITY",
            "AFFINE",
            "APPROVED_FUNCTION",
        }:
            raise M4LongitudinalError(
                "M4_TREND_BRIDGE_CONVERSION_KIND_INVALID",
                self.conversion_kind,
            )
        if self.status not in {"DRAFT", "APPROVED", "RETIRED"}:
            raise M4LongitudinalError(
                "M4_TREND_BRIDGE_STATUS_INVALID",
                self.status,
            )
        _json_object(self.conversion_spec_json, field="conversion_spec_json")
        _json_object(self.applicability_json, field="applicability_json")
        _hash64(
            self.validation_result_hash,
            field="validation_result_hash",
        )
        _hash64(self.bridge_hash, field="bridge_hash")
        _utc(self.approved_at_utc, field="approved_at_utc")
        if not self.approved_by.strip():
            raise M4LongitudinalError(
                "M4_TREND_BRIDGE_APPROVER_REQUIRED",
                self.bridge_code,
            )


@dataclass(frozen=True)
class M4PerformanceTrendPoint:
    trend_id: str
    point_order: int
    sample_id: str
    subject_type: str
    subject_id: str
    session_order: int
    occurred_at_utc: str | None
    value: float | None
    sample_status: str
    configuration_key: str
    lifecycle_marker_refs: tuple[dict[str, object], ...]

    def projection(self) -> dict[str, object]:
        return {
            "trend_id": self.trend_id,
            "point_order": self.point_order,
            "sample_id": self.sample_id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "session_order": self.session_order,
            "occurred_at_utc": self.occurred_at_utc,
            "value": self.value,
            "sample_status": self.sample_status,
            "configuration_key": self.configuration_key,
            "lifecycle_marker_refs": list(self.lifecycle_marker_refs),
        }


@dataclass(frozen=True)
class M4PerformanceTrendSeries:
    trend_id: str
    release_id: str
    longitudinal_scope_id: str
    longitudinal_scope_key: str
    subject_type: str
    subject_id: str
    metric_definition_id: str
    metric_semantic_id: str
    metric_semantic_version: int
    comparison_key_hash: str
    trend_semantics: str
    x_axis_semantics: str
    session_order_scope_id: str
    as_of_session_order: int
    as_of_occurred_at_utc: str | None
    sample_count_total: int
    sample_count_valid: int
    current_value: float | None
    ewma_value: float | None
    slope: float | None
    slope_unit: str | None
    stability_mad: float | None
    trend_status: str
    status: str
    reason_codes: tuple[str, ...]
    trend_profile_id: str
    trend_profile_version: str
    trend_profile_hash: str
    input_hash: str
    bridge_hashes: tuple[str, ...]
    input_membership: tuple[tuple[str, str], ...]
    created_at_utc: str
    supersedes_trend_id: str | None
    points: tuple[M4PerformanceTrendPoint, ...]

    def projection(self) -> dict[str, object]:
        return {
            "trend_id": self.trend_id,
            "release_id": self.release_id,
            "longitudinal_scope_id": self.longitudinal_scope_id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "aircraft_id": (
                self.subject_id if self.subject_type == "AIRCRAFT" else None
            ),
            "mission_system_instance_id": (
                self.subject_id
                if self.subject_type == "MISSION_SYSTEM_INSTANCE"
                else None
            ),
            "metric_definition_id": self.metric_definition_id,
            "metric_semantic_id": self.metric_semantic_id,
            "metric_semantic_version": self.metric_semantic_version,
            "comparison_key_hash": self.comparison_key_hash,
            "trend_semantics": self.trend_semantics,
            "x_axis_semantics": self.x_axis_semantics,
            "session_order_scope_id": self.session_order_scope_id,
            "as_of_session_order": self.as_of_session_order,
            "as_of_occurred_at_utc": self.as_of_occurred_at_utc,
            "sample_count_total": self.sample_count_total,
            "sample_count_valid": self.sample_count_valid,
            "current_value": self.current_value,
            "ewma_value": self.ewma_value,
            "slope": self.slope,
            "slope_unit": self.slope_unit,
            "stability_mad": self.stability_mad,
            "trend_status": self.trend_status,
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "trend_profile_version": self.trend_profile_version,
            "input_hash": self.input_hash,
            "created_at": self.created_at_utc,
            "supersedes_trend_id": self.supersedes_trend_id,
        }

    def logical_product(self) -> dict[str, object]:
        return {
            "series": self.projection(),
            "trend_profile_id": self.trend_profile_id,
            "trend_profile_hash": self.trend_profile_hash,
            "bridge_hashes": list(self.bridge_hashes),
            "input_membership": [
                {
                    "input_session_release_id": release_id,
                    "input_sample_id": sample_id,
                }
                for release_id, sample_id in self.input_membership
            ],
            "points": [item.projection() for item in self.points],
        }

    @property
    def logical_hash(self) -> str:
        return _canonical_hash(self.logical_product())


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
        raise M4LongitudinalError(
            "M4_TREND_CANONICAL_JSON_INVALID",
            type(exc).__name__,
        ) from exc


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _hash64(value: str, *, field: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise M4LongitudinalError(
            "M4_TREND_HASH_INVALID",
            f"{field}={value!r}",
        )
    return value


def _uuid(value: str, *, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise M4LongitudinalError(
            "M4_TREND_UUID_INVALID",
            f"{field}={value!r}",
        ) from exc
    if str(parsed) != value or parsed.int == 0:
        raise M4LongitudinalError(
            "M4_TREND_UUID_INVALID",
            f"{field}={value!r}",
        )
    return value


def _utc(value: str, *, field: str) -> str:
    if not value.endswith("Z") or "T" not in value:
        raise M4LongitudinalError(
            "M4_TREND_UTC_INVALID",
            f"{field}={value!r}",
        )
    return value


def _json_object(value: str, *, field: str) -> dict[str, object]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise M4LongitudinalError(
            "M4_TREND_BRIDGE_JSON_INVALID",
            field,
        ) from exc
    if not isinstance(payload, dict):
        raise M4LongitudinalError(
            "M4_TREND_BRIDGE_JSON_INVALID",
            field,
        )
    return cast(dict[str, object], payload)


def load_m4_trend_authority(baseline_root: Path) -> M4TrendAuthority:
    artifact = CanonicalArtifactLoader(baseline_root).load(
        "M4_LONGITUDINAL_DEBRIEF_AUTHORITY",
        expectation=ArtifactExpectation(
            version="1.0.0",
            schema_version="1.6.0",
            required_top_level_keys=(
                "trend_profile",
                "trend_input_hash_contract",
            ),
        ),
    )
    profile_raw = artifact.payload["trend_profile"]
    input_raw = artifact.payload["trend_input_hash_contract"]
    if not isinstance(profile_raw, Mapping) or not isinstance(input_raw, Mapping):
        raise M4LongitudinalError(
            "M4_TREND_AUTHORITY_SHAPE_INVALID",
            "root",
        )
    profile = dict(profile_raw)
    expected_hash = profile.get("profile_hash")
    if not isinstance(expected_hash, str):
        raise M4LongitudinalError(
            "M4_TREND_AUTHORITY_SHAPE_INVALID",
            "profile_hash",
        )
    hash_material = dict(profile)
    hash_material.pop("profile_hash", None)
    hash_material.pop("profile_hash_algorithm", None)
    if _canonical_hash(hash_material) != expected_hash:
        raise M4LongitudinalError(
            "M4_TREND_PROFILE_HASH_DRIFT",
            expected_hash,
        )

    ewma = profile.get("ewma")
    slope = profile.get("slope")
    stability = profile.get("stability")
    trend_status = profile.get("trend_status")
    series_status = profile.get("series_status")
    if not all(
        isinstance(item, Mapping)
        for item in (ewma, slope, stability, trend_status, series_status)
    ):
        raise M4LongitudinalError(
            "M4_TREND_AUTHORITY_SHAPE_INVALID",
            "profile sections",
        )
    assert isinstance(ewma, Mapping)
    assert isinstance(slope, Mapping)
    assert isinstance(stability, Mapping)
    assert isinstance(trend_status, Mapping)
    assert isinstance(series_status, Mapping)

    if (
        profile.get("profile_id") != M4_TREND_PROFILE_ID
        or profile.get("profile_version") != M4_TREND_PROFILE_VERSION
        or profile.get("x_axis_semantics") != "SESSION_ORDER"
        or slope.get("estimator") != "ORDINARY_LEAST_SQUARES"
        or stability.get("statistic")
        != "UNSCALED_MEDIAN_ABSOLUTE_DEVIATION"
    ):
        raise M4LongitudinalError(
            "M4_TREND_AUTHORITY_CONTRACT_DRIFT",
            M4_TREND_PROFILE_ID,
        )
    numerator = ewma.get("alpha_numerator")
    denominator = ewma.get("alpha_denominator")
    if (
        isinstance(numerator, bool)
        or not isinstance(numerator, int)
        or isinstance(denominator, bool)
        or not isinstance(denominator, int)
        or denominator <= 0
    ):
        raise M4LongitudinalError(
            "M4_TREND_AUTHORITY_SHAPE_INVALID",
            "ewma alpha",
        )
    alpha = numerator / denominator
    declared_alpha = ewma.get("alpha")
    if (
        isinstance(declared_alpha, bool)
        or not isinstance(declared_alpha, (int, float))
        or not math.isclose(
            float(declared_alpha),
            alpha,
            rel_tol=0.0,
            abs_tol=1e-15,
        )
    ):
        raise M4LongitudinalError(
            "M4_TREND_AUTHORITY_CONTRACT_DRIFT",
            "ewma alpha",
        )

    values = trend_status.get("values")
    if not isinstance(values, list) or not all(
        isinstance(item, str) for item in values
    ):
        raise M4LongitudinalError(
            "M4_TREND_AUTHORITY_SHAPE_INVALID",
            "trend_status.values",
        )
    input_schema = input_raw.get("schema")
    if not isinstance(input_schema, str):
        raise M4LongitudinalError(
            "M4_TREND_AUTHORITY_SHAPE_INVALID",
            "trend_input_hash_contract.schema",
        )

    return M4TrendAuthority(
        profile_id=str(profile["profile_id"]),
        profile_version=str(profile["profile_version"]),
        profile_hash=expected_hash,
        x_axis_semantics=str(profile["x_axis_semantics"]),
        valid_sample_status=str(profile["valid_sample_status"]),
        ewma_alpha=alpha,
        slope_max_valid_points=int(cast(int, slope["max_valid_points"])),
        slope_min_valid_points=int(cast(int, slope["min_valid_points"])),
        stability_max_valid_points=int(
            cast(int, stability["max_valid_points"])
        ),
        stability_min_valid_points=int(
            cast(int, stability["min_valid_points"])
        ),
        trend_status_values=tuple(cast(list[str], values)),
        no_valid_series_status=str(series_status["no_valid_samples"]),
        valid_series_status=str(series_status["one_or_more_valid_samples"]),
        insufficient_trend_reason=str(
            series_status["insufficient_trend_reason"]
        ),
        no_valid_reason=str(series_status["no_valid_reason"]),
        input_manifest_schema=input_schema,
    )


def _matching_bridge(
    *,
    sample: M4LongitudinalSample,
    scope: M4LongitudinalScope,
    bridges: Sequence[M4TrendBridge],
) -> M4TrendBridge:
    matching = tuple(
        bridge
        for bridge in bridges
        if bridge.from_metric_semantic_id == sample.metric_semantic_id
        and bridge.from_metric_semantic_version
        == sample.metric_semantic_version
        and bridge.to_metric_semantic_id == scope.metric_semantic_id
        and bridge.to_metric_semantic_version
        == scope.metric_semantic_version
    )
    if not matching:
        raise M4LongitudinalError(
            "M4_TREND_BRIDGE_REQUIRED",
            f"{sample.metric_semantic_version}->{scope.metric_semantic_version}",
        )
    approved = tuple(item for item in matching if item.status == "APPROVED")
    if not approved:
        raise M4LongitudinalError(
            "M4_TREND_BRIDGE_NOT_APPROVED",
            matching[0].bridge_code,
        )
    if len(approved) != 1:
        raise M4LongitudinalError(
            "M4_TREND_BRIDGE_AMBIGUOUS",
            repr(tuple(item.bridge_code for item in approved)),
        )
    bridge = approved[0]
    if bridge.conversion_kind != "IDENTITY":
        raise M4LongitudinalError(
            "M4_TREND_BRIDGE_CONVERSION_NOT_EXECUTABLE",
            bridge.conversion_kind,
        )
    if _json_object(
        bridge.applicability_json,
        field="applicability_json",
    ):
        raise M4LongitudinalError(
            "M4_TREND_BRIDGE_APPLICABILITY_NOT_EXECUTABLE",
            bridge.bridge_code,
        )
    return bridge


def _validated_samples(
    *,
    scope: M4LongitudinalScope,
    samples: Sequence[M4LongitudinalSample],
    bridges: Sequence[M4TrendBridge],
) -> tuple[
    tuple[M4LongitudinalSample, ...],
    tuple[str, ...],
]:
    if not samples:
        raise M4LongitudinalError(
            "M4_TREND_INPUT_EMPTY",
            scope.longitudinal_scope_key,
        )
    ordered = tuple(
        sorted(
            samples,
            key=lambda item: (
                item.session_order
                if item.session_order is not None
                else -1
            ),
        )
    )
    orders: list[int] = []
    sample_ids: set[str] = set()
    bridge_hashes: set[str] = set()
    configuration_key = ordered[0].configuration_key
    for sample in ordered:
        _uuid(sample.sample_id, field="sample_id")
        _hash64(sample.logical_content_hash, field="logical_content_hash")
        if sample.sample_id in sample_ids:
            raise M4LongitudinalError(
                "M4_TREND_DUPLICATE_SAMPLE_ID",
                sample.sample_id,
            )
        sample_ids.add(sample.sample_id)
        if sample.session_order is None or sample.session_order < 0:
            raise M4LongitudinalError(
                "M4_TREND_SESSION_ORDER_REQUIRED",
                sample.sample_id,
            )
        orders.append(sample.session_order)
        if (
            sample.release_scope_type != "SESSION"
            or sample.sample_unit != "SESSION_CONFIG"
            or sample.subject_type != scope.subject_type
            or sample.subject_id != scope.subject_id
            or sample.metric_semantic_id != scope.metric_semantic_id
            or sample.session_order_scope_id != scope.session_order_scope_id
            or sample.configuration_key != configuration_key
        ):
            raise M4LongitudinalError(
                "M4_TREND_INPUT_SCOPE_MISMATCH",
                sample.sample_id,
            )
        if sample.metric_semantic_version == scope.metric_semantic_version:
            if sample.comparison_key_hash != scope.comparison_key_hash:
                raise M4LongitudinalError(
                    "M4_TREND_COMPARISON_KEY_SEGMENTED",
                    sample.sample_id,
                )
        else:
            bridge = _matching_bridge(
                sample=sample,
                scope=scope,
                bridges=bridges,
            )
            bridge_hashes.add(bridge.bridge_hash)
        if sample.status == "VALID":
            if (
                sample.value_numeric is None
                or isinstance(sample.value_numeric, bool)
                or not math.isfinite(sample.value_numeric)
            ):
                raise M4LongitudinalError(
                    "M4_TREND_VALID_VALUE_INVALID",
                    sample.sample_id,
                )
        elif sample.value_numeric is not None:
            raise M4LongitudinalError(
                "M4_TREND_NONVALID_VALUE_MUST_BE_NULL",
                sample.sample_id,
            )
    if len(set(orders)) != len(orders):
        raise M4LongitudinalError(
            "FAIL_CLOSED_DUPLICATE_SESSION_ORDER",
            repr(orders),
        )
    return ordered, tuple(sorted(bridge_hashes))


def build_performance_trend_series(
    *,
    authority: M4TrendAuthority,
    release_id: str,
    longitudinal_scope_id: str,
    metric_definition_id: str,
    metric_unit: str,
    scope: M4LongitudinalScope,
    samples: Sequence[M4LongitudinalSample],
    bridges: Sequence[M4TrendBridge] = (),
    created_at_utc: str,
    supersedes_trend_id: str | None = None,
) -> M4PerformanceTrendSeries:
    _uuid(release_id, field="release_id")
    _uuid(longitudinal_scope_id, field="longitudinal_scope_id")
    _uuid(metric_definition_id, field="metric_definition_id")
    _utc(created_at_utc, field="created_at_utc")
    if supersedes_trend_id is not None:
        _uuid(supersedes_trend_id, field="supersedes_trend_id")
    _hash64(scope.longitudinal_scope_key, field="longitudinal_scope_key")
    _hash64(scope.comparison_key_hash, field="comparison_key_hash")
    if authority.profile_version != scope.trend_profile_version:
        raise M4LongitudinalError(
            "M4_TREND_PROFILE_SCOPE_MISMATCH",
            scope.trend_profile_version,
        )
    if not metric_unit.strip():
        raise M4LongitudinalError(
            "M4_TREND_METRIC_UNIT_REQUIRED",
            metric_definition_id,
        )

    ordered, bridge_hashes = _validated_samples(
        scope=scope,
        samples=samples,
        bridges=bridges,
    )
    valid = tuple(
        item
        for item in ordered
        if item.status == authority.valid_sample_status
    )
    current_value = (
        valid[-1].value_numeric if valid else None
    )
    ewma_value: float | None = None
    for item in valid:
        assert item.value_numeric is not None
        ewma_value = (
            item.value_numeric
            if ewma_value is None
            else (
                authority.ewma_alpha * item.value_numeric
                + (1.0 - authority.ewma_alpha) * ewma_value
            )
        )

    slope: float | None = None
    stability_mad: float | None = None
    if len(valid) >= authority.slope_min_valid_points:
        slope_window = valid[-authority.slope_max_valid_points :]
        x0 = cast(int, slope_window[0].session_order)
        xs = [
            cast(int, item.session_order) - x0
            for item in slope_window
        ]
        ys = [cast(float, item.value_numeric) for item in slope_window]
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        denominator = sum((value - mean_x) ** 2 for value in xs)
        if denominator == 0:
            raise M4LongitudinalError(
                "FAIL_CLOSED_DUPLICATE_SESSION_ORDER",
                repr(xs),
            )
        slope = sum(
            (x_value - mean_x) * (y_value - mean_y)
            for x_value, y_value in zip(xs, ys, strict=True)
        ) / denominator

        stability_window = valid[
            -authority.stability_max_valid_points :
        ]
        stability_values = [
            cast(float, item.value_numeric)
            for item in stability_window
        ]
        center = statistics.median(stability_values)
        stability_mad = statistics.median(
            abs(value - center)
            for value in stability_values
        )
        projected_change = slope * (xs[-1] - xs[0])
        if stability_mad == 0.0:
            if slope > 0:
                trend_status = "INCREASING"
            elif slope < 0:
                trend_status = "DECREASING"
            else:
                trend_status = "STABLE"
        elif abs(projected_change) <= stability_mad:
            trend_status = "STABLE"
        elif projected_change > 0:
            trend_status = "INCREASING"
        else:
            trend_status = "DECREASING"
        reason_codes: tuple[str, ...] = ()
    else:
        trend_status = "INSUFFICIENT_DATA"
        if valid:
            reason_codes = (authority.insufficient_trend_reason,)
        else:
            reason_codes = (authority.no_valid_reason,)

    if trend_status not in authority.trend_status_values:
        raise M4LongitudinalError(
            "M4_TREND_STATUS_AUTHORITY_MISMATCH",
            trend_status,
        )
    status = (
        authority.valid_series_status
        if valid
        else authority.no_valid_series_status
    )
    input_manifest = {
        "schema": authority.input_manifest_schema,
        "comparison_key_hash": scope.comparison_key_hash,
        "longitudinal_scope_key": scope.longitudinal_scope_key,
        "x_axis_semantics": authority.x_axis_semantics,
        "trend_profile_id": authority.profile_id,
        "trend_profile_version": authority.profile_version,
        "trend_profile_hash": authority.profile_hash,
        "samples": [
            {
                "sample_id": item.sample_id,
                "logical_content_hash": item.logical_content_hash,
            }
            for item in ordered
        ],
        "bridge_hashes": list(bridge_hashes),
    }
    input_hash = _canonical_hash(input_manifest)
    trend_id = str(
        uuid5(
            M4_TREND_NAMESPACE,
            (
                f"{release_id}|{longitudinal_scope_id}|"
                f"{metric_definition_id}|{input_hash}"
            ),
        )
    )
    points = tuple(
        M4PerformanceTrendPoint(
            trend_id=trend_id,
            point_order=index,
            sample_id=item.sample_id,
            subject_type=item.subject_type,
            subject_id=item.subject_id,
            session_order=cast(int, item.session_order),
            occurred_at_utc=item.occurred_at_utc,
            value=(
                item.value_numeric
                if item.status == authority.valid_sample_status
                else None
            ),
            sample_status=item.status,
            configuration_key=item.configuration_key,
            lifecycle_marker_refs=(),
        )
        for index, item in enumerate(ordered, start=1)
    )
    last = ordered[-1]
    input_membership = tuple(
        (item.release_id, item.sample_id)
        for item in ordered
    )
    return M4PerformanceTrendSeries(
        trend_id=trend_id,
        release_id=release_id,
        longitudinal_scope_id=longitudinal_scope_id,
        longitudinal_scope_key=scope.longitudinal_scope_key,
        subject_type=scope.subject_type,
        subject_id=scope.subject_id,
        metric_definition_id=metric_definition_id,
        metric_semantic_id=scope.metric_semantic_id,
        metric_semantic_version=scope.metric_semantic_version,
        comparison_key_hash=scope.comparison_key_hash,
        trend_semantics=M4_TREND_SEMANTICS,
        x_axis_semantics=authority.x_axis_semantics,
        session_order_scope_id=scope.session_order_scope_id,
        as_of_session_order=cast(int, last.session_order),
        as_of_occurred_at_utc=last.occurred_at_utc,
        sample_count_total=len(ordered),
        sample_count_valid=len(valid),
        current_value=current_value,
        ewma_value=ewma_value,
        slope=slope,
        slope_unit=(
            f"{metric_unit}/session_order"
            if slope is not None
            else None
        ),
        stability_mad=stability_mad,
        trend_status=trend_status,
        status=status,
        reason_codes=reason_codes,
        trend_profile_id=authority.profile_id,
        trend_profile_version=authority.profile_version,
        trend_profile_hash=authority.profile_hash,
        input_hash=input_hash,
        bridge_hashes=bridge_hashes,
        input_membership=input_membership,
        created_at_utc=created_at_utc,
        supersedes_trend_id=supersedes_trend_id,
        points=points,
    )
