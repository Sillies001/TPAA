from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace

import pytest

from tpaa_assessment import (
    P2AdjustedCapabilityEstimate,
    P2AttributionRunProduct,
    P2ExecutionProfile,
)
from tpaa_storage.p2_domain_repository import (
    P2DomainPersistenceError,
    SQLiteP2DomainRepository,
)


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE "metric.capability_observation" (
            observation_id TEXT PRIMARY KEY,
            release_id TEXT NOT NULL
        );
        CREATE TABLE "assessment.attribution_run" (
            attribution_run_id TEXT PRIMARY KEY,
            attribution_spec_id TEXT NOT NULL,
            attribution_spec_version TEXT NOT NULL,
            model_plugin TEXT NOT NULL,
            model_plugin_version TEXT NOT NULL,
            training_dataset_snapshot_id TEXT NOT NULL,
            reference_condition_id TEXT NOT NULL,
            status TEXT NOT NULL,
            diagnostics TEXT NOT NULL,
            model_artifact_uri TEXT NULL,
            model_artifact_hash TEXT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            created_by TEXT NULL
        );
        CREATE TABLE "assessment.attribution_run_request_binding" (
            attribution_run_id TEXT PRIMARY KEY,
            run_request_hash TEXT NOT NULL,
            compute_job_id TEXT NULL
        );
        CREATE TABLE "capability.adjusted_capability_estimate" (
            estimate_id TEXT PRIMARY KEY,
            source_observation_id TEXT NOT NULL,
            attribution_run_id TEXT NOT NULL,
            aircraft_id TEXT NOT NULL,
            capability_type TEXT NOT NULL,
            reference_condition_id TEXT NOT NULL,
            adjusted_value REAL NULL,
            unit TEXT NOT NULL,
            uncertainty_lower REAL NULL,
            uncertainty_upper REAL NULL,
            residual REAL NULL,
            factor_effects TEXT NOT NULL,
            claim_level TEXT NOT NULL,
            status TEXT NOT NULL,
            evidence_set_id TEXT NOT NULL,
            estimate_time TEXT NOT NULL,
            created_at TEXT NOT NULL,
            supersedes_estimate_id TEXT NULL
        );
        CREATE TABLE "capability.adjusted_capability_estimate_revision" (
            estimate_id TEXT PRIMARY KEY,
            p2_release_id TEXT NOT NULL,
            reason_codes TEXT NOT NULL
        );
        """
    )
    return connection


def _fixture() -> tuple[P2AttributionRunProduct, P2AdjustedCapabilityEstimate]:
    profile = P2ExecutionProfile.from_canonical()
    observation_id = "92000000-0000-4000-8000-000000000001"
    source_release_id = "92000000-0000-4000-8000-000000000002"
    p2_release_id = "92000000-0000-4000-8000-000000000003"
    run_id = "92000000-0000-4000-8000-000000000004"
    estimate_id = "92000000-0000-4000-8000-000000000005"
    evidence_set_id = "92000000-0000-4000-8000-000000000006"
    reason = "INSUFFICIENT_INDEPENDENT_SUBJECTS"
    request_hash = "a" * 64
    diagnostics = {
        "reason_codes": [reason],
        "run_request_hash": request_hash,
        "uncertainty_method": profile.uncertainty_method,
        "uncertainty_level": profile.uncertainty_level,
        "factor_effect_semantics": profile.factor_effect_semantics,
        "claim_level": profile.claim_level,
    }
    run = P2AttributionRunProduct(
        attribution_run_id=run_id,
        attribution_spec_id=profile.attribution_spec_id,
        attribution_spec_version=profile.attribution_spec_version,
        model_plugin=profile.model_plugin,
        model_plugin_version=profile.model_plugin_version,
        training_dataset_snapshot_id="92000000-0000-4000-8000-000000000007",
        reference_condition_id="92000000-0000-4000-8000-000000000008",
        status="NOT_IDENTIFIABLE",
        diagnostics_json=json.dumps(
            diagnostics,
            sort_keys=True,
            separators=(",", ":"),
        ),
        model_artifact_uri=None,
        model_artifact_hash=None,
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:00Z",
        created_by="PIQB-B2-TEST",
        run_request_hash=request_hash,
    )
    logical = {
        "source_observation_id": observation_id,
        "source_release_id": source_release_id,
        "p2_release_id": p2_release_id,
        "attribution_run_id": run_id,
        "reference_condition_id": run.reference_condition_id,
        "status": "NOT_IDENTIFIABLE",
        "reason_codes": [reason],
        "claim_level": profile.claim_level,
        "evidence_set_id": evidence_set_id,
    }
    estimate = P2AdjustedCapabilityEstimate(
        estimate_id=estimate_id,
        source_observation_id=observation_id,
        source_release_id=source_release_id,
        p2_release_id=p2_release_id,
        attribution_run_id=run_id,
        aircraft_id="92000000-0000-4000-8000-000000000009",
        capability_type="BVR_SENSOR_EMPLOYMENT",
        reference_condition_id=run.reference_condition_id,
        adjusted_value=None,
        unit="score",
        uncertainty_lower=None,
        uncertainty_upper=None,
        uncertainty_method=profile.uncertainty_method,
        uncertainty_level=profile.uncertainty_level,
        residual=None,
        factor_effects=(),
        claim_level=profile.claim_level,
        status="NOT_IDENTIFIABLE",
        reason_codes=(reason,),
        evidence_set_id=evidence_set_id,
        estimate_time="2026-01-01T00:00:00Z",
        created_at="2026-01-01T00:00:00Z",
        supersedes_estimate_id=None,
        logical_hash=_canonical_hash(logical),
    )
    return run, estimate


def test_sqlite_p2_db_1_7_exact_round_trip() -> None:
    connection = _connection()
    run, estimate = _fixture()
    connection.execute(
        'INSERT INTO "metric.capability_observation" '
        "(observation_id, release_id) VALUES (?, ?)",
        (estimate.source_observation_id, estimate.source_release_id),
    )
    repository = SQLiteP2DomainRepository(connection)
    repository.register_attribution_run(run)
    repository.register_adjusted_estimate(estimate)

    assert repository.exact_attribution_run(run.attribution_run_id) == run
    assert repository.exact_adjusted_estimate(estimate.estimate_id) == estimate


def test_sqlite_p2_db_1_7_idempotent_replay_and_conflict_fail_closed() -> None:
    connection = _connection()
    run, estimate = _fixture()
    connection.execute(
        'INSERT INTO "metric.capability_observation" '
        "(observation_id, release_id) VALUES (?, ?)",
        (estimate.source_observation_id, estimate.source_release_id),
    )
    repository = SQLiteP2DomainRepository(connection)
    repository.register_attribution_run(run)
    repository.register_adjusted_estimate(estimate)
    repository.register_attribution_run(run)
    repository.register_adjusted_estimate(estimate)

    with pytest.raises(P2DomainPersistenceError, match="P2_IMMUTABLE_CONFLICT"):
        repository.register_attribution_run(
            replace(run, created_by="conflicting-writer")
        )


def test_sqlite_p2_db_1_7_rejects_logical_hash_drift() -> None:
    connection = _connection()
    run, estimate = _fixture()
    connection.execute(
        'INSERT INTO "metric.capability_observation" '
        "(observation_id, release_id) VALUES (?, ?)",
        (estimate.source_observation_id, estimate.source_release_id),
    )
    repository = SQLiteP2DomainRepository(connection)
    repository.register_attribution_run(run)

    with pytest.raises(P2DomainPersistenceError, match="P2_LOGICAL_HASH_MISMATCH"):
        repository.register_adjusted_estimate(
            replace(estimate, logical_hash="0" * 64)
        )
