from __future__ import annotations

from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tpaa_api.runtime import register_product_runtime_routes
from tpaa_application import ApplicationService
from tpaa_runtime import CachedOperationalMetrics, render_prometheus_metrics


def _payload() -> dict[str, object]:
    return {
        "operational_metrics_schema": "TPAA_OPERATIONAL_METRICS_V1",
        "job_status_counts": {"RUNNING": 2, "FAILED": 1},
        "job_active_count": 2,
        "job_failure_code_counts": {
            "ADAPTER_FAILURE": 1,
            'password="must-not-escape"': 5,
        },
        "adapter_error_count": 1,
        "access_denial_count": 3,
        "object_count": 4,
        "object_bytes": 128,
        "database_metric_query_latency_us": 10,
        "object_scan_latency_us": 11,
        "backup_status": {"state": "VERIFIED", "age_seconds": 7},
        "database_private_path": "must-never-be-projected",
    }


class _OperationalApplication:
    def operational_status(self) -> dict[str, object]:
        return _payload()


class _CountingCollector:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self) -> dict[str, object]:
        self.calls += 1
        return {"nested": {"count": self.calls}}


def test_prometheus_projection_is_bounded_and_secret_safe() -> None:
    rendered = render_prometheus_metrics(_payload())

    assert 'tpaa_job_status_current{status="FAILED"} 1' in rendered
    assert 'tpaa_job_failure_reason_current{reason_code="ADAPTER_FAILURE"} 1' in rendered
    assert 'reason_code="UNSAFE_OR_UNKNOWN"} 5' in rendered
    assert 'tpaa_backup_status{state="VERIFIED"} 1' in rendered
    assert "must-not-escape" not in rendered
    assert "must-never-be-projected" not in rendered


def test_prometheus_endpoint_returns_standard_text_media_type() -> None:
    app = register_product_runtime_routes(
        FastAPI(),
        cast(ApplicationService, _OperationalApplication()),
    )

    response = TestClient(app).get("/runtime/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain;")
    assert "version=0.0.4" in response.headers["content-type"]
    assert "tpaa_object_inventory_bytes 128.0" in response.text


def test_operational_metrics_cache_isolated_snapshot() -> None:
    collector = _CountingCollector()
    cached = CachedOperationalMetrics(collector, ttl_seconds=60)

    first = cached.execute()
    cast(dict[str, object], first["nested"])["count"] = 999
    second = cached.execute()

    assert collector.calls == 1
    assert second == {"nested": {"count": 1}}
