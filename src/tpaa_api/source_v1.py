"""W2 production Source ingress HTTP transport."""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, Query, Request, status
from fastapi.responses import JSONResponse
from starlette.requests import ClientDisconnect

from tpaa_application import (
    SOURCE_MAX_ARTIFACT_BYTES,
    SOURCE_STREAM_CHUNK_BYTES,
    ApplicationService,
    SourceWorkflowError,
    bounded_source_bytes,
)


def _error(exc: SourceWorkflowError) -> JSONResponse:
    if exc.code == "W2_SOURCE_IMPORT_CANCELLED":
        http_status = status.HTTP_409_CONFLICT
    elif exc.code in {"SOURCE_ARTIFACT_SIZE_INVALID", "W2_SOURCE_CHUNK_TOO_LARGE"}:
        http_status = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    else:
        http_status = status.HTTP_422_UNPROCESSABLE_CONTENT
    return JSONResponse(
        status_code=http_status,
        content={
            "outcome": "SYSTEM_ERROR",
            "error": {"code": exc.code, "detail": exc.detail},
        },
    )


async def _source_body(request: Request) -> bytes:
    chunks: list[bytes] = []
    received_bytes = 0
    try:
        async for received in request.stream():
            if not received:
                continue
            for start in range(0, len(received), SOURCE_STREAM_CHUNK_BYTES):
                chunk = received[start : start + SOURCE_STREAM_CHUNK_BYTES]
                received_bytes += len(chunk)
                if received_bytes > SOURCE_MAX_ARTIFACT_BYTES:
                    raise SourceWorkflowError("SOURCE_ARTIFACT_SIZE_INVALID", str(received_bytes))
                chunks.append(chunk)
    except ClientDisconnect as exc:
        raise SourceWorkflowError("W2_SOURCE_IMPORT_CANCELLED", "client_disconnect") from exc
    return bounded_source_bytes(chunks)


def register_source_v1_routes(app: FastAPI, application: ApplicationService) -> FastAPI:
    """Register inspect/validate/stage/canonicalize routes over raw CSV bodies."""

    @app.get("/api/v1/sources/adapters")
    def adapters() -> JSONResponse:
        try:
            payload = application.source_workflow().adapter_registry()
        except RuntimeError as exc:
            return JSONResponse(
                status_code=503,
                content={
                    "outcome": "SYSTEM_ERROR",
                    "error": {"code": "SOURCE_WORKFLOW_UNAVAILABLE", "detail": str(exc)},
                },
            )
        return JSONResponse(status_code=200, content=payload)

    @app.post("/api/v1/sources/flight-csv/inspect")
    async def inspect_flight_csv(
        request: Request,
        session_id: Annotated[str, Query()],
        aircraft_id: Annotated[str, Query()],
        source_ref: Annotated[str, Query()],
    ) -> JSONResponse:
        try:
            data = await _source_body(request)
            payload = application.source_workflow().inspect_flight_csv(
                data,
                session_id=session_id,
                aircraft_id=aircraft_id,
                source_ref=source_ref,
            )
        except SourceWorkflowError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.post("/api/v1/sources/flight-csv/stage")
    async def stage_flight_csv(
        request: Request,
        session_id: Annotated[str, Query()],
        aircraft_id: Annotated[str, Query()],
        source_ref: Annotated[str, Query()],
        raw_artifact_id: Annotated[str, Query()],
        canonical_artifact_id: Annotated[str, Query()],
        source_id: Annotated[str, Query()],
        source_stream_id: Annotated[str, Query()],
        producer_system: Annotated[str, Query()],
        session_code: Annotated[str, Query()],
        session_type: Annotated[str, Query(pattern="^(LIVE|SIM|LVC)$")],
        classification_label: Annotated[str | None, Query()] = None,
        nominal_rate_hz: Annotated[float | None, Query(gt=0.0)] = None,
    ) -> JSONResponse:
        try:
            data = await _source_body(request)
            payload = application.source_workflow().stage_flight_csv(
                data,
                session_id=session_id,
                aircraft_id=aircraft_id,
                source_ref=source_ref,
                raw_artifact_id=raw_artifact_id,
                canonical_artifact_id=canonical_artifact_id,
                source_id=source_id,
                source_stream_id=source_stream_id,
                producer_system=producer_system,
                session_code=session_code,
                session_type=session_type,
                classification_label=classification_label,
                nominal_rate_hz=nominal_rate_hz,
            )
        except SourceWorkflowError as exc:
            return _error(exc)
        return JSONResponse(status_code=201, content=payload)

    return app
