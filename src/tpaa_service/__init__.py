"""Public TPAA Service application factory."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from fastapi import FastAPI

from tpaa_runtime import (
    ProductionRuntime,
    build_service_production_runtime,
    create_production_service_app,
    project_version,
    resolve_authority_root,
    service_production_config_from_environment,
)


def create_app(
    *,
    environ: Mapping[str, str] | None = None,
    app_root: Path | None = None,
) -> FastAPI:
    """Create only the durable DB 1.9 Service graph."""

    return create_production_service_app(
        create_runtime(environ=environ, app_root=app_root)
    )


def create_runtime(
    *,
    environ: Mapping[str, str] | None = None,
    app_root: Path | None = None,
) -> ProductionRuntime:
    """Validate configuration and compose the durable Service runtime."""

    config = service_production_config_from_environment(
        product_build_version=project_version(app_root),
        authority_root=resolve_authority_root(
            anchor=app_root or Path(__file__),
            environ=environ,
        ),
        environ=environ,
    )
    return build_service_production_runtime(config)


def service_preflight(
    *,
    environ: Mapping[str, str] | None = None,
    app_root: Path | None = None,
) -> dict[str, object]:
    """Return a secret-free live dependency/readiness result."""

    runtime = create_runtime(environ=environ, app_root=app_root)
    storage = runtime.application.storage_baseline_status()
    readiness = runtime.application.runtime_baseline_status()
    return {
        "schema": "TPAA_SERVICE_PREFLIGHT_V1",
        "status": "READY" if readiness.ready else "NOT_READY",
        "profile": runtime.config.profile.value,
        "product_build_version": runtime.config.product_build_version,
        "db_schema_version": storage.schema_version,
        "core_baseline": storage.core_baseline,
        "identity_mode": (
            "OIDC_MTLS"
            if runtime.config.service_identity is not None
            else "LEGACY_STATIC_FINGERPRINT"
        ),
        "principal_count": len(runtime.config.service_principals),
        "readiness": readiness.readiness,
        "mismatches": list(readiness.mismatches),
    }


__all__ = ["create_app", "create_runtime", "project_version", "service_preflight"]
