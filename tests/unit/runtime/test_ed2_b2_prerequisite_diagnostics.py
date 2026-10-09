"""Failure diagnostics preserve the governed prerequisite identity gate."""

from __future__ import annotations

from tpaa_runtime.durable_jobs import (
    ProductionJobExecutionError,
    _governed_job_failure_detail,
)


def test_ed2_b2_prerequisite_failure_reports_table_and_columns_not_values() -> None:
    failure = ProductionJobExecutionError(
        "ED2_P1_PREREQUISITE_IDENTITY_DRIFT",
        "metric.metric_definition:metric_definition_id=123:"
        "fields=capability_dimension,spec_hash",
    )
    assert _governed_job_failure_detail(failure) == (
        "ProductionJobExecutionError:metric.metric_definition:"
        "fields=capability_dimension,spec_hash"
    )
    assert "123" not in _governed_job_failure_detail(failure)


def test_ed2_b2_unrelated_failures_retain_exception_only() -> None:
    assert _governed_job_failure_detail(
        ProductionJobExecutionError("OTHER", "sensitive:payload")
    ) == "ProductionJobExecutionError"
