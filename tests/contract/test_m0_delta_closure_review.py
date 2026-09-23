from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY = REPO_ROOT / "tools" / "governance" / "verify_m0_delta_closure.py"
DEV = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"
REVIEW = REPO_ROOT / "docs" / "reviews" / "M0_SDIB-1.0.1_DELTA_CLOSURE.json"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_m0_delta_closure_machine_review_passes() -> None:
    result = _run(str(VERIFY))
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"
    assert evidence["task_count"] == 48
    assert all(item["status"] == "PASS" for item in evidence["checks"])


def test_m0_delta_closure_contains_exactly_48_unique_closed_tasks() -> None:
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    tasks = review["tasks"]
    assert len(tasks) == 48
    assert len({item["task_id"] for item in tasks}) == 48
    assert all(item["status"] == "CLOSED" for item in tasks)
    assert review["decision"] == "GO"


def test_m0_delta_closure_verifier_is_available_through_unified_cli() -> None:
    result = _run(str(DEV), "verify-m0-delta-closure")
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"
    assert evidence["task_count"] == 48
