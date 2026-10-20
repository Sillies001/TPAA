from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from tpaa_runtime import render_prometheus_metrics


def test_prometheus_image_accepts_runtime_exposition() -> None:
    image = os.environ.get("TPAA_TEST_PROMETHEUS_IMAGE")
    if not image:
        pytest.skip("TPAA_TEST_PROMETHEUS_IMAGE is not configured")
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("docker is unavailable")
    payload = {
        "operational_metrics_schema": "TPAA_OPERATIONAL_METRICS_V1",
        "job_status_counts": {"SUBMITTED": 0, "RUNNING": 1, "FAILED": 0},
        "job_active_count": 1,
        "job_failure_code_counts": {},
        "adapter_error_count": 0,
        "access_denial_count": 0,
        "object_count": 2,
        "object_bytes": 64,
        "database_metric_query_latency_us": 8,
        "object_scan_latency_us": 9,
        "backup_status": {"state": "EXTERNAL_GOVERNANCE_REQUIRED"},
    }

    completed = subprocess.run(
        [
            docker,
            "run",
            "--rm",
            "-i",
            "--entrypoint",
            "/bin/promtool",
            image,
            "check",
            "metrics",
        ],
        input=render_prometheus_metrics(payload).encode("utf-8"),
        capture_output=True,
        check=False,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
