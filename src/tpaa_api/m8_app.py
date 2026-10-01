"""M8 exact P4/P5 FastAPI transport with injected principal resolution."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tpaa_application import (
    ApplicationService,
    M8AnnotationMutation,
    M8ApplicationError,
    M8ApprovalMutation,
    M8P4Query,
    M8P5Query,
    M8ViewerContext,
    M8WorkspaceQuery,
)

from .app import create_app

M8PrincipalResolver = Callable[[Request], M8ViewerContext]


def _error(exc: M8ApplicationError) -> JSONResponse:
    if exc.code in {
        "M8_P4_REVISION_NOT_FOUND",
        "M8_P5_REVISION_NOT_FOUND",
        "M8_ANNOTATION_NOT_FOUND",
    }:
        status = 404
    elif exc.code == "M8_P4_P5_NOT_ADMITTED":
        status = 423
    elif (
        "NOT_AUTHORIZED" in exc.code
        or "APPROVAL_NOT_AUTHORIZED" in exc.code
    ):
        status = 403
    elif exc.code in {
        "M8_IMMUTABLE_CONFLICT",
        "M8_P4_P5_SCOPE_MISMATCH",
    }:
        status = 409
    else:
        status = 422
    return JSONResponse(
        status_code=status,
        content={
            "outcome": "SYSTEM_ERROR",
            "error": {"code": exc.code, "detail": exc.detail},
        },
    )


def _text(body: dict[str, object], field: str) -> str:
    value = body.get(field)
    if not isinstance(value, str) or not value:
        raise M8ApplicationError("M8_DTO_STRING_INVALID", field)
    return value


def _optional_text(body: dict[str, object], field: str) -> str | None:
    value = body.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise M8ApplicationError("M8_DTO_STRING_INVALID", field)
    return value


def _optional_int(body: dict[str, object], field: str) -> int | None:
    value = body.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise M8ApplicationError("M8_DTO_INTEGER_INVALID", field)
    return value


def register_m8_routes(
    app: FastAPI,
    application: ApplicationService,
    *,
    principal_resolver: M8PrincipalResolver,
) -> FastAPI:
    """Register exact-ID M8 routes; identity/roles come from injected auth context."""

    def principal(request: Request) -> M8ViewerContext:
        try:
            value = principal_resolver(request)
        except M8ApplicationError:
            raise
        except Exception as exc:
            raise M8ApplicationError(
                "FAIL_CLOSED_P4_P5_DIRECT_IDENTITY_NOT_AUTHORIZED",
                type(exc).__name__,
            ) from exc
        if not isinstance(value, M8ViewerContext):
            raise M8ApplicationError(
                "FAIL_CLOSED_P4_P5_DIRECT_IDENTITY_NOT_AUTHORIZED",
                "principal resolver returned invalid context",
            )
        return value

    @app.get("/m8/p4/assessments/{actor_assessment_id}")
    def p4(actor_assessment_id: str, request: Request) -> JSONResponse:
        try:
            payload = application.m8_p4(
                M8P4Query(
                    actor_assessment_id=actor_assessment_id,
                    viewer=principal(request),
                )
            )
        except M8ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.get("/m8/p5/assessments/{mission_assessment_id}")
    def p5(mission_assessment_id: str, request: Request) -> JSONResponse:
        try:
            payload = application.m8_p5(
                M8P5Query(
                    mission_assessment_id=mission_assessment_id,
                    viewer=principal(request),
                )
            )
        except M8ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.get(
        "/m8/workspace/p4/{actor_assessment_id}/p5/{mission_assessment_id}"
    )
    def workspace(
        actor_assessment_id: str,
        mission_assessment_id: str,
        request: Request,
    ) -> JSONResponse:
        try:
            payload = application.m8_workspace(
                M8WorkspaceQuery(
                    actor_assessment_id=actor_assessment_id,
                    mission_assessment_id=mission_assessment_id,
                    viewer=principal(request),
                )
            )
        except M8ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.post("/m8/p4/assessments/{actor_assessment_id}/annotations")
    def annotate(
        actor_assessment_id: str,
        request: Request,
        body: dict[str, object],
    ) -> JSONResponse:
        try:
            payload = application.m8_annotation(
                M8AnnotationMutation(
                    target_p4_revision_id=actor_assessment_id,
                    previous_annotation_id=_optional_text(
                        body,
                        "previous_annotation_id",
                    ),
                    request_id=_text(body, "request_id"),
                    base_release_id=_text(body, "base_release_id"),
                    annotation_type=_text(body, "annotation_type"),
                    start_session_time_us=_optional_int(
                        body,
                        "start_session_time_us",
                    ),
                    end_session_time_us=_optional_int(
                        body,
                        "end_session_time_us",
                    ),
                    body_text=_text(body, "body_text"),
                    visibility=_text(body, "visibility"),
                    reason=_text(body, "reason"),
                    created_at_utc=_text(body, "created_at_utc"),
                    viewer=principal(request),
                )
            )
        except M8ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.post("/m8/p4/assessments/{actor_assessment_id}/approval")
    def p4_approval(
        actor_assessment_id: str,
        request: Request,
        body: dict[str, object],
    ) -> JSONResponse:
        try:
            payload = application.m8_p4_approval(
                M8ApprovalMutation(
                    target_revision_id=actor_assessment_id,
                    request_id=_text(body, "request_id"),
                    target_state=_text(body, "target_state"),
                    reason=_text(body, "reason"),
                    created_at_utc=_text(body, "created_at_utc"),
                    viewer=principal(request),
                )
            )
        except M8ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.post("/m8/p5/assessments/{mission_assessment_id}/approval")
    def p5_approval(
        mission_assessment_id: str,
        request: Request,
        body: dict[str, object],
    ) -> JSONResponse:
        try:
            payload = application.m8_p5_approval(
                M8ApprovalMutation(
                    target_revision_id=mission_assessment_id,
                    request_id=_text(body, "request_id"),
                    target_state=_text(body, "target_state"),
                    reason=_text(body, "reason"),
                    created_at_utc=_text(body, "created_at_utc"),
                    viewer=principal(request),
                )
            )
        except M8ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.get(
        "/m8/export/p4/{actor_assessment_id}/p5/{mission_assessment_id}"
    )
    def export(
        actor_assessment_id: str,
        mission_assessment_id: str,
        request: Request,
    ) -> JSONResponse:
        try:
            payload = application.m8_export(
                M8WorkspaceQuery(
                    actor_assessment_id=actor_assessment_id,
                    mission_assessment_id=mission_assessment_id,
                    viewer=principal(request),
                )
            )
        except M8ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    return app


def create_m8_app(
    application: ApplicationService,
    *,
    principal_resolver: M8PrincipalResolver,
) -> FastAPI:
    return register_m8_routes(
        create_app(application),
        application,
        principal_resolver=principal_resolver,
    )
