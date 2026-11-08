"""G9 V03 replay-context exit-gate tests."""

from __future__ import annotations

import pytest

from tests.fixtures.weapon_events import (
    InMemoryWeaponEventStore,
    StaticLaunchSource,
    launch_fact,
    shooter_anchors,
)
from tpaa_application import ApplicationService, ReplayContextApplicationService, ReplayContextError
from tpaa_application.weapon_event import WeaponEventDetector
from tpaa_application.weapon_event_application import (
    WeaponEventApplicationService,
)


class _UnusedStorage:
    def execute(self) -> object:
        raise AssertionError("storage is not used by the G9 read model")


RELEASE_ID = "22222222-2222-4222-8222-222222222222"
CONTEXT_ID = "33333333-3333-4333-8333-333333333333"


class _ExactPresentationSource:
    def release_presentation(self, release_id: str) -> dict[str, object]:
        return {
            "schema": "TPAA_RELEASE_PRESENTATION_BINDING_V1",
            "release_id": release_id,
            "available": True,
            "reason_code": "READY",
            "current_latest_fallback_used": False,
            "presentation": {
                "schema": "TPAA_TRAJECTORY_PRESENTATION_V1",
                "release_id": release_id,
                "time_semantics": "SESSION_TIME",
                "business_recompute": False,
                "persistence_access": False,
                "mutable_alias_resolution": False,
                "samples": [
                    {
                        "session_time_us": 11_000_000,
                        "latitude_deg": 31.1,
                        "longitude_deg": 121.1,
                        "altitude_m": 1000.0,
                        "source_release_id": release_id,
                        "evidence_ref": "e-before",
                    },
                    {
                        "session_time_us": 15_000_000,
                        "latitude_deg": 31.2,
                        "longitude_deg": 121.2,
                        "altitude_m": 1200.0,
                        "source_release_id": release_id,
                        "evidence_ref": "e-in-window",
                    },
                    {
                        "session_time_us": 23_000_000,
                        "latitude_deg": 31.3,
                        "longitude_deg": 121.3,
                        "altitude_m": 1300.0,
                        "source_release_id": release_id,
                        "evidence_ref": "e-after",
                    },
                ],
                "media": [
                    {
                        "media_id": "media-1",
                        "media_type": "video/mp4",
                        "uri": "file:///must-not-cross-application-boundary.mp4",
                        "source_release_id": release_id,
                        "evidence_ref": "media-evidence-1",
                    }
                ],
            },
        }


def _service() -> tuple[ReplayContextApplicationService, str, str]:
    weapon_service, weapon_event_id, batch_id = _weapon_service()
    return ReplayContextApplicationService(weapon_service), weapon_event_id, batch_id


def _weapon_service() -> tuple[WeaponEventApplicationService, str, str]:
    batch_id = "11111111-1111-4111-8111-111111111111"
    store = InMemoryWeaponEventStore()
    fact = launch_fact("L1", batch_id=batch_id, release_id=RELEASE_ID)
    event = WeaponEventDetector(StaticLaunchSource((fact,)), store).detect_and_publish(batch_id)[0]
    service = WeaponEventApplicationService(store)
    service.register(event, shooter_anchors(), context_id=CONTEXT_ID)
    return service, event.weapon_event_id, batch_id


def test_exact_replay_context_exposes_window_anchors_and_honest_media() -> None:
    service, weapon_event_id, batch_id = _service()
    payload = service.context(
        weapon_event_id,
        request_id="req-1",
        release_id=RELEASE_ID,
        context_id=CONTEXT_ID,
        perspective="shooter",
    )
    assert payload["schema"] == "TPAA_G9_REPLAY_CONTEXT_V1"
    assert payload["request_id"] == "req-1"
    assert payload["weapon_event_id"] == weapon_event_id
    assert payload["batch_id"] == batch_id
    assert payload["release_id"] == RELEASE_ID
    assert payload["context_id"] == CONTEXT_ID
    assert payload["provenance"]["exact_we_scope"] is True
    assert payload["provenance"]["latest_fallback"] is False
    assert payload["ranges"]["media_ranges"] == []
    assert payload["ranges"]["reason_code"] == "MEDIA_PIPELINE_NOT_ADMITTED"


def test_unknown_weapon_event_fails_closed_404() -> None:
    service, _weapon_event_id, _batch_id = _service()
    with pytest.raises(ReplayContextError) as excinfo:
        service.context(
            "missing-we",
            request_id="req-2",
            release_id=RELEASE_ID,
            context_id=CONTEXT_ID,
            perspective="shooter",
        )
    assert excinfo.value.code == "WEAPON_EVENT_NOT_FOUND"
    assert excinfo.value.http_status == 404


def test_exact_release_presentation_is_windowed_and_raw_media_uri_is_not_exposed() -> None:
    weapon_service, weapon_event_id, _batch_id = _weapon_service()
    service = ReplayContextApplicationService(
        weapon_service,
        presentation_source=_ExactPresentationSource(),
    )
    payload = service.context(
        weapon_event_id,
        request_id="req-presentation",
        release_id=RELEASE_ID,
        context_id=CONTEXT_ID,
        perspective="shooter",
    )
    trajectory = payload["ranges"]["trajectory"]
    assert trajectory["state"] == "READY"
    assert [item["session_time_us"] for item in trajectory["samples"]] == ["15000000"]
    media = payload["media_ranges"]["items"]
    assert media == [
        {
            "media_id": "media-1",
            "media_type": "video/mp4",
            "evidence_ref": "media-evidence-1",
            "ticket_required": True,
        }
    ]
    assert "uri" not in media[0]
    assert payload["provenance"]["latest_fallback"] is False


def test_capability_disabled_fails_closed_403() -> None:
    weapon_service, _weapon_event_id, _batch_id = _weapon_service()
    disabled = ReplayContextApplicationService(weapon_service, capability_enabled=False)
    with pytest.raises(ReplayContextError) as excinfo:
        disabled.context(
            "any",
            request_id="req-3",
            release_id=RELEASE_ID,
            context_id=CONTEXT_ID,
            perspective="shooter",
        )
    assert excinfo.value.code == "CAPABILITY_DISABLED"
    assert excinfo.value.http_status == 403


def test_replay_scope_mismatch_fails_closed() -> None:
    service, weapon_event_id, _batch_id = _service()
    with pytest.raises(ReplayContextError) as excinfo:
        service.context(
            weapon_event_id,
            request_id="req-mismatch",
            release_id="44444444-4444-4444-8444-444444444444",
            context_id=CONTEXT_ID,
            perspective="shooter",
        )
    assert excinfo.value.code == "REPLAY_SCOPE_MISMATCH"
    assert excinfo.value.http_status == 422


def test_application_accessor_guards_fail_closed() -> None:
    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),  # type: ignore[arg-type]
    )
    assert application.has_replay_context() is False
    with pytest.raises(RuntimeError, match="G9_REPLAY_CONTEXT_SERVICE_UNAVAILABLE"):
        application.replay_context()
