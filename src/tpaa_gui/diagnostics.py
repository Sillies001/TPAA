"""Read-only Desktop diagnostics projection for M0-GUI-003.

The view model deliberately contains only non-secret runtime identity/readiness data.
It never recomputes READY semantics and never carries the Desktop bearer token.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class DiagnosticsIdentity:
    """Minimum identity dimensions required by the M0 diagnostics view."""

    product_build_version: str
    core_baseline: str
    p1_metric_catalog_version: str
    db_schema_version: str


@dataclass(frozen=True)
class DiagnosticsSnapshot:
    """Sanitized diagnostics snapshot rendered by the Desktop GUI."""

    readiness: str
    backend_state: str
    mismatches: tuple[str, ...]
    failure_code: str | None
    expected: DiagnosticsIdentity | None
    observed: DiagnosticsIdentity | None

    def with_lifecycle(
        self,
        *,
        backend_state: str,
        backend_ready: bool,
        failure_code: str | None,
    ) -> DiagnosticsSnapshot:
        """Overlay current child lifecycle without re-evaluating baseline identity."""

        effective_readiness = "READY" if backend_ready and self.readiness == "READY" else "NOT_READY"
        return replace(
            self,
            readiness=effective_readiness,
            backend_state=backend_state,
            failure_code=failure_code,
        )


EMPTY_DIAGNOSTICS = DiagnosticsSnapshot(
    readiness="NOT_READY",
    backend_state="STOPPED",
    mismatches=(),
    failure_code=None,
    expected=None,
    observed=None,
)


def _identity(payload: Mapping[str, Any] | None) -> DiagnosticsIdentity | None:
    if payload is None:
        return None
    keys = (
        "product_build_version",
        "core_baseline",
        "p1_metric_catalog_version",
        "db_schema_version",
    )
    values: dict[str, str] = {}
    for key in keys:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            return None
        values[key] = value
    return DiagnosticsIdentity(**values)


def snapshot_from_http(
    readiness_payload: Mapping[str, Any],
    version_payload: Mapping[str, Any],
    *,
    backend_state: str,
) -> DiagnosticsSnapshot:
    """Project authenticated backend payloads into a stable GUI-only model."""

    readiness = readiness_payload.get("status")
    mismatches = readiness_payload.get("mismatches", [])
    expected = version_payload.get("expected")
    observed = version_payload.get("observed")

    return DiagnosticsSnapshot(
        readiness=readiness if isinstance(readiness, str) else "NOT_READY",
        backend_state=backend_state,
        mismatches=tuple(item for item in mismatches if isinstance(item, str))
        if isinstance(mismatches, list)
        else (),
        failure_code=None,
        expected=_identity(expected if isinstance(expected, Mapping) else None),
        observed=_identity(observed if isinstance(observed, Mapping) else None),
    )


def diagnostics_lines(snapshot: DiagnosticsSnapshot) -> tuple[tuple[str, str, str], ...]:
    """Return stable label object names and user-visible diagnostics text."""

    expected = snapshot.expected
    observed = snapshot.observed

    def pair(label: str, expected_value: str | None, observed_value: str | None) -> str:
        return f"{label}: expected={expected_value or 'unavailable'} observed={observed_value or 'unavailable'}"

    mismatches = ", ".join(snapshot.mismatches) if snapshot.mismatches else "NONE"
    failure = snapshot.failure_code or "NONE"
    return (
        ("tpaaDiagnosticsReadiness", "Readiness", f"Readiness: {snapshot.readiness}"),
        ("tpaaDiagnosticsBackendState", "Backend", f"Backend state: {snapshot.backend_state}"),
        ("tpaaDiagnosticsFailure", "Failure", f"Lifecycle failure: {failure}"),
        ("tpaaDiagnosticsMismatches", "Mismatches", f"Mismatches: {mismatches}"),
        (
            "tpaaDiagnosticsBuild",
            "Build",
            pair(
                "Build",
                None if expected is None else expected.product_build_version,
                None if observed is None else observed.product_build_version,
            ),
        ),
        (
            "tpaaDiagnosticsCore",
            "Core",
            pair(
                "Core baseline",
                None if expected is None else expected.core_baseline,
                None if observed is None else observed.core_baseline,
            ),
        ),
        (
            "tpaaDiagnosticsCatalog",
            "Catalog",
            pair(
                "P1 Catalog",
                None if expected is None else expected.p1_metric_catalog_version,
                None if observed is None else observed.p1_metric_catalog_version,
            ),
        ),
        (
            "tpaaDiagnosticsSchema",
            "Schema",
            pair(
                "DB schema",
                None if expected is None else expected.db_schema_version,
                None if observed is None else observed.db_schema_version,
            ),
        ),
    )
