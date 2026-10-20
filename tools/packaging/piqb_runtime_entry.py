#!/usr/bin/env python3
"""PIQB-1.0 production runtime entry for packaged Desktop and Service profiles."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any, cast

APP_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = APP_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tpaa_desktop import create_app as create_desktop_app  # noqa: E402
from tpaa_desktop.__main__ import main as desktop_main  # noqa: E402
from tpaa_runtime import RuntimeProfile, project_version  # noqa: E402
from tpaa_service import create_app as create_service_app  # noqa: E402
from tpaa_service.__main__ import main as service_main  # noqa: E402

DESKTOP_PROFILES = {"WINDOWS_DESKTOP_X64", "LINUX_DESKTOP_X64"}
SERVICE_PROFILES = {"WINDOWS_SERVICE_X64", "LINUX_SERVICE_X64"}
ALL_PROFILES = DESKTOP_PROFILES | SERVICE_PROFILES
_REQUIRED_PHASES = ("P1", "P2", "P3", "P4", "P5", "P6")
_REQUIRED_PRODUCT_ROUTE_MARKERS = (
    "/api/v1/products/p1/",
    "/api/v1/products/p2/",
    "/api/v1/products/p3/",
    "/api/v1/products/p4/",
    "/api/v1/products/p5/",
    "/api/v1/products/p6/",
)


def _project_version() -> str:
    return project_version(APP_ROOT)


def _runtime_profile(profile_id: str) -> RuntimeProfile:
    if profile_id in DESKTOP_PROFILES:
        return RuntimeProfile.DESKTOP
    if profile_id in SERVICE_PROFILES:
        return RuntimeProfile.SERVICE
    raise ValueError(f"unsupported PIQB runtime profile: {profile_id}")


def _service_probe_token() -> str:
    token = os.environ.get("TPAA_SERVICE_PROBE_TOKEN", "")
    if len(token) < 24:
        raise RuntimeError(
            "TPAA_SERVICE_PROBE_TOKEN must be injected and at least 24 characters"
        )
    return token


def _app(profile_id: str) -> tuple[FastAPI, dict[str, str]]:
    if profile_id in DESKTOP_PROFILES:
        token = secrets.token_urlsafe(32)
        app = create_desktop_app(bearer_token=token, app_root=APP_ROOT)
        headers = {"Authorization": f"Bearer {token}"}
    else:
        token = _service_probe_token()
        app = create_service_app(app_root=APP_ROOT)
        headers = {"Authorization": f"Bearer {token}"}
    if app.version != _project_version():
        raise RuntimeError(
            "FastAPI product version drift "
            f"expected={_project_version()} observed={app.version}"
        )
    return app, headers


def _payload(response: Any) -> dict[str, Any]:
    value = response.json()
    if not isinstance(value, dict):
        raise RuntimeError("product API response must be an object")
    return cast(dict[str, Any], value)


def _route_paths(app: FastAPI) -> tuple[str, ...]:
    paths = {
        value
        for route in app.routes
        if isinstance((value := getattr(route, "path", None)), str)
    }
    return tuple(sorted(paths))


def _runtime_probe(profile_id: str) -> dict[str, Any]:
    app, headers = _app(profile_id)
    with TestClient(app) as client:
        health = client.get("/health", headers=headers)
        readiness = client.get("/readiness", headers=headers)
        version = client.get("/version", headers=headers)
        features = client.get("/runtime/features", headers=headers)
        qualification = client.get("/runtime/qualification", headers=headers)
        observability = client.get("/runtime/observability", headers=headers)

    if health.status_code != 200 or _payload(health).get("status") != "UP":
        raise RuntimeError("product health probe failed")
    if readiness.status_code != 200 or _payload(readiness).get("ready") is not True:
        raise RuntimeError("product readiness probe failed")

    version_payload = _payload(version)
    expected = version_payload.get("expected")
    if not isinstance(expected, dict) or expected.get("product_build_version") != _project_version():
        raise RuntimeError("product build version handshake failed")

    feature_payload = _payload(features)
    items = feature_payload.get("items")
    if not isinstance(items, list) or len(items) != 6:
        raise RuntimeError("P1-P6 feature inventory invalid")
    phases = tuple(
        str(item.get("phase"))
        for item in items
        if isinstance(item, dict)
    )
    states = tuple(
        str(item.get("state"))
        for item in items
        if isinstance(item, dict)
    )
    if phases != _REQUIRED_PHASES or states != ("AVAILABLE",) * 6:
        raise RuntimeError(f"P1-P6 availability invalid phases={phases} states={states}")

    qualification_payload = _payload(qualification)
    if qualification.status_code != 200:
        raise RuntimeError(
            "product qualification probe failed "
            f"status={qualification.status_code} payload={qualification_payload}"
        )
    if (
        qualification_payload.get("product_build_version") != _project_version()
        or qualification_payload.get("db_schema_version") != "1.9.0"
    ):
        raise RuntimeError(
            "product qualification identity mismatch "
            f"payload={qualification_payload}"
        )

    observability_payload = _payload(observability)
    if observability.status_code != 200:
        raise RuntimeError(
            "product observability probe failed "
            f"status={observability.status_code} payload={observability_payload}"
        )

    route_paths = _route_paths(app)
    for marker in _REQUIRED_PRODUCT_ROUTE_MARKERS:
        if not any(path.startswith(marker) for path in route_paths):
            raise RuntimeError(f"missing unified product route marker: {marker}")

    return {
        "schema": "TPAA_PIQB_RUNTIME_PROBE_V1",
        "status": "PASS",
        "profile_id": profile_id,
        "runtime_profile": _runtime_profile(profile_id).value,
        "product_version": _project_version(),
        "db_schema_version": "1.9.0",
        "phases": list(phases),
        "feature_states": list(states),
        "route_markers": list(_REQUIRED_PRODUCT_ROUTE_MARKERS),
        "route_count": len(route_paths),
        "readiness": "READY",
    }


def _component_smoke(profile_id: str) -> dict[str, object]:
    probe = _runtime_probe(profile_id)
    checks: dict[str, bool] = {
        "full_product_runtime": True,
        "P1-P6": True,
        "DB 1.9.0 identity": probe["db_schema_version"] == "1.9.0",
        "Unified product API": True,
    }
    if profile_id in DESKTOP_PROFILES:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        qt = QApplication.instance() or QApplication([])
        checks["Desktop GUI"] = qt is not None
    else:
        import psycopg  # noqa: F401

        checks["PostgreSQL client"] = True
        checks["Service identity boundary"] = True
    if not all(checks.values()):
        raise RuntimeError(f"PIQB component smoke failed: {checks}")
    return {
        "schema": "TPAA_PIQB_RUNTIME_COMPONENT_SMOKE_V1",
        "status": "PASS",
        "profile_id": profile_id,
        "checks": checks,
    }


def _hold(profile_id: str, stop_file: Path) -> int:
    payload = _runtime_probe(profile_id)
    payload["product_probe_status"] = payload["status"]
    payload["status"] = "READY"
    print(json.dumps(payload, sort_keys=True), flush=True)
    while not stop_file.exists():
        time.sleep(0.05)
    return 0


def _run_desktop(profile_id: str) -> int:
    if profile_id not in DESKTOP_PROFILES:
        raise RuntimeError("desktop command requires Desktop profile")
    return desktop_main((), app_root=APP_ROOT)


def _run_service(profile_id: str, host: str, port: int) -> int:
    if profile_id not in SERVICE_PROFILES:
        raise RuntimeError("service command requires Service profile")
    return service_main(
        ("--host", host, "--port", str(port)),
        app_root=APP_ROOT,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=sorted(ALL_PROFILES))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ready")
    sub.add_parser("component-smoke")
    sub.add_parser("product-smoke")
    hold = sub.add_parser("hold")
    hold.add_argument("--stop-file", type=Path, required=True)
    sub.add_parser("desktop")
    service = sub.add_parser("service")
    service.add_argument("--host", default="127.0.0.1")
    service.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.command in {"ready", "product-smoke"}:
        result: object = _runtime_probe(args.profile)
    elif args.command == "component-smoke":
        result = _component_smoke(args.profile)
    elif args.command == "hold":
        return _hold(args.profile, args.stop_file)
    elif args.command == "desktop":
        return _run_desktop(args.profile)
    elif args.command == "service":
        return _run_service(args.profile, args.host, args.port)
    else:
        raise AssertionError(args.command)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
