"""Consolidated machine evidence for M1 execution Batch 1 (#86)."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import cast
from uuid import UUID, uuid5

from tpaa_episode import project_basic_flight_stage_quality, supersede_stage
from tpaa_ingest import GOVERNED_FIXTURE_IDS
from tpaa_metric import (
    MetricResult,
    MetricStagingArea,
    build_metric_context,
    compute_representative_metrics,
)
from tpaa_world import project_minimal_p1_world

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY_ROOT = ROOT / "baseline" / "CB-1.4.0" / "canonical"
RELEASE_NAMESPACE = UUID("ef9be1ed-f928-43e5-a7ef-e89ce57b68c2")
BATCH_ID = "M1-BATCH-1-CORE-PRODUCT"
TASK_IDS = (
    "M1-WORLD-004",
    "M1-WORLD-005",
    "M1-WORLD-006",
    "M1-WORLD-007",
    "M1-MET-001",
    "M1-MET-002",
    "M1-MET-003",
    "M1-MET-004",
    "M1-MET-005",
    "M1-MET-006",
    "M1-MET-007",
    "M1-MET-008",
    "M1-TST-002",
    "M1-TST-003",
)


def _load_object(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ValueError(f"invalid object: {path}")
    return cast(dict[str, object], raw)


def _metric_map(results: tuple[MetricResult, ...]) -> dict[str, MetricResult]:
    return {result.metric_code: result for result in results}


def _close(actual: float | None, expected: float) -> bool:
    return actual is not None and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)


def _stage_golden_ok(bundle: Path) -> bool:
    expected = _load_object(bundle / "expected" / "expected.json")
    raw_stages = expected.get("stages")
    if not isinstance(raw_stages, list):
        return False
    projection = project_basic_flight_stage_quality(bundle, authority_root=AUTHORITY_ROOT)
    actual = [
        {
            "stage_type": stage.stage_type,
            "start_session_time_us": str(stage.start_session_time_us),
            "end_session_time_us": str(stage.end_session_time_us),
        }
        for stage in projection.stages
    ]
    return actual == raw_stages and all(
        stage.stage_status == "VALID" and stage.coverage == 1.0 and stage.confidence == 1.0
        for stage in projection.stages
    )


def _nominal_golden_ok(metrics: dict[str, MetricResult]) -> bool:
    envelope = metrics["P1-AIR-007"].value_structured
    return (
        _close(metrics["P1-AIR-001"].value_numeric, 0.6)
        and _close(metrics["P1-AIR-002"].value_numeric, 2.5)
        and _close(metrics["P1-AIR-003"].value_numeric, 0.1)
        and _close(metrics["P1-AIR-004"].value_numeric, 0.1)
        and envelope is not None
        and envelope.tas.n == 8
        and _close(envelope.tas.p05, 101.75)
        and _close(envelope.tas.p50, 117.5)
        and _close(envelope.tas.p95, 133.25)
        and envelope.mach.n == 8
        and _close(envelope.mach.p05, 0.3035)
        and _close(envelope.mach.p50, 0.335)
        and _close(envelope.mach.p95, 0.3665)
    )


def run(evidence: Path | None) -> int:
    failures: list[str] = []
    worlds: dict[str, str] = {}
    batches: dict[str, str] = {}
    all_stage_golden = True
    all_world_minimal = True
    all_world_refs = True
    all_context_exact = True
    all_value_slots_exact = True
    all_staging_atomic = True
    stage_revision_ok = False
    nominal_ok = False
    angle_wrap_ok = False
    gap_ok = False
    structured_partial_ok = False
    stage_boundary_ok = False

    for fixture_id in GOVERNED_FIXTURE_IDS:
        bundle = FIXTURE_ROOT / fixture_id
        release_id = str(uuid5(RELEASE_NAMESPACE, fixture_id))
        try:
            world = project_minimal_p1_world(
                bundle,
                authority_root=AUTHORITY_ROOT,
                release_id=release_id,
            )
            replayed_world = project_minimal_p1_world(
                bundle,
                authority_root=AUTHORITY_ROOT,
                release_id=release_id,
            )
            context = build_metric_context(bundle, authority_root=AUTHORITY_ROOT, world=world)
            batch = compute_representative_metrics(context, world)
            replayed_batch = compute_representative_metrics(context, replayed_world)
            metrics = _metric_map(batch.results)
            staging = MetricStagingArea()
            staging.stage(batch)

            worlds[fixture_id] = world.logical_content_hash
            batches[fixture_id] = batch.logical_hash
            all_stage_golden = all_stage_golden and _stage_golden_ok(bundle)
            all_world_minimal = all_world_minimal and (
                world == replayed_world
                and world.present_capability_letters == ("C", "W", "A", "M")
                and world.absent_capability_letters == ("P", "J")
                and not world.database_persistence_executed
                and not world.release_publication_executed
                and not world.metric_logic_executed
            )
            ref_classes = {ref.ref_class for ref in context.input_refs}
            all_world_refs = all_world_refs and (
                {"EVALUATION_CONTEXT", "CANONICAL", "EPISODE", "STAGE", "WORLD", "EVIDENCE"}
                <= ref_classes
            )
            all_context_exact = all_context_exact and (
                context.subject_type == "AIRCRAFT"
                and context.subject_id == world.aircraft_id
                and not context.latest_fallback_used
                and not context.ui_or_database_inference_used
            )
            all_value_slots_exact = all_value_slots_exact and all(
                (
                    result.status != "VALID"
                    and result.value_numeric is None
                    and result.value_structured is None
                )
                or (
                    result.value_kind == "NUMERIC"
                    and result.value_numeric is not None
                    and result.value_structured is None
                )
                or (
                    result.value_kind == "STRUCTURED"
                    and result.value_structured is not None
                    and result.value_numeric is None
                )
                for result in batch.results
            )
            all_staging_atomic = all_staging_atomic and (
                batch == replayed_batch
                and len(staging.staged) == 1
                and not staging.current_published
                and not batch.publication_executed
                and not batch.database_persistence_executed
            )

            if fixture_id == "BF_M1_NOMINAL_V1":
                nominal_ok = _nominal_golden_ok(metrics)
                original = world.stages[0]
                revised = supersede_stage(original, correction_key="batch-1-revision-smoke")
                stage_revision_ok = (
                    revised.stage_id != original.stage_id
                    and revised.supersedes_stage_id == original.stage_id
                    and original.supersedes_stage_id is None
                )
            elif fixture_id == "BF_M1_ANGLE_WRAP_V1":
                angle_wrap_ok = _close(metrics["P1-AIR-003"].value_numeric, 0.03490658503988659)
            elif fixture_id == "BF_M1_GAP_V1":
                gap_ok = all(
                    metrics[code].status == "INSUFFICIENT_DATA"
                    and metrics[code].reason_codes == ("MAX_GAP_EXCEEDED",)
                    and metrics[code].value_numeric is None
                    for code in ("P1-AIR-001", "P1-AIR-004")
                )
            elif fixture_id == "BF_M1_STRUCTURED_PARTIAL_V1":
                envelope = metrics["P1-AIR-007"].value_structured
                structured_partial_ok = (
                    envelope is not None
                    and envelope.schema_id == "STRUCT_P1_AIR_007_V1"
                    and envelope.tas.n == 4
                    and envelope.mach.n == 4
                    and _close(envelope.tas.p50, 115.0)
                    and _close(envelope.mach.p50, 0.34)
                )
            elif fixture_id == "BF_M1_STAGE_BOUNDARY_V1":
                setup = compute_representative_metrics(
                    context,
                    world,
                    stage_id=world.stages[0].stage_id,
                )
                execution = compute_representative_metrics(
                    context,
                    world,
                    stage_id=world.stages[1].stage_id,
                )
                stage_boundary_ok = _close(
                    _metric_map(setup.results)["P1-AIR-001"].value_numeric, 0.5
                ) and _close(_metric_map(execution.results)["P1-AIR-001"].value_numeric, 9.0)
        except Exception as exc:  # noqa: BLE001 - evidence must capture all fixture failures
            failures.append(f"{fixture_id}:{type(exc).__name__}:{exc}")

    acceptance = {
        "minimal_world_no_fabricated_p_j": all_world_minimal,
        "stage_revision_is_immutable_supersede": stage_revision_ok,
        "world_logical_hash_replay_stable": len(worlds) == len(GOVERNED_FIXTURE_IDS),
        "world_and_metric_evidence_refs_exact": all_world_refs,
        "metric_context_exact_no_latest_or_ui_db_guess": all_context_exact,
        "p1_air_001_nominal_gap_and_stage_boundary": nominal_ok and gap_ok and stage_boundary_ok,
        "p1_air_002_primary_and_diagnostic_separated": nominal_ok,
        "p1_air_003_unwrap_derivative_lls": nominal_ok and angle_wrap_ok,
        "p1_air_004_rolling_median_dwell_and_gap": nominal_ok and gap_ok,
        "p1_air_007_typed_structured_partial": nominal_ok and structured_partial_ok,
        "applicability_and_value_slots_exact": all_value_slots_exact,
        "metric_compute_staging_atomic_and_unpublished": all_staging_atomic,
        "five_metric_nominal_edge_failure_golden": (
            nominal_ok and angle_wrap_ok and gap_ok and structured_partial_ok and stage_boundary_ok
        ),
        "four_stage_boundaries_golden_exact": all_stage_golden,
    }
    failed_acceptance = sorted(name for name, passed in acceptance.items() if not passed)
    status = "PASS" if not failures and not failed_acceptance else "FAIL"
    payload: dict[str, object] = {
        "schema": "TPAA_M1_BATCH_1_CORE_EVIDENCE_V1",
        "batch_id": BATCH_ID,
        "tracking_issue": 86,
        "task_ids": list(TASK_IDS),
        "status": status,
        "fixture_count": len(worlds),
        "world_logical_hashes": worlds,
        "metric_batch_hashes": batches,
        "acceptance": acceptance,
        "failed_acceptance": failed_acceptance,
        "failures": failures,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if evidence is not None:
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"M1_BATCH_1_EVIDENCE_WRITTEN {evidence}")
    return 0 if status == "PASS" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args(argv)
    return run(args.evidence)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
