#!/usr/bin/env python3
"""M3-MET-002 exact P1 AIR remainder qualification evidence."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "m1"
TRACKING_ISSUE = 114
RELEASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3"


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    value = completed.stdout.strip()
    return value if len(value) == 40 else "UNKNOWN"


def _load(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{path}: root must be string-keyed object")
    return cast(dict[str, object], raw)


def _series(function, *, count: int = 21, step_us: int = 500_000) -> list[dict[str, object]]:
    return [
        {
            "session_time_us": index * step_us,
            "value": float(function(index * step_us / 1_000_000.0)),
        }
        for index in range(count)
    ]


def _control_event(
    event_id: str,
    *,
    start_us: int,
    command_scale: float = 1.0,
) -> dict[str, object]:
    command = [
        {"session_time_us": start_us + index * 500_000, "value": command_scale * value}
        for index, value in enumerate((0.2, 0.4, 0.6, 0.8))
    ]
    response = [
        {"session_time_us": row["session_time_us"], "value": 2.0 * float(row["value"])}
        for row in command
    ]
    return {
        "event_id": event_id,
        "start_session_time_us": start_us,
        "mode": "NORMAL",
        "control_axis": "ROLL",
        "response_channel": "body_p_rad_s",
        "response_unit": "rad/s",
        "gain_unit": "rad/s/normalized",
        "command": command,
        "response": response,
    }


def _identity_fields() -> dict[str, object]:
    return {
        "control_calibration_id": "CAL-A",
        "control_calibration_version": "1.0.0",
        "control_calibration_hash": "a" * 64,
        "control_response_map_id": "MAP-A",
        "control_response_map_version": "1.0.0",
        "control_response_map_hash": "b" * 64,
    }


def _golden_inputs() -> dict[str, dict[str, object]]:
    derivative_profile = {"derivative_window_s": 2.0, "max_gap_us": 600_000}
    sustain_profile = {
        "sustain_duration_s": 2.0,
        "min_coverage": 0.8,
        "max_gap_us": 600_000,
    }
    energy = _series(lambda t: 1000.0 + 100.0 * t)
    rate = _series(lambda _t: 100.0)
    fuel = _series(lambda t: 100.0 - t)
    burn = _series(lambda _t: 1.0)
    command_response = {
        **_identity_fields(),
        "command_response_events": [
            {
                "event_id": "evt-delay",
                "start_session_time_us": 0,
                "mode": "NORMAL",
                "command": _series(lambda t: 0.0 if t < 1.0 else 0.5),
                "response": _series(lambda t: 0.0 if t < 1.5 else 1.0),
            }
        ],
        "profile": {
            "command_deadband": 0.2,
            "command_persistence_s": 0.5,
            "response_threshold": 0.5,
            "response_persistence_s": 0.5,
            "max_search_s": 4.0,
            "max_gap_us": 600_000,
        },
    }
    reversal_values = []
    for index in range(21):
        time = index * 500_000
        seconds = time / 1_000_000.0
        value = 1.0 if seconds <= 3.0 or seconds >= 7.0 else -1.0
        reversal_values.append({"session_time_us": time, "value": value})
    high_aoa = _series(lambda t: 0.3 if 2.0 <= t <= 6.0 else 0.1)
    quat_rows = []
    for index in range(21):
        seconds = index * 0.5
        theta = 0.1 * seconds
        quat_rows.append(
            {
                "session_time_us": index * 500_000,
                "w": math.cos(theta / 2.0),
                "x": 0.0,
                "y": 0.0,
                "z": math.sin(theta / 2.0),
            }
        )
    attitude_roll = _series(
        lambda t: math.sin(2.0 * math.pi * t),
        count=201,
        step_us=50_000,
    )
    attitude_pitch = _series(
        lambda t: 0.5 * math.sin(2.0 * math.pi * 1.2 * t),
        count=201,
        step_us=50_000,
    )
    accel_rows = [
        {
            "session_time_us": index * 500_000,
            "x": (index * 0.5) ** 2,
            "y": 2.0 * (index * 0.5) ** 2,
            "z": 0.5 * (index * 0.5) ** 2,
        }
        for index in range(21)
    ]
    deadband_events = [
        {
            "event_id": f"evt-deadband-{number}",
            "start_session_time_us": number * 6_000_000,
            "mode": "NORMAL",
            "command": [
                {
                    "session_time_us": number * 6_000_000 + index * 500_000,
                    "value": 0.25,
                }
                for index in range(5)
            ],
            "response": [
                {
                    "session_time_us": number * 6_000_000 + index * 500_000,
                    "value": 0.6,
                }
                for index in range(5)
            ],
        }
        for number in range(2)
    ]
    persistence_events = []
    for number in range(2):
        base = number * 6_000_000
        persistence_events.append(
            {
                "event_id": f"evt-persistence-{number}",
                "start_session_time_us": base,
                "response_onset_time_us": base + 1_000_000,
                "response_sign": 1.0,
                "response": [
                    {
                        "session_time_us": base + index * 500_000,
                        "value": 0.8 if 1.0 <= index * 0.5 <= 3.0 else 0.0,
                    }
                    for index in range(9)
                ],
            }
        )

    return {
        "P1-AIR-004": {
            "P1-AIR-003.heading_rate_rad_s": _series(
                lambda t: 2.0 if t == 5.0 else 0.2
            ),
            "profile": dict(sustain_profile),
        },
        "P1-AIR-005": {
            "ground_speed_mps": _series(lambda _t: 100.0),
            "track_true_rad": _series(lambda t: 0.1 * t),
            "profile": {
                **derivative_profile,
                "min_turn_rate_rad_s": 0.05,
            },
        },
        "P1-AIR-006": {
            "nz_g": _series(lambda _t: 2.5),
            "profile": dict(sustain_profile),
        },
        "P1-AIR-007": {
            "tas_mps": _series(lambda t: 100.0 + 5.0 * t),
            "mach": _series(lambda t: 0.5 + 0.01 * t),
        },
        "P1-AIR-008": {
            "tas_mps": _series(lambda t: 100.0 + 5.0 * t),
            "profile": dict(derivative_profile),
        },
        "P1-AIR-009": {
            "tas_mps": _series(lambda t: 100.0 + 5.0 * t),
            "profile": {
                **derivative_profile,
                "sustain_duration_s": 2.0,
                "min_coverage": 0.8,
            },
        },
        "P1-AIR-010": {
            "tas_mps": _series(lambda t: 100.0 + 5.0 * t),
            "mach": _series(lambda t: 0.5 + 0.01 * t),
            "profile": {
                "lower_speed_bound_mps": 110.0,
                "upper_speed_bound_mps": 140.0,
                "max_gap_us": 600_000,
            },
        },
        "P1-AIR-011": {
            "tas_mps": _series(lambda t: 200.0 - 5.0 * t),
            "profile": dict(derivative_profile),
        },
        "P1-AIR-012": {
            "tas_mps": _series(lambda t: 200.0 - 5.0 * t),
            "mach": _series(lambda t: 0.9 - 0.01 * t),
            "profile": {
                "lower_speed_bound_mps": 160.0,
                "upper_speed_bound_mps": 190.0,
                "max_gap_us": 600_000,
            },
        },
        "P1-AIR-013": {
            "alt_msl_m": _series(lambda t: 1000.0 + 10.0 * t),
            "vertical_speed_mps": _series(lambda _t: 10.0),
            "profile": dict(derivative_profile),
        },
        "P1-AIR-014": {
            "alt_msl_m": _series(lambda t: 1000.0 + 10.0 * t),
            "profile": {
                **derivative_profile,
                "sustain_duration_s": 2.0,
                "min_coverage": 0.8,
            },
        },
        "P1-AIR-015": {
            "tas_mps": _series(lambda t: 200.0 + 3.0 * t),
            "alt_msl_m": _series(lambda t: 2000.0 - 20.0 * t),
            "profile": {
                **derivative_profile,
                "min_descent_rate_mps": 5.0,
            },
        },
        "P1-AIR-016": {
            "tas_mps": _series(lambda t: 200.0 + t),
            "alt_msl_m": _series(lambda t: 1000.0 + 5.0 * t),
        },
        "P1-AIR-017": {
            "P1-AIR-016.specific_mechanical_energy": energy,
            "profile": dict(derivative_profile),
        },
        "P1-AIR-018": {
            "tas_mps": _series(lambda _t: 200.0),
            "alt_msl_m": _series(lambda t: 1000.0 + 10.0 * t),
            "profile": dict(derivative_profile),
        },
        "P1-AIR-019": {
            "P1-AIR-016.specific_mechanical_energy": energy,
            "P1-AIR-017.specific_energy_rate": rate,
            "window_start_us": 0,
            "window_end_us": 10_000_000,
        },
        "P1-AIR-020": {
            "specific_mechanical_energy": _series(lambda t: 800.0 + 25.0 * t),
            "maneuver_end_time_us": 0,
            "pre_event_reference_energy": 1000.0,
            "post_event_min_energy": 800.0,
            "profile": {
                "recovery_fraction": 0.5,
                "max_recovery_window_s": 8.0,
                "min_crossing_persistence_s": 1.0,
                "max_gap_us": 600_000,
            },
        },
        "P1-AIR-021": {
            "specific_energy_rate": rate,
            "recovery_window": {
                "resolved": True,
                "start_session_time_us": 0,
                "end_session_time_us": 10_000_000,
            },
            "profile": {"max_gap_us": 600_000},
        },
        "P1-AIR-022": {
            "body_p_rad_s": _series(lambda _t: 0.5),
            "profile": dict(sustain_profile),
        },
        "P1-AIR-023": {
            "roll_rad": _series(lambda t: min(0.1 * t, 0.5)),
            "roll_onset_time_us": 0,
            "profile": {
                "bank_delta_rad": 0.5,
                "bank_tolerance_rad": 0.01,
                "achievement_persistence_s": 1.0,
                "max_gap_us": 600_000,
            },
        },
        "P1-AIR-024": {
            "attitude_quat": quat_rows,
            "profile": {"max_gap_us": 600_000},
        },
        "P1-AIR-025": {
            "aoa_rad": _series(lambda t: 0.05 + 0.01 * t),
        },
        "P1-AIR-026": {
            "aoa_rad": high_aoa,
            "profile": {
                "aoa_threshold_rad": 0.2,
                "min_dwell_s": 2.0,
                "max_gap_us": 600_000,
            },
        },
        "P1-AIR-027": command_response,
        "P1-AIR-028": {
            **{key: value for key, value in _identity_fields().items() if key.startswith("control_calibration")},
            "control_input": _series(lambda t: 0.2 * t),
            "profile": {
                **derivative_profile,
                "control_deadband": 0.1,
            },
        },
        "P1-AIR-029": {
            **{key: value for key, value in _identity_fields().items() if key.startswith("control_calibration")},
            "control_input": reversal_values,
            "profile": {
                "control_deadband": 0.1,
                "reversal_persistence_s": 1.0,
                "max_gap_us": 600_000,
            },
        },
        "P1-AIR-030": {
            "roll_rad": attitude_roll,
            "pitch_rad": attitude_pitch,
            "profile": {
                "low_hz": 0.5,
                "high_hz": 2.0,
                "min_window_s": 5.0,
                "min_coverage": 0.9,
                "max_gap_us": 100_000,
                "resample_rate_hz": 20.0,
                "filter_padding_s": 1.0,
            },
        },
        "P1-AIR-031": {
            "accel_body_mps2_xyz": accel_rows,
            "profile": dict(derivative_profile),
        },
        "P1-AIR-032": {
            "fuel_flow_kg_s": _series(lambda t: 2.0 + 0.01 * t),
        },
        "P1-AIR-033": {
            "fuel_remaining_kg": fuel,
            "fuel_event_markers": [],
            "profile": {
                **derivative_profile,
                "refuel_jump_threshold_kg": 10.0,
                "event_guard_s": 1.0,
            },
        },
        "P1-AIR-034": {
            "fuel_remaining_kg": fuel,
            "P1-AIR-033.fuel_burn_rate_kg_s": burn,
            "profile": {
                "burn_rate_window_s": 2.0,
                "min_coverage": 0.8,
                "max_gap_us": 600_000,
            },
        },
        "P1-AIR-035": {
            **_identity_fields(),
            "command_response_events": [_control_event("evt-gain", start_us=0)],
            "profile": {
                "event_window_s": 2.0,
                "min_unique_command_levels": 3,
                "command_deadband": 0.1,
                "max_gap_us": 600_000,
            },
        },
        "P1-AIR-036": {
            **_identity_fields(),
            "command_response_events": deadband_events,
            "profile": {
                "response_threshold": 0.2,
                "command_persistence_s": 1.0,
                "min_event_count": 2,
                "max_gap_us": 600_000,
            },
        },
        "P1-AIR-037": {
            **{key: value for key, value in _identity_fields().items() if key.startswith("control_response_map")},
            "command_response_events": persistence_events,
            "profile": {
                "response_threshold": 0.5,
                "max_gap_us": 600_000,
                "reversal_threshold": 0.5,
                "min_event_count": 2,
            },
        },
        "P1-AIR-038": {
            "P1-AIR-017.specific_energy_rate": rate,
            "alt_msl_m": _series(lambda t: 1000.0 + 10.0 * t),
            "profile": dict(derivative_profile),
        },
        "P1-AIR-039": {
            "P1-AIR-016.specific_mechanical_energy": energy,
            "P1-AIR-017.specific_energy_rate": rate,
            "P1-AIR-015.dive_eligible_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 2_000_000},
                {"start_session_time_us": 4_000_000, "end_session_time_us": 6_000_000},
            ],
        },
    }


def _direct_outputs(plan, registry, inputs):
    from tpaa_metric.catalog_engine import M2MetricPluginRequest, validate_m2_runtime_output
    from tpaa_metric.m3_air import M3_AIR_CODES
    from tpaa_metric.m3_air_operators import M3_AIR_OPERATOR_IMPLEMENTATIONS

    outputs: dict[str, dict[str, object]] = {}
    for code in M3_AIR_CODES:
        definition = plan.definition(code)
        _plugin_id, plugin = registry.resolve(definition.algorithm_id, definition.algorithm_version)
        request = M2MetricPluginRequest(
            definition=definition,
            input_payload=inputs[code],
            upstream_result_hashes=(),
            operators={
                operator_id: M3_AIR_OPERATOR_IMPLEMENTATIONS[operator_id]
                for operator_id in definition.operator_bindings
            },
        )
        output = dict(plugin(request))
        validate_m2_runtime_output(definition, inputs[code], output)
        outputs[code] = output
    return outputs


def _instance(output: dict[str, object]) -> dict[str, object]:
    raw = output.get("instances")
    if not isinstance(raw, list) or len(raw) != 1 or not isinstance(raw[0], dict):
        raise ValueError("expected one metric instance")
    return cast(dict[str, object], raw[0])


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_metric import (
        CatalogMetricEngine,
        MetricPluginRegistry,
        build_m2_air_formal_delivery,
        build_metric_context,
        register_m2_air_plugins,
    )
    from tpaa_metric.m3_air import (
        M3_AIR_CODES,
        M3_AIR_FAMILY_COUNTS,
        M3_AIR_STRUCTURED_CODES,
        register_m3_air_plugins,
    )
    from tpaa_metric.m3_air_operators import M3_AIR_OPERATOR_IMPLEMENTATIONS
    from tpaa_metric.m3_general_engine import (
        M3_DEFERRED_OPERATOR_IDS,
        build_m3_metric_execution_plan,
    )
    from tpaa_world import project_minimal_p1_world

    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    air_definitions = tuple(
        item for item in plan.definitions if item.metric_code in M3_AIR_CODES
    )
    inputs = _golden_inputs()

    bundle = FIXTURES / "BF_M1_NOMINAL_V1"
    world = project_minimal_p1_world(
        bundle,
        authority_root=AUTHORITY_ROOT,
        release_id=RELEASE_ID,
    )
    context = build_metric_context(bundle, authority_root=AUTHORITY_ROOT, world=world)
    foundation = build_m2_air_formal_delivery(context, world)

    registry = MetricPluginRegistry()
    register_m2_air_plugins(plan, registry)
    register_m3_air_plugins(plan, registry)
    engine_inputs: dict[str, dict[str, object] | Mapping[str, object]] = dict(inputs)
    engine_inputs["P1-AIR-003"] = foundation.engine_inputs["P1-AIR-003"]

    engine = CatalogMetricEngine(
        plan,
        registry,
        operator_implementations=M3_AIR_OPERATOR_IMPLEMENTATIONS,
    )
    first = engine.execute(engine_inputs, metric_codes=M3_AIR_CODES)
    replay = engine.execute(engine_inputs, metric_codes=M3_AIR_CODES)
    outputs = _direct_outputs(plan, registry, inputs)
    outputs_replay = _direct_outputs(plan, registry, inputs)

    m3_records = tuple(record for record in first.records if record.metric_code in M3_AIR_CODES)
    family_counts = dict(sorted(Counter(item.family for item in air_definitions).items()))
    structured = tuple(
        item.metric_code for item in air_definitions if item.value_kind == "STRUCTURED"
    )
    statuses = {
        code: _instance(output)["status"]
        for code, output in outputs.items()
    }
    numeric = {
        code: _instance(outputs[code]).get("value_numeric")
        for code in ("P1-AIR-005", "P1-AIR-010", "P1-AIR-015", "P1-AIR-024", "P1-AIR-038")
    }

    negative_inputs = _golden_inputs()
    negative_019 = dict(negative_inputs["P1-AIR-019"])
    negative_019["P1-AIR-016.specific_mechanical_energy"] = [
        {"session_time_us": 0, "value": 1e-7},
        {"session_time_us": 10_000_000, "value": 1000.0},
    ]
    definition_019 = plan.definition("P1-AIR-019")
    _pid, plugin_019 = registry.resolve(
        definition_019.algorithm_id,
        definition_019.algorithm_version,
    )
    from tpaa_metric.catalog_engine import M2MetricPluginRequest

    neg_request = M2MetricPluginRequest(
        definition=definition_019,
        input_payload=negative_019,
        upstream_result_hashes=(),
        operators={
            operator_id: M3_AIR_OPERATOR_IMPLEMENTATIONS[operator_id]
            for operator_id in definition_019.operator_bindings
        },
    )
    negative_019_status = _instance(dict(plugin_019(neg_request)))["status"]

    bandpass_negative = False
    from tpaa_metric.m3_air_operators import bandpass_butterworth4_zp_v1
    from tpaa_metric.operators import TimedValue

    try:
        bandpass_butterworth4_zp_v1(
            tuple(TimedValue(index * 50_000, float(index)) for index in range(201)),
            low_hz=0.5,
            high_hz=10.0,
            min_window_s=5.0,
            min_coverage=0.9,
            max_gap_us=100_000,
            resample_rate_hz=20.0,
            filter_padding_s=1.0,
        )
    except ValueError as exc:
        bandpass_negative = "FREQUENCY_INVALID" in str(exc)

    deferred_remaining = tuple(
        operator_id
        for operator_id in M3_DEFERRED_OPERATOR_IDS
        if operator_id in {"CV_PROPAGATION_V1", "MAD_V1"}
    )
    air_operator_ids = sorted(
        {
            operator_id
            for definition in air_definitions
            for operator_id in definition.operator_bindings
        }
    )
    acceptance = {
        "air_remainder_exact_36": (
            len(air_definitions) == 36
            and tuple(item.metric_code for item in air_definitions) == M3_AIR_CODES
        ),
        "air_family_counts_exact": family_counts == dict(sorted(M3_AIR_FAMILY_COUNTS.items())),
        "six_structured_schemas_exact": structured == M3_AIR_STRUCTURED_CODES,
        "all_air_operator_bindings_implemented": set(air_operator_ids)
        <= set(M3_AIR_OPERATOR_IMPLEMENTATIONS),
        "later_family_operators_still_deferred": set(deferred_remaining)
        == {"CV_PROPAGATION_V1", "MAD_V1"},
        "single_catalog_engine_dispatch": (
            first.dispatch_key == "algorithm_id+algorithm_version"
            and {record.plugin_id for record in m3_records}
            == {f"m3-air-remainder:{code}:v1" for code in M3_AIR_CODES}
        ),
        "foundation_dependency_integrated": "P1-AIR-003" in first.metric_codes,
        "m3_execution_exact_36": (
            len(m3_records) == 36
            and {record.metric_code for record in m3_records} == set(M3_AIR_CODES)
        ),
        "runtime_contract_all_valid": set(statuses.values()) == {"VALID"},
        "structured_runtime_exact_six": all(
            _instance(outputs[code]).get("value_structured") is not None
            for code in M3_AIR_STRUCTURED_CODES
        ),
        "execution_replay_exact": first == replay,
        "plugin_replay_exact": outputs == outputs_replay,
        "golden_turn_radius": abs(float(cast(float, numeric["P1-AIR-005"])) - 1000.0) < 1e-8,
        "golden_acceleration_band_six_seconds": abs(
            float(cast(float, numeric["P1-AIR-010"])) - 6.0
        )
        < 1e-8,
        "golden_dive_acceleration_three": abs(
            float(cast(float, numeric["P1-AIR-015"])) - 3.0
        )
        < 1e-8,
        "golden_nose_pointing_rate": abs(
            float(cast(float, numeric["P1-AIR-024"])) - 0.1
        )
        < 1e-8,
        "golden_climb_energy_partition": abs(
            float(cast(float, numeric["P1-AIR-038"])) - 0.980665
        )
        < 1e-8,
        "negative_energy_denominator_fails_closed": negative_019_status == "N_A",
        "negative_bandpass_nyquist_fails_closed": bandpass_negative,
    }
    failed = sorted(key for key, passed in acceptance.items() if not bool(passed))

    logical_product = {
        "metric_codes": list(M3_AIR_CODES),
        "family_counts": family_counts,
        "structured_metric_codes": list(structured),
        "operator_ids": air_operator_ids,
        "deferred_later_operator_ids": list(deferred_remaining),
        "execution_metric_codes": list(first.metric_codes),
        "m3_record_hashes": [
            [record.metric_code, record.logical_hash] for record in m3_records
        ],
        "execution_logical_hash": first.logical_hash,
        "plugin_manifest_hash": first.plugin_manifest_hash,
        "statuses": statuses,
        "golden_numeric": numeric,
        "structured_values": {
            code: _instance(outputs[code]).get("value_structured")
            for code in M3_AIR_STRUCTURED_CODES
        },
    }
    return {
        "schema": "TPAA_M3_MET_002_AIR_REMAINDER_EVIDENCE_V1",
        "task_id": "M3-MET-002",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": _git_revision(),
        "task_complete": not failed,
        "implementation_complete": not failed,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "exact_air_remainder_36": True,
            "shared_catalog_engine": True,
            "six_structured_schemas_runtime_validated": True,
            "golden_and_negative_cases_executed": True,
            "persistence_executed": False,
            "publication_executed": False,
        },
    }


def compare_evidence(
    windows_path: Path,
    linux_path: Path,
    *,
    expected_revision: str,
) -> dict[str, object]:
    windows = _load(windows_path)
    linux = _load(linux_path)
    checks = {
        "windows_status_pass": windows.get("status") == "PASS",
        "linux_status_pass": linux.get("status") == "PASS",
        "windows_revision_exact": windows.get("source_revision") == expected_revision,
        "linux_revision_exact": linux.get("source_revision") == expected_revision,
        "windows_task_complete": windows.get("task_complete") is True,
        "linux_task_complete": linux.get("task_complete") is True,
        "logical_product_equal": windows.get("logical_product") == linux.get("logical_product"),
        "acceptance_equal": windows.get("acceptance") == linux.get("acceptance"),
        "failed_acceptance_empty": (
            windows.get("failed_acceptance") == []
            and linux.get("failed_acceptance") == []
        ),
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    return {
        "schema": "TPAA_M3_MET_002_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": "M3-MET-002",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": expected_revision,
        "windows_source_revision": windows.get("source_revision"),
        "linux_source_revision": linux.get("source_revision"),
        "logical_product": windows.get("logical_product"),
        "checks": checks,
        "failed_acceptance": failed,
    }


def _write(payload: dict[str, object], path: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    print(rendered, end="")
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    check = sub.add_parser("check")
    check.add_argument("--evidence", type=Path)
    compare = sub.add_parser("compare")
    compare.add_argument("--windows", type=Path, required=True)
    compare.add_argument("--linux", type=Path, required=True)
    compare.add_argument("--expected-revision", required=True)
    compare.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.mode == "check":
            payload = verify()
            evidence = args.evidence
        else:
            payload = compare_evidence(
                args.windows,
                args.linux,
                expected_revision=args.expected_revision,
            )
            evidence = args.evidence
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M3_MET_002_AIR_REMAINDER_EVIDENCE_V1",
            "task_id": "M3-MET-002",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "source_revision": _git_revision(),
            "task_complete": False,
            "implementation_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        evidence = getattr(args, "evidence", None)
        code = 2
    _write(payload, evidence)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
