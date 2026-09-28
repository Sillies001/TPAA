from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tpaa_metric import build_m3_metric_execution_plan
from tpaa_observation import (
    M2PublicationRoutingError,
    build_m2_publication_routing_plan,
    build_m3_publication_routing_plan,
    route_m2_metric_definition,
)

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
CHECK = ROOT / "tools" / "testing" / "m3_publication_routing_check.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECK), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_m3_obs_001_routes_exact_116_and_preserves_foundation() -> None:
    plan = build_m3_publication_routing_plan(AUTHORITY)
    foundation = build_m2_publication_routing_plan(AUTHORITY)

    assert len(plan.targets) == 116
    assert len(set(plan.metric_codes)) == 116
    assert len(plan.logical_hash) == 64
    assert plan.foundation_publication_routing_plan_hash == foundation.logical_hash

    by_code = {target.metric_code: target for target in plan.targets}
    for target in foundation.targets:
        assert by_code[target.metric_code] == target

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

    assert capability == {
        *(f"P1-AIR-{index:03d}" for index in range(1, 40)),
    }
    assert evidence_only == {
        "P1-QA-001",
        "P1-QA-002",
        "P1-QA-005",
        "P1-QA-007",
        "P1-QA-008",
    }
    assert len(system) == 72
    assert {
        *(f"P1-TRK-{index:03d}" for index in range(1, 8)),
        *(f"P1-ID-{index:03d}" for index in range(1, 13)),
        *(f"P1-PSV-{index:03d}" for index in range(1, 8)),
        *(f"P1-ESM-{index:03d}" for index in range(1, 7)),
        *(f"P1-DL-{index:03d}" for index in range(1, 9)),
        *(f"P1-FUS-{index:03d}" for index in range(1, 9)),
    } <= system


def test_m3_obs_001_routing_fails_closed_on_remainder_contract_drift() -> None:
    metric_plan = build_m3_metric_execution_plan(AUTHORITY)
    by_code = {
        definition.metric_code: definition
        for definition in metric_plan.definitions
    }

    with pytest.raises(M2PublicationRoutingError) as unknown:
        route_m2_metric_definition(
            replace(
                by_code["P1-FUS-001"],
                publication_route="UNKNOWN_ROUTE",
            )
        )
    assert unknown.value.code == "M2_PUBLICATION_ROUTE_UNKNOWN"

    with pytest.raises(M2PublicationRoutingError) as lane:
        route_m2_metric_definition(
            replace(
                by_code["P1-AIR-039"],
                observation_lane="SYSTEM_PERFORMANCE_OBSERVATION",
            )
        )
    assert lane.value.code == "M2_PUBLICATION_LANE_MISMATCH"

    with pytest.raises(M2PublicationRoutingError) as subject:
        route_m2_metric_definition(
            replace(by_code["P1-DL-001"], subject_type="AIRCRAFT")
        )
    assert subject.value.code == "M2_PUBLICATION_SUBJECT_MISMATCH"


def test_m3_obs_001_evidence_and_cross_platform_contract(tmp_path: Path) -> None:
    source = tmp_path / "publication-routing.json"
    checked = _run(
        "check",
        "--evidence",
        str(source),
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr

    payload = json.loads(source.read_text(encoding="utf-8"))
    assert payload["schema"] == "TPAA_M3_OBS_001_PUBLICATION_ROUTING_EVIDENCE_V1"
    assert payload["task_id"] == "M3-OBS-001"
    assert payload["tracking_issue"] == 116
    assert payload["status"] == "PASS"
    assert payload["task_complete"] is True
    assert payload["implementation_complete"] is True
    assert payload["failed_acceptance"] == []
    assert all(payload["acceptance"].values())
    assert payload["logical_product"]["route_counts"] == {
        "CAPABILITY_OBSERVATION": 39,
        "METRIC_INSTANCE_EVIDENCE_ONLY": 5,
        "SYSTEM_PERFORMANCE_OBSERVATION": 72,
    }
    assert payload["logical_product"]["lane_counts"] == {
        "AIRCRAFT_CAP_L1_OBSERVATION": 39,
        "QUALITY_EVIDENCE_ONLY": 5,
        "SYSTEM_PERFORMANCE_OBSERVATION": 72,
    }
    assert payload["scope"]["metric_values_recomputed"] is False
    assert payload["scope"]["database_persistence_executed"] is False

    revision = payload["source_revision"]
    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"
    result = _run(
        "compare",
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
        "TPAA_M3_OBS_001_PUBLICATION_ROUTING_CROSS_PLATFORM_EVIDENCE_V1"
    )
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is True
    assert evidence["implementation_complete"] is True
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
