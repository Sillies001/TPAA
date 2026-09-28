from __future__ import annotations

from fastapi.testclient import TestClient

from tpaa_api import create_m4_app
from tpaa_application import (
    ApplicationService,
    InMemoryM4DebriefRepository,
    M4AnnotationCommand,
    M4DebriefQuery,
    M4DebriefTimelineItem,
    M4TrendQuery,
    M4WorkspaceService,
)
from tpaa_longitudinal import (
    InMemoryM4LongitudinalReleaseRepository,
    M4LongitudinalPublicationService,
    M4LongitudinalReleaseInput,
    M4LongitudinalReleaseSnapshot,
    M4PerformanceTrendPoint,
    M4PerformanceTrendSeries,
    M4PublishedLongitudinalRelease,
)

RELEASE_ID = "60000000-0000-4000-8000-000000000001"
RETRO_RELEASE_ID = "60000000-0000-4000-8000-000000000002"
SCOPE_ID = "60000000-0000-4000-8000-000000000003"
SESSION_ID = "60000000-0000-4000-8000-000000000004"
SOURCE_RELEASE_ID = "60000000-0000-4000-8000-000000000005"
SAMPLE_ID = "60000000-0000-4000-8000-000000000006"
TREND_ID = "60000000-0000-4000-8000-000000000007"
AUTHOR_ID = "60000000-0000-4000-8000-000000000008"
EVIDENCE_ID = "60000000-0000-4000-8000-000000000009"
SCOPE_KEY = "a" * 64
COMPARISON_HASH = "b" * 64
PROFILE_HASH = (
    "87981c6e3c79f9587786d082d826a639"
    "3d15192f67b10c817612da8912982729"
)


class _StorageStatus:
    def execute(self):
        raise AssertionError("storage baseline is not used by M4 routes")


def _series(release_id: str) -> M4PerformanceTrendSeries:
    point = M4PerformanceTrendPoint(
        trend_id=TREND_ID,
        point_order=1,
        sample_id=SAMPLE_ID,
        source_release_id=SOURCE_RELEASE_ID,
        session_id=SESSION_ID,
        subject_type="AIRCRAFT",
        subject_id="60000000-0000-4000-8000-000000000010",
        session_order=10,
        occurred_at_utc="2026-09-28T01:00:00Z",
        value=100.0,
        sample_status="VALID",
        configuration_key="AIRCRAFT_CONFIG_SHA256:" + "c" * 64,
        lifecycle_marker_refs=(),
    )
    return M4PerformanceTrendSeries(
        trend_id=TREND_ID,
        release_id=release_id,
        longitudinal_scope_id=SCOPE_ID,
        longitudinal_scope_key=SCOPE_KEY,
        subject_type="AIRCRAFT",
        subject_id="60000000-0000-4000-8000-000000000010",
        metric_definition_id="60000000-0000-4000-8000-000000000011",
        metric_code="P1-AIR-001",
        metric_semantic_id="P1-AIR-001",
        metric_semantic_version=1,
        comparison_key_hash=COMPARISON_HASH,
        trend_semantics="OBSERVED_PERFORMANCE",
        x_axis_semantics="SESSION_ORDER",
        session_order_scope_id="60000000-0000-4000-8000-000000000012",
        as_of_session_order=10,
        as_of_occurred_at_utc="2026-09-28T01:00:00Z",
        sample_count_total=1,
        sample_count_valid=1,
        current_value=100.0,
        ewma_value=100.0,
        slope=None,
        slope_unit=None,
        stability_mad=None,
        trend_status="INSUFFICIENT_DATA",
        status="VALID",
        reason_codes=("TREND_MIN_VALID_POINTS_NOT_MET",),
        trend_profile_id="M4_P1_OBSERVED_TREND_V1",
        trend_profile_version="1.0.0",
        trend_profile_hash=PROFILE_HASH,
        input_hash="d" * 64,
        bridge_hashes=(),
        input_membership=((SOURCE_RELEASE_ID, SAMPLE_ID),),
        created_at_utc="2026-09-28T01:01:00Z",
        supersedes_trend_id=None,
        points=(point,),
    )


def _snapshot(
    release_id: str,
    *,
    release_no: int,
    parent_release_id: str | None,
) -> M4LongitudinalReleaseSnapshot:
    series = _series(release_id)
    return M4LongitudinalReleaseSnapshot(
        release_id=release_id,
        request_hash="e" * 64,
        scope_type="LONGITUDINAL",
        scope_key=SCOPE_KEY,
        longitudinal_scope_id=SCOPE_ID,
        release_no=release_no,
        compute_job_id="60000000-0000-4000-8000-000000000013",
        catalog_version="1.14.0",
        catalog_hash="f" * 64,
        context_binding_hash="1" * 64,
        status="VALIDATED",
        parent_release_id=parent_release_id,
        manifest_hash=("2" if release_no == 1 else "3") * 64,
        created_at_utc="2026-09-28T01:02:00Z",
        inputs=(
            M4LongitudinalReleaseInput(
                input_session_release_id=SOURCE_RELEASE_ID,
                input_sample_id=SAMPLE_ID,
            ),
        ),
        trend_series=series,
    )


def _configured() -> tuple[ApplicationService, InMemoryM4DebriefRepository]:
    longitudinal_repo = InMemoryM4LongitudinalReleaseRepository()
    first = M4PublishedLongitudinalRelease(
        release=_snapshot(RELEASE_ID, release_no=1, parent_release_id=None),
        version_token=1,
        published_at_utc="2026-09-28T01:03:00Z",
    )
    second = M4PublishedLongitudinalRelease(
        release=_snapshot(
            RETRO_RELEASE_ID,
            release_no=2,
            parent_release_id=RELEASE_ID,
        ),
        version_token=2,
        published_at_utc="2026-09-28T01:04:00Z",
    )
    longitudinal_repo._releases[RELEASE_ID] = first
    longitudinal_repo._releases[RETRO_RELEASE_ID] = second
    longitudinal_repo._current[SCOPE_KEY] = RETRO_RELEASE_ID
    longitudinal_repo._tokens[SCOPE_KEY] = 2
    longitudinal = M4LongitudinalPublicationService(longitudinal_repo)
    debrief = InMemoryM4DebriefRepository(
        clock=lambda: "2026-09-28T01:05:00Z"
    )
    debrief.register_timeline(
        RELEASE_ID,
        (
            M4DebriefTimelineItem(
                item_id="metric:P1-AIR-001",
                item_type="METRIC",
                session_id=SESSION_ID,
                episode_id=None,
                stage_id=None,
                start_session_time_us=100,
                end_session_time_us=200,
                evidence_set_id=EVIDENCE_ID,
                source_release_id=SOURCE_RELEASE_ID,
            ),
        ),
    )
    debrief.register_timeline(
        RETRO_RELEASE_ID,
        (
            M4DebriefTimelineItem(
                item_id="evidence:retrospective",
                item_type="EVIDENCE",
                session_id=SESSION_ID,
                episode_id=None,
                stage_id=None,
                start_session_time_us=100,
                end_session_time_us=200,
                evidence_set_id=EVIDENCE_ID,
                source_release_id=RETRO_RELEASE_ID,
            ),
        ),
    )
    workspace = M4WorkspaceService(
        longitudinal=longitudinal,
        debrief=debrief,
    )
    application = ApplicationService(
        get_storage_baseline_status=_StorageStatus(),
        m4_workspace=workspace,
    )
    return application, debrief


def test_m4_application_trend_is_exact_release_projection_only() -> None:
    application, _debrief = _configured()
    projection = application.m4_trend(
        M4TrendQuery(
            release_id=RELEASE_ID,
            metric_code="P1-AIR-001",
        )
    )
    assert projection["query"]["release_id"] == RELEASE_ID
    assert projection["release"]["release_id"] == RELEASE_ID
    assert projection["scope"]["longitudinal_scope_id"] == SCOPE_ID
    assert projection["series"]["metric_code"] == "P1-AIR-001"
    assert projection["series"]["current_value"] == 100.0
    assert projection["points"] == [
        {
            "trend_id": TREND_ID,
            "point_order": 1,
            "sample_id": SAMPLE_ID,
            "release_id": SOURCE_RELEASE_ID,
            "session_id": SESSION_ID,
            "subject_type": "AIRCRAFT",
            "subject_id": "60000000-0000-4000-8000-000000000010",
            "session_order": 10,
            "occurred_at_utc": "2026-09-28T01:00:00Z",
            "value": 100.0,
            "sample_status": "VALID",
            "configuration_key": "AIRCRAFT_CONFIG_SHA256:" + "c" * 64,
            "lifecycle_marker_refs": [],
        }
    ]


def test_m4_debrief_annotation_revisions_do_not_mutate_release() -> None:
    application, _debrief = _configured()
    before = application.m4_trend(M4TrendQuery(release_id=RELEASE_ID))
    created = application.m4_annotation(
        M4AnnotationCommand(
            request_id="request-create",
            operation="CREATE",
            base_release_id=RELEASE_ID,
            target_annotation_id=None,
            session_id=SESSION_ID,
            episode_id=None,
            stage_id=None,
            author_id=AUTHOR_ID,
            annotation_type="EVIDENCE_NOTE",
            start_session_time_us=100,
            end_session_time_us=200,
            body_text="Evidence note",
            visibility="PROJECT",
            reason="Debrief observation",
            evidence_set_id=EVIDENCE_ID,
        )
    )
    superseded = application.m4_annotation(
        M4AnnotationCommand(
            request_id="request-supersede",
            operation="SUPERSEDE",
            base_release_id=RELEASE_ID,
            target_annotation_id=str(created["annotation_id"]),
            session_id=SESSION_ID,
            episode_id=None,
            stage_id=None,
            author_id=AUTHOR_ID,
            annotation_type="EVIDENCE_NOTE",
            start_session_time_us=100,
            end_session_time_us=200,
            body_text="Corrected evidence note",
            visibility="PROJECT",
            reason="Correction",
            evidence_set_id=EVIDENCE_ID,
        )
    )
    bundle = application.m4_debrief(
        M4DebriefQuery(
            base_release_id=RELEASE_ID,
            view_mode="ORIGINAL_AS_KNOWN",
            retrospective_release_id=None,
            annotation_view="EXACT_REVISION_SET",
            annotation_as_of_utc=None,
            annotation_ids=(
                str(created["annotation_id"]),
                str(superseded["annotation_id"]),
            ),
        )
    )
    assert bundle["base_release"]["release_id"] == RELEASE_ID
    assert len(bundle["timeline"]) == 1
    assert bundle["timeline"][0]["evidence_set_id"] == EVIDENCE_ID
    assert [item["revision_no"] for item in bundle["annotations"]] == [1, 2]
    assert bundle["annotations"][0]["status"] == "SUPERSEDED"
    assert bundle["annotations"][1]["status"] == "ACTIVE"
    after = application.m4_trend(M4TrendQuery(release_id=RELEASE_ID))
    assert after["release"]["manifest_hash"] == before["release"]["manifest_hash"]
    assert after["series"] == before["series"]
    assert after["points"] == before["points"]


def test_m4_api_exposes_exact_release_and_retrospective_distinction() -> None:
    application, _debrief = _configured()
    client = TestClient(create_m4_app(application))

    trend = client.get(
        f"/m4/longitudinal/releases/{RELEASE_ID}/trend",
        params={"metric_code": "P1-AIR-001"},
    )
    assert trend.status_code == 200
    assert trend.json()["release"]["release_id"] == RELEASE_ID

    debrief = client.get(
        f"/m4/debrief/releases/{RELEASE_ID}",
        params={
            "view_mode": "RETROSPECTIVE",
            "retrospective_release_id": RETRO_RELEASE_ID,
            "annotation_view": "NONE",
        },
    )
    assert debrief.status_code == 200
    payload = debrief.json()
    assert payload["query"]["base_release_id"] == RELEASE_ID
    assert payload["query"]["retrospective_release_id"] == RETRO_RELEASE_ID
    assert [item["source_release_id"] for item in payload["timeline"]] == [
        SOURCE_RELEASE_ID,
        RETRO_RELEASE_ID,
    ]

    missing = client.get(
        "/m4/longitudinal/releases//trend"
    )
    assert missing.status_code in {404, 405}
