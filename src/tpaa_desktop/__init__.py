"""Public TPAA Desktop production application factory."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from fastapi import FastAPI

from tpaa_runtime import (
    ProductionRuntime,
    build_desktop_production_runtime,
    create_production_desktop_app,
    default_desktop_data_root,
    prepare_desktop_production_config,
    project_version,
    resolve_authority_root,
)


def create_runtime(
    *,
    product_build_version: str | None = None,
    data_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
    app_root: Path | None = None,
) -> ProductionRuntime:
    """Validate configuration and compose the durable Desktop runtime."""

    authority_root = resolve_authority_root(
        anchor=app_root or Path(__file__),
        environ=environ,
    )
    configured_data_root = data_root or default_desktop_data_root(environ=environ)
    config = prepare_desktop_production_config(
        product_build_version=product_build_version or project_version(app_root),
        authority_root=authority_root,
        data_root=configured_data_root,
    )
    return build_desktop_production_runtime(config)


def create_app(
    *,
    bearer_token: str,
    product_build_version: str | None = None,
    data_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
    app_root: Path | None = None,
) -> FastAPI:
    """Create the authenticated loopback Desktop API over durable storage."""

    runtime = create_runtime(
        product_build_version=product_build_version,
        data_root=data_root,
        environ=environ,
        app_root=app_root,
    )
    return create_production_desktop_app(runtime, bearer_token=bearer_token)


__all__ = ["create_app", "create_runtime"]
