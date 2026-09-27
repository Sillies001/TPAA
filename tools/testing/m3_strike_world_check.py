#!/usr/bin/env python3
"""M3-WORLD-003 Strike Stage/World/Event qualification evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
FIXTURE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "m3"
    / "STRIKE_M3_WORLD_003_NOMINAL_V1.json"
)
EXPECTED_STAGES = (
    "MISSION_SETUP",
    "ROUTE_TASK_EXECUTION",
    "TARGET_INFORMATION_AVAILABLE",
    "TARGET_ASSOCIATION",
    "DESIGNATION_TRACK",
    "TRAINING_ATTACK_EVENT",
    "RANGE_SIM_ADJUDICATION",
    "POST_EVENT_TASK_TRANSITION",
    "RECOVERY",
)
EXPECTED_WORLDS = ("A", "C", "M", "W")
TRACKING_ISSUE = 112


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

    from tpaa_world.m2_reference_time import CoreWorldManifest
    from tpaa_world.m3_profile_training import project_m3_training_profile

    first = project_m3_training_profile(FIXTURE, authority_root=AUTHORITY_ROOT)
    replay = project_m3_training_profile(FIXTURE, authority_root=AUTHORITY_ROOT)
    range_event = next(
        event
        for event in first.events
        if event.stage_type == "RANGE_SIM_ADJUDICATION"
    )
    acceptance = {
        "strike_training_type_exact": first.training_type == "STRIKE",
        "strike_episode_type_exact": first.episode_type == "STRIKE_MISSION",
        "strike_profile_exact": first.stage_profile_id == "STRIKE_MISSION_V1",
        "strike_core_capability_exact": (
            first.world_capability_code == "STRIKE_CORE"
        ),
        "stage_order_exact": (
            tuple(stage.stage_type for stage in first.stages)
            == EXPECTED_STAGES
        ),
        "stage_order_indexes_exact": (
            tuple(stage.stage_order for stage in first.stages)
            == tuple(range(len(EXPECTED_STAGES)))
        ),
        "half_open_intervals_exact": (
            first.interval_semantics == "half-open"
            and all(
                left.end_session_time_us == right.start_session_time_us
                for left, right in zip(
                    first.stages,
                    first.stages[1:],
                    strict=False,
                )
            )
        ),
        "event_projection_exact": (
            tuple(event.stage_type for event in first.events)
            == EXPECTED_STAGES
            and all(
                event.stage_id == stage.stage_id
                and event.session_time_us == stage.start_session_time_us
                and event.event_type == "STAGE_ENTRY_MARKER"
                for event, stage in zip(
                    first.events,
                    first.stages,
                    strict=True,
                )
            )
        ),
        "required_worlds_exact": first.required_world_codes == EXPECTED_WORLDS,
        "core_world_manifest_reused": all(
            isinstance(manifest, CoreWorldManifest)
            for _, manifest in first.worlds
        ),
        "adjudication_world_absent_without_j": all(
            manifest.world_kind != "ADJUDICATION"
            for _, manifest in first.worlds
        ),
        "range_adjudication_is_marker_only": (
            range_event.event_type == "STAGE_ENTRY_MARKER"
            and range_event.authority_source == "CONTEXT_OFFICIAL_MARKER"
        ),
        "authority_hashes_bound": all(
            len(value) == 64
            for value in (
                first.stage_registry_sha256,
                first.world_registry_sha256,
                first.taxonomy_sha256,
                first.core_schema_sha256,
            )
        ),
        "replay_stable": first == replay,
        "no_shadow_stage_schema": not first.shadow_stage_schema_created,
        "no_event_persistence_schema": (
            not first.event_persistence_schema_created
        ),
        "canonical_authority_not_mutated": (
            not first.canonical_authority_mutated
        ),
        "metric_logic_not_executed": not first.metric_logic_executed,
        "persistence_not_executed": not first.persistence_executed,
        "release_publication_not_executed": (
            not first.release_publication_executed
        ),
    }
    failed = sorted(
        key for key, passed in acceptance.items() if not passed
    )
    logical_product = {
        "fixture_id": first.fixture_id,
        "fixture_sha256": first.fixture_sha256,
        "training_type": first.training_type,
        "episode_type": first.episode_type,
        "stage_profile_id": first.stage_profile_id,
        "world_capability_code": first.world_capability_code,
        "required_world_codes": first.required_world_codes,
        "authorities": {
            "stage_registry_sha256": first.stage_registry_sha256,
            "world_registry_sha256": first.world_registry_sha256,
            "taxonomy_sha256": first.taxonomy_sha256,
            "core_schema_sha256": first.core_schema_sha256,
        },
        "episode_id": first.episode.episode_id,
        "stages": [
            {
                "stage_id": stage.stage_id,
                "stage_type": stage.stage_type,
                "stage_order": stage.stage_order,
                "start_session_time_us": stage.start_session_time_us,
                "end_session_time_us": stage.end_session_time_us,
            }
            for stage in first.stages
        ],
        "events": [
            {
                "event_id": event.event_id,
                "stage_id": event.stage_id,
                "stage_type": event.stage_type,
                "session_time_us": event.session_time_us,
                "event_type": event.event_type,
                "logical_hash": event.logical_hash,
            }
            for event in first.events
        ],
        "worlds": [
            {
                "world_code": code,
                "world_kind": manifest.world_kind,
                "world_product_id": manifest.world_product_id,
                "logical_content_hash": manifest.logical_content_hash,
                "request_hash": manifest.request_hash,
            }
            for code, manifest in first.worlds
        ],
        "bundle_logical_hash": first.logical_hash,
    }
    return {
        "schema": "TPAA_M3_WORLD_003_STRIKE_STAGE_WORLD_EVENT_EVIDENCE_V1",
        "task_id": "M3-WORLD-003",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": _git_revision(),
        "task_complete": not failed,
        "implementation_complete": not failed,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        payload = verify()
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M3_WORLD_003_STRIKE_STAGE_WORLD_EVENT_EVIDENCE_V1",
            "task_id": "M3-WORLD-003",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "source_revision": _git_revision(),
            "task_complete": False,
            "implementation_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
