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
        timeout=180,
    )


def test_m2_batch_2_authority_sentinel_reports_adopted_c3(tmp_path: Path) -> None:
    path = tmp_path / "authority-sentinel.json"
    completed = _run(
        "m2-authority-gap-sentinel-check",
        "--evidence",
        str(path),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    evidence = json.loads(path.read_text(encoding="utf-8"))

    assert evidence["schema"] == "TPAA_M2_BATCH_2_AUTHORITY_GAP_SENTINEL_V1"
    assert evidence["tracking_issue"] == 97
    assert evidence["baseline_change_issue"] == 106
    assert evidence["status"] == "PASS"
    assert evidence["authority_resolution_ready"] is True
    assert evidence["task_complete"] is True
    assert evidence["blocked_tasks"] == []
    assert evidence["failed_acceptance"] == []
    assert all(evidence["acceptance"].values())
    assert evidence["scope"] == {
        "semantic_decision_adopted": True,
        "authority_values_invented_by_implementation": False,
        "sentinel_only": True,
    }
    product = evidence["logical_product"]
    assert product["authority_id"] == "M2_QA_SNS_AUTHORITY"
    assert product["authority_version"] == "1.0.0"
    assert product["profile_id"] == "M2_REFERENCE_MATCH_QUALITY_V1"
    assert product["profile_version"] == "1.1.0"
    assert product["fixture_profile_missing_fields"] == []
    assert product["fixture_profile_integrated"] is True
    assert evidence["acceptance"]["fixture_profile_integrated_exact"] is True


def test_m2_batch_2_authority_sentinel_compare_is_revision_exact(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.json"
    checked = _run(
        "m2-authority-gap-sentinel-check",
        "--evidence",
        str(source),
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    payload = json.loads(source.read_text(encoding="utf-8"))
    revision = payload["source_revision"]

    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"
    completed = _run(
        "m2-authority-gap-sentinel-compare",
        "--windows",
        str(windows),
        "--linux",
        str(linux),
        "--expected-revision",
        revision,
        "--evidence",
        str(compared),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    evidence = json.loads(compared.read_text(encoding="utf-8"))
    assert evidence["schema"] == (
        "TPAA_M2_BATCH_2_AUTHORITY_GAP_SENTINEL_CROSS_PLATFORM_V1"
    )
    assert evidence["status"] == "PASS"
    assert evidence["authority_resolution_ready"] is True
    assert evidence["task_complete"] is True
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
