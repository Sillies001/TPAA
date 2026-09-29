#!/usr/bin/env python3
"""M5-TST-006 aggregate cold reconstruction and complete RC evidence categories."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tpaa_qualification import (  # noqa: E402
    load_m5_qualification_authority,
    validate_signoff_contract,
)

BASELINE = ROOT / "baseline" / "CB-1.4.0"
TASK_BASELINE = ROOT / "docs" / "baseline" / "SDIB-1.4" / "M5_TASK_BASELINE.json"
TRACKING_ISSUE = 142
TASK_ID = "M5-TST-006"


def _json(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path}: root must be object")
    return cast(dict[str, Any], value)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review(
    *,
    parity_path: Path,
    windows_path: Path,
    linux_path: Path,
    formal_rc_path: Path,
    expected_revision: str,
) -> dict[str, Any]:
    authority = load_m5_qualification_authority(BASELINE)
    task_baseline = _json(TASK_BASELINE)
    rows = task_baseline.get("tasks")
    if not isinstance(rows, list) or task_baseline.get("task_count") != 23:
        raise RuntimeError("M5 task baseline drift")
    task_ids = tuple(str(cast(dict[str, object], row).get("task_id")) for row in rows)

    parity = _json(parity_path)
    windows = _json(windows_path)
    linux = _json(linux_path)
    rc = _json(formal_rc_path)
    for payload in (parity, windows, linux, rc):
        if payload.get("status") != "PASS":
            raise RuntimeError("M5-TST-006 prerequisite is not PASS")
        if payload.get("source_revision") != expected_revision:
            raise RuntimeError("M5-TST-006 source revision mismatch")

    upstream = parity.get("upstream_task_evidence_hashes")
    if (
        not isinstance(upstream, dict)
        or len(upstream) != len(task_ids[:20])
        or set(upstream) != set(task_ids[:20])
    ):
        raise RuntimeError("M5-TST-005 upstream task evidence inventory drift")
    if tuple(parity.get("qualified_task_ids", ())) != task_ids[:21]:
        raise RuntimeError("M5-TST-005 qualified task inventory drift")

    for payload, platform_name in ((windows, "windows"), (linux, "linux")):
        if payload.get("platform") != platform_name:
            raise RuntimeError("cold reconstruction platform mismatch")
        if payload.get("failed_acceptance") != []:
            raise RuntimeError("cold reconstruction has failed acceptance")

    categories = rc.get("evidence_categories")
    if not isinstance(categories, dict):
        raise RuntimeError("formal RC evidence categories missing")
    completed_categories = copy.deepcopy(categories)
    completed_categories["COLD_START_RECONSTRUCTION"] = {
        "status": "PASS",
        "evidence_sha256": [_sha(windows_path), _sha(linux_path)],
    }
    completed_categories["FORMAL_RC_MANIFEST"] = {
        "status": "PASS",
        "evidence_sha256": [_sha(formal_rc_path)],
    }
    required_categories = tuple(
        authority.formal_release_acceptance_profile["required_evidence_categories"]
    )
    if set(completed_categories) != set(required_categories):
        raise RuntimeError("completed RC evidence category inventory mismatch")
    completed_categories = {
        category: completed_categories[category] for category in required_categories
    }
    if any(
        not isinstance(completed_categories[category], dict)
        or completed_categories[category].get("status") != "PASS"
        for category in required_categories
    ):
        raise RuntimeError("completed RC evidence category is not PASS")

    signoff_contract = rc.get("signoff_contract")
    if not isinstance(signoff_contract, dict):
        raise RuntimeError("formal RC signoff contract missing")
    validate_signoff_contract(authority, signoff_contract)

    task_hashes = {str(key): str(value) for key, value in upstream.items()}
    task_hashes["M5-TST-005"] = _sha(parity_path)
    acceptance = {
        "exact_21_upstream_tasks": (
            len(task_hashes) == len(task_ids[:21])
            and set(task_hashes) == set(task_ids[:21])
        ),
        "windows_clean_reconstruction_pass": windows.get("failed_acceptance") == [],
        "linux_clean_reconstruction_pass": linux.get("failed_acceptance") == [],
        "all_four_reconstructed_profiles": (
            len(cast(dict[str, Any], windows.get("profiles", {}))) == 2
            and len(cast(dict[str, Any], linux.get("profiles", {}))) == 2
        ),
        "completed_rc_categories_exact_and_pass": tuple(completed_categories)
        == required_categories,
        "candidate_package_refs_preserved": isinstance(
            rc.get("candidate_package_refs"), dict
        ),
        "signoff_contract_preserved": True,
        "all_waivers_unexpired": parity.get("acceptance", {}).get(
            "all_waivers_unexpired_at_review_time"
        )
        is True,
        "formal_release_not_claimed": rc.get("formal_release_claimed") is False
        and rc.get("m5_exit_go_claimed") is False,
        "db_schema_1_6_0": authority.db_schema_version == "1.6.0",
        "p1_only": authority.admitted_phases == ("P1",),
    }
    failed = sorted(key for key, value in acceptance.items() if value is not True)

    completed_manifest = {
        "schema": "TPAA_M5_COMPLETED_RC_MANIFEST_V1",
        "source_revision": expected_revision,
        "semantic_build_version": rc.get("semantic_build_version"),
        "authority_sha256": rc.get("authority_sha256"),
        "baseline_lock_sha256": rc.get("baseline_lock_sha256"),
        "profile_status": {
            profile_id: cast(dict[str, Any], rc["profile_status"])[profile_id]
            for profile_id in authority.mandatory_profile_ids
        },
        "candidate_package_refs": rc.get("candidate_package_refs"),
        "evidence_categories": completed_categories,
        "signoff_contract": signoff_contract,
        "signoffs": [],
        "signoff_status": "READY_FOR_FINAL_SIGNOFF",
        "all_waivers_unexpired_at_release_time": acceptance[
            "all_waivers_unexpired"
        ],
        "formal_release_claimed": False,
        "m5_exit_go_claimed": False,
    }
    return {
        "schema": "TPAA_M5_TST_006_COLD_RECONSTRUCTION_V1",
        "task_id": TASK_ID,
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "implementation_complete": not failed,
        "task_complete": False,
        "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
        "source_revision": expected_revision,
        "semantic_build_version": rc.get("semantic_build_version"),
        "qualified_task_ids": list(task_ids[:22]),
        "upstream_task_evidence_hashes": task_hashes,
        "completed_rc_manifest": completed_manifest,
        "platform_reconstruction_hashes": {
            "windows": _sha(windows_path),
            "linux": _sha(linux_path),
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "p1_only": True,
            "p2_p6_inactive": True,
            "db_schema_version": authority.db_schema_version,
            "shadow_schema_created": False,
            "formal_release_claimed": False,
            "m5_exit_go_claimed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parity", type=Path, required=True)
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--linux", type=Path, required=True)
    parser.add_argument("--formal-rc", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = review(
            parity_path=args.parity,
            windows_path=args.windows,
            linux_path=args.linux,
            formal_rc_path=args.formal_rc,
            expected_revision=args.expected_revision,
        )
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M5_TST_006_COLD_RECONSTRUCTION_V1",
            "task_id": TASK_ID,
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "source_revision": args.expected_revision,
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
