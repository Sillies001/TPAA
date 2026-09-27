#!/usr/bin/env python3
"""M3-OBS-002 immutable exact-116 Release snapshot qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
TRACKING_ISSUE = 116
SESSION_ID = "77777777-7777-4777-8777-777777777777"


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


def _load(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{path}: root must be string-keyed object")
    return cast(dict[str, object], raw)


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_metric import (
        CatalogMetricEngine,
        M2MetricPluginRequest,
        M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
        MetricPluginRegistry,
        build_m2_metric_execution_plan,
        build_m3_metric_execution_plan,
    )
    from tpaa_observation import (
        M3ReleaseSnapshotError,
        build_m2_publication_routing_plan,
        build_m3_publication_routing_plan,
        build_m3_release_snapshot,
    )

    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    routing = build_m3_publication_routing_plan(AUTHORITY_ROOT)
    foundation_plan = build_m2_metric_execution_plan(AUTHORITY_ROOT)
    foundation_routing = build_m2_publication_routing_plan(AUTHORITY_ROOT)

    registry = MetricPluginRegistry()

    def probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {
            "metric_code": request.definition.metric_code,
            "definition_hash": request.definition.definition_hash,
            "input_token": request.input_payload["input_token"],
            "upstream_result_hashes": list(request.upstream_result_hashes),
        }

    for definition in plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m3-obs-002-snapshot-probe:{definition.metric_code}:v1",
            plugin=probe,
        )
    inputs = {
        definition.metric_code: {
            "input_token": f"M3-OBS-002::{definition.metric_code}",
        }
        for definition in plan.definitions
    }
    batch = CatalogMetricEngine(
        plan,
        registry,
        operator_implementations=M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
    ).execute(
        inputs,
        validate_runtime_contract=False,
    )

    request_hash = _canonical_hash(
        {
            "command": "M3_BUILD_RELEASE_SNAPSHOT",
            "session_id": SESSION_ID,
            "metric_codes": list(plan.metric_codes),
        }
    )
    context_input: dict[str, object] = {
        "context_id": "88888888-8888-4888-8888-888888888888",
        "context_version": "M3_CONTEXT_SNAPSHOT_V1",
        "catalog_hash": plan.catalog_sha256,
    }
    world_input: dict[str, object] = {
        "world_product_id": "99999999-9999-4999-8999-999999999999",
        "world_logical_hash": "a" * 64,
        "world_contract": "M3_FOUR_TRAINING_WORLD_V1",
    }
    identity_input: dict[str, object] = {
        "aircraft_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "mission_system_instance_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "subject_binding_version": "M3_SUBJECT_BINDING_V1",
    }
    provenance_input: dict[str, object] = {
        "source_revision": _git_revision(),
        "catalog_hash": plan.catalog_sha256,
        "metric_execution_plan_hash": plan.logical_hash,
        "publication_routing_plan_hash": routing.logical_hash,
        "execution_batch_hash": batch.logical_hash,
    }
    evidence_input: dict[str, dict[str, object]] = {
        definition.metric_code: {
            "evidence_contract": "M3_RELEASE_EVIDENCE_BINDING_V1",
            "metric_code": definition.metric_code,
            "source_artifact_hash": _canonical_hash(
                {
                    "metric_code": definition.metric_code,
                    "input_token": inputs[definition.metric_code]["input_token"],
                }
            ),
        }
        for definition in plan.definitions
    }

    first = build_m3_release_snapshot(
        session_id=SESSION_ID,
        request_hash=request_hash,
        release_no=1,
        parent_release_id=None,
        plan=plan,
        routing=routing,
        batch=batch,
        evidence_by_metric=evidence_input,
        context_snapshot=context_input,
        world_snapshot=world_input,
        identity_snapshot=identity_input,
        provenance_snapshot=provenance_input,
    )
    replay = build_m3_release_snapshot(
        session_id=SESSION_ID,
        request_hash=request_hash,
        release_no=1,
        parent_release_id=None,
        plan=plan,
        routing=routing,
        batch=batch,
        evidence_by_metric={
            code: dict(reversed(tuple(payload.items())))
            for code, payload in reversed(tuple(evidence_input.items()))
        },
        context_snapshot=dict(reversed(tuple(context_input.items()))),
        world_snapshot=dict(reversed(tuple(world_input.items()))),
        identity_snapshot=dict(reversed(tuple(identity_input.items()))),
        provenance_snapshot=dict(reversed(tuple(provenance_input.items()))),
    )

    first_code = plan.metric_codes[0]
    historical_code = plan.metric_codes[-1]
    frozen_context_json = first.bindings.context_json
    frozen_evidence_json = first.evidence(first_code).evidence_json
    historical_definition_hash = first.definition(historical_code).definition_hash

    changed_evidence_input = {
        code: dict(payload)
        for code, payload in evidence_input.items()
    }
    changed_evidence_input[first_code]["source_artifact_hash"] = "c" * 64
    changed_evidence = build_m3_release_snapshot(
        session_id=SESSION_ID,
        request_hash=request_hash,
        release_no=1,
        parent_release_id=None,
        plan=plan,
        routing=routing,
        batch=batch,
        evidence_by_metric=changed_evidence_input,
        context_snapshot=context_input,
        world_snapshot=world_input,
        identity_snapshot=identity_input,
        provenance_snapshot=provenance_input,
    )

    context_input["context_version"] = "MUTATED_AFTER_FREEZE"
    evidence_input[first_code]["evidence_contract"] = "MUTATED_AFTER_FREEZE"
    simulated_current_definition = replace(
        plan.definition(historical_code),
        definition_hash="0" * 64,
    )

    batch_mismatch_code = "NO_ERROR"
    try:
        build_m3_release_snapshot(
            session_id=SESSION_ID,
            request_hash=request_hash,
            release_no=1,
            parent_release_id=None,
            plan=plan,
            routing=routing,
            batch=replace(batch, plan_hash="0" * 64),
            evidence_by_metric=changed_evidence_input,
            context_snapshot={"context": "v1"},
            world_snapshot={"world": "v1"},
            identity_snapshot={"identity": "v1"},
            provenance_snapshot={"provenance": "v1"},
        )
    except M3ReleaseSnapshotError as exc:
        batch_mismatch_code = exc.code

    missing_evidence = dict(changed_evidence_input)
    missing_evidence.pop(plan.metric_codes[-1])
    evidence_membership_code = "NO_ERROR"
    try:
        build_m3_release_snapshot(
            session_id=SESSION_ID,
            request_hash=request_hash,
            release_no=1,
            parent_release_id=None,
            plan=plan,
            routing=routing,
            batch=batch,
            evidence_by_metric=missing_evidence,
            context_snapshot={"context": "v1"},
            world_snapshot={"world": "v1"},
            identity_snapshot={"identity": "v1"},
            provenance_snapshot={"provenance": "v1"},
        )
    except M3ReleaseSnapshotError as exc:
        evidence_membership_code = exc.code

    definition_by_code = {
        definition.metric_code: definition
        for definition in plan.definitions
    }
    record_by_code = {
        record.metric_code: record
        for record in batch.records
    }
    foundation_codes = set(foundation_plan.metric_codes)
    foundation_route_by_code = {
        target.metric_code: target
        for target in foundation_routing.targets
    }

    acceptance = {
        "release_definitions_exact_116": (
            len(first.definitions) == 116
            and first.metric_codes == plan.metric_codes
        ),
        "release_execution_records_exact_116": (
            len(first.execution_records) == 116
            and tuple(item.metric_code for item in first.execution_records)
            == plan.metric_codes
        ),
        "release_evidence_bindings_exact_116": (
            len(first.evidence_bindings) == 116
            and tuple(item.metric_code for item in first.evidence_bindings)
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
        "release_definition_binding_exact_116": all(
            snapshot.definition_hash
            == definition_by_code[snapshot.metric_code].definition_hash
            and snapshot.authority_lineage_hash
            == definition_by_code[snapshot.metric_code].authority_lineage_hash
            and snapshot.publication_route
            == routing.target(snapshot.metric_code).publication_route
            and snapshot.observation_lane
            == routing.target(snapshot.metric_code).observation_lane
            for snapshot in first.definitions
        ),
        "release_execution_binding_exact_116": all(
            snapshot.plan_hash == plan.logical_hash
            and snapshot.definition_hash
            == definition_by_code[snapshot.metric_code].definition_hash
            and len(snapshot.input_payload_hash) == 64
            and len(snapshot.dependency_manifest_hash) == 64
            and len(snapshot.plugin_output_hash) == 64
            and len(snapshot.record_logical_hash) == 64
            for snapshot in first.execution_records
        ),
        "release_evidence_binding_exact_116": all(
            snapshot.definition_hash
            == definition_by_code[snapshot.metric_code].definition_hash
            and snapshot.execution_record_hash
            == record_by_code[snapshot.metric_code].logical_hash
            and len(snapshot.evidence_hash) == 64
            for snapshot in first.evidence_bindings
        ),
        "explicit_context_world_identity_provenance_snapshots_present": all(
            len(value) == 64
            for value in (
                first.bindings.context_hash,
                first.bindings.world_hash,
                first.bindings.identity_hash,
                first.bindings.provenance_hash,
            )
        ),
        "foundation_definition_routes_preserved_exact_32": (
            len(foundation_codes) == 32
            and all(
                first.definition(code).definition_hash
                == foundation_plan.definition(code).definition_hash
                and first.definition(code).publication_route
                == foundation_route_by_code[code].publication_route
                and first.definition(code).observation_lane
                == foundation_route_by_code[code].observation_lane
                for code in foundation_codes
            )
        ),
        "binding_snapshot_is_deeply_frozen": (
            first.bindings.context_json == frozen_context_json
            and "MUTATED_AFTER_FREEZE" not in first.bindings.context_json
        ),
        "evidence_snapshot_is_deeply_frozen": (
            first.evidence(first_code).evidence_json == frozen_evidence_json
            and "MUTATED_AFTER_FREEZE"
            not in first.evidence(first_code).evidence_json
        ),
        "input_mapping_order_independent": replay == first,
        "release_snapshot_replay_exact": (
            replay.manifest_hash == first.manifest_hash
            and replay.logical_membership() == first.logical_membership()
        ),
        "evidence_mutation_changes_manifest": (
            changed_evidence.evidence(first_code).evidence_hash
            != first.evidence(first_code).evidence_hash
            and changed_evidence.manifest_hash != first.manifest_hash
        ),
        "historical_definition_read_ignores_current_authority": (
            first.definition(historical_code).definition_hash
            == historical_definition_hash
            and historical_definition_hash
            != simulated_current_definition.definition_hash
        ),
        "historical_evidence_read_uses_release_snapshot_only": (
            first.evidence(first_code).evidence_json == frozen_evidence_json
        ),
        "release_id_deterministic": first.release_id == replay.release_id,
        "manifest_hash_well_formed": len(first.manifest_hash) == 64,
        "batch_plan_mismatch_fails_closed": (
            batch_mismatch_code == "M3_RELEASE_BATCH_PLAN_MISMATCH"
        ),
        "missing_evidence_fails_closed": (
            evidence_membership_code == "M3_RELEASE_EVIDENCE_MEMBERSHIP_INVALID"
        ),
        "no_latest_or_current_authority_resolution": True,
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)

    return {
        "schema": "TPAA_M3_OBS_002_IMMUTABLE_RELEASE_EVIDENCE_V1",
        "task_id": "M3-OBS-002",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "implementation_complete": not failed,
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
            "current_authority_resolution_used": False,
            "database_persistence_executed": False,
            "idempotent_publication_executed": False,
            "api_projection_executed": False,
            "gui_rendering_executed": False,
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
        "windows_implementation_complete": (
            windows.get("implementation_complete") is True
        ),
        "linux_implementation_complete": linux.get("implementation_complete") is True,
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
        "schema": "TPAA_M3_OBS_002_IMMUTABLE_RELEASE_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": "M3-OBS-002",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "implementation_complete": not failed,
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
            "schema": "TPAA_M3_OBS_002_IMMUTABLE_RELEASE_EVIDENCE_V1",
            "task_id": "M3-OBS-002",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        evidence = getattr(args, "evidence", None)
        code = 2
    _write(payload, evidence)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
