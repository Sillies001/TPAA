"""M2 SNS detection Metric plugins over canonical upstream contracts.

The plugins consume opportunity/confirmation contracts supplied by WRE. They
never rebuild opportunity eligibility or detection-confirmation state.
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
from tpaa_metric.operators import TimedValue

if TYPE_CHECKING:
    from tpaa_world import M2RadarSensorWorld, M2StageWorldLineage

SNS_DETECTION_CODES = (
    "P1-SNS-001",
    "P1-SNS-002",
    "P1-SNS-003",
    "P1-SNS-004",
)


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"M2_SNS_INPUT_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _mappings(value: object, *, field: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"M2_SNS_INPUT_INVALID:{field}")
    return tuple(_mapping(item, field=f"{field}[{index}]") for index, item in enumerate(value))


def _text(mapping: Mapping[str, object], name: str, *, field: str) -> str:
    value = mapping.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"M2_SNS_INPUT_INVALID:{field}.{name}")
    return value


def _integer(mapping: Mapping[str, object], name: str, *, field: str) -> int:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"M2_SNS_INPUT_INVALID:{field}.{name}")
    return value


def _finite(mapping: Mapping[str, object], name: str, *, field: str) -> float:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M2_SNS_INPUT_INVALID:{field}.{name}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M2_SNS_INPUT_NONFINITE:{field}.{name}")
    return result


def _valid_opportunities(payload: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    opportunities = _mappings(payload.get("opportunities"), field="opportunities")
    mission_system_instance_id = _text(
        payload,
        "mission_system_instance_id",
        field="opportunities",
    )
    valid: list[Mapping[str, object]] = []
    seen: set[str] = set()
    for index, item in enumerate(opportunities):
        field = f"opportunities[{index}]"
        opportunity_id = _text(item, "opportunity_id", field=field)
        if opportunity_id in seen:
            raise ValueError(f"M2_SNS_OPPORTUNITY_DUPLICATE:{opportunity_id}")
        seen.add(opportunity_id)
        status = _text(item, "validity_status", field=field)
        if status not in {"VALID", "INVALID"}:
            raise ValueError(f"M2_SNS_OPPORTUNITY_STATUS_INVALID:{opportunity_id}")
        if status == "INVALID":
            continue
        if _text(item, "evaluated_system_instance_id", field=field) != mission_system_instance_id:
            raise ValueError(f"M2_SNS_OPPORTUNITY_SYSTEM_MISMATCH:{opportunity_id}")
        start = _integer(item, "start_session_time_us", field=field)
        end = _integer(item, "end_session_time_us", field=field)
        if end <= start:
            raise ValueError(f"M2_SNS_OPPORTUNITY_INTERVAL_INVALID:{opportunity_id}")
        _text(item, "reference_entity_id", field=field)
        _text(item, "opportunity_profile_id", field=field)
        _text(item, "opportunity_profile_version", field=field)
        _text(item, "eligibility_reason", field=field)
        _text(item, "eligibility_provenance", field=field)
        profile_hash = _text(item, "opportunity_profile_hash", field=field)
        if len(profile_hash) != 64:
            raise ValueError(f"M2_SNS_PROFILE_HASH_INVALID:{opportunity_id}")
        valid.append(item)
    return tuple(valid)


def _confirmations(payload: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    confirmations = _mappings(payload.get("confirmations"), field="confirmations")
    seen: set[str] = set()
    for index, item in enumerate(confirmations):
        field = f"confirmations[{index}]"
        event_id = _text(item, "confirmation_event_id", field=field)
        if event_id in seen:
            raise ValueError(f"M2_SNS_CONFIRMATION_DUPLICATE:{event_id}")
        seen.add(event_id)
        _text(item, "opportunity_id", field=field)
        _text(item, "reference_entity_id", field=field)
        _integer(item, "first_confirmed_detection_time_us", field=field)
        _text(item, "confirmation_profile_id", field=field)
        _text(item, "confirmation_profile_version", field=field)
        persistence = _finite(item, "confirmation_persistence_s", field=field)
        if persistence <= 0.0:
            raise ValueError(f"M2_SNS_CONFIRMATION_PERSISTENCE_INVALID:{event_id}")
        _text(item, "association_provenance", field=field)
        profile_hash = _text(item, "confirmation_profile_hash", field=field)
        if len(profile_hash) != 64:
            raise ValueError(f"M2_SNS_PROFILE_HASH_INVALID:{event_id}")
    return confirmations


def _confirmation_by_opportunity(
    opportunities: Sequence[Mapping[str, object]],
    confirmations: Sequence[Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    opportunity_by_id = {
        _text(item, "opportunity_id", field="opportunity"): item for item in opportunities
    }
    result: dict[str, Mapping[str, object]] = {}
    for event in confirmations:
        event_id = _text(event, "confirmation_event_id", field="confirmation")
        opportunity_id = _text(event, "opportunity_id", field=event_id)
        opportunity = opportunity_by_id.get(opportunity_id)
        if opportunity is None:
            raise ValueError(f"M2_SNS_CONFIRMATION_OPPORTUNITY_UNRESOLVED:{event_id}")
        reference = _text(event, "reference_entity_id", field=event_id)
        if reference != _text(opportunity, "reference_entity_id", field=opportunity_id):
            raise ValueError(f"M2_SNS_CONFIRMATION_ASSOCIATION_MISMATCH:{event_id}")
        timestamp = _integer(event, "first_confirmed_detection_time_us", field=event_id)
        start = _integer(opportunity, "start_session_time_us", field=opportunity_id)
        end = _integer(opportunity, "end_session_time_us", field=opportunity_id)
        if not start <= timestamp < end:
            raise ValueError(f"M2_SNS_CONFIRMATION_OUTSIDE_OPPORTUNITY:{event_id}")
        previous = result.get(opportunity_id)
        if previous is None or timestamp < _integer(
            previous,
            "first_confirmed_detection_time_us",
            field=opportunity_id,
        ):
            result[opportunity_id] = event
    return result


def _guard(request: M2MetricPluginRequest, metric_code: str) -> bool:
    definition = request.definition
    if (
        definition.metric_code != metric_code
        or definition.family != "SENSOR_DETECTION"
        or definition.subject_type != "MISSION_SYSTEM_INSTANCE"
        or definition.value_kind != "NUMERIC"
        or definition.structured_output_schema_id is not None
        or definition.publication_route != "SYSTEM_PERFORMANCE_OBSERVATION"
        or definition.observation_lane != "SYSTEM_PERFORMANCE_OBSERVATION"
        or definition.applicability.applicability_mode != "SYSTEM_TYPE_EXACT"
        or definition.applicability.allowed_system_types != ("RADAR",)
    ):
        raise ValueError(f"M2_SNS_CATALOG_DEFINITION_DRIFT:{metric_code}")
    system_type = _text(request.input_payload, "system_type", field=metric_code)
    return system_type in definition.applicability.allowed_system_types


def _not_applicable(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return {
        "metric_code": request.definition.metric_code,
        "applicable": False,
        "reason_codes": ["SYSTEM_TYPE_NOT_APPLICABLE"],
        "instances": [],
    }


def _instance(
    value: float | None,
    *,
    status: str = "VALID",
    reason_codes: Sequence[str] = (),
    evidence: Mapping[str, object],
) -> dict[str, object]:
    if status == "VALID" and (value is None or not math.isfinite(value)):
        raise ValueError("M2_SNS_VALID_VALUE_MISSING")
    return {
        "status": status,
        "reason_codes": list(reason_codes),
        "value_kind": "NUMERIC",
        "value_numeric": value,
        "value_structured": None,
        "evidence": dict(evidence),
    }


def _sns001(request: M2MetricPluginRequest) -> Mapping[str, object]:
    if not _guard(request, "P1-SNS-001"):
        return _not_applicable(request)
    opportunities = _valid_opportunities(request.input_payload)
    presence = _mappings(
        request.input_payload.get("target_presence_intervals"),
        field="target_presence_intervals",
    )
    mission_system_instance_id = _text(
        request.input_payload,
        "mission_system_instance_id",
        field="P1-SNS-001",
    )
    denominator = 0
    for index, interval in enumerate(presence):
        field = f"target_presence_intervals[{index}]"
        if (
            _text(interval, "evaluated_system_instance_id", field=field)
            != mission_system_instance_id
        ):
            raise ValueError(f"M2_SNS_TARGET_PRESENCE_SYSTEM_MISMATCH:{index}")
        _text(interval, "reference_entity_id", field=field)
        _text(interval, "presence_provenance", field=field)
        start = _integer(interval, "start_session_time_us", field=field)
        end = _integer(interval, "end_session_time_us", field=field)
        if end <= start:
            raise ValueError(f"M2_SNS_TARGET_PRESENCE_INTERVAL_INVALID:{index}")
        denominator += end - start
    for opportunity in opportunities:
        opportunity_id = _text(opportunity, "opportunity_id", field="opportunity")
        reference_id = _text(opportunity, "reference_entity_id", field=opportunity_id)
        start = _integer(opportunity, "start_session_time_us", field=opportunity_id)
        end = _integer(opportunity, "end_session_time_us", field=opportunity_id)
        if not any(
            _text(interval, "reference_entity_id", field="target_presence") == reference_id
            and _integer(interval, "start_session_time_us", field="target_presence") <= start
            and end <= _integer(interval, "end_session_time_us", field="target_presence")
            for interval in presence
        ):
            raise ValueError(f"M2_SNS_OPPORTUNITY_TARGET_PRESENCE_UNRESOLVED:{opportunity_id}")
    if denominator == 0:
        instance = _instance(
            None,
            status="N_A",
            reason_codes=("NO_AUTHORITATIVE_TARGET_PRESENCE",),
            evidence={"opportunity_ids": []},
        )
    else:
        numerator = sum(
            _integer(item, "end_session_time_us", field="opportunity")
            - _integer(item, "start_session_time_us", field="opportunity")
            for item in opportunities
        )
        if numerator > denominator:
            raise ValueError("M2_SNS_OPPORTUNITY_COVERAGE_EXCEEDS_PRESENCE")
        instance = _instance(
            numerator / denominator,
            evidence={
                "opportunity_ids": [item["opportunity_id"] for item in opportunities],
                "opportunity_duration_us": numerator,
                "target_presence_duration_us": denominator,
                "opportunity_profile_hashes": sorted(
                    {str(item["opportunity_profile_hash"]) for item in opportunities}
                ),
            },
        )
    return {
        "metric_code": request.definition.metric_code,
        "applicable": True,
        "instances": [instance],
    }


def _sns002(request: M2MetricPluginRequest) -> Mapping[str, object]:
    if not _guard(request, "P1-SNS-002"):
        return _not_applicable(request)
    opportunities = _valid_opportunities(request.input_payload)
    confirmations = _confirmations(request.input_payload)
    matched = _confirmation_by_opportunity(opportunities, confirmations)
    if not opportunities:
        instance = _instance(
            None,
            status="N_A",
            reason_codes=("NO_VALID_DETECTION_OPPORTUNITIES",),
            evidence={"opportunity_ids": [], "confirmation_event_ids": []},
        )
    else:
        instance = _instance(
            len(matched) / len(opportunities),
            evidence={
                "opportunity_ids": [item["opportunity_id"] for item in opportunities],
                "confirmation_event_ids": sorted(
                    str(item["confirmation_event_id"]) for item in matched.values()
                ),
                "invalid_opportunity_count": len(
                    _mappings(request.input_payload.get("opportunities"), field="opportunities")
                )
                - len(opportunities),
            },
        )
    return {
        "metric_code": request.definition.metric_code,
        "applicable": True,
        "instances": [instance],
    }


def _sns003(request: M2MetricPluginRequest) -> Mapping[str, object]:
    if not _guard(request, "P1-SNS-003"):
        return _not_applicable(request)
    opportunities = _valid_opportunities(request.input_payload)
    matched = _confirmation_by_opportunity(
        opportunities,
        _confirmations(request.input_payload),
    )
    instances: list[dict[str, object]] = []
    for opportunity in opportunities:
        opportunity_id = str(opportunity["opportunity_id"])
        event = matched.get(opportunity_id)
        evidence = {
            "opportunity_id": opportunity_id,
            "reference_entity_id": opportunity["reference_entity_id"],
        }
        if event is None:
            instances.append(
                _instance(
                    None,
                    status="N_A",
                    reason_codes=("NO_CONFIRMED_DETECTION",),
                    evidence=evidence,
                )
            )
            continue
        start = _integer(opportunity, "start_session_time_us", field=opportunity_id)
        detection = _integer(event, "first_confirmed_detection_time_us", field=opportunity_id)
        evidence["confirmation_event_id"] = event["confirmation_event_id"]
        evidence["confirmation_profile_hash"] = event["confirmation_profile_hash"]
        instances.append(_instance((detection - start) / 1_000_000.0, evidence=evidence))
    return {
        "metric_code": request.definition.metric_code,
        "applicable": True,
        "instances": instances,
    }


def _sns004(request: M2MetricPluginRequest) -> Mapping[str, object]:
    if not _guard(request, "P1-SNS-004"):
        return _not_applicable(request)
    opportunities = _valid_opportunities(request.input_payload)
    matched = _confirmation_by_opportunity(
        opportunities,
        _confirmations(request.input_payload),
    )
    samples = _mappings(
        request.input_payload.get("reference_range_samples"), field="reference_range_samples"
    )
    max_gap_us = _integer(request.input_payload, "interpolation_max_gap_us", field="P1-SNS-004")
    interpolate = request.operators["LINEAR_INTERPOLATION_V1"]
    instances: list[dict[str, object]] = []
    for opportunity in opportunities:
        opportunity_id = str(opportunity["opportunity_id"])
        event = matched.get(opportunity_id)
        if event is None:
            continue
        reference_id = str(opportunity["reference_entity_id"])
        timed_values = tuple(
            TimedValue(
                _integer(sample, "session_time_us", field="reference_range_sample"),
                _finite(sample, "reference_range_m", field="reference_range_sample"),
            )
            for sample in samples
            if _text(sample, "reference_entity_id", field="reference_range_sample") == reference_id
        )
        timestamp = _integer(event, "first_confirmed_detection_time_us", field=opportunity_id)
        evidence = {
            "opportunity_id": opportunity_id,
            "confirmation_event_id": event["confirmation_event_id"],
            "reference_entity_id": reference_id,
            "reference_state_ids": [
                sample["reference_state_id"]
                for sample in samples
                if sample["reference_entity_id"] == reference_id
            ],
        }
        try:
            raw = interpolate(timed_values, timestamp, max_gap_us=max_gap_us)
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise ValueError("M2_SNS_INTERPOLATION_OUTPUT_INVALID")
            value = float(raw)
            instances.append(_instance(value, evidence=evidence))
        except ValueError:
            instances.append(
                _instance(
                    None,
                    status="N_A",
                    reason_codes=("REFERENCE_RANGE_MATCH_UNAVAILABLE",),
                    evidence=evidence,
                )
            )
    return {
        "metric_code": request.definition.metric_code,
        "applicable": True,
        "instances": instances,
    }


M2_SNS_DETECTION_PLUGINS: Mapping[str, M2MetricPlugin] = MappingProxyType(
    {
        "P1-SNS-001": _sns001,
        "P1-SNS-002": _sns002,
        "P1-SNS-003": _sns003,
        "P1-SNS-004": _sns004,
    }
)


def register_m2_sns_detection_plugins(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
) -> None:
    """Register the four detection algorithms in the shared registry."""

    for metric_code in SNS_DETECTION_CODES:
        definition = plan.definition(metric_code)
        registry.register(
            definition.algorithm_id,
            plugin_id=f"m2-sns-detection:{metric_code}:v1",
            plugin=M2_SNS_DETECTION_PLUGINS[metric_code],
        )


def build_m2_sns_detection_inputs(
    radar_world: M2RadarSensorWorld,
    stage_world: M2StageWorldLineage,
    *,
    opportunities: Sequence[Mapping[str, object]],
    confirmations: Sequence[Mapping[str, object]],
    target_presence_intervals: Sequence[Mapping[str, object]],
    reference_range_samples: Sequence[Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    """Bind supplied canonical contracts to exact World identity and lineage."""

    if radar_world.mission_system.instance.system_type != "RADAR":
        raise CatalogMetricEngineError(
            "M2_SNS_SYSTEM_NOT_APPLICABLE", radar_world.mission_system_instance_id
        )
    if (
        stage_world.radar_sensor_world.logical_hash != radar_world.logical_hash
        or stage_world.status != "READY"
    ):
        raise CatalogMetricEngineError("M2_SNS_STAGE_WORLD_MISMATCH", stage_world.logical_hash)
    common: Mapping[str, object] = MappingProxyType(
        {
            "system_type": "RADAR",
            "mission_system_instance_id": radar_world.mission_system_instance_id,
            "world_logical_hash": radar_world.logical_hash,
            "stage_world_logical_hash": stage_world.logical_hash,
            "opportunities": tuple(opportunities),
            "confirmations": tuple(confirmations),
            "target_presence_intervals": tuple(target_presence_intervals),
            "reference_range_samples": tuple(reference_range_samples),
            "interpolation_max_gap_us": radar_world.measurement_alignment.quality_profile.max_gap_us,
            "upstream_contracts_supplied": True,
            "opportunity_rebuilt_by_metric": False,
            "confirmation_rebuilt_by_metric": False,
        }
    )
    return {code: common for code in SNS_DETECTION_CODES}
