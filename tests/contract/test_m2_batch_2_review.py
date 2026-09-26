from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"
REVISION = "1" * 40

PLATFORM = {
    "M2-MET-001": (
        "m2-met-001/{platform}/general-engine.json",
        "TPAA_M2_MET_001_GENERAL_ENGINE_EVIDENCE_V1",
        None,
    ),
    "M2-MET-002": (
        "m2-met-002/{platform}/qa-incremental.json",
        "TPAA_M2_MET_002_INCREMENTAL_QA_EVIDENCE_V1",
        False,
    ),
    "M2-MET-003": (
        "m2-met-003/{platform}/air-formal-delivery.json",
        "TPAA_M2_MET_003_AIR_FORMAL_DELIVERY_EVIDENCE_V1",
        True,
    ),
    "M2-MET-004": (
        "m2-met-004/{platform}/sns-detection.json",
        "TPAA_M2_MET_004_SNS_DETECTION_EVIDENCE_V1",
        True,
    ),
    "M2-MET-005": (
        "m2-met-005/{platform}/sns-accuracy-incremental.json",
        "TPAA_M2_MET_005_SNS_ACCURACY_INCREMENTAL_EVIDENCE_V1",
        False,
    ),
    "M2-MET-006": (
        "m2-met-006/{platform}/runtime-contract-incremental.json",
        "TPAA_M2_MET_006_RUNTIME_CONTRACT_INCREMENTAL_EVIDENCE_V1",
        False,
    ),
    "M2-MET-007": (
        "m2-met-007/{platform}/batch-replay-incremental.json",
        "TPAA_M2_MET_007_BATCH_REPLAY_INCREMENTAL_EVIDENCE_V1",
        False,
    ),
}

LOGICAL = {
    "M2-MET-001": (
        "m2-met-001-logical-equivalence.json",
        "TPAA_M2_MET_001_CROSS_PLATFORM_EVIDENCE_V1",
        None,
    ),
    "M2-MET-002": (
        "m2-met-002-incremental-logical-equivalence.json",
        "TPAA_M2_MET_002_INCREMENTAL_CROSS_PLATFORM_EVIDENCE_V1",
        False,
    ),
    "M2-MET-003": (
        "m2-met-003-logical-equivalence.json",
        "TPAA_M2_MET_003_AIR_CROSS_PLATFORM_EVIDENCE_V1",
        True,
    ),
    "M2-MET-004": (
        "m2-met-004-logical-equivalence.json",
        "TPAA_M2_MET_004_SNS_DETECTION_CROSS_PLATFORM_EVIDENCE_V1",
        True,
    ),
    "M2-MET-005": (
        "m2-met-005-incremental-logical-equivalence.json",
        "TPAA_M2_MET_005_SNS_ACCURACY_INCREMENTAL_CROSS_PLATFORM_EVIDENCE_V1",
        False,
    ),
    "M2-MET-006": (
        "m2-met-006-incremental-logical-equivalence.json",
        "TPAA_M2_MET_006_RUNTIME_CONTRACT_INCREMENTAL_CROSS_PLATFORM_EVIDENCE_V1",
        False,
    ),
    "M2-MET-007": (
        "m2-met-007-incremental-logical-equivalence.json",
        "TPAA_M2_MET_007_BATCH_REPLAY_INCREMENTAL_CROSS_PLATFORM_EVIDENCE_V1",
        False,
    ),
}


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _seed(platform_root: Path, logical_root: Path) -> None:
    for task, (pattern, schema, complete) in PLATFORM.items():
        for platform in ("windows", "linux"):
            payload: dict[str, object] = {
                "schema": schema,
                "task_id": task,
                "tracking_issue": 97,
                "status": "PASS",
                "source_revision": REVISION,
                "failed_acceptance": [],
            }
            if complete is not None:
                payload["task_complete"] = complete
            _write(platform_root / pattern.format(platform=platform), payload)

    for task, (name, schema, complete) in LOGICAL.items():
        payload = {
            "schema": schema,
            "task_id": task,
            "tracking_issue": 97,
            "status": "PASS",
            "source_revision": REVISION,
            "failed_acceptance": [],
        }
        if complete is not None:
            payload["task_complete"] = complete
        _write(logical_root / name, payload)

    for platform in ("windows", "linux"):
        _write(
            platform_root / f"m2-authority-gap/{platform}/sentinel.json",
            {
                "schema": "TPAA_M2_BATCH_2_AUTHORITY_GAP_SENTINEL_V1",
                "tracking_issue": 97,
                "baseline_change_issue": 106,
                "status": "PASS",
                "source_revision": REVISION,
                "authority_resolution_ready": False,
                "task_complete": False,
                "failed_acceptance": [],
            },
        )
    _write(
        logical_root / "m2-authority-gap-sentinel.json",
        {
            "schema": "TPAA_M2_BATCH_2_AUTHORITY_GAP_SENTINEL_CROSS_PLATFORM_V1",
            "tracking_issue": 97,
            "baseline_change_issue": 106,
            "status": "PASS",
            "source_revision": REVISION,
            "authority_resolution_ready": False,
            "task_complete": False,
            "failed_acceptance": [],
        },
    )


def _run(
    platform_root: Path,
    logical_root: Path,
    output: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(DEV),
            "m2-batch-2-review",
            "--platform-root",
            str(platform_root),
            "--logical-root",
            str(logical_root),
            "--expected-revision",
            REVISION,
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_m2_batch_2_review_reports_exact_blocked_matrix(tmp_path: Path) -> None:
    platform_root = tmp_path / "platform"
    logical_root = tmp_path / "logical"
    output = tmp_path / "review.json"
    _seed(platform_root, logical_root)

    completed = _run(platform_root, logical_root, output)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    evidence = json.loads(output.read_text(encoding="utf-8"))

    assert evidence["schema"] == "TPAA_M2_BATCH_2_REVIEW_V1"
    assert evidence["tracking_issue"] == 97
    assert evidence["baseline_change_issue"] == 106
    assert evidence["status"] == "PASS"
    assert evidence["gate_state"] == "BLOCKED_AUTHORITY"
    assert evidence["batch_complete"] is False
    assert evidence["merge_authorized"] is False
    assert evidence["authority_resolution_ready"] is False
    assert evidence["completed_tasks"] == [
        "M2-MET-001",
        "M2-MET-003",
        "M2-MET-004",
    ]
    assert evidence["incomplete_tasks"] == [
        "M2-MET-002",
        "M2-MET-005",
        "M2-MET-006",
        "M2-MET-007",
    ]
    assert evidence["failed_evidence_checks"] == []
    assert evidence["scope"]["semantic_decision_made"] is False
    assert evidence["scope"]["authority_values_invented"] is False


def test_m2_batch_2_review_fails_on_revision_drift(tmp_path: Path) -> None:
    platform_root = tmp_path / "platform"
    logical_root = tmp_path / "logical"
    output = tmp_path / "review.json"
    _seed(platform_root, logical_root)

    path = platform_root / "m2-met-006/windows/runtime-contract-incremental.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["source_revision"] = "2" * 40
    _write(path, payload)

    completed = _run(platform_root, logical_root, output)
    assert completed.returncode == 2
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["status"] == "FAIL"
    assert evidence["batch_complete"] is False
    assert (
        "M2-MET-006:windows:revision"
        in evidence["failed_evidence_checks"]
    )
