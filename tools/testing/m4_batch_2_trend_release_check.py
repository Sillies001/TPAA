#!/usr/bin/env python3
"""M4 Batch 2 executable evidence for trend, Release and replay."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = str(REPO_ROOT / "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from tpaa_longitudinal import (  # noqa: E402
    InMemoryM4LongitudinalReleaseRepository,
    M4LongitudinalError,
    M4LongitudinalPublicationService,
    M4LongitudinalReleaseSnapshot,
    M4LongitudinalSample,
    M4LongitudinalScope,
    M4PerformanceTrendSeries,
    M4TrendBridge,
    allocate_m4_longitudinal_release_id,
    build_m4_longitudinal_release,
    build_performance_trend_series,
    load_m4_trend_authority,
)

BASELINE = REPO_ROOT / "baseline" / "CB-1.4.0"
AUTHORITY_PATH = (
    BASELINE / "canonical" / "M4_LONGITUDINAL_DEBRIEF_AUTHORITY.json"
)
TRACKING_ISSUE = 127
LONGITUDINAL_SCOPE_ID = "50000000-0000-4000-8000-000000000001"
METRIC_DEFINITION_ID = "50000000-0000-4000-8000-000000000002"
COMPUTE_JOB_ID = "50000000-0000-4000-8000-000000000003"
CREATED_AT = "2026-09-28T11:00:00Z"
PUBLISHED_AT = "2026-09-28T11:01:00Z"


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    value = completed.stdout.strip()
    return value if len(value) == 40 else "UNKNOWN"


def _payload() -> dict[str, object]:
    raw: object = json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("authority root invalid")
    return raw


def _scope(
    *,
    semantic_version: int = 1,
    comparison_key_hash: str | None = None,
) -> M4LongitudinalScope:
    golden = _payload()["golden_vectors"]
    if not isinstance(golden, dict):
        raise ValueError("golden_vectors invalid")
    scope_golden = golden["longitudinal_scope"]
    if not isinstance(scope_golden, dict):
        raise ValueError("longitudinal_scope golden invalid")
    descriptor = scope_golden["descriptor"]
    if not isinstance(descriptor, dict):
        raise ValueError("scope descriptor invalid")
    key = str(scope_golden["expected_longitudinal_scope_key"])
    comparison = (
        comparison_key_hash
        if comparison_key_hash is not None
        else str(descriptor["comparison_key_hash"])
    )
    material = dict(descriptor)
    material["metric_semantic_version"] = semantic_version
    material["comparison_key_hash"] = comparison
    return M4LongitudinalScope(
        longitudinal_scope_key=key,
        subject_type=str(descriptor["subject_type"]),
        subject_id=str(descriptor["subject_id"]),
        metric_semantic_id=str(descriptor["metric_semantic_id"]),
        metric_semantic_version=semantic_version,
        comparison_key_hash=comparison,
        session_order_scope_id=str(descriptor["session_order_scope_id"]),
        trend_profile_version=str(descriptor["trend_profile_version"]),
        descriptor_json=json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ),
        descriptor_hash=key,
    )


def _samples(
    *,
    semantic_version: int = 1,
    comparison_key_hash: str | None = None,
) -> tuple[M4LongitudinalSample, ...]:
    golden = _payload()["golden_vectors"]
    if not isinstance(golden, dict):
        raise ValueError("golden_vectors invalid")
    trend = golden["trend"]
    if not isinstance(trend, dict):
        raise ValueError("trend golden invalid")
    points = trend["points"]
    if not isinstance(points, list):
        raise ValueError("trend points invalid")
    scope = _scope(
        semantic_version=semantic_version,
        comparison_key_hash=comparison_key_hash,
    )
    result: list[M4LongitudinalSample] = []
    for index, point_raw in enumerate(points, start=1):
        if not isinstance(point_raw, dict):
            raise ValueError("trend point invalid")
        status = str(point_raw["status"])
        value = point_raw["value"]
        result.append(
            M4LongitudinalSample(
                sample_id=str(point_raw["sample_id"]),
                release_id=(
                    f"51000000-0000-4000-8000-{index:012d}"
                ),
                release_scope_type="SESSION",
                subject_type=scope.subject_type,
                subject_id=scope.subject_id,
                aircraft_id=scope.subject_id,
                mission_system_instance_id=None,
                session_id=(
                    f"52000000-0000-4000-8000-{index:012d}"
                ),
                session_order_scope_id=scope.session_order_scope_id,
                session_order=int(point_raw["session_order"]),
                occurred_at_utc=None,
                configuration_key=(
                    "AIRCRAFT_CONFIG_SHA256:" + "a" * 64
                ),
                metric_definition_id=METRIC_DEFINITION_ID,
                metric_semantic_id=scope.metric_semantic_id,
                metric_semantic_version=semantic_version,
                comparison_key_hash=scope.comparison_key_hash,
                sample_unit="SESSION_CONFIG",
                aggregation_method="MEDIAN",
                value_numeric=(
                    float(value) if value is not None else None
                ),
                status=status,
                reason_codes=(
                    ("SOURCE_GAP",)
                    if status != "VALID"
                    else ()
                ),
                source_observation_refs=(),
                source_episode_count=1 if status == "VALID" else 0,
                coverage=1.0,
                confidence=1.0,
                sample_profile_version="1.0.0",
                logical_content_hash=str(
                    point_raw["logical_content_hash"]
                ),
            )
        )
    return tuple(result)


def _request_hash(character: str) -> str:
    return character * 64


def _series(
    *,
    request_hash: str,
    scope: M4LongitudinalScope | None = None,
    samples: tuple[M4LongitudinalSample, ...] | None = None,
    bridges: tuple[M4TrendBridge, ...] = (),
) -> M4PerformanceTrendSeries:
    actual_scope = scope or _scope()
    actual_samples = samples or _samples()
    release_id = allocate_m4_longitudinal_release_id(
        longitudinal_scope_key=actual_scope.longitudinal_scope_key,
        request_hash=request_hash,
    )
    return build_performance_trend_series(
        authority=load_m4_trend_authority(BASELINE),
        release_id=release_id,
        longitudinal_scope_id=LONGITUDINAL_SCOPE_ID,
        metric_definition_id=METRIC_DEFINITION_ID,
        metric_unit="metric_unit",
        scope=actual_scope,
        samples=actual_samples,
        bridges=bridges,
        created_at_utc=CREATED_AT,
    )


def _release(
    *,
    request_hash: str,
    release_no: int = 1,
    parent_release_id: str | None = None,
) -> M4LongitudinalReleaseSnapshot:
    scope = _scope()
    series = _series(
        request_hash=request_hash,
        scope=scope,
    )
    return build_m4_longitudinal_release(
        release_id=series.release_id,
        request_hash=request_hash,
        release_no=release_no,
        parent_release_id=parent_release_id,
        compute_job_id=COMPUTE_JOB_ID,
        catalog_version="1.14.0",
        catalog_hash=(
            "24ab6d06ced0b768ff16e4c945e778cc"
            "8fd2d3838be3ca30051ec8f8e0d7277d"
        ),
        context_binding_hash="c" * 64,
        longitudinal_scope_id=LONGITUDINAL_SCOPE_ID,
        scope=scope,
        trend_series=series,
        created_at_utc=CREATED_AT,
    )


def _error_code(action: Callable[[], object]) -> str:
    try:
        action()
    except M4LongitudinalError as exc:
        return exc.code
    return "NO_ERROR"


def verify() -> dict[str, object]:
    payload = _payload()
    golden = payload["golden_vectors"]
    if not isinstance(golden, dict):
        raise ValueError("golden_vectors invalid")
    trend_golden = golden["trend"]
    if not isinstance(trend_golden, dict):
        raise ValueError("trend golden invalid")
    expected = trend_golden["expected"]
    if not isinstance(expected, dict):
        raise ValueError("trend expected invalid")

    golden_series = _series(request_hash=_request_hash("a"))
    base_samples = _samples()
    insufficient = _series(
        request_hash=_request_hash("b"),
        samples=base_samples[:2],
    )
    no_valid = tuple(
        replace(
            sample,
            status="INSUFFICIENT_DATA",
            value_numeric=None,
        )
        for sample in base_samples[:2]
    )
    no_valid_series = _series(
        request_hash=_request_hash("d"),
        samples=no_valid,
    )
    duplicate_error = _error_code(
        lambda: _series(
            request_hash=_request_hash("e"),
            samples=(
                base_samples[0],
                replace(
                    base_samples[1],
                    session_order=base_samples[0].session_order,
                ),
            ),
        )
    )

    target_scope = _scope(
        semantic_version=2,
        comparison_key_hash="b" * 64,
    )
    target_samples = _samples(
        semantic_version=2,
        comparison_key_hash="b" * 64,
    )
    mixed_samples = (
        replace(
            target_samples[0],
            metric_semantic_version=1,
            comparison_key_hash="a" * 64,
        ),
        *target_samples[1:],
    )
    bridge = M4TrendBridge(
        trend_bridge_id="53000000-0000-4000-8000-000000000001",
        bridge_code="P1-AIR-001-V1-V2",
        bridge_version="1.0.0",
        from_metric_semantic_id=target_scope.metric_semantic_id,
        from_metric_semantic_version=1,
        to_metric_semantic_id=target_scope.metric_semantic_id,
        to_metric_semantic_version=2,
        conversion_kind="IDENTITY",
        conversion_spec_json="{}",
        applicability_json="{}",
        validation_dataset_snapshot_id=(
            "53000000-0000-4000-8000-000000000002"
        ),
        validation_result_hash="1" * 64,
        approved_by="governance",
        approved_at_utc=CREATED_AT,
        bridge_hash="2" * 64,
        status="APPROVED",
    )
    missing_bridge_error = _error_code(
        lambda: _series(
            request_hash=_request_hash("f"),
            scope=target_scope,
            samples=mixed_samples,
        )
    )
    draft_bridge_error = _error_code(
        lambda: _series(
            request_hash=_request_hash("f"),
            scope=target_scope,
            samples=mixed_samples,
            bridges=(replace(bridge, status="DRAFT"),),
        )
    )
    affine_bridge_error = _error_code(
        lambda: _series(
            request_hash=_request_hash("f"),
            scope=target_scope,
            samples=mixed_samples,
            bridges=(
                replace(
                    bridge,
                    conversion_kind="AFFINE",
                    conversion_spec_json='{"a":1,"b":0}',
                ),
            ),
        )
    )
    bridged_series = _series(
        request_hash=_request_hash("f"),
        scope=target_scope,
        samples=mixed_samples,
        bridges=(bridge,),
    )

    first_release = _release(request_hash=_request_hash("7"))
    repository = InMemoryM4LongitudinalReleaseRepository()
    service = M4LongitudinalPublicationService(repository)
    first_publish = service.publish(
        first_release,
        idempotency_key="m4-batch2-release-1",
        expected_version_token=0,
        published_at_utc=PUBLISHED_AT,
    )
    idempotent_publish = service.publish(
        first_release,
        idempotency_key="m4-batch2-release-1",
        expected_version_token=999,
        published_at_utc=PUBLISHED_AT,
    )
    replay = service.replay(
        first_release.release_id,
        first_release,
    )
    original = service.original_as_known(first_release.release_id)

    second_release = _release(
        request_hash=_request_hash("8"),
        release_no=2,
        parent_release_id=first_release.release_id,
    )
    second_publish = service.publish(
        second_release,
        idempotency_key="m4-batch2-release-2",
        expected_version_token=1,
        published_at_utc="2026-09-28T11:02:00Z",
    )
    retrospective = service.retrospective(
        first_release.release_id,
        second_release.release_id,
    )
    missing_historical_error = _error_code(
        lambda: service.historical_release("")
    )
    missing_retrospective_error = _error_code(
        lambda: service.retrospective(
            first_release.release_id,
            "",
        )
    )

    acceptance = {
        "trend_profile_authority_exact": (
            golden_series.trend_profile_id
            == "M4_P1_OBSERVED_TREND_V1"
            and golden_series.trend_profile_version == "1.0.0"
            and golden_series.trend_profile_hash
            == "87981c6e3c79f9587786d082d826a639"
            "3d15192f67b10c817612da8912982729"
        ),
        "golden_sample_counts_exact": (
            golden_series.sample_count_total
            == expected["sample_count_total"]
            and golden_series.sample_count_valid
            == expected["sample_count_valid"]
        ),
        "golden_current_exact": (
            golden_series.current_value == expected["current_value"]
        ),
        "golden_ewma_exact": math.isclose(
            float(golden_series.ewma_value),
            float(expected["ewma_value"]),
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
        "golden_slope_exact": math.isclose(
            float(golden_series.slope),
            float(expected["slope"]),
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
        "golden_mad_exact": math.isclose(
            float(golden_series.stability_mad),
            float(expected["stability_mad"]),
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
        "golden_status_exact": (
            golden_series.trend_status == expected["trend_status"]
            and golden_series.status == expected["status"]
            and list(golden_series.reason_codes)
            == expected["reason_codes"]
        ),
        "golden_input_hash_exact": (
            golden_series.input_hash
            == trend_golden["expected_input_hash"]
        ),
        "all_points_preserved": (
            len(golden_series.points) == 6
            and golden_series.points[1].value is None
        ),
        "insufficient_trend_fail_closed": (
            insufficient.status == "VALID"
            and insufficient.trend_status == "INSUFFICIENT_DATA"
            and insufficient.reason_codes
            == ("TREND_MIN_VALID_POINTS_NOT_MET",)
        ),
        "no_valid_series_fail_closed": (
            no_valid_series.status == "INSUFFICIENT_DATA"
            and no_valid_series.current_value is None
            and no_valid_series.ewma_value is None
            and no_valid_series.reason_codes
            == ("NO_VALID_LONGITUDINAL_SAMPLES",)
        ),
        "duplicate_session_order_fails_closed": (
            duplicate_error
            == "FAIL_CLOSED_DUPLICATE_SESSION_ORDER"
        ),
        "missing_bridge_fails_closed": (
            missing_bridge_error == "M4_TREND_BRIDGE_REQUIRED"
        ),
        "unapproved_bridge_fails_closed": (
            draft_bridge_error == "M4_TREND_BRIDGE_NOT_APPROVED"
        ),
        "undefined_affine_bridge_fails_closed": (
            affine_bridge_error
            == "M4_TREND_BRIDGE_CONVERSION_NOT_EXECUTABLE"
        ),
        "approved_identity_bridge_lineage_exact": (
            bridged_series.bridge_hashes == (bridge.bridge_hash,)
            and bridged_series.metric_semantic_version == 2
        ),
        "longitudinal_release_scope_exact": (
            first_release.scope_type == "LONGITUDINAL"
            and first_release.scope_key
            == golden_series.longitudinal_scope_key
        ),
        "release_input_membership_exact": (
            len(first_release.inputs) == 6
            and tuple(
                item.input_sample_id
                for item in first_release.inputs
            )
            == tuple(
                point.sample_id
                for point in golden_series.points
            )
        ),
        "release_manifest_exact_replay": (
            replay.manifest_equal
            and replay.input_membership_equal
            and replay.trend_logical_product_equal
            and replay.exact_logical_products_equal
        ),
        "release_idempotency_exact": (
            first_publish.reused is False
            and idempotent_publish.reused is True
            and idempotent_publish.published.release.release_id
            == first_release.release_id
        ),
        "release_cas_chain_exact": (
            first_publish.published.version_token == 1
            and second_publish.published.version_token == 2
            and second_release.parent_release_id
            == first_release.release_id
        ),
        "original_as_known_exact": (
            original.view_mode == "ORIGINAL_AS_KNOWN"
            and original.release_ids
            == (first_release.release_id,)
        ),
        "retrospective_exact_and_distinct": (
            retrospective.view_mode == "RETROSPECTIVE"
            and retrospective.base_release_id
            == first_release.release_id
            and retrospective.retrospective_release_id
            == second_release.release_id
            and retrospective.release_ids
            == (
                first_release.release_id,
                second_release.release_id,
            )
        ),
        "historical_missing_release_fails_closed": (
            missing_historical_error
            == "FAIL_CLOSED_EXACT_RELEASE_REQUIRED"
        ),
        "retrospective_missing_release_fails_closed": (
            missing_retrospective_error
            == "FAIL_CLOSED_RETROSPECTIVE_RELEASE_REQUIRED"
        ),
        "no_current_latest_replay_fallback": (
            service.current(first_release.scope_key)
            == second_publish.published
            and original.release_ids
            == (first_release.release_id,)
        ),
    }
    failed = sorted(
        name
        for name, passed in acceptance.items()
        if not passed
    )
    logical_product = {
        "golden_trend": golden_series.logical_product(),
        "first_release": first_release.logical_membership(),
        "second_release": second_release.logical_membership(),
        "original_as_known": {
            "view_mode": original.view_mode,
            "release_ids": list(original.release_ids),
        },
        "retrospective": {
            "view_mode": retrospective.view_mode,
            "release_ids": list(retrospective.release_ids),
        },
    }
    return {
        "schema": "TPAA_M4_BATCH_2_TREND_RELEASE_EVIDENCE_V1",
        "tracking_issue": TRACKING_ISSUE,
        "task_ids": [
            "M4-LONG-004",
            "M4-LONG-005",
            "M4-OBS-001",
            "M4-OBS-002",
            "M4-OBS-003",
            "M4-TST-002",
        ],
        "status": "PASS" if not failed else "FAIL",
        "implementation_complete": not failed,
        "task_complete": False,
        "completion_gate": (
            "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED"
        ),
        "source_revision": _git_revision(),
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "p1_only": True,
            "db_schema_version": "1.6.0",
            "shadow_schema_created": False,
            "historical_current_latest_fallback": False,
            "p4_p5_human_team_assessment_active": False,
            "m5_formal_product_qualification_claimed": False,
            "api_gui_implemented": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        payload = verify()
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M4_BATCH_2_TREND_RELEASE_EVIDENCE_V1",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    rendered = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
    print(rendered, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(
            rendered,
            encoding="utf-8",
            newline="\n",
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
