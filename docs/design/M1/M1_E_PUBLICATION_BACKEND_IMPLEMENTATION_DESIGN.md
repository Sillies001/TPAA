# M1-E Publication / Persistence / API / Replay Implementation Design

## Role and authority

This is the implementation design for coarse Batch 2 / Issue #87. It is not
semantic authority. SDIB-1.0.1 and the frozen CB-1.4.0 machine-readable
artifacts remain authoritative for Canonical identity, Metric semantics, DTO
shape, persistence schema, Stage semantics, and gate evidence.

Batch 2 consumes the protected-main Batch 1 products at
`a1036cf3dd2ccba7ce6d76695acd10865290db53`. It may not redefine them.

Primary frozen authorities:

- `CORE_RULES.json`
- `CORE_LOGICAL_MODEL.json`
- `CROSS_LAYER_DTO_CONTRACTS.json`
- `P1_METRIC_CATALOG.json`
- `METRIC_INPUT_AUTHORITY_MATRIX.json`
- `STAGE_REGISTRY.json`

## Existing authority that Batch 2 must use

The Core 1.6.0 logical model already defines the publication persistence
surface. No M1-only semantic tables are added:

- `registry.compute_job`
- `registry.analysis_release`
- `registry.release_scope_pointer`
- `registry.session_release_context_ref`
- `metric.metric_definition`
- `metric.evidence_set`
- `metric.metric_instance`
- `metric.capability_observation`

`CapabilityObservationDTO` is generated from
`CROSS_LAYER_DTO_CONTRACTS.json`; handwritten transport substitutes are
forbidden.

The five representative Batch 1 metrics are Aircraft subjects and their frozen
`publication_route` is `CAPABILITY_OBSERVATION`.

## M1-OBS-001 — Capability Observation projection

Publication consumes exact `MetricContext`, `AircraftObservedWorld`, and
`MetricBatch` values. It does not recompute Metric semantics.

The projection follows these invariants:

1. `publication_route == CAPABILITY_OBSERVATION` is checked from frozen generated
   Metric authority.
2. Metric definition identity is frozen with semantic id/version, algorithm
   id/version, value kind, unit, catalog version/hash, and route.
3. Metric instance binds exact Release, Context, World, Evidence, subject and
   typed value slot.
4. Observation DTO time values are decimal strings.
5. `CAP_L1_OBSERVED` is used exactly as constrained by the Core model.
6. No current formula or latest catalog is consulted when reading a historical
   Release.

Batch 1 intentionally did not create aircraft model / aircraft instance /
subject entity identities. Batch 2 therefore accepts those identities only from
an explicit authoritative upstream mapping. It must not synthesize them from
source aliases, UI state, row order, filenames, or current database state.

## M1-OBS-002 — SESSION Release

One immutable logical Release binds:

- Session identity
- exact Evaluation Context and binding hash
- exact Catalog version/hash
- immutable Metric Definition snapshots
- exact World product id/logical hash
- immutable Evidence sets
- immutable Metric instances
- Capability Observations

The Release manifest hash excludes physical timestamps and deployment details.
A Release is constructed as `VALIDATED`; repository publication is the only
operation allowed to advance it to `PUBLISHED`.

## M1-OBS-003 — publish CAS / idempotency

`registry.release_scope_pointer` is the sole current pointer. Publish uses
compare-and-swap semantics on `(scope_type, scope_key, version_token)`.
A repeated identical request must resolve to the same logical publication.
The same Idempotency-Key with a different canonical request hash is a conflict.

There is never an update-in-place of a published Release payload.

## M1-OBS-004 / M1-OBS-005 — historical read and replay

Historical read begins from an explicit `release_id`. All Definition, Context,
World, Evidence and Metric refs are release-bound.

Forbidden:

- current/latest Context fallback
- current/latest Metric formula fallback
- current release pointer substitution for a requested historical release
- mutation of old payloads after a newer release publishes

Replay re-runs the frozen provenance inputs and compares logical World and
Metric product hashes. Platform/timestamp metadata is excluded from logical
comparison.

## M1-STO-001 — Repository mapping

Concrete adapters may issue SQL only inside `tpaa_storage`. Application and API
layers consume engine-neutral repository ports.

SQLite and PostgreSQL must map only Core model columns. Adapter code must not
create repair tables, shadow publication tables, or engine-specific business
semantics.

## M1-STO-002 — staging to sealed object flow

Large immutable bytes use the existing logical object URI abstraction. Batch 2
adds an explicit state transition:

`staging logical URI -> verified bytes/hash -> sealed logical URI`

Crash/cancel leaves no sealed pointer. Orphan staging objects are discoverable
and removable without changing a published Release.

## M1-STO-003 — engine parity

For the same frozen fixture and request, SQLite and PostgreSQL must expose the
same logical Release membership:

- Release id/manifest hash
- bound Context/Catalog/World identities
- Definition hashes
- Evidence hashes
- Metric instance hashes
- Observation identities

Physical SQL/timestamps may differ and are not logical membership.

## M1-API-001..005

REST remains an adapter over `tpaa_application`.

- import / compute / publish commands require `Idempotency-Key`; the canonical
  request hash is returned.
- Session / Context / Episode / Stage reads return generated DTOs or explicit
  projections only.
- Metric reads are Release-bound and return immutable Definition/Metric/Evidence.
- Release / history / replay responses always expose `release_id`, provenance
  and status.
- high-frequency series are served only by bounded range query with explicit
  start/end and limit; they are not embedded in a large metric JSON response.

## M1-TST-004..007 and M1-PLAT-003

Required evidence before PR:

- immutable published payload/definition/context
- concurrent identical publish produces one logical current Release
- historical interpretation unchanged after a newer current Release
- exact DTO, decimal-string time and structured-result snapshots
- Windows/Linux service smoke through the same Application/Repository contract
- SQLite/PostgreSQL logical release parity

Hosted CI begins only when all 18 #87 acceptance rows are represented by
executable evidence. PR green alone does not complete Batch 2; exact merged-main
protected CI must also pass before #87 closes.
