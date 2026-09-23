"""FastAPI health/readiness/version transport for M0-API-002.

Controllers deliberately consume only ``tpaa_application``. They do not import Core,
Canonical, Repository, DB-driver, or GUI implementation packages and do not recompute
READY semantics.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import FastAPI, Header, status
from fastapi.responses import JSONResponse

from tpaa_application import (
    ApplicationService,
    IdempotencyConflict,
    JobNotFound,
    JobRecord,
    RuntimeBaselineStatus,
)


def _readiness_payload(runtime: RuntimeBaselineStatus) -> dict[str, object]:
    return {
        "status": runtime.readiness,
        "ready": runtime.ready,
        "mismatches": list(runtime.mismatches),
    }


def _version_payload(runtime: RuntimeBaselineStatus) -> dict[str, object]:
    return {
        "readiness": runtime.readiness,
        "expected": asdict(runtime.expected),
        "observed": asdict(runtime.observed),
    }


def _job_payload(record: JobRecord, *, reused: bool | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "job_id": record.job_id,
        "request_hash": record.request_hash,
        "command": record.command,
        "status": record.status.value,
        "cancellation_reason": record.cancellation_reason,
    }
    if reused is not None:
        payload["reused"] = reused
    return payload


def _system_error(code: str, detail: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={
            "outcome": "SYSTEM_ERROR",
            "error": {"code": code, "detail": detail},
        },
    )


def create_app(application: ApplicationService) -> FastAPI:
    """Create the local/service HTTP adapter around an already-wired Application Service."""

    app = FastAPI(title="TPAA", version="0.0.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        """Process liveness only; it intentionally does not claim business readiness."""

        return {"status": "UP"}

    @app.get("/readiness")
    def readiness() -> JSONResponse:
        """Expose the Application-projected Core handshake with fail-closed HTTP status."""

        runtime = application.runtime_baseline_status()
        http_status = status.HTTP_200_OK if runtime.ready else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(status_code=http_status, content=_readiness_payload(runtime))

    @app.get("/version")
    def version() -> dict[str, object]:
        """Expose expected/observed runtime baseline/build identity for diagnostics."""

        return _version_payload(application.runtime_baseline_status())

    @app.post("/jobs")
    def submit_job(
        body: dict[str, object],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
        actor: Annotated[str, Header(alias="X-TPAA-Actor")] = "development",
    ) -> JSONResponse:
        command = body.get("command")
        payload = body.get("payload")
        if idempotency_key is None or not idempotency_key.strip():
            return _system_error("IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key is required", 400)
        if not isinstance(command, str) or not command:
            return _system_error("JOB_COMMAND_INVALID", "command must be non-empty string", 422)
        if not isinstance(payload, dict) or not all(isinstance(key, str) for key in payload):
            return _system_error("JOB_PAYLOAD_INVALID", "payload must be an object", 422)
        try:
            submission = application.submit_job(
                idempotency_key=idempotency_key,
                command=command,
                payload=payload,
                actor=actor,
            )
        except IdempotencyConflict as exc:
            return _system_error("IDEMPOTENCY_KEY_CONFLICT", str(exc), 409)
        return JSONResponse(
            status_code=200 if submission.reused else 202,
            content=_job_payload(submission.record, reused=submission.reused),
        )

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str) -> JSONResponse:
        try:
            record = application.job(job_id)
        except JobNotFound as exc:
            return _system_error("JOB_NOT_FOUND", str(exc), 404)
        return JSONResponse(status_code=200, content=_job_payload(record))

    @app.post("/jobs/{job_id}/cancel")
    def cancel_job(
        job_id: str,
        body: dict[str, object],
        actor: Annotated[str, Header(alias="X-TPAA-Actor")] = "development",
    ) -> JSONResponse:
        reason = body.get("reason")
        if not isinstance(reason, str) or not reason:
            return _system_error("CANCEL_REASON_REQUIRED", "reason must be non-empty string", 422)
        try:
            record = application.cancel_job(job_id=job_id, actor=actor, reason=reason)
        except JobNotFound as exc:
            return _system_error("JOB_NOT_FOUND", str(exc), 404)
        return JSONResponse(status_code=200, content=_job_payload(record))

    return app
