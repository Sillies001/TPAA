"""G5 Weapon Event Application read-model tests (DTO shape, fail-closed, exact identity)."""

from __future__ import annotations

import pytest

from tests.fixtures.weapon_events import (
    InMemoryWeaponEventStore,
    StaticLaunchSource,
    launch_fact,
    shooter_anchors,
)
from tpaa_application.weapon_event import WeaponEventDetector
from tpaa_application.weapon_event_application import (
    WeaponEventApplicationError,
    WeaponEventApplicationService,
)

BATCH = "b-batch-0001"


def _service(*weapon_types: str) -> WeaponEventApplicationService:
    store = InMemoryWeaponEventStore()
    facts = [
        launch_fact(f"L{i+1}", weapon_type_raw=wtype, t1_us=12_170_000 + i * 5_000)
        for i, wtype in enumerate(weapon_types)
    ]
    events = WeaponEventDetector(StaticLaunchSource(facts), store).detect_and_publish(BATCH)
    service = WeaponEventApplicationService(store)
    for event in events:
        service.register(
            event,
            shooter_anchors(t1_session_time_us=event.t1_session_time_us),
            geometry_available=True,
            series_available=True,
            target_projection_available=True,
        )
    return service


def test_detail_dto_shape_and_decimal_session_time() -> None:
    service = _service("IR_MISSILE")
    weapon_event_id = service.list_ids(BATCH)[0]
    detail = service.detail(weapon_event_id)
    assert detail["schema"] == "TPAA_G5_WEAPON_EVENT_DETAIL_V1"
    assert detail["category"] == "WVR"
    assert isinstance(detail["t1_session_time_us"], str)
    assert detail["provenance"]["latest_fallback"] is False
    assert detail["provenance"]["exact_identity"] is True


def test_unknown_weapon_event_fails_closed_404() -> None:
    service = _service("IR_MISSILE")
    with pytest.raises(WeaponEventApplicationError) as excinfo:
        service.detail("we-does-not-exist")
    assert excinfo.value.code == "WEAPON_EVENT_NOT_FOUND"
    assert excinfo.value.http_status == 404
    with pytest.raises(WeaponEventApplicationError):
        service.window("we-does-not-exist", "shooter")


def test_window_dto_shooter_and_target() -> None:
    service = _service("IR_MISSILE")
    weapon_event_id = service.list_ids(BATCH)[0]
    window = service.window(weapon_event_id, "shooter")
    assert window["schema"] == "TPAA_G5_WEAPON_EVENT_WINDOW_V1"
    assert window["perspective"] == "shooter"
    assert isinstance(window["start_session_time_us"], str)
    assert window["end_session_time_us"] is None or isinstance(window["end_session_time_us"], str)
    assert window["terminal_state"] in {"TERMINAL_KNOWN", "TERMINAL_UNKNOWN"}
    with pytest.raises(WeaponEventApplicationError) as excinfo:
        service.window(weapon_event_id, "diagonal")
    assert excinfo.value.code == "PERSPECTIVE_INVALID"


def test_perspective_allowed_for_wvr_fail_closed_for_strike_target() -> None:
    service = _service("IR_MISSILE", "STRIKE_ROCKET")
    ids = service.list_ids(BATCH)
    by_category = {service.detail(event_id)["category"]: event_id for event_id in ids}
    wvr = service.perspective(by_category["WVR"], "target")
    assert wvr["allowed"] is True
    assert wvr["geometry_available"] is True
    strike = service.perspective(by_category["STRIKE"], "target")
    assert strike["allowed"] is False
    assert strike["denial_reason"] == "NOT_APPLICABLE_STRIKE_TARGET"


def test_capability_and_adapter_states_are_distinct() -> None:
    disabled = WeaponEventApplicationService(capability_enabled=False)
    assert disabled.capability_state() == "CAPABILITY_DISABLED"
    with pytest.raises(WeaponEventApplicationError) as excinfo:
        disabled.detail("we-any")
    assert excinfo.value.code == "CAPABILITY_DISABLED"
    assert excinfo.value.http_status == 403

    degraded = WeaponEventApplicationService(adapter_ready=False)
    assert degraded.capability_state() == "ADAPTER_UNAVAILABLE"
    with pytest.raises(WeaponEventApplicationError) as excinfo:
        degraded.window("we-any", "shooter")
    assert excinfo.value.code == "ADAPTER_UNAVAILABLE"
    assert excinfo.value.http_status == 503


def test_ready_backend_unknown_we_is_exact_404_not_empty() -> None:
    ready = WeaponEventApplicationService(InMemoryWeaponEventStore())
    assert ready.capability_state() == "READY"
    with pytest.raises(WeaponEventApplicationError) as excinfo:
        ready.perspective("we-absent", "shooter")
    assert excinfo.value.code == "WEAPON_EVENT_NOT_FOUND"
    assert excinfo.value.http_status == 404


def test_four_state_batch_read_state_distinguishes_empty() -> None:
    ready_empty = WeaponEventApplicationService(InMemoryWeaponEventStore())
    assert ready_empty.batch_read_state(BATCH) == "EMPTY"
    ready_with_data = _service("IR_MISSILE")
    assert ready_with_data.batch_read_state(BATCH) == "READY"
    assert ready_with_data.batch_read_state("other-batch") == "EMPTY"
    # Capability-disabled still wins over data-level EMPTY.
    assert WeaponEventApplicationService(capability_enabled=False).batch_read_state(BATCH) == "CAPABILITY_DISABLED"
    assert WeaponEventApplicationService(adapter_ready=False).batch_read_state(BATCH) == "ADAPTER_UNAVAILABLE"
