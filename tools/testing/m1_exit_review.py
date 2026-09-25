#!/usr/bin/env python3
"""Fail-closed integrated M1 Exit review for Batch 4 / Issue #88."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "TPAA_M1_EXIT_REVIEW_V1"

PRE_BATCH_TASKS = {
    "M1-TST-001": ("m1-fixtures/{platform}/fixture-evidence.json", "TPAA_M1_TST_001_FIXTURE_EVIDENCE_V1"),
    "M1-DATA-001": ("m1-data-001/{platform}/source-adapter.json", "TPAA_M1_DATA_001_SOURCE_ADAPTER_EVIDENCE_V1"),
    "M1-DATA-002": ("m1-data-002/{platform}/source-registry.json", "TPAA_M1_DATA_002_SOURCE_REGISTRY_EVIDENCE_V1"),
    "M1-DATA-003": ("m1-data-003/{platform}/session-time.json", "TPAA_M1_DATA_003_SESSION_TIME_EVIDENCE_V1"),
    "M1-DATA-004": ("m1-data-004/{platform}/aircraft-identity.json", "TPAA_M1_DATA_004_AIRCRAFT_IDENTITY_EVIDENCE_V1"),
    "M1-DATA-005": ("m1-data-005/{platform}/canonical-flight-channels.json", "TPAA_M1_DATA_005_CANONICAL_FLIGHT_CHANNEL_EVIDENCE_V1"),
    "M1-DATA-006": ("m1-data-006/{platform}/evaluation-context.json", "TPAA_M1_DATA_006_EVALUATION_CONTEXT_EVIDENCE_V1"),
    "M1-DATA-007": ("m1-data-007/{platform}/lineage-quality.json", "TPAA_M1_DATA_007_LINEAGE_QUALITY_EVIDENCE_V1"),
    "M1-WORLD-001": ("m1-world-001/{platform}/basic-episode.json", "TPAA_M1_WORLD_001_BASIC_EPISODE_EVIDENCE_V1"),
    "M1-WORLD-002": ("m1-world-002/{platform}/basic-stage.json", "TPAA_M1_WORLD_002_BASIC_STAGE_EVIDENCE_V1"),
    "M1-WORLD-003": ("m1-world-003/{platform}/stage-quality.json", "TPAA_M1_WORLD_003_STAGE_QUALITY_EVIDENCE_V1"),
}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"evidence must be an object: {path}")
    return payload


def _acceptance_map(payload: dict[str, Any]) -> dict[str, bool]:
    raw = payload.get("acceptance")
    if not isinstance(raw, dict):
        return {}
    return {str(k): v is True for k, v in raw.items()}


def run(
    *,
    artifact_root: Path,
    batch1_logical: Path,
    batch2_review: Path,
    batch3_review: Path,
    batch4_windows: Path,
    batch4_linux: Path,
    batch4_logical: Path,
    expected_revision: str,
    event_name: str,
    git_ref: str,
    output: Path,
) -> int:
    task_acceptance: dict[str, bool] = {}
    revision_checks: dict[str, bool] = {}
    evidence_checks: dict[str, bool] = {}

    for task, (pattern, schema) in PRE_BATCH_TASKS.items():
        platform_results: list[bool] = []
        for platform in ("windows", "linux"):
            payload = _load(artifact_root / "evidence" / pattern.format(platform=platform))
            prefix = f"{task}:{platform}"
            evidence_checks[f"{prefix}:schema"] = payload.get("schema") == schema
            evidence_checks[f"{prefix}:status"] = payload.get("status") == "PASS"
            revision_checks[f"{prefix}:revision"] = payload.get("source_revision") == expected_revision
            platform_results.append(
                evidence_checks[f"{prefix}:schema"]
                and evidence_checks[f"{prefix}:status"]
                and revision_checks[f"{prefix}:revision"]
            )
        task_acceptance[task] = all(platform_results)

    b1_win = _load(artifact_root / "evidence" / "m1-batch-1" / "windows" / "core-product.json")
    b1_lin = _load(artifact_root / "evidence" / "m1-batch-1" / "linux" / "core-product.json")
    b1_eq = _load(batch1_logical)
    b1_tasks = b1_win.get("task_ids")
    if not isinstance(b1_tasks, list):
        b1_tasks = []
    b1_ok = (
        b1_win.get("schema") == "TPAA_M1_BATCH_1_CORE_EVIDENCE_V1"
        and b1_lin.get("schema") == "TPAA_M1_BATCH_1_CORE_EVIDENCE_V1"
        and b1_win.get("status") == "PASS"
        and b1_lin.get("status") == "PASS"
        and b1_win.get("source_revision") == expected_revision
        and b1_lin.get("source_revision") == expected_revision
        and b1_eq.get("schema") == "TPAA_M1_BATCH_1_LOGICAL_EQUIVALENCE_V1"
        and b1_eq.get("status") == "PASS"
        and b1_eq.get("source_revision") == expected_revision
    )
    for task in b1_tasks:
        task_acceptance[str(task)] = b1_ok
    revision_checks["batch1_windows_revision"] = b1_win.get("source_revision") == expected_revision
    revision_checks["batch1_linux_revision"] = b1_lin.get("source_revision") == expected_revision
    revision_checks["batch1_logical_revision"] = b1_eq.get("source_revision") == expected_revision

    b2 = _load(batch2_review)
    b3 = _load(batch3_review)
    b2_acceptance = _acceptance_map(b2)
    b3_acceptance = _acceptance_map(b3)
    for task, passed in b2_acceptance.items():
        task_acceptance[task] = passed
    for task, passed in b3_acceptance.items():
        task_acceptance[task] = passed
    revision_checks["batch2_review_revision"] = b2.get("source_revision") == expected_revision
    revision_checks["batch3_review_revision"] = b3.get("source_revision") == expected_revision
    evidence_checks["batch2_review_status"] = b2.get("status") == "PASS"
    evidence_checks["batch3_review_status"] = b3.get("status") == "PASS"

    b4_win = _load(batch4_windows)
    b4_lin = _load(batch4_linux)
    b4_eq = _load(batch4_logical)
    b4_win_acceptance = _acceptance_map(b4_win)
    b4_lin_acceptance = _acceptance_map(b4_lin)
    b4_eq_acceptance = _acceptance_map(b4_eq)
    task_acceptance["M1-TST-010"] = (
        b4_win_acceptance.get("M1-TST-010") is True
        and b4_lin_acceptance.get("M1-TST-010") is True
    )
    task_acceptance["M1-TST-009"] = b4_eq_acceptance.get("M1-TST-009") is True
    task_acceptance["M1-PLAT-004"] = b4_eq_acceptance.get("M1-PLAT-004") is True
    revision_checks["batch4_windows_revision"] = b4_win.get("source_revision") == expected_revision
    revision_checks["batch4_linux_revision"] = b4_lin.get("source_revision") == expected_revision
    revision_checks["batch4_logical_revision"] = b4_eq.get("source_revision") == expected_revision
    evidence_checks["batch4_windows_status"] = b4_win.get("status") == "PASS"
    evidence_checks["batch4_linux_status"] = b4_lin.get("status") == "PASS"
    evidence_checks["batch4_logical_status"] = b4_eq.get("status") == "PASS"

    expected_task_ids = {
        *PRE_BATCH_TASKS.keys(),
        *[str(x) for x in b1_tasks],
        *b2_acceptance.keys(),
        *b3_acceptance.keys(),
        "M1-TST-009",
        "M1-TST-010",
        "M1-PLAT-004",
    }
    failed_tasks = sorted(task for task in expected_task_ids if task_acceptance.get(task) is not True)
    failed_revision_checks = sorted(name for name, passed in revision_checks.items() if not passed)
    failed_evidence_checks = sorted(name for name, passed in evidence_checks.items() if not passed)
    task_set_complete = len(expected_task_ids) == 56
    all_pass = (
        task_set_complete
        and not failed_tasks
        and not failed_revision_checks
        and not failed_evidence_checks
    )
    protected_main = event_name == "push" and git_ref == "refs/heads/main"
    decision = "GO" if all_pass and protected_main else "PENDING_PROTECTED_MAIN" if all_pass else "NO_GO"
    unresolved_risks = []
    if failed_tasks:
        unresolved_risks.append({"kind": "task_acceptance", "items": failed_tasks})
    if failed_revision_checks:
        unresolved_risks.append({"kind": "revision", "items": failed_revision_checks})
    if failed_evidence_checks:
        unresolved_risks.append({"kind": "evidence", "items": failed_evidence_checks})
    if not task_set_complete:
        unresolved_risks.append({"kind": "task_inventory", "expected": 56, "actual": len(expected_task_ids)})

    payload = {
        "schema": SCHEMA,
        "tracking_issue": 88,
        "source_revision": expected_revision,
        "event_name": event_name,
        "git_ref": git_ref,
        "status": "PASS" if all_pass else "FAIL",
        "decision": decision,
        "protected_main_exact": protected_main,
        "task_count": len(expected_task_ids),
        "task_ids": sorted(expected_task_ids),
        "task_acceptance": {task: task_acceptance.get(task) is True for task in sorted(expected_task_ids)},
        "failed_acceptance": failed_tasks,
        "revision_checks": revision_checks,
        "failed_revision_checks": failed_revision_checks,
        "evidence_checks": evidence_checks,
        "failed_evidence_checks": failed_evidence_checks,
        "checklist": {
            "all_56_m1_tasks_present": task_set_complete,
            "all_m1_tasks_pass": not failed_tasks and task_set_complete,
            "all_evidence_exact_revision": not failed_revision_checks,
            "all_review_artifacts_pass": not failed_evidence_checks,
            "unresolved_risk_register_complete": True,
            "protected_main_required_for_go": True,
        },
        "unresolved_risks": unresolved_risks,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if all_pass else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--batch1-logical", type=Path, required=True)
    parser.add_argument("--batch2-review", type=Path, required=True)
    parser.add_argument("--batch3-review", type=Path, required=True)
    parser.add_argument("--batch4-windows", type=Path, required=True)
    parser.add_argument("--batch4-linux", type=Path, required=True)
    parser.add_argument("--batch4-logical", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--git-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    return run(
        artifact_root=args.artifact_root,
        batch1_logical=args.batch1_logical,
        batch2_review=args.batch2_review,
        batch3_review=args.batch3_review,
        batch4_windows=args.batch4_windows,
        batch4_linux=args.batch4_linux,
        batch4_logical=args.batch4_logical,
        expected_revision=args.expected_revision,
        event_name=args.event_name,
        git_ref=args.git_ref,
        output=args.output,
    )


if __name__ == "__main__":
    raise SystemExit(main())
