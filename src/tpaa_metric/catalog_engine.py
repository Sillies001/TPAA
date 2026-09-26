"""Catalog-driven general Metric Engine for the frozen M2 foundation batch.

The engine owns ordering, authority binding, operator resolution and algorithm-plugin
dispatch. Business algorithms are supplied as algorithm-id plugins; families are not
separate engines or dispatch namespaces.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol, cast

from tpaa_generated.metric_registry import P1_METRICS
from tpaa_metric.operators import M2_OPERATOR_IMPLEMENTATIONS

M2_DELIVERY_MILESTONE = "M2"
M2_DELIVERY_BATCH = "P1_FOUNDATION_32"
M2_FOUNDATION_COUNT = 32
M2_EXPECTED_FAMILY_COUNTS = MappingProxyType(
    {
        "REFERENCE_TRUTH": 3,
        "TIME_ALIGNMENT": 5,
        "AIRCRAFT_FLIGHT": 3,
        "SENSOR_DETECTION": 4,
        "SENSOR_ACCURACY": 17,
    }
)
M2_DISPATCH_KEY = "algorithm_id"
M2_INPUT_LINEAGE_ENCODING = "TPAA_M2_INPUT_LINEAGE_JSON_V1"
_REFERENCE_MATCH_QUALITY_PROFILE_CONTRACT = "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1"
_REFERENCE_MATCH_QUALITY_PROFILE_IDENTITY_FIELDS = (
    "reference_match_quality_profile_id",
    "reference_match_quality_profile_version",
    "reference_match_quality_profile_hash",
)


class CatalogMetricEngineError(RuntimeError):
    """Deterministic fail-closed Catalog Metric Engine error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ApplicabilityContract:
    key: str
    subject_type: str
    applicability_mode: str
    allowed_system_types: tuple[str, ...]
    required_product_semantics: str | None


@dataclass(frozen=True)
class InputAuthorityBinding:
    metric_semantic_id: str
    input_field: str
    optional: bool
    binding_kind: str
    authority_id: str
    authority_field: str
    normalization_rule: str


@dataclass(frozen=True)
class M2MetricDefinition:
    catalog_index: int
    metric_code: str
    name: str
    semantic_id: str
    semantic_version: int
    family: str
    subject_type: str
    unit: str
    value_kind: str
    algorithm_id: str
    algorithm_version: str
    observation_lane: str
    publication_route: str
    p1_longitudinal_trend_eligibility: bool
    default_aggregation: str
    structured_output_schema_id: str | None
    structured_output_schema_json: str | None
    structured_output_schema_hash_sha256: str | None
    input_fields: tuple[str, ...]
    formula: str
    validity_conditions: str
    na_conditions: str
    profile_parameters: tuple[str, ...]
    operator_bindings: tuple[str, ...]
    constant_bindings: tuple[str, ...]
    upstream_dependencies: tuple[str, ...]
    metric_dependencies: tuple[str, ...]
    external_dependencies: tuple[str, ...]
    state_machine_bindings: tuple[str, ...]
    input_authority_bindings: tuple[InputAuthorityBinding, ...]
    allowed_result_statuses: tuple[str, ...]
    allowed_mission_system_types: tuple[str, ...]
    applicability: ApplicabilityContract
    formula_dependency_references: tuple[tuple[str, str], ...]
    definition_hash: str
    authority_lineage_hash: str


@dataclass(frozen=True)
class M2MetricExecutionPlan:
    catalog_id: str
    catalog_version: str
    catalog_sha256: str
    input_authority_matrix_sha256: str
    source_provenance_sha256: str
    world_capability_registry_sha256: str
    core_logical_model_sha256: str
    core_rules_sha256: str
    operator_registry_sha256: str
    constant_registry_sha256: str
    state_machine_registry_sha256: str
    upstream_contract_registry_sha256: str
    structured_output_schema_registry_sha256: str
    family_applicability_contracts_sha256: str
    execution_identity_sha256: str
    input_lineage_encoding: str
    allowed_result_statuses: tuple[str, ...]
    allowed_mission_system_types: tuple[str, ...]
    db_schema_version: str
    delivery_milestone: str
    delivery_batch: str
    catalog_metric_codes: tuple[str, ...]
    definitions: tuple[M2MetricDefinition, ...]
    required_operator_ids: tuple[str, ...]
    required_state_machine_ids: tuple[str, ...]
    required_external_dependency_ids: tuple[str, ...]
    logical_hash: str

    @property
    def metric_codes(self) -> tuple[str, ...]:
        return tuple(item.metric_code for item in self.definitions)

    def definition(self, metric_code: str) -> M2MetricDefinition:
        for definition in self.definitions:
            if definition.metric_code == metric_code:
                return definition
        raise CatalogMetricEngineError("M2_METRIC_DEFINITION_MISSING", metric_code)


@dataclass(frozen=True)
class M2MetricPluginRequest:
    definition: M2MetricDefinition
    input_payload: Mapping[str, object]
    upstream_result_hashes: tuple[tuple[str, str], ...]
    operators: Mapping[str, Callable[..., object]]


class M2MetricPlugin(Protocol):
    def __call__(self, request: M2MetricPluginRequest) -> Mapping[str, object]:
        """Execute one Catalog algorithm and return a JSON-compatible logical result."""


@dataclass(frozen=True)
class M2MetricExecutionRecord:
    metric_code: str
    semantic_id: str
    semantic_version: int
    algorithm_id: str
    algorithm_version: str
    definition_hash: str
    authority_lineage_hash: str
    input_lineage_encoding: str
    input_payload_hash: str
    plugin_id: str
    operator_bindings: tuple[str, ...]
    upstream_result_hashes: tuple[tuple[str, str], ...]
    plugin_output_hash: str
    logical_hash: str


@dataclass(frozen=True)
class M2MetricExecutionBatch:
    plan_hash: str
    dispatch_key: str
    plugin_manifest_hash: str
    records: tuple[M2MetricExecutionRecord, ...]
    logical_hash: str

    @property
    def metric_codes(self) -> tuple[str, ...]:
        return tuple(item.metric_code for item in self.records)


class MetricPluginRegistry:
    """Algorithm-id plugin registry shared by every Metric family."""

    def __init__(self) -> None:
        self._plugins: dict[tuple[str, str | None], tuple[str, M2MetricPlugin]] = {}

    def register(
        self,
        algorithm_id: str,
        *,
        algorithm_version: str | None = None,
        plugin_id: str,
        plugin: M2MetricPlugin,
    ) -> None:
        if (
            not algorithm_id
            or not plugin_id
            or (algorithm_version is not None and not algorithm_version)
        ):
            raise CatalogMetricEngineError(
                "M2_METRIC_PLUGIN_ID_INVALID",
                repr((algorithm_id, algorithm_version, plugin_id)),
            )
        identity = (algorithm_id, algorithm_version)
        if identity in self._plugins:
            raise CatalogMetricEngineError(
                "M2_METRIC_PLUGIN_DUPLICATE",
                f"{algorithm_id}@{algorithm_version or 'UNVERSIONED'}",
            )
        self._plugins[identity] = (plugin_id, plugin)

    def resolve(
        self,
        algorithm_id: str,
        algorithm_version: str | None = None,
    ) -> tuple[str, M2MetricPlugin]:
        if algorithm_version is not None:
            exact = self._plugins.get((algorithm_id, algorithm_version))
            if exact is not None:
                return exact
            registered_versions = tuple(
                sorted(
                    "UNVERSIONED" if version is None else version
                    for registered_id, version in self._plugins
                    if registered_id == algorithm_id
                )
            )
            if registered_versions:
                code = (
                    "M2_METRIC_PLUGIN_VERSION_UNBOUND"
                    if "UNVERSIONED" in registered_versions
                    else "M2_METRIC_PLUGIN_VERSION_MISMATCH"
                )
                raise CatalogMetricEngineError(
                    code,
                    f"{algorithm_id}@{algorithm_version}:registered={registered_versions!r}",
                )
            raise CatalogMetricEngineError(
                "M2_METRIC_PLUGIN_MISSING",
                f"{algorithm_id}@{algorithm_version}",
            )

        matches = tuple(
            value
            for (registered_id, _version), value in self._plugins.items()
            if registered_id == algorithm_id
        )
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise CatalogMetricEngineError(
                "M2_METRIC_PLUGIN_VERSION_AMBIGUOUS",
                algorithm_id,
            )
        raise CatalogMetricEngineError("M2_METRIC_PLUGIN_MISSING", algorithm_id)

    @property
    def plugin_ids(self) -> Mapping[str, str]:
        result: dict[str, str] = {}
        for (algorithm_id, _version), value in self._plugins.items():
            if algorithm_id in result:
                raise CatalogMetricEngineError(
                    "M2_METRIC_PLUGIN_VERSION_AMBIGUOUS",
                    algorithm_id,
                )
            result[algorithm_id] = value[0]
        return MappingProxyType(result)

    @property
    def plugin_identity_manifest(self) -> tuple[tuple[str, str, str], ...]:
        return tuple(
            sorted(
                (
                    algorithm_id,
                    version if version is not None else "UNVERSIONED",
                    value[0],
                )
                for (algorithm_id, version), value in self._plugins.items()
            )
        )


class CatalogMetricEngine:
    """One Catalog-driven execution engine with algorithm-id plugin dispatch."""

    dispatch_key = M2_DISPATCH_KEY

    def __init__(
        self,
        plan: M2MetricExecutionPlan,
        plugins: MetricPluginRegistry,
    ) -> None:
        self.plan = plan
        self.plugins = plugins

    def _execution_definitions(
        self,
        metric_codes: Sequence[str] | None,
    ) -> tuple[M2MetricDefinition, ...]:
        if metric_codes is None:
            return self.plan.definitions

        requested = set(metric_codes)
        if len(requested) != len(metric_codes):
            raise CatalogMetricEngineError(
                "M2_METRIC_REQUEST_DUPLICATE",
                repr(tuple(metric_codes)),
            )
        unknown = requested - set(self.plan.metric_codes)
        if unknown:
            raise CatalogMetricEngineError(
                "M2_METRIC_REQUEST_UNKNOWN",
                repr(sorted(unknown)),
            )

        closure = set(requested)
        changed = True
        while changed:
            changed = False
            for definition in self.plan.definitions:
                if definition.metric_code not in closure:
                    continue
                for dependency in definition.metric_dependencies:
                    if dependency not in closure:
                        closure.add(dependency)
                        changed = True
        return tuple(
            definition
            for definition in self.plan.definitions
            if definition.metric_code in closure
        )

    def execute(
        self,
        inputs: Mapping[str, Mapping[str, object]],
        *,
        metric_codes: Sequence[str] | None = None,
        validate_runtime_contract: bool = True,
    ) -> M2MetricExecutionBatch:
        definitions = self._execution_definitions(metric_codes)
        records: list[M2MetricExecutionRecord] = []
        result_hashes: dict[str, str] = {}
        plugin_manifest: list[tuple[str, str, str]] = []

        for definition in definitions:
            input_payload = inputs.get(definition.metric_code)
            if input_payload is None:
                raise CatalogMetricEngineError(
                    "M2_METRIC_INPUT_PAYLOAD_MISSING",
                    definition.metric_code,
                )
            plugin_id, plugin = self.plugins.resolve(
                definition.algorithm_id,
                definition.algorithm_version,
            )
            plugin_manifest.append(
                (definition.algorithm_id, definition.algorithm_version, plugin_id)
            )
            input_payload_hash = _sha256_input_payload(input_payload)
            upstream_hashes = tuple(
                (dependency, result_hashes[dependency])
                for dependency in definition.metric_dependencies
            )
            operators = MappingProxyType(
                {
                    operator_id: M2_OPERATOR_IMPLEMENTATIONS[operator_id]
                    for operator_id in definition.operator_bindings
                }
            )
            request = M2MetricPluginRequest(
                definition=definition,
                input_payload=input_payload,
                upstream_result_hashes=upstream_hashes,
                operators=operators,
            )
            try:
                output = dict(plugin(request))
            except (TypeError, ValueError, OverflowError) as exc:
                raise CatalogMetricEngineError(
                    "M2_METRIC_PLUGIN_OUTPUT_INVALID",
                    f"{definition.metric_code}: {exc}",
                ) from exc
            if validate_runtime_contract:
                validate_m2_runtime_output(
                    definition,
                    input_payload,
                    output,
                )
            output_hash = _sha256_object(output)

            logical_hash = _sha256_object(
                {
                    "metric_code": definition.metric_code,
                    "semantic_id": definition.semantic_id,
                    "semantic_version": definition.semantic_version,
                    "definition_hash": definition.definition_hash,
                    "authority_lineage_hash": definition.authority_lineage_hash,
                    "input_lineage_encoding": M2_INPUT_LINEAGE_ENCODING,
                    "input_payload_hash": input_payload_hash,
                    "algorithm_id": definition.algorithm_id,
                    "algorithm_version": definition.algorithm_version,
                    "plugin_id": plugin_id,
                    "operator_bindings": definition.operator_bindings,
                    "upstream_result_hashes": upstream_hashes,
                    "plugin_output_hash": output_hash,
                }
            )
            record = M2MetricExecutionRecord(
                metric_code=definition.metric_code,
                semantic_id=definition.semantic_id,
                semantic_version=definition.semantic_version,
                algorithm_id=definition.algorithm_id,
                algorithm_version=definition.algorithm_version,
                definition_hash=definition.definition_hash,
                authority_lineage_hash=definition.authority_lineage_hash,
                input_lineage_encoding=M2_INPUT_LINEAGE_ENCODING,
                input_payload_hash=input_payload_hash,
                plugin_id=plugin_id,
                operator_bindings=definition.operator_bindings,
                upstream_result_hashes=upstream_hashes,
                plugin_output_hash=output_hash,
                logical_hash=logical_hash,
            )
            records.append(record)
            result_hashes[definition.metric_code] = logical_hash

        plugin_manifest_hash = _sha256_object(plugin_manifest)
        batch_hash = _sha256_object(
            {
                "plan_hash": self.plan.logical_hash,
                "dispatch_key": self.dispatch_key,
                "plugin_manifest_hash": plugin_manifest_hash,
                "record_hashes": [record.logical_hash for record in records],
            }
        )
        return M2MetricExecutionBatch(
            plan_hash=self.plan.logical_hash,
            dispatch_key=self.dispatch_key,
            plugin_manifest_hash=plugin_manifest_hash,
            records=tuple(records),
            logical_hash=batch_hash,
        )


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, OverflowError) as exc:
        raise CatalogMetricEngineError(
            "M2_METRIC_CANONICALIZATION_FAILED",
            str(exc),
        ) from exc


def _sha256_object(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _lineage_json_value(value: object, *, field: str) -> object:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise CatalogMetricEngineError(
                "M2_METRIC_INPUT_LINEAGE_UNSUPPORTED",
                f"{field}: mapping keys must be strings",
            )
        return {
            cast(str, key): _lineage_json_value(item, field=f"{field}.{key}")
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            _lineage_json_value(item, field=f"{field}[{index}]")
            for index, item in enumerate(value)
        ]
    if is_dataclass(value) and not isinstance(value, type):
        dataclass_type = type(value)
        return {
            "$dataclass": (
                f"{dataclass_type.__module__}.{dataclass_type.__qualname__}"
            ),
            "fields": {
                item.name: _lineage_json_value(
                    getattr(value, item.name),
                    field=f"{field}.{item.name}",
                )
                for item in fields(cast(Any, value))
            },
        }
    raise CatalogMetricEngineError(
        "M2_METRIC_INPUT_LINEAGE_UNSUPPORTED",
        f"{field}: {type(value).__module__}.{type(value).__qualname__}",
    )


def _sha256_input_payload(value: Mapping[str, object]) -> str:
    return _sha256_object(_lineage_json_value(value, field="input_payload"))


_SUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "$schema",
        "$id",
        "type",
        "additionalProperties",
        "required",
        "properties",
        "items",
        "minItems",
        "maxItems",
        "enum",
        "minimum",
        "pattern",
    }
)
_SUPPORTED_JSON_TYPES = frozenset(
    {"object", "array", "number", "integer", "string", "boolean", "null"}
)


def _canonical_schema_json(value: Mapping[str, object]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _schema_type_names(schema: Mapping[str, object], *, field: str) -> tuple[str, ...]:
    raw = schema.get("type")
    names: tuple[str, ...]
    if isinstance(raw, str):
        names = (raw,)
    elif isinstance(raw, list) and raw and all(isinstance(item, str) for item in raw):
        names = tuple(cast(list[str], raw))
    else:
        raise CatalogMetricEngineError(
            "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED",
            f"{field}.type",
        )
    if not set(names).issubset(_SUPPORTED_JSON_TYPES):
        raise CatalogMetricEngineError(
            "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED",
            f"{field}.type={names!r}",
        )
    return names


def _validate_schema_definition(schema: Mapping[str, object], *, field: str) -> None:
    unsupported = set(schema) - _SUPPORTED_SCHEMA_KEYS
    if unsupported:
        raise CatalogMetricEngineError(
            "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED",
            f"{field}: {sorted(unsupported)!r}",
        )
    _schema_type_names(schema, field=field)
    required = schema.get("required")
    if required is not None and (
        not isinstance(required, list)
        or not all(isinstance(item, str) for item in required)
        or len(set(required)) != len(required)
    ):
        raise CatalogMetricEngineError(
            "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED",
            f"{field}.required",
        )
    additional = schema.get("additionalProperties")
    if additional is not None and not isinstance(additional, bool):
        raise CatalogMetricEngineError(
            "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED",
            f"{field}.additionalProperties",
        )
    type_names = _schema_type_names(schema, field=field)
    properties = schema.get("properties")
    if "object" in type_names:
        if additional is not False:
            raise CatalogMetricEngineError(
                "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED",
                f"{field}.additionalProperties must be false",
            )
        if not isinstance(properties, dict) or not all(
            isinstance(key, str) and isinstance(value, dict)
            for key, value in properties.items()
        ):
            raise CatalogMetricEngineError(
                "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED",
                f"{field}.properties",
            )
        if isinstance(required, list) and not set(required).issubset(properties):
            raise CatalogMetricEngineError(
                "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED",
                f"{field}.required outside properties",
            )
    if properties is not None:
        if not isinstance(properties, dict) or not all(
            isinstance(key, str) and isinstance(value, dict)
            for key, value in properties.items()
        ):
            raise CatalogMetricEngineError(
                "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED",
                f"{field}.properties",
            )
        for name, nested in properties.items():
            _validate_schema_definition(
                cast(dict[str, object], nested),
                field=f"{field}.properties.{name}",
            )
    items = schema.get("items")
    if items is not None:
        if not isinstance(items, dict):
            raise CatalogMetricEngineError(
                "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED",
                f"{field}.items",
            )
        _validate_schema_definition(
            cast(dict[str, object], items),
            field=f"{field}.items",
        )
    for name in ("minItems", "maxItems"):
        raw = schema.get(name)
        if raw is not None and (
            isinstance(raw, bool) or not isinstance(raw, int) or raw < 0
        ):
            raise CatalogMetricEngineError(
                "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED",
                f"{field}.{name}",
            )
    minimum = schema.get("minimum")
    if minimum is not None and (
        isinstance(minimum, bool) or not isinstance(minimum, (int, float))
    ):
        raise CatalogMetricEngineError(
            "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED",
            f"{field}.minimum",
        )
    enum = schema.get("enum")
    if enum is not None and not isinstance(enum, list):
        raise CatalogMetricEngineError(
            "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED",
            f"{field}.enum",
        )
    pattern = schema.get("pattern")
    if pattern is not None:
        if not isinstance(pattern, str):
            raise CatalogMetricEngineError(
                "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED",
                f"{field}.pattern",
            )
        try:
            re.compile(pattern)
        except re.error as exc:
            raise CatalogMetricEngineError(
                "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED",
                f"{field}.pattern",
            ) from exc


def _compile_structured_output_schema(
    schema_registry: Mapping[str, object],
    *,
    metric_code: str,
    schema_id: str,
) -> tuple[str, str]:
    entry = _object(
        schema_registry.get(schema_id),
        field=f"structured_output_schema_registry.{schema_id}",
    )
    if _text(entry, "metric_code", field=schema_id) != metric_code:
        raise CatalogMetricEngineError(
            "M2_METRIC_STRUCTURED_SCHEMA_METRIC_DRIFT",
            f"{metric_code}:{schema_id}",
        )
    dialect = _text(entry, "json_schema_dialect", field=schema_id)
    if dialect != "https://json-schema.org/draft/2020-12/schema":
        raise CatalogMetricEngineError(
            "M2_METRIC_STRUCTURED_SCHEMA_DIALECT_DRIFT",
            f"{schema_id}:{dialect}",
        )
    schema = _object(entry.get("json_schema"), field=f"{schema_id}.json_schema")
    _validate_schema_definition(schema, field=schema_id)
    canonical = _canonical_schema_json(schema)
    computed_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    authority_hash = _text(entry, "schema_hash_sha256", field=schema_id)
    if computed_hash != authority_hash:
        raise CatalogMetricEngineError(
            "M2_METRIC_STRUCTURED_SCHEMA_HASH_DRIFT",
            schema_id,
        )
    return canonical, authority_hash


def _json_type_matches(value: object, type_name: str) -> bool:
    if type_name == "null":
        return value is None
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        )
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "array":
        return isinstance(value, Sequence) and not isinstance(value, (str, bytes))
    if type_name == "object":
        return isinstance(value, Mapping) and all(
            isinstance(key, str) for key in value
        )
    return False


def _validate_json_value(
    value: object,
    schema: Mapping[str, object],
    *,
    metric_code: str,
    field: str,
) -> None:
    type_names = _schema_type_names(schema, field=field)
    if not any(_json_type_matches(value, name) for name in type_names):
        raise CatalogMetricEngineError(
            "M2_METRIC_STRUCTURED_OUTPUT_SCHEMA_VIOLATION",
            f"{metric_code}:{field}:type",
        )
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        raise CatalogMetricEngineError(
            "M2_METRIC_STRUCTURED_OUTPUT_SCHEMA_VIOLATION",
            f"{metric_code}:{field}:enum",
        )
    if isinstance(value, Mapping):
        required = schema.get("required", [])
        if isinstance(required, list):
            missing = [name for name in required if name not in value]
            if missing:
                raise CatalogMetricEngineError(
                    "M2_METRIC_STRUCTURED_OUTPUT_SCHEMA_VIOLATION",
                    f"{metric_code}:{field}:missing={missing!r}",
                )
        properties_raw = schema.get("properties", {})
        properties = (
            cast(dict[str, object], properties_raw)
            if isinstance(properties_raw, dict)
            else {}
        )
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise CatalogMetricEngineError(
                    "M2_METRIC_STRUCTURED_OUTPUT_SCHEMA_VIOLATION",
                    f"{metric_code}:{field}:extra={extra!r}",
                )
        for name, item in value.items():
            nested = properties.get(name)
            if nested is not None:
                if not isinstance(nested, dict):
                    raise CatalogMetricEngineError(
                        "M2_METRIC_STRUCTURED_SCHEMA_UNSUPPORTED",
                        f"{field}.properties.{name}",
                    )
                _validate_json_value(
                    item,
                    cast(dict[str, object], nested),
                    metric_code=metric_code,
                    field=f"{field}.{name}",
                )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if isinstance(min_items, int) and len(value) < min_items:
            raise CatalogMetricEngineError(
                "M2_METRIC_STRUCTURED_OUTPUT_SCHEMA_VIOLATION",
                f"{metric_code}:{field}:minItems",
            )
        if isinstance(max_items, int) and len(value) > max_items:
            raise CatalogMetricEngineError(
                "M2_METRIC_STRUCTURED_OUTPUT_SCHEMA_VIOLATION",
                f"{metric_code}:{field}:maxItems",
            )
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                _validate_json_value(
                    item,
                    cast(dict[str, object], items),
                    metric_code=metric_code,
                    field=f"{field}[{index}]",
                )
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            raise CatalogMetricEngineError(
                "M2_METRIC_STRUCTURED_OUTPUT_SCHEMA_VIOLATION",
                f"{metric_code}:{field}:minimum",
            )
    if isinstance(value, str):
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            raise CatalogMetricEngineError(
                "M2_METRIC_STRUCTURED_OUTPUT_SCHEMA_VIOLATION",
                f"{metric_code}:{field}:pattern",
            )


def validate_m2_runtime_output(
    definition: M2MetricDefinition,
    input_payload: Mapping[str, object],
    output: Mapping[str, object],
) -> None:
    """Enforce frozen applicability, value-slot and structured-schema contracts."""

    if not all(isinstance(key, str) for key in output):
        raise CatalogMetricEngineError(
            "M2_METRIC_RUNTIME_OUTPUT_SHAPE_INVALID",
            f"{definition.metric_code}:root keys",
        )
    if output.get("metric_code") != definition.metric_code:
        raise CatalogMetricEngineError(
            "M2_METRIC_RUNTIME_METRIC_CODE_MISMATCH",
            definition.metric_code,
        )
    if output.get("subject_type") != definition.subject_type:
        raise CatalogMetricEngineError(
            "M2_METRIC_RUNTIME_SUBJECT_TYPE_MISMATCH",
            (
                f"{definition.metric_code}:"
                f"{output.get('subject_type')!r}->{definition.subject_type}"
            ),
        )
    if output.get("observation_lane") != definition.observation_lane:
        raise CatalogMetricEngineError(
            "M2_METRIC_RUNTIME_OBSERVATION_LANE_MISMATCH",
            (
                f"{definition.metric_code}:"
                f"{output.get('observation_lane')!r}->{definition.observation_lane}"
            ),
        )
    if output.get("publication_route") != definition.publication_route:
        raise CatalogMetricEngineError(
            "M2_METRIC_RUNTIME_PUBLICATION_ROUTE_MISMATCH",
            (
                f"{definition.metric_code}:"
                f"{output.get('publication_route')!r}->{definition.publication_route}"
            ),
        )

    applicability = definition.applicability
    if applicability.applicability_mode == "SYSTEM_TYPE_EXACT":
        system_type = input_payload.get("system_type")
        if (
            not isinstance(system_type, str)
            or system_type not in definition.allowed_mission_system_types
        ):
            raise CatalogMetricEngineError(
                "M2_METRIC_APPLICABILITY_INPUT_INVALID",
                f"{definition.metric_code}:{system_type!r}",
            )
        runtime_applicable = system_type in applicability.allowed_system_types
        if not runtime_applicable:
            if output.get("applicable") is not False or output.get("instances") != []:
                raise CatalogMetricEngineError(
                    "M2_METRIC_NOT_APPLICABLE_OUTPUT_INVALID",
                    f"{definition.metric_code}:{system_type}",
                )
            return
        if output.get("applicable") is not True:
            raise CatalogMetricEngineError(
                "M2_METRIC_APPLICABLE_OUTPUT_REJECTED",
                f"{definition.metric_code}:{system_type}",
            )
    elif applicability.applicability_mode not in {
        "SUBJECT_TYPE",
        "QUALITY_FOUNDATION",
    }:
        raise CatalogMetricEngineError(
            "M2_METRIC_APPLICABILITY_MODE_UNSUPPORTED",
            f"{definition.metric_code}:{applicability.applicability_mode}",
        )

    raw_instances = output.get("instances")
    if raw_instances is None:
        if "status" not in output or "value_kind" not in output:
            raise CatalogMetricEngineError(
                "M2_METRIC_RUNTIME_OUTPUT_SHAPE_INVALID",
                definition.metric_code,
            )
        instances: tuple[Mapping[str, object], ...] = (output,)
    else:
        if not isinstance(raw_instances, list):
            raise CatalogMetricEngineError(
                "M2_METRIC_RUNTIME_OUTPUT_SHAPE_INVALID",
                f"{definition.metric_code}:instances",
            )
        normalized: list[Mapping[str, object]] = []
        for index, item in enumerate(raw_instances):
            if not isinstance(item, Mapping) or not all(
                isinstance(key, str) for key in item
            ):
                raise CatalogMetricEngineError(
                    "M2_METRIC_RUNTIME_OUTPUT_SHAPE_INVALID",
                    f"{definition.metric_code}:instances[{index}]",
                )
            normalized.append(cast(Mapping[str, object], item))
        instances = tuple(normalized)

    schema: Mapping[str, object] | None = None
    if definition.value_kind == "STRUCTURED":
        if definition.structured_output_schema_json is None:
            raise CatalogMetricEngineError(
                "M2_METRIC_STRUCTURED_SCHEMA_MISSING",
                definition.metric_code,
            )
        parsed: object = json.loads(definition.structured_output_schema_json)
        if not isinstance(parsed, dict):
            raise CatalogMetricEngineError(
                "M2_METRIC_STRUCTURED_SCHEMA_MISSING",
                definition.metric_code,
            )
        schema = cast(dict[str, object], parsed)

    for index, instance in enumerate(instances):
        value_kind = instance.get("value_kind")
        if value_kind != definition.value_kind:
            raise CatalogMetricEngineError(
                "M2_METRIC_RUNTIME_VALUE_KIND_MISMATCH",
                f"{definition.metric_code}:instances[{index}]",
            )
        status = instance.get("status")
        if (
            not isinstance(status, str)
            or status not in definition.allowed_result_statuses
        ):
            raise CatalogMetricEngineError(
                "M2_METRIC_RUNTIME_STATUS_INVALID",
                f"{definition.metric_code}:instances[{index}]:{status!r}",
            )
        reason_codes = instance.get("reason_codes")
        if (
            not isinstance(reason_codes, list)
            or not all(isinstance(item, str) and item for item in reason_codes)
        ):
            raise CatalogMetricEngineError(
                "M2_METRIC_RUNTIME_REASON_CODES_INVALID",
                f"{definition.metric_code}:instances[{index}]",
            )
        if status in {"N_A", "INSUFFICIENT_DATA"} and not reason_codes:
            raise CatalogMetricEngineError(
                "M2_METRIC_RUNTIME_REASON_CODE_REQUIRED",
                f"{definition.metric_code}:instances[{index}]:{status}",
            )
        for other_slot in ("value_text", "value_boolean"):
            if instance.get(other_slot) is not None:
                raise CatalogMetricEngineError(
                    "M2_METRIC_RUNTIME_VALUE_SLOT_MISMATCH",
                    f"{definition.metric_code}:instances[{index}].{other_slot}",
                )
        numeric = instance.get("value_numeric")
        structured = instance.get("value_structured")
        if definition.value_kind == "NUMERIC":
            if structured is not None:
                raise CatalogMetricEngineError(
                    "M2_METRIC_RUNTIME_VALUE_SLOT_MISMATCH",
                    f"{definition.metric_code}:instances[{index}].value_structured",
                )
            if numeric is not None and not _json_type_matches(numeric, "number"):
                raise CatalogMetricEngineError(
                    "M2_METRIC_RUNTIME_NUMERIC_INVALID",
                    f"{definition.metric_code}:instances[{index}]",
                )
            if status == "VALID" and numeric is None:
                raise CatalogMetricEngineError(
                    "M2_METRIC_RUNTIME_VALID_VALUE_MISSING",
                    f"{definition.metric_code}:instances[{index}]",
                )
        elif definition.value_kind == "STRUCTURED":
            if numeric is not None:
                raise CatalogMetricEngineError(
                    "M2_METRIC_RUNTIME_VALUE_SLOT_MISMATCH",
                    f"{definition.metric_code}:instances[{index}].value_numeric",
                )
            if structured is not None:
                if schema is None:
                    raise CatalogMetricEngineError(
                        "M2_METRIC_STRUCTURED_SCHEMA_MISSING",
                        definition.metric_code,
                    )
                _validate_json_value(
                    structured,
                    schema,
                    metric_code=definition.metric_code,
                    field=f"instances[{index}].value_structured",
                )
            if status == "VALID" and structured is None:
                raise CatalogMetricEngineError(
                    "M2_METRIC_RUNTIME_VALID_VALUE_MISSING",
                    f"{definition.metric_code}:instances[{index}]",
                )
        else:
            raise CatalogMetricEngineError(
                "M2_METRIC_VALUE_KIND_UNSUPPORTED",
                f"{definition.metric_code}:{definition.value_kind}",
            )


def _load_object(path: Path) -> tuple[dict[str, object], bytes]:
    try:
        raw_bytes = path.read_bytes()
        raw: object = json.loads(raw_bytes)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CatalogMetricEngineError(
            "M2_METRIC_CATALOG_INVALID",
            path.as_posix(),
        ) from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise CatalogMetricEngineError(
            "M2_METRIC_CATALOG_INVALID",
            "root must be string-keyed object",
        )
    return cast(dict[str, object], raw), raw_bytes


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise CatalogMetricEngineError(
            "M2_METRIC_CATALOG_SHAPE_INVALID",
            f"{field} must be string-keyed object",
        )
    return cast(dict[str, object], value)


def _objects(value: object, *, field: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise CatalogMetricEngineError(
            "M2_METRIC_CATALOG_SHAPE_INVALID",
            f"{field} must be list",
        )
    result: list[dict[str, object]] = []
    for index, item in enumerate(value):
        result.append(_object(item, field=f"{field}[{index}]"))
    return result


def _text(mapping: Mapping[str, object], name: str, *, field: str) -> str:
    value = mapping.get(name)
    if not isinstance(value, str) or not value:
        raise CatalogMetricEngineError(
            "M2_METRIC_CATALOG_FIELD_INVALID",
            f"{field}.{name}",
        )
    return value


def _integer(mapping: Mapping[str, object], name: str, *, field: str) -> int:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise CatalogMetricEngineError(
            "M2_METRIC_CATALOG_FIELD_INVALID",
            f"{field}.{name}",
        )
    return value


def _string_list(mapping: Mapping[str, object], name: str, *, field: str) -> tuple[str, ...]:
    value = mapping.get(name)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise CatalogMetricEngineError(
            "M2_METRIC_CATALOG_FIELD_INVALID",
            f"{field}.{name}",
        )
    return tuple(cast(list[str], value))


def _formula_mentions_identifier(formula: str, identifier: str) -> bool:
    return (
        re.search(
            rf"(?<![A-Za-z0-9_.-]){re.escape(identifier)}(?![A-Za-z0-9_.-])",
            formula,
        )
        is not None
    )


def _validate_governed_formula_dependency_closure(
    *,
    metric_code: str,
    formula: str,
    operator_bindings: tuple[str, ...],
    constant_bindings: tuple[str, ...],
    upstream_dependencies: tuple[str, ...],
    state_machine_bindings: tuple[str, ...],
    operator_registry: Mapping[str, object],
    constant_registry: Mapping[str, object],
    upstream_registry: Mapping[str, object],
    state_machine_registry: Mapping[str, object],
    selected_metric_codes: set[str],
) -> tuple[tuple[str, str], ...]:
    declared = {
        "OPERATOR": operator_bindings,
        "CONSTANT": constant_bindings,
        "UPSTREAM_CONTRACT": upstream_dependencies,
        "STATE_MACHINE": state_machine_bindings,
    }
    for kind, identifiers in declared.items():
        if len(identifiers) != len(set(identifiers)):
            raise CatalogMetricEngineError(
                "M2_METRIC_DEPENDENCY_BINDING_DUPLICATE",
                f"{metric_code}:{kind}:{identifiers!r}",
            )

    references: list[tuple[str, str]] = []
    governed_namespaces = (
        ("OPERATOR", operator_registry, set(operator_bindings)),
        ("CONSTANT", constant_registry, set(constant_bindings)),
        ("UPSTREAM_CONTRACT", upstream_registry, set(upstream_dependencies)),
        ("STATE_MACHINE", state_machine_registry, set(state_machine_bindings)),
    )
    for kind, registry, bindings in governed_namespaces:
        for identifier in registry:
            if not _formula_mentions_identifier(formula, identifier):
                continue
            references.append((kind, identifier))
            if identifier not in bindings:
                raise CatalogMetricEngineError(
                    "M2_METRIC_FORMULA_DEPENDENCY_UNBOUND",
                    f"{metric_code}:{kind}:{identifier}",
                )

    upstream_binding_set = set(upstream_dependencies)
    for dependency in selected_metric_codes:
        if dependency == metric_code or not _formula_mentions_identifier(
            formula,
            dependency,
        ):
            continue
        references.append(("METRIC", dependency))
        if dependency not in upstream_binding_set:
            raise CatalogMetricEngineError(
                "M2_METRIC_FORMULA_DEPENDENCY_UNBOUND",
                f"{metric_code}:METRIC:{dependency}",
            )

    return tuple(sorted(references))


def _validate_versioned_registry_entry(
    registry: Mapping[str, object],
    entry_id: str,
    *,
    field: str,
) -> None:
    entry = _object(registry.get(entry_id), field=f"{field}.{entry_id}")
    _text(entry, "version", field=f"{field}.{entry_id}")
    _text(entry, "definition", field=f"{field}.{entry_id}")


def _optional_text(mapping: Mapping[str, object], name: str, *, field: str) -> str | None:
    value = mapping.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise CatalogMetricEngineError(
            "M2_METRIC_CATALOG_FIELD_INVALID",
            f"{field}.{name}",
        )
    return value


def _applicability_key(metric_code: str) -> str:
    parts = metric_code.split("-")
    if len(parts) != 3 or parts[0] != "P1":
        raise CatalogMetricEngineError("M2_METRIC_CODE_INVALID", metric_code)
    return f"{parts[0]}-{parts[1]}-*"


def _applicability(
    definition: Mapping[str, object],
    family_contracts: Mapping[str, object],
) -> ApplicabilityContract:
    metric_code = _text(definition, "metric_code", field="metric")
    key = _applicability_key(metric_code)
    contract = _object(family_contracts.get(key), field=f"family_applicability_contracts.{key}")
    allowed_raw = contract.get("allowed_system_types", [])
    if not isinstance(allowed_raw, list) or not all(
        isinstance(item, str) for item in allowed_raw
    ):
        raise CatalogMetricEngineError(
            "M2_METRIC_APPLICABILITY_INVALID",
            f"{key}.allowed_system_types",
        )
    result = ApplicabilityContract(
        key=key,
        subject_type=_text(contract, "subject_type", field=key),
        applicability_mode=_text(contract, "applicability_mode", field=key),
        allowed_system_types=tuple(cast(list[str], allowed_raw)),
        required_product_semantics=_optional_text(
            contract,
            "required_product_semantics",
            field=key,
        ),
    )
    subject_type = _text(definition, "subject_type", field=metric_code)
    if result.subject_type != "MIXED" and result.subject_type != subject_type:
        raise CatalogMetricEngineError(
            "M2_METRIC_APPLICABILITY_SUBJECT_DRIFT",
            metric_code,
        )
    if key == "P1-SNS-*" and (
        result.applicability_mode != "SYSTEM_TYPE_EXACT"
        or result.allowed_system_types != ("RADAR",)
    ):
        raise CatalogMetricEngineError(
            "M2_METRIC_SNS_APPLICABILITY_DRIFT",
            repr(result),
        )
    return result


def _input_binding_provenance_hash(authority_root: Path) -> str:
    path = authority_root / "SOURCE_PROVENANCE.json"
    provenance, raw_bytes = _load_object(path)
    if (
        _text(provenance, "provenance_id", field="source_provenance")
        != "R39_TO_REBASELINE_R3_3_METRIC_DESIGN_GUIDE"
    ):
        raise CatalogMetricEngineError(
            "M2_METRIC_INPUT_AUTHORITY_PROVENANCE_DRIFT",
            "provenance_id",
        )
    expected_note = (
        "R3.3 adds a complete 116-metric design-intent/interpretation guide and "
        "explicit metric-family applicability contracts. Metric codes, semantic IDs, "
        "algorithms, formulas, input_fields and the 661 binding tuples are unchanged."
    )
    if _text(provenance, "migration_note", field="source_provenance") != expected_note:
        raise CatalogMetricEngineError(
            "M2_METRIC_INPUT_AUTHORITY_PROVENANCE_DRIFT",
            "migration_note",
        )

    metric_migration = _object(
        provenance.get("metric_authority_migration"),
        field="source_provenance.metric_authority_migration",
    )
    if (
        _text(
            metric_migration,
            "current_artifact",
            field="source_provenance.metric_authority_migration",
        )
        != "P1_METRIC_CATALOG.json"
    ):
        raise CatalogMetricEngineError(
            "M2_METRIC_INPUT_AUTHORITY_PROVENANCE_DRIFT",
            "metric_authority_migration.current_artifact",
        )

    input_migration = _object(
        provenance.get("input_authority_migration"),
        field="source_provenance.input_authority_migration",
    )
    if (
        _text(
            input_migration,
            "current_artifact",
            field="source_provenance.input_authority_migration",
        )
        != "METRIC_INPUT_AUTHORITY_MATRIX.json"
        or _text(
            input_migration,
            "migration_scope",
            field="source_provenance.input_authority_migration",
        )
        != "Terminology/reference-name normalization only; 661 binding tuples unchanged."
    ):
        raise CatalogMetricEngineError(
            "M2_METRIC_INPUT_AUTHORITY_PROVENANCE_DRIFT",
            "input_authority_migration",
        )
    return hashlib.sha256(raw_bytes).hexdigest()


def _input_authority_by_metric(
    authority_root: Path,
    *,
    catalog_version: str,
    selected_semantic_ids: Mapping[str, str],
) -> tuple[dict[str, tuple[InputAuthorityBinding, ...]], str, str]:
    path = authority_root / "METRIC_INPUT_AUTHORITY_MATRIX.json"
    matrix, raw_bytes = _load_object(path)
    source_provenance_sha256 = _input_binding_provenance_hash(authority_root)
    matrix_catalog_version = _text(
        matrix,
        "catalog_version",
        field="input_authority_matrix",
    )
    if matrix_catalog_version != catalog_version and not source_provenance_sha256:
        raise CatalogMetricEngineError(
            "M2_METRIC_INPUT_AUTHORITY_CATALOG_VERSION_DRIFT",
            f"{matrix_catalog_version}->{catalog_version}",
        )

    contracts = _object(
        matrix.get("authority_contracts"),
        field="input_authority_matrix.authority_contracts",
    )
    bindings = _objects(matrix.get("bindings"), field="input_authority_matrix.bindings")
    selected_codes = set(selected_semantic_ids)
    grouped: dict[str, list[InputAuthorityBinding]] = {code: [] for code in selected_codes}
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(bindings):
        code = _text(raw, "metric_code", field=f"bindings[{index}]")
        if code not in selected_codes:
            continue
        semantic_id = _text(raw, "metric_semantic_id", field=f"bindings[{index}]")
        if semantic_id != selected_semantic_ids[code]:
            raise CatalogMetricEngineError(
                "M2_METRIC_INPUT_AUTHORITY_SEMANTIC_DRIFT",
                f"{code}:{semantic_id}",
            )
        input_field = _text(raw, "input_field", field=f"bindings[{index}]")
        key = (code, input_field)
        if key in seen:
            raise CatalogMetricEngineError(
                "M2_METRIC_INPUT_AUTHORITY_DUPLICATE",
                f"{code}:{input_field}",
            )
        seen.add(key)
        authority_id = _text(raw, "authority_id", field=f"bindings[{index}]")
        if authority_id not in contracts:
            raise CatalogMetricEngineError(
                "M2_METRIC_INPUT_AUTHORITY_MISSING",
                f"{code}:{input_field}:{authority_id}",
            )
        optional = raw.get("optional")
        if not isinstance(optional, bool):
            raise CatalogMetricEngineError(
                "M2_METRIC_INPUT_AUTHORITY_INVALID",
                f"{code}:{input_field}:optional",
            )
        if optional != input_field.endswith("?"):
            raise CatalogMetricEngineError(
                "M2_METRIC_INPUT_AUTHORITY_OPTIONAL_DRIFT",
                f"{code}:{input_field}",
            )
        grouped[code].append(
            InputAuthorityBinding(
                metric_semantic_id=semantic_id,
                input_field=input_field,
                optional=optional,
                binding_kind=_text(raw, "binding_kind", field=f"bindings[{index}]"),
                authority_id=authority_id,
                authority_field=_text(raw, "authority_field", field=f"bindings[{index}]"),
                normalization_rule=_text(
                    raw,
                    "normalization_rule",
                    field=f"bindings[{index}]",
                ),
            )
        )
    return (
        {code: tuple(items) for code, items in grouped.items()},
        hashlib.sha256(raw_bytes).hexdigest(),
        source_provenance_sha256,
    )


def _world_capability_registry_hash(authority_root: Path) -> str:
    path = authority_root / "WORLD_CAPABILITY_REGISTRY.json"
    registry, raw_bytes = _load_object(path)
    if _text(registry, "registry_id", field="world_capability_registry") != "WORLD_CAPABILITY_REGISTRY":
        raise CatalogMetricEngineError(
            "M2_METRIC_WORLD_CAPABILITY_REGISTRY_INVALID",
            "registry_id",
        )
    _object(registry.get("worlds"), field="world_capability_registry.worlds")
    _object(registry.get("capabilities"), field="world_capability_registry.capabilities")
    missing_rules = registry.get("missing_rules")
    if not isinstance(missing_rules, list) or not all(
        isinstance(item, str) and item for item in missing_rules
    ):
        raise CatalogMetricEngineError(
            "M2_METRIC_WORLD_CAPABILITY_REGISTRY_INVALID",
            "missing_rules",
        )
    return hashlib.sha256(raw_bytes).hexdigest()


def _metric_result_status_authority(
    authority_root: Path,
) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    path = authority_root / "CORE_LOGICAL_MODEL.json"
    model, raw_bytes = _load_object(path)
    if _text(model, "authority_id", field="core_logical_model") != "CORE_LOGICAL_MODEL":
        raise CatalogMetricEngineError(
            "M2_METRIC_RESULT_STATUS_AUTHORITY_INVALID",
            "authority_id",
        )
    tables = _object(model.get("tables"), field="core_logical_model.tables")
    metric_instance = _object(
        tables.get("metric.metric_instance"),
        field="core_logical_model.tables.metric.metric_instance",
    )
    fields = _objects(
        metric_instance.get("fields"),
        field="core_logical_model.tables.metric.metric_instance.fields",
    )
    status_fields = [field for field in fields if field.get("name") == "status"]
    if len(status_fields) != 1:
        raise CatalogMetricEngineError(
            "M2_METRIC_RESULT_STATUS_AUTHORITY_INVALID",
            "metric.metric_instance.status cardinality",
        )
    status_field = status_fields[0]
    if (
        _text(status_field, "type", field="metric.metric_instance.status") != "text"
        or status_field.get("nullable") is not False
    ):
        raise CatalogMetricEngineError(
            "M2_METRIC_RESULT_STATUS_AUTHORITY_INVALID",
            "metric.metric_instance.status type/nullability",
        )
    sql = _text(status_field, "sql", field="metric.metric_instance.status")
    match = re.fullmatch(
        r"status text NOT NULL CHECK \(status IN \((?P<values>(?:'[^']+'(?:,'[^']+')*)+)\)\)",
        sql,
    )
    if match is None:
        raise CatalogMetricEngineError(
            "M2_METRIC_RESULT_STATUS_AUTHORITY_INVALID",
            "metric.metric_instance.status SQL",
        )
    statuses = tuple(re.findall(r"'([^']+)'", match.group("values")))
    if not statuses or len(set(statuses)) != len(statuses):
        raise CatalogMetricEngineError(
            "M2_METRIC_RESULT_STATUS_AUTHORITY_INVALID",
            "metric.metric_instance.status values",
        )

    mission_system = _object(
        tables.get("master.mission_system_instance"),
        field="core_logical_model.tables.master.mission_system_instance",
    )
    mission_system_fields = _objects(
        mission_system.get("fields"),
        field="core_logical_model.tables.master.mission_system_instance.fields",
    )
    system_type_fields = [
        field for field in mission_system_fields if field.get("name") == "system_type"
    ]
    if len(system_type_fields) != 1:
        raise CatalogMetricEngineError(
            "M2_METRIC_SYSTEM_TYPE_AUTHORITY_INVALID",
            "master.mission_system_instance.system_type cardinality",
        )
    system_type_field = system_type_fields[0]
    if (
        _text(
            system_type_field,
            "type",
            field="master.mission_system_instance.system_type",
        )
        != "text"
        or system_type_field.get("nullable") is not False
    ):
        raise CatalogMetricEngineError(
            "M2_METRIC_SYSTEM_TYPE_AUTHORITY_INVALID",
            "master.mission_system_instance.system_type type/nullability",
        )
    system_type_sql = _text(
        system_type_field,
        "sql",
        field="master.mission_system_instance.system_type",
    )
    system_type_match = re.fullmatch(
        r"system_type text NOT NULL CHECK \(system_type IN \((?P<values>(?:'[^']+'(?:,'[^']+')*)+)\)\)",
        system_type_sql,
    )
    if system_type_match is None:
        raise CatalogMetricEngineError(
            "M2_METRIC_SYSTEM_TYPE_AUTHORITY_INVALID",
            "master.mission_system_instance.system_type SQL",
        )
    system_types = tuple(
        re.findall(r"'([^']+)'", system_type_match.group("values"))
    )
    if not system_types or len(set(system_types)) != len(system_types):
        raise CatalogMetricEngineError(
            "M2_METRIC_SYSTEM_TYPE_AUTHORITY_INVALID",
            "master.mission_system_instance.system_type values",
        )
    return statuses, system_types, hashlib.sha256(raw_bytes).hexdigest()


def _metric_runtime_transport_authority(
    authority_root: Path,
    catalog: Mapping[str, object],
) -> str:
    path = authority_root / "CORE_RULES.json"
    rules_document, raw_bytes = _load_object(path)
    if _text(rules_document, "authority_id", field="core_rules") != "CORE_RULES":
        raise CatalogMetricEngineError(
            "M2_METRIC_RUNTIME_RULE_AUTHORITY_INVALID",
            "authority_id",
        )
    rules = _objects(rules_document.get("rules"), field="core_rules.rules")
    by_id = {
        _text(rule, "id", field="core_rules.rule"): rule
        for rule in rules
    }
    expected_core_rules = {
        "CR-005": (
            "Missing Is Not Zero",
            "Missing prerequisite data yields N_A or INSUFFICIENT_DATA with reason code; never fabricate zero.",
        ),
        "CR-008": (
            "Typed Metric Value",
            "value_kind determines one legal value slot; STRUCTURED is object and binds exactly one executable structured schema.",
        ),
        "CR-009": (
            "Stable Subjects",
            "P1 primary subjects are AIRCRAFT and MISSION_SYSTEM_INSTANCE; TARGET_PAIR is reference/evaluation quality only and never a longitudinal subject.",
        ),
        "CR-010": (
            "Observation Lanes",
            "AIRCRAFT_CAP_L1_OBSERVATION, SYSTEM_PERFORMANCE_OBSERVATION and QUALITY_EVIDENCE_ONLY are mutually governed publication lanes.",
        ),
    }
    for rule_id, (expected_name, expected_rule) in expected_core_rules.items():
        rule = by_id.get(rule_id)
        if rule is None or (
            _text(rule, "name", field=rule_id) != expected_name
            or _text(rule, "rule", field=rule_id) != expected_rule
        ):
            raise CatalogMetricEngineError(
                "M2_METRIC_RUNTIME_RULE_AUTHORITY_INVALID",
                rule_id,
            )

    common_rules = _object(catalog.get("common_rules"), field="common_rules")
    if (
        _text(common_rules, "missing", field="common_rules")
        != "Missing prerequisite data => N_A or INSUFFICIENT_DATA with reason code; never fabricate zero."
        or _text(
            common_rules,
            "metric_value_transport_contract",
            field="common_rules",
        )
        != (
            "Catalog value_kind is authoritative. NUMERIC/TEXT/BOOLEAN/STRUCTURED map to typed result slots; "
            "STRUCTURED uses value_structured/object and MUST NOT be JSON-serialized into value_text. "
            "For VALID results exactly the value slot matching semantic value_kind is populated; "
            "non-VALID results may have all value slots null."
        )
        or _text(
            common_rules,
            "observation_lane_routing",
            field="common_rules",
        )
        != (
            "Every P1 metric declares observation_lane and publication_route. P1-AIR-* publishes to "
            "AIRCRAFT_CAP_L1_OBSERVATION/CAPABILITY_OBSERVATION; MISSION_SYSTEM_INSTANCE metrics publish "
            "to SYSTEM_PERFORMANCE_OBSERVATION; reference/alignment/data-quality metrics that must not "
            "become capability/system observations publish to QUALITY_EVIDENCE_ONLY/METRIC_INSTANCE_EVIDENCE_ONLY. "
            "QUALITY_EVIDENCE_ONLY metrics MUST have p1_longitudinal_trend_eligibility=false and MUST NOT create "
            "longitudinal_sample rows."
        )
        or _text(
            common_rules,
            "longitudinal_value_contract",
            field="common_rules",
        )
        != (
            "P1 longitudinal longitudinal_sample is numeric-only. "
            "p1_longitudinal_trend_eligibility=true requires value_kind=NUMERIC and "
            "default_aggregation=MEDIAN. STRUCTURED or quality-only metrics use "
            "default_aggregation=NONE and never enter longitudinal_sample unless a future "
            "separately versioned component metric/projection contract is introduced."
        )
        or _text(
            common_rules,
            "trend_subject_compatibility",
            field="common_rules",
        )
        != (
            "P1 longitudinal longitudinal subject types are AIRCRAFT and MISSION_SYSTEM_INSTANCE only. "
            "Any metric with subject_type=TARGET_PAIR is reference/evaluation-quality evidence and MUST have "
            "p1_longitudinal_trend_eligibility=false; its quality/uncertainty travels with the owning "
            "mission-system observation/sample rather than creating a TARGET_PAIR trend lane."
        )
        or _text(
            common_rules,
            "default_aggregation_contract",
            field="common_rules",
        )
        != (
            "default_aggregation is the baseline SESSION_CONFIG longitudinal aggregation, "
            "not a free formula selector. Current values are MEDIAN for trend-eligible "
            "NUMERIC metrics and NONE for metrics that do not enter P1 longitudinal. "
            "Approved alternate sample profiles are governed separately and segment comparison keys."
        )
        or _text(
            common_rules,
            "algorithm_identity",
            field="common_rules",
        )
        != (
            "Every metric has exactly one algorithm_id + algorithm_version. The pair is immutable inside "
            "a released Metric Definition. Profile parameters are part of provenance/comparison_key but never "
            "substitute for algorithm identity."
        )
        or _text(
            common_rules,
            "reference_match_eligibility",
            field="common_rules",
        )
        != (
            "Mission-system accuracy metrics that bind CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 "
            "use only the exact profile_id/version/hash supplied in MetricContext. Eligibility thresholds "
            "are configuration data; missing profile fields are an error, not an implicit default."
        )
        or _text(
            common_rules,
            "profile_input_exact_name_contract",
            field="common_rules",
        )
        != (
            "For every Metric, the set of declared profile_parameters MUST equal exactly the suffix set "
            "of input_fields entries named profile.<parameter>. Generic aliases such as "
            "profile.band/profile.deadband/profile.event_window are forbidden; API/Profile editors consume "
            "exact Catalog parameter names only."
        )
        or _text(
            common_rules,
            "algorithm_dependency_closure",
            field="common_rules",
        )
        != (
            "Every formula dependency that is not a raw/canonical input must be declared in "
            "operator_bindings, constant_bindings, upstream_dependencies or state_machine_bindings. "
            "Registry references are immutable/versioned. Unbound derivative/smoothing/filter/"
            "sustained-window/epsilon/reset/stable/qualified/association/handover semantics are forbidden."
        )
        or _text(
            common_rules,
            "derived_operator_binding",
            field="common_rules",
        )
        != (
            "Derivative/filter/smoothing/rolling/statistical operators must bind to operator_registry IDs "
            "when the implementation has nontrivial method choice. Sustained metrics must bind "
            "ROLLING_MEDIAN_V1 and declare sustain_duration_s/min_coverage/max_gap_us."
        )
        or _text(
            common_rules,
            "constant_binding",
            field="common_rules",
        )
        != (
            "Algorithm constants that affect eligibility/numerical behavior must use constant_registry IDs "
            "or literal values with units in formula. Bare epsilon is forbidden."
        )
        or _text(
            common_rules,
            "state_machine_binding",
            field="common_rules",
        )
        != (
            "Metrics using stable/qualified/reset/refuel/drop/reacquire/association/handover/opportunity "
            "semantics must consume a frozen upstream state/event or bind a state_machine_registry ID; "
            "the metric may not invent an unstated state machine. A metric that itself produces/qualifies "
            "a state must declare that state machine's numeric parameters; a downstream consumer may instead "
            "consume a pre-qualified upstream state/event whose producer/version is present in "
            "upstream_dependencies/Evidence."
        )
        or _text(
            common_rules,
            "event_authority",
            field="common_rules",
        )
        != (
            "Opportunity/confirmation state machines execute only in the WRE canonical event builders. "
            "Metrics consume CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1 / "
            "CONTRACT_DETECTION_CONFIRMATION_EVENT_V1 and never rebuild those events."
        )
        or _text(
            common_rules,
            "shared_event_authority_contract",
            field="common_rules",
        )
        != (
            "Canonical Opportunity, Confirmation and Fusion Handover events are built once by WRE. "
            "Metric Plugins consume the versioned event contract and never rerun the owning state machine "
            "or infer event authority from another Metric result."
        )
        or _text(
            common_rules,
            "structured_schema_standard",
            field="common_rules",
        )
        != (
            "structured_output_schema_registry[].json_schema is the executable authority and MUST be valid "
            "JSON Schema Draft 2020-12 with additionalProperties=false at every object level. field_contracts "
            "is a human-readable summary only. DB schema_json seeds exactly json_schema; API returns the same "
            "schema/hash."
        )
    ):
        raise CatalogMetricEngineError(
            "M2_METRIC_RUNTIME_RULE_AUTHORITY_INVALID",
            "catalog.common_rules",
        )
    return hashlib.sha256(raw_bytes).hexdigest()


def _generated_metadata_by_code() -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for raw in P1_METRICS:
        code = raw.get("metric_code")
        if not isinstance(code, str) or not code:
            raise CatalogMetricEngineError(
                "M2_METRIC_GENERATED_REGISTRY_INVALID",
                repr(code),
            )
        result[code] = raw
    return result


def _validate_generated_projection(
    raw: Mapping[str, object],
    generated: Mapping[str, object],
) -> None:
    code = _text(raw, "metric_code", field="metric")
    keys = (
        "metric_code",
        "semantic_id",
        "semantic_version",
        "family",
        "subject_type",
        "unit",
        "value_kind",
        "algorithm_id",
        "algorithm_version",
        "delivery_milestone",
        "delivery_batch",
        "observation_lane",
        "publication_route",
        "structured_output_schema_id",
        "p1_longitudinal_trend_eligibility",
    )
    for key in keys:
        if raw.get(key) != generated.get(key):
            raise CatalogMetricEngineError(
                "M2_METRIC_GENERATED_REGISTRY_DRIFT",
                f"{code}.{key}",
            )


def _topological_order(
    definitions: Sequence[M2MetricDefinition],
) -> tuple[M2MetricDefinition, ...]:
    by_code = {definition.metric_code: definition for definition in definitions}
    remaining = set(by_code)
    completed: set[str] = set()
    ordered: list[M2MetricDefinition] = []

    while remaining:
        ready = sorted(
            (
                by_code[code]
                for code in remaining
                if set(by_code[code].metric_dependencies).issubset(completed)
            ),
            key=lambda definition: definition.catalog_index,
        )
        if not ready:
            raise CatalogMetricEngineError(
                "M2_METRIC_DEPENDENCY_CYCLE",
                repr(sorted(remaining)),
            )
        for definition in ready:
            ordered.append(definition)
            completed.add(definition.metric_code)
            remaining.remove(definition.metric_code)
    return tuple(ordered)


def build_m2_metric_execution_plan(authority_root: Path) -> M2MetricExecutionPlan:
    """Compile the exact frozen M2 Catalog batch into one deterministic plan."""

    catalog_path = authority_root / "P1_METRIC_CATALOG.json"
    catalog, catalog_bytes = _load_object(catalog_path)
    catalog_version = _text(catalog, "catalog_version", field="catalog")
    db_schema_version = _text(catalog, "db_schema_version", field="catalog")
    if db_schema_version != "1.6.0":
        raise CatalogMetricEngineError(
            "M2_METRIC_DB_SCHEMA_VERSION_DRIFT",
            db_schema_version,
        )

    metrics = _objects(catalog.get("metrics"), field="metrics")
    selected_with_index = [
        (index, metric)
        for index, metric in enumerate(metrics)
        if metric.get("delivery_milestone") == M2_DELIVERY_MILESTONE
        and metric.get("delivery_batch") == M2_DELIVERY_BATCH
    ]
    if len(selected_with_index) != M2_FOUNDATION_COUNT:
        raise CatalogMetricEngineError(
            "M2_METRIC_FOUNDATION_COUNT_DRIFT",
            str(len(selected_with_index)),
        )
    catalog_codes = tuple(
        _text(metric, "metric_code", field=f"metrics[{index}]")
        for index, metric in selected_with_index
    )
    if len(set(catalog_codes)) != M2_FOUNDATION_COUNT:
        raise CatalogMetricEngineError(
            "M2_METRIC_FOUNDATION_CODE_DUPLICATE",
            repr(catalog_codes),
        )

    family_counts = Counter(
        _text(metric, "family", field=f"metrics[{index}]")
        for index, metric in selected_with_index
    )
    if dict(family_counts) != dict(M2_EXPECTED_FAMILY_COUNTS):
        raise CatalogMetricEngineError(
            "M2_METRIC_FAMILY_COUNT_DRIFT",
            repr(dict(family_counts)),
        )

    operator_registry = _object(catalog.get("operator_registry"), field="operator_registry")
    constant_registry = _object(catalog.get("constant_registry"), field="constant_registry")
    state_machine_registry = _object(
        catalog.get("state_machine_registry"),
        field="state_machine_registry",
    )
    upstream_registry = _object(
        catalog.get("upstream_contract_registry"),
        field="upstream_contract_registry",
    )
    schema_registry = _object(
        catalog.get("structured_output_schema_registry"),
        field="structured_output_schema_registry",
    )
    family_contracts = _object(
        catalog.get("family_applicability_contracts"),
        field="family_applicability_contracts",
    )
    operator_registry_sha256 = _sha256_object(operator_registry)
    constant_registry_sha256 = _sha256_object(constant_registry)
    state_machine_registry_sha256 = _sha256_object(state_machine_registry)
    upstream_contract_registry_sha256 = _sha256_object(upstream_registry)
    structured_output_schema_registry_sha256 = _sha256_object(schema_registry)
    family_applicability_contracts_sha256 = _sha256_object(family_contracts)
    generated_by_code = _generated_metadata_by_code()
    selected_codes = set(catalog_codes)
    selected_semantic_ids = {
        _text(metric, "metric_code", field=f"metrics[{index}]"): _text(
            metric,
            "semantic_id",
            field=f"metrics[{index}]",
        )
        for index, metric in selected_with_index
    }
    (
        input_authority_by_metric,
        input_authority_matrix_sha256,
        source_provenance_sha256,
    ) = _input_authority_by_metric(
        authority_root,
        catalog_version=catalog_version,
        selected_semantic_ids=selected_semantic_ids,
    )
    world_capability_registry_sha256 = _world_capability_registry_hash(authority_root)
    (
        allowed_result_statuses,
        allowed_mission_system_types,
        core_logical_model_sha256,
    ) = _metric_result_status_authority(authority_root)
    core_rules_sha256 = _metric_runtime_transport_authority(
        authority_root,
        catalog,
    )
    definitions: list[M2MetricDefinition] = []

    for index, raw in selected_with_index:
        code = _text(raw, "metric_code", field=f"metrics[{index}]")
        generated = generated_by_code.get(code)
        if generated is None:
            raise CatalogMetricEngineError(
                "M2_METRIC_GENERATED_DEFINITION_MISSING",
                code,
            )
        _validate_generated_projection(raw, generated)

        operators = _string_list(raw, "operator_bindings", field=code)
        constants = _string_list(raw, "constant_bindings", field=code)
        upstream = _string_list(raw, "upstream_dependencies", field=code)
        state_machines = _string_list(raw, "state_machine_bindings", field=code)
        formula = _text(raw, "formula", field=code)
        formula_dependency_references = _validate_governed_formula_dependency_closure(
            metric_code=code,
            formula=formula,
            operator_bindings=operators,
            constant_bindings=constants,
            upstream_dependencies=upstream,
            state_machine_bindings=state_machines,
            operator_registry=operator_registry,
            constant_registry=constant_registry,
            upstream_registry=upstream_registry,
            state_machine_registry=state_machine_registry,
            selected_metric_codes=selected_codes,
        )
        profile_parameters = _string_list(raw, "profile_parameters", field=code)
        input_fields = _string_list(raw, "input_fields", field=code)
        profile_input_parameters = tuple(
            field[len("profile.") : -1]
            if field.startswith("profile.") and field.endswith("?")
            else field[len("profile.") :]
            for field in input_fields
            if field.startswith("profile.")
        )
        if (
            len(set(profile_parameters)) != len(profile_parameters)
            or len(set(profile_input_parameters)) != len(profile_input_parameters)
            or set(profile_parameters) != set(profile_input_parameters)
        ):
            raise CatalogMetricEngineError(
                "M2_METRIC_PROFILE_INPUT_CONTRACT_DRIFT",
                (
                    f"{code}:declared={sorted(profile_parameters)!r}:"
                    f"inputs={sorted(profile_input_parameters)!r}"
                ),
            )
        raw_authority_bindings = input_authority_by_metric.get(code, ())
        binding_by_field = {
            binding.input_field: binding for binding in raw_authority_bindings
        }
        if (
            len(binding_by_field) != len(raw_authority_bindings)
            or set(binding_by_field) != set(input_fields)
        ):
            raise CatalogMetricEngineError(
                "M2_METRIC_INPUT_AUTHORITY_COVERAGE_DRIFT",
                code,
            )
        authority_bindings = tuple(binding_by_field[field] for field in input_fields)
        if any(
            binding.binding_kind == "UPSTREAM_CONTRACT"
            and binding.authority_id not in upstream
            for binding in authority_bindings
        ):
            raise CatalogMetricEngineError(
                "M2_METRIC_INPUT_AUTHORITY_UPSTREAM_DRIFT",
                code,
            )

        reference_match_identity_bindings = tuple(
            binding
            for binding in authority_bindings
            if binding.authority_id == _REFERENCE_MATCH_QUALITY_PROFILE_CONTRACT
        )
        reference_match_identity_expected = {
            (field, field, "UPSTREAM_CONTRACT", False)
            for field in _REFERENCE_MATCH_QUALITY_PROFILE_IDENTITY_FIELDS
        }
        reference_match_identity_actual = {
            (
                binding.input_field,
                binding.authority_field,
                binding.binding_kind,
                binding.optional,
            )
            for binding in reference_match_identity_bindings
        }
        if _REFERENCE_MATCH_QUALITY_PROFILE_CONTRACT in upstream:
            if (
                len(reference_match_identity_bindings)
                != len(_REFERENCE_MATCH_QUALITY_PROFILE_IDENTITY_FIELDS)
                or reference_match_identity_actual != reference_match_identity_expected
            ):
                raise CatalogMetricEngineError(
                    "M2_METRIC_REFERENCE_MATCH_PROFILE_IDENTITY_DRIFT",
                    code,
                )
        elif reference_match_identity_bindings:
            raise CatalogMetricEngineError(
                "M2_METRIC_REFERENCE_MATCH_PROFILE_IDENTITY_DRIFT",
                code,
            )

        for operator_id in operators:
            if operator_id not in operator_registry:
                raise CatalogMetricEngineError(
                    "M2_METRIC_OPERATOR_AUTHORITY_MISSING",
                    f"{code}:{operator_id}",
                )
            _validate_versioned_registry_entry(
                operator_registry,
                operator_id,
                field="operator_registry",
            )
            if operator_id not in M2_OPERATOR_IMPLEMENTATIONS:
                raise CatalogMetricEngineError(
                    "M2_METRIC_OPERATOR_IMPLEMENTATION_MISSING",
                    f"{code}:{operator_id}",
                )
        for constant_id in constants:
            if constant_id not in constant_registry:
                raise CatalogMetricEngineError(
                    "M2_METRIC_CONSTANT_AUTHORITY_MISSING",
                    f"{code}:{constant_id}",
                )
        for state_machine_id in state_machines:
            if state_machine_id not in state_machine_registry:
                raise CatalogMetricEngineError(
                    "M2_METRIC_STATE_MACHINE_AUTHORITY_MISSING",
                    f"{code}:{state_machine_id}",
                )
            _validate_versioned_registry_entry(
                state_machine_registry,
                state_machine_id,
                field="state_machine_registry",
            )

        metric_dependencies = tuple(item for item in upstream if item in selected_codes)
        external_dependencies = tuple(item for item in upstream if item not in selected_codes)
        for dependency in external_dependencies:
            if dependency.startswith("P1-") or dependency not in upstream_registry:
                raise CatalogMetricEngineError(
                    "M2_METRIC_UPSTREAM_AUTHORITY_MISSING",
                    f"{code}:{dependency}",
                )
            _validate_versioned_registry_entry(
                upstream_registry,
                dependency,
                field="upstream_contract_registry",
            )

        value_kind = _text(raw, "value_kind", field=code)
        trend_eligible = raw.get("p1_longitudinal_trend_eligibility")
        if not isinstance(trend_eligible, bool):
            raise CatalogMetricEngineError(
                "M2_METRIC_LONGITUDINAL_ELIGIBILITY_INVALID",
                code,
            )
        default_aggregation = _text(raw, "default_aggregation", field=code)
        observation_lane = _text(raw, "observation_lane", field=code)
        subject_type = _text(raw, "subject_type", field=code)
        if subject_type == "TARGET_PAIR" and trend_eligible:
            raise CatalogMetricEngineError(
                "M2_METRIC_TARGET_PAIR_LONGITUDINAL_FORBIDDEN",
                code,
            )
        if trend_eligible and subject_type not in {
            "AIRCRAFT",
            "MISSION_SYSTEM_INSTANCE",
        }:
            raise CatalogMetricEngineError(
                "M2_METRIC_LONGITUDINAL_SUBJECT_INVALID",
                f"{code}:{subject_type}",
            )
        if trend_eligible:
            if value_kind != "NUMERIC" or default_aggregation != "MEDIAN":
                raise CatalogMetricEngineError(
                    "M2_METRIC_LONGITUDINAL_CONTRACT_DRIFT",
                    code,
                )
        elif default_aggregation != "NONE":
            raise CatalogMetricEngineError(
                "M2_METRIC_LONGITUDINAL_CONTRACT_DRIFT",
                code,
            )
        if observation_lane == "QUALITY_EVIDENCE_ONLY" and trend_eligible:
            raise CatalogMetricEngineError(
                "M2_METRIC_QUALITY_LONGITUDINAL_FORBIDDEN",
                code,
            )
        if value_kind == "STRUCTURED" and trend_eligible:
            raise CatalogMetricEngineError(
                "M2_METRIC_STRUCTURED_LONGITUDINAL_FORBIDDEN",
                code,
            )

        schema_id = _optional_text(raw, "structured_output_schema_id", field=code)
        schema_json: str | None = None
        schema_hash: str | None = None
        if value_kind == "STRUCTURED":
            if schema_id is None or schema_id not in schema_registry:
                raise CatalogMetricEngineError(
                    "M2_METRIC_STRUCTURED_SCHEMA_MISSING",
                    code,
                )
            schema_json, schema_hash = _compile_structured_output_schema(
                schema_registry,
                metric_code=code,
                schema_id=schema_id,
            )
        elif value_kind == "NUMERIC":
            if schema_id is not None:
                raise CatalogMetricEngineError(
                    "M2_METRIC_NUMERIC_SCHEMA_UNEXPECTED",
                    code,
                )
        else:
            raise CatalogMetricEngineError(
                "M2_METRIC_VALUE_KIND_UNSUPPORTED",
                f"{code}:{value_kind}",
            )

        applicability = _applicability(raw, family_contracts)
        definition_hash = _sha256_object(raw)
        authority_lineage_hash = _sha256_object(
            {
                "metric_code": code,
                "definition_hash": definition_hash,
                "input_authority_bindings": [
                    {
                        "metric_semantic_id": binding.metric_semantic_id,
                        "input_field": binding.input_field,
                        "optional": binding.optional,
                        "binding_kind": binding.binding_kind,
                        "authority_id": binding.authority_id,
                        "authority_field": binding.authority_field,
                        "normalization_rule": binding.normalization_rule,
                    }
                    for binding in authority_bindings
                ],
                "operator_authority": {
                    operator_id: operator_registry[operator_id]
                    for operator_id in operators
                },
                "constant_authority": {
                    constant_id: constant_registry[constant_id]
                    for constant_id in constants
                },
                "state_machine_authority": {
                    state_machine_id: state_machine_registry[state_machine_id]
                    for state_machine_id in state_machines
                },
                "external_dependency_authority": {
                    dependency: upstream_registry[dependency]
                    for dependency in external_dependencies
                },
                "structured_output_schema_id": schema_id,
                "structured_output_schema_hash_sha256": schema_hash,
                "family_applicability_contract": family_contracts[applicability.key],
                "formula_dependency_references": formula_dependency_references,
                "source_provenance_sha256": source_provenance_sha256,
                "world_capability_registry_sha256": world_capability_registry_sha256,
                "core_logical_model_sha256": core_logical_model_sha256,
                "core_rules_sha256": core_rules_sha256,
            }
        )

        definition = M2MetricDefinition(
            catalog_index=index,
            metric_code=code,
            name=_text(raw, "name", field=code),
            semantic_id=_text(raw, "semantic_id", field=code),
            semantic_version=_integer(raw, "semantic_version", field=code),
            family=_text(raw, "family", field=code),
            subject_type=_text(raw, "subject_type", field=code),
            unit=_text(raw, "unit", field=code),
            value_kind=value_kind,
            algorithm_id=_text(raw, "algorithm_id", field=code),
            algorithm_version=_text(raw, "algorithm_version", field=code),
            observation_lane=observation_lane,
            publication_route=_text(raw, "publication_route", field=code),
            p1_longitudinal_trend_eligibility=trend_eligible,
            default_aggregation=default_aggregation,
            structured_output_schema_id=schema_id,
            structured_output_schema_json=schema_json,
            structured_output_schema_hash_sha256=schema_hash,
            input_fields=input_fields,
            formula=formula,
            validity_conditions=_text(raw, "validity_conditions", field=code),
            na_conditions=_text(raw, "na_conditions", field=code),
            profile_parameters=profile_parameters,
            operator_bindings=operators,
            constant_bindings=constants,
            upstream_dependencies=upstream,
            metric_dependencies=metric_dependencies,
            external_dependencies=external_dependencies,
            state_machine_bindings=state_machines,
            input_authority_bindings=authority_bindings,
            allowed_result_statuses=allowed_result_statuses,
            allowed_mission_system_types=allowed_mission_system_types,
            applicability=applicability,
            formula_dependency_references=formula_dependency_references,
            definition_hash=definition_hash,
            authority_lineage_hash=authority_lineage_hash,
        )
        definitions.append(definition)

    ordered = _topological_order(definitions)
    required_operator_ids = tuple(
        sorted({operator for definition in ordered for operator in definition.operator_bindings})
    )
    required_state_machine_ids = tuple(
        sorted(
            {
                state_machine
                for definition in ordered
                for state_machine in definition.state_machine_bindings
            }
        )
    )
    required_external_dependency_ids = tuple(
        sorted(
            {
                dependency
                for definition in ordered
                for dependency in definition.external_dependencies
            }
        )
    )
    execution_identity_sha256 = _sha256_object(
        [
            {
                "metric_code": definition.metric_code,
                "semantic_id": definition.semantic_id,
                "semantic_version": definition.semantic_version,
                "algorithm_id": definition.algorithm_id,
                "algorithm_version": definition.algorithm_version,
                "definition_hash": definition.definition_hash,
            }
            for definition in ordered
        ]
    )
    logical_hash = _sha256_object(
        {
            "catalog_id": "P1_METRIC_CATALOG",
            "catalog_version": catalog_version,
            "catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest(),
            "input_authority_matrix_sha256": input_authority_matrix_sha256,
            "source_provenance_sha256": source_provenance_sha256,
            "world_capability_registry_sha256": world_capability_registry_sha256,
            "core_logical_model_sha256": core_logical_model_sha256,
            "core_rules_sha256": core_rules_sha256,
            "operator_registry_sha256": operator_registry_sha256,
            "constant_registry_sha256": constant_registry_sha256,
            "state_machine_registry_sha256": state_machine_registry_sha256,
            "upstream_contract_registry_sha256": upstream_contract_registry_sha256,
            "structured_output_schema_registry_sha256": structured_output_schema_registry_sha256,
            "family_applicability_contracts_sha256": family_applicability_contracts_sha256,
            "execution_identity_sha256": execution_identity_sha256,
            "input_lineage_encoding": M2_INPUT_LINEAGE_ENCODING,
            "allowed_result_statuses": allowed_result_statuses,
            "allowed_mission_system_types": allowed_mission_system_types,
            "db_schema_version": db_schema_version,
            "delivery_milestone": M2_DELIVERY_MILESTONE,
            "delivery_batch": M2_DELIVERY_BATCH,
            "catalog_metric_codes": catalog_codes,
            "execution_metric_codes": [definition.metric_code for definition in ordered],
            "definition_hashes": [
                (definition.metric_code, definition.definition_hash) for definition in ordered
            ],
            "authority_lineage_hashes": [
                (definition.metric_code, definition.authority_lineage_hash)
                for definition in ordered
            ],
            "required_operator_ids": required_operator_ids,
            "required_state_machine_ids": required_state_machine_ids,
            "required_external_dependency_ids": required_external_dependency_ids,
            "dispatch_key": M2_DISPATCH_KEY,
        }
    )
    return M2MetricExecutionPlan(
        catalog_id="P1_METRIC_CATALOG",
        catalog_version=catalog_version,
        catalog_sha256=hashlib.sha256(catalog_bytes).hexdigest(),
        input_authority_matrix_sha256=input_authority_matrix_sha256,
        source_provenance_sha256=source_provenance_sha256,
        world_capability_registry_sha256=world_capability_registry_sha256,
        core_logical_model_sha256=core_logical_model_sha256,
        core_rules_sha256=core_rules_sha256,
        operator_registry_sha256=operator_registry_sha256,
        constant_registry_sha256=constant_registry_sha256,
        state_machine_registry_sha256=state_machine_registry_sha256,
        upstream_contract_registry_sha256=upstream_contract_registry_sha256,
        structured_output_schema_registry_sha256=structured_output_schema_registry_sha256,
        family_applicability_contracts_sha256=family_applicability_contracts_sha256,
        execution_identity_sha256=execution_identity_sha256,
        input_lineage_encoding=M2_INPUT_LINEAGE_ENCODING,
        allowed_result_statuses=allowed_result_statuses,
        allowed_mission_system_types=allowed_mission_system_types,
        db_schema_version=db_schema_version,
        delivery_milestone=M2_DELIVERY_MILESTONE,
        delivery_batch=M2_DELIVERY_BATCH,
        catalog_metric_codes=catalog_codes,
        definitions=ordered,
        required_operator_ids=required_operator_ids,
        required_state_machine_ids=required_state_machine_ids,
        required_external_dependency_ids=required_external_dependency_ids,
        logical_hash=logical_hash,
    )
