"""G4 governed Batch, import-ticket and force/formation HTTP adapter."""

from __future__ import annotations

from urllib.parse import unquote

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from tpaa_application import (
    SOURCE_MAX_ARTIFACT_BYTES,
    ApplicationService,
    BatchImportError,
    ForceFormationMember,
)


def _actor(request: Request) -> str:
    from .unified import UnifiedPrincipal

    principal = getattr(request.state, "tpaa_principal", None)
    if not isinstance(principal, UnifiedPrincipal):
        raise BatchImportError("FORBIDDEN", "principal", http_status=403)
    return principal.actor_key


def _error(exc: BatchImportError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "schema": "TPAA_G4_BATCH_ERROR_V1",
            "status": "FORBIDDEN" if exc.http_status == 403 else "ERROR",
            "code": exc.code,
            "detail": exc.detail,
            "provenance": {
                "authority_id": "GUI_BATCH_IMPORT_AUTHORITY",
                "authority_version": "1.0.0",
                "core_baseline": "CB-1.9.0",
            },
        },
        headers={"Cache-Control": "private, no-store"},
    )


def _object(body: object) -> dict[str, object]:
    if not isinstance(body, dict) or not all(isinstance(key, str) for key in body):
        raise BatchImportError("G4_REQUEST_BODY_INVALID", "object")
    return body


def _string(body: dict[str, object], field: str) -> str:
    value = body.get(field)
    if not isinstance(value, str):
        raise BatchImportError("G4_REQUEST_FIELD_INVALID", field)
    return value


def _optional_string(body: dict[str, object], field: str) -> str | None:
    value = body.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise BatchImportError("G4_REQUEST_FIELD_INVALID", field)
    return value


def register_gui_batch_routes(app: FastAPI, application: ApplicationService) -> None:
    @app.post("/api/v1/gui/import-tickets", operation_id="issueGuiImportTicket")
    async def issue_ticket(
        request: Request,
        x_tpaa_ticket_kind: str = Header(alias="X-TPAA-Ticket-Kind"),
        x_tpaa_display_name: str = Header(alias="X-TPAA-Display-Name"),
    ) -> JSONResponse:
        length = request.headers.get("content-length")
        if length is not None:
            try:
                declared = int(length)
            except ValueError:
                return _error(BatchImportError("G4_CONTENT_LENGTH_INVALID", length, http_status=400))
            if declared <= 0 or declared > SOURCE_MAX_ARTIFACT_BYTES:
                return _error(BatchImportError("G4_IMPORT_SIZE_INVALID", length, http_status=413))
        data = await request.body()
        if len(data) > SOURCE_MAX_ARTIFACT_BYTES:
            return _error(BatchImportError("G4_IMPORT_SIZE_INVALID", str(len(data)), http_status=413))
        try:
            payload = application.batch_import().issue_ticket(
                kind=x_tpaa_ticket_kind.upper(),
                name=unquote(x_tpaa_display_name),
                data=data,
            )
        except BatchImportError as exc:
            return _error(exc)
        return JSONResponse(payload, status_code=201, headers={"Cache-Control": "private, no-store"})

    @app.get("/api/v1/gui/batches", operation_id="listGuiBatches")
    def list_batches() -> JSONResponse:
        try:
            payload = application.batch_import().list_batches()
        except BatchImportError as exc:
            return _error(exc)
        return JSONResponse(payload, headers={"Cache-Control": "private, no-store"})

    @app.get("/api/v1/gui/batches/{batch_id}", operation_id="getGuiBatch")
    def batch_detail(batch_id: str) -> JSONResponse:
        try:
            payload = application.batch_import().get_batch(batch_id)
        except BatchImportError as exc:
            return _error(exc)
        return JSONResponse(payload, headers={"Cache-Control": "private, no-store"})

    @app.post("/api/v1/gui/batches", operation_id="registerGuiBatch")
    def register_batch(
        request: Request,
        body: dict[str, object],
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        try:
            value = _object(body)
            if idempotency_key is None:
                raise BatchImportError("G4_IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key", http_status=400)
            confirmed = value.get("training_type_confirmed")
            if not isinstance(confirmed, bool):
                raise BatchImportError("G4_REQUEST_FIELD_INVALID", "training_type_confirmed")
            payload = application.batch_import().register_batch(
                idempotency_key=idempotency_key,
                actor=_actor(request),
                ticket_id=_string(value, "ticket_id"),
                session_id=_string(value, "session_id"),
                aircraft_id=_string(value, "aircraft_id"),
                batch_date=_string(value, "batch_date"),
                batch_training_type=_string(value, "batch_training_type"),
                training_type_confirmed=confirmed,
                producer_system=_string(value, "producer_system"),
                session_code=_string(value, "session_code"),
                session_type=_string(value, "session_type"),
                context_id=_optional_string(value, "context_id"),
                release_id=_optional_string(value, "release_id"),
            )
        except BatchImportError as exc:
            return _error(exc)
        status_code = 201 if payload.get("reason_code") != "IDEMPOTENT_REPLAY" else 200
        return JSONResponse(payload, status_code=status_code, headers={"Cache-Control": "private, no-store"})

    @app.post(
        "/api/v1/gui/batches/{batch_id}/training-type-revisions",
        operation_id="reviseGuiBatchTrainingType",
    )
    def revise_training_type(
        batch_id: str, request: Request, body: dict[str, object]
    ) -> JSONResponse:
        try:
            value = _object(body)
            payload = application.batch_import().revise_training_type(
                batch_id,
                training_type=_string(value, "batch_training_type"),
                actor=_actor(request),
                reason=_string(value, "reason"),
            )
        except BatchImportError as exc:
            return _error(exc)
        return JSONResponse(payload, headers={"Cache-Control": "private, no-store"})

    @app.get(
        "/api/v1/gui/contexts/{context_id}/force-formation",
        operation_id="getGuiForceFormationContext",
    )
    def get_context(context_id: str) -> JSONResponse:
        try:
            payload = application.batch_import().get_context(context_id)
        except BatchImportError as exc:
            return _error(exc)
        return JSONResponse(payload, headers={"Cache-Control": "private, no-store"})

    @app.post(
        "/api/v1/gui/contexts/{context_id}/force-formation-revisions",
        operation_id="reviseGuiForceFormationContext",
    )
    def revise_context(
        context_id: str, request: Request, body: dict[str, object]
    ) -> JSONResponse:
        try:
            value = _object(body)
            raw_members = value.get("members")
            if not isinstance(raw_members, list):
                raise BatchImportError("G4_REQUEST_FIELD_INVALID", "members")
            members: list[ForceFormationMember] = []
            for raw in raw_members:
                item = _object(raw)
                independent = item.get("independent_target")
                if not isinstance(independent, bool):
                    raise BatchImportError("G4_REQUEST_FIELD_INVALID", "independent_target")
                members.append(
                    ForceFormationMember(
                        aircraft_id=_string(item, "aircraft_id"),
                        formation_id=_optional_string(item, "formation_id"),
                        side=_string(item, "side"),
                        member_role=_string(item, "member_role"),
                        independent_target=independent,
                    )
                )
            valid_from = value.get("valid_from_session_time_us")
            valid_to = value.get("valid_to_session_time_us")
            if isinstance(valid_from, bool) or not isinstance(valid_from, int):
                raise BatchImportError("G4_REQUEST_FIELD_INVALID", "valid_from_session_time_us")
            if valid_to is not None and (isinstance(valid_to, bool) or not isinstance(valid_to, int)):
                raise BatchImportError("G4_REQUEST_FIELD_INVALID", "valid_to_session_time_us")
            payload = application.batch_import().revise_context(
                context_id,
                valid_from_session_time_us=valid_from,
                valid_to_session_time_us=valid_to,
                source=_string(value, "source"),
                reason=_string(value, "reason"),
                actor=_actor(request),
                members=members,
            )
        except BatchImportError as exc:
            return _error(exc)
        return JSONResponse(payload, status_code=201, headers={"Cache-Control": "private, no-store"})


__all__ = ["register_gui_batch_routes"]
