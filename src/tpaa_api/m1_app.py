"""M1 Batch 2 FastAPI transport over the Application Service only."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, Query
from fastapi.responses import JSONResponse

from tpaa_application import (
    ApplicationService,
    M1ApplicationError,
    M1PublishSessionCommand,
)

from .app import create_app


def _m1_error(exc: M1ApplicationError) -> JSONResponse:
    if exc.code in {"RELEASE_NOT_FOUND", "METRIC_NOT_FOUND", "M1_FIXTURE_NOT_FOUND"}:
        http_status = 404
    elif exc.code in {"PUBLISH_CAS_CONFLICT", "IDEMPOTENCY_KEY_CONFLICT"}:
        http_status = 409
    elif exc.code.startswith("HISTORICAL_"):
        http_status = 409
    else:
        http_status = 422
    return JSONResponse(
        status_code=http_status,
        content={
            "outcome": "SYSTEM_ERROR",
            "error": {"code": exc.code, "detail": exc.detail},
        },
    )


def _required_text(body: dict[str, object], field: str) -> str:
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        raise M1ApplicationError("M1_COMMAND_FIELD_INVALID", field)
    return value


def _required_token(body: dict[str, object]) -> int:
    value = body.get("expected_version_token")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise M1ApplicationError("M1_COMMAND_FIELD_INVALID", "expected_version_token")
    return value


def create_m1_app(application: ApplicationService):
    """Extend the stable M0 transport with release-bound M1 backend endpoints."""

    app = create_app(application)

    def _submit_control_command(
        *,
        command: str,
        body: dict[str, object],
        idempotency_key: str | None,
        actor: str,
    ) -> JSONResponse:
        if idempotency_key is None or not idempotency_key.strip():
            return JSONResponse(
                status_code=400,
                content={
                    "outcome": "SYSTEM_ERROR",
                    "error": {
                        "code": "IDEMPOTENCY_KEY_REQUIRED",
                        "detail": "Idempotency-Key is required",
                    },
                },
            )
        try:
            submission = application.submit_job(
                idempotency_key=idempotency_key,
                command=command,
                payload=body,
                actor=actor,
            )
        except Exception as exc:
            from tpaa_application import IdempotencyConflict

            if isinstance(exc, IdempotencyConflict):
                return JSONResponse(
                    status_code=409,
                    content={
                        "outcome": "SYSTEM_ERROR",
                        "error": {"code": "IDEMPOTENCY_KEY_CONFLICT", "detail": str(exc)},
                    },
                )
            raise
        record = submission.record
        return JSONResponse(
            status_code=200 if submission.reused else 202,
            content={
                "job_id": record.job_id,
                "request_hash": record.request_hash,
                "command": record.command,
                "status": record.status.value,
                "reused": submission.reused,
            },
        )

    @app.post("/m1/commands/import-session")
    def import_session(
        body: dict[str, object],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
        actor: Annotated[str, Header(alias="X-TPAA-Actor")] = "development",
    ) -> JSONResponse:
        return _submit_control_command(
            command="M1_IMPORT_SESSION",
            body=body,
            idempotency_key=idempotency_key,
            actor=actor,
        )

    @app.post("/m1/commands/compute-session")
    def compute_session(
        body: dict[str, object],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
        actor: Annotated[str, Header(alias="X-TPAA-Actor")] = "development",
    ) -> JSONResponse:
        return _submit_control_command(
            command="M1_COMPUTE_SESSION",
            body=body,
            idempotency_key=idempotency_key,
            actor=actor,
        )

    @app.post("/m1/commands/publish-session")
    def publish_session(
        body: dict[str, object],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> JSONResponse:
        if idempotency_key is None or not idempotency_key.strip():
            return JSONResponse(
                status_code=400,
                content={
                    "outcome": "SYSTEM_ERROR",
                    "error": {
                        "code": "IDEMPOTENCY_KEY_REQUIRED",
                        "detail": "Idempotency-Key is required",
                    },
                },
            )
        try:
            command = M1PublishSessionCommand(
                fixture_id=_required_text(body, "fixture_id"),
                aircraft_model_id=_required_text(body, "aircraft_model_id"),
                aircraft_instance_id=_required_text(body, "aircraft_instance_id"),
                subject_entity_id=_required_text(body, "subject_entity_id"),
                capability_dimension=_required_text(body, "capability_dimension"),
                capability_type=_required_text(body, "capability_type"),
                expected_version_token=_required_token(body),
            )
            result = application.publish_m1_session(
                command,
                idempotency_key=idempotency_key,
            )
        except M1ApplicationError as exc:
            return _m1_error(exc)
        return JSONResponse(
            status_code=200 if result.reused else 201,
            content={
                "release_id": result.release_id,
                "session_id": result.session_id,
                "request_hash": result.request_hash,
                "manifest_hash": result.manifest_hash,
                "status": result.status,
                "version_token": result.version_token,
                "reused": result.reused,
            },
        )

    @app.get("/m1/releases/{release_id}")
    def get_release(release_id: str) -> JSONResponse:
        try:
            return JSONResponse(status_code=200, content=application.m1_release(release_id))
        except M1ApplicationError as exc:
            return _m1_error(exc)

    @app.get("/m1/releases/{release_id}/observations")
    def get_observations(release_id: str) -> JSONResponse:
        try:
            return JSONResponse(
                status_code=200,
                content={"release_id": release_id, "items": application.m1_observations(release_id)},
            )
        except M1ApplicationError as exc:
            return _m1_error(exc)

    @app.get("/m1/releases/{release_id}/metrics")
    def get_metrics(release_id: str) -> JSONResponse:
        try:
            return JSONResponse(
                status_code=200,
                content={"release_id": release_id, "items": application.m1_metrics(release_id)},
            )
        except M1ApplicationError as exc:
            return _m1_error(exc)

    @app.get("/m1/releases/{release_id}/metrics/{metric_code}")
    def get_metric(release_id: str, metric_code: str) -> JSONResponse:
        try:
            return JSONResponse(
                status_code=200,
                content=application.m1_metric(release_id, metric_code),
            )
        except M1ApplicationError as exc:
            return _m1_error(exc)

    @app.get("/m1/releases/{release_id}/context")
    def get_context(release_id: str) -> JSONResponse:
        try:
            return JSONResponse(status_code=200, content=application.m1_context(release_id))
        except M1ApplicationError as exc:
            return _m1_error(exc)

    @app.get("/m1/releases/{release_id}/topology")
    def get_session_episode_stages(release_id: str) -> JSONResponse:
        try:
            return JSONResponse(
                status_code=200,
                content=application.m1_session_episode_stages(release_id),
            )
        except M1ApplicationError as exc:
            return _m1_error(exc)

    @app.post("/m1/releases/{release_id}/replay")
    def replay(release_id: str) -> JSONResponse:
        try:
            return JSONResponse(
                status_code=200,
                content=application.replay_m1_release(release_id),
            )
        except M1ApplicationError as exc:
            return _m1_error(exc)

    @app.get("/m1/releases/{release_id}/series")
    def series(
        release_id: str,
        start_session_time_us: Annotated[int, Query()],
        end_session_time_us: Annotated[int, Query()],
        limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
    ) -> JSONResponse:
        try:
            return JSONResponse(
                status_code=200,
                content=application.m1_series_range(
                    release_id,
                    start_session_time_us=start_session_time_us,
                    end_session_time_us=end_session_time_us,
                    limit=limit,
                ),
            )
        except M1ApplicationError as exc:
            return _m1_error(exc)

    return app
