#!/usr/bin/env python3
"""M3-MET-009 116-metric runtime/schema/replay closure evidence.

Family business semantics are owned by the already-qualified M3-MET-002..008
(and M2 foundation) predecessors. This task closes the integrated runtime
contract: exact plugin coverage, applicability, value slots, all nine structured
schemas, dependency/output hash binding, and deterministic cross-platform replay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
TRACKING_ISSUE = 114
EXPECTED_STRUCTURED_CODES = {
    "P1-QA-001",
    "P1-QA-002",
    "P1-QA-006",
    "P1-AIR-007",
    "P1-AIR-019",
    "P1-AIR-025",
    "P1-AIR-030",
    "P1-AIR-035",
    "P1-AIR-039",
}
EXPECTED_M3_STRUCTURED_CODES = {
    "P1-AIR-007",
    "P1-AIR-019",
    "P1-AIR-025",
    "P1-AIR-030",
    "P1-AIR-035",
    "P1-AIR-039",
}
EXPECTED_APPLICABILITY_MODE_COUNTS = {
    "QUALITY_FOUNDATION": 8,
    "SUBJECT_TYPE": 39,
    "SYSTEM_TYPE_EXACT": 37,
    "SYSTEM_TYPE_SET": 13,
    "PRODUCT_CAPABILITY": 19,
}


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


def _load(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{path}: root must be string-keyed object")
    return cast(dict[str, object], raw)


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be a string-keyed object")
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
        if (
            isinstance(min_items, bool)
            or not isinstance(min_items, int)
            or min_items < 0
        ):
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
        if schema.get("pattern") == "^-?[0-9]+$":
            return "0"
        return "PROBE"
    if primary == "boolean":
        return False
    raise ValueError(f"{field}: unsupported schema type {primary!r}")


def _positive_input(definition: object) -> dict[str, object]:
    from tpaa_metric.catalog_engine import M2MetricDefinition

    if not isinstance(definition, M2MetricDefinition):
        raise TypeError("definition must be M2MetricDefinition")
    applicability = definition.applicability
    payload: dict[str, object] = {
        "probe_token": f"M3-MET-009::{definition.metric_code}",
    }
    if applicability.applicability_mode in {"SYSTEM_TYPE_EXACT", "SYSTEM_TYPE_SET"}:
        if not applicability.allowed_system_types:
            raise ValueError(
                f"{definition.metric_code}: no applicable system type"
            )
        payload["system_type"] = applicability.allowed_system_types[0]
    elif applicability.applicability_mode == "PRODUCT_CAPABILITY":
        required = applicability.required_product_semantics
        if required is None:
            raise ValueError(
                f"{definition.metric_code}: product capability unresolved"
            )
        payload["product_semantics"] = [required]
    return payload


def _structured_value(definition: object) -> object:
    from tpaa_metric.catalog_engine import M2MetricDefinition

    if not isinstance(definition, M2MetricDefinition):
        raise TypeError("definition must be M2MetricDefinition")
    if definition.structured_output_schema_json is None:
        raise ValueError(f"{definition.metric_code}: structured schema missing")
    raw: object = json.loads(definition.structured_output_schema_json)
    schema = _mapping(raw, field=definition.metric_code)
    return _schema_probe_value(schema, field=definition.metric_code)


def _runtime_probe_output(
    definition: object,
    input_payload: Mapping[str, object],
    upstream_result_hashes: Sequence[tuple[str, str]],
) -> dict[str, object]:
    from tpaa_metric.catalog_engine import M2MetricDefinition

    if not isinstance(definition, M2MetricDefinition):
        raise TypeError("definition must be M2MetricDefinition")

    numeric: float | None = None
    structured: object | None = None
    if definition.value_kind == "NUMERIC":
        numeric = 1.0
    elif definition.value_kind == "STRUCTURED":
        structured = _structured_value(definition)
    else:
        raise ValueError(
            f"{definition.metric_code}: unsupported value kind {definition.value_kind}"
        )

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
                "evidence": {
                    "probe_token": input_payload.get("probe_token"),
                    "upstream_result_hashes": [
                        [code, digest]
                        for code, digest in upstream_result_hashes
                    ],
                },
            }
        ],
    }


def _negative_applicability_input(
    definition: object,
) -> dict[str, object] | None:
    from tpaa_metric.catalog_engine import M2MetricDefinition

    if not isinstance(definition, M2MetricDefinition):
        raise TypeError("definition must be M2MetricDefinition")
    applicability = definition.applicability
    if applicability.applicability_mode in {"SYSTEM_TYPE_EXACT", "SYSTEM_TYPE_SET"}:
        negative = next(
            (
                system_type
                for system_type in definition.allowed_mission_system_types
                if system_type not in applicability.allowed_system_types
            ),
            None,
        )
        if negative is None:
            raise ValueError(
                f"{definition.metric_code}: no negative mission system type"
            )
        return {"system_type": negative}
    if applicability.applicability_mode == "PRODUCT_CAPABILITY":
        return {"product_semantics": []}
    return None


def _not_applicable_output(definition: object) -> dict[str, object]:
    from tpaa_metric.catalog_engine import M2MetricDefinition

    if not isinstance(definition, M2MetricDefinition):
        raise TypeError("definition must be M2MetricDefinition")
    return {
        "metric_code": definition.metric_code,
        "subject_type": definition.subject_type,
        "observation_lane": definition.observation_lane,
        "publication_route": definition.publication_route,
        "applicable": False,
        "instances": [],
    }


def _applicability_contract_exact(definition: object) -> bool:
    from tpaa_metric.catalog_engine import M2MetricDefinition

    if not isinstance(definition, M2MetricDefinition):
        return False
    prefix = "-".join(definition.metric_code.split("-")[:2])
    applicability = definition.applicability
    if applicability.key != f"{prefix}-*":
        return False
    if prefix == "P1-QA":
        return (
            applicability.applicability_mode == "QUALITY_FOUNDATION"
            and applicability.subject_type == "MIXED"
        )
    if prefix == "P1-AIR":
        return (
            applicability.applicability_mode == "SUBJECT_TYPE"
            and applicability.subject_type == "AIRCRAFT"
            and definition.subject_type == "AIRCRAFT"
        )
    return (
        applicability.subject_type == "MISSION_SYSTEM_INSTANCE"
        and definition.subject_type == "MISSION_SYSTEM_INSTANCE"
        and applicability.applicability_mode
        in {"SYSTEM_TYPE_EXACT", "SYSTEM_TYPE_SET", "PRODUCT_CAPABILITY"}
    )


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_metric import (
        M3_RUNTIME_METRIC_COUNT,
        M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
        CatalogMetricEngine,
        M2MetricPluginRequest,
        MetricPluginRegistry,
        build_m3_metric_execution_plan,
        build_m3_runtime_plugin_registry,
        validate_m2_runtime_output,
    )

    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    replay_plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)

    actual_registry = build_m3_runtime_plugin_registry(plan)
    actual_plugins: list[list[str]] = []
    for definition in plan.definitions:
        plugin_id, _plugin = actual_registry.resolve(
            definition.algorithm_id,
            definition.algorithm_version,
        )
        actual_plugins.append([definition.metric_code, plugin_id])

    probe_registry = MetricPluginRegistry()

    def runtime_probe(request: M2MetricPluginRequest) -> Mapping[str, object]:
        return _runtime_probe_output(
            request.definition,
            request.input_payload,
            request.upstream_result_hashes,
        )

    for definition in plan.definitions:
        probe_registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m3-met-009-runtime-probe:{definition.metric_code}:v1",
            plugin=runtime_probe,
        )

    inputs: dict[str, Mapping[str, object]] = {
        definition.metric_code: _positive_input(definition)
        for definition in plan.definitions
    }
    engine = CatalogMetricEngine(
        plan,
        probe_registry,
        operator_implementations=M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
    )
    first = engine.execute(inputs)
    replay = engine.execute(dict(reversed(tuple(inputs.items()))))
    reverse_request = engine.execute(
        inputs,
        metric_codes=tuple(reversed(plan.metric_codes)),
    )

    tampered_inputs = dict(inputs)
    qa001 = dict(tampered_inputs["P1-QA-001"])
    qa001["probe_token"] = "M3-MET-009::P1-QA-001::MUTATED"
    tampered_inputs["P1-QA-001"] = qa001
    tampered = engine.execute(tampered_inputs)

    record_by_code = {record.metric_code: record for record in first.records}
    tampered_by_code = {
        record.metric_code: record for record in tampered.records
    }

    negative_codes: list[str] = []
    for definition in plan.definitions:
        negative_input = _negative_applicability_input(definition)
        if negative_input is None:
            continue
        validate_m2_runtime_output(
            definition,
            negative_input,
            _not_applicable_output(definition),
        )
        negative_codes.append(definition.metric_code)

    structured = tuple(
        definition
        for definition in plan.definitions
        if definition.value_kind == "STRUCTURED"
    )
    structured_codes = {definition.metric_code for definition in structured}
    m3_structured_codes = {
        definition.metric_code
        for definition in structured
        if definition.metric_code.startswith("P1-AIR-")
    }
    structured_schema_hashes = {
        definition.metric_code: definition.structured_output_schema_hash_sha256
        for definition in structured
    }
    structured_hashes_exact = all(
        definition.structured_output_schema_json is not None
        and definition.structured_output_schema_hash_sha256 is not None
        and hashlib.sha256(
            definition.structured_output_schema_json.encode("utf-8")
        ).hexdigest()
        == definition.structured_output_schema_hash_sha256
        for definition in structured
    )

    dependency_manifest_exact = all(
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
    upstream_hashes_exact = all(
        record_by_code[definition.metric_code].upstream_result_hashes
        == tuple(
            (
                dependency,
                record_by_code[dependency].logical_hash,
            )
            for dependency in definition.metric_dependencies
        )
        for definition in plan.definitions
    )
    plugin_output_hashes_exact = all(
        record_by_code[definition.metric_code].plugin_output_hash
        == _canonical_hash(
            _runtime_probe_output(
                definition,
                inputs[definition.metric_code],
                record_by_code[definition.metric_code].upstream_result_hashes,
            )
        )
        for definition in plan.definitions
    )
    record_hashes_exact = all(
        record_by_code[definition.metric_code].logical_hash
        == _canonical_hash(
            {
                "metric_code": definition.metric_code,
                "semantic_id": definition.semantic_id,
                "semantic_version": definition.semantic_version,
                "definition_hash": definition.definition_hash,
                "authority_lineage_hash": definition.authority_lineage_hash,
                "plan_hash": plan.logical_hash,
                "input_lineage_encoding": plan.input_lineage_encoding,
                "input_payload_hash": record_by_code[
                    definition.metric_code
                ].input_payload_hash,
                "algorithm_id": definition.algorithm_id,
                "algorithm_version": definition.algorithm_version,
                "plugin_id": record_by_code[definition.metric_code].plugin_id,
                "operator_bindings": definition.operator_bindings,
                "dependency_manifest_hash": record_by_code[
                    definition.metric_code
                ].dependency_manifest_hash,
                "upstream_result_hashes": record_by_code[
                    definition.metric_code
                ].upstream_result_hashes,
                "plugin_output_hash": record_by_code[
                    definition.metric_code
                ].plugin_output_hash,
            }
        )
        for definition in plan.definitions
    )
    plugin_manifest_hash_exact = first.plugin_manifest_hash == _canonical_hash(
        [
            (
                record.algorithm_id,
                record.algorithm_version,
                record.plugin_id,
            )
            for record in first.records
        ]
    )
    batch_hash_exact = first.logical_hash == _canonical_hash(
        {
            "plan_hash": plan.logical_hash,
            "dispatch_key": first.dispatch_key,
            "plugin_manifest_hash": first.plugin_manifest_hash,
            "record_hashes": [record.logical_hash for record in first.records],
        }
    )

    expected_mutated_codes = {"P1-QA-001"}
    changed = True
    while changed:
        changed = False
        for definition in plan.definitions:
            if definition.metric_code in expected_mutated_codes:
                continue
            if any(
                dependency in expected_mutated_codes
                for dependency in definition.metric_dependencies
            ):
                expected_mutated_codes.add(definition.metric_code)
                changed = True
    actual_mutated_codes = {
        code
        for code in plan.metric_codes
        if record_by_code[code].logical_hash
        != tampered_by_code[code].logical_hash
    }

    applicability_mode_counts = dict(
        sorted(
            Counter(
                definition.applicability.applicability_mode
                for definition in plan.definitions
            ).items()
        )
    )
    value_kind_counts = dict(
        sorted(Counter(definition.value_kind for definition in plan.definitions).items())
    )
    dependency_edges = [
        [dependency, definition.metric_code]
        for definition in plan.definitions
        for dependency in definition.metric_dependencies
    ]
    per_metric_hashes = [
        {
            "metric_code": definition.metric_code,
            "definition_hash": definition.definition_hash,
            "authority_lineage_hash": definition.authority_lineage_hash,
            "input_payload_hash": record_by_code[
                definition.metric_code
            ].input_payload_hash,
            "dependency_manifest_hash": record_by_code[
                definition.metric_code
            ].dependency_manifest_hash,
            "plugin_output_hash": record_by_code[
                definition.metric_code
            ].plugin_output_hash,
            "record_logical_hash": record_by_code[
                definition.metric_code
            ].logical_hash,
        }
        for definition in plan.definitions
    ]
    hashes_well_formed = all(
        _is_sha256(item[key])
        for item in per_metric_hashes
        for key in (
            "definition_hash",
            "authority_lineage_hash",
            "input_payload_hash",
            "dependency_manifest_hash",
            "plugin_output_hash",
            "record_logical_hash",
        )
    )

    acceptance = {
        "integrated_plan_exact_116": (
            len(plan.definitions) == M3_RUNTIME_METRIC_COUNT == 116
            and len(set(plan.metric_codes)) == 116
        ),
        "actual_business_plugin_registry_exact_116": (
            len(actual_registry.plugin_identity_manifest) == 116
            and len(actual_plugins) == 116
        ),
        "all_actual_plugins_version_resolved": (
            len({code for code, _plugin_id in actual_plugins}) == 116
            and all(plugin_id for _code, plugin_id in actual_plugins)
        ),
        "runtime_operator_coverage_complete": (
            set(plan.required_operator_ids)
            <= set(M3_RUNTIME_OPERATOR_IMPLEMENTATIONS)
        ),
        "applicability_contracts_exact_116": all(
            _applicability_contract_exact(definition)
            for definition in plan.definitions
        ),
        "applicability_mode_counts_exact": (
            applicability_mode_counts == EXPECTED_APPLICABILITY_MODE_COUNTS
        ),
        "negative_applicability_fail_closed_exact_69": (
            len(negative_codes) == 69
            and len(set(negative_codes)) == 69
        ),
        "value_kind_counts_exact_107_numeric_9_structured": (
            value_kind_counts == {"NUMERIC": 107, "STRUCTURED": 9}
        ),
        "structured_metric_codes_exact_9": (
            structured_codes == EXPECTED_STRUCTURED_CODES
        ),
        "m3_structured_metric_codes_exact_6": (
            m3_structured_codes == EXPECTED_M3_STRUCTURED_CODES
        ),
        "structured_schema_hashes_exact_9": (
            structured_hashes_exact and len(structured_schema_hashes) == 9
        ),
        "runtime_validation_executes_exact_116": (
            len(first.records) == 116 and first.metric_codes == plan.metric_codes
        ),
        "dependency_manifest_hash_binding_exact_116": dependency_manifest_exact,
        "upstream_result_hash_binding_exact_116": upstream_hashes_exact,
        "plugin_output_hash_binding_exact_116": plugin_output_hashes_exact,
        "record_logical_hash_binding_exact_116": record_hashes_exact,
        "plugin_manifest_hash_binding_exact": plugin_manifest_hash_exact,
        "batch_logical_hash_binding_exact": batch_hash_exact,
        "all_runtime_hashes_well_formed": hashes_well_formed,
        "plan_recompile_exact": plan == replay_plan,
        "input_mapping_order_independent": replay == first,
        "request_order_independent": reverse_request == first,
        "deterministic_replay_exact": (
            first.logical_hash
            == replay.logical_hash
            == reverse_request.logical_hash
        ),
        "input_mutation_propagates_exact_transitive_dependents": (
            actual_mutated_codes == expected_mutated_codes
        ),
        "input_mutation_changes_batch_hash": (
            tampered.logical_hash != first.logical_hash
        ),
    }
    failed = sorted(key for key, passed in acceptance.items() if not bool(passed))

    logical_product = {
        "catalog_version": plan.catalog_version,
        "catalog_sha256": plan.catalog_sha256,
        "db_schema_version": plan.db_schema_version,
        "metric_codes": list(plan.metric_codes),
        "applicability_mode_counts": applicability_mode_counts,
        "value_kind_counts": value_kind_counts,
        "structured_metric_codes": sorted(structured_codes),
        "m3_structured_metric_codes": sorted(m3_structured_codes),
        "structured_schema_hashes": dict(sorted(structured_schema_hashes.items())),
        "required_operator_ids": list(plan.required_operator_ids),
        "actual_plugin_ids": actual_plugins,
        "dependency_edges": dependency_edges,
        "plan_logical_hash": plan.logical_hash,
        "plugin_manifest_hash": first.plugin_manifest_hash,
        "batch_logical_hash": first.logical_hash,
        "mutation_batch_logical_hash": tampered.logical_hash,
        "mutation_expected_changed_codes": sorted(expected_mutated_codes),
        "mutation_actual_changed_codes": sorted(actual_mutated_codes),
        "negative_applicability_codes": sorted(negative_codes),
        "per_metric_hashes": per_metric_hashes,
    }
    return {
        "schema": "TPAA_M3_MET_009_RUNTIME_CLOSURE_EVIDENCE_V1",
        "task_id": "M3-MET-009",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": _git_revision(),
        "task_complete": not failed,
        "implementation_complete": not failed,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "integrated_runtime_contract_exact_116": True,
            "actual_business_plugin_registry_coverage_checked": True,
            "runtime_probe_uses_shared_catalog_engine": True,
            "business_metric_semantics_requalified": False,
            "business_semantics_owned_by_predecessors": [
                "M2 foundation qualification",
                "M3-MET-002",
                "M3-MET-003",
                "M3-MET-004",
                "M3-MET-005",
                "M3-MET-006",
                "M3-MET-007",
                "M3-MET-008",
            ],
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
        "windows_task_complete": windows.get("task_complete") is True,
        "linux_task_complete": linux.get("task_complete") is True,
        "windows_revision_exact": windows.get("source_revision") == expected_revision,
        "linux_revision_exact": linux.get("source_revision") == expected_revision,
        "logical_product_equal": (
            windows.get("logical_product") == linux.get("logical_product")
        ),
        "acceptance_equal": windows.get("acceptance") == linux.get("acceptance"),
        "failed_acceptance_empty": (
            windows.get("failed_acceptance") == []
            and linux.get("failed_acceptance") == []
        ),
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    return {
        "schema": "TPAA_M3_MET_009_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": "M3-MET-009",
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
    rendered = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
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
            "schema": "TPAA_M3_MET_009_RUNTIME_CLOSURE_EVIDENCE_V1",
            "task_id": "M3-MET-009",
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
