"""M9 exact P6 FastAPI transport with injected principal resolution."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tpaa_application import (
    ApplicationService,
    M9ApplicationError,
    M9CounterfactualMutation,
    M9ExactQuery,
    M9ForecastMutation,
    M9ModelReleaseMutation,
    M9RecommendationApprovalMutation,
    M9RecommendationMutation,
    M9WorkspaceQuery,
)
from tpaa_context import P6SecurityViewer

from .app import create_app

M9PrincipalResolver = Callable[[Request], P6SecurityViewer]


def _error(exc: M9ApplicationError) -> JSONResponse:
    if exc.code.endswith("_NOT_FOUND"):
        status = 404
    elif "NOT_ADMITTED" in exc.code:
        status = 423
    elif "NOT_AUTHORIZED" in exc.code or "denied" in exc.detail.lower():
        status = 403
    elif "CONFLICT" in exc.code:
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


def _text(body: Mapping[str, object], field: str) -> str:
    value = body.get(field)
    if not isinstance(value, str) or not value:
        raise M9ApplicationError("M9_DTO_STRING_INVALID", field)
    return value


def _mapping(body: Mapping[str, object], field: str) -> dict[str, object]:
    value = body.get(field)
    if not isinstance(value, Mapping):
        raise M9ApplicationError("M9_DTO_MAPPING_INVALID", field)
    return {str(key): item for key, item in value.items()}


def _strings(body: Mapping[str, object], field: str) -> tuple[str, ...]:
    value = body.get(field)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise M9ApplicationError("M9_DTO_STRINGS_INVALID", field)
    if not all(isinstance(item, str) and item for item in value):
        raise M9ApplicationError("M9_DTO_STRINGS_INVALID", field)
    return tuple(cast(Sequence[str], value))


def register_m9_routes(
    app: FastAPI,
    application: ApplicationService,
    *,
    principal_resolver: M9PrincipalResolver,
) -> FastAPI:
    """Register exact-ID M9 routes; transports never resolve aliases or recompute."""

    def principal(request: Request) -> P6SecurityViewer:
        try:
            value = principal_resolver(request)
        except M9ApplicationError:
            raise
        except Exception as exc:
            raise M9ApplicationError(
                "M9_PROJECTION_NOT_AUTHORIZED",
                type(exc).__name__,
            ) from exc
        if not isinstance(value, P6SecurityViewer):
            raise M9ApplicationError(
                "M9_PROJECTION_NOT_AUTHORIZED",
                "invalid principal context",
            )
        return value

    @app.get("/m9/models/{capability_model_id}")
    def model(capability_model_id: str, request: Request) -> JSONResponse:
        try:
            payload = application.m9_model(
                M9ExactQuery(capability_model_id, principal(request))
            )
        except M9ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.get("/m9/forecast-requests/{forecast_request_id}")
    def forecast_request(
        forecast_request_id: str,
        request: Request,
    ) -> JSONResponse:
        try:
            payload = application.m9_forecast_request(
                M9ExactQuery(forecast_request_id, principal(request))
            )
        except M9ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.get(
        "/m9/counterfactual-requests/{counterfactual_request_id}"
    )
    def counterfactual_request(
        counterfactual_request_id: str,
        request: Request,
    ) -> JSONResponse:
        try:
            payload = application.m9_counterfactual_request(
                M9ExactQuery(counterfactual_request_id, principal(request))
            )
        except M9ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.get("/m9/forecasts/{forecast_result_id}")
    def forecast(forecast_result_id: str, request: Request) -> JSONResponse:
        try:
            payload = application.m9_forecast(
                M9ExactQuery(forecast_result_id, principal(request))
            )
        except M9ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.get("/m9/counterfactuals/{counterfactual_run_id}")
    def counterfactual(
        counterfactual_run_id: str,
        request: Request,
    ) -> JSONResponse:
        try:
            payload = application.m9_counterfactual(
                M9ExactQuery(counterfactual_run_id, principal(request))
            )
        except M9ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.get("/m9/recommendations/{recommendation_id}")
    def recommendation(
        recommendation_id: str,
        request: Request,
    ) -> JSONResponse:
        try:
            payload = application.m9_recommendation(
                M9ExactQuery(recommendation_id, principal(request))
            )
        except M9ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.get(
        "/m9/workspace/forecast/{forecast_result_id}"
        "/counterfactual/{counterfactual_run_id}"
        "/recommendation/{recommendation_id}"
    )
    def workspace(
        forecast_result_id: str,
        counterfactual_run_id: str,
        recommendation_id: str,
        request: Request,
    ) -> JSONResponse:
        try:
            payload = application.m9_workspace(
                M9WorkspaceQuery(
                    forecast_result_id=forecast_result_id,
                    counterfactual_run_id=counterfactual_run_id,
                    recommendation_id=recommendation_id,
                    viewer=principal(request),
                )
            )
        except M9ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.post("/m9/forecast-requests/{forecast_request_id}/run")
    def run_forecast(
        forecast_request_id: str,
        body: dict[str, object],
        request: Request,
    ) -> JSONResponse:
        try:
            payload = application.m9_run_forecast(
                M9ForecastMutation(
                    request_id=_text(body, "request_id"),
                    forecast_request_id=forecast_request_id,
                    published_at_utc=_text(body, "published_at_utc"),
                    viewer=principal(request),
                )
            )
        except M9ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.post(
        "/m9/counterfactual-requests/{counterfactual_request_id}/run"
    )
    def run_counterfactual(
        counterfactual_request_id: str,
        body: dict[str, object],
        request: Request,
    ) -> JSONResponse:
        try:
            payload = application.m9_run_counterfactual(
                M9CounterfactualMutation(
                    request_id=_text(body, "request_id"),
                    counterfactual_request_id=counterfactual_request_id,
                    created_at_utc=_text(body, "created_at_utc"),
                    viewer=principal(request),
                )
            )
        except M9ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.post("/m9/recommendations")
    def create_recommendation(
        body: dict[str, object],
        request: Request,
    ) -> JSONResponse:
        try:
            payload = application.m9_create_recommendation(
                M9RecommendationMutation(
                    request_id=_text(body, "request_id"),
                    subject_id=_text(body, "subject_id"),
                    recommendation_spec_id=_text(
                        body,
                        "recommendation_spec_id",
                    ),
                    recommendation_spec_version=_text(
                        body,
                        "recommendation_spec_version",
                    ),
                    source_forecast_result_ids=_strings(
                        body,
                        "source_forecast_result_ids",
                    ),
                    source_counterfactual_run_ids=_strings(
                        body,
                        "source_counterfactual_run_ids",
                    ),
                    objective_constraints=_mapping(
                        body,
                        "objective_constraints",
                    ),
                    allowed_action_space=_mapping(
                        body,
                        "allowed_action_space",
                    ),
                    rationale=_mapping(body, "rationale"),
                    source_gap_refs=_strings(body, "source_gap_refs"),
                    proposed_training_items=_mapping(
                        body,
                        "proposed_training_items",
                    ),
                    created_at_utc=_text(body, "created_at_utc"),
                    viewer=principal(request),
                )
            )
        except M9ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=201, content=payload)

    @app.post("/m9/recommendations/{recommendation_id}/approval")
    def approve_recommendation(
        recommendation_id: str,
        body: dict[str, object],
        request: Request,
    ) -> JSONResponse:
        try:
            payload = application.m9_approve_recommendation(
                M9RecommendationApprovalMutation(
                    recommendation_id=recommendation_id,
                    request_id=_text(body, "request_id"),
                    target_state=_text(body, "target_state"),
                    reason=_text(body, "reason"),
                    created_at_utc=_text(body, "created_at_utc"),
                    viewer=principal(request),
                )
            )
        except M9ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.post("/m9/models/{capability_model_id}/release")
    def release_model(
        capability_model_id: str,
        body: dict[str, object],
        request: Request,
    ) -> JSONResponse:
        try:
            payload = application.m9_release_model(
                M9ModelReleaseMutation(
                    capability_model_id=capability_model_id,
                    request_id=_text(body, "request_id"),
                    published_at_utc=_text(body, "published_at_utc"),
                    viewer=principal(request),
                )
            )
        except M9ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    @app.get(
        "/m9/export/forecast/{forecast_result_id}"
        "/counterfactual/{counterfactual_run_id}"
        "/recommendation/{recommendation_id}"
    )
    def export(
        forecast_result_id: str,
        counterfactual_run_id: str,
        recommendation_id: str,
        request: Request,
    ) -> JSONResponse:
        try:
            payload = application.m9_export(
                M9WorkspaceQuery(
                    forecast_result_id=forecast_result_id,
                    counterfactual_run_id=counterfactual_run_id,
                    recommendation_id=recommendation_id,
                    viewer=principal(request),
                )
            )
        except M9ApplicationError as exc:
            return _error(exc)
        return JSONResponse(status_code=200, content=payload)

    return app


def create_m9_app(
    application: ApplicationService,
    *,
    principal_resolver: M9PrincipalResolver,
) -> FastAPI:
    return register_m9_routes(
        create_app(application),
        application,
        principal_resolver=principal_resolver,
    )
