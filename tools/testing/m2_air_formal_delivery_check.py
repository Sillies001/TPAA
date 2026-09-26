#!/usr/bin/env python3
"""Exact M2-MET-003 AIR formal-delivery evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import MappingProxyType
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = str(REPO_ROOT / "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from tpaa_context import resolve_evaluation_context  # noqa: E402
from tpaa_generated.dto import EvaluationContextDTO  # noqa: E402
from tpaa_metric import (  # noqa: E402
    AIR_M1_IMPLEMENTATION,
    AIR_M2_FORMAL_CODES,
    CatalogMetricEngine,
    M2AirFormalDelivery,
    M2MetricExecutionPlan,
    M2MetricPluginRequest,
    MetricContext,
    MetricPluginRegistry,
    build_m2_air_formal_delivery,
    build_m2_metric_execution_plan,
    build_metric_context,
    register_m2_air_plugins,
)
from tpaa_metric.operators import M2_OPERATOR_IMPLEMENTATIONS  # noqa: E402
from tpaa_observation import (  # noqa: E402
    AircraftPublicationIdentity,
    SessionRelease,
    build_session_release,
    compare_replay,
)
from tpaa_world import AircraftObservedWorld, project_minimal_p1_world  # noqa: E402

AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m1"
RELEASE_IDS = {
    "nominal": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3",
    "wrap": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa4",
    "gap": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa5",
    "stage": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa6",
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


def _runtime(
    fixture_id: str,
    *,
    release_id: str,
    stage_id: str | None = None,
) -> tuple[Path, AircraftObservedWorld, MetricContext, M2AirFormalDelivery]:
    bundle = FIXTURE_ROOT / fixture_id
    world = project_minimal_p1_world(
        bundle,
        authority_root=AUTHORITY_ROOT,
        release_id=release_id,
    )
    context = build_metric_context(
        bundle,
        authority_root=AUTHORITY_ROOT,
        world=world,
    )
    return (
        bundle,
        world,
        context,
        build_m2_air_formal_delivery(context, world, stage_id=stage_id),
    )


def _direct_outputs(
    delivery: M2AirFormalDelivery,
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
) -> dict[str, dict[str, object]]:
    outputs: dict[str, dict[str, object]] = {}
    for code in AIR_M2_FORMAL_CODES:
        definition = plan.definition(code)
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
        outputs[code] = dict(
            plugin(
                M2MetricPluginRequest(
                    definition=definition,
                    input_payload=delivery.engine_inputs[code],
                    upstream_result_hashes=(),
                    operators=operators,
                )
            )
        )
    return outputs


def _details(output: Mapping[str, object]) -> dict[str, str]:
    evidence = output.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("M2_AIR_EVIDENCE_INVALID")
    raw = evidence.get("details")
    if not isinstance(raw, list):
        raise ValueError("M2_AIR_EVIDENCE_DETAILS_INVALID")
    result: dict[str, str] = {}
    for item in raw:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not all(isinstance(value, str) for value in item)
        ):
            raise ValueError("M2_AIR_EVIDENCE_DETAILS_INVALID")
        result[cast(str, item[0])] = cast(str, item[1])
    return result


def _evidence_ref_classes(output: Mapping[str, object]) -> set[str]:
    evidence = output.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("M2_AIR_EVIDENCE_INVALID")
    refs = evidence.get("refs")
    if not isinstance(refs, list):
        raise ValueError("M2_AIR_EVIDENCE_REFS_INVALID")
    classes: set[str] = set()
    for ref in refs:
        if not isinstance(ref, dict) or not isinstance(ref.get("ref_class"), str):
            raise ValueError("M2_AIR_EVIDENCE_REFS_INVALID")
        classes.add(cast(str, ref["ref_class"]))
    return classes


def _release(
    bundle: Path,
    world: AircraftObservedWorld,
    context: MetricContext,
    delivery: M2AirFormalDelivery,
) -> tuple[SessionRelease, str]:
    resolved = resolve_evaluation_context(bundle, authority_root=AUTHORITY_ROOT)
    snapshot: EvaluationContextDTO = {
        "context_id": resolved.context_id,
        "session_id": resolved.session_id,
        "context_version": resolved.context_version,
        "revision_no": resolved.revision_no,
        "rule_set_version": resolved.rule_set_version,
        "metric_profile_version": resolved.metric_profile_version,
        "status": resolved.status,
    }
    release = build_session_release(
        release_id=world.release_id,
        request_hash=hashlib.sha256(b"M2-MET-003").hexdigest(),
        release_no=1,
        parent_release_id=None,
        context=context,
        context_version=resolved.context_version,
        context_projection=snapshot,
        world=world,
        batch=delivery.metric_batch,
        identity=AircraftPublicationIdentity(
            aircraft_id=world.aircraft_id,
            aircraft_model_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1",
            aircraft_instance_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2",
            subject_entity_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb3",
            capability_dimension="AIRCRAFT_FLIGHT",
            capability_type="BASIC_FLIGHT",
        ),
    )
    return release, resolved.context_version


def _release_immutable(release: SessionRelease) -> bool:
    try:
        release.status = "MUTATED"  # type: ignore[misc]
    except FrozenInstanceError:
        return True
    return False


def verify() -> dict[str, object]:
    plan = build_m2_metric_execution_plan(AUTHORITY_ROOT)
    registry = MetricPluginRegistry()
    register_m2_air_plugins(plan, registry)
    engine = CatalogMetricEngine(plan, registry)

    bundle, world, context, nominal = _runtime(
        "BF_M1_NOMINAL_V1",
        release_id=RELEASE_IDS["nominal"],
    )
    nominal_outputs = _direct_outputs(nominal, plan, registry)
    first = engine.execute(nominal.engine_inputs, metric_codes=AIR_M2_FORMAL_CODES)
    replayed = engine.execute(nominal.engine_inputs, metric_codes=AIR_M2_FORMAL_CODES)
    records = {record.metric_code: record for record in first.records}

    _, _, _, wrap = _runtime(
        "BF_M1_ANGLE_WRAP_V1",
        release_id=RELEASE_IDS["wrap"],
    )
    wrap_outputs = _direct_outputs(wrap, plan, registry)
    _, _, _, gap = _runtime(
        "BF_M1_GAP_V1",
        release_id=RELEASE_IDS["gap"],
    )
    gap_outputs = _direct_outputs(gap, plan, registry)

    stage_bundle = FIXTURE_ROOT / "BF_M1_STAGE_BOUNDARY_V1"
    stage_world = project_minimal_p1_world(
        stage_bundle,
        authority_root=AUTHORITY_ROOT,
        release_id=RELEASE_IDS["stage"],
    )
    stage_context = build_metric_context(
        stage_bundle,
        authority_root=AUTHORITY_ROOT,
        world=stage_world,
    )
    setup = build_m2_air_formal_delivery(
        stage_context,
        stage_world,
        stage_id=stage_world.stages[0].stage_id,
    )
    execution = build_m2_air_formal_delivery(
        stage_context,
        stage_world,
        stage_id=stage_world.stages[1].stage_id,
    )
    setup_outputs = _direct_outputs(setup, plan, registry)
    execution_outputs = _direct_outputs(execution, plan, registry)

    rows = list(world.canonical_rows)
    rows[6] = replace(rows[6], nz_g=99.0, quality_mask=1)
    invalid_nz = build_m2_air_formal_delivery(
        context,
        replace(world, canonical_rows=tuple(rows)),
    )
    invalid_nz_output = _direct_outputs(invalid_nz, plan, registry)["P1-AIR-002"]

    release, context_version = _release(bundle, world, context, nominal)
    release_codes = tuple(item.metric_code for item in release.definitions)
    replay = compare_replay(
        release,
        context=context,
        context_version=context_version,
        world=world,
        batch=nominal.metric_batch,
    )

    expected_catalog = {
        "P1-AIR-001": (
            "tpaa.p1.air.max_abs_body_roll_rate",
            "alg.tpaa.p1.air.max_abs_body_roll_rate",
            "1.0.1",
            "rad/s",
        ),
        "P1-AIR-002": (
            "tpaa.p1.air.max_nz",
            "alg.tpaa.p1.air.max_nz",
            "1.0.1",
            "g",
        ),
        "P1-AIR-003": (
            "tpaa.p1.air.true_heading_rate",
            "alg.tpaa.p1.air.true_heading_rate",
            "1.0.0",
            "rad/s",
        ),
    }
    catalog_exact = all(
        (definition := plan.definition(code)).semantic_id == expected[0]
        and definition.algorithm_id == expected[1]
        and definition.algorithm_version == expected[2]
        and definition.unit == expected[3]
        and definition.subject_type == "AIRCRAFT"
        and definition.value_kind == "NUMERIC"
        and definition.structured_output_schema_id is None
        and definition.observation_lane == "AIRCRAFT_CAP_L1_OBSERVATION"
        and definition.publication_route == "CAPABILITY_OBSERVATION"
        for code, expected in expected_catalog.items()
    )
    release_definition_by_code = {item.metric_code: item for item in release.definitions}
    release_catalog_exact = all(
        release_definition_by_code[code].semantic_id == plan.definition(code).semantic_id
        and release_definition_by_code[code].semantic_version
        == plan.definition(code).semantic_version
        and release_definition_by_code[code].algorithm_id == plan.definition(code).algorithm_id
        and release_definition_by_code[code].algorithm_version
        == plan.definition(code).algorithm_version
        and release_definition_by_code[code].subject_type == plan.definition(code).subject_type
        and release_definition_by_code[code].unit == plan.definition(code).unit
        and release_definition_by_code[code].value_kind == plan.definition(code).value_kind
        and release_definition_by_code[code].structured_output_schema_id
        == plan.definition(code).structured_output_schema_id
        and release_definition_by_code[code].observation_lane
        == plan.definition(code).observation_lane
        and release_definition_by_code[code].publication_route
        == plan.definition(code).publication_route
        for code in AIR_M2_FORMAL_CODES
    )

    required_refs = {
        "EVALUATION_CONTEXT",
        "CANONICAL",
        "EPISODE",
        "STAGE",
        "WORLD",
        "EVIDENCE",
    }
    acceptance = {
        "catalog_air_membership_exact_3": (
            tuple(code for code in plan.catalog_metric_codes if code.startswith("P1-AIR-"))
            == AIR_M2_FORMAL_CODES
        ),
        "m2_delivery_membership_exact_no_remainder": (
            tuple(result.metric_code for result in nominal.metric_batch.results)
            == AIR_M2_FORMAL_CODES
            and "P1-AIR-004" not in nominal.engine_inputs
            and "P1-AIR-007" not in nominal.engine_inputs
        ),
        "catalog_definition_contract_exact": catalog_exact,
        "shared_engine_algorithm_dispatch_exact": (
            first.metric_codes == AIR_M2_FORMAL_CODES
            and first.dispatch_key == "algorithm_id+algorithm_version"
            and set(registry.plugin_ids)
            == {plan.definition(code).algorithm_id for code in AIR_M2_FORMAL_CODES}
            and {
                (algorithm_id, algorithm_version)
                for algorithm_id, algorithm_version, _plugin_id
                in registry.plugin_identity_manifest
            }
            == {
                (
                    plan.definition(code).algorithm_id,
                    plan.definition(code).algorithm_version,
                )
                for code in AIR_M2_FORMAL_CODES
            }
        ),
        "m1_implementation_reused_no_air_formula_copy": all(
            output.get("implementation_reuse") == AIR_M1_IMPLEMENTATION
            for output in nominal_outputs.values()
        ),
        "engine_plugin_outputs_match_reused_results": all(
            records[code].plugin_output_hash == _canonical_hash(nominal_outputs[code])
            for code in AIR_M2_FORMAL_CODES
        ),
        "engine_replay_deterministic": first == replayed,
        "air_001_nominal_golden": math.isclose(
            cast(float, nominal_outputs["P1-AIR-001"]["value_numeric"]),
            0.6,
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
        "air_001_gap_fails_closed": (
            gap_outputs["P1-AIR-001"].get("status") == "INSUFFICIENT_DATA"
            and gap_outputs["P1-AIR-001"].get("reason_codes") == ["MAX_GAP_EXCEEDED"]
        ),
        "air_001_stage_boundary_exact": (
            setup_outputs["P1-AIR-001"].get("value_numeric") == 0.5
            and execution_outputs["P1-AIR-001"].get("value_numeric") == 9.0
        ),
        "air_002_primary_and_diagnostic_exact": (
            nominal_outputs["P1-AIR-002"].get("value_numeric") == 2.5
            and _details(nominal_outputs["P1-AIR-002"]).get("diagnostic_min_nz_g") == "1.0"
            and invalid_nz_output.get("value_numeric") == 2.5
        ),
        "air_003_nominal_derivative_exact": (
            nominal_outputs["P1-AIR-003"].get("value_numeric") == 0.1
            and _details(nominal_outputs["P1-AIR-003"]).get("operator") == "DERIVATIVE_LLS_V1"
        ),
        "air_003_angle_unwrap_golden": math.isclose(
            cast(float, wrap_outputs["P1-AIR-003"]["value_numeric"]),
            0.03490658503988659,
            rel_tol=0.0,
            abs_tol=1e-15,
        ),
        "air_003_gap_not_bridged": (gap_outputs["P1-AIR-003"].get("value_numeric") == 0.1),
        "air_003_insufficient_window_fails_closed": (
            setup_outputs["P1-AIR-003"].get("status") == "INSUFFICIENT_DATA"
            and setup_outputs["P1-AIR-003"].get("reason_codes") == ["DERIVATIVE_UNAVAILABLE"]
        ),
        "metric_evidence_refs_exact": all(
            required_refs.issubset(_evidence_ref_classes(output))
            for output in nominal_outputs.values()
        ),
        "release_membership_exact_3": (
            release_codes == AIR_M2_FORMAL_CODES
            and tuple(item.metric_code for item in release.metric_instances) == AIR_M2_FORMAL_CODES
            and tuple(item.metric_code for item in release.observations) == AIR_M2_FORMAL_CODES
        ),
        "release_catalog_definition_exact": release_catalog_exact,
        "release_route_and_lane_exact": all(
            item.publication_route == "CAPABILITY_OBSERVATION"
            and item.observation_lane == "AIRCRAFT_CAP_L1_OBSERVATION"
            for item in release.definitions
        ),
        "release_definition_and_evidence_hashes_present": (
            all(len(item.definition_hash) == 64 for item in release.definitions)
            and all(len(item.logical_hash) == 64 for item in release.evidence_sets)
        ),
        "release_manifest_frozen_and_instance_immutable": (
            len(release.manifest_hash) == 64 and _release_immutable(release)
        ),
        "release_bound_replay_exact_no_latest": (
            replay.exact_logical_products_equal and not context.latest_fallback_used
        ),
    }
    failed_acceptance = sorted(key for key, passed in acceptance.items() if not passed)

    logical_product = {
        "delivery_membership": list(AIR_M2_FORMAL_CODES),
        "implementation_reuse": AIR_M1_IMPLEMENTATION,
        "plan_logical_hash": plan.logical_hash,
        "catalog_definition_hashes": {
            code: plan.definition(code).definition_hash for code in AIR_M2_FORMAL_CODES
        },
        "m1_batch_logical_hash": nominal.m1_batch_logical_hash,
        "m2_delivery_logical_hash": nominal.logical_hash,
        "engine_batch_logical_hash": first.logical_hash,
        "dispatch_key": first.dispatch_key,
        "engine_records": [
            {
                "metric_code": record.metric_code,
                "algorithm_id": record.algorithm_id,
                "algorithm_version": record.algorithm_version,
                "plugin_id": record.plugin_id,
                "operator_bindings": list(record.operator_bindings),
                "dependency_manifest_hash": record.dependency_manifest_hash,
                "plugin_output_hash": record.plugin_output_hash,
                "logical_hash": record.logical_hash,
            }
            for record in first.records
        ],
        "nominal_outputs": nominal_outputs,
        "angle_wrap_air_003": wrap_outputs["P1-AIR-003"],
        "gap_outputs": {code: gap_outputs[code] for code in AIR_M2_FORMAL_CODES},
        "stage_boundary_outputs": {
            "setup": setup_outputs,
            "execution": execution_outputs,
        },
        "invalid_nz_air_002": invalid_nz_output,
        "release_membership": release.logical_membership(),
        "release_definition_hashes": {
            item.metric_code: item.definition_hash for item in release.definitions
        },
        "release_evidence_hashes": {
            item.evidence_set_id: item.logical_hash for item in release.evidence_sets
        },
        "release_replay": {
            "world_equal": replay.world_equal,
            "metric_batch_equal": replay.metric_batch_equal,
            "context_equal": replay.context_equal,
            "exact_logical_products_equal": replay.exact_logical_products_equal,
        },
    }
    return {
        "schema": "TPAA_M2_MET_003_AIR_FORMAL_DELIVERY_EVIDENCE_V1",
        "task_id": "M2-MET-003",
        "tracking_issue": 97,
        "status": "PASS" if not failed_acceptance else "FAIL",
        "task_complete": not failed_acceptance,
        "source_revision": _git_revision(),
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed_acceptance,
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
            "schema": "TPAA_M2_MET_003_AIR_FORMAL_DELIVERY_EVIDENCE_V1",
            "task_id": "M2-MET-003",
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
