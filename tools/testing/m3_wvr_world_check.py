#!/usr/bin/env python3
"""M3-WORLD-001 WVR Stage/World/Event qualification evidence."""

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
    / "WVR_M3_WORLD_001_NOMINAL_V1.json"
)
EXPECTED_STAGE_ORDER = (
    "MERGE",
    "POSITION_ADVANTAGE",
    "MANEUVER",
    "WEAPON_ENVELOPE",
    "LAUNCH",
    "KILL_ASSESSMENT",
)
EXPECTED_WORLD_CODES = ("A", "C", "M", "W")
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
    from tpaa_world.m3_wvr_training import project_m3_wvr_world

    first = project_m3_wvr_world(FIXTURE, authority_root=AUTHORITY_ROOT)
    replay = project_m3_wvr_world(FIXTURE, authority_root=AUTHORITY_ROOT)
    stage_order = tuple(stage.stage_type for stage in first.stages)
    world_codes = tuple(code for code, _ in first.worlds)

    acceptance = {
        "wvr_profile_exact": first.stage_profile_id == "WVR_ENGAGEMENT_V1",
        "episode_type_exact": first.episode.episode_type == "WVR_ENGAGEMENT",
        "wvr_core_capability_exact": (
            first.episode.world_capability_code == "WVR_CORE"
        ),
        "stage_order_exact": stage_order == EXPECTED_STAGE_ORDER,
        "stage_order_indexes_exact": (
            tuple(stage.stage_order for stage in first.stages)
            == tuple(range(len(EXPECTED_STAGE_ORDER)))
        ),
        "half_open_intervals_exact": (
            first.interval_semantics == "half-open"
            and all(
                stage.start_session_time_us < stage.end_session_time_us
                for stage in first.stages
            )
            and all(
                left.end_session_time_us == right.start_session_time_us
                for left, right in zip(
                    first.stages,
                    first.stages[1:],
                    strict=False,
                )
            )
        ),
        "stage_status_quality_exact": all(
            stage.stage_status == "VALID"
            and stage.coverage == 1.0
            and stage.confidence == 1.0
            and stage.detection_method == "CONTEXT"
            for stage in first.stages
        ),
        "event_projection_exact": (
            len(first.events) == len(first.stages)
            and tuple(event.stage_type for event in first.events)
            == EXPECTED_STAGE_ORDER
            and all(
                event.stage_id == stage.stage_id
                and event.session_time_us == stage.start_session_time_us
                and event.event_type == "STAGE_ENTRY_MARKER"
                and event.authority_source == "CONTEXT_OFFICIAL_MARKER"
                for event, stage in zip(
                    first.events,
                    first.stages,
                    strict=True,
                )
            )
        ),
        "required_worlds_exact": world_codes == EXPECTED_WORLD_CODES,
        "core_world_manifest_reused": all(
            isinstance(manifest, CoreWorldManifest)
            for _, manifest in first.worlds
        ),
        "worlds_episode_bound": all(
            manifest.episode_id == first.episode.episode_id
            and manifest.stage_id is None
            and manifest.status == "READY"
            and manifest.coverage == 1.0
            and manifest.confidence == 1.0
            for _, manifest in first.worlds
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
        "logical_hash_replay_stable": first.logical_hash == replay.logical_hash,
        "no_shadow_stage_schema": not first.shadow_stage_schema_created,
        "no_event_persistence_schema": (
            not first.event_persistence_schema_created
        ),
        "canonical_authority_not_mutated": (
            not first.canonical_authority_mutated
        ),
        "persistence_not_executed": not first.persistence_executed,
        "metric_logic_not_executed": not first.metric_logic_executed,
        "observation_not_executed": (
            not first.observation_projection_executed
        ),
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
        "stage_profile_id": first.stage_profile_id,
        "authorities": {
            "stage_registry_sha256": first.stage_registry_sha256,
            "world_registry_sha256": first.world_registry_sha256,
            "taxonomy_sha256": first.taxonomy_sha256,
            "core_schema_sha256": first.core_schema_sha256,
        },
        "episode": {
            "episode_id": first.episode.episode_id,
            "session_id": first.episode.session_id,
            "episode_type": first.episode.episode_type,
            "context_id": first.episode.context_id,
            "primary_aircraft_id": first.episode.primary_aircraft_id,
            "world_capability_code": first.episode.world_capability_code,
            "start_session_time_us": first.episode.start_session_time_us,
            "end_session_time_us": first.episode.end_session_time_us,
            "status": first.episode.episode_status,
            "detector_version": first.episode.detector_version,
            "coverage": first.episode.coverage,
            "confidence": first.episode.confidence,
            "data_sufficiency_status": (
                first.episode.data_sufficiency_status
            ),
        },
        "stages": [
            {
                "stage_id": stage.stage_id,
                "stage_type": stage.stage_type,
                "stage_order": stage.stage_order,
                "start_session_time_us": stage.start_session_time_us,
                "end_session_time_us": stage.end_session_time_us,
                "detection_method": stage.detection_method,
                "stage_status": stage.stage_status,
                "coverage": stage.coverage,
                "confidence": stage.confidence,
                "detector_version": stage.detector_version,
            }
            for stage in first.stages
        ],
        "events": [
            {
                "event_id": event.event_id,
                "stage_id": event.stage_id,
                "event_type": event.event_type,
                "stage_type": event.stage_type,
                "session_time_us": event.session_time_us,
                "authority_source": event.authority_source,
                "projector_version": event.projector_version,
                "logical_hash": event.logical_hash,
            }
            for event in first.events
        ],
        "worlds": [
            {
                "world_code": code,
                "world_product_id": manifest.world_product_id,
                "world_kind": manifest.world_kind,
                "world_version": manifest.world_version,
                "policy_version": manifest.policy_version,
                "status": manifest.status,
                "logical_content_hash": manifest.logical_content_hash,
                "request_hash": manifest.request_hash,
            }
            for code, manifest in first.worlds
        ],
        "bundle_logical_hash": first.logical_hash,
    }
    return {
        "schema": (
            "TPAA_M3_WORLD_001_WVR_STAGE_WORLD_EVENT_EVIDENCE_V1"
        ),
        "task_id": "M3-WORLD-001",
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
            "schema": (
                "TPAA_M3_WORLD_001_WVR_STAGE_WORLD_EVENT_EVIDENCE_V1"
            ),
            "task_id": "M3-WORLD-001",
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
        args.evidence.write_text(
            rendered,
            encoding="utf-8",
            newline="\n",
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
