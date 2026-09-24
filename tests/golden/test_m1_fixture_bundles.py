from __future__ import annotations

import json

from tools.testing.m1_fixture_harness import FIXTURE_ROOT, load_spec, validate_all


def test_m1_tst_001_all_eight_fixture_bundles_validate() -> None:
    evidence = validate_all()

    assert evidence["schema"] == "TPAA_M1_TST_001_FIXTURE_EVIDENCE_V1"
    assert evidence["task_id"] == "M1-TST-001"
    assert evidence["status"] == "PASS"
    assert evidence["bundle_count"] == 8
    assert evidence["reviewed_bundle_count"] == 8
    assert evidence["business_logic_executed"] is False

    bundles = evidence["bundles"]
    assert isinstance(bundles, list)
    assert {item["fixture_id"] for item in bundles} == {
        "BF_M1_NOMINAL_V1",
        "BF_M1_GAP_V1",
        "BF_M1_ANGLE_WRAP_V1",
        "BF_M1_STRUCTURED_PARTIAL_V1",
        "BF_M1_STAGE_BOUNDARY_V1",
        "BF_M1_REPLAY_V1",
        "BF_M1_CROSS_PLATFORM_V1",
        "BF_M1_FAILURE_V1",
    }
    assert all(item["review_state"] == "REVIEWED" for item in bundles)


def test_bf_m1_nominal_v1_has_independent_reference_expectations() -> None:
    spec = load_spec(FIXTURE_ROOT / "BF_M1_NOMINAL_V1")
    expected = json.loads(spec.expected_path.read_text(encoding="utf-8"))

    generation = expected["expected_generation"]
    assert generation["generated_from_implementation_under_test"] is False
    assert generation["independently_reviewable"] is True
    assert generation["method"] == "human_recalculation"

    metrics = expected["scenario_expectations"]["metrics"]
    assert metrics["P1-AIR-001"]["value"] == 0.6
    assert metrics["P1-AIR-002"]["value"] == 2.5
    assert metrics["P1-AIR-003"]["value"] == 0.1
    assert metrics["P1-AIR-004"]["value"] == 0.1

    envelope = metrics["P1-AIR-007"]["value"]
    assert envelope["tas"]["n"] == 8
    assert envelope["tas"]["p50_mps"] == 117.5
    assert envelope["mach"]["n"] == 8
    assert envelope["mach"]["p95"] == 0.3665


def test_bf_m1_nominal_v1_stage_contract_is_exact() -> None:
    spec = load_spec(FIXTURE_ROOT / "BF_M1_NOMINAL_V1")
    expected = json.loads(spec.expected_path.read_text(encoding="utf-8"))

    stages = expected["stages"]
    assert [item["stage_type"] for item in stages] == [
        "SETUP_ENTRY",
        "EXECUTION",
        "STABILIZATION_RECOVERY",
        "COMPLETION",
    ]
    intervals = [
        (item["start_session_time_us"], item["end_session_time_us"])
        for item in stages
    ]
    assert intervals == [
        ("1000000", "3000000"),
        ("3000000", "5000000"),
        ("5000000", "7000000"),
        ("7000000", "9000000"),
    ]
