"""Transport-neutral Application result models for M0-API-001."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StorageBaselineStatus:
    """Persisted schema/baseline provenance projected into the Application layer."""

    engine_profile: str
    schema_version: str
    core_baseline: str
    authority_artifact_id: str
    authority_sha256: str
    baseline_lock_sha256: str
    physical_schema_sha256: str
