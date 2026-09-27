from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tpaa_metric import build_m2_metric_execution_plan

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
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


def test_m2_tst_001_exact_catalog_partition_and_plan_membership() -> None:
    catalog = json.loads(
        (AUTHORITY / "P1_METRIC_CATALOG.json").read_text(encoding="utf-8")
    )
    metrics = catalog["metrics"]
    foundation = [
        item
        for item in metrics
        if item["delivery_milestone"] == "M2"
        and item["delivery_batch"] == "P1_FOUNDATION_32"
    ]
    remainder = [
        item
        for item in metrics
        if item["delivery_milestone"] == "M3"
        and item["delivery_batch"] == "P1_REMAINDER_84"
    ]
    foundation_codes = tuple(item["metric_code"] for item in foundation)
    remainder_codes = {item["metric_code"] for item in remainder}
    plan = build_m2_metric_execution_plan(AUTHORITY)

    assert len(metrics) == 116
    assert len(foundation) == 32
    assert len(remainder) == 84
    assert plan.catalog_metric_codes == foundation_codes
    assert len(plan.metric_codes) == 32
    assert set(plan.metric_codes) == set(foundation_codes)
    assert set(plan.metric_codes).isdisjoint(remainder_codes)


def test_m2_tst_001_evidence_and_cross_platform_contract(
    tmp_path: Path,
) -> None:
    source = tmp_path / "catalog-coverage.json"
    checked = _run(
        "m2-catalog-coverage-check",
        "--evidence",
        str(source),
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr

    payload = json.loads(source.read_text(encoding="utf-8"))
    assert payload["schema"] == "TPAA_M2_TST_001_CATALOG_COVERAGE_EVIDENCE_V1"
    assert payload["task_id"] == "M2-TST-001"
    assert payload["tracking_issue"] == 99
    assert payload["status"] == "PASS"
    assert payload["task_complete"] is True
    assert payload["implementation_complete"] is True
    assert payload["failed_acceptance"] == []
    assert all(payload["acceptance"].values())
    assert payload["logical_product"]["catalog_total_count"] == 116
    assert payload["logical_product"]["foundation_count"] == 32
    assert payload["logical_product"]["remainder_count"] == 84
    assert payload["scope"]["p1_remainder_84_counted_as_m2"] is False

    revision = payload["source_revision"]
    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"
    result = _run(
        "m2-catalog-coverage-compare",
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
        "TPAA_M2_TST_001_CATALOG_COVERAGE_CROSS_PLATFORM_EVIDENCE_V1"
    )
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is True
    assert evidence["implementation_complete"] is True
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
