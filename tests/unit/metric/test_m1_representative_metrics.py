from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tpaa_metric import (
    MetricComputationError,
    MetricStagingArea,
    build_metric_context,
    compute_representative_metrics,
)
from tpaa_world import project_minimal_p1_world

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY_ROOT = ROOT / "baseline" / "CB-1.4.0" / "canonical"
RELEASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _compute(fixture_id: str, *, stage_id: str | None = None):
    bundle = FIXTURES / fixture_id
    world = project_minimal_p1_world(
        bundle,
        authority_root=AUTHORITY_ROOT,
        release_id=RELEASE_ID,
    )
    context = build_metric_context(bundle, authority_root=AUTHORITY_ROOT, world=world)
    return world, context, compute_representative_metrics(context, world, stage_id=stage_id)


def _by_code(batch):
    return {result.metric_code: result for result in batch.results}


def test_metric_context_binds_exact_authorities_and_all_required_ref_classes() -> None:
    world, context, _ = _compute("BF_M1_NOMINAL_V1")

    assert context.subject_type == "AIRCRAFT"
    assert context.subject_id == world.aircraft_id
    assert context.catalog_id == "P1_METRIC_CATALOG"
    assert context.profile_id == "M1_BASIC_AIR_PROFILE_V1"
    assert tuple(item.metric_code for item in context.authorities) == (
        "P1-AIR-001",
        "P1-AIR-002",
        "P1-AIR-003",
        "P1-AIR-004",
        "P1-AIR-007",
    )
    assert {ref.ref_class for ref in context.input_refs} >= {
        "EVALUATION_CONTEXT",
        "CANONICAL",
        "EPISODE",
        "STAGE",
        "WORLD",
        "EVIDENCE",
    }
    assert context.latest_fallback_used is False
    assert context.ui_or_database_inference_used is False


def test_nominal_five_metric_results_match_independent_expected_values() -> None:
    _, _, batch = _compute("BF_M1_NOMINAL_V1")
    metrics = _by_code(batch)

    assert metrics["P1-AIR-001"].value_numeric == pytest.approx(0.6)
    assert metrics["P1-AIR-002"].value_numeric == pytest.approx(2.5)
    assert dict(metrics["P1-AIR-002"].evidence.details)["diagnostic_min_nz_g"] == "1.0"
    assert metrics["P1-AIR-003"].value_numeric == pytest.approx(0.1)
    assert metrics["P1-AIR-004"].value_numeric == pytest.approx(0.1)
    envelope = metrics["P1-AIR-007"].value_structured
    assert envelope is not None
    assert envelope.as_dict() == {
        "tas": {
            "status": "VALID",
            "n": 8,
            "min_mps": 100.0,
            "max_mps": 135.0,
            "p05_mps": 101.75,
            "p50_mps": 117.5,
            "p95_mps": 133.25,
        },
        "mach": {
            "status": "VALID",
            "n": 8,
            "min": 0.3,
            "max": 0.37,
            "p05": pytest.approx(0.3035),
            "p50": pytest.approx(0.335),
            "p95": pytest.approx(0.3665),
        },
    }
    assert all(result.status == "VALID" for result in batch.results)
    assert batch.publication_executed is False
    assert batch.database_persistence_executed is False


def test_heading_unwrap_prevents_false_2pi_spike() -> None:
    _, _, batch = _compute("BF_M1_ANGLE_WRAP_V1")
    result = _by_code(batch)["P1-AIR-003"]

    assert result.status == "VALID"
    assert result.value_numeric == pytest.approx(0.03490658503988659)
    assert result.value_numeric < 0.1
    assert dict(result.evidence.details)["operator"] == "DERIVATIVE_LLS_V1"


def test_gap_fails_closed_without_fabricating_zero() -> None:
    _, _, batch = _compute("BF_M1_GAP_V1")
    metrics = _by_code(batch)

    for code in ("P1-AIR-001", "P1-AIR-004"):
        result = metrics[code]
        assert result.status == "INSUFFICIENT_DATA"
        assert result.reason_codes == ("MAX_GAP_EXCEEDED",)
        assert result.value_numeric is None
        assert result.value_structured is None


def test_structured_partial_channels_are_independent_and_typed() -> None:
    _, _, batch = _compute("BF_M1_STRUCTURED_PARTIAL_V1")
    result = _by_code(batch)["P1-AIR-007"]
    envelope = result.value_structured

    assert result.status == "VALID"
    assert result.value_kind == "STRUCTURED"
    assert result.value_numeric is None
    assert envelope is not None
    assert envelope.schema_id == "STRUCT_P1_AIR_007_V1"
    assert envelope.tas.n == 4
    assert envelope.tas.p50 == pytest.approx(115.0)
    assert envelope.mach.n == 4
    assert envelope.mach.p50 == pytest.approx(0.34)


def test_half_open_stage_membership_controls_metric_window() -> None:
    bundle = FIXTURES / "BF_M1_STAGE_BOUNDARY_V1"
    world = project_minimal_p1_world(
        bundle,
        authority_root=AUTHORITY_ROOT,
        release_id=RELEASE_ID,
    )
    context = build_metric_context(bundle, authority_root=AUTHORITY_ROOT, world=world)
    setup = compute_representative_metrics(context, world, stage_id=world.stages[0].stage_id)
    execution = compute_representative_metrics(context, world, stage_id=world.stages[1].stage_id)

    assert _by_code(setup)["P1-AIR-001"].value_numeric == pytest.approx(0.5)
    assert _by_code(execution)["P1-AIR-001"].value_numeric == pytest.approx(9.0)


def test_compute_is_replay_stable_and_stages_atomically_without_publish() -> None:
    _, context, first = _compute("BF_M1_CROSS_PLATFORM_V1")
    _, _, second = _compute("BF_M1_CROSS_PLATFORM_V1")
    staging = MetricStagingArea()

    assert first == second
    staging.stage(first)
    before = dict(staging.staged)
    with pytest.raises(MetricComputationError):
        staging.stage(replace(first, staging_status="FAILED"))
    assert dict(staging.staged) == before
    assert dict(staging.current_published) == {}
    assert context.latest_fallback_used is False


def test_subject_applicability_gate_fails_closed() -> None:
    world, context, _ = _compute("BF_M1_NOMINAL_V1")

    with pytest.raises(MetricComputationError) as caught:
        compute_representative_metrics(replace(context, subject_type="TARGET_PAIR"), world)

    assert caught.value.code == "M1_METRIC_CONTEXT_SUBJECT_DRIFT"
