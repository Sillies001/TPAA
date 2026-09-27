from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tpaa_metric import build_m2_metric_execution_plan
from tpaa_observation import (
    M2PublicationRoutingError,
    build_m2_publication_routing_plan,
    route_m2_metric_definition,
)

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


def test_m2_obs_001_routes_exact_foundation_32_from_catalog() -> None:
    plan = build_m2_publication_routing_plan(AUTHORITY)
    assert len(plan.targets) == 32
    assert len(set(plan.metric_codes)) == 32
    assert len(plan.logical_hash) == 64

    capability = {
        target.metric_code
        for target in plan.targets
        if target.publication_route == "CAPABILITY_OBSERVATION"
    }
    evidence_only = {
        target.metric_code
        for target in plan.targets
        if target.publication_route == "METRIC_INSTANCE_EVIDENCE_ONLY"
    }
    system = {
        target.metric_code
        for target in plan.targets
        if target.publication_route == "SYSTEM_PERFORMANCE_OBSERVATION"
    }

    assert capability == {"P1-AIR-001", "P1-AIR-002", "P1-AIR-003"}
    assert evidence_only == {
        "P1-QA-001",
        "P1-QA-002",
        "P1-QA-005",
        "P1-QA-007",
        "P1-QA-008",
    }
    assert system == {
        "P1-QA-003",
        "P1-QA-004",
        "P1-QA-006",
        *(f"P1-SNS-{index:03d}" for index in range(1, 22)),
    }
    assert all(
        target.persist_metric_instance and target.persist_evidence_set
        for target in plan.targets
    )
    assert all(
        target.observation_record_type is None
        for target in plan.targets
        if target.publication_route == "METRIC_INSTANCE_EVIDENCE_ONLY"
    )


def test_m2_obs_001_routing_fails_closed_on_catalog_contract_drift() -> None:
    metric_plan = build_m2_metric_execution_plan(AUTHORITY)
    by_code = {
        definition.metric_code: definition
        for definition in metric_plan.definitions
    }

    with pytest.raises(M2PublicationRoutingError) as unknown:
        route_m2_metric_definition(
            replace(
                by_code["P1-QA-001"],
                publication_route="UNKNOWN_ROUTE",
            )
        )
    assert unknown.value.code == "M2_PUBLICATION_ROUTE_UNKNOWN"

    with pytest.raises(M2PublicationRoutingError) as lane:
        route_m2_metric_definition(
            replace(
                by_code["P1-AIR-001"],
                observation_lane="QUALITY_EVIDENCE_ONLY",
            )
        )
    assert lane.value.code == "M2_PUBLICATION_LANE_MISMATCH"

    with pytest.raises(M2PublicationRoutingError) as subject:
        route_m2_metric_definition(
            replace(by_code["P1-AIR-001"], subject_type="TARGET_PAIR")
        )
    assert subject.value.code == "M2_PUBLICATION_SUBJECT_MISMATCH"

    with pytest.raises(M2PublicationRoutingError) as trend:
        route_m2_metric_definition(
            replace(
                by_code["P1-QA-001"],
                p1_longitudinal_trend_eligibility=True,
            )
        )
    assert trend.value.code == "M2_PUBLICATION_QUALITY_TREND_FORBIDDEN"


def test_m2_obs_001_evidence_and_cross_platform_contract(tmp_path: Path) -> None:
    source = tmp_path / "publication-routing.json"
    checked = _run(
        "m2-publication-routing-check",
        "--evidence",
        str(source),
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr

    payload = json.loads(source.read_text(encoding="utf-8"))
    assert payload["schema"] == "TPAA_M2_OBS_001_PUBLICATION_ROUTING_EVIDENCE_V1"
    assert payload["task_id"] == "M2-OBS-001"
    assert payload["tracking_issue"] == 98
    assert payload["status"] == "PASS"
    assert payload["task_complete"] is True
    assert payload["implementation_complete"] is True
    assert payload["failed_acceptance"] == []
    assert all(payload["acceptance"].values())
    assert payload["logical_product"]["route_counts"] == {
        "CAPABILITY_OBSERVATION": 3,
        "METRIC_INSTANCE_EVIDENCE_ONLY": 5,
        "SYSTEM_PERFORMANCE_OBSERVATION": 24,
    }
    assert payload["logical_product"]["lane_counts"] == {
        "AIRCRAFT_CAP_L1_OBSERVATION": 3,
        "QUALITY_EVIDENCE_ONLY": 5,
        "SYSTEM_PERFORMANCE_OBSERVATION": 24,
    }
    assert payload["scope"]["business_metric_semantics_executed"] is False
    assert payload["scope"]["metric_values_recomputed"] is False
    assert payload["scope"]["database_persistence_executed"] is False

    revision = payload["source_revision"]
    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"
    result = _run(
        "m2-publication-routing-compare",
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
        "TPAA_M2_OBS_001_PUBLICATION_ROUTING_CROSS_PLATFORM_EVIDENCE_V1"
    )
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is True
    assert evidence["implementation_complete"] is True
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
