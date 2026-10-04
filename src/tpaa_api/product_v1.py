"""PIQB B4 versioned exact-ID Product API v1 facade."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict
from uuid import UUID

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from tpaa_application import (
    ApplicationService,
    M6P2ComparisonQuery,
    M7EstimateQuery,
    M7TwinQuery,
    M8P4Query,
    M8P5Query,
    M8ViewerContext,
    M9ExactQuery,
    M9ViewerContext,
)

PRODUCT_API_VERSION = "v1"
PRODUCT_API_AUTHORITY_ID = "CROSS_LAYER_DTO_CONTRACTS"
PRODUCT_API_AUTHORITY_VERSION = "UNVERSIONED_BY_AUTHORITY"
PRODUCT_API_CORE_BASELINE = "CB-1.4.0"
PRODUCT_API_AUTHORITY_SHA256 = (
    "28f7209e40709fb4eb53ceffdfee3542e867f060c4e63605cc1ad149a8e3819a"
)


class ProductV1Authority(TypedDict):
    artifact_id: str
    artifact_version: str
    core_baseline: str
    sha256: str


class ProductV1Envelope(TypedDict):
    api_version: str
    phase: str
    product_kind: str
    exact_ids: dict[str, str]
    authority: ProductV1Authority
    payload: dict[str, object]


M8ProductPrincipalResolver = Callable[[Request], M8ViewerContext]
M9ProductPrincipalResolver = Callable[[Request], M9ViewerContext]


def _authority() -> ProductV1Authority:
    return ProductV1Authority(
        artifact_id=PRODUCT_API_AUTHORITY_ID,
        artifact_version=PRODUCT_API_AUTHORITY_VERSION,
        core_baseline=PRODUCT_API_CORE_BASELINE,
        sha256=PRODUCT_API_AUTHORITY_SHA256,
    )


def _envelope(
    *,
    phase: str,
    product_kind: str,
    exact_ids: dict[str, str],
    payload: dict[str, object],
) -> ProductV1Envelope:
    return ProductV1Envelope(
        api_version=PRODUCT_API_VERSION,
        phase=phase,
        product_kind=product_kind,
        exact_ids=exact_ids,
        authority=_authority(),
        payload=payload,
    )


def _error(exc: Exception) -> JSONResponse:
    detail = str(exc)
    upper = detail.upper()
    if "NOT_FOUND" in upper or isinstance(exc, LookupError):
        code = status.HTTP_404_NOT_FOUND
    elif "NOT_ADMITTED" in upper:
        code = status.HTTP_423_LOCKED
    elif (
        "NOT_AUTHORIZED" in upper
        or "DENIED" in upper
        or isinstance(exc, PermissionError)
    ):
        code = status.HTTP_403_FORBIDDEN
    elif "CONFLICT" in upper or "MISMATCH" in upper:
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    return JSONResponse(
        status_code=code,
        content={
            "outcome": "SYSTEM_ERROR",
            "error": {
                "code": "PRODUCT_V1_EXACT_READ_FAILED",
                "detail": detail,
            },
        },
    )


def _m8_principal(
    resolver: M8ProductPrincipalResolver,
    request: Request,
) -> M8ViewerContext:
    value = resolver(request)
    if not isinstance(value, M8ViewerContext):
        raise PermissionError("invalid M8 principal context")
    return value


def _m9_principal(
    resolver: M9ProductPrincipalResolver,
    request: Request,
) -> M9ViewerContext:
    value = resolver(request)
    if not isinstance(value, M9ViewerContext):
        raise PermissionError("invalid M9 principal context")
    return value


def register_product_v1_routes(
    app: FastAPI,
    application: ApplicationService,
    *,
    m8_principal_resolver: M8ProductPrincipalResolver,
    m9_principal_resolver: M9ProductPrincipalResolver,
) -> FastAPI:
    """Register immutable exact-ID product reads; no alias/latest resolution exists."""

    @app.get(
        "/api/v1/products/p1/releases/{release_id}",
        operation_id="getProductV1P1Release",
        response_model=ProductV1Envelope,
    )
    def p1_release(release_id: UUID) -> ProductV1Envelope | JSONResponse:
        exact = str(release_id)
        try:
            payload = application.m1_release(exact)
        except (LookupError, RuntimeError, ValueError, PermissionError) as exc:
            return _error(exc)
        return _envelope(
            phase="P1",
            product_kind="P1_SESSION_RELEASE",
            exact_ids={"release_id": exact},
            payload=payload,
        )

    @app.get(
        "/api/v1/products/p2/releases/{p2_release_id}/estimates/{estimate_id}",
        operation_id="getProductV1P2Estimate",
        response_model=ProductV1Envelope,
    )
    def p2_estimate(
        p2_release_id: UUID,
        estimate_id: UUID,
    ) -> ProductV1Envelope | JSONResponse:
        release = str(p2_release_id)
        estimate = str(estimate_id)
        try:
            payload = application.m6_p2_comparison(
                M6P2ComparisonQuery(
                    p2_release_id=release,
                    estimate_id=estimate,
                )
            )
        except (LookupError, RuntimeError, ValueError, PermissionError) as exc:
            return _error(exc)
        return _envelope(
            phase="P2",
            product_kind="P2_ADJUSTED_ESTIMATE",
            exact_ids={
                "p2_release_id": release,
                "estimate_id": estimate,
            },
            payload=payload,
        )

    @app.get(
        "/api/v1/products/p3/twins/{twin_revision_id}",
        operation_id="getProductV1P3Twin",
        response_model=ProductV1Envelope,
    )
    def p3_twin(twin_revision_id: UUID) -> ProductV1Envelope | JSONResponse:
        twin = str(twin_revision_id)
        try:
            payload = application.m7_p3_twin(
                M7TwinQuery(twin_revision_id=twin)
            )
        except (LookupError, RuntimeError, ValueError, PermissionError) as exc:
            return _error(exc)
        return _envelope(
            phase="P3",
            product_kind="P3_TWIN_REVISION",
            exact_ids={"twin_revision_id": twin},
            payload=payload,
        )

    @app.get(
        "/api/v1/products/p3/twins/{twin_revision_id}/estimates/{estimate_id}",
        operation_id="getProductV1P3Estimate",
        response_model=ProductV1Envelope,
    )
    def p3_estimate(
        twin_revision_id: UUID,
        estimate_id: UUID,
    ) -> ProductV1Envelope | JSONResponse:
        twin = str(twin_revision_id)
        estimate = str(estimate_id)
        try:
            payload = application.m7_p3_estimate(
                M7EstimateQuery(
                    twin_revision_id=twin,
                    estimate_id=estimate,
                )
            )
        except (LookupError, RuntimeError, ValueError, PermissionError) as exc:
            return _error(exc)
        return _envelope(
            phase="P3",
            product_kind="P3_CAPABILITY_ESTIMATE",
            exact_ids={
                "twin_revision_id": twin,
                "estimate_id": estimate,
            },
            payload=payload,
        )

    @app.get(
        "/api/v1/products/p4/assessments/{actor_assessment_id}",
        operation_id="getProductV1P4Assessment",
        response_model=ProductV1Envelope,
    )
    def p4_assessment(
        actor_assessment_id: UUID,
        request: Request,
    ) -> ProductV1Envelope | JSONResponse:
        assessment = str(actor_assessment_id)
        try:
            payload = application.m8_p4(
                M8P4Query(
                    actor_assessment_id=assessment,
                    viewer=_m8_principal(m8_principal_resolver, request),
                )
            )
        except (LookupError, RuntimeError, ValueError, PermissionError) as exc:
            return _error(exc)
        return _envelope(
            phase="P4",
            product_kind="P4_ACTOR_ASSESSMENT",
            exact_ids={"actor_assessment_id": assessment},
            payload=payload,
        )

    @app.get(
        "/api/v1/products/p5/assessments/{mission_assessment_id}",
        operation_id="getProductV1P5Assessment",
        response_model=ProductV1Envelope,
    )
    def p5_assessment(
        mission_assessment_id: UUID,
        request: Request,
    ) -> ProductV1Envelope | JSONResponse:
        assessment = str(mission_assessment_id)
        try:
            payload = application.m8_p5(
                M8P5Query(
                    mission_assessment_id=assessment,
                    viewer=_m8_principal(m8_principal_resolver, request),
                )
            )
        except (LookupError, RuntimeError, ValueError, PermissionError) as exc:
            return _error(exc)
        return _envelope(
            phase="P5",
            product_kind="P5_MISSION_ASSESSMENT",
            exact_ids={"mission_assessment_id": assessment},
            payload=payload,
        )

    @app.get(
        "/api/v1/products/p6/models/{capability_model_id}",
        operation_id="getProductV1P6Model",
        response_model=ProductV1Envelope,
    )
    def p6_model(
        capability_model_id: UUID,
        request: Request,
    ) -> ProductV1Envelope | JSONResponse:
        model_id = str(capability_model_id)
        try:
            payload = application.m9_model(
                M9ExactQuery(
                    object_id=model_id,
                    viewer=_m9_principal(m9_principal_resolver, request),
                )
            )
        except (LookupError, RuntimeError, ValueError, PermissionError) as exc:
            return _error(exc)
        return _envelope(
            phase="P6",
            product_kind="P6_CAPABILITY_MODEL",
            exact_ids={"capability_model_id": model_id},
            payload=payload,
        )

    @app.get(
        "/api/v1/products/p6/forecasts/{forecast_result_id}",
        operation_id="getProductV1P6Forecast",
        response_model=ProductV1Envelope,
    )
    def p6_forecast(
        forecast_result_id: UUID,
        request: Request,
    ) -> ProductV1Envelope | JSONResponse:
        result_id = str(forecast_result_id)
        try:
            payload = application.m9_forecast(
                M9ExactQuery(
                    object_id=result_id,
                    viewer=_m9_principal(m9_principal_resolver, request),
                )
            )
        except (LookupError, RuntimeError, ValueError, PermissionError) as exc:
            return _error(exc)
        return _envelope(
            phase="P6",
            product_kind="P6_FORECAST",
            exact_ids={"forecast_result_id": result_id},
            payload=payload,
        )

    @app.get(
        "/api/v1/products/p6/counterfactuals/{counterfactual_run_id}",
        operation_id="getProductV1P6Counterfactual",
        response_model=ProductV1Envelope,
    )
    def p6_counterfactual(
        counterfactual_run_id: UUID,
        request: Request,
    ) -> ProductV1Envelope | JSONResponse:
        run_id = str(counterfactual_run_id)
        try:
            payload = application.m9_counterfactual(
                M9ExactQuery(
                    object_id=run_id,
                    viewer=_m9_principal(m9_principal_resolver, request),
                )
            )
        except (LookupError, RuntimeError, ValueError, PermissionError) as exc:
            return _error(exc)
        return _envelope(
            phase="P6",
            product_kind="P6_COUNTERFACTUAL",
            exact_ids={"counterfactual_run_id": run_id},
            payload=payload,
        )

    @app.get(
        "/api/v1/products/p6/recommendations/{recommendation_id}",
        operation_id="getProductV1P6Recommendation",
        response_model=ProductV1Envelope,
    )
    def p6_recommendation(
        recommendation_id: UUID,
        request: Request,
    ) -> ProductV1Envelope | JSONResponse:
        exact = str(recommendation_id)
        try:
            payload = application.m9_recommendation(
                M9ExactQuery(
                    object_id=exact,
                    viewer=_m9_principal(m9_principal_resolver, request),
                )
            )
        except (LookupError, RuntimeError, ValueError, PermissionError) as exc:
            return _error(exc)
        return _envelope(
            phase="P6",
            product_kind="P6_RECOMMENDATION",
            exact_ids={"recommendation_id": exact},
            payload=payload,
        )

    return app
