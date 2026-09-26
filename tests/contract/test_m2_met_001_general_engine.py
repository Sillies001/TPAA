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


def test_m2_met_001_plan_is_exact_frozen_foundation_authority() -> None:
    plan = build_m2_metric_execution_plan(AUTHORITY)

    assert plan.delivery_milestone == "M2"
    assert plan.delivery_batch == "P1_FOUNDATION_32"
    assert len(plan.catalog_metric_codes) == 32
    assert set(plan.metric_codes) == set(plan.catalog_metric_codes)
    assert all(
        definition.metric_code.startswith(("P1-QA-", "P1-AIR-", "P1-SNS-"))
        for definition in plan.definitions
    )
    assert all(
        definition.applicability.allowed_system_types == ("RADAR",)
        for definition in plan.definitions
        if definition.metric_code.startswith("P1-SNS-")
    )


def test_m2_met_001_evidence_proves_general_engine_contract(tmp_path: Path) -> None:
    evidence_path = tmp_path / "engine.json"
    result = _run(
        "m2-general-metric-engine-check",
        "--evidence",
        str(evidence_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M2_MET_001_GENERAL_ENGINE_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-MET-001"
    assert evidence["tracking_issue"] == 97
    assert evidence["status"] == "PASS"
    assert evidence["failed_acceptance"] == []
    assert all(evidence["acceptance"].values())

    product = evidence["logical_product"]
    assert product["delivery_milestone"] == "M2"
    assert product["delivery_batch"] == "P1_FOUNDATION_32"
    assert len(product["catalog_metric_codes"]) == 32
    assert len(product["execution_metric_codes"]) == 32
    assert product["dispatch_key"] == "algorithm_id"
    assert len(product["required_operator_ids"]) == 8
    assert len(product["plan_logical_hash"]) == 64
    assert len(product["execution_logical_hash"]) == 64
    assert evidence["acceptance"]["governed_formula_dependency_closure_exact_32"]
    assert product["formula_dependency_references"]["P1-QA-003"] == [
        ["OPERATOR", "MEAN_V1"],
        ["OPERATOR", "QUANTILE_HF7_V1"],
        ["OPERATOR", "RMS_V1"],
        ["STATE_MACHINE", "SM_CLOCK_SEGMENT_V1"],
    ]
    assert len(product["plugin_manifest_hash"]) == 64
    assert len(product["plugin_identity_manifest"]) == 32
    assert all(
        len(item) == 3 and item[1] != "UNVERSIONED"
        for item in product["plugin_identity_manifest"]
    )

    scope = evidence["scope"]
    assert scope["business_metric_semantics_executed"] is False
    assert scope["family_specific_engine_created"] is False
    assert scope["database_persistence_executed"] is False
    assert scope["publication_executed"] is False


def test_m2_met_001_cross_platform_compare_is_revision_exact(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    checked = _run(
        "m2-general-metric-engine-check",
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

    result = _run(
        "m2-general-metric-engine-compare",
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
    assert evidence["schema"] == "TPAA_M2_MET_001_CROSS_PLATFORM_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-MET-001"
    assert evidence["tracking_issue"] == 97
    assert evidence["status"] == "PASS"
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
