from __future__ import annotations

from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tpaa_api.runtime import register_product_runtime_routes
from tpaa_application import ApplicationService


class _ExplodingOperationalStatus:
    def operational_status(self) -> dict[str, object]:
        raise RuntimeError("password=do-not-return host=private-database")


def test_runtime_observability_redacts_internal_exception_detail() -> None:
    app = register_product_runtime_routes(
        FastAPI(),
        cast(ApplicationService, _ExplodingOperationalStatus()),
    )
    response = TestClient(app).get("/runtime/observability")
    assert response.status_code == 503
    assert response.json() == {
        "outcome": "SYSTEM_ERROR",
        "error": {
            "code": "OPERATIONAL_STATUS_NOT_CONFIGURED",
            "detail": "operational status unavailable",
        },
    }
    assert "password" not in response.text
    assert "private-database" not in response.text

    metrics = TestClient(app).get("/runtime/metrics")
    assert metrics.status_code == 503
    assert metrics.text == "# TPAA operational metrics unavailable\n"
    assert "password" not in metrics.text
    assert "private-database" not in metrics.text
