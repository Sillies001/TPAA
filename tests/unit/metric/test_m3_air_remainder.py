from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

import pytest

from tpaa_metric.catalog_engine import M2MetricPluginRequest, MetricPluginRegistry
from tpaa_metric.m3_air import (
    M3_AIR_CODES,
    M3_AIR_FAMILY_COUNTS,
    M3_AIR_STRUCTURED_CODES,
    register_m3_air_plugins,
)
from tpaa_metric.m3_air_operators import (
    M3_AIR_OPERATOR_IMPLEMENTATIONS,
    bandpass_butterworth4_zp_v1,
    geodesic_pair_rate_v1,
    rolling_median_v1,
    theil_sen_gain_v1,
)
from tpaa_metric.m3_general_engine import build_m3_metric_execution_plan
from tpaa_metric.operators import TimedValue

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def _request(code: str, payload: dict[str, object]) -> tuple[M2MetricPluginRequest, object]:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    register_m3_air_plugins(plan, registry)
    definition = plan.definition(code)
    _plugin_id, plugin = registry.resolve(definition.algorithm_id, definition.algorithm_version)
    request = M2MetricPluginRequest(
        definition=definition,
        input_payload=payload,
        upstream_result_hashes=(),
        operators={
            operator_id: M3_AIR_OPERATOR_IMPLEMENTATIONS[operator_id]
            for operator_id in definition.operator_bindings
        },
    )
    return request, plugin


def test_m3_air_catalog_membership_families_and_structured_schemas_are_exact() -> None:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    definitions = tuple(
        definition for definition in plan.definitions if definition.metric_code in M3_AIR_CODES
    )

    assert len(definitions) == 36
    assert tuple(item.metric_code for item in definitions) == M3_AIR_CODES
    assert Counter(item.family for item in definitions) == Counter(M3_AIR_FAMILY_COUNTS)
    assert tuple(
        item.metric_code for item in definitions if item.value_kind == "STRUCTURED"
    ) == M3_AIR_STRUCTURED_CODES
    assert all(
        definition.subject_type == "AIRCRAFT"
        and definition.observation_lane == "AIRCRAFT_CAP_L1_OBSERVATION"
        and definition.publication_route == "CAPABILITY_OBSERVATION"
        for definition in definitions
    )

    registry = MetricPluginRegistry()
    register_m3_air_plugins(plan, registry)
    for definition in definitions:
        plugin_id, _plugin = registry.resolve(
            definition.algorithm_id,
            definition.algorithm_version,
        )
        assert plugin_id == f"m3-air-remainder:{definition.metric_code}:v1"


def test_m3_air_new_operators_follow_frozen_goldens_and_fail_closed() -> None:
    pair_rates = geodesic_pair_rate_v1(
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        (0, 1_000_000),
        max_gap_us=1_000_000,
    )
    assert len(pair_rates) == 1
    assert pair_rates[0].value == pytest.approx(math.pi / 2.0)

    assert theil_sen_gain_v1(
        (0.0, 1.0, 2.0, 3.0),
        (1.0, 3.0, 5.0, 7.0),
        min_unique_command_levels=3,
    ) == pytest.approx(2.0)
    with pytest.raises(ValueError, match="COMMAND_LEVELS_INSUFFICIENT"):
        theil_sen_gain_v1(
            (1.0, 1.0),
            (2.0, 3.0),
            min_unique_command_levels=2,
        )

    rolling = rolling_median_v1(
        tuple(
            TimedValue(index * 500_000, value)
            for index, value in enumerate((1.0, 1.0, 10.0, 1.0, 1.0, 1.0, 1.0))
        ),
        sustain_duration_s=1.5,
        min_coverage=0.75,
        max_gap_us=600_000,
    )
    assert rolling
    assert max(item[0].value for item in rolling) < 10.0

    source = tuple(
        TimedValue(
            index * 50_000,
            math.sin(2.0 * math.pi * 1.0 * index / 20.0) + 0.01 * index / 20.0,
        )
        for index in range(201)
    )
    filtered = bandpass_butterworth4_zp_v1(
        source,
        low_hz=0.5,
        high_hz=2.0,
        min_window_s=5.0,
        min_coverage=0.9,
        max_gap_us=100_000,
        resample_rate_hz=20.0,
        filter_padding_s=1.0,
    )
    assert len(filtered) >= 100
    rms = math.sqrt(sum(item * item for item in filtered) / len(filtered))
    assert 0.4 < rms < 1.2
    with pytest.raises(ValueError, match="FREQUENCY_INVALID"):
        bandpass_butterworth4_zp_v1(
            source,
            low_hz=0.5,
            high_hz=10.0,
            min_window_s=5.0,
            min_coverage=0.9,
            max_gap_us=100_000,
            resample_rate_hz=20.0,
            filter_padding_s=1.0,
        )


def test_m3_air_structured_golden_and_denominator_negative() -> None:
    request, plugin = _request(
        "P1-AIR-007",
        {
            "tas_mps": [
                {"session_time_us": 0, "value": 100.0},
                {"session_time_us": 1_000_000, "value": 200.0},
            ],
            "mach": [
                {"session_time_us": 0, "value": 0.5},
                {"session_time_us": 1_000_000, "value": 0.9},
            ],
        },
    )
    output = plugin(request)
    instance = output["instances"][0]
    assert instance["status"] == "VALID"
    assert instance["value_structured"]["tas"]["p50_mps"] == pytest.approx(150.0)
    assert instance["value_structured"]["mach"]["p50"] == pytest.approx(0.7)

    request, plugin = _request(
        "P1-AIR-019",
        {
            "P1-AIR-016.specific_mechanical_energy": [
                {"session_time_us": 0, "value": 1000.0},
                {"session_time_us": 1_000_000, "value": 1100.0},
                {"session_time_us": 2_000_000, "value": 1200.0},
            ],
            "P1-AIR-017.specific_energy_rate": [
                {"session_time_us": 1_000_000, "value": 100.0},
            ],
            "window_start_us": 0,
            "window_end_us": 2_000_000,
        },
    )
    output = plugin(request)
    instance = output["instances"][0]
    assert instance["status"] == "VALID"
    assert instance["value_structured"] == {
        "retention_ratio": pytest.approx(1.2),
        "delta_E_s_j_per_kg": pytest.approx(200.0),
        "median_energy_rate_w_per_kg": pytest.approx(100.0),
        "median_energy_rate_status": "VALID",
    }

    request, plugin = _request(
        "P1-AIR-019",
        {
            "P1-AIR-016.specific_mechanical_energy": [
                {"session_time_us": 0, "value": 1e-7},
                {"session_time_us": 1_000_000, "value": 1.0},
            ],
            "P1-AIR-017.specific_energy_rate": [],
            "window_start_us": 0,
            "window_end_us": 1_000_000,
        },
    )
    output = plugin(request)
    instance = output["instances"][0]
    assert instance["status"] == "N_A"
    assert instance["reason_codes"] == ["ENERGY_DENOMINATOR_INELIGIBLE"]
