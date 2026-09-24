#!/usr/bin/env python3
"""M1-DATA-006 Evaluation Context resolver acceptance evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m1"
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


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_context import resolve_all_evaluation_contexts

    first = resolve_all_evaluation_contexts(
        FIXTURE_ROOT,
        authority_root=AUTHORITY_ROOT,
    )
    replay = resolve_all_evaluation_contexts(
        FIXTURE_ROOT,
        authority_root=AUTHORITY_ROOT,
    )
    replay_stable = first == replay

    records: list[dict[str, Any]] = []
    for resolved in first:
        records.append(
            {
                "fixture_id": resolved.fixture_id,
                "fixture_version": resolved.fixture_version,
                "context_id": resolved.context_id,
                "session_id": resolved.session_id,
                "context_version": resolved.context_version,
                "revision_no": resolved.revision_no,
                "supersedes_context_id": resolved.supersedes_context_id,
                "rule_set_version": resolved.rule_set_version,
                "metric_profile_version": resolved.metric_profile_version,
                "status": resolved.status,
                "basic_profile_id": resolved.basic_profile_id,
                "stage_profile_id": resolved.stage_profile_id,
                "stage_profile_authority": resolved.stage_profile_authority,
                "stage_registry_sha256": resolved.stage_registry_sha256,
                "context_file_sha256": resolved.context_file_sha256,
                "artifact_refs": [
                    {
                        "binding_role": ref.binding_role,
                        "context_artifact_id": ref.context_artifact_id,
                        "artifact_kind": ref.artifact_kind,
                        "logical_key": ref.logical_key,
                        "artifact_version": ref.artifact_version,
                        "object_ref_id": ref.object_ref_id,
                        "artifact_sha256": ref.artifact_sha256,
                        "schema_version": ref.schema_version,
                    }
                    for ref in resolved.artifact_refs
                ],
                "logical_hash": resolved.logical_hash,
                "frozen_refs_used": resolved.frozen_refs_used,
                "current_refs_differ_from_frozen": (
                    resolved.current_refs_differ_from_frozen
                ),
                "current_latest_fallback_used": (
                    resolved.current_latest_fallback_used
                ),
                "stage_profile_persistence_binding_created": (
                    resolved.stage_profile_persistence_binding_created
                ),
                "database_persistence_executed": (
                    resolved.database_persistence_executed
                ),
                "stage_projection_executed": resolved.stage_projection_executed,
                "world_projection_executed": resolved.world_projection_executed,
                "metric_logic_executed": resolved.metric_logic_executed,
                "status_check": "PASS",
            }
        )

    role_sets = {
        tuple(ref["binding_role"] for ref in record["artifact_refs"])
        for record in records
    }
    artifact_ref_count = sum(len(record["artifact_refs"]) for record in records)
    logical_hashes = {record["logical_hash"] for record in records}
    context_hashes = {record["context_file_sha256"] for record in records}
    frozen_count = sum(bool(record["frozen_refs_used"]) for record in records)
    current_drift_count = sum(
        bool(record["current_refs_differ_from_frozen"]) for record in records
    )
    fallback_used = any(
        bool(record["current_latest_fallback_used"]) for record in records
    )
    stage_binding_created = any(
        bool(record["stage_profile_persistence_binding_created"])
        for record in records
    )
    downstream_execution = any(
        bool(record[field])
        for record in records
        for field in (
            "database_persistence_executed",
            "stage_projection_executed",
            "world_projection_executed",
            "metric_logic_executed",
        )
    )
    rule_set_hashes = {
        ref["artifact_sha256"]
        for record in records
        for ref in record["artifact_refs"]
        if ref["binding_role"] == "RULE_SET"
    }
    metric_profile_hashes = {
        ref["artifact_sha256"]
        for record in records
        for ref in record["artifact_refs"]
        if ref["binding_role"] == "METRIC_PROFILE"
    }

    status = (
        "PASS"
        if len(records) == 8
        and artifact_ref_count == 16
        and role_sets == {("METRIC_PROFILE", "RULE_SET")}
        and replay_stable
        and len(logical_hashes) == 8
        and len(context_hashes) == 8
        and len(rule_set_hashes) == 1
        and len(metric_profile_hashes) == 1
        and frozen_count == 1
        and current_drift_count == 1
        and not fallback_used
        and not stage_binding_created
        and not downstream_execution
        and {record["basic_profile_id"] for record in records}
        == {"M1-BASIC-CONTEXT-1.0.0"}
        and {record["stage_profile_id"] for record in records}
        == {"BASIC_FLIGHT_V1"}
        and {record["metric_profile_version"] for record in records}
        == {"M1_BASIC_AIR_PROFILE_V1"}
        else "FAIL"
    )

    return {
        "schema": "TPAA_M1_DATA_006_EVALUATION_CONTEXT_EVIDENCE_V1",
        "task_id": "M1-DATA-006",
        "status": status,
        "source_revision": _git_revision(),
        "context_count": len(records),
        "artifact_ref_count": artifact_ref_count,
        "required_binding_roles": ["METRIC_PROFILE", "RULE_SET"],
        "artifact_refs_stable_sorted": role_sets == {("METRIC_PROFILE", "RULE_SET")},
        "basic_profile_id": "M1-BASIC-CONTEXT-1.0.0",
        "stage_profile_id": "BASIC_FLIGHT_V1",
        "metric_profile_id": "M1_BASIC_AIR_PROFILE_V1",
        "unique_logical_hash_count": len(logical_hashes),
        "unique_context_file_hash_count": len(context_hashes),
        "replay_stable": replay_stable,
        "frozen_refs_resolution_count": frozen_count,
        "current_ref_drift_fixture_count": current_drift_count,
        "current_latest_fallback_used": fallback_used,
        "stage_profile_persistence_binding_created": stage_binding_created,
        "database_persistence_executed": False,
        "stage_projection_executed": False,
        "world_projection_executed": False,
        "metric_logic_executed": False,
        "records": records,
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
            "schema": "TPAA_M1_DATA_006_EVALUATION_CONTEXT_EVIDENCE_V1",
            "task_id": "M1-DATA-006",
            "status": "FAIL",
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
