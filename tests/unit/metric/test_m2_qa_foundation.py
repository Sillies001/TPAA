from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

import pytest

from tpaa_metric.catalog_engine import (
    CatalogMetricEngine,
    M2MetricExecutionPlan,
    M2MetricPluginRequest,
    MetricPluginRegistry,
    build_m2_metric_execution_plan,
)
from tpaa_metric.operators import M2_OPERATOR_IMPLEMENTATIONS
from tpaa_metric.qa_foundation import (
    QA_AUTHORITY_BLOCKED_CODES,
    QA_EXECUTABLE_CODES,
    QA_FOUNDATION_CODES,
    build_m2_qa_inputs,
    register_m2_qa_plugins,
)
from tpaa_world import (
    project_m2_radar_sensor_world,
    project_m2_reference_time_world,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
FIXTURES = ROOT / "tests" / "fixtures" / "m2"
C3_AUTHORITY = AUTHORITY / "M2_QA_SNS_AUTHORITY.json"


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _runtime() -> tuple[
    M2MetricExecutionPlan,
    MetricPluginRegistry,
    dict[str, Mapping[str, object]],
    CatalogMetricEngine,
]:
    reference_time = project_m2_reference_time_world(
        FIXTURES / "RT_M2_NOMINAL_V1",
        FIXTURES / "TA_M2_NOMINAL_V1",
        authority_root=AUTHORITY,
        release_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1",
    )
    radar = project_m2_radar_sensor_world(
        FIXTURES / "MSI_M2_RADAR_V1",
        FIXTURES / "MA_M2_NOMINAL_V1",
        authority_root=AUTHORITY,
        release_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2",
    )
    plan = build_m2_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    register_m2_qa_plugins(plan, registry)
    inputs = build_m2_qa_inputs(reference_time, radar)
    return plan, registry, inputs, CatalogMetricEngine(plan, registry)


def _direct(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
    payload: Mapping[str, object],
    metric_code: str,
) -> dict[str, object]:
    definition = plan.definition(metric_code)
    _plugin_id, plugin = registry.resolve(
        definition.algorithm_id,
        definition.algorithm_version,
    )
    operators = MappingProxyType(
        {
            operator_id: M2_OPERATOR_IMPLEMENTATIONS[operator_id]
            for operator_id in definition.operator_bindings
        }
    )
    return dict(
        plugin(
            M2MetricPluginRequest(
                definition=definition,
                input_payload=payload,
                upstream_result_hashes=(),
                operators=operators,
            )
        )
    )


def _instance(output: Mapping[str, object], index: int = 0) -> dict[str, object]:
    instances = output["instances"]
    assert isinstance(instances, list)
    item = instances[index]
    assert isinstance(item, dict)
    assert all(isinstance(key, str) for key in item)
    return item


def _structured(output: Mapping[str, object], index: int = 0) -> dict[str, object]:
    value = _instance(output, index)["value_structured"]
    assert isinstance(value, dict)
    assert all(isinstance(key, str) for key in value)
    return value


def _c3() -> dict[str, object]:
    value = json.loads(C3_AUTHORITY.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _qa001_golden_payload(case: Mapping[str, object]) -> dict[str, object]:
    inp = case["input"]
    assert isinstance(inp, dict)
    return {
        "samples": [
            {
                "own": {
                    "position_ecef_m": inp["own_position_ecef_m"],
                    "velocity_ecef_mps": inp["own_velocity_ecef_mps"],
                    "attitude_quat": inp["own_attitude_quat"],
                },
                "target": {
                    "position_ecef_m": inp["target_position_ecef_m"],
                    "velocity_ecef_mps": inp["target_velocity_ecef_mps"],
                },
                "sensor_boresight_quat": inp["sensor_boresight_quat"],
                "session_time_us": 0,
            }
        ]
    }


def _qa002_golden_payload(case: Mapping[str, object]) -> dict[str, object]:
    inp = case["input"]
    assert isinstance(inp, dict)
    return {
        "samples": [
            {
                "target_position_uncertainty_ref": {
                    "representation": "COVARIANCE",
                    "unit": "m^2",
                    "frame_ref": "ECEF",
                    "value": inp["target_position_covariance_ecef_m2"],
                },
                "own_position_uncertainty_ref": {
                    "representation": "COVARIANCE",
                    "unit": "m^2",
                    "frame_ref": "ECEF",
                    "value": inp["own_position_covariance_ecef_m2"],
                },
                "own_attitude_uncertainty_ref": {
                    "representation": "SIGMA_1D",
                    "unit": "rad",
                    "frame_ref": "OWN_BODY_FRD",
                    "value": inp["own_attitude_sigma_rad"],
                },
                "target_attitude_uncertainty_ref": {
                    "representation": "SIGMA_1D",
                    "unit": "rad",
                    "frame_ref": "TARGET_BODY_FRD",
                    "value": inp["target_attitude_sigma_rad"],
                },
                "time_alignment_uncertainty_ref": {
                    "representation": "TWO_SIDED_HARD_BOUND",
                    "unit": "us",
                    "frame_ref": "SESSION_TIME",
                    "value": inp["time_alignment_two_sided_hard_bound_us"],
                },
                "relative_state_jacobian": inp["relative_state_jacobian"],
                "qa_001_basis": {
                    "target_velocity_ecef_mps": inp["target_velocity_ecef_mps"],
                    "own_velocity_ecef_mps": inp["own_velocity_ecef_mps"],
                    "own_attitude_quat": inp["own_attitude_quat"],
                    "r_rel_ecef_m": inp["r_rel_ecef_m"],
                },
            }
        ]
    }


def test_m2_qa_registry_is_catalog_driven_and_all_eight_replay() -> None:
    plan, registry, inputs, engine = _runtime()
    qa_codes = tuple(code for code in plan.metric_codes if code.startswith("P1-QA-"))
    assert len(qa_codes) == 8
    assert set(qa_codes) == set(QA_FOUNDATION_CODES)
    assert QA_AUTHORITY_BLOCKED_CODES == ()
    assert QA_EXECUTABLE_CODES == QA_FOUNDATION_CODES

    expected_algorithms = {
        plan.definition(code).algorithm_id for code in QA_FOUNDATION_CODES
    }
    assert set(registry.plugin_ids) == expected_algorithms

    first = engine.execute(inputs, metric_codes=QA_FOUNDATION_CODES)
    replayed = engine.execute(inputs, metric_codes=QA_FOUNDATION_CODES)
    assert first == replayed
    assert first.metric_codes == QA_FOUNDATION_CODES

    direct = {
        code: _direct(plan, registry, inputs[code], code)
        for code in QA_FOUNDATION_CODES
    }
    for record in first.records:
        assert record.plugin_output_hash == _canonical_hash(direct[record.metric_code])


def test_m2_qa_frozen_fixture_golden_values() -> None:
    plan, registry, inputs, _engine = _runtime()
    direct = {
        code: _direct(plan, registry, inputs[code], code)
        for code in QA_FOUNDATION_CODES
    }

    qa001 = _structured(direct["P1-QA-001"])
    assert qa001["r_rel_ecef_m"] == [0.0, 1000.0, 100.0]
    assert qa001["v_rel_ecef_mps"] == [0.0, -20.0, 0.0]
    assert qa001["range_m"] == pytest.approx(1004.987562112089)
    assert qa001["range_rate_mps"] == pytest.approx(-19.900743804199784)
    assert qa001["own_body_az_rad"] == pytest.approx(math.pi / 2.0)
    assert qa001["own_body_el_rad"] == pytest.approx(-0.09966865249116202)
    assert qa001["sensor_az_rad"] is None
    assert qa001["sensor_el_rad"] is None
    assert qa001["sensor_frame_status"] == "NOT_CONFIGURED"

    qa002 = _structured(direct["P1-QA-002"])
    assert qa002["sigma_range_m"] == pytest.approx(3.6219900898844437)
    assert qa002["sigma_az_rad"] == pytest.approx(0.0037429934544425804)
    assert qa002["sigma_el_rad"] == pytest.approx(0.005063085988294449)
    assert qa002["sigma_position_3d_m"] == pytest.approx(7.141428451880851)

    assert [_instance(direct["P1-QA-003"], index)["value_numeric"] for index in range(2)] == [
        2000.0,
        2000.0,
    ]

    qa004 = _instance(direct["P1-QA-004"])
    assert qa004["value_numeric"] == 40000.0
    assert isinstance(qa004["diagnostics"], dict)
    assert qa004["diagnostics"]["p95_us"] == 49000.0

    qa005 = _instance(direct["P1-QA-005"])
    assert qa005["value_numeric"] == 50000.0
    assert isinstance(qa005["diagnostics"], dict)
    assert qa005["diagnostics"]["max_us"] == 50000.0

    expected_qa006 = 5.0 / math.sqrt(14.0)
    for index in range(3):
        structured = _structured(direct["P1-QA-006"], index)
        assert structured["normalized_residual_status"] == "VALID"
        assert structured["normalized_residual"] == pytest.approx(expected_qa006)

    assert _instance(direct["P1-QA-007"])["value_numeric"] == pytest.approx(
        math.sqrt((500.0 / math.sqrt(3.0)) ** 2 + 100.0**2)
    )
    assert _instance(direct["P1-QA-008"])["value_numeric"] == pytest.approx(
        math.sqrt((800.0 / math.sqrt(3.0)) ** 2 + 200.0**2)
    )


def test_c3_qa001_nonidentity_golden_and_zero_norm_negative() -> None:
    plan, registry, _inputs, _engine = _runtime()
    authority = _c3()
    vectors = authority["golden_vectors"]
    assert isinstance(vectors, dict)
    case = vectors["qa_001"]
    assert isinstance(case, dict)
    expected = case["expected"]
    assert isinstance(expected, dict)

    output = _direct(plan, registry, _qa001_golden_payload(case), "P1-QA-001")
    structured = _structured(output)
    for field in (
        "r_rel_ecef_m",
        "v_rel_ecef_mps",
        "range_m",
        "range_rate_mps",
        "own_body_az_rad",
        "own_body_el_rad",
        "sensor_az_rad",
        "sensor_el_rad",
        "sensor_frame_status",
    ):
        if isinstance(expected[field], (int, float)):
            assert structured[field] == pytest.approx(expected[field])
        else:
            assert structured[field] == expected[field]

    negative = _qa001_golden_payload(case)
    sample = negative["samples"][0]
    assert isinstance(sample, dict)
    own = sample["own"]
    assert isinstance(own, dict)
    own["attitude_quat"] = [0.0, 0.0, 0.0, 0.0]
    with pytest.raises(ValueError, match="M2_QA_QUATERNION_ZERO_NORM"):
        _direct(plan, registry, negative, "P1-QA-001")


def test_c3_qa002_nondegenerate_golden_and_wrong_jacobian_negative() -> None:
    plan, registry, _inputs, _engine = _runtime()
    authority = _c3()
    vectors = authority["golden_vectors"]
    assert isinstance(vectors, dict)
    case = vectors["qa_002"]
    assert isinstance(case, dict)
    expected = case["expected"]
    assert isinstance(expected, dict)

    output = _direct(plan, registry, _qa002_golden_payload(case), "P1-QA-002")
    structured = _structured(output)
    for field in (
        "sigma_range_m",
        "sigma_az_rad",
        "sigma_el_rad",
        "sigma_position_3d_m",
    ):
        assert structured[field] == pytest.approx(expected[field])

    negative = _qa002_golden_payload(case)
    sample = negative["samples"][0]
    assert isinstance(sample, dict)
    sample["relative_state_jacobian"] = [[1.0, 0.0, 0.0, -1.0, 0.0]]
    with pytest.raises(ValueError, match="M2_QA_INPUT_SHAPE_INVALID"):
        _direct(plan, registry, negative, "P1-QA-002")
