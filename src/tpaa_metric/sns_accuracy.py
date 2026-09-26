"""M2 SNS accuracy plugins over supplied canonical match contracts.

The 17 algorithms in this module execute through :class:`CatalogMetricEngine`'s
shared algorithm registry.  They do not construct associations, reference
relative state, frame transforms, uncertainty policy, or match-quality policy.
Those authorities must be supplied explicitly and are validated fail-closed.
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
    from tpaa_world import M2RadarSensorWorld, M2StageWorldLineage

SNS_ACCURACY_CODES = tuple(f"P1-SNS-{index:03d}" for index in range(5, 22))

_ERROR_DOMAINS = MappingProxyType(
    {
        "P1-SNS-005": "RANGE",
        "P1-SNS-006": "RANGE",
        "P1-SNS-007": "RANGE",
        "P1-SNS-008": "AZIMUTH",
        "P1-SNS-009": "AZIMUTH",
        "P1-SNS-010": "ELEVATION",
        "P1-SNS-011": "POSITION_3D",
        "P1-SNS-012": "RADIAL_VELOCITY",
        "P1-SNS-013": "CROSS_RANGE",
        "P1-SNS-014": "VERTICAL_POSITION",
        "P1-SNS-015": "RANGE",
        "P1-SNS-016": "RANGE",
        "P1-SNS-017": "RANGE",
        "P1-SNS-018": "AZIMUTH",
        "P1-SNS-019": "ELEVATION",
        "P1-SNS-020": "ELEVATION",
        "P1-SNS-021": "RADIAL_POSITION",
    }
)
_REQUIRED_PROFILE_FIELDS = frozenset(
    {
        "profile_id",
        "profile_version",
        "profile_hash",
        "max_interpolation_age_us",
        "accepted_reference_quality_statuses",
        "max_sigma_by_error_domain",
        "required_uncertainty_components",
        "na_reason_map",
    }
)
_REASON_KEYS = (
    "ASSOCIATION_INVALID",
    "MATCH_STATUS_INVALID",
    "INTERPOLATION_AGE_EXCEEDED",
    "REFERENCE_QUALITY_REJECTED",
    "UNCERTAINTY_COMPONENT_MISSING",
    "UNCERTAINTY_DOMAIN_CAP_EXCEEDED",
    "NO_VALID_MATCHED_SAMPLES",
)


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"M2_SNS_ACCURACY_INPUT_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _mappings(value: object, *, field: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"M2_SNS_ACCURACY_INPUT_INVALID:{field}")
    return tuple(_mapping(item, field=f"{field}[{index}]") for index, item in enumerate(value))


def _text(mapping: Mapping[str, object], name: str, *, field: str) -> str:
    value = mapping.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"M2_SNS_ACCURACY_INPUT_INVALID:{field}.{name}")
    return value


def _integer(mapping: Mapping[str, object], name: str, *, field: str) -> int:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"M2_SNS_ACCURACY_INPUT_INVALID:{field}.{name}")
    return value


def _finite(mapping: Mapping[str, object], name: str, *, field: str) -> float:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M2_SNS_ACCURACY_INPUT_INVALID:{field}.{name}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M2_SNS_ACCURACY_INPUT_NONFINITE:{field}.{name}")
    return result


def _vector3(mapping: Mapping[str, object], name: str, *, field: str) -> tuple[float, float, float]:
    value = mapping.get(name)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 3:
        raise ValueError(f"M2_SNS_ACCURACY_INPUT_INVALID:{field}.{name}")
    output: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"M2_SNS_ACCURACY_INPUT_INVALID:{field}.{name}")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(f"M2_SNS_ACCURACY_INPUT_NONFINITE:{field}.{name}")
        output.append(number)
    return cast(tuple[float, float, float], tuple(output))


def _strings(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"M2_SNS_ACCURACY_INPUT_INVALID:{field}")
    result = tuple(value)
    if not result or not all(isinstance(item, str) and item for item in result):
        raise ValueError(f"M2_SNS_ACCURACY_INPUT_INVALID:{field}")
    return cast(tuple[str, ...], result)


def _guard(request: M2MetricPluginRequest) -> bool:
    definition = request.definition
    code = definition.metric_code
    required_upstream = {
        "CONTRACT_REFERENCE_RELATIVE_STATE_V1",
        "P1-QA-001",
        "P1-QA-002",
        "CONTRACT_ASSOCIATION_RELATION_V1",
        "P1-QA-005",
        "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1",
    }
    if (
        code not in SNS_ACCURACY_CODES
        or definition.family != "SENSOR_ACCURACY"
        or definition.subject_type != "MISSION_SYSTEM_INSTANCE"
        or definition.value_kind != "NUMERIC"
        or definition.structured_output_schema_id is not None
        or definition.publication_route != "SYSTEM_PERFORMANCE_OBSERVATION"
        or definition.observation_lane != "SYSTEM_PERFORMANCE_OBSERVATION"
        or definition.applicability.applicability_mode != "SYSTEM_TYPE_EXACT"
        or definition.applicability.allowed_system_types != ("RADAR",)
        or set(definition.upstream_dependencies) != required_upstream
    ):
        raise ValueError(f"M2_SNS_ACCURACY_CATALOG_DEFINITION_DRIFT:{code}")
    return _text(request.input_payload, "system_type", field=code) == "RADAR"


def _profile(payload: Mapping[str, object], *, domain: str) -> Mapping[str, object]:
    profile = _mapping(payload.get("reference_match_quality_profile"), field="quality_profile")
    missing = sorted(_REQUIRED_PROFILE_FIELDS - set(profile))
    if missing:
        raise CatalogMetricEngineError(
            "M2_SNS_MATCH_QUALITY_PROFILE_INCOMPLETE",
            repr(missing),
        )
    _text(profile, "profile_id", field="quality_profile")
    _text(profile, "profile_version", field="quality_profile")
    profile_hash = _text(profile, "profile_hash", field="quality_profile")
    if len(profile_hash) != 64:
        raise ValueError("M2_SNS_ACCURACY_PROFILE_HASH_INVALID")
    max_age = _integer(profile, "max_interpolation_age_us", field="quality_profile")
    if max_age < 0:
        raise ValueError("M2_SNS_ACCURACY_PROFILE_MAX_AGE_INVALID")
    _strings(
        profile.get("accepted_reference_quality_statuses"),
        field="quality_profile.accepted_reference_quality_statuses",
    )
    required = _strings(
        profile.get("required_uncertainty_components"),
        field="quality_profile.required_uncertainty_components",
    )
    if len(set(required)) != len(required):
        raise ValueError("M2_SNS_ACCURACY_PROFILE_UNCERTAINTY_DUPLICATE")
    caps = _mapping(profile.get("max_sigma_by_error_domain"), field="quality_profile.max_sigma")
    if domain not in caps:
        raise CatalogMetricEngineError("M2_SNS_MATCH_QUALITY_DOMAIN_CAP_MISSING", domain)
    cap = caps[domain]
    if cap is not None and (
        isinstance(cap, bool)
        or not isinstance(cap, (int, float))
        or not math.isfinite(float(cap))
        or float(cap) < 0.0
    ):
        raise ValueError(f"M2_SNS_ACCURACY_PROFILE_SIGMA_CAP_INVALID:{domain}")
    reasons = _mapping(profile.get("na_reason_map"), field="quality_profile.na_reason_map")
    for key in _REASON_KEYS:
        _text(reasons, key, field="quality_profile.na_reason_map")
    return profile


def _eligible_samples(
    payload: Mapping[str, object],
    *,
    domain: str,
) -> tuple[tuple[Mapping[str, object], ...], tuple[dict[str, object], ...], Mapping[str, object]]:
    profile = _profile(payload, domain=domain)
    accepted = set(
        _strings(
            profile["accepted_reference_quality_statuses"],
            field="quality_profile.accepted_reference_quality_statuses",
        )
    )
    required = _strings(
        profile["required_uncertainty_components"],
        field="quality_profile.required_uncertainty_components",
    )
    reasons = _mapping(profile["na_reason_map"], field="quality_profile.na_reason_map")
    caps = _mapping(profile["max_sigma_by_error_domain"], field="quality_profile.max_sigma")
    cap_value = caps[domain]
    cap = None if cap_value is None else float(cast(float | int, cap_value))
    max_age = cast(int, profile["max_interpolation_age_us"])
    samples = _mappings(payload.get("samples"), field="samples")
    eligible: list[Mapping[str, object]] = []
    rejected: list[dict[str, object]] = []
    seen: set[str] = set()
    previous_time: int | None = None
    for index, sample in enumerate(samples):
        field = f"samples[{index}]"
        measurement_id = _text(sample, "measurement_id", field=field)
        if measurement_id in seen:
            raise ValueError(f"M2_SNS_ACCURACY_MEASUREMENT_DUPLICATE:{measurement_id}")
        seen.add(measurement_id)
        _text(sample, "reference_state_id", field=field)
        _text(sample, "association_id", field=field)
        _text(sample, "association_provenance", field=field)
        measurement_time = _integer(sample, "measurement_time_us", field=field)
        reference_time = _integer(sample, "reference_time_us", field=field)
        if previous_time is not None and measurement_time <= previous_time:
            raise ValueError("M2_SNS_ACCURACY_TIME_NOT_STRICTLY_INCREASING")
        previous_time = measurement_time
        rejection_key: str | None = None
        if sample.get("association_valid") is not True:
            rejection_key = "ASSOCIATION_INVALID"
        elif sample.get("match_status") != "MATCHED":
            rejection_key = "MATCH_STATUS_INVALID"
        elif abs(measurement_time - reference_time) > max_age:
            rejection_key = "INTERPOLATION_AGE_EXCEEDED"
        elif _text(sample, "reference_quality_status", field=field) not in accepted:
            rejection_key = "REFERENCE_QUALITY_REJECTED"
        uncertainty = _mapping(sample.get("uncertainty_components"), field=f"{field}.uncertainty")
        component_values: list[float] = []
        if rejection_key is None:
            for component in required:
                value = uncertainty.get(component)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                    or float(value) < 0.0
                ):
                    rejection_key = "UNCERTAINTY_COMPONENT_MISSING"
                    break
                component_values.append(float(value))
        if rejection_key is None and cap is not None:
            # Frozen Catalog rule: every required uncertainty component must be
            # individually within the domain cap. Do not invent a combined-sigma
            # policy here; a different combination rule would be C3 authority.
            if any(value > cap for value in component_values):
                rejection_key = "UNCERTAINTY_DOMAIN_CAP_EXCEEDED"
        if rejection_key is None:
            eligible.append(sample)
        else:
            rejected.append(
                {
                    "measurement_id": measurement_id,
                    "reason_code": _text(
                        reasons, rejection_key, field="quality_profile.na_reason_map"
                    ),
                }
            )
    return tuple(eligible), tuple(rejected), profile


def _scalar(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M2_SNS_ACCURACY_OPERATOR_OUTPUT_INVALID:{field}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M2_SNS_ACCURACY_OPERATOR_OUTPUT_NONFINITE:{field}")
    return result


def _position_error(
    sample: Mapping[str, object], measured: str, reference: str
) -> tuple[float, float, float]:
    left = _vector3(sample, measured, field="sample")
    right = _vector3(sample, reference, field="sample")
    return tuple(a - b for a, b in zip(left, right, strict=True))  # type: ignore[return-value]


def _norm(vector: Sequence[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def _radial_components(sample: Mapping[str, object]) -> tuple[float, float]:
    error = _position_error(
        sample,
        "measured_position_sensor_frame",
        "reference_position_sensor_frame",
    )
    reference = _vector3(sample, "reference_position_sensor_frame", field="sample")
    length = _norm(reference)
    if length == 0.0:
        raise ValueError("M2_SNS_ACCURACY_REFERENCE_LOS_ZERO")
    unit = tuple(value / length for value in reference)
    radial = sum(a * b for a, b in zip(error, unit, strict=True))
    cross = _norm(tuple(a - radial * b for a, b in zip(error, unit, strict=True)))
    return radial, cross


def _errors(
    request: M2MetricPluginRequest,
    samples: Sequence[Mapping[str, object]],
) -> tuple[float, ...]:
    code = request.definition.metric_code
    wrap = request.operators.get("WRAP_PI_V1")
    values: list[float] = []
    for sample in samples:
        if code in {
            "P1-SNS-005",
            "P1-SNS-006",
            "P1-SNS-007",
            "P1-SNS-015",
            "P1-SNS-016",
            "P1-SNS-017",
        }:
            value = _finite(sample, "measured_range_m", field="sample") - _finite(
                sample, "reference_range_m", field="sample"
            )
        elif code in {"P1-SNS-008", "P1-SNS-009", "P1-SNS-018"}:
            if wrap is None:
                raise ValueError("M2_SNS_ACCURACY_WRAP_OPERATOR_MISSING")
            value = _scalar(
                wrap(
                    _finite(sample, "measured_az_rad", field="sample")
                    - _finite(sample, "reference_az_rad", field="sample")
                ),
                field=f"{code}.WRAP_PI_V1",
            )
        elif code in {"P1-SNS-010", "P1-SNS-019", "P1-SNS-020"}:
            value = _finite(sample, "measured_el_rad", field="sample") - _finite(
                sample, "reference_el_rad", field="sample"
            )
        elif code == "P1-SNS-011":
            value = _norm(
                _position_error(
                    sample,
                    "measured_position_ecef_m",
                    "reference_target_position_ecef_m",
                )
            )
        elif code == "P1-SNS-012":
            value = _finite(sample, "measured_radial_velocity_mps", field="sample") - _finite(
                sample, "reference_range_rate_mps", field="sample"
            )
        elif code == "P1-SNS-013":
            _radial, value = _radial_components(sample)
        elif code == "P1-SNS-014":
            measured = _vector3(sample, "measured_position_local", field="sample")
            reference = _vector3(sample, "reference_position_local", field="sample")
            value = measured[2] - reference[2]
        elif code == "P1-SNS-021":
            value, _cross = _radial_components(sample)
        else:
            raise ValueError(f"M2_SNS_ACCURACY_CODE_UNSUPPORTED:{code}")
        values.append(value)
    return tuple(values)


def _aggregate(request: M2MetricPluginRequest, values: Sequence[float]) -> float:
    code = request.definition.metric_code
    if code in {"P1-SNS-005", "P1-SNS-015", "P1-SNS-019"}:
        mean = request.operators["MEAN_V1"]
        source = tuple(abs(value) for value in values) if code == "P1-SNS-015" else tuple(values)
        return _scalar(mean(source), field=f"{code}.MEAN_V1")
    if code == "P1-SNS-008":
        circular_mean = request.operators["CIRCULAR_MEAN_V1"]
        return _scalar(circular_mean(tuple(values)), field=f"{code}.CIRCULAR_MEAN_V1")
    if code in {
        "P1-SNS-006",
        "P1-SNS-009",
        "P1-SNS-010",
        "P1-SNS-011",
        "P1-SNS-012",
        "P1-SNS-013",
        "P1-SNS-014",
        "P1-SNS-021",
    }:
        rms = request.operators["RMS_V1"]
        return _scalar(rms(tuple(values)), field=f"{code}.RMS_V1")
    if code in {"P1-SNS-007", "P1-SNS-016", "P1-SNS-018", "P1-SNS-020"}:
        quantile = request.operators["QUANTILE_HF7_V1"]
        probability = 0.50 if code == "P1-SNS-016" else 0.95
        return _scalar(
            quantile(tuple(abs(value) for value in values), probability),
            field=f"{code}.QUANTILE_HF7_V1",
        )
    if code == "P1-SNS-017":
        return max(abs(value) for value in values)
    raise ValueError(f"M2_SNS_ACCURACY_AGGREGATE_UNSUPPORTED:{code}")


def _execute(request: M2MetricPluginRequest) -> Mapping[str, object]:
    if not _guard(request):
        return {
            "metric_code": request.definition.metric_code,
            "subject_type": request.definition.subject_type,
            "observation_lane": request.definition.observation_lane,
            "publication_route": request.definition.publication_route,
            "applicable": False,
            "reason_codes": ["SYSTEM_TYPE_NOT_APPLICABLE"],
            "instances": [],
        }
    domain = _ERROR_DOMAINS[request.definition.metric_code]
    samples, rejected, profile = _eligible_samples(request.input_payload, domain=domain)
    evidence = {
        "error_domain": domain,
        "reference_truth_profile_id": profile["profile_id"],
        "reference_truth_profile_version": profile["profile_version"],
        "reference_truth_profile_hash": profile["profile_hash"],
        "reference_match_quality_profile_id": profile["profile_id"],
        "reference_match_quality_profile_version": profile["profile_version"],
        "reference_match_quality_profile_hash": profile["profile_hash"],
        "eligible_measurement_ids": [item["measurement_id"] for item in samples],
        "eligible_sample_count": len(samples),
        "rejected_sample_count": len(rejected),
        "rejected_samples": list(rejected),
    }
    if not samples:
        reasons = _mapping(profile["na_reason_map"], field="quality_profile.na_reason_map")
        reason_codes = sorted({str(item["reason_code"]) for item in rejected})
        if not reason_codes:
            reason_codes = [
                _text(reasons, "NO_VALID_MATCHED_SAMPLES", field="quality_profile.na_reason_map")
            ]
        instance: dict[str, object] = {
            "status": "N_A",
            "reason_codes": reason_codes,
            "value_kind": "NUMERIC",
            "value_numeric": None,
            "value_structured": None,
            "evidence": evidence,
        }
    else:
        value = _aggregate(request, _errors(request, samples))
        instance = {
            "status": "VALID",
            "reason_codes": [],
            "value_kind": "NUMERIC",
            "value_numeric": value,
            "value_structured": None,
            "evidence": evidence,
        }
    return {
        "metric_code": request.definition.metric_code,
        "subject_type": request.definition.subject_type,
        "observation_lane": request.definition.observation_lane,
        "publication_route": request.definition.publication_route,
        "applicable": True,
        "instances": [instance],
    }


M2_SNS_ACCURACY_PLUGINS: Mapping[str, M2MetricPlugin] = MappingProxyType(
    {code: _execute for code in SNS_ACCURACY_CODES}
)


def register_m2_sns_accuracy_plugins(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
) -> None:
    """Register all 17 Catalog-owned SNS accuracy algorithms."""

    for metric_code in SNS_ACCURACY_CODES:
        definition = plan.definition(metric_code)
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m2-sns-accuracy:{metric_code}:v1",
            plugin=M2_SNS_ACCURACY_PLUGINS[metric_code],
        )


def build_m2_sns_accuracy_inputs(
    radar_world: M2RadarSensorWorld,
    stage_world: M2StageWorldLineage,
    *,
    associations: Mapping[str, Mapping[str, object]],
    reference_match_quality_profile: Mapping[str, object] | None = None,
) -> dict[str, Mapping[str, object]]:
    """Bind World rows to association and governed match-quality contracts.

    M2 consumes the C3-adopted match-quality profile carried by the measurement
    alignment World product. Callers may provide the profile explicitly only
    when it is byte-for-byte logically equal to that adopted contract. There is
    no synthetic/default profile fallback, association inference, or frame
    conversion.
    """

    if radar_world.mission_system.instance.system_type != "RADAR":
        raise CatalogMetricEngineError(
            "M2_SNS_SYSTEM_NOT_APPLICABLE", radar_world.mission_system_instance_id
        )
    if (
        stage_world.radar_sensor_world.logical_hash != radar_world.logical_hash
        or stage_world.status != "READY"
    ):
        raise CatalogMetricEngineError("M2_SNS_STAGE_WORLD_MISMATCH", stage_world.logical_hash)

    adopted_profile = dict(
        radar_world.measurement_alignment.quality_profile.as_contract()
    )
    if reference_match_quality_profile is None:
        quality_profile = adopted_profile
    else:
        quality_profile = dict(reference_match_quality_profile)
        if quality_profile != adopted_profile:
            raise CatalogMetricEngineError(
                "M2_SNS_MATCH_QUALITY_PROFILE_AUTHORITY_MISMATCH",
                (
                    f"supplied={quality_profile.get('profile_id')!r}@"
                    f"{quality_profile.get('profile_version')!r} "
                    f"adopted={adopted_profile.get('profile_id')!r}@"
                    f"{adopted_profile.get('profile_version')!r}"
                ),
            )
    missing = sorted(_REQUIRED_PROFILE_FIELDS - set(quality_profile))
    if missing:
        raise CatalogMetricEngineError("M2_SNS_MATCH_QUALITY_PROFILE_INCOMPLETE", repr(missing))
    rows: list[dict[str, object]] = []
    for row in radar_world.measurement_alignment.rows:
        association = associations.get(row.measurement_id)
        if association is None:
            raise CatalogMetricEngineError(
                "M2_SNS_ASSOCIATION_CONTRACT_MISSING", row.measurement_id
            )
        rows.append(
            {
                "measurement_id": row.measurement_id,
                "reference_state_id": row.reference_state_id,
                "association_id": _text(association, "association_id", field=row.measurement_id),
                "association_provenance": _text(
                    association, "association_provenance", field=row.measurement_id
                ),
                "association_valid": association.get("association_valid"),
                "reference_quality_status": _text(
                    association, "reference_quality_status", field=row.measurement_id
                ),
                "measurement_time_us": row.measurement_time_us,
                "reference_time_us": row.reference_time_us,
                "match_status": row.match_status,
                "measured_range_m": row.measured_range_m,
                "reference_range_m": row.reference_range_m,
                "measured_az_rad": row.measured_az_rad,
                "reference_az_rad": row.reference_az_rad,
                "measured_el_rad": row.measured_el_rad,
                "reference_el_rad": row.reference_el_rad,
                "measured_position_ecef_m": row.measured_position_ecef_m,
                "reference_target_position_ecef_m": row.reference_target_position_ecef_m,
                "measured_radial_velocity_mps": row.measured_radial_velocity_mps,
                "reference_range_rate_mps": row.reference_range_rate_mps,
                "measured_position_sensor_frame": row.measured_position_sensor_frame,
                "reference_position_sensor_frame": row.reference_position_sensor_frame,
                "measured_position_local": row.measured_position_local,
                "reference_position_local": row.reference_position_local,
                "sensor_measurement": dict(row.sensor_measurement),
                "reference_relative_state": dict(row.reference_relative_state),
                "reference_truth_uncertainty": row.reference_truth_uncertainty,
                "uncertainty_components": {
                    "reference_truth_uncertainty": row.reference_truth_uncertainty,
                    "alignment_uncertainty": row.alignment_uncertainty,
                    "sensor_measurement_uncertainty": row.sensor_measurement_uncertainty,
                },
            }
        )
    common: Mapping[str, object] = MappingProxyType(
        {
            "system_type": "RADAR",
            "mission_system_instance_id": radar_world.mission_system_instance_id,
            "world_logical_hash": radar_world.logical_hash,
            "stage_world_logical_hash": stage_world.logical_hash,
            "reference_match_quality_profile": quality_profile,
            "samples": tuple(rows),
            "association_contract_supplied": True,
            "quality_profile_contract_supplied": True,
            "association_rebuilt_by_metric": False,
            "quality_policy_defaulted_by_metric": False,
            "frame_transform_executed_by_metric": False,
        }
    )
    return {code: common for code in SNS_ACCURACY_CODES}
