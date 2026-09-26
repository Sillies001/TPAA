from __future__ import annotations

import hashlib
import json
import math
import shutil
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

import tpaa_metric.catalog_engine as catalog_engine
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
    for definition in plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
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
    assert plan.required_state_machine_ids == (
        "SM_CLOCK_SEGMENT_V1",
        "SM_VALIDITY_PIECE_V1",
    )
    assert plan.required_external_dependency_ids == (
        "CONTRACT_ASSOCIATION_RELATION_V1",
        "CONTRACT_DETECTION_CONFIRMATION_EVENT_V1",
        "CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1",
        "CONTRACT_NAV_UNCERTAINTY_REPRESENTATION_V1",
        "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1",
        "CONTRACT_REFERENCE_RELATIVE_STATE_V1",
        "CONTRACT_TIME_TRANSFORM_V1",
    )
    assert len(plan.logical_hash) == 64
    assert len(plan.catalog_sha256) == 64
    assert len(plan.input_authority_matrix_sha256) == 64
    assert len(plan.source_provenance_sha256) == 64
    assert len(plan.world_capability_registry_sha256) == 64
    assert len(plan.core_logical_model_sha256) == 64
    assert len(plan.core_rules_sha256) == 64
    assert len(plan.operator_registry_sha256) == 64
    assert len(plan.constant_registry_sha256) == 64
    assert len(plan.state_machine_registry_sha256) == 64
    assert len(plan.upstream_contract_registry_sha256) == 64
    assert len(plan.structured_output_schema_registry_sha256) == 64
    assert len(plan.family_applicability_contracts_sha256) == 64
    assert len(plan.generated_metric_projection_sha256) == 64
    assert len(plan.execution_identity_sha256) == 64
    assert plan.input_lineage_encoding == "TPAA_M2_INPUT_LINEAGE_JSON_V1"
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
    assert sum(
        definition.p1_longitudinal_trend_eligibility
        for definition in plan.definitions
    ) == 26
    assert sum(
        definition.default_aggregation == "MEDIAN"
        for definition in plan.definitions
    ) == 26
    assert sum(
        definition.default_aggregation == "NONE"
        for definition in plan.definitions
    ) == 6
    assert all(
        not definition.p1_longitudinal_trend_eligibility
        for definition in plan.definitions
        if definition.observation_lane == "QUALITY_EVIDENCE_ONLY"
    )
    assert all(
        not definition.p1_longitudinal_trend_eligibility
        for definition in plan.definitions
        if definition.value_kind == "STRUCTURED"
    )
    assert all(
        not definition.p1_longitudinal_trend_eligibility
        for definition in plan.definitions
        if definition.subject_type == "TARGET_PAIR"
    )
    assert all(
        definition.subject_type in {"AIRCRAFT", "MISSION_SYSTEM_INSTANCE"}
        for definition in plan.definitions
        if definition.p1_longitudinal_trend_eligibility
    )
    assert {
        definition.metric_code: tuple(sorted(definition.profile_parameters))
        for definition in plan.definitions
        if definition.profile_parameters
    } == {
        "P1-QA-005": ("max_gap_us",),
        "P1-AIR-001": ("max_gap_us", "min_coverage"),
        "P1-AIR-003": ("derivative_window_s", "max_gap_us"),
    }
    assert all(
        binding.metric_semantic_id == definition.semantic_id
        and binding.optional == binding.input_field.endswith("?")
        for definition in plan.definitions
        for binding in definition.input_authority_bindings
    )
    assert all(
        definition.semantic_id
        and isinstance(definition.semantic_version, int)
        and definition.algorithm_id
        and definition.algorithm_version
        and len(definition.definition_hash) == 64
        and len(definition.authority_lineage_hash) == 64
        for definition in plan.definitions
    )
    reference_match_definitions = tuple(
        definition
        for definition in plan.definitions
        if "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1"
        in definition.upstream_dependencies
    )
    assert tuple(item.metric_code for item in reference_match_definitions) == tuple(
        f"P1-SNS-{index:03d}" for index in range(5, 22)
    )
    expected_reference_match_identity = {
        (
            "reference_match_quality_profile_id",
            "reference_match_quality_profile_id",
            "UPSTREAM_CONTRACT",
            False,
        ),
        (
            "reference_match_quality_profile_version",
            "reference_match_quality_profile_version",
            "UPSTREAM_CONTRACT",
            False,
        ),
        (
            "reference_match_quality_profile_hash",
            "reference_match_quality_profile_hash",
            "UPSTREAM_CONTRACT",
            False,
        ),
    }
    for definition in reference_match_definitions:
        bindings = {
            (
                binding.input_field,
                binding.authority_field,
                binding.binding_kind,
                binding.optional,
            )
            for binding in definition.input_authority_bindings
            if binding.authority_id == "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1"
        }
        assert bindings == expected_reference_match_identity


def test_m2_reference_match_profile_identity_binding_fails_closed(
    tmp_path: Path,
) -> None:
    authority = _copy_authority(tmp_path)
    path = authority / "METRIC_INPUT_AUTHORITY_MATRIX.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    binding = next(
        item
        for item in payload["bindings"]
        if item["metric_code"] == "P1-SNS-005"
        and item["input_field"] == "reference_match_quality_profile_hash"
    )
    binding["authority_field"] = "profile_hash"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogMetricEngineError) as caught:
        build_m2_metric_execution_plan(authority)
    assert caught.value.code == "M2_METRIC_REFERENCE_MATCH_PROFILE_IDENTITY_DRIFT"


def test_m2_profile_parameter_input_exact_name_contract_fails_closed(
    tmp_path: Path,
) -> None:
    authority = _copy_authority(tmp_path)
    path = authority / "P1_METRIC_CATALOG.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    metric = next(
        item
        for item in payload["metrics"]
        if item["metric_code"] == "P1-AIR-001"
    )
    metric["profile_parameters"] = ["max_gap_us"]
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogMetricEngineError) as caught:
        build_m2_metric_execution_plan(authority)
    assert caught.value.code == "M2_METRIC_PROFILE_INPUT_CONTRACT_DRIFT"


def test_m2_governed_formula_dependency_reference_fails_closed(
    tmp_path: Path,
) -> None:
    authority = _copy_authority(tmp_path)
    path = authority / "P1_METRIC_CATALOG.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    metric = next(
        item for item in payload["metrics"] if item["metric_code"] == "P1-QA-003"
    )
    metric["operator_bindings"].remove("MEAN_V1")
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogMetricEngineError) as caught:
        build_m2_metric_execution_plan(authority)
    assert caught.value.code == "M2_METRIC_FORMULA_DEPENDENCY_UNBOUND"


def test_m2_canonical_event_contract_reference_fails_closed(
    tmp_path: Path,
) -> None:
    authority = _copy_authority(tmp_path)
    path = authority / "P1_METRIC_CATALOG.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    metric = next(
        item for item in payload["metrics"] if item["metric_code"] == "P1-SNS-002"
    )
    metric["upstream_dependencies"].remove(
        "CONTRACT_DETECTION_CONFIRMATION_EVENT_V1"
    )
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogMetricEngineError) as caught:
        build_m2_metric_execution_plan(authority)
    assert caught.value.code == "M2_METRIC_FORMULA_DEPENDENCY_UNBOUND"


def test_m2_dependency_binding_duplicates_fail_closed(tmp_path: Path) -> None:
    authority = _copy_authority(tmp_path)
    path = authority / "P1_METRIC_CATALOG.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    metric = next(
        item for item in payload["metrics"] if item["metric_code"] == "P1-QA-003"
    )
    metric["operator_bindings"].append("MEAN_V1")
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogMetricEngineError) as caught:
        build_m2_metric_execution_plan(authority)
    assert caught.value.code == "M2_METRIC_DEPENDENCY_BINDING_DUPLICATE"


def test_m2_dependency_closure_common_rule_drift_fails_closed(
    tmp_path: Path,
) -> None:
    authority = _copy_authority(tmp_path)
    path = authority / "P1_METRIC_CATALOG.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["common_rules"]["algorithm_dependency_closure"] = "TEST_ONLY_DRIFT"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogMetricEngineError) as caught:
        build_m2_metric_execution_plan(authority)
    assert caught.value.code == "M2_METRIC_RUNTIME_RULE_AUTHORITY_INVALID"


def test_m2_versioned_registry_entry_shape_fails_closed(
    tmp_path: Path,
) -> None:
    authority = _copy_authority(tmp_path)
    path = authority / "P1_METRIC_CATALOG.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["upstream_contract_registry"]["CONTRACT_TIME_TRANSFORM_V1"]["version"]
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogMetricEngineError) as caught:
        build_m2_metric_execution_plan(authority)
    assert caught.value.code == "M2_METRIC_CATALOG_FIELD_INVALID"


def test_m2_generated_projection_name_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mutated = []
    for raw in catalog_engine.P1_METRICS:
        item = dict(raw)
        if item["metric_code"] == "P1-AIR-001":
            item["name"] = "TEST_ONLY_GENERATED_NAME_DRIFT"
        mutated.append(item)
    monkeypatch.setattr(catalog_engine, "P1_METRICS", tuple(mutated))

    with pytest.raises(CatalogMetricEngineError) as caught:
        build_m2_metric_execution_plan(AUTHORITY)
    assert caught.value.code == "M2_METRIC_GENERATED_REGISTRY_DRIFT"


def test_m2_generated_projection_duplicate_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate = dict(catalog_engine.P1_METRICS[0])
    monkeypatch.setattr(
        catalog_engine,
        "P1_METRICS",
        (*catalog_engine.P1_METRICS, duplicate),
    )

    with pytest.raises(CatalogMetricEngineError) as caught:
        build_m2_metric_execution_plan(AUTHORITY)
    assert caught.value.code == "M2_METRIC_GENERATED_REGISTRY_DUPLICATE"


def test_m2_algorithm_identity_common_rule_drift_fails_closed(
    tmp_path: Path,
) -> None:
    authority = _copy_authority(tmp_path)
    path = authority / "P1_METRIC_CATALOG.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["common_rules"]["algorithm_identity"] = "TEST_ONLY_DRIFT"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogMetricEngineError) as caught:
        build_m2_metric_execution_plan(authority)
    assert caught.value.code == "M2_METRIC_RUNTIME_RULE_AUTHORITY_INVALID"


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


def test_m2_longitudinal_metadata_drift_fails_closed(tmp_path: Path) -> None:
    authority = _copy_authority(tmp_path)
    path = authority / "P1_METRIC_CATALOG.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    metric = next(
        item
        for item in payload["metrics"]
        if item["metric_code"] == "P1-QA-005"
    )
    metric["default_aggregation"] = "MEDIAN"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogMetricEngineError) as caught:
        build_m2_metric_execution_plan(authority)
    assert caught.value.code == "M2_METRIC_LONGITUDINAL_CONTRACT_DRIFT"


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
    assert first.dispatch_key == "algorithm_id+algorithm_version"
    assert len(first.records) == 32
    assert first.metric_codes == plan.metric_codes
    assert len({record.plugin_id for record in first.records}) == 1
    assert {record.plugin_id for record in first.records} == {"contract-probe-v1"}
    assert len(first.logical_hash) == 64

    seen: dict[str, str] = {}
    for record in first.records:
        definition = plan.definition(record.metric_code)
        assert record.semantic_id == definition.semantic_id
        assert record.semantic_version == definition.semantic_version
        assert record.algorithm_id == definition.algorithm_id
        assert record.algorithm_version == definition.algorithm_version
        assert record.definition_hash == definition.definition_hash
        assert record.authority_lineage_hash == definition.authority_lineage_hash
        assert record.plan_hash == plan.logical_hash
        assert record.input_lineage_encoding == "TPAA_M2_INPUT_LINEAGE_JSON_V1"
        assert len(record.input_payload_hash) == 64
        assert record.operator_bindings == definition.operator_bindings
        assert len(record.dependency_manifest_hash) == 64
        expected_dependency_manifest_hash = hashlib.sha256(
            json.dumps(
                {
                    "constant_bindings": definition.constant_bindings,
                    "external_dependencies": definition.external_dependencies,
                    "formula_dependency_references": (
                        definition.formula_dependency_references
                    ),
                    "metric_dependencies": definition.metric_dependencies,
                    "operator_bindings": definition.operator_bindings,
                    "state_machine_bindings": definition.state_machine_bindings,
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
        ).hexdigest()
        assert record.dependency_manifest_hash == expected_dependency_manifest_hash
        assert record.upstream_result_hashes == tuple(
            (dependency, seen[dependency])
            for dependency in definition.metric_dependencies
        )
        expected_record_hash = hashlib.sha256(
            json.dumps(
                {
                    "algorithm_id": record.algorithm_id,
                    "algorithm_version": record.algorithm_version,
                    "authority_lineage_hash": record.authority_lineage_hash,
                    "definition_hash": record.definition_hash,
                    "dependency_manifest_hash": record.dependency_manifest_hash,
                    "input_lineage_encoding": record.input_lineage_encoding,
                    "input_payload_hash": record.input_payload_hash,
                    "metric_code": record.metric_code,
                    "operator_bindings": record.operator_bindings,
                    "plan_hash": record.plan_hash,
                    "plugin_id": record.plugin_id,
                    "plugin_output_hash": record.plugin_output_hash,
                    "semantic_id": record.semantic_id,
                    "semantic_version": record.semantic_version,
                    "upstream_result_hashes": record.upstream_result_hashes,
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
        ).hexdigest()
        assert record.logical_hash == expected_record_hash
        seen[record.metric_code] = record.logical_hash

    expected_plugin_manifest_hash = hashlib.sha256(
        json.dumps(
            [
                (record.algorithm_id, record.algorithm_version, record.plugin_id)
                for record in first.records
            ],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    assert first.plugin_manifest_hash == expected_plugin_manifest_hash
    expected_batch_hash = hashlib.sha256(
        json.dumps(
            {
                "dispatch_key": first.dispatch_key,
                "plan_hash": plan.logical_hash,
                "plugin_manifest_hash": first.plugin_manifest_hash,
                "record_hashes": [record.logical_hash for record in first.records],
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    assert first.logical_hash == expected_batch_hash


def test_input_payload_hash_changes_record_even_when_plugin_output_is_constant() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)

    def constant_probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {"metric_code": request.definition.metric_code, "constant": True}

    registry = MetricPluginRegistry()
    for definition in plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id="constant-lineage-probe-v1",
            plugin=constant_probe,
        )

    engine = CatalogMetricEngine(plan, registry)
    first_inputs = _inputs()
    second_inputs = {code: dict(payload) for code, payload in first_inputs.items()}
    second_inputs["P1-AIR-001"]["fixture"] = "M2-MET-001-CONTRACT-MUTATED"

    first = engine.execute(first_inputs, validate_runtime_contract=False)
    second = engine.execute(second_inputs, validate_runtime_contract=False)
    first_record = next(record for record in first.records if record.metric_code == "P1-AIR-001")
    second_record = next(record for record in second.records if record.metric_code == "P1-AIR-001")

    assert first_record.plugin_output_hash == second_record.plugin_output_hash
    assert first_record.input_payload_hash != second_record.input_payload_hash
    assert first_record.logical_hash != second_record.logical_hash
    assert first.logical_hash != second.logical_hash


def test_plan_hash_is_bound_into_every_record_and_batch_hash() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    mutated_plan = replace(plan, logical_hash="0" * 64)

    def constant_probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {"metric_code": request.definition.metric_code, "constant": True}

    registry = MetricPluginRegistry()
    for definition in plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id="plan-lineage-probe-v1",
            plugin=constant_probe,
        )

    inputs = _inputs()
    first = CatalogMetricEngine(plan, registry).execute(
        inputs,
        validate_runtime_contract=False,
    )
    mutated = CatalogMetricEngine(mutated_plan, registry).execute(
        inputs,
        validate_runtime_contract=False,
    )

    assert first.logical_hash != mutated.logical_hash
    assert first.plugin_manifest_hash == mutated.plugin_manifest_hash
    first_by_code = {record.metric_code: record for record in first.records}
    mutated_by_code = {record.metric_code: record for record in mutated.records}
    assert all(
        first_by_code[code].plan_hash == plan.logical_hash
        for code in plan.metric_codes
    )
    assert all(
        mutated_by_code[code].plan_hash == "0" * 64
        for code in plan.metric_codes
    )
    assert all(
        first_by_code[code].plugin_output_hash
        == mutated_by_code[code].plugin_output_hash
        for code in plan.metric_codes
    )
    assert all(
        first_by_code[code].dependency_manifest_hash
        == mutated_by_code[code].dependency_manifest_hash
        for code in plan.metric_codes
    )
    assert all(
        first_by_code[code].logical_hash != mutated_by_code[code].logical_hash
        for code in plan.metric_codes
    )


def test_input_payload_lineage_rejects_opaque_runtime_objects() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    engine = CatalogMetricEngine(plan, _registry())
    inputs = _inputs()
    inputs["P1-AIR-001"]["opaque"] = object()

    with pytest.raises(CatalogMetricEngineError) as caught:
        engine.execute(
            inputs,
            metric_codes=("P1-AIR-001",),
            validate_runtime_contract=False,
        )
    assert caught.value.code == "M2_METRIC_INPUT_LINEAGE_UNSUPPORTED"


def test_authority_lineage_hash_is_scoped_to_referenced_registry_entries(
    tmp_path: Path,
) -> None:
    baseline = build_m2_metric_execution_plan(AUTHORITY)
    authority = _copy_authority(tmp_path)
    path = authority / "P1_METRIC_CATALOG.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["operator_registry"]["MEAN_V1"]["definition"] += " TEST_ONLY_LINEAGE_MUTATION"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    mutated = build_m2_metric_execution_plan(authority)

    baseline_by_code = {item.metric_code: item for item in baseline.definitions}
    mutated_by_code = {item.metric_code: item for item in mutated.definitions}
    expected_changed = {
        item.metric_code
        for item in baseline.definitions
        if "MEAN_V1" in item.operator_bindings
    }
    actual_changed = {
        code
        for code in baseline_by_code
        if baseline_by_code[code].authority_lineage_hash
        != mutated_by_code[code].authority_lineage_hash
    }

    assert expected_changed
    assert actual_changed == expected_changed
    assert baseline.logical_hash != mutated.logical_hash


def test_subset_execution_closes_metric_dependencies_and_missing_plugin_fails_closed() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    engine = CatalogMetricEngine(plan, _registry())
    requested = ("P1-SNS-005",)
    batch = engine.execute(
        _inputs(),
        metric_codes=requested,
        validate_runtime_contract=False,
    )

    expected_codes = set(requested)
    changed = True
    while changed:
        changed = False
        for definition in plan.definitions:
            if definition.metric_code not in expected_codes:
                continue
            for dependency in definition.metric_dependencies:
                if dependency not in expected_codes:
                    expected_codes.add(dependency)
                    changed = True
    assert batch.metric_codes == tuple(
        code for code in plan.metric_codes if code in expected_codes
    )
    assert batch.metric_codes[-1] == "P1-SNS-005"
    assert "P1-QA-001" in batch.metric_codes
    assert "P1-QA-002" in batch.metric_codes
    assert "P1-QA-005" in batch.metric_codes

    all_inputs = _inputs()
    closure_inputs = {code: all_inputs[code] for code in batch.metric_codes}
    scoped = engine.execute(
        closure_inputs,
        metric_codes=requested,
        validate_runtime_contract=False,
    )
    assert scoped == batch

    missing_code = batch.metric_codes[0]
    del closure_inputs[missing_code]
    with pytest.raises(CatalogMetricEngineError) as missing:
        engine.execute(
            closure_inputs,
            metric_codes=requested,
            validate_runtime_contract=False,
        )
    assert missing.value.code == "M2_METRIC_INPUT_PAYLOAD_MISSING"

    with pytest.raises(CatalogMetricEngineError) as duplicate:
        engine.execute(
            _inputs(),
            metric_codes=("P1-SNS-005", "P1-SNS-005"),
            validate_runtime_contract=False,
        )
    assert duplicate.value.code == "M2_METRIC_REQUEST_DUPLICATE"

    with pytest.raises(CatalogMetricEngineError) as unknown:
        engine.execute(
            _inputs(),
            metric_codes=("P1-SNS-005", "P1-UNKNOWN-999"),
            validate_runtime_contract=False,
        )
    assert unknown.value.code == "M2_METRIC_REQUEST_UNKNOWN"

    empty_engine = CatalogMetricEngine(plan, MetricPluginRegistry())
    with pytest.raises(CatalogMetricEngineError) as caught:
        empty_engine.execute(_inputs(), metric_codes=("P1-AIR-001",))
    assert caught.value.code == "M2_METRIC_PLUGIN_MISSING"


def test_plugin_identity_manifest_changes_lineage_without_changing_constant_output() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)

    def constant_probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {"metric_code": request.definition.metric_code, "constant": True}

    def registry(plugin_id: str) -> MetricPluginRegistry:
        result = MetricPluginRegistry()
        for definition in plan.definitions:
            result.register(
                definition.algorithm_id,
                algorithm_version=definition.algorithm_version,
                plugin_id=plugin_id,
                plugin=constant_probe,
            )
        return result

    first = CatalogMetricEngine(plan, registry("identity-probe-v1")).execute(
        _inputs(),
        validate_runtime_contract=False,
    )
    second = CatalogMetricEngine(plan, registry("identity-probe-v2")).execute(
        _inputs(),
        validate_runtime_contract=False,
    )

    expected_manifest_hash = hashlib.sha256(
        json.dumps(
            [
                (
                    definition.algorithm_id,
                    definition.algorithm_version,
                    "identity-probe-v1",
                )
                for definition in plan.definitions
            ],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    assert first.plugin_manifest_hash == expected_manifest_hash
    assert second.plugin_manifest_hash != first.plugin_manifest_hash
    assert second.logical_hash != first.logical_hash

    first_by_code = {record.metric_code: record for record in first.records}
    second_by_code = {record.metric_code: record for record in second.records}
    assert all(
        first_by_code[code].plugin_output_hash
        == second_by_code[code].plugin_output_hash
        for code in plan.metric_codes
    )
    assert all(
        first_by_code[code].logical_hash != second_by_code[code].logical_hash
        for code in plan.metric_codes
    )


def test_plugin_registry_is_version_qualified_and_fails_closed() -> None:
    registry = MetricPluginRegistry()
    registry.register(
        "alg.example",
        algorithm_version="1.0.0",
        plugin_id="contract-probe-v1",
        plugin=_probe,
    )
    with pytest.raises(CatalogMetricEngineError) as caught:
        registry.register(
            "alg.example",
            algorithm_version="1.0.0",
            plugin_id="contract-probe-v1",
            plugin=_probe,
        )
    assert caught.value.code == "M2_METRIC_PLUGIN_DUPLICATE"

    registry.register(
        "alg.example",
        algorithm_version="1.0.1",
        plugin_id="contract-probe-v2",
        plugin=_probe,
    )
    assert registry.resolve("alg.example", "1.0.0")[0] == "contract-probe-v1"
    assert registry.resolve("alg.example", "1.0.1")[0] == "contract-probe-v2"
    with pytest.raises(CatalogMetricEngineError) as ambiguous:
        registry.resolve("alg.example")
    assert ambiguous.value.code == "M2_METRIC_PLUGIN_VERSION_AMBIGUOUS"


def test_engine_rejects_wrong_or_unversioned_algorithm_plugin() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    definition = plan.definition("P1-AIR-001")

    wrong_version = MetricPluginRegistry()
    wrong_version.register(
        definition.algorithm_id,
        algorithm_version="0.0.0",
        plugin_id="wrong-version-probe-v1",
        plugin=_probe,
    )
    with pytest.raises(CatalogMetricEngineError) as mismatch:
        CatalogMetricEngine(plan, wrong_version).execute(
            _inputs(),
            metric_codes=("P1-AIR-001",),
            validate_runtime_contract=False,
        )
    assert mismatch.value.code == "M2_METRIC_PLUGIN_VERSION_MISMATCH"

    unversioned = MetricPluginRegistry()
    unversioned.register(
        definition.algorithm_id,
        plugin_id="unversioned-probe-v1",
        plugin=_probe,
    )
    with pytest.raises(CatalogMetricEngineError) as unbound:
        CatalogMetricEngine(plan, unversioned).execute(
            _inputs(),
            metric_codes=("P1-AIR-001",),
            validate_runtime_contract=False,
        )
    assert unbound.value.code == "M2_METRIC_PLUGIN_VERSION_UNBOUND"


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
