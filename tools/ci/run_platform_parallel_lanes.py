#!/usr/bin/env python3
"""Run independent Windows/Linux milestone evidence lanes in parallel.

This preserves the historical command inventory and each lane's internal
dependency order while allowing independent milestone evidence generation to
overlap inside the two governed platform jobs.  The aggregate exits non-zero
when any command fails; no gate result is masked.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_LANES = ("m1", "m2", "m3", "m4", "m5")
INDEPENDENT_LANES = ("m1", "m2", "m3", "m4")
M5_PREREQUISITE_LANES = ("m3", "m4")
DESKTOP_PROFILES = {
    "linux": "LINUX_DESKTOP_X64",
    "windows": "WINDOWS_DESKTOP_X64",
}


@dataclass(frozen=True, slots=True)
class Command:
    template: str
    env: Mapping[str, str] = field(default_factory=dict)


LANES: dict[str, tuple[Command, ...]] = {
    "m1": (
        Command("python tools/dev/tpaa_dev.py verify-m1-entry-preparation"),
        Command("python tools/dev/tpaa_dev.py verify-m1-entry-gate-state"),
        Command("python tools/dev/tpaa_dev.py verify-m1-detailed-design"),
        Command(
            "python tools/dev/tpaa_dev.py m1-fixture-check "
            "--evidence evidence/m1-fixtures/{platform}/fixture-evidence.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m1-source-adapter-check "
            "--evidence evidence/m1-data-001/{platform}/source-adapter.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m1-source-registry-check "
            "--evidence evidence/m1-data-002/{platform}/source-registry.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m1-session-time-check "
            "--evidence evidence/m1-data-003/{platform}/session-time.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m1-aircraft-identity-check "
            "--evidence evidence/m1-data-004/{platform}/aircraft-identity.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m1-canonical-flight-channels-check "
            "--evidence evidence/m1-data-005/{platform}/canonical-flight-channels.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m1-evaluation-context-check "
            "--evidence evidence/m1-data-006/{platform}/evaluation-context.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m1-lineage-quality-check "
            "--evidence evidence/m1-data-007/{platform}/lineage-quality.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m1-basic-episode-check "
            "--evidence evidence/m1-world-001/{platform}/basic-episode.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m1-basic-stage-check "
            "--evidence evidence/m1-world-002/{platform}/basic-stage.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m1-stage-quality-check "
            "--evidence evidence/m1-world-003/{platform}/stage-quality.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m1-batch-1-core-check "
            "--evidence evidence/m1-batch-1/{platform}/core-product.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m1-batch-2-service-smoke "
            "--expected-platform {platform} "
            "--source-revision {source_revision} "
            "--evidence evidence/m1-batch-2/{platform}/service-smoke.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m1-batch-2-backend-check "
            "--platform {platform} "
            "--source-revision {source_revision} "
            "--evidence evidence/m1-batch-2/{platform}/backend.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m1-batch-3-desktop-e2e "
            "--expected-platform {platform} "
            "--source-revision {source_revision} "
            "--evidence evidence/m1-batch-3/{platform}/desktop-e2e.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m1-batch-4-platform-check "
            "--batch1 evidence/m1-batch-1/{platform}/core-product.json "
            "--batch2-service evidence/m1-batch-2/{platform}/service-smoke.json "
            "--batch3-desktop evidence/m1-batch-3/{platform}/desktop-e2e.json "
            "--expected-revision {source_revision} "
            "--evidence evidence/m1-batch-4/{platform}/platform.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m1-entry-manifest "
            "--profile {desktop_profile} "
            "--output evidence/m1-entry/{platform}/build-manifest.json"
        ),
    ),
    "m2": (
        Command(
            "python tools/dev/tpaa_dev.py m2-reference-truth-check "
            "--evidence evidence/m2-data-001/{platform}/reference-truth.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-time-alignment-check "
            "--evidence evidence/m2-data-002/{platform}/time-alignment.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-mission-system-check "
            "--evidence evidence/m2-data-003/{platform}/mission-system.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-measurement-alignment-check "
            "--evidence evidence/m2-data-004/{platform}/measurement-alignment.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-fixture-family-check "
            "--evidence evidence/m2-data-005/{platform}/fixture-family.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-reference-time-world-check "
            "--evidence evidence/m2-world-001/{platform}/reference-time-world.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-radar-sensor-world-check "
            "--evidence evidence/m2-world-002/{platform}/radar-sensor-world.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-stage-world-lineage-check "
            "--evidence evidence/m2-world-003/{platform}/stage-world-lineage.json"
        ),
        Command(
            "python tools/testing/m2_general_metric_engine_check.py "
            "--evidence evidence/m2-met-001/{platform}/general-engine.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-qa-foundation-incremental-check "
            "--evidence evidence/m2-met-002/{platform}/qa-incremental.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-air-formal-delivery-check "
            "--evidence evidence/m2-met-003/{platform}/air-formal-delivery.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-sns-detection-check "
            "--evidence evidence/m2-met-004/{platform}/sns-detection.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-sns-accuracy-incremental-check "
            "--evidence evidence/m2-met-005/{platform}/sns-accuracy-incremental.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-runtime-contract-incremental-check "
            "--evidence evidence/m2-met-006/{platform}/runtime-contract-incremental.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-batch-replay-incremental-check "
            "--evidence evidence/m2-met-007/{platform}/batch-replay-incremental.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-authority-gap-sentinel-check "
            "--evidence evidence/m2-authority-gap/{platform}/sentinel.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-publication-routing-check "
            "--evidence evidence/m2-obs-001/{platform}/publication-routing.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-immutable-release-check "
            "--evidence evidence/m2-obs-002/{platform}/immutable-release.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-idempotent-publication-check "
            "--evidence evidence/m2-obs-003/{platform}/publication-replay.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-gui-foundation-navigation-check "
            "--evidence evidence/m2-gui-001/{platform}/foundation-navigation.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-gui-observation-lane-check "
            "--evidence evidence/m2-gui-002/{platform}/observation-lane.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-gui-state-ux-check "
            "--evidence evidence/m2-gui-003/{platform}/state-ux.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-catalog-coverage-check "
            "--evidence evidence/m2-tst-001/{platform}/catalog-coverage.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-qa-air-golden-check "
            "--evidence evidence/m2-tst-002/{platform}/qa-air-golden-negative.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-sns-golden-check "
            "--evidence evidence/m2-tst-003/{platform}/sns-golden-applicability.json"
        ),
        Command(
            "python tools/dev/tpaa_dev.py m2-release-history-replay-check "
            "--evidence evidence/m2-tst-004/{platform}/release-history-replay.json"
        ),
    ),
    "m3": (
        Command(
            "python tools/testing/m3_wvr_world_check.py "
            "--evidence evidence/m3-world-001/{platform}/wvr-stage-world-event.json"
        ),
        Command(
            "python tools/testing/m3_bvr_world_check.py "
            "--evidence evidence/m3-world-002/{platform}/bvr-stage-world-event.json"
        ),
        Command(
            "python tools/testing/m3_strike_world_check.py "
            "--evidence evidence/m3-world-003/{platform}/strike-stage-world-event.json"
        ),
        Command(
            "python tools/testing/m3_mission_product_applicability_check.py "
            "--evidence evidence/m3-world-004/{platform}/mission-product-applicability.json"
        ),
        Command(
            "python tools/testing/m3_fixture_family_check.py check "
            "--evidence evidence/m3-world-005/{platform}/fixture-family.json"
        ),
        Command(
            "python tools/testing/m3_general_metric_engine_check.py check "
            "--evidence evidence/m3-met-001/{platform}/general-engine.json"
        ),
        Command(
            "python tools/testing/m3_air_remainder_check.py check "
            "--evidence evidence/m3-met-002/{platform}/air-remainder.json"
        ),
        Command(
            "python tools/testing/m3_track_remainder_check.py check "
            "--evidence evidence/m3-met-003/{platform}/track-remainder.json"
        ),
        Command(
            "python tools/testing/m3_identification_remainder_check.py check "
            "--evidence evidence/m3-met-004/{platform}/identification-remainder.json"
        ),
        Command(
            "python tools/testing/m3_passive_remainder_check.py check "
            "--evidence evidence/m3-met-005/{platform}/passive-remainder.json"
        ),
        Command(
            "python tools/testing/m3_esm_remainder_check.py check "
            "--evidence evidence/m3-met-006/{platform}/esm-remainder.json"
        ),
        Command(
            "python tools/testing/m3_datalink_remainder_check.py check "
            "--evidence evidence/m3-met-007/{platform}/datalink-remainder.json"
        ),
        Command(
            "python tools/testing/m3_fusion_remainder_check.py check "
            "--evidence evidence/m3-met-008/{platform}/fusion-remainder.json"
        ),
        Command(
            "python tools/testing/m3_runtime_closure_check.py check "
            "--evidence evidence/m3-met-009/{platform}/runtime-closure.json"
        ),
        Command(
            "python tools/testing/m3_publication_routing_check.py check "
            "--evidence evidence/m3-obs-001/{platform}/publication-routing.json"
        ),
        Command(
            "python tools/testing/m3_immutable_release_check.py check "
            "--evidence evidence/m3-obs-002/{platform}/immutable-release.json"
        ),
        Command(
            "python tools/testing/m3_idempotent_publication_check.py check "
            "--evidence evidence/m3-obs-003/{platform}/publication-replay.json"
        ),
        Command(
            "python tools/testing/m3_api_release_query_check.py check "
            "--evidence evidence/m3-api-001/{platform}/release-query.json"
        ),
        Command(
            "python tools/testing/m3_api_workspace_check.py check "
            "--evidence evidence/m3-api-002/{platform}/workspace.json"
        ),
        Command(
            "python tools/testing/m3_gui_workspace_navigation_check.py check "
            "--evidence evidence/m3-gui-001/{platform}/workspace-navigation.json"
        ),
        Command(
            "python tools/testing/m3_gui_family_applicability_check.py check "
            "--evidence evidence/m3-gui-002/{platform}/family-applicability.json"
        ),
        Command(
            "python tools/testing/m3_gui_status_evidence_replay_check.py check "
            "--evidence evidence/m3-gui-003/{platform}/status-evidence-replay.json"
        ),
        Command(
            "python tools/testing/m3_catalog_coverage_check.py check "
            "--evidence evidence/m3-tst-001/{platform}/catalog-coverage.json"
        ),
        Command(
            "python tools/testing/m3_four_training_golden_check.py check "
            "--evidence evidence/m3-tst-002/{platform}/four-training-golden.json"
        ),
        Command(
            "python tools/testing/m3_air_golden_check.py check "
            "--evidence evidence/m3-tst-003/{platform}/air-golden.json"
        ),
        Command(
            "python tools/testing/m3_product_layer_golden_check.py check "
            "--evidence evidence/m3-tst-004/{platform}/product-layer-golden.json"
        ),
        Command(
            "python tools/testing/m3_release_api_gui_storage_qualification.py check "
            "--evidence-root evidence "
            "--platform {platform} "
            "--expected-revision {source_revision} "
            "--evidence evidence/m3-tst-005/{platform}/release-api-gui.json"
        ),
    ),
    "m4": (
        Command(
            "python tools/testing/m4_batch_1_longitudinal_sample_check.py "
            "--evidence evidence/m4-batch-1/{platform}/longitudinal-sample.json"
        ),
        Command(
            "python tools/testing/m4_batch_2_trend_release_check.py "
            "--evidence evidence/m4-batch-2/{platform}/trend-release.json"
        ),
        Command(
            "python tools/testing/m4_batch_3_api_gui_debrief_check.py "
            "--evidence evidence/m4-batch-3/{platform}/api-gui-debrief.json"
        ),
        Command(
            "python tools/testing/m4_longitudinal_coverage_check.py "
            "--evidence evidence/m4-tst-004/{platform}/coverage.json"
        ),
        Command(
            "python tools/testing/m4_release_api_gui_storage_qualification.py check "
            "--evidence-root evidence "
            "--platform {platform} "
            "--expected-revision {source_revision} "
            "--evidence evidence/m4-tst-005/{platform}/platform.json"
        ),
    ),
    "m5": (
        Command(
            "python tools/testing/m5_batch_1_qualification_profile_check.py "
            "--platform {platform} "
            "--evidence evidence/m5-batch-1/{platform}/qualification-profile.json"
        ),
        Command(
            "python tools/testing/m5_batch_2_qualification.py "
            "--platform {platform} "
            "--package-output dist/m5/{platform} "
            "--evidence evidence/m5-batch-2/{platform}/qualification.json",
            env={"TPAA_M5_STORAGE_CLASS": "SSD"},
        ),
        Command(
            "python tools/testing/m5_batch_3_platform_qualification.py "
            "--platform {platform} "
            "--batch2 evidence/m5-batch-2/{platform}/qualification.json "
            "--evidence evidence/m5-batch-3/{platform}/platform-recovery.json"
        ),
        Command(
            "python tools/testing/m5_batch_4_cold_reconstruction.py "
            "--platform {platform} "
            "--batch2 evidence/m5-batch-2/{platform}/qualification.json "
            "--batch3 evidence/m5-batch-3/{platform}/platform-recovery.json "
            "--cold-start evidence/devops/{platform}/cold-start.json "
            "--expected-revision {source_revision} "
            "--evidence evidence/m5-batch-4/{platform}/cold-reconstruction.json"
        ),
    ),
}


def _render(command: Command, *, platform: str, source_revision: str) -> tuple[list[str], dict[str, str]]:
    desktop_profile = DESKTOP_PROFILES[platform]
    rendered = command.template.format(
        platform=platform,
        source_revision=source_revision,
        desktop_profile=desktop_profile,
    )
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required for governed platform lanes")
    args = [uv, "run", "--locked", *shlex.split(rendered, posix=True)]
    env = os.environ.copy()
    env.update(command.env)
    return args, env


def _run_lane(name: str, commands: tuple[Command, ...], *, platform: str, source_revision: str) -> dict[str, object]:
    completed: list[str] = []
    for index, command in enumerate(commands, start=1):
        args, env = _render(
            command,
            platform=platform,
            source_revision=source_revision,
        )
        print(
            f"PARALLEL_LANE_START lane={name} step={index}/{len(commands)} "
            f"command={command.template}",
            flush=True,
        )
        result = subprocess.run(
            args,
            cwd=REPO_ROOT,
            env=env,
            check=False,
        )
        if result.returncode != 0:
            print(
                f"PARALLEL_LANE_FAIL lane={name} step={index} "
                f"return_code={result.returncode}",
                flush=True,
            )
            return {
                "lane": name,
                "status": "FAIL",
                "return_code": result.returncode,
                "completed": completed,
                "failed_command": command.template,
            }
        completed.append(command.template)
    print(
        f"PARALLEL_LANE_PASS lane={name} commands={len(commands)}",
        flush=True,
    )
    return {
        "lane": name,
        "status": "PASS",
        "return_code": 0,
        "completed": completed,
        "failed_command": None,
    }


def verify_contract() -> dict[str, object]:
    lane_names = tuple(LANES)
    command_count = sum(len(commands) for commands in LANES.values())
    checks = {
        "lane_inventory_exact": lane_names == EXPECTED_LANES,
        "independent_lane_inventory_exact": INDEPENDENT_LANES == ("m1", "m2", "m3", "m4"),
        "m5_prerequisite_lanes_exact": M5_PREREQUISITE_LANES == ("m3", "m4"),
        "command_count_nonzero": command_count > 0,
        "m5_chain_ordered": tuple(
            command.template.split()[1]
            if len(command.template.split()) > 1
            else command.template
            for command in LANES["m5"]
        ) == (
            "tools/testing/m5_batch_1_qualification_profile_check.py",
            "tools/testing/m5_batch_2_qualification.py",
            "tools/testing/m5_batch_3_platform_qualification.py",
            "tools/testing/m5_batch_4_cold_reconstruction.py",
        ),
        "no_shell_failure_mask": all(
            "|| true" not in command.template
            for commands in LANES.values()
            for command in commands
        ),
    }
    return {
        "schema": "TPAA_PLATFORM_PARALLEL_LANES_V1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "lanes": {
            name: len(commands)
            for name, commands in LANES.items()
        },
        "command_count": command_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("linux", "windows"))
    parser.add_argument("--source-revision")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    contract = verify_contract()
    if args.verify_only:
        print(json.dumps(contract, indent=2, sort_keys=True))
        return 0 if contract["status"] == "PASS" else 2
    if args.platform is None or args.source_revision is None:
        parser.error("--platform and --source-revision are required unless --verify-only")
    if contract["status"] != "PASS":
        print(json.dumps(contract, indent=2, sort_keys=True))
        return 2

    results_by_name: dict[str, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=len(INDEPENDENT_LANES)) as executor:
        futures = {
            executor.submit(
                _run_lane,
                name,
                LANES[name],
                platform=args.platform,
                source_revision=args.source_revision,
            ): name
            for name in INDEPENDENT_LANES
        }
        for future in as_completed(futures):
            name = futures[future]
            results_by_name[name] = future.result()

    blocked_by = [
        name
        for name in M5_PREREQUISITE_LANES
        if results_by_name[name]["status"] != "PASS"
    ]
    if blocked_by:
        print(
            "PARALLEL_LANE_BLOCKED lane=m5 prerequisites=" + ",".join(blocked_by),
            flush=True,
        )
        results_by_name["m5"] = {
            "lane": "m5",
            "status": "FAIL",
            "return_code": 2,
            "completed": [],
            "failed_command": None,
            "blocked_by": blocked_by,
        }
    else:
        results_by_name["m5"] = _run_lane(
            "m5",
            LANES["m5"],
            platform=args.platform,
            source_revision=args.source_revision,
        )

    results = [results_by_name[name] for name in EXPECTED_LANES]
    status = "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL"
    payload = {
        "schema": "TPAA_PLATFORM_PARALLEL_EXECUTION_V1",
        "platform": args.platform,
        "source_revision": args.source_revision,
        "status": status,
        "lanes": results,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
