# M0-CORE-006 — Runtime Baseline Handshake Model

**Status:** COMPLETE

**Authority:** SDIB-1.0 §17 task `M0-CORE-006`, Appendix G, Appendix H, Appendix Q.

## Purpose

M0-CORE-006 establishes one transport-neutral, fail-closed comparison model for runtime
baseline identity.  FastAPI, GUI and future local-backend lifecycle code must consume this
model rather than independently deciding whether a runtime is READY.

The minimum SDIB acceptance is exact: a Core, Catalog, DB schema or product-build mismatch
must not enter READY.

## Identity dimensions

`RuntimeBaselineIdentity` carries the dimensions needed by the M0 handshake:

- product build version;
- Core Baseline;
- approved `BASELINE_LOCK.json` SHA-256;
- DB schema version;
- Core logical-model authority id/hash;
- P1 Metric Catalog version/hash;
- cross-layer DTO authority hash.

The Core/Catalog/DTO values for the local trusted identity are read only through the existing
`CanonicalArtifactLoader`, so exact baseline-lock and controlled-artifact byte/hash checks
remain the trust boundary.  M0-CORE-006 does not duplicate Canonical JSON parsing or create a
second schema authority.

## READY semantics

`evaluate_runtime_baseline_handshake()` performs deterministic exact comparison and returns:

- `READY` only when every governed identity dimension is equal;
- `NOT_READY` when one or more dimensions differ;
- a stable ordered tuple of engineering mismatch codes for diagnostics.

Mismatch codes are engineering readiness diagnostics, not Metric/business status reason
codes.

## Product build boundary

The product build version is an explicit input to the trusted identity loader.  This is
intentional: M0-DEV-003 owns the future build manifest/source-revision artifact.  This task
must not infer a product build from a Git checkout, filesystem path or package timestamp, and
must not invent `build-manifest.json` before its governing task.

When M0-DEV-003 is implemented, its approved product-build value can feed the existing
handshake without changing comparison semantics.

## Explicit non-scope

This task does not implement:

- FastAPI health/readiness/version routes (`M0-API-002`);
- PySide6/local-backend lifecycle or token/port strategy (`ADR-M0-005`, GUI tasks);
- the M0-DEV-003 build manifest;
- Repository transaction smoke beyond the already completed Storage tasks;
- Object/Parquet, Worker, Security or platform-certification readiness checks owned by later
  tasks.

Those checks may contribute to a broader Appendix-Q readiness aggregate later.  They must not
weaken the M0-CORE-006 rule that any governed baseline mismatch is fail-closed.

## Acceptance evidence

Unit and contract tests cover exact READY, each Core/Catalog/schema/build mismatch class,
multiple simultaneous mismatches, deterministic ordering, trusted Canonical identity
construction, explicit product-build input and the absence of transport/database dependencies
from the handshake module.
