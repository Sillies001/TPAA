"""PRCB C4 immutable product discovery/navigation API."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, status

from tpaa_application import ApplicationService


def register_product_discovery_routes(
    app: FastAPI,
    application: ApplicationService,
) -> None:
    @app.get(
        "/api/v1/discovery/sessions",
        operation_id="discoverProductSessions",
    )
    def sessions() -> dict[str, object]:
        return application.discover_sessions()

    @app.get(
        "/api/v1/discovery/sessions/{session_id}/releases",
        operation_id="discoverProductSessionReleases",
    )
    def releases(session_id: str) -> dict[str, object]:
        try:
            return application.discover_releases(session_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    @app.get(
        "/api/v1/discovery/releases/{release_id}/presentation",
        operation_id="discoverExactReleasePresentation",
    )
    def presentation(release_id: str) -> dict[str, object]:
        try:
            return application.discover_release_presentation(release_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    @app.get(
        "/api/v1/discovery/products/{kind}",
        operation_id="discoverExactProducts",
    )
    def products(kind: str) -> dict[str, object]:
        try:
            return application.discover_products(kind)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
