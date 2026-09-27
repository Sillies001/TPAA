from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=360,
    )


def test_m2_tst_004_release_history_replay_idempotency(
    tmp_path: Path,
) -> None:
    source = tmp_path / "release-history-replay.json"
    checked = _run(
        "m2-release-history-replay-check",
        "--evidence",
        str(source),
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr

    payload = json.loads(source.read_text(encoding="utf-8"))
    assert payload["schema"] == (
        "TPAA_M2_TST_004_RELEASE_HISTORY_REPLAY_IDEMPOTENCY_EVIDENCE_V1"
    )
    assert payload["task_id"] == "M2-TST-004"
    assert payload["tracking_issue"] == 99
    assert payload["status"] == "PASS"
    assert payload["task_complete"] is True
    assert payload["implementation_complete"] is True
    assert payload["failed_acceptance"] == []
    assert all(payload["acceptance"].values())
    assert payload["logical_product"]["first_version_token"] == 1
    assert payload["logical_product"]["second_version_token"] == 2
    assert len(payload["logical_product"]["execution_metric_codes"]) == 32
    assert payload["scope"]["latest_authority_resolution_used"] is False

    revision = payload["source_revision"]
    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"
    result = _run(
        "m2-release-history-replay-compare",
        "--windows",
        str(windows),
        "--linux",
        str(linux),
        "--expected-revision",
        revision,
        "--evidence",
        str(compared),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(compared.read_text(encoding="utf-8"))
    assert evidence["schema"] == (
        "TPAA_M2_TST_004_RELEASE_HISTORY_REPLAY_IDEMPOTENCY_"
        "CROSS_PLATFORM_EVIDENCE_V1"
    )
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is True
    assert evidence["implementation_complete"] is True
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
