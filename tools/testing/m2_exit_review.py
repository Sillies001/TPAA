#!/usr/bin/env python3
"""M2-TST-006 clean-reconstruction and protected-main Exit review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = REPO_ROOT / "docs" / "baseline" / "SDIB-1.1" / "M2_TASK_BASELINE.json"

TASK_EVIDENCE = {
    "M2-DATA-001": "m2-data-001/{platform}/reference-truth.json",
    "M2-DATA-002": "m2-data-002/{platform}/time-alignment.json",
    "M2-DATA-003": "m2-data-003/{platform}/mission-system.json",
    "M2-DATA-004": "m2-data-004/{platform}/measurement-alignment.json",
    "M2-DATA-005": "m2-data-005/{platform}/fixture-family.json",
    "M2-WORLD-001": "m2-world-001/{platform}/reference-time-world.json",
    "M2-WORLD-002": "m2-world-002/{platform}/radar-sensor-world.json",
    "M2-WORLD-003": "m2-world-003/{platform}/stage-world-lineage.json",
    "M2-MET-001": "m2-met-001/{platform}/general-engine.json",
    "M2-MET-002": "m2-met-002/{platform}/qa-incremental.json",
    "M2-MET-003": "m2-met-003/{platform}/air-formal-delivery.json",
    "M2-MET-004": "m2-met-004/{platform}/sns-detection.json",
    "M2-MET-005": "m2-met-005/{platform}/sns-accuracy-incremental.json",
    "M2-MET-006": "m2-met-006/{platform}/runtime-contract-incremental.json",
    "M2-MET-007": "m2-met-007/{platform}/batch-replay-incremental.json",
    "M2-OBS-001": "m2-obs-001/{platform}/publication-routing.json",
    "M2-OBS-002": "m2-obs-002/{platform}/immutable-release.json",
    "M2-OBS-003": "m2-obs-003/{platform}/publication-replay.json",
    "M2-GUI-001": "m2-gui-001/{platform}/foundation-navigation.json",
    "M2-GUI-002": "m2-gui-002/{platform}/observation-lane.json",
    "M2-GUI-003": "m2-gui-003/{platform}/state-ux.json",
    "M2-TST-001": "m2-tst-001/{platform}/catalog-coverage.json",
    "M2-TST-002": "m2-tst-002/{platform}/qa-air-golden-negative.json",
    "M2-TST-003": "m2-tst-003/{platform}/sns-golden-applicability.json",
    "M2-TST-004": "m2-tst-004/{platform}/release-history-replay.json",
}
EXPECTED_TASK_IDS = tuple(TASK_EVIDENCE) + ("M2-TST-005", "M2-TST-006")


def _load(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise ValueError(f"{path}: root must be a string-keyed object")
    return cast(dict[str, object], value)


def _task_identity(payload: dict[str, object], task_id: str) -> bool:
    if payload.get("task_id") == task_id:
        return True
    task_ids = payload.get("task_ids")
    return isinstance(task_ids, list) and task_id in task_ids


def _task_evidence_pass(
    payload: dict[str, object],
    *,
    task_id: str,
    expected_revision: str,
) -> bool:
    task_complete = payload.get("task_complete")
    implementation_complete = payload.get("implementation_complete")
    return (
        _task_identity(payload, task_id)
        and payload.get("status") == "PASS"
        and payload.get("source_revision") == expected_revision
        and payload.get("failed_acceptance") == []
        and task_complete is not False
        and implementation_complete is not False
    )


def _cold_start_pass(
    payload: dict[str, object],
    *,
    platform: str,
    expected_revision: str,
    require_postgres: bool,
) -> bool:
    base = (
        payload.get("schema") == "TPAA_M0_COLD_START_V2"
        and payload.get("status") == "PASS"
        and payload.get("source_revision") == expected_revision
        and payload.get("platform") == platform
        and payload.get("clean_clone") is True
        and payload.get("uv_sync_locked") is True
        and payload.get("m0_gates") == "PASS"
        and payload.get("worktree_clean") is True
    )
    if not base:
        return False
    if require_postgres:
        return (
            payload.get("postgres_bootstrap") == "PASS"
            and payload.get("postgres_repository") == "PASS"
        )
    return True


def review(
    *,
    artifact_root: Path,
    tst005_path: Path,
    postgres_cold_start_path: Path,
    expected_revision: str,
    event_name: str,
    git_ref: str,
) -> dict[str, object]:
    if len(expected_revision) != 40:
        raise ValueError("expected_revision must be an exact 40-character Git SHA")

    baseline = _load(BASELINE)
    raw_tasks = baseline.get("tasks")
    if not isinstance(raw_tasks, list) or not all(isinstance(x, dict) for x in raw_tasks):
        raise ValueError("M2 task baseline tasks must be object rows")
    baseline_task_ids = tuple(str(item.get("task_id")) for item in raw_tasks)

    task_acceptance: dict[str, bool] = {}
    task_evidence_hashes: dict[str, dict[str, str]] = {}
    upstream_failed_acceptance_empty = True
    for task_id, pattern in TASK_EVIDENCE.items():
        platform_hashes: dict[str, str] = {}
        platform_pass: list[bool] = []
        for platform in ("windows", "linux"):
            path = artifact_root / pattern.format(platform=platform)
            payload = _load(path)
            platform_pass.append(
                _task_evidence_pass(
                    payload,
                    task_id=task_id,
                    expected_revision=expected_revision,
                )
            )
            upstream_failed_acceptance_empty = (
                upstream_failed_acceptance_empty
                and payload.get("failed_acceptance") == []
            )
            import hashlib

            platform_hashes[platform] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
        task_acceptance[task_id] = all(platform_pass)
        task_evidence_hashes[task_id] = platform_hashes

    tst005 = _load(tst005_path)
    tst005_complete = (
        tst005.get("schema")
        == "TPAA_M2_TST_005_CROSS_PLATFORM_STORAGE_QUALIFICATION_V1"
        and _task_evidence_pass(
            tst005,
            task_id="M2-TST-005",
            expected_revision=expected_revision,
        )
        and isinstance(tst005.get("scope"), dict)
        and cast(dict[str, object], tst005["scope"]).get(
            "p1_remainder_84_executed"
        )
        is False
    )
    task_acceptance["M2-TST-005"] = tst005_complete
    upstream_failed_acceptance_empty = (
        upstream_failed_acceptance_empty
        and tst005.get("failed_acceptance") == []
    )

    authority_ok: list[bool] = []
    for platform in ("windows", "linux"):
        sentinel = _load(
            artifact_root / "m2-authority-gap" / platform / "sentinel.json"
        )
        authority_ok.append(
            sentinel.get("status") == "PASS"
            and sentinel.get("source_revision") == expected_revision
            and sentinel.get("authority_resolution_ready") is True
            and sentinel.get("task_complete") is True
            and sentinel.get("blocked_tasks") == []
            and sentinel.get("failed_acceptance") == []
        )

    windows_cold = _load(
        artifact_root / "devops" / "windows" / "cold-start.json"
    )
    linux_cold = _load(
        artifact_root / "devops" / "linux" / "cold-start.json"
    )
    postgres_cold = _load(postgres_cold_start_path)

    acceptance = {
        "baseline_task_count_exact_27": (
            baseline.get("task_count") == 27 and len(baseline_task_ids) == 27
        ),
        "baseline_task_ids_exact": baseline_task_ids == EXPECTED_TASK_IDS,
        "platform_task_evidence_exact_25": (
            len(TASK_EVIDENCE) == 25
            and all(task_acceptance[task] for task in TASK_EVIDENCE)
        ),
        "tst005_exact_revision_complete": tst005_complete,
        "upstream_failed_acceptance_empty": upstream_failed_acceptance_empty,
        "authority_resolution_ready_cross_platform": all(authority_ok),
        "windows_clean_reconstruction_pass": _cold_start_pass(
            windows_cold,
            platform="windows",
            expected_revision=expected_revision,
            require_postgres=False,
        ),
        "linux_clean_reconstruction_pass": _cold_start_pass(
            linux_cold,
            platform="linux",
            expected_revision=expected_revision,
            require_postgres=False,
        ),
        "postgres_clean_reconstruction_pass": _cold_start_pass(
            postgres_cold,
            platform="linux",
            expected_revision=expected_revision,
            require_postgres=True,
        ),
        "p1_remainder_84_not_counted_as_m2": (
            isinstance(tst005.get("scope"), dict)
            and cast(dict[str, object], tst005["scope"]).get(
                "p1_remainder_84_executed"
            )
            is False
        ),
        "no_unresolved_authority_or_blocker_risk": all(authority_ok),
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    implementation_complete = not failed
    task_acceptance["M2-TST-006"] = implementation_complete

    protected_main = event_name == "push" and git_ref == "refs/heads/main"
    task_complete = implementation_complete and protected_main
    decision = (
        "GO"
        if task_complete
        else "PENDING_PROTECTED_MAIN"
        if implementation_complete
        else "NO_GO"
    )
    unresolved_risks: list[dict[str, object]] = []
    if failed:
        unresolved_risks.append(
            {"kind": "acceptance", "items": failed}
        )

    return {
        "schema": "TPAA_M2_EXIT_REVIEW_V1",
        "task_id": "M2-TST-006",
        "tracking_issue": 99,
        "status": "PASS" if implementation_complete else "FAIL",
        "decision": decision,
        "task_complete": task_complete,
        "implementation_complete": implementation_complete,
        "formal_completion_blocked_by_protected_main": (
            implementation_complete and not protected_main
        ),
        "protected_main_exact": protected_main,
        "source_revision": expected_revision,
        "task_count": len(EXPECTED_TASK_IDS),
        "task_ids": list(EXPECTED_TASK_IDS),
        "task_acceptance": task_acceptance,
        "task_evidence_hashes": task_evidence_hashes,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "unresolved_risks": unresolved_risks,
        "scope": {
            "cold_start_and_m2_exit_review_only": True,
            "clean_source_baseline_reconstruction_executed": True,
            "windows_linux_exact_revision_evidence_reviewed": True,
            "sqlite_postgresql_parity_reused_from_m2_tst_005": True,
            "protected_main_required_for_go": True,
            "p1_remainder_84_executed": False,
            "business_metric_semantics_recomputed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--tst005", type=Path, required=True)
    parser.add_argument("--postgres-cold-start", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--git-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = review(
            artifact_root=args.artifact_root,
            tst005_path=args.tst005,
            postgres_cold_start_path=args.postgres_cold_start,
            expected_revision=args.expected_revision,
            event_name=args.event_name,
            git_ref=args.git_ref,
        )
        return_code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M2_EXIT_REVIEW_V1",
            "task_id": "M2-TST-006",
            "tracking_issue": 99,
            "status": "FAIL",
            "decision": "NO_GO",
            "task_complete": False,
            "implementation_complete": False,
            "source_revision": args.expected_revision,
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
