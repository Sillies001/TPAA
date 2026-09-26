from __future__ import annotations

import hashlib
import json
import math
import shutil
from collections import Counter
from pathlib import Path

import pytest

from tpaa_metric import (
    CatalogMetricEngine,
    CatalogMetricEngineError,
    M2MetricPluginRequest,
    MetricPluginRegistry,
    build_m2_metric_execution_plan,
    validate_m2_runtime_output,
)
from tpaa_metric.operators import (
    TimedValue,
    arithmetic_mean,
    circular_mean,
    linear_interpolate,
    rms,
    wrap_pi,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
M2_AUTHORITY_FILES = (
    "P1_METRIC_CATALOG.json",
    "METRIC_INPUT_AUTHORITY_MATRIX.json",
    "SOURCE_PROVENANCE.json",
    "WORLD_CAPABILITY_REGISTRY.json",
    "CORE_LOGICAL_MODEL.json",
    "CORE_RULES.json",
)


def _copy_authority(tmp_path: Path) -> Path:
    copied = tmp_path / "canonical"
    copied.mkdir()
    for name in M2_AUTHORITY_FILES:
        shutil.copy2(AUTHORITY / name, copied / name)
    return copied


def _probe(request: M2MetricPluginRequest) -> dict[str, object]:
    return {
        "metric_code": request.definition.metric_code,
        "subject_type": request.definition.subject_type,
        "observation_lane": request.definition.observation_lane,
        "publication_route": request.definition.publication_route,
        "algorithm_id": request.definition.algorithm_id,
        "operators": sorted(request.operators),
        "input": dict(request.input_payload),
        "upstream": list(request.upstream_result_hashes),
    }


def _registry() -> MetricPluginRegistry:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    for algorithm_id in dict.fromkeys(
        definition.algorithm_id for definition in plan.definitions
    ):
        registry.register(
            algorithm_id,
            plugin_id="contract-probe-v1",
            plugin=_probe,
        )
    return registry


def _inputs() -> dict[str, dict[str, object]]:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    return {
        definition.metric_code: {
            "fixture": "M2-MET-001-CONTRACT",
            "catalog_index": definition.catalog_index,
        }
        for definition in plan.definitions
    }


def test_m2_plan_is_exact_catalog_foundation_batch() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)

    assert plan.catalog_id == "P1_METRIC_CATALOG"
    assert plan.db_schema_version == "1.6.0"
    assert plan.delivery_milestone == "M2"
    assert plan.delivery_batch == "P1_FOUNDATION_32"
    assert len(plan.catalog_metric_codes) == 32
    assert len(set(plan.catalog_metric_codes)) == 32
    assert set(plan.metric_codes) == set(plan.catalog_metric_codes)
    assert Counter(item.family for item in plan.definitions) == {
        "REFERENCE_TRUTH": 3,
        "TIME_ALIGNMENT": 5,
        "AIRCRAFT_FLIGHT": 3,
        "SENSOR_DETECTION": 4,
        "SENSOR_ACCURACY": 17,
    }
    assert plan.required_operator_ids == (
        "CIRCULAR_MEAN_V1",
        "DERIVATIVE_LLS_V1",
        "LINEAR_INTERPOLATION_V1",
        "MEAN_V1",
        "MEDIAN_V1",
        "QUANTILE_HF7_V1",
        "RMS_V1",
        "WRAP_PI_V1",
    )
    assert len(plan.logical_hash) == 64
    assert len(plan.catalog_sha256) == 64
    assert len(plan.input_authority_matrix_sha256) == 64
    assert len(plan.source_provenance_sha256) == 64
    assert len(plan.world_capability_registry_sha256) == 64
    assert len(plan.core_logical_model_sha256) == 64
    assert len(plan.core_rules_sha256) == 64
    assert plan.allowed_result_statuses == (
        "VALID",
        "N_A",
        "INSUFFICIENT_DATA",
        "INVALID",
        "REVIEW_REQUIRED",
    )
    assert plan.allowed_mission_system_types == (
        "RADAR",
        "IRST",
        "EO",
        "RWR",
        "ESM",
        "DATALINK",
        "FUSION",
        "MISSION_COMPUTER",
        "OTHER",
    )
    assert all(
        binding.metric_semantic_id == definition.semantic_id
        and binding.optional == binding.input_field.endswith("?")
        for definition in plan.definitions
        for binding in definition.input_authority_bindings
    )


def test_m2_input_authority_version_bridge_requires_frozen_provenance(
    tmp_path: Path,
) -> None:
    authority = _copy_authority(tmp_path)
    path = authority / "SOURCE_PROVENANCE.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["input_authority_migration"]["migration_scope"] = "TEST_ONLY_DRIFT"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogMetricEngineError) as caught:
        build_m2_metric_execution_plan(authority)
    assert caught.value.code == "M2_METRIC_INPUT_AUTHORITY_PROVENANCE_DRIFT"


def test_m2_input_authority_optional_marker_drift_fails_closed(
    tmp_path: Path,
) -> None:
    authority = _copy_authority(tmp_path)
    path = authority / "METRIC_INPUT_AUTHORITY_MATRIX.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    binding = next(
        item
        for item in payload["bindings"]
        if item["metric_code"] == "P1-QA-001"
        and item["input_field"] == "sensor_boresight_quat?"
    )
    binding["optional"] = False
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogMetricEngineError) as caught:
        build_m2_metric_execution_plan(authority)
    assert caught.value.code == "M2_METRIC_INPUT_AUTHORITY_OPTIONAL_DRIFT"


def test_m2_structured_schema_object_must_remain_closed_even_with_valid_hash(
    tmp_path: Path,
) -> None:
    authority = _copy_authority(tmp_path)
    path = authority / "P1_METRIC_CATALOG.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    entry = payload["structured_output_schema_registry"]["STRUCT_P1_QA_006_V1"]
    schema = entry["json_schema"]
    schema["additionalProperties"] = True
    canonical = json.dumps(
        schema,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    entry["schema_hash_sha256"] = hashlib.sha256(canonical).hexdigest()
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogMetricEngineError) as caught:
        build_m2_metric_execution_plan(authority)
    assert caught.value.code == "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED"


def test_m2_plan_is_dependency_ordered_and_sns_stays_radar_only() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    positions = {code: index for index, code in enumerate(plan.metric_codes)}

    for definition in plan.definitions:
        for dependency in definition.metric_dependencies:
            assert positions[dependency] < positions[definition.metric_code]

    sns = [item for item in plan.definitions if item.metric_code.startswith("P1-SNS-")]
    assert len(sns) == 21
    assert all(item.subject_type == "MISSION_SYSTEM_INSTANCE" for item in sns)
    assert all(item.applicability.key == "P1-SNS-*" for item in sns)
    assert all(item.applicability.applicability_mode == "SYSTEM_TYPE_EXACT" for item in sns)
    assert all(item.applicability.allowed_system_types == ("RADAR",) for item in sns)


def test_one_engine_dispatches_all_families_by_algorithm_id_replay_stably() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    engine = CatalogMetricEngine(plan, _registry())
    inputs = _inputs()

    first = engine.execute(inputs, validate_runtime_contract=False)
    second = engine.execute(inputs, validate_runtime_contract=False)

    assert first == second
    assert first.dispatch_key == "algorithm_id"
    assert len(first.records) == 32
    assert first.metric_codes == plan.metric_codes
    assert len({record.plugin_id for record in first.records}) == 1
    assert {record.plugin_id for record in first.records} == {"contract-probe-v1"}
    assert len(first.logical_hash) == 64

    seen: dict[str, str] = {}
    for record in first.records:
        definition = plan.definition(record.metric_code)
        assert record.algorithm_id == definition.algorithm_id
        assert record.operator_bindings == definition.operator_bindings
        assert record.upstream_result_hashes == tuple(
            (dependency, seen[dependency])
            for dependency in definition.metric_dependencies
        )
        seen[record.metric_code] = record.logical_hash


def test_subset_execution_closes_metric_dependencies_and_missing_plugin_fails_closed() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    engine = CatalogMetricEngine(plan, _registry())
    batch = engine.execute(
        _inputs(),
        metric_codes=("P1-SNS-005",),
        validate_runtime_contract=False,
    )

    assert batch.metric_codes[-1] == "P1-SNS-005"
    assert "P1-QA-001" in batch.metric_codes
    assert "P1-QA-002" in batch.metric_codes
    assert "P1-QA-005" in batch.metric_codes

    empty_engine = CatalogMetricEngine(plan, MetricPluginRegistry())
    with pytest.raises(CatalogMetricEngineError) as caught:
        empty_engine.execute(_inputs(), metric_codes=("P1-AIR-001",))
    assert caught.value.code == "M2_METRIC_PLUGIN_MISSING"


def test_plugin_registry_rejects_duplicate_algorithm_registration() -> None:
    registry = MetricPluginRegistry()
    registry.register(
        "alg.example",
        plugin_id="contract-probe-v1",
        plugin=_probe,
    )
    with pytest.raises(CatalogMetricEngineError) as caught:
        registry.register(
            "alg.example",
            plugin_id="contract-probe-v1",
            plugin=_probe,
        )
    assert caught.value.code == "M2_METRIC_PLUGIN_DUPLICATE"


def test_governed_m2_operator_primitives_are_deterministic_and_fail_closed() -> None:
    assert arithmetic_mean((1.0, 2.0, 3.0)) == 2.0
    assert rms((3.0, 4.0)) == pytest.approx(math.sqrt(12.5))
    assert wrap_pi(math.pi) == pytest.approx(-math.pi)
    assert wrap_pi(-math.pi) == pytest.approx(-math.pi)
    assert circular_mean((math.radians(179.0), math.radians(-179.0))) == pytest.approx(
        -math.pi,
        abs=1e-12,
    )

    values = (
        TimedValue(0, 0.0),
        TimedValue(1_000_000, 10.0),
        TimedValue(5_000_000, 50.0),
    )
    assert linear_interpolate(values, 500_000, max_gap_us=2_000_000) == 5.0
    with pytest.raises(ValueError, match="OUTSIDE_VALID_PIECE"):
        linear_interpolate(values, 3_000_000, max_gap_us=2_000_000)


def _valid_runtime_instance(
    *,
    value_kind: str,
    value_numeric: float | None = None,
    value_structured: dict[str, object] | None = None,
    status: str = "VALID",
) -> dict[str, object]:
    return {
        "status": status,
        "reason_codes": [],
        "value_kind": value_kind,
        "value_numeric": value_numeric,
        "value_structured": value_structured,
    }


def test_runtime_contract_gate_enforces_value_slots_and_structured_schema() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    numeric = plan.definition("P1-QA-003")
    validate_m2_runtime_output(
        numeric,
        {},
        {
            "metric_code": numeric.metric_code,
            "subject_type": numeric.subject_type,
            "observation_lane": numeric.observation_lane,
            "publication_route": numeric.publication_route,
            "instances": [
                _valid_runtime_instance(
                    value_kind="NUMERIC",
                    value_numeric=1.0,
                )
            ],
        },
    )

    with pytest.raises(CatalogMetricEngineError) as caught:
        validate_m2_runtime_output(
            numeric,
            {},
            {
                "metric_code": numeric.metric_code,
                "subject_type": numeric.subject_type,
            "observation_lane": numeric.observation_lane,
            "publication_route": numeric.publication_route,
                "observation_lane": numeric.observation_lane,
                "publication_route": numeric.publication_route,
                "instances": [
                    _valid_runtime_instance(
                        value_kind="NUMERIC",
                        value_structured={"forbidden": True},
                    )
                ],
            },
        )
    assert caught.value.code == "M2_METRIC_RUNTIME_VALUE_SLOT_MISMATCH"

    structured = plan.definition("P1-QA-006")
    valid_structured = {
        "error_domain": "RANGE",
        "residual_unit": "m",
        "raw_residual": 5.0,
        "reference_uncertainty": 3.0,
        "alignment_uncertainty": 1.0,
        "sensor_reported_uncertainty": 2.0,
        "normalized_residual": 5.0 / math.sqrt(14.0),
        "normalized_residual_status": "VALID",
    }
    validate_m2_runtime_output(
        structured,
        {},
        {
            "metric_code": structured.metric_code,
            "subject_type": structured.subject_type,
            "observation_lane": structured.observation_lane,
            "publication_route": structured.publication_route,
            "instances": [
                _valid_runtime_instance(
                    value_kind="STRUCTURED",
                    value_structured=valid_structured,
                )
            ],
        },
    )
    assert structured.structured_output_schema_hash_sha256 is not None
    assert len(structured.structured_output_schema_hash_sha256) == 64

    invalid_structured = dict(valid_structured)
    invalid_structured["unexpected"] = 1
    with pytest.raises(CatalogMetricEngineError) as caught:
        validate_m2_runtime_output(
            structured,
            {},
            {
                "metric_code": structured.metric_code,
                "subject_type": structured.subject_type,
            "observation_lane": structured.observation_lane,
            "publication_route": structured.publication_route,
                "observation_lane": structured.observation_lane,
                "publication_route": structured.publication_route,
                "instances": [
                    _valid_runtime_instance(
                        value_kind="STRUCTURED",
                        value_structured=invalid_structured,
                    )
                ],
            },
        )
    assert caught.value.code == "M2_METRIC_STRUCTURED_OUTPUT_SCHEMA_VIOLATION"


def test_runtime_contract_gate_enforces_subject_type_metadata() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    numeric = plan.definition("P1-QA-003")
    with pytest.raises(CatalogMetricEngineError) as caught:
        validate_m2_runtime_output(
            numeric,
            {},
            {
                "metric_code": numeric.metric_code,
                "subject_type": "AIRCRAFT",
                "observation_lane": numeric.observation_lane,
                "publication_route": numeric.publication_route,
                "instances": [
                    _valid_runtime_instance(
                        value_kind="NUMERIC",
                        value_numeric=1.0,
                    )
                ],
            },
        )
    assert caught.value.code == "M2_METRIC_RUNTIME_SUBJECT_TYPE_MISMATCH"


def test_runtime_contract_gate_enforces_publication_metadata() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    numeric = plan.definition("P1-QA-003")
    base = {
        "metric_code": numeric.metric_code,
        "subject_type": numeric.subject_type,
        "observation_lane": numeric.observation_lane,
        "publication_route": numeric.publication_route,
        "instances": [
            _valid_runtime_instance(
                value_kind="NUMERIC",
                value_numeric=1.0,
            )
        ],
    }

    wrong_lane = dict(base)
    wrong_lane["observation_lane"] = "TEST_ONLY_WRONG_LANE"
    with pytest.raises(CatalogMetricEngineError) as caught:
        validate_m2_runtime_output(numeric, {}, wrong_lane)
    assert caught.value.code == "M2_METRIC_RUNTIME_OBSERVATION_LANE_MISMATCH"

    wrong_route = dict(base)
    wrong_route["publication_route"] = "TEST_ONLY_WRONG_ROUTE"
    with pytest.raises(CatalogMetricEngineError) as caught:
        validate_m2_runtime_output(numeric, {}, wrong_route)
    assert caught.value.code == "M2_METRIC_RUNTIME_PUBLICATION_ROUTE_MISMATCH"


def test_runtime_contract_gate_enforces_sns_system_type_applicability() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    sns = plan.definition("P1-SNS-001")
    validate_m2_runtime_output(
        sns,
        {"system_type": "EO"},
        {
            "metric_code": sns.metric_code,
            "subject_type": sns.subject_type,
            "observation_lane": sns.observation_lane,
            "publication_route": sns.publication_route,
            "applicable": False,
            "reason_codes": ["SYSTEM_TYPE_NOT_APPLICABLE"],
            "instances": [],
        },
    )

    with pytest.raises(CatalogMetricEngineError) as caught:
        validate_m2_runtime_output(
            sns,
            {"system_type": "EO"},
            {
                "metric_code": sns.metric_code,
                "applicable": False,
                "reason_codes": ["SYSTEM_TYPE_NOT_APPLICABLE"],
                "instances": [],
            },
        )
    assert caught.value.code == "M2_METRIC_RUNTIME_SUBJECT_TYPE_MISMATCH"

    with pytest.raises(CatalogMetricEngineError) as caught:
        validate_m2_runtime_output(
            sns,
            {"system_type": "EO"},
            {
                "metric_code": sns.metric_code,
                "subject_type": sns.subject_type,
            "observation_lane": sns.observation_lane,
            "publication_route": sns.publication_route,
                "observation_lane": sns.observation_lane,
                "publication_route": sns.publication_route,
                "instances": [
                    _valid_runtime_instance(
                        value_kind="NUMERIC",
                        value_numeric=1.0,
                    )
                ],
            },
        )
    assert caught.value.code == "M2_METRIC_NOT_APPLICABLE_OUTPUT_INVALID"

    with pytest.raises(CatalogMetricEngineError) as caught:
        validate_m2_runtime_output(
            sns,
            {"system_type": "TEST_ONLY_UNKNOWN_SYSTEM_TYPE"},
            {
                "metric_code": sns.metric_code,
                "subject_type": sns.subject_type,
            "observation_lane": sns.observation_lane,
            "publication_route": sns.publication_route,
                "observation_lane": sns.observation_lane,
                "publication_route": sns.publication_route,
                "applicable": False,
                "reason_codes": ["SYSTEM_TYPE_NOT_APPLICABLE"],
                "instances": [],
            },
        )
    assert caught.value.code == "M2_METRIC_APPLICABILITY_INPUT_INVALID"

    with pytest.raises(CatalogMetricEngineError) as caught:
        validate_m2_runtime_output(
            sns,
            {"system_type": "RADAR"},
            {
                "metric_code": sns.metric_code,
                "subject_type": sns.subject_type,
            "observation_lane": sns.observation_lane,
            "publication_route": sns.publication_route,
                "observation_lane": sns.observation_lane,
                "publication_route": sns.publication_route,
                "applicable": False,
                "reason_codes": ["SYSTEM_TYPE_NOT_APPLICABLE"],
                "instances": [],
            },
        )
    assert caught.value.code == "M2_METRIC_APPLICABLE_OUTPUT_REJECTED"

    with pytest.raises(CatalogMetricEngineError) as caught:
        validate_m2_runtime_output(
            sns,
            {"system_type": "RADAR"},
            {
                "metric_code": sns.metric_code,
                "subject_type": sns.subject_type,
            "observation_lane": sns.observation_lane,
            "publication_route": sns.publication_route,
                "observation_lane": sns.observation_lane,
                "publication_route": sns.publication_route,
                "instances": [
                    _valid_runtime_instance(
                        value_kind="NUMERIC",
                        value_numeric=1.0,
                    )
                ],
            },
        )
    assert caught.value.code == "M2_METRIC_APPLICABLE_OUTPUT_REJECTED"


def test_general_engine_runtime_gate_is_default_and_probe_opt_out_is_explicit() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    engine = CatalogMetricEngine(plan, _registry())

    with pytest.raises(CatalogMetricEngineError) as caught:
        engine.execute(_inputs(), metric_codes=("P1-AIR-001",))
    assert caught.value.code == "M2_METRIC_RUNTIME_OUTPUT_SHAPE_INVALID"

    batch = engine.execute(
        _inputs(),
        metric_codes=("P1-AIR-001",),
        validate_runtime_contract=False,
    )
    assert batch.metric_codes == ("P1-AIR-001",)



def test_runtime_contract_gate_binds_core_status_enum_and_missing_reason_rule() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    numeric = plan.definition("P1-QA-003")

    for status, reasons in (
        ("N_A", ["TEST_MISSING_PREREQUISITE"]),
        ("INSUFFICIENT_DATA", ["TEST_INSUFFICIENT_DATA"]),
        ("INVALID", []),
        ("REVIEW_REQUIRED", []),
    ):
        validate_m2_runtime_output(
            numeric,
            {},
            {
                "metric_code": numeric.metric_code,
                "subject_type": numeric.subject_type,
            "observation_lane": numeric.observation_lane,
            "publication_route": numeric.publication_route,
                "observation_lane": numeric.observation_lane,
                "publication_route": numeric.publication_route,
                "instances": [
                    {
                        "status": status,
                        "reason_codes": reasons,
                        "value_kind": "NUMERIC",
                        "value_numeric": None,
                        "value_structured": None,
                    }
                ],
            },
        )

    with pytest.raises(CatalogMetricEngineError) as caught:
        validate_m2_runtime_output(
            numeric,
            {},
            {
                "metric_code": numeric.metric_code,
                "subject_type": numeric.subject_type,
            "observation_lane": numeric.observation_lane,
            "publication_route": numeric.publication_route,
                "observation_lane": numeric.observation_lane,
                "publication_route": numeric.publication_route,
                "instances": [
                    {
                        "status": "TEST_ONLY_UNKNOWN_STATUS",
                        "reason_codes": [],
                        "value_kind": "NUMERIC",
                        "value_numeric": None,
                        "value_structured": None,
                    }
                ],
            },
        )
    assert caught.value.code == "M2_METRIC_RUNTIME_STATUS_INVALID"

    for status in ("N_A", "INSUFFICIENT_DATA"):
        with pytest.raises(CatalogMetricEngineError) as caught:
            validate_m2_runtime_output(
                numeric,
                {},
                {
                    "metric_code": numeric.metric_code,
                    "subject_type": numeric.subject_type,
            "observation_lane": numeric.observation_lane,
            "publication_route": numeric.publication_route,
                "observation_lane": numeric.observation_lane,
                "publication_route": numeric.publication_route,
                    "instances": [
                        {
                            "status": status,
                            "reason_codes": [],
                            "value_kind": "NUMERIC",
                            "value_numeric": None,
                            "value_structured": None,
                        }
                    ],
                },
            )
        assert caught.value.code == "M2_METRIC_RUNTIME_REASON_CODE_REQUIRED"
