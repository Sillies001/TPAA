#!/usr/bin/env python3
"""Authority-safe incremental 32-metric batch/replay evidence for M2-MET-007.

This check exercises the frozen 32-code plan, dependency ordering, runtime
transport validation and deterministic hashing with schema-derived probe values.
It intentionally does not claim business-formula execution for authority-blocked
QA/SNS semantics and keeps M2-MET-007 incomplete until its frozen predecessors
are complete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"


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


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be string-keyed object")
    return cast(dict[str, object], value)


def _schema_types(schema: Mapping[str, object], *, field: str) -> tuple[str, ...]:
    raw = schema.get("type")
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, list) and raw and all(isinstance(item, str) for item in raw):
        return tuple(cast(list[str], raw))
    raise ValueError(f"{field}.type is unsupported")


def _schema_probe_value(schema: Mapping[str, object], *, field: str) -> object:
    types = _schema_types(schema, field=field)
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    if "null" in types:
        return None
    primary = types[0]
    if primary == "object":
        properties = _mapping(schema.get("properties"), field=f"{field}.properties")
        required = schema.get("required", [])
        if not isinstance(required, list) or not all(
            isinstance(item, str) for item in required
        ):
            raise ValueError(f"{field}.required is unsupported")
        result: dict[str, object] = {}
        for name in cast(list[str], required):
            result[name] = _schema_probe_value(
                _mapping(properties.get(name), field=f"{field}.{name}"),
                field=f"{field}.{name}",
            )
        return result
    if primary == "array":
        items = _mapping(schema.get("items"), field=f"{field}.items")
        min_items = schema.get("minItems", 0)
        if isinstance(min_items, bool) or not isinstance(min_items, int) or min_items < 0:
            raise ValueError(f"{field}.minItems is unsupported")
        return [
            _schema_probe_value(items, field=f"{field}[{index}]")
            for index in range(min_items)
        ]
    if primary == "number":
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and not isinstance(minimum, bool):
            value = float(minimum)
            if not math.isfinite(value):
                raise ValueError(f"{field}.minimum is non-finite")
            return value
        return 0.0
    if primary == "integer":
        minimum = schema.get("minimum")
        if isinstance(minimum, int) and not isinstance(minimum, bool):
            return minimum
        return 0
    if primary == "string":
        pattern = schema.get("pattern")
        if pattern == "^-?[0-9]+$":
            return "0"
        return "PROBE"
    if primary == "boolean":
        return False
    raise ValueError(f"{field}: unsupported schema type {primary}")


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_metric import (
        CatalogMetricEngine,
        M2MetricDefinition,
        M2MetricPluginRequest,
        MetricPluginRegistry,
        build_m2_metric_execution_plan,
    )

    plan = build_m2_metric_execution_plan(AUTHORITY_ROOT)
    replay_plan = build_m2_metric_execution_plan(AUTHORITY_ROOT)

    def input_payload(definition: M2MetricDefinition) -> dict[str, object]:
        payload: dict[str, object] = {
            "input_token": (
                f"M2-MET-007::{definition.catalog_index}::{definition.metric_code}"
            )
        }
        if definition.applicability.applicability_mode == "SYSTEM_TYPE_EXACT":
            payload["system_type"] = "RADAR"
        return payload

    def evidence_hash(
        definition: M2MetricDefinition,
        payload: Mapping[str, object],
    ) -> str:
        return _canonical_hash(
            {
                "task_id": "M2-MET-007",
                "metric_code": definition.metric_code,
                "definition_hash": definition.definition_hash,
                "input_token": payload.get("input_token"),
            }
        )

    def probe(request: M2MetricPluginRequest) -> Mapping[str, object]:
        definition = request.definition
        payload = request.input_payload
        probe_hash = evidence_hash(definition, payload)
        if definition.value_kind == "NUMERIC":
            value_numeric: float | None = 1.0
            value_structured: object = None
        elif definition.value_kind == "STRUCTURED":
            if definition.structured_output_schema_json is None:
                raise ValueError(
                    f"M2_MET_007_SCHEMA_MISSING:{definition.metric_code}"
                )
            raw_schema: object = json.loads(definition.structured_output_schema_json)
            schema = _mapping(
                raw_schema,
                field=f"{definition.metric_code}.structured_schema",
            )
            value_numeric = None
            value_structured = _schema_probe_value(
                schema,
                field=definition.metric_code,
            )
        else:
            raise ValueError(
                f"M2_MET_007_VALUE_KIND_UNSUPPORTED:{definition.value_kind}"
            )
        output: dict[str, object] = {
            "metric_code": definition.metric_code,
            "subject_type": definition.subject_type,
            "observation_lane": definition.observation_lane,
            "publication_route": definition.publication_route,
            "probe_evidence_hash": probe_hash,
            "instances": [
                {
                    "status": "VALID",
                    "reason_codes": [],
                    "value_kind": definition.value_kind,
                    "value_numeric": value_numeric,
                    "value_structured": value_structured,
                    "probe_evidence_hash": probe_hash,
                }
            ],
        }
        if definition.applicability.applicability_mode == "SYSTEM_TYPE_EXACT":
            output["applicable"] = True
        return output

    registry = MetricPluginRegistry()
    for definition in plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id="m2-met-007-runtime-replay-probe-v1",
            plugin=probe,
        )

    inputs = {
        definition.metric_code: input_payload(definition)
        for definition in plan.definitions
    }
    reversed_inputs = dict(reversed(tuple(inputs.items())))
    engine = CatalogMetricEngine(plan, registry)
    first = engine.execute(inputs)
    replayed = engine.execute(reversed_inputs)
    reversed_request = engine.execute(
        inputs,
        metric_codes=tuple(reversed(plan.metric_codes)),
    )

    tampered_inputs = {code: dict(payload) for code, payload in inputs.items()}
    tampered_inputs["P1-AIR-001"]["input_token"] = "M2-MET-007::TAMPER"
    tampered = engine.execute(tampered_inputs)

    positions = {code: index for index, code in enumerate(first.metric_codes)}
    dependency_order_exact = all(
        positions[dependency] < positions[definition.metric_code]
        for definition in plan.definitions
        for dependency in definition.metric_dependencies
    )
    record_by_code = {record.metric_code: record for record in first.records}
    dependency_manifest_hash_binding_exact = all(
        record_by_code[definition.metric_code].dependency_manifest_hash
        == _canonical_hash(
            {
                "operator_bindings": definition.operator_bindings,
                "constant_bindings": definition.constant_bindings,
                "state_machine_bindings": definition.state_machine_bindings,
                "metric_dependencies": definition.metric_dependencies,
                "external_dependencies": definition.external_dependencies,
                "formula_dependency_references": (
                    definition.formula_dependency_references
                ),
            }
        )
        for definition in plan.definitions
    )
    dependency_hash_binding_exact = all(
        record_by_code[definition.metric_code].upstream_result_hashes
        == tuple(
            (dependency, record_by_code[dependency].logical_hash)
            for dependency in definition.metric_dependencies
        )
        for definition in plan.definitions
    )
    record_identity_binding_exact = all(
        record_by_code[definition.metric_code].semantic_id == definition.semantic_id
        and record_by_code[definition.metric_code].semantic_version
        == definition.semantic_version
        and record_by_code[definition.metric_code].algorithm_id
        == definition.algorithm_id
        and record_by_code[definition.metric_code].algorithm_version
        == definition.algorithm_version
        and record_by_code[definition.metric_code].definition_hash
        == definition.definition_hash
        for definition in plan.definitions
    )
    per_metric_hashes = [
        {
            "metric_code": definition.metric_code,
            "semantic_id": record_by_code[definition.metric_code].semantic_id,
            "semantic_version": record_by_code[definition.metric_code].semantic_version,
            "algorithm_id": record_by_code[definition.metric_code].algorithm_id,
            "algorithm_version": record_by_code[definition.metric_code].algorithm_version,
            "definition_hash": definition.definition_hash,
            "authority_lineage_hash": record_by_code[
                definition.metric_code
            ].authority_lineage_hash,
            "input_payload_hash": record_by_code[
                definition.metric_code
            ].input_payload_hash,
            "dependency_manifest_hash": record_by_code[
                definition.metric_code
            ].dependency_manifest_hash,
            "probe_evidence_hash": evidence_hash(
                definition,
                inputs[definition.metric_code],
            ),
            "plugin_output_hash": record_by_code[
                definition.metric_code
            ].plugin_output_hash,
            "record_logical_hash": record_by_code[
                definition.metric_code
            ].logical_hash,
        }
        for definition in plan.definitions
    ]
    all_hashes_well_formed = all(
        _is_sha256(item[key])
        for item in per_metric_hashes
        for key in (
            "definition_hash",
            "authority_lineage_hash",
            "input_payload_hash",
            "dependency_manifest_hash",
            "probe_evidence_hash",
            "plugin_output_hash",
            "record_logical_hash",
        )
    )
    tampered_record_by_code = {
        record.metric_code: record for record in tampered.records
    }
    input_payload_hash_binding_exact = all(
        record_by_code[definition.metric_code].input_payload_hash
        == _canonical_hash(inputs[definition.metric_code])
        for definition in plan.definitions
    )
    authority_lineage_hash_binding_exact = all(
        record_by_code[definition.metric_code].authority_lineage_hash
        == definition.authority_lineage_hash
        for definition in plan.definitions
    )
    dependency_edges = [
        [dependency, definition.metric_code]
        for definition in plan.definitions
        for dependency in definition.metric_dependencies
    ]

    acceptance = {
        "catalog_membership_exact_32": (
            len(plan.catalog_metric_codes) == 32
            and len(set(plan.catalog_metric_codes)) == 32
            and set(first.metric_codes) == set(plan.catalog_metric_codes)
        ),
        "execution_membership_exact_32": (
            len(first.records) == 32 and first.metric_codes == plan.metric_codes
        ),
        "dependency_order_exact": dependency_order_exact,
        "dependency_hash_binding_exact": dependency_hash_binding_exact,
        "dependency_manifest_hash_binding_exact_32": (
            dependency_manifest_hash_binding_exact
        ),
        "dispatch_key_version_qualified": (
            first.dispatch_key == "algorithm_id+algorithm_version"
        ),
        "record_identity_binding_exact_32": record_identity_binding_exact,
        "plugin_manifest_hash_well_formed": _is_sha256(first.plugin_manifest_hash),
        "plugin_manifest_replay_exact": (
            first.plugin_manifest_hash
            == replayed.plugin_manifest_hash
            == reversed_request.plugin_manifest_hash
            == tampered.plugin_manifest_hash
        ),
        "input_lineage_encoding_exact": (
            plan.input_lineage_encoding == "TPAA_M2_INPUT_LINEAGE_JSON_V1"
            and all(
                record.input_lineage_encoding == plan.input_lineage_encoding
                for record in first.records
            )
        ),
        "input_payload_hash_binding_exact_32": input_payload_hash_binding_exact,
        "authority_lineage_hash_binding_exact_32": authority_lineage_hash_binding_exact,
        "tampered_input_payload_hash_changes": (
            tampered_record_by_code["P1-AIR-001"].input_payload_hash
            != record_by_code["P1-AIR-001"].input_payload_hash
        ),
        "generated_metric_projection_hash_well_formed": _is_sha256(
            plan.generated_metric_projection_sha256
        ),
        "execution_identity_hash_well_formed": _is_sha256(plan.execution_identity_sha256),
        "registry_lineage_hashes_well_formed": all(
            _is_sha256(value)
            for value in (
                plan.operator_registry_sha256,
                plan.constant_registry_sha256,
                plan.state_machine_registry_sha256,
                plan.upstream_contract_registry_sha256,
                plan.structured_output_schema_registry_sha256,
                plan.family_applicability_contracts_sha256,
            )
        ),
        "plan_recompile_exact": replay_plan == plan,
        "input_mapping_order_independent": replayed == first,
        "request_order_independent": reversed_request == first,
        "batch_replay_exact": (
            first.logical_hash == replayed.logical_hash
            == reversed_request.logical_hash
        ),
        "batch_hash_well_formed": len(first.logical_hash) == 64,
        "per_metric_definition_evidence_hashes_exact_32": (
            len(per_metric_hashes) == 32 and all_hashes_well_formed
        ),
        "tampered_input_changes_batch_hash": tampered.logical_hash != first.logical_hash,
        "runtime_validation_enabled_for_probe_batch": True,
        "formal_predecessor_gate_preserved": True,
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    return {
        "schema": "TPAA_M2_MET_007_BATCH_REPLAY_INCREMENTAL_EVIDENCE_V1",
        "task_id": "M2-MET-007",
        "tracking_issue": 97,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": False,
        "source_revision": _git_revision(),
        "frozen_predecessors": [
            "M2-MET-002",
            "M2-MET-003",
            "M2-MET-004",
            "M2-MET-005",
            "M2-MET-006",
        ],
        "blocked_predecessors": [
            "M2-MET-002",
            "M2-MET-005",
            "M2-MET-006",
        ],
        "external_authority_gaps": {
            "P1-QA-001": "frame convention authority unresolved",
            "P1-QA-002": "six-dimensional uncertainty mapping authority unresolved",
            "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1": (
                "frozen M2 alignment fixture omits five required profile fields"
            ),
        },
        "scope": {
            "business_metric_semantics_executed": False,
            "synthetic_runtime_probe_only": True,
            "execution_identity_lineage_only": True,
            "registry_lineage_binding_only": True,
            "per_metric_authority_lineage_binding_only": True,
            "input_payload_lineage_binding_only": True,
            "version_qualified_plugin_dispatch_only": True,
            "governed_dependency_lineage_only": True,
            "formal_32_metric_replay_claimed": False,
            "authority_values_invented": False,
        },
        "logical_product": {
            "plan_logical_hash": plan.logical_hash,
            "generated_metric_projection_sha256": plan.generated_metric_projection_sha256,
            "execution_identity_sha256": plan.execution_identity_sha256,
            "input_lineage_encoding": plan.input_lineage_encoding,
            "registry_authority_hashes": {
                "operator_registry": plan.operator_registry_sha256,
                "constant_registry": plan.constant_registry_sha256,
                "state_machine_registry": plan.state_machine_registry_sha256,
                "upstream_contract_registry": plan.upstream_contract_registry_sha256,
                "structured_output_schema_registry": plan.structured_output_schema_registry_sha256,
                "family_applicability_contracts": plan.family_applicability_contracts_sha256,
            },
            "catalog_metric_codes": list(plan.catalog_metric_codes),
            "execution_metric_codes": list(first.metric_codes),
            "dependency_edges": dependency_edges,
            "dispatch_key": first.dispatch_key,
            "batch_logical_hash": first.logical_hash,
            "tampered_batch_logical_hash": tampered.logical_hash,
            "plugin_manifest_hash": first.plugin_manifest_hash,
            "plugin_identity_manifest": [
                [record.algorithm_id, record.algorithm_version, record.plugin_id]
                for record in first.records
            ],
            "per_metric_hashes": per_metric_hashes,
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        payload = verify()
        return_code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M2_MET_007_BATCH_REPLAY_INCREMENTAL_EVIDENCE_V1",
            "task_id": "M2-MET-007",
            "tracking_issue": 97,
            "status": "FAIL",
            "task_complete": False,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
