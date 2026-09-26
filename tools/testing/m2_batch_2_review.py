#!/usr/bin/env python3
"""Aggregate exact-revision M2 Batch 2 evidence without weakening blocked gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

SCHEMA = "TPAA_M2_BATCH_2_REVIEW_V1"
TRACKING_ISSUE = 97
BASELINE_CHANGE_ISSUE = 106
TASK_IDS = (
    "M2-MET-001",
    "M2-MET-002",
    "M2-MET-003",
    "M2-MET-004",
    "M2-MET-005",
    "M2-MET-006",
    "M2-MET-007",
)

PLATFORM_EVIDENCE = {
    "M2-MET-001": (
        "m2-met-001/{platform}/general-engine.json",
        "TPAA_M2_MET_001_GENERAL_ENGINE_EVIDENCE_V1",
    ),
    "M2-MET-002": (
        "m2-met-002/{platform}/qa-incremental.json",
        "TPAA_M2_MET_002_INCREMENTAL_QA_EVIDENCE_V1",
    ),
    "M2-MET-003": (
        "m2-met-003/{platform}/air-formal-delivery.json",
        "TPAA_M2_MET_003_AIR_FORMAL_DELIVERY_EVIDENCE_V1",
    ),
    "M2-MET-004": (
        "m2-met-004/{platform}/sns-detection.json",
        "TPAA_M2_MET_004_SNS_DETECTION_EVIDENCE_V1",
    ),
    "M2-MET-005": (
        "m2-met-005/{platform}/sns-accuracy-incremental.json",
        "TPAA_M2_MET_005_SNS_ACCURACY_INCREMENTAL_EVIDENCE_V1",
    ),
    "M2-MET-006": (
        "m2-met-006/{platform}/runtime-contract-incremental.json",
        "TPAA_M2_MET_006_RUNTIME_CONTRACT_INCREMENTAL_EVIDENCE_V1",
    ),
    "M2-MET-007": (
        "m2-met-007/{platform}/batch-replay-incremental.json",
        "TPAA_M2_MET_007_BATCH_REPLAY_INCREMENTAL_EVIDENCE_V1",
    ),
}

LOGICAL_EVIDENCE = {
    "M2-MET-001": (
        "m2-met-001-logical-equivalence.json",
        "TPAA_M2_MET_001_CROSS_PLATFORM_EVIDENCE_V1",
    ),
    "M2-MET-002": (
        "m2-met-002-incremental-logical-equivalence.json",
        "TPAA_M2_MET_002_INCREMENTAL_CROSS_PLATFORM_EVIDENCE_V1",
    ),
    "M2-MET-003": (
        "m2-met-003-logical-equivalence.json",
        "TPAA_M2_MET_003_AIR_CROSS_PLATFORM_EVIDENCE_V1",
    ),
    "M2-MET-004": (
        "m2-met-004-logical-equivalence.json",
        "TPAA_M2_MET_004_SNS_DETECTION_CROSS_PLATFORM_EVIDENCE_V1",
    ),
    "M2-MET-005": (
        "m2-met-005-incremental-logical-equivalence.json",
        "TPAA_M2_MET_005_SNS_ACCURACY_INCREMENTAL_CROSS_PLATFORM_EVIDENCE_V1",
    ),
    "M2-MET-006": (
        "m2-met-006-incremental-logical-equivalence.json",
        "TPAA_M2_MET_006_RUNTIME_CONTRACT_INCREMENTAL_CROSS_PLATFORM_EVIDENCE_V1",
    ),
    "M2-MET-007": (
        "m2-met-007-incremental-logical-equivalence.json",
        "TPAA_M2_MET_007_BATCH_REPLAY_INCREMENTAL_CROSS_PLATFORM_EVIDENCE_V1",
    ),
}

AUTHORITY_PLATFORM = (
    "m2-authority-gap/{platform}/sentinel.json",
    "TPAA_M2_BATCH_2_AUTHORITY_GAP_SENTINEL_V1",
)
AUTHORITY_LOGICAL = (
    "m2-authority-gap-sentinel.json",
    "TPAA_M2_BATCH_2_AUTHORITY_GAP_SENTINEL_CROSS_PLATFORM_V1",
)


def _load(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{path}: root must be string-keyed object")
    return cast(dict[str, object], value)


def _failed_acceptance_empty(payload: dict[str, object]) -> bool:
    raw = payload.get("failed_acceptance")
    return raw == []


def _platform_task_complete(task_id: str, payload: dict[str, object]) -> bool:
    if task_id == "M2-MET-001":
        # M2-MET-001 predates the explicit task_complete field; its formal
        # evidence schema is complete when the full acceptance object passes.
        return payload.get("status") == "PASS" and _failed_acceptance_empty(payload)
    return payload.get("task_complete") is True


def _logical_task_complete(task_id: str, payload: dict[str, object]) -> bool:
    if task_id == "M2-MET-001":
        return payload.get("status") == "PASS" and _failed_acceptance_empty(payload)
    return payload.get("task_complete") is True


def review(
    *,
    platform_root: Path,
    logical_root: Path,
    expected_revision: str,
) -> dict[str, object]:
    if len(expected_revision) != 40:
        raise ValueError("expected_revision must be an exact 40-character Git SHA")

    evidence_checks: dict[str, bool] = {}
    task_raw_complete: dict[str, bool] = {}
    task_platform_complete: dict[str, dict[str, bool]] = {}

    for task_id in TASK_IDS:
        relative, platform_schema = PLATFORM_EVIDENCE[task_id]
        per_platform: dict[str, bool] = {}
        for platform in ("windows", "linux"):
            path = platform_root / relative.format(platform=platform)
            payload = _load(path)
            prefix = f"{task_id}:{platform}"
            evidence_checks[f"{prefix}:schema"] = payload.get("schema") == platform_schema
            evidence_checks[f"{prefix}:task"] = payload.get("task_id") == task_id
            evidence_checks[f"{prefix}:tracking_issue"] = (
                payload.get("tracking_issue") == TRACKING_ISSUE
            )
            evidence_checks[f"{prefix}:status"] = payload.get("status") == "PASS"
            evidence_checks[f"{prefix}:revision"] = (
                payload.get("source_revision") == expected_revision
            )
            evidence_checks[f"{prefix}:failed_acceptance"] = (
                _failed_acceptance_empty(payload)
            )
            per_platform[platform] = _platform_task_complete(task_id, payload)
        task_platform_complete[task_id] = per_platform

        logical_name, logical_schema = LOGICAL_EVIDENCE[task_id]
        logical = _load(logical_root / logical_name)
        prefix = f"{task_id}:logical"
        evidence_checks[f"{prefix}:schema"] = logical.get("schema") == logical_schema
        evidence_checks[f"{prefix}:task"] = logical.get("task_id") == task_id
        evidence_checks[f"{prefix}:tracking_issue"] = (
            logical.get("tracking_issue") == TRACKING_ISSUE
        )
        evidence_checks[f"{prefix}:status"] = logical.get("status") == "PASS"
        evidence_checks[f"{prefix}:revision"] = (
            logical.get("source_revision") == expected_revision
        )
        evidence_checks[f"{prefix}:failed_acceptance"] = (
            _failed_acceptance_empty(logical)
        )
        task_raw_complete[task_id] = (
            per_platform["windows"]
            and per_platform["linux"]
            and _logical_task_complete(task_id, logical)
        )

    authority_platform: dict[str, dict[str, object]] = {}
    authority_relative, authority_platform_schema = AUTHORITY_PLATFORM
    for platform in ("windows", "linux"):
        payload = _load(platform_root / authority_relative.format(platform=platform))
        authority_platform[platform] = payload
        prefix = f"authority:{platform}"
        evidence_checks[f"{prefix}:schema"] = (
            payload.get("schema") == authority_platform_schema
        )
        evidence_checks[f"{prefix}:status"] = payload.get("status") == "PASS"
        evidence_checks[f"{prefix}:revision"] = (
            payload.get("source_revision") == expected_revision
        )
        evidence_checks[f"{prefix}:tracking_issue"] = (
            payload.get("tracking_issue") == TRACKING_ISSUE
        )
        evidence_checks[f"{prefix}:baseline_change_issue"] = (
            payload.get("baseline_change_issue") == BASELINE_CHANGE_ISSUE
        )
        evidence_checks[f"{prefix}:failed_acceptance"] = (
            _failed_acceptance_empty(payload)
        )

    authority_logical_name, authority_logical_schema = AUTHORITY_LOGICAL
    authority_logical = _load(logical_root / authority_logical_name)
    evidence_checks["authority:logical:schema"] = (
        authority_logical.get("schema") == authority_logical_schema
    )
    evidence_checks["authority:logical:status"] = (
        authority_logical.get("status") == "PASS"
    )
    evidence_checks["authority:logical:revision"] = (
        authority_logical.get("source_revision") == expected_revision
    )
    evidence_checks["authority:logical:tracking_issue"] = (
        authority_logical.get("tracking_issue") == TRACKING_ISSUE
    )
    evidence_checks["authority:logical:baseline_change_issue"] = (
        authority_logical.get("baseline_change_issue") == BASELINE_CHANGE_ISSUE
    )
    evidence_checks["authority:logical:failed_acceptance"] = (
        _failed_acceptance_empty(authority_logical)
    )

    authority_resolution_ready = (
        authority_platform["windows"].get("authority_resolution_ready") is True
        and authority_platform["linux"].get("authority_resolution_ready") is True
        and authority_logical.get("authority_resolution_ready") is True
    )

    # Formal predecessor closure from the frozen Batch 2 matrix.
    task_effective_complete = dict(task_raw_complete)
    task_effective_complete["M2-MET-006"] = (
        task_raw_complete["M2-MET-006"]
        and all(
            task_effective_complete[task]
            for task in (
                "M2-MET-002",
                "M2-MET-003",
                "M2-MET-004",
                "M2-MET-005",
            )
        )
    )
    task_effective_complete["M2-MET-007"] = (
        task_raw_complete["M2-MET-007"]
        and all(
            task_effective_complete[task]
            for task in (
                "M2-MET-002",
                "M2-MET-003",
                "M2-MET-004",
                "M2-MET-005",
                "M2-MET-006",
            )
        )
    )

    failed_evidence_checks = sorted(
        name for name, passed in evidence_checks.items() if not passed
    )
    completed_tasks = [
        task for task in TASK_IDS if task_effective_complete.get(task) is True
    ]
    incomplete_tasks = [
        task for task in TASK_IDS if task_effective_complete.get(task) is not True
    ]
    evidence_consistent = not failed_evidence_checks
    batch_complete = (
        evidence_consistent
        and authority_resolution_ready
        and not incomplete_tasks
    )
    gate_state = (
        "READY_FOR_FINAL_CANDIDATE"
        if batch_complete
        else "BLOCKED_AUTHORITY"
        if not authority_resolution_ready
        else "INCOMPLETE_TASKS"
    )

    blockers: list[dict[str, object]] = []
    if not authority_resolution_ready:
        blockers.append(
            {
                "kind": "c3_authority",
                "issue": BASELINE_CHANGE_ISSUE,
                "items": [
                    "P1-QA-001 frame convention",
                    "P1-QA-002 six-dimensional P_inputs mapping",
                    "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 instance closure",
                ],
            }
        )
    if incomplete_tasks:
        blockers.append({"kind": "task_completion", "items": incomplete_tasks})
    if failed_evidence_checks:
        blockers.append({"kind": "evidence_integrity", "items": failed_evidence_checks})

    return {
        "schema": SCHEMA,
        "tracking_issue": TRACKING_ISSUE,
        "baseline_change_issue": BASELINE_CHANGE_ISSUE,
        "source_revision": expected_revision,
        "status": "PASS" if evidence_consistent else "FAIL",
        "gate_state": gate_state,
        "batch_complete": batch_complete,
        "merge_authorized": False,
        "authority_resolution_ready": authority_resolution_ready,
        "task_ids": list(TASK_IDS),
        "task_raw_complete": task_raw_complete,
        "task_complete": task_effective_complete,
        "task_platform_complete": task_platform_complete,
        "completed_tasks": completed_tasks,
        "incomplete_tasks": incomplete_tasks,
        "evidence_checks": evidence_checks,
        "failed_evidence_checks": failed_evidence_checks,
        "blockers": blockers,
        "scope": {
            "review_only": True,
            "semantic_decision_made": False,
            "authority_values_invented": False,
            "blocked_state_is_successful_review": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    parser.add_argument("--logical-root", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = review(
            platform_root=args.platform_root,
            logical_root=args.logical_root,
            expected_revision=args.expected_revision,
        )
        return_code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": SCHEMA,
            "tracking_issue": TRACKING_ISSUE,
            "baseline_change_issue": BASELINE_CHANGE_ISSUE,
            "source_revision": args.expected_revision,
            "status": "FAIL",
            "gate_state": "EVIDENCE_INVALID",
            "batch_complete": False,
            "merge_authorized": False,
            "authority_resolution_ready": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2

    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
