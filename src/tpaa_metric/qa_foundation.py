"""Executable M2 QA foundation Metric plugins with explicit authority blockers.

M2-MET-002 owns P1-QA-001..008. The general CatalogMetricEngine remains the
only execution engine. This module supplies algorithm plugins and a World-input
adapter only; it does not create a family-specific engine.

P1-QA-001 and P1-QA-002 intentionally fail closed until the frozen authority
gaps recorded on #97/#85 are resolved. The other six plugins implement only
formula semantics already frozen by P1_METRIC_CATALOG.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from tpaa_metric.catalog_engine import (
    CatalogMetricEngineError,
    M2MetricExecutionPlan,
    M2MetricPlugin,
    M2MetricPluginRequest,
    MetricPluginRegistry,
)

if TYPE_CHECKING:
    from tpaa_world.m2_radar_sensor import M2RadarSensorWorld
    from tpaa_world.m2_reference_time import M2ReferenceTimeWorld

QA_FOUNDATION_CODES = (
    "P1-QA-001",
    "P1-QA-002",
    "P1-QA-003",
    "P1-QA-004",
    "P1-QA-005",
    "P1-QA-006",
    "P1-QA-007",
    "P1-QA-008",
)
QA_AUTHORITY_BLOCKED_CODES = ("P1-QA-001", "P1-QA-002")
QA_EXECUTABLE_CODES = (
    "P1-QA-003",
    "P1-QA-004",
    "P1-QA-005",
    "P1-QA-006",
    "P1-QA-007",
    "P1-QA-008",
)


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"M2_QA_INPUT_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _mappings(value: object, *, field: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"M2_QA_INPUT_INVALID:{field}")
    return tuple(_mapping(item, field=f"{field}[{index}]") for index, item in enumerate(value))


def _text(mapping: Mapping[str, object], name: str, *, field: str) -> str:
    value = mapping.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"M2_QA_INPUT_INVALID:{field}.{name}")
    return value


def _finite(mapping: Mapping[str, object], name: str, *, field: str) -> float:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M2_QA_INPUT_INVALID:{field}.{name}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M2_QA_INPUT_NONFINITE:{field}.{name}")
    return result


def _integer(mapping: Mapping[str, object], name: str, *, field: str) -> int:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"M2_QA_INPUT_INVALID:{field}.{name}")
    return value


def _optional_finite(
    mapping: Mapping[str, object],
    name: str,
    *,
    field: str,
) -> float | None:
    value = mapping.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M2_QA_INPUT_INVALID:{field}.{name}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M2_QA_INPUT_NONFINITE:{field}.{name}")
    return result


def _operator_finite(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M2_QA_OPERATOR_OUTPUT_INVALID:{field}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M2_QA_OPERATOR_OUTPUT_NONFINITE:{field}")
    return result


def _metric_guard(
    request: M2MetricPluginRequest,
    *,
    metric_code: str,
    value_kind: str,
) -> None:
    definition = request.definition
    if definition.metric_code != metric_code:
        raise ValueError(
            f"M2_QA_PLUGIN_METRIC_MISMATCH:{metric_code}:{definition.metric_code}"
        )
    if definition.value_kind != value_kind:
        raise ValueError(
            f"M2_QA_PLUGIN_VALUE_KIND_MISMATCH:{metric_code}:{definition.value_kind}"
        )


def _instance(
    *,
    value_kind: str,
    value_numeric: float | None = None,
    value_structured: Mapping[str, object] | None = None,
    status: str = "VALID",
    reason_codes: Sequence[str] = (),
    diagnostics: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if value_kind == "NUMERIC":
        if status == "VALID" and value_numeric is None:
            raise ValueError("M2_QA_VALID_NUMERIC_MISSING")
        if value_structured is not None:
            raise ValueError("M2_QA_NUMERIC_STRUCTURED_SLOT_FORBIDDEN")
    elif value_kind == "STRUCTURED":
        if status == "VALID" and value_structured is None:
            raise ValueError("M2_QA_VALID_STRUCTURED_MISSING")
        if value_numeric is not None:
            raise ValueError("M2_QA_STRUCTURED_NUMERIC_SLOT_FORBIDDEN")
    else:
        raise ValueError(f"M2_QA_VALUE_KIND_UNSUPPORTED:{value_kind}")
    return {
        "status": status,
        "reason_codes": list(reason_codes),
        "value_kind": value_kind,
        "value_numeric": value_numeric,
        "value_structured": None if value_structured is None else dict(value_structured),
        "diagnostics": {} if diagnostics is None else dict(diagnostics),
    }


def _blocked_plugin(request: M2MetricPluginRequest) -> Mapping[str, object]:
    if request.definition.metric_code == "P1-QA-001":
        detail = (
            "P1-QA-001 requires frozen quaternion ordering/rotation/body-axis/"
            "az-el convention before non-identity frame transforms are executable"
        )
    elif request.definition.metric_code == "P1-QA-002":
        detail = (
            "P1-QA-002 requires frozen mapping from position/attitude/time "
            "uncertainty records into the six dimensions consumed by the 3x6 "
            "relative_state_jacobian"
        )
    else:
        detail = request.definition.metric_code
    raise CatalogMetricEngineError("M2_QA_AUTHORITY_GAP", detail)


def _qa003(request: M2MetricPluginRequest) -> Mapping[str, object]:
    _metric_guard(request, metric_code="P1-QA-003", value_kind="NUMERIC")
    segments = _mappings(request.input_payload.get("clock_segments"), field="clock_segments")
    mean = request.operators["MEAN_V1"]
    rms = request.operators["RMS_V1"]
    quantile = request.operators["QUANTILE_HF7_V1"]
    instances: list[dict[str, object]] = []
    for segment_index, segment in enumerate(segments):
        segment_id = _text(segment, "segment_id", field=f"clock_segments[{segment_index}]")
        transform_id = _text(
            segment,
            "time_transform_id",
            field=f"clock_segments[{segment_index}]",
        )
        samples = _mappings(
            segment.get("samples"),
            field=f"clock_segments[{segment_index}].samples",
        )
        offsets: list[float] = []
        sample_times: list[int] = []
        for sample_index, sample in enumerate(samples):
            field = f"clock_segments[{segment_index}].samples[{sample_index}]"
            mapped = _integer(
                sample,
                "sensor_timestamp_mapped_to_session_time_us",
                field=field,
            )
            aligned = _integer(sample, "aligned_session_time_us", field=field)
            sample_transform = _text(sample, "time_transform_id", field=field)
            if sample_transform != transform_id:
                raise ValueError(f"M2_QA_CLOCK_SEGMENT_TRANSFORM_DRIFT:{segment_id}")
            offsets.append(float(aligned - mapped))
            sample_times.append(aligned)
        if not offsets:
            instances.append(
                _instance(
                    value_kind="NUMERIC",
                    status="N_A",
                    reason_codes=("NO_VALID_CLOCK_SAMPLES",),
                    diagnostics={
                        "segment_id": segment_id,
                        "time_transform_id": transform_id,
                    },
                )
            )
            continue
        instances.append(
            _instance(
                value_kind="NUMERIC",
                value_numeric=_operator_finite(mean(tuple(offsets)), field="P1-QA-003.MEAN_V1"),
                diagnostics={
                    "segment_id": segment_id,
                    "time_transform_id": transform_id,
                    "sample_count": len(offsets),
                    "sample_session_time_min_us": min(sample_times),
                    "sample_session_time_max_us": max(sample_times),
                    "rmse_us": _operator_finite(rms(tuple(offsets)), field="P1-QA-003.RMS_V1"),
                    "p95_us": _operator_finite(quantile(tuple(offsets), 0.95), field="P1-QA-003.QUANTILE_HF7_V1"),
                },
            )
        )
    return {
        "metric_code": request.definition.metric_code,
        "subject_type": request.definition.subject_type,
        "instances": instances,
    }


def _qa004(request: M2MetricPluginRequest) -> Mapping[str, object]:
    _metric_guard(request, metric_code="P1-QA-004", value_kind="NUMERIC")
    samples = _mappings(request.input_payload.get("samples"), field="samples")
    median = request.operators["MEDIAN_V1"]
    quantile = request.operators["QUANTILE_HF7_V1"]
    latencies: list[float] = []
    for index, sample in enumerate(samples):
        field = f"samples[{index}]"
        sensor_time = _integer(sample, "sensor_measurement_effective_time_us", field=field)
        ownship_time = _integer(
            sample,
            "referenced_ownship_state_effective_time_us",
            field=field,
        )
        latencies.append(float(sensor_time - ownship_time))
    if not latencies:
        instance = _instance(
            value_kind="NUMERIC",
            status="N_A",
            reason_codes=("EFFECTIVE_TIME_UNRESOLVED",),
        )
    else:
        instance = _instance(
            value_kind="NUMERIC",
            value_numeric=_operator_finite(median(tuple(latencies)), field="P1-QA-004.MEDIAN_V1"),
            diagnostics={
                "sample_count": len(latencies),
                "p95_us": _operator_finite(quantile(tuple(latencies), 0.95), field="P1-QA-004.QUANTILE_HF7_V1"),
            },
        )
    return {
        "metric_code": request.definition.metric_code,
        "subject_type": request.definition.subject_type,
        "instances": [instance],
    }


def _qa005(request: M2MetricPluginRequest) -> Mapping[str, object]:
    _metric_guard(request, metric_code="P1-QA-005", value_kind="NUMERIC")
    samples = _mappings(request.input_payload.get("samples"), field="samples")
    median = request.operators["MEDIAN_V1"]
    quantile = request.operators["QUANTILE_HF7_V1"]
    ages: list[float] = []
    rejected = 0
    for index, sample in enumerate(samples):
        field = f"samples[{index}]"
        measurement = _integer(sample, "measurement_time_us", field=field)
        left = _integer(sample, "left_truth_time_us", field=field)
        right = _integer(sample, "right_truth_time_us", field=field)
        max_gap = _integer(sample, "profile.max_gap_us", field=field)
        if not left <= measurement <= right or max_gap <= 0:
            raise ValueError(f"M2_QA_INTERPOLATION_BRACKET_INVALID:{index}")
        age = max(measurement - left, right - measurement)
        if age > max_gap:
            rejected += 1
            continue
        ages.append(float(age))
    if not ages:
        instance = _instance(
            value_kind="NUMERIC",
            status="N_A",
            reason_codes=("NO_VALID_BRACKETING_POINTS",),
            diagnostics={"eligible_count": 0, "rejected_max_gap_count": rejected},
        )
    else:
        instance = _instance(
            value_kind="NUMERIC",
            value_numeric=_operator_finite(median(tuple(ages)), field="P1-QA-005.MEDIAN_V1"),
            diagnostics={
                "eligible_count": len(ages),
                "rejected_max_gap_count": rejected,
                "p95_us": _operator_finite(quantile(tuple(ages), 0.95), field="P1-QA-005.QUANTILE_HF7_V1"),
                "max_us": max(ages),
            },
        )
    return {
        "metric_code": request.definition.metric_code,
        "subject_type": request.definition.subject_type,
        "instances": [instance],
    }


def _qa006(request: M2MetricPluginRequest) -> Mapping[str, object]:
    _metric_guard(request, metric_code="P1-QA-006", value_kind="STRUCTURED")
    samples = _mappings(request.input_payload.get("samples"), field="samples")
    instances: list[dict[str, object]] = []
    for index, sample in enumerate(samples):
        field = f"samples[{index}]"
        residual_unit = _text(sample, "residual_unit", field=field)
        error_domain = _text(sample, "error_domain", field=field)
        raw = _finite(sample, "measurement_error", field=field)
        reference = _finite(sample, "reference_uncertainty", field=field)
        alignment = _finite(sample, "alignment_uncertainty", field=field)
        sensor = _optional_finite(
            sample,
            "sensor_measurement_uncertainty?",
            field=field,
        )
        normalized: float | None = None
        normalized_status = "INSUFFICIENT_UNCERTAINTY"
        if (
            reference >= 0.0
            and alignment >= 0.0
            and sensor is not None
            and sensor >= 0.0
        ):
            denominator = math.sqrt(
                reference * reference + alignment * alignment + sensor * sensor
            )
            if denominator > 0.0:
                normalized = raw / denominator
                normalized_status = "VALID"
        value = {
            "error_domain": error_domain,
            "residual_unit": residual_unit,
            "raw_residual": raw,
            "reference_uncertainty": reference,
            "alignment_uncertainty": alignment,
            "sensor_reported_uncertainty": sensor,
            "normalized_residual": normalized,
            "normalized_residual_status": normalized_status,
        }
        instances.append(
            _instance(
                value_kind="STRUCTURED",
                value_structured=value,
                diagnostics={"sample_index": index},
            )
        )
    if not instances:
        instances.append(
            _instance(
                value_kind="STRUCTURED",
                status="N_A",
                reason_codes=("REFERENCE_QUALITY_INVALID",),
            )
        )
    return {
        "metric_code": request.definition.metric_code,
        "subject_type": request.definition.subject_type,
        "instances": instances,
    }


def _uncertainty_sigma_us(record: Mapping[str, object], *, field: str) -> float:
    representation = _text(record, "representation_type", field=field)
    if representation == "SIGMA_1D":
        sigma = _finite(record, "value_us", field=field)
        if sigma < 0.0:
            raise ValueError(f"M2_QA_UNCERTAINTY_NEGATIVE:{field}")
        return sigma
    if representation == "TWO_SIDED_HARD_BOUND":
        bound = _finite(record, "bound_us", field=field)
        if bound < 0.0:
            raise ValueError(f"M2_QA_UNCERTAINTY_NEGATIVE:{field}")
        return bound / math.sqrt(3.0)
    if representation == "COVARIANCE":
        variance = _finite(record, "variance_us2", field=field)
        if variance < 0.0:
            raise ValueError(f"M2_QA_UNCERTAINTY_NEGATIVE:{field}")
        return math.sqrt(variance)
    raise ValueError(f"M2_QA_UNCERTAINTY_REPRESENTATION_UNSUPPORTED:{representation}")


def _time_uncertainty(
    request: M2MetricPluginRequest,
    *,
    metric_code: str,
    ref_field: str,
    residual_field: str,
) -> Mapping[str, object]:
    _metric_guard(request, metric_code=metric_code, value_kind="NUMERIC")
    record = _mapping(request.input_payload.get(ref_field), field=ref_field)
    sigma_source = _uncertainty_sigma_us(record, field=ref_field)
    sigma_transform = _finite(request.input_payload, residual_field, field=metric_code)
    if sigma_transform < 0.0:
        raise ValueError(f"M2_QA_UNCERTAINTY_NEGATIVE:{residual_field}")
    value = math.sqrt(
        sigma_source * sigma_source + sigma_transform * sigma_transform
    )
    return {
        "metric_code": request.definition.metric_code,
        "subject_type": request.definition.subject_type,
        "instances": [
            _instance(
                value_kind="NUMERIC",
                value_numeric=value,
                diagnostics={
                    "source_sigma_us": sigma_source,
                    "transform_residual_sigma_us": sigma_transform,
                    "uncertainty_provenance_ref": record.get("provenance_ref"),
                },
            )
        ],
    }


def _qa007(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return _time_uncertainty(
        request,
        metric_code="P1-QA-007",
        ref_field="ownship_nav_time_uncertainty_ref",
        residual_field="ownship_clock_transform_residual_sigma_us",
    )


def _qa008(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return _time_uncertainty(
        request,
        metric_code="P1-QA-008",
        ref_field="target_nav_time_uncertainty_ref",
        residual_field="target_clock_transform_residual_sigma_us",
    )


M2_QA_PLUGIN_IMPLEMENTATIONS: Mapping[str, M2MetricPlugin] = MappingProxyType(
    {
        "P1-QA-001": _blocked_plugin,
        "P1-QA-002": _blocked_plugin,
        "P1-QA-003": _qa003,
        "P1-QA-004": _qa004,
        "P1-QA-005": _qa005,
        "P1-QA-006": _qa006,
        "P1-QA-007": _qa007,
        "P1-QA-008": _qa008,
    }
)


def register_m2_qa_plugins(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
) -> None:
    """Register QA algorithms through the existing Catalog algorithm-id registry."""

    for metric_code in QA_FOUNDATION_CODES:
        definition = plan.definition(metric_code)
        registry.register(
            definition.algorithm_id,
            plugin_id=f"m2-qa-foundation:{metric_code}:v1",
            plugin=M2_QA_PLUGIN_IMPLEMENTATIONS[metric_code],
        )


def build_m2_qa_inputs(
    reference_time_world: M2ReferenceTimeWorld,
    radar_sensor_world: M2RadarSensorWorld,
) -> dict[str, Mapping[str, object]]:
    """Project frozen M2 World inputs into QA plugin payloads.

    This adapter does not execute Metric formulas. It preserves Catalog input
    semantic names inside samples and carries only deterministic World content.
    """

    time = reference_time_world.time_alignment
    uncertainty_by_name = {
        record.reference_name: record for record in time.uncertainty_records
    }

    def time_uncertainty_record(reference_name: str) -> dict[str, object]:
        try:
            record = uncertainty_by_name[reference_name]
        except KeyError as exc:
            raise CatalogMetricEngineError(
                "M2_QA_TIME_UNCERTAINTY_REF_MISSING",
                reference_name,
            ) from exc
        return {
            "representation_type": record.representation,
            "bound_us": record.bound_us,
            "provenance_ref": record.provenance_ref,
        }

    qa003_segments = [
        {
            "segment_id": segment.segment_id,
            "time_transform_id": segment.time_transform_id,
            "samples": [
                {
                    "sensor_timestamp_mapped_to_session_time_us": (
                        row.sensor_timestamp_mapped_to_session_time_us
                    ),
                    "aligned_session_time_us": row.aligned_session_time_us,
                    "time_transform_id": segment.time_transform_id,
                }
                for row in segment.records
            ],
        }
        for segment in time.clock_segments
    ]
    qa004_samples = [
        {
            "sensor_measurement_effective_time_us": (
                row.sensor_measurement_effective_time_us
            ),
            "referenced_ownship_state_effective_time_us": (
                row.referenced_ownship_state_effective_time_us
            ),
        }
        for row in time.latency_records
    ]
    qa005_samples = [
        {
            "measurement_time_us": row.measurement_time_us,
            "left_truth_time_us": row.left_truth_time_us,
            "right_truth_time_us": row.right_truth_time_us,
            "profile.max_gap_us": time.max_gap_us,
        }
        for row in time.interpolation_records
    ]

    alignment = radar_sensor_world.measurement_alignment
    qa006_samples = [
        {
            "residual_unit": row.residual_unit,
            "error_domain": row.error_domain,
            "measurement_error": row.measurement_error,
            "reference_uncertainty": row.reference_uncertainty,
            "alignment_uncertainty": row.alignment_uncertainty,
            "sensor_measurement_uncertainty?": row.sensor_measurement_uncertainty,
        }
        for row in alignment.rows
        if row.match_status == "MATCHED"
    ]

    return {
        "P1-QA-001": {
            "authority_gap": "FRAME_CONVENTION_UNRESOLVED",
            "world_logical_hash": reference_time_world.logical_hash,
        },
        "P1-QA-002": {
            "authority_gap": "UNCERTAINTY_JACOBIAN_DIMENSION_MAPPING_UNRESOLVED",
            "world_logical_hash": reference_time_world.logical_hash,
        },
        "P1-QA-003": {"clock_segments": qa003_segments},
        "P1-QA-004": {"samples": qa004_samples},
        "P1-QA-005": {"samples": qa005_samples},
        "P1-QA-006": {"samples": qa006_samples},
        "P1-QA-007": {
            "ownship_nav_time_uncertainty_ref": time_uncertainty_record(
                "ownship_nav_time_uncertainty_ref"
            ),
            "ownship_clock_transform_residual_sigma_us": (
                time.ownship_clock_transform_residual_sigma_us
            ),
        },
        "P1-QA-008": {
            "target_nav_time_uncertainty_ref": time_uncertainty_record(
                "target_nav_time_uncertainty_ref"
            ),
            "target_clock_transform_residual_sigma_us": (
                time.target_clock_transform_residual_sigma_us
            ),
        },
    }
