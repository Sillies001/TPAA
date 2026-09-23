#!/usr/bin/env python3
"""Disposable M0-API-002 HTTP smoke for health/readiness/version endpoints."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from tpaa_api import create_app  # noqa: E402
from tpaa_application import ApplicationService, GetRuntimeBaselineStatus  # noqa: E402
from tpaa_canonical.runtime_handshake import (  # noqa: E402
    RuntimeBaselineIdentity,
    evaluate_runtime_baseline_handshake,
)


class _UnusedStorageUseCase:
    def execute(self) -> object:
        raise RuntimeError("storage baseline status is not part of M0-API-002 smoke")


def _identity() -> RuntimeBaselineIdentity:
    return RuntimeBaselineIdentity(
        product_build_version="m0-api-002-smoke",
        core_baseline="CB-1.4.0",
        baseline_lock_sha256="smoke-lock",
        db_schema_version="1.6.0",
        core_authority_artifact_id="CORE_LOGICAL_MODEL",
        core_authority_sha256="smoke-core",
        p1_metric_catalog_version="P1-smoke",
        p1_metric_catalog_sha256="smoke-catalog",
        dto_authority_sha256="smoke-dto",
    )


def _client(*, ready: bool) -> TestClient:
    expected = _identity()
    observed = expected if ready else replace(expected, db_schema_version="mismatch")
    runtime = GetRuntimeBaselineStatus(
        lambda: evaluate_runtime_baseline_handshake(expected=expected, observed=observed)
    )
    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorageUseCase(),  # type: ignore[arg-type]
        get_runtime_baseline_status=runtime,
    )
    return TestClient(create_app(application))


def run_smoke() -> dict[str, object]:
    with _client(ready=True) as ready_client:
        health = ready_client.get("/health")
        readiness = ready_client.get("/readiness")
        version = ready_client.get("/version")
    with _client(ready=False) as not_ready_client:
        blocked = not_ready_client.get("/readiness")

    checks = {
        "health": "PASS" if health.status_code == 200 and health.json() == {"status": "UP"} else "FAIL",
        "readiness_ready": "PASS" if readiness.status_code == 200 and readiness.json().get("ready") is True else "FAIL",
        "readiness_not_ready": "PASS" if blocked.status_code == 503 and blocked.json().get("ready") is False else "FAIL",
        "version": "PASS" if version.status_code == 200 and "expected" in version.json() and "observed" in version.json() else "FAIL",
    }
    if any(value != "PASS" for value in checks.values()):
        raise RuntimeError(f"M0-API-002 smoke failed: {checks}")
    return {"m0_api_002": checks, "status": "PASS"}


def main() -> int:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
