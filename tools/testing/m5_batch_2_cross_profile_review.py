#!/usr/bin/env python3
"""M5 Batch 2 same-candidate four-profile review."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tpaa_qualification import (  # noqa: E402
    load_m5_qualification_authority,
    validate_four_profile_candidate,
)

BASELINE = ROOT / "baseline" / "CB-1.4.0"
TASK_IDS = (
    "M5-DEV-001",
    "M5-DEV-002",
    "M5-PLAT-002",
    "M5-PLAT-003",
    "M5-PLAT-004",
    "M5-PLAT-005",
    "M5-PERF-002",
    "M5-SEC-002",
    "M5-TST-002",
)


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def verify(
    windows: Path,
    linux: Path,
    *,
    expected_revision: str,
) -> dict[str, Any]:
    authority = load_m5_qualification_authority(BASELINE)
    inputs = [_load(windows), _load(linux)]
    for payload in inputs:
        if payload.get("status") != "PASS":
            raise RuntimeError("platform Batch 2 qualification is not PASS")
        if payload.get("source_revision") != expected_revision:
            raise RuntimeError("platform Batch 2 source revision mismatch")

    by_profile: dict[str, dict[str, Any]] = {}
    for payload in inputs:
        profiles = payload.get("profiles")
        if not isinstance(profiles, list):
            raise RuntimeError("platform profiles missing")
        for raw in profiles:
            if not isinstance(raw, dict):
                raise RuntimeError("profile row invalid")
            profile_id = raw.get("profile_id")
            if not isinstance(profile_id, str):
                raise RuntimeError("profile id invalid")
            by_profile[profile_id] = raw

    ordered = [by_profile[profile_id] for profile_id in authority.mandatory_profile_ids]
    validate_four_profile_candidate(authority, ordered)

    workload_hashes = {
        str(report["workload"]["workload_manifest_sha256"]) for report in ordered
    }
    authority_hashes = {str(report["authority_sha256"]) for report in ordered}
    acceptance = {
        "exact_four_profiles": (
            len(by_profile) == len(authority.mandatory_profile_ids)
            and set(by_profile) == set(authority.mandatory_profile_ids)
        ),
        "same_candidate_source_revision": len(
            {report["source_revision"] for report in ordered}
        )
        == 1
        and ordered[0]["source_revision"] == expected_revision,
        "same_semantic_build_version": len(
            {report["semantic_build_version"] for report in ordered}
        )
        == 1,
        "same_authority": authority_hashes == {authority.authority_sha256},
        "same_workload_manifest": len(workload_hashes) == 1,
        "all_package_lifecycle_pass": all(
            report["package"]["lifecycle"]["clean_install_pass"]
            and report["package"]["lifecycle"]["ready_start_pass"]
            and report["package"]["lifecycle"]["component_smoke_pass"]
            and report["package"]["lifecycle"]["graceful_stop_pass"]
            and report["package"]["lifecycle"]["uninstall_pass"]
            for report in ordered
        ),
        "all_performance_pass": all(
            report["performance"]["status"] == "PASS" for report in ordered
        ),
        "all_security_pass": all(
            report["security"]["status"] == "PASS" for report in ordered
        ),
        "formal_release_not_claimed": all(
            report["formal_release_claimed"] is False for report in ordered
        ),
    }
    failed = sorted(key for key, value in acceptance.items() if value is not True)
    return {
        "schema": "TPAA_M5_BATCH_2_FOUR_PROFILE_REVIEW_V1",
        "tracking_issue": 140,
        "task_ids": list(TASK_IDS),
        "status": "PASS" if not failed else "FAIL",
        "implementation_complete": not failed,
        "task_complete": False,
        "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
        "source_revision": expected_revision,
        "semantic_build_version": ordered[0]["semantic_build_version"],
        "authority_sha256": authority.authority_sha256,
        "mandatory_profiles": list(authority.mandatory_profile_ids),
        "profile_status": {
            report["profile_id"]: report["status"] for report in ordered
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "p1_only": True,
            "p2_p6_inactive": True,
            "db_schema_version": authority.db_schema_version,
            "formal_release_claimed": False,
            "m5_exit_go_claimed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--linux", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = verify(
        args.windows,
        args.linux,
        expected_revision=args.expected_revision,
    )
    rendered = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
