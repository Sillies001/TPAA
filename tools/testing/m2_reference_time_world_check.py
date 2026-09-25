#!/usr/bin/env python3
"""M2-WORLD-001 reference/time World product evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m2"
REFERENCE = FIXTURE_ROOT / "RT_M2_NOMINAL_V1"
TIME = FIXTURE_ROOT / "TA_M2_NOMINAL_V1"
RELEASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1"
ALTERNATE_RELEASE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2"


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

    from tpaa_world import (
        CORE_WORLD_MANIFEST_WRITABLE_FIELDS,
        CoreWorldManifest,
        project_m2_reference_time_world,
    )

    world = project_m2_reference_time_world(
        REFERENCE,
        TIME,
        authority_root=AUTHORITY_ROOT,
        release_id=RELEASE_ID,
    )
    replayed = project_m2_reference_time_world(
        REFERENCE,
        TIME,
        authority_root=AUTHORITY_ROOT,
        release_id=RELEASE_ID,
    )
    alternate_release = project_m2_reference_time_world(
        REFERENCE,
        TIME,
        authority_root=AUTHORITY_ROOT,
        release_id=ALTERNATE_RELEASE_ID,
    )

    manifest_fields = tuple(item.name for item in fields(CoreWorldManifest))
    acceptance = {
        "core_manifest_contract_exact": (
            manifest_fields == CORE_WORLD_MANIFEST_WRITABLE_FIELDS
        ),
        "reference_world_truth_kind": world.reference_manifest.world_kind == "TRUTH",
        "time_world_machine_kind": world.time_manifest.world_kind == "MACHINE",
        "world_status_ready": (
            world.reference_manifest.status == "READY"
            and world.time_manifest.status == "READY"
        ),
        "session_identity_exact": (
            world.reference_manifest.session_id
            == world.time_manifest.session_id
            == world.reference_truth.session_id
            == world.time_alignment.session_id
        ),
        "reference_upstream_projection_preserved": (
            world.reference_manifest.source_authority_signature
            and world.reference_truth.logical_hash
        ),
        "time_upstream_projection_preserved": (
            world.time_manifest.source_authority_signature
            and world.time_alignment.logical_hash
        ),
        "replay_stable": world == replayed,
        "logical_content_release_independent": (
            world.logical_hash == alternate_release.logical_hash
            and world.reference_manifest.logical_content_hash
            == alternate_release.reference_manifest.logical_content_hash
            and world.time_manifest.logical_content_hash
            == alternate_release.time_manifest.logical_content_hash
        ),
        "world_identity_release_bound": (
            world.reference_manifest.world_product_id
            != alternate_release.reference_manifest.world_product_id
            and world.time_manifest.world_product_id
            != alternate_release.time_manifest.world_product_id
        ),
        "authority_hashes_bound": (
            len(world.core_schema_sha256) == 64
            and len(world.world_policy_sha256) == 64
        ),
        "no_shadow_schema": not world.shadow_schema_created,
        "metric_logic_not_executed": not world.metric_logic_executed,
        "stage_projection_not_executed": not world.stage_projection_executed,
        "persistence_not_executed": not world.persistence_executed,
        "observation_projection_not_executed": (
            not world.observation_projection_executed
        ),
        "publication_not_executed": not world.release_publication_executed,
    }
    failed_acceptance = sorted(
        key for key, passed in acceptance.items() if not bool(passed)
    )
    logical_product = {
        "session_id": world.reference_manifest.session_id,
        "core_schema_sha256": world.core_schema_sha256,
        "world_policy_sha256": world.world_policy_sha256,
        "bundle_logical_hash": world.logical_hash,
        "reference_world": {
            "world_kind": world.reference_manifest.world_kind,
            "world_version": world.reference_manifest.world_version,
            "logical_content_hash": world.reference_manifest.logical_content_hash,
            "source_authority_signature": (
                world.reference_manifest.source_authority_signature
            ),
            "start_session_time_us": world.reference_manifest.start_session_time_us,
            "end_session_time_us": world.reference_manifest.end_session_time_us,
            "upstream_logical_hash": world.reference_truth.logical_hash,
            "input_sha256": world.reference_truth.input_sha256,
            "source_sha256": world.reference_truth.source_sha256,
        },
        "time_world": {
            "world_kind": world.time_manifest.world_kind,
            "world_version": world.time_manifest.world_version,
            "logical_content_hash": world.time_manifest.logical_content_hash,
            "source_authority_signature": world.time_manifest.source_authority_signature,
            "start_session_time_us": world.time_manifest.start_session_time_us,
            "end_session_time_us": world.time_manifest.end_session_time_us,
            "upstream_logical_hash": world.time_alignment.logical_hash,
            "source_sha256": world.time_alignment.source_sha256,
        },
    }
    return {
        "schema": "TPAA_M2_WORLD_001_REFERENCE_TIME_EVIDENCE_V1",
        "task_id": "M2-WORLD-001",
        "tracking_issue": 96,
        "status": "PASS" if not failed_acceptance else "FAIL",
        "source_revision": _git_revision(),
        "reference_fixture_id": world.reference_truth.fixture_id,
        "time_fixture_id": world.time_alignment.fixture_id,
        "reference_world_product_id": world.reference_manifest.world_product_id,
        "time_world_product_id": world.time_manifest.world_product_id,
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
            "schema": "TPAA_M2_WORLD_001_REFERENCE_TIME_EVIDENCE_V1",
            "task_id": "M2-WORLD-001",
            "tracking_issue": 96,
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
