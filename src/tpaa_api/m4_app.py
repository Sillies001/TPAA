"""M4 exact-release longitudinal and Debrief FastAPI transport."""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from tpaa_application import (
    ApplicationService,
    M4AnnotationCommand,
    M4ApplicationError,
    M4DebriefQuery,
    M4TrendQuery,
)

from .app import create_app


def _error(exc: M4ApplicationError) -> JSONResponse:
    if exc.code in {
        "M4_RELEASE_NOT_FOUND",
        "M4_ANNOTATION_TARGET_NOT_FOUND",
    }:
        status = 404
    elif exc.code in {
        "M4_ANNOTATION_REQUEST_CONFLICT",
        "M4_ANNOTATION_TARGET_NOT_ACTIVE",
        "M4_DEBRIEF_TIMELINE_IMMUTABLE",
        "M4_TREND_QUERY_NO_MATCH",
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


def register_m4_routes(
    app: FastAPI,
    application: ApplicationService,
) -> FastAPI:
    """Register C3-authority-bound M4 routes over Application projections."""

    @app.get("/m4/longitudinal/releases/{release_id}/trend")
    def get_longitudinal_trend(
        release_id: str,
        trend_id: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        metric_code: str | None = None,
        comparison_key_hash: str | None = None,
    ) -> JSONResponse:
        try:
            payload = application.m4_trend(
                M4TrendQuery(
                    release_id=release_id,
                    trend_id=trend_id,
                    subject_type=subject_type,
                    subject_id=subject_id,
                    metric_code=metric_code,
                    comparison_key_hash=comparison_key_hash,
                )
            )
            return JSONResponse(status_code=200, content=payload)
        except M4ApplicationError as exc:
            return _error(exc)

    @app.get("/m4/debrief/releases/{base_release_id}")
    def get_debrief(
        base_release_id: str,
        view_mode: str = "ORIGINAL_AS_KNOWN",
        retrospective_release_id: str | None = None,
        annotation_view: str = "NONE",
        annotation_as_of_utc: str | None = None,
        annotation_ids: Annotated[list[str] | None, Query()] = None,
    ) -> JSONResponse:
        try:
            payload = application.m4_debrief(
                M4DebriefQuery(
                    base_release_id=base_release_id,
                    view_mode=view_mode,
                    retrospective_release_id=retrospective_release_id,
                    annotation_view=annotation_view,
                    annotation_as_of_utc=annotation_as_of_utc,
                    annotation_ids=tuple(annotation_ids or ()),
                )
            )
            return JSONResponse(status_code=200, content=payload)
        except M4ApplicationError as exc:
            return _error(exc)

    @app.post("/m4/debrief/annotations")
    def mutate_annotation(body: dict[str, object]) -> JSONResponse:
        try:
            command = M4AnnotationCommand(
                request_id=str(body.get("request_id") or ""),
                operation=str(body.get("operation") or ""),
                base_release_id=str(body.get("base_release_id") or ""),
                target_annotation_id=cast_optional_str(
                    body.get("target_annotation_id")
                ),
                session_id=str(body.get("session_id") or ""),
                episode_id=cast_optional_str(body.get("episode_id")),
                stage_id=cast_optional_str(body.get("stage_id")),
                author_id=str(body.get("author_id") or ""),
                annotation_type=str(body.get("annotation_type") or ""),
                start_session_time_us=cast_optional_int(
                    body.get("start_session_time_us")
                ),
                end_session_time_us=cast_optional_int(
                    body.get("end_session_time_us")
                ),
                body_text=str(body.get("body_text") or ""),
                visibility=str(body.get("visibility") or ""),
                reason=str(body.get("reason") or ""),
                evidence_set_id=cast_optional_str(
                    body.get("evidence_set_id")
                ),
            )
            payload = application.m4_annotation(command)
            return JSONResponse(status_code=200, content=payload)
        except M4ApplicationError as exc:
            return _error(exc)

    return app


def cast_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise M4ApplicationError(
            "M4_DTO_STRING_INVALID",
            repr(value),
        )
    return value


def cast_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise M4ApplicationError(
            "M4_DTO_INTEGER_INVALID",
            repr(value),
        )
    return value


def create_m4_app(application: ApplicationService) -> FastAPI:
    """Extend the stable local transport with exact-release M4 routes."""

    return register_m4_routes(create_app(application), application)
