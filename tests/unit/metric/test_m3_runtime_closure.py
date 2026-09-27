from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from tpaa_metric import (
    M3_RUNTIME_METRIC_COUNT,
    M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
    build_m3_metric_execution_plan,
    build_m3_runtime_plugin_registry,
    validate_m2_runtime_output,
)
from tpaa_metric.catalog_engine import M2MetricDefinition

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise AssertionError(f"{field} must be a string-keyed object")
    return cast(dict[str, object], value)


def _schema_types(schema: Mapping[str, object]) -> tuple[str, ...]:
    raw = schema.get("type")
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, list) and raw and all(isinstance(item, str) for item in raw):
        return tuple(cast(list[str], raw))
    raise AssertionError(f"unsupported schema type {raw!r}")


def _schema_value(schema: Mapping[str, object], *, field: str) -> object:
    types = _schema_types(schema)
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    if "null" in types:
        return None

    primary = types[0]
    if primary == "object":
        properties = _mapping(schema.get("properties"), field=f"{field}.properties")
        required = schema.get("required", [])
        assert isinstance(required, list)
        result: dict[str, object] = {}
        for raw_name in required:
            assert isinstance(raw_name, str)
            result[raw_name] = _schema_value(
                _mapping(properties.get(raw_name), field=f"{field}.{raw_name}"),
                field=f"{field}.{raw_name}",
            )
        return result
    if primary == "array":
        items = _mapping(schema.get("items"), field=f"{field}.items")
        min_items = schema.get("minItems", 0)
        assert isinstance(min_items, int) and not isinstance(min_items, bool)
        return [
            _schema_value(items, field=f"{field}[{index}]")
            for index in range(min_items)
        ]
    if primary == "number":
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and not isinstance(minimum, bool):
            result = float(minimum)
            assert math.isfinite(result)
            return result
        return 0.0
    if primary == "integer":
        minimum = schema.get("minimum")
        if isinstance(minimum, int) and not isinstance(minimum, bool):
            return minimum
        return 0
    if primary == "string":
        if schema.get("pattern") == "^-?[0-9]+$":
            return "0"
        return "PROBE"
    if primary == "boolean":
        return False
    raise AssertionError(f"unsupported schema type {primary!r}")


def _positive_input(definition: M2MetricDefinition) -> dict[str, object]:
    applicability = definition.applicability
    payload: dict[str, object] = {"probe_token": definition.metric_code}
    if applicability.applicability_mode in {"SYSTEM_TYPE_EXACT", "SYSTEM_TYPE_SET"}:
        assert applicability.allowed_system_types
        payload["system_type"] = applicability.allowed_system_types[0]
    elif applicability.applicability_mode == "PRODUCT_CAPABILITY":
        required = applicability.required_product_semantics
        assert required is not None
        payload["product_semantics"] = [required]
    return payload


def _positive_output(definition: M2MetricDefinition) -> dict[str, object]:
    structured: object | None = None
    numeric: float | None = None
    if definition.value_kind == "STRUCTURED":
        assert definition.structured_output_schema_json is not None
        schema_raw: object = json.loads(definition.structured_output_schema_json)
        schema = _mapping(schema_raw, field=definition.metric_code)
        structured = _schema_value(schema, field=definition.metric_code)
    else:
        assert definition.value_kind == "NUMERIC"
        numeric = 1.0
    return {
        "metric_code": definition.metric_code,
        "subject_type": definition.subject_type,
        "observation_lane": definition.observation_lane,
        "publication_route": definition.publication_route,
        "applicable": True,
        "instances": [
            {
                "status": "VALID",
                "reason_codes": [],
                "value_kind": definition.value_kind,
                "value_numeric": numeric,
                "value_structured": structured,
                "value_text": None,
                "value_boolean": None,
            }
        ],
    }


def test_m3_runtime_registry_resolves_exact_116() -> None:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    registry = build_m3_runtime_plugin_registry(plan)

    assert len(plan.definitions) == M3_RUNTIME_METRIC_COUNT == 116
    assert len(registry.plugin_identity_manifest) == 116
    assert set(plan.required_operator_ids) <= set(M3_RUNTIME_OPERATOR_IMPLEMENTATIONS)
    for definition in plan.definitions:
        plugin_id, _plugin = registry.resolve(
            definition.algorithm_id,
            definition.algorithm_version,
        )
        assert plugin_id


def test_all_116_positive_runtime_slots_and_nine_structured_schemas_validate() -> None:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    structured = tuple(
        definition
        for definition in plan.definitions
        if definition.value_kind == "STRUCTURED"
    )

    assert len(structured) == 9
    assert sum(definition.metric_code.startswith("P1-AIR-") for definition in structured) == 6

    for definition in plan.definitions:
        validate_m2_runtime_output(
            definition,
            _positive_input(definition),
            _positive_output(definition),
        )

    for definition in structured:
        assert definition.structured_output_schema_json is not None
        assert definition.structured_output_schema_hash_sha256 is not None
        actual = hashlib.sha256(
            definition.structured_output_schema_json.encode("utf-8")
        ).hexdigest()
        assert actual == definition.structured_output_schema_hash_sha256


def test_all_mission_product_applicability_modes_fail_closed_when_not_applicable() -> None:
    plan = build_m3_metric_execution_plan(AUTHORITY)

    checked = 0
    for definition in plan.definitions:
        applicability = definition.applicability
        payload: dict[str, object]
        if applicability.applicability_mode in {"SYSTEM_TYPE_EXACT", "SYSTEM_TYPE_SET"}:
            negative = next(
                system_type
                for system_type in definition.allowed_mission_system_types
                if system_type not in applicability.allowed_system_types
            )
            payload = {"system_type": negative}
        elif applicability.applicability_mode == "PRODUCT_CAPABILITY":
            payload = {"product_semantics": []}
        else:
            continue

        output = {
            "metric_code": definition.metric_code,
            "subject_type": definition.subject_type,
            "observation_lane": definition.observation_lane,
            "publication_route": definition.publication_route,
            "applicable": False,
            "instances": [],
        }
        validate_m2_runtime_output(definition, payload, output)
        checked += 1

    assert checked == 69
