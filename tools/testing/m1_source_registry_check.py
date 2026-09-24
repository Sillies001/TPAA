#!/usr/bin/env python3
"""M1-DATA-002 Source Registry acceptance evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m1"


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

    from tpaa_registry import register_all_synthetic_fixtures

    index, registrations = register_all_synthetic_fixtures(FIXTURE_ROOT)
    records: list[dict[str, object]] = []
    for registration in registrations:
        records.append(
            {
                "fixture_id": registration.fixture_id,
                "fixture_version": registration.fixture_version,
                "session_id": registration.session_id,
                "source_id": registration.source_id,
                "source_stream_id": registration.source_stream_id,
                "source_time_basis": registration.source_time_basis,
                "bundle_ref": registration.bundle_ref.logical_ref,
                "bundle_sha256": registration.bundle_ref.sha256,
                "bundle_immutable": registration.bundle_ref.immutable,
                "source_artifact_id": registration.source_artifact.object_id,
                "source_artifact_ref": registration.source_artifact.logical_ref,
                "source_artifact_sha256": registration.source_artifact.sha256,
                "source_artifact_immutable": registration.source_artifact.immutable,
                "context_object_ref_id": registration.context_artifact.object_id,
                "context_artifact_ref": registration.context_artifact.logical_ref,
                "context_artifact_sha256": registration.context_artifact.sha256,
                "context_artifact_immutable": registration.context_artifact.immutable,
                "context_version": registration.context_version,
                "persistence_executed": registration.persistence_executed,
                "canonical_context_artifact_row_executed": (
                    registration.canonical_context_artifact_row_executed
                ),
                "status": "PASS",
            }
        )

    bundle_refs = {item["bundle_ref"] for item in records}
    context_refs = {item["context_artifact_ref"] for item in records}
    immutable = all(
        item["bundle_immutable"] is True
        and item["source_artifact_immutable"] is True
        and item["context_artifact_immutable"] is True
        for item in records
    )
    status = (
        "PASS"
        if len(records) == 8
        and len(bundle_refs) == 8
        and len(context_refs) == 8
        and index.ref_count == 24
        and immutable
        else "FAIL"
    )
    return {
        "schema": "TPAA_M1_DATA_002_SOURCE_REGISTRY_EVIDENCE_V1",
        "task_id": "M1-DATA-002",
        "status": status,
        "source_revision": _git_revision(),
        "registration_count": len(records),
        "registry_ref_count": index.ref_count,
        "unique_bundle_ref_count": len(bundle_refs),
        "unique_context_ref_count": len(context_refs),
        "immutable_refs_verified": immutable,
        "database_persistence_executed": False,
        "session_time_transform_executed": False,
        "canonical_projection_executed": False,
        "evaluation_context_binding_executed": False,
        "canonical_context_artifact_kind_invented": False,
        "context_binding_deferred_to": "M1-DATA-006",
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
            "schema": "TPAA_M1_DATA_002_SOURCE_REGISTRY_EVIDENCE_V1",
            "task_id": "M1-DATA-002",
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
