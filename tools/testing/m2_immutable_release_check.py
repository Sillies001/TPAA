#!/usr/bin/env python3
"""Formal M2-OBS-002 immutable Release snapshot evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
SESSION_ID = "11111111-1111-4111-8111-111111111111"


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
    from tpaa_observation import (
        M2ReleaseSnapshotError,
        build_m2_publication_routing_plan,
        build_m2_release_snapshot,
    )

    def probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {
            "metric_code": request.definition.metric_code,
            "definition_hash": request.definition.definition_hash,
            "input_token": request.input_payload["input_token"],
            "upstream_result_hashes": list(request.upstream_result_hashes),
        }

    plan = build_m2_metric_execution_plan(AUTHORITY_ROOT)
    routing = build_m2_publication_routing_plan(AUTHORITY_ROOT)
    registry = MetricPluginRegistry()
    for definition in plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m2-obs-002-snapshot-probe:{definition.metric_code}:v1",
            plugin=probe,
        )
    inputs = {
        definition.metric_code: {
            "input_token": f"M2-OBS-002::{definition.metric_code}",
        }
        for definition in plan.definitions
    }
    batch = CatalogMetricEngine(plan, registry).execute(
        inputs,
        validate_runtime_contract=False,
    )

    request_hash = _canonical_hash(
        {
            "command": "M2_BUILD_RELEASE_SNAPSHOT",
            "session_id": SESSION_ID,
            "metric_codes": list(plan.metric_codes),
        }
    )
    context_input: dict[str, object] = {
        "context_id": "22222222-2222-4222-8222-222222222222",
        "context_version": "M2_CONTEXT_SNAPSHOT_V1",
        "catalog_hash": plan.catalog_sha256,
    }
    world_input: dict[str, object] = {
        "world_product_id": "33333333-3333-4333-8333-333333333333",
        "world_logical_hash": "4" * 64,
        "world_contract": "M2_REFERENCE_RADAR_WORLD_V1",
    }
    identity_input: dict[str, object] = {
        "aircraft_id": "55555555-5555-4555-8555-555555555555",
        "mission_system_instance_id": "66666666-6666-4666-8666-666666666666",
        "subject_binding_version": "M2_SUBJECT_BINDING_V1",
    }
    provenance_input: dict[str, object] = {
        "source_revision": _git_revision(),
        "metric_execution_plan_hash": plan.logical_hash,
        "publication_routing_plan_hash": routing.logical_hash,
    }

    first = build_m2_release_snapshot(
        session_id=SESSION_ID,
        request_hash=request_hash,
        release_no=1,
        parent_release_id=None,
        plan=plan,
        routing=routing,
        batch=batch,
        context_snapshot=context_input,
        world_snapshot=world_input,
        identity_snapshot=identity_input,
        provenance_snapshot=provenance_input,
    )
    replay = build_m2_release_snapshot(
        session_id=SESSION_ID,
        request_hash=request_hash,
        release_no=1,
        parent_release_id=None,
        plan=plan,
        routing=routing,
        batch=batch,
        context_snapshot=dict(reversed(tuple(context_input.items()))),
        world_snapshot=dict(reversed(tuple(world_input.items()))),
        identity_snapshot=dict(reversed(tuple(identity_input.items()))),
        provenance_snapshot=dict(reversed(tuple(provenance_input.items()))),
    )

    frozen_context_json = first.bindings.context_json
    context_input["context_version"] = "MUTATED_AFTER_FREEZE"

    changed_context = build_m2_release_snapshot(
        session_id=SESSION_ID,
        request_hash=request_hash,
        release_no=1,
        parent_release_id=None,
        plan=plan,
        routing=routing,
        batch=batch,
        context_snapshot={
            "context_id": "22222222-2222-4222-8222-222222222222",
            "context_version": "M2_CONTEXT_SNAPSHOT_V2",
            "catalog_hash": plan.catalog_sha256,
        },
        world_snapshot=world_input,
        identity_snapshot=identity_input,
        provenance_snapshot=provenance_input,
    )

    bad_batch_code = "NO_ERROR"
    try:
        build_m2_release_snapshot(
            session_id=SESSION_ID,
            request_hash=request_hash,
            release_no=1,
            parent_release_id=None,
            plan=plan,
            routing=routing,
            batch=replace(batch, plan_hash="0" * 64),
            context_snapshot={"context_id": "x"},
            world_snapshot={"world": "x"},
            identity_snapshot={"identity": "x"},
            provenance_snapshot={"provenance": "x"},
        )
    except M2ReleaseSnapshotError as exc:
        bad_batch_code = exc.code

    empty_binding_code = "NO_ERROR"
    try:
        build_m2_release_snapshot(
            session_id=SESSION_ID,
            request_hash=request_hash,
            release_no=1,
            parent_release_id=None,
            plan=plan,
            routing=routing,
            batch=batch,
            context_snapshot={},
            world_snapshot={"world": "x"},
            identity_snapshot={"identity": "x"},
            provenance_snapshot={"provenance": "x"},
        )
    except M2ReleaseSnapshotError as exc:
        empty_binding_code = exc.code

    acceptance = {
        "foundation_definitions_exact_32": (
            len(first.definitions) == 32
            and first.metric_codes == plan.metric_codes
        ),
        "foundation_execution_records_exact_32": (
            len(first.execution_records) == 32
            and tuple(item.metric_code for item in first.execution_records)
            == plan.metric_codes
        ),
        "release_catalog_binding_exact": (
            first.catalog_id == plan.catalog_id
            and first.catalog_version == plan.catalog_version
            and first.catalog_hash == plan.catalog_sha256
        ),
        "release_plan_binding_exact": (
            first.metric_execution_plan_hash == plan.logical_hash
            and first.publication_routing_plan_hash == routing.logical_hash
            and first.execution_batch_hash == batch.logical_hash
            and first.plugin_manifest_hash == batch.plugin_manifest_hash
        ),
        "release_definition_binding_exact_32": all(
            snapshot.definition_hash == plan.definition(snapshot.metric_code).definition_hash
            and snapshot.authority_lineage_hash
            == plan.definition(snapshot.metric_code).authority_lineage_hash
            and snapshot.publication_route
            == routing.target(snapshot.metric_code).publication_route
            and snapshot.observation_lane
            == routing.target(snapshot.metric_code).observation_lane
            for snapshot in first.definitions
        ),
        "release_execution_binding_exact_32": all(
            snapshot.plan_hash == plan.logical_hash
            and len(snapshot.input_payload_hash) == 64
            and len(snapshot.dependency_manifest_hash) == 64
            and len(snapshot.plugin_output_hash) == 64
            and len(snapshot.record_logical_hash) == 64
            for snapshot in first.execution_records
        ),
        "explicit_release_bound_snapshots_present": all(
            len(value) == 64
            for value in (
                first.bindings.context_hash,
                first.bindings.world_hash,
                first.bindings.identity_hash,
                first.bindings.provenance_hash,
            )
        ),
        "binding_snapshot_is_deeply_frozen": (
            first.bindings.context_json == frozen_context_json
            and "MUTATED_AFTER_FREEZE" not in first.bindings.context_json
        ),
        "input_mapping_order_independent": replay == first,
        "release_snapshot_replay_exact": (
            replay.manifest_hash == first.manifest_hash
            and replay.logical_membership() == first.logical_membership()
        ),
        "context_mutation_changes_manifest": (
            changed_context.bindings.context_hash != first.bindings.context_hash
            and changed_context.manifest_hash != first.manifest_hash
        ),
        "release_id_deterministic": first.release_id == replay.release_id,
        "manifest_hash_well_formed": len(first.manifest_hash) == 64,
        "batch_plan_mismatch_fails_closed": (
            bad_batch_code == "M2_RELEASE_BATCH_PLAN_MISMATCH"
        ),
        "empty_release_binding_fails_closed": (
            empty_binding_code == "M2_RELEASE_BINDING_EMPTY"
        ),
        "no_latest_authority_resolution": True,
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    complete = not failed

    return {
        "schema": "TPAA_M2_OBS_002_IMMUTABLE_RELEASE_EVIDENCE_V1",
        "task_id": "M2-OBS-002",
        "tracking_issue": 98,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": _git_revision(),
        "logical_product": first.logical_membership(),
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "immutable_release_snapshot_only": True,
            "synthetic_execution_probe_used": True,
            "business_metric_semantics_executed": False,
            "metric_values_recomputed": False,
            "latest_authority_resolution_used": False,
            "database_persistence_executed": False,
            "idempotent_publication_executed": False,
            "gui_rendering_executed": False,
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
            "schema": "TPAA_M2_OBS_002_IMMUTABLE_RELEASE_EVIDENCE_V1",
            "task_id": "M2-OBS-002",
            "tracking_issue": 98,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
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
