#!/usr/bin/env python3
"""M2-MET-001 Catalog-driven general Metric Engine evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path

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


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_metric import (
        CatalogMetricEngine,
        M2MetricPluginRequest,
        MetricPluginRegistry,
        build_m2_metric_execution_plan,
    )
    from tpaa_metric.operators import (
        M2_OPERATOR_IMPLEMENTATIONS,
        TimedValue,
        arithmetic_mean,
        circular_mean,
        derivative_lls,
        linear_interpolate,
        median,
        quantile_hf7,
        rms,
        wrap_pi,
    )

    def contract_probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {
            "metric_code": request.definition.metric_code,
            "algorithm_id": request.definition.algorithm_id,
            "definition_hash": request.definition.definition_hash,
            "operator_ids": sorted(request.operators),
            "input_token": request.input_payload["input_token"],
            "upstream_result_hashes": list(request.upstream_result_hashes),
        }

    plan = build_m2_metric_execution_plan(AUTHORITY_ROOT)
    replay_plan = build_m2_metric_execution_plan(AUTHORITY_ROOT)
    registry = MetricPluginRegistry()
    algorithm_identities = tuple(
        (definition.algorithm_id, definition.algorithm_version)
        for definition in plan.definitions
    )
    for algorithm_id, algorithm_version in algorithm_identities:
        registry.register(
            algorithm_id,
            algorithm_version=algorithm_version,
            plugin_id="m2-met-001-contract-probe-v1",
            plugin=contract_probe,
        )

    inputs = {
        definition.metric_code: {
            "input_token": f"M2-MET-001::{definition.metric_code}",
        }
        for definition in plan.definitions
    }
    engine = CatalogMetricEngine(plan, registry)
    first = engine.execute(inputs, validate_runtime_contract=False)
    replayed = engine.execute(inputs, validate_runtime_contract=False)

    positions = {code: index for index, code in enumerate(plan.metric_codes)}
    dependency_order_exact = all(
        positions[dependency] < positions[definition.metric_code]
        for definition in plan.definitions
        for dependency in definition.metric_dependencies
    )
    sns = tuple(
        definition
        for definition in plan.definitions
        if definition.metric_code.startswith("P1-SNS-")
    )
    family_counts = dict(Counter(definition.family for definition in plan.definitions))

    sample = (
        TimedValue(0, 0.0),
        TimedValue(1_000_000, 1.0),
        TimedValue(2_000_000, 2.0),
    )
    derivative = derivative_lls(
        sample,
        derivative_window_s=2.0,
        max_gap_us=2_000_000,
    )
    operator_probe = {
        "CIRCULAR_MEAN_V1": circular_mean(
            (math.radians(179.0), math.radians(-179.0))
        ),
        "DERIVATIVE_LLS_V1": [
            (item.session_time_us, item.value) for item in derivative
        ],
        "LINEAR_INTERPOLATION_V1": linear_interpolate(
            sample,
            500_000,
            max_gap_us=2_000_000,
        ),
        "MEAN_V1": arithmetic_mean((1.0, 2.0, 3.0)),
        "MEDIAN_V1": median((1.0, 3.0, 2.0)),
        "QUANTILE_HF7_V1": quantile_hf7((1.0, 2.0, 3.0), 0.5),
        "RMS_V1": rms((3.0, 4.0)),
        "WRAP_PI_V1": wrap_pi(math.pi),
    }

    record_logical_hash_binding_exact = all(
        record.logical_hash
        == _canonical_hash(
            {
                "metric_code": definition.metric_code,
                "semantic_id": definition.semantic_id,
                "semantic_version": definition.semantic_version,
                "definition_hash": definition.definition_hash,
                "authority_lineage_hash": definition.authority_lineage_hash,
                "plan_hash": plan.logical_hash,
                "input_lineage_encoding": plan.input_lineage_encoding,
                "input_payload_hash": record.input_payload_hash,
                "algorithm_id": definition.algorithm_id,
                "algorithm_version": definition.algorithm_version,
                "plugin_id": record.plugin_id,
                "operator_bindings": definition.operator_bindings,
                "dependency_manifest_hash": record.dependency_manifest_hash,
                "upstream_result_hashes": record.upstream_result_hashes,
                "plugin_output_hash": record.plugin_output_hash,
            }
        )
        for record, definition in zip(first.records, plan.definitions, strict=True)
    )
    plugin_manifest_hash_binding_exact = first.plugin_manifest_hash == _canonical_hash(
        [
            (record.algorithm_id, record.algorithm_version, record.plugin_id)
            for record in first.records
        ]
    )
    batch_logical_hash_binding_exact = first.logical_hash == _canonical_hash(
        {
            "plan_hash": plan.logical_hash,
            "dispatch_key": first.dispatch_key,
            "plugin_manifest_hash": first.plugin_manifest_hash,
            "record_hashes": [record.logical_hash for record in first.records],
        }
    )

    acceptance = {
        "catalog_foundation_exact_32": (
            len(plan.catalog_metric_codes) == 32
            and len(set(plan.catalog_metric_codes)) == 32
        ),
        "execution_set_exact_32": (
            len(first.records) == 32
            and first.metric_codes == plan.metric_codes
            and set(first.metric_codes) == set(plan.catalog_metric_codes)
        ),
        "delivery_metadata_exact": (
            plan.delivery_milestone == "M2"
            and plan.delivery_batch == "P1_FOUNDATION_32"
        ),
        "family_counts_exact": family_counts
        == {
            "REFERENCE_TRUTH": 3,
            "TIME_ALIGNMENT": 5,
            "AIRCRAFT_FLIGHT": 3,
            "SENSOR_DETECTION": 4,
            "SENSOR_ACCURACY": 17,
        },
        "catalog_replay_stable": plan == replay_plan,
        "execution_replay_stable": first == replayed,
        "dependency_order_exact": dependency_order_exact,
        "algorithm_plugin_coverage_exact": (
            {
                (algorithm_id, algorithm_version)
                for algorithm_id, algorithm_version, _plugin_id
                in registry.plugin_identity_manifest
            }
            == set(algorithm_identities)
            and len(algorithm_identities) == 32
        ),
        "version_qualified_plugin_dispatch": (
            len(first.plugin_manifest_hash) == 64
            and first.plugin_manifest_hash == replayed.plugin_manifest_hash
        ),
        "single_general_plugin_mechanism": (
            set(registry.plugin_ids.values()) == {"m2-met-001-contract-probe-v1"}
        ),
        "dispatch_key_version_qualified": (
            first.dispatch_key == "algorithm_id+algorithm_version"
        ),
        "required_operator_registry_exact": (
            set(plan.required_operator_ids) == set(M2_OPERATOR_IMPLEMENTATIONS)
            and len(plan.required_operator_ids) == 8
        ),
        "all_required_operators_executed": (
            set(operator_probe) == set(plan.required_operator_ids)
        ),
        "sns_radar_applicability_exact": (
            len(sns) == 21
            and all(
                item.subject_type == "MISSION_SYSTEM_INSTANCE"
                and item.applicability.applicability_mode == "SYSTEM_TYPE_EXACT"
                and item.applicability.allowed_system_types == ("RADAR",)
                for item in sns
            )
        ),
        "input_authority_bound_exact": all(
            tuple(binding.input_field for binding in definition.input_authority_bindings)
            and set(binding.input_field for binding in definition.input_authority_bindings)
            == set(definition.input_fields)
            for definition in plan.definitions
        ),
        "input_authority_semantics_exact": all(
            binding.metric_semantic_id == definition.semantic_id
            and binding.optional == binding.input_field.endswith("?")
            for definition in plan.definitions
            for binding in definition.input_authority_bindings
        ),
        "input_authority_hash_bound": len(plan.input_authority_matrix_sha256) == 64,
        "source_provenance_hash_bound": len(plan.source_provenance_sha256) == 64,
        "world_capability_registry_hash_bound": (
            len(plan.world_capability_registry_sha256) == 64
        ),
        "definition_hashes_complete": all(
            len(definition.definition_hash) == 64 for definition in plan.definitions
        ),
        "generated_metric_projection_hash_bound": (
            len(plan.generated_metric_projection_sha256) == 64
        ),
        "governed_formula_dependency_closure_exact_32": all(
            len(definition.operator_bindings) == len(set(definition.operator_bindings))
            and len(definition.constant_bindings) == len(set(definition.constant_bindings))
            and len(definition.upstream_dependencies)
            == len(set(definition.upstream_dependencies))
            and len(definition.state_machine_bindings)
            == len(set(definition.state_machine_bindings))
            for definition in plan.definitions
        ),
        "record_hashes_complete": all(
            len(record.logical_hash) == 64
            and len(record.plugin_output_hash) == 64
            and len(record.dependency_manifest_hash) == 64
            and len(record.plan_hash) == 64
            for record in first.records
        ),
        "record_plan_hash_binding_exact_32": all(
            record.plan_hash == plan.logical_hash for record in first.records
        ),
        "record_logical_hash_binding_exact_32": record_logical_hash_binding_exact,
        "plugin_manifest_hash_binding_exact": plugin_manifest_hash_binding_exact,
        "batch_logical_hash_binding_exact": batch_logical_hash_binding_exact,
        "record_dependency_manifest_hashes_exact_32": all(
            record.dependency_manifest_hash
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
            for record, definition in zip(first.records, plan.definitions, strict=True)
        ),
    }
    failed_acceptance = sorted(
        key for key, passed in acceptance.items() if not bool(passed)
    )
    logical_product = {
        "catalog_id": plan.catalog_id,
        "catalog_version": plan.catalog_version,
        "catalog_sha256": plan.catalog_sha256,
        "generated_metric_projection_sha256": plan.generated_metric_projection_sha256,
        "input_authority_matrix_sha256": plan.input_authority_matrix_sha256,
        "source_provenance_sha256": plan.source_provenance_sha256,
        "world_capability_registry_sha256": plan.world_capability_registry_sha256,
        "db_schema_version": plan.db_schema_version,
        "delivery_milestone": plan.delivery_milestone,
        "delivery_batch": plan.delivery_batch,
        "catalog_metric_codes": list(plan.catalog_metric_codes),
        "execution_metric_codes": list(plan.metric_codes),
        "definition_hashes": [
            [definition.metric_code, definition.definition_hash]
            for definition in plan.definitions
        ],
        "formula_dependency_references": {
            definition.metric_code: [
                list(item) for item in definition.formula_dependency_references
            ]
            for definition in plan.definitions
            if definition.formula_dependency_references
        },
        "input_authority_bindings": [
            [
                definition.metric_code,
                [
                    [
                        binding.metric_semantic_id,
                        binding.input_field,
                        binding.binding_kind,
                        binding.authority_id,
                        binding.authority_field,
                        binding.optional,
                    ]
                    for binding in definition.input_authority_bindings
                ],
            ]
            for definition in plan.definitions
        ],
        "dependency_edges": [
            [dependency, definition.metric_code]
            for definition in plan.definitions
            for dependency in definition.metric_dependencies
        ],
        "family_counts": family_counts,
        "required_operator_ids": list(plan.required_operator_ids),
        "operator_probe": operator_probe,
        "plan_logical_hash": plan.logical_hash,
        "record_plan_hashes": sorted({record.plan_hash for record in first.records}),
        "execution_logical_hash": first.logical_hash,
        "plugin_manifest_hash": first.plugin_manifest_hash,
        "plugin_identity_manifest": [list(item) for item in registry.plugin_identity_manifest],
        "dispatch_key": first.dispatch_key,
        "plugin_id": "m2-met-001-contract-probe-v1",
    }
    return {
        "schema": "TPAA_M2_MET_001_GENERAL_ENGINE_EVIDENCE_V1",
        "task_id": "M2-MET-001",
        "tracking_issue": 97,
        "status": "PASS" if not failed_acceptance else "FAIL",
        "source_revision": _git_revision(),
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed_acceptance,
        "scope": {
            "business_metric_semantics_executed": False,
            "purpose": (
                "Prove Catalog compilation, deterministic dependency ordering, "
                "governed operator resolution and one algorithm-plugin dispatch "
                "mechanism. M2-MET-002..005 own business Metric implementations."
            ),
            "family_specific_engine_created": False,
            "database_persistence_executed": False,
            "observation_projection_executed": False,
            "publication_executed": False,
        },
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
            "schema": "TPAA_M2_MET_001_GENERAL_ENGINE_EVIDENCE_V1",
            "task_id": "M2-MET-001",
            "tracking_issue": 97,
            "status": "FAIL",
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2

    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
