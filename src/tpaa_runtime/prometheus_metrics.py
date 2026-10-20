"""Bounded Prometheus text projection for secret-safe operational metrics."""

from __future__ import annotations

import re
from collections.abc import Mapping

_SAFE_LABEL = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


def _number(value: object, *, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"operational metric {field} must be numeric")
    return value


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"operational metric {field} must be a mapping")
    return value


def _label(value: object) -> str:
    text = str(value)
    if _SAFE_LABEL.fullmatch(text) is None:
        return "UNSAFE_OR_UNKNOWN"
    return text


def _metric(name: str, value: object, labels: Mapping[str, object] | None = None) -> str:
    suffix = ""
    if labels:
        encoded = ",".join(f'{key}="{_label(labels[key])}"' for key in sorted(labels))
        suffix = "{" + encoded + "}"
    return f"{name}{suffix} {_number(value, field=name)}"


def render_prometheus_metrics(payload: Mapping[str, object]) -> str:
    """Render only the governed, bounded metric subset; ignore all identities."""

    if payload.get("operational_metrics_schema") != "TPAA_OPERATIONAL_METRICS_V1":
        raise ValueError("operational metrics schema mismatch")
    lines = [
        "# HELP tpaa_job_status_current Durable jobs by bounded lifecycle state.",
        "# TYPE tpaa_job_status_current gauge",
    ]
    statuses = _mapping(payload.get("job_status_counts"), field="job_status_counts")
    for state in sorted(statuses):
        lines.append(
            _metric(
                "tpaa_job_status_current",
                statuses[state],
                {"status": state},
            )
        )
    lines.extend(
        (
            "# HELP tpaa_job_active Current active durable jobs.",
            "# TYPE tpaa_job_active gauge",
            _metric("tpaa_job_active", payload.get("job_active_count")),
            "# HELP tpaa_job_failure_reason_current Failed jobs by bounded reason code.",
            "# TYPE tpaa_job_failure_reason_current gauge",
        )
    )
    failures = _mapping(
        payload.get("job_failure_code_counts"),
        field="job_failure_code_counts",
    )
    for reason in sorted(failures):
        lines.append(
            _metric(
                "tpaa_job_failure_reason_current",
                failures[reason],
                {"reason_code": reason},
            )
        )
    scalar_metrics = (
        ("tpaa_adapter_errors", "adapter_error_count", "Current adapter errors.", 1.0),
        ("tpaa_access_denials", "access_denial_count", "Current access denials.", 1.0),
        ("tpaa_object_inventory_objects", "object_count", "Governed object inventory size.", 1.0),
        ("tpaa_object_inventory_bytes", "object_bytes", "Governed object inventory bytes.", 1.0),
        (
            "tpaa_database_query_latency_seconds",
            "database_metric_query_latency_us",
            "Operational database query latency in seconds.",
            1_000_000.0,
        ),
        (
            "tpaa_object_scan_latency_seconds",
            "object_scan_latency_us",
            "Governed object scan latency in seconds.",
            1_000_000.0,
        ),
        ("tpaa_storage_capacity_bytes", "storage_capacity_bytes", "Storage capacity bytes.", 1.0),
        ("tpaa_storage_used_bytes", "storage_used_bytes", "Storage used bytes.", 1.0),
        ("tpaa_storage_free_bytes", "storage_free_bytes", "Storage free bytes.", 1.0),
    )
    for metric_name, field, help_text, divisor in scalar_metrics:
        if field in payload:
            lines.extend(
                (
                    f"# HELP {metric_name} {help_text}",
                    f"# TYPE {metric_name} gauge",
                    _metric(
                        metric_name,
                        _number(payload[field], field=field) / divisor,
                    ),
                )
            )
    backup = _mapping(payload.get("backup_status"), field="backup_status")
    lines.extend(
        (
            "# HELP tpaa_backup_status Current governed backup state.",
            "# TYPE tpaa_backup_status gauge",
            _metric(
                "tpaa_backup_status",
                1,
                {"state": backup.get("state", "UNKNOWN")},
            ),
        )
    )
    if "age_seconds" in backup:
        lines.extend(
            (
                "# HELP tpaa_backup_age_seconds Age of the verified backup in seconds.",
                "# TYPE tpaa_backup_age_seconds gauge",
                _metric("tpaa_backup_age_seconds", backup["age_seconds"]),
            )
        )
    return "\n".join(lines) + "\n"


__all__ = ["render_prometheus_metrics"]
