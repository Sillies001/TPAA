from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

from tpaa_longitudinal import (
    InMemoryM4LongitudinalReleaseRepository,
    M4LongitudinalError,
    M4LongitudinalPublicationService,
    M4LongitudinalSample,
    M4LongitudinalScope,
    M4TrendBridge,
    allocate_m4_longitudinal_release_id,
    build_m4_longitudinal_release,
    build_performance_trend_series,
    load_m4_trend_authority,
)

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
AUTHORITY_PATH = (
    BASELINE / "canonical" / "M4_LONGITUDINAL_DEBRIEF_AUTHORITY.json"
)
LONGITUDINAL_SCOPE_ID = "40000000-0000-4000-8000-000000000001"
METRIC_DEFINITION_ID = "40000000-0000-4000-8000-000000000002"
COMPUTE_JOB_ID = "40000000-0000-4000-8000-000000000003"
CREATED_AT = "2026-09-28T10:00:00Z"
PUBLISHED_AT = "2026-09-28T10:01:00Z"


def _authority_payload() -> dict[str, object]:
    payload = json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _scope(
    *,
    semantic_version: int = 1,
    comparison_key_hash: str | None = None,
) -> M4LongitudinalScope:
    golden = _authority_payload()["golden_vectors"]
    assert isinstance(golden, dict)
    scope_golden = golden["longitudinal_scope"]
    assert isinstance(scope_golden, dict)
    descriptor = scope_golden["descriptor"]
    assert isinstance(descriptor, dict)
    key = str(scope_golden["expected_longitudinal_scope_key"])
    comparison = (
        comparison_key_hash
        if comparison_key_hash is not None
        else str(descriptor["comparison_key_hash"])
    )
    material = dict(descriptor)
    material["metric_semantic_version"] = semantic_version
    material["comparison_key_hash"] = comparison
    descriptor_json = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return M4LongitudinalScope(
        longitudinal_scope_key=key,
        subject_type=str(descriptor["subject_type"]),
        subject_id=str(descriptor["subject_id"]),
        metric_semantic_id=str(descriptor["metric_semantic_id"]),
        metric_semantic_version=semantic_version,
        comparison_key_hash=comparison,
        session_order_scope_id=str(descriptor["session_order_scope_id"]),
        trend_profile_version=str(descriptor["trend_profile_version"]),
        descriptor_json=descriptor_json,
        descriptor_hash=key,
    )


def _samples(
    *,
    semantic_version: int = 1,
    comparison_key_hash: str | None = None,
) -> tuple[M4LongitudinalSample, ...]:
    payload = _authority_payload()
    golden = payload["golden_vectors"]
    assert isinstance(golden, dict)
    trend = golden["trend"]
    assert isinstance(trend, dict)
    points = trend["points"]
    assert isinstance(points, list)
    scope = _scope(
        semantic_version=semantic_version,
        comparison_key_hash=comparison_key_hash,
    )
    configuration_key = (
        "AIRCRAFT_CONFIG_SHA256:"
        + "a" * 64
    )
    result: list[M4LongitudinalSample] = []
    for index, point in enumerate(points, start=1):
        assert isinstance(point, dict)
        status = str(point["status"])
        value = point["value"]
        result.append(
            M4LongitudinalSample(
                sample_id=str(point["sample_id"]),
                release_id=(
                    f"41000000-0000-4000-8000-{index:012d}"
                ),
                release_scope_type="SESSION",
                subject_type=scope.subject_type,
                subject_id=scope.subject_id,
                aircraft_id=scope.subject_id,
                mission_system_instance_id=None,
                session_id=(
                    f"42000000-0000-4000-8000-{index:012d}"
                ),
                session_order_scope_id=scope.session_order_scope_id,
                session_order=int(point["session_order"]),
                occurred_at_utc=None,
                configuration_key=configuration_key,
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
                logical_content_hash=str(point["logical_content_hash"]),
            )
        )
    return tuple(result)


def _request_hash(suffix: str) -> str:
    return (suffix * 64)[:64]


def _series(
    *,
    request_hash: str,
    scope: M4LongitudinalScope | None = None,
    samples: tuple[M4LongitudinalSample, ...] | None = None,
    bridges: tuple[M4TrendBridge, ...] = (),
):
    trend_authority = load_m4_trend_authority(BASELINE)
    actual_scope = scope or _scope()
    actual_samples = samples or _samples()
    release_id = allocate_m4_longitudinal_release_id(
        longitudinal_scope_key=actual_scope.longitudinal_scope_key,
        request_hash=request_hash,
    )
    return build_performance_trend_series(
        authority=trend_authority,
        release_id=release_id,
        longitudinal_scope_id=LONGITUDINAL_SCOPE_ID,
        metric_definition_id=METRIC_DEFINITION_ID,
        metric_code="P1-AIR-001",
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
):
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


def test_m4_trend_matches_c3_golden_exactly() -> None:
    payload = _authority_payload()
    golden = payload["golden_vectors"]
    assert isinstance(golden, dict)
    trend = golden["trend"]
    assert isinstance(trend, dict)
    expected = trend["expected"]
    assert isinstance(expected, dict)

    series = _series(request_hash=_request_hash("a"))
    assert series.sample_count_total == expected["sample_count_total"]
    assert series.sample_count_valid == expected["sample_count_valid"]
    assert series.current_value == expected["current_value"]
    assert math.isclose(
        float(series.ewma_value),
        float(expected["ewma_value"]),
        rel_tol=0.0,
        abs_tol=1e-12,
    )
    assert math.isclose(
        float(series.slope),
        float(expected["slope"]),
        rel_tol=0.0,
        abs_tol=1e-12,
    )
    assert series.slope_unit == expected["slope_unit"]
    assert math.isclose(
        float(series.stability_mad),
        float(expected["stability_mad"]),
        rel_tol=0.0,
        abs_tol=1e-12,
    )
    assert series.trend_status == expected["trend_status"]
    assert series.status == expected["status"]
    assert list(series.reason_codes) == expected["reason_codes"]
    assert series.input_hash == trend["expected_input_hash"]
    assert [point.point_order for point in series.points] == list(
        range(1, 7)
    )
    assert series.points[1].value is None


def test_m4_trend_insufficient_data_and_duplicate_order_fail_closed() -> None:
    scope = _scope()
    samples = _samples()
    series = _series(
        request_hash=_request_hash("b"),
        scope=scope,
        samples=samples[:2],
    )
    assert series.status == "VALID"
    assert series.trend_status == "INSUFFICIENT_DATA"
    assert series.reason_codes == ("TREND_MIN_VALID_POINTS_NOT_MET",)
    assert series.slope is None
    assert series.stability_mad is None

    no_valid = tuple(
        replace(
            item,
            value_numeric=None,
            status="INSUFFICIENT_DATA",
        )
        for item in samples[:2]
    )
    no_valid_series = _series(
        request_hash=_request_hash("d"),
        scope=scope,
        samples=no_valid,
    )
    assert no_valid_series.status == "INSUFFICIENT_DATA"
    assert no_valid_series.current_value is None
    assert no_valid_series.ewma_value is None
    assert no_valid_series.reason_codes == (
        "NO_VALID_LONGITUDINAL_SAMPLES",
    )

    duplicate = (
        samples[0],
        replace(samples[1], session_order=samples[0].session_order),
    )
    with pytest.raises(M4LongitudinalError) as excinfo:
        _series(
            request_hash=_request_hash("e"),
            scope=scope,
            samples=duplicate,
        )
    assert excinfo.value.code == "FAIL_CLOSED_DUPLICATE_SESSION_ORDER"


def test_m4_trend_bridge_requires_approved_identity_authority() -> None:
    target_hash = "b" * 64
    source_hash = "a" * 64
    scope = _scope(
        semantic_version=2,
        comparison_key_hash=target_hash,
    )
    base = _samples(
        semantic_version=2,
        comparison_key_hash=target_hash,
    )
    bridged_sample = replace(
        base[0],
        metric_semantic_version=1,
        comparison_key_hash=source_hash,
    )
    samples = (bridged_sample, *base[1:])
    approved = M4TrendBridge(
        trend_bridge_id="43000000-0000-4000-8000-000000000001",
        bridge_code="P1-AIR-001-V1-V2",
        bridge_version="1.0.0",
        from_metric_semantic_id=scope.metric_semantic_id,
        from_metric_semantic_version=1,
        to_metric_semantic_id=scope.metric_semantic_id,
        to_metric_semantic_version=2,
        conversion_kind="IDENTITY",
        conversion_spec_json="{}",
        applicability_json="{}",
        validation_dataset_snapshot_id=(
            "43000000-0000-4000-8000-000000000002"
        ),
        validation_result_hash="1" * 64,
        approved_by="governance",
        approved_at_utc=CREATED_AT,
        bridge_hash="2" * 64,
        status="APPROVED",
    )

    with pytest.raises(M4LongitudinalError) as excinfo:
        _series(
            request_hash=_request_hash("f"),
            scope=scope,
            samples=samples,
        )
    assert excinfo.value.code == "M4_TREND_BRIDGE_REQUIRED"

    with pytest.raises(M4LongitudinalError) as excinfo:
        _series(
            request_hash=_request_hash("f"),
            scope=scope,
            samples=samples,
            bridges=(replace(approved, status="DRAFT"),),
        )
    assert excinfo.value.code == "M4_TREND_BRIDGE_NOT_APPROVED"

    series = _series(
        request_hash=_request_hash("f"),
        scope=scope,
        samples=samples,
        bridges=(approved,),
    )
    assert series.bridge_hashes == (approved.bridge_hash,)
    assert series.metric_semantic_version == 2


def test_m4_longitudinal_release_publication_and_exact_replay() -> None:
    first = _release(request_hash=_request_hash("7"))
    repository = InMemoryM4LongitudinalReleaseRepository()
    service = M4LongitudinalPublicationService(repository)

    published = service.publish(
        first,
        idempotency_key="m4-release-1",
        expected_version_token=0,
        published_at_utc=PUBLISHED_AT,
    )
    assert published.reused is False
    assert published.published.status == "PUBLISHED"
    assert published.published.version_token == 1
    assert len(first.inputs) == 6

    reused = service.publish(
        first,
        idempotency_key="m4-release-1",
        expected_version_token=999,
        published_at_utc=PUBLISHED_AT,
    )
    assert reused.reused is True
    assert reused.published.release.release_id == first.release_id

    historical = service.historical_release(first.release_id)
    assert historical.release.manifest_hash == first.manifest_hash
    assert service.current(first.scope_key) == historical
    replay = service.replay(first.release_id, first)
    assert replay.exact_logical_products_equal is True
    original = service.original_as_known(first.release_id)
    assert original.view_mode == "ORIGINAL_AS_KNOWN"
    assert original.release_ids == (first.release_id,)

    second = _release(
        request_hash=_request_hash("8"),
        release_no=2,
        parent_release_id=first.release_id,
    )
    service.publish(
        second,
        idempotency_key="m4-release-2",
        expected_version_token=1,
        published_at_utc="2026-09-28T10:02:00Z",
    )
    retrospective = service.retrospective(
        first.release_id,
        second.release_id,
    )
    assert retrospective.view_mode == "RETROSPECTIVE"
    assert retrospective.base_release_id == first.release_id
    assert retrospective.retrospective_release_id == second.release_id
    assert retrospective.release_ids == (
        first.release_id,
        second.release_id,
    )

    with pytest.raises(M4LongitudinalError) as excinfo:
        service.historical_release("")
    assert excinfo.value.code == "FAIL_CLOSED_EXACT_RELEASE_REQUIRED"

    with pytest.raises(M4LongitudinalError) as excinfo:
        service.retrospective(first.release_id, "")
    assert excinfo.value.code == (
        "FAIL_CLOSED_RETROSPECTIVE_RELEASE_REQUIRED"
    )
