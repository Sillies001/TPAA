"""G5 Weapon Event detail/window/perspective HTTP adapter."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from tpaa_application import ApplicationService, WeaponEventApplicationError


def _error(exc: WeaponEventApplicationError) -> JSONResponse:
    state = (
        exc.code
        if exc.code in {"CAPABILITY_DISABLED", "ADAPTER_UNAVAILABLE"}
        else "ERROR"
    )
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "schema": "TPAA_G5_WEAPON_EVENT_ERROR_V1",
            "state": state,
            "code": exc.code,
            "detail": exc.detail,
            "provenance": {
                "authority_id": "GUI_WEAPON_EVENT_AUTHORITY",
                "core_baseline": "CB-1.14.0",
                "latest_fallback": False,
            },
        },
        headers={"Cache-Control": "private, no-store"},
    )


def register_gui_weapon_event_routes(app: FastAPI, application: ApplicationService) -> None:
    """Register G5 routes only when the trusted runtime activated the capability."""

    # Historical route-graph contract probes intentionally pass an opaque sentinel;
    # only a real Application facade with the trusted G5 service may expose routes.
    if not isinstance(application, ApplicationService) or not application.has_weapon_event():
        return

    @app.get(
        "/api/v1/gui/weapon-events/{weapon_event_id}",
        operation_id="getGuiWeaponEvent",
    )
    def weapon_event_detail(weapon_event_id: str) -> JSONResponse:
        try:
            payload = application.weapon_event().detail(weapon_event_id)
        except WeaponEventApplicationError as exc:
            return _error(exc)
        return JSONResponse(payload, headers={"Cache-Control": "private, no-store"})

    @app.get(
        "/api/v1/gui/weapon-events/{weapon_event_id}/windows/{perspective}",
        operation_id="getGuiWeaponEventWindow",
    )
    def weapon_event_window(weapon_event_id: str, perspective: str) -> JSONResponse:
        try:
            payload = application.weapon_event().window(weapon_event_id, perspective)
        except WeaponEventApplicationError as exc:
            return _error(exc)
        return JSONResponse(payload, headers={"Cache-Control": "private, no-store"})

    @app.get(
        "/api/v1/gui/weapon-events/{weapon_event_id}/perspectives/{perspective}",
        operation_id="getGuiWeaponEventPerspective",
    )
    def weapon_event_perspective(weapon_event_id: str, perspective: str) -> JSONResponse:
        try:
            payload = application.weapon_event().perspective(weapon_event_id, perspective)
        except WeaponEventApplicationError as exc:
            return _error(exc)
        return JSONResponse(payload, headers={"Cache-Control": "private, no-store"})


__all__ = ["register_gui_weapon_event_routes"]
