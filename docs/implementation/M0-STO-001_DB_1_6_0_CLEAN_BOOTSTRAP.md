# M0-STO-001 — DB 1.6.0 Clean Bootstrap Implementation Plan

**Task:** M0-STO-001  
**Workstream:** WS-STORAGE  
**Status:** IN PROGRESS  
**Plan version:** v0.2  
**Implementation baseline:** SDIB-1.0 + frozen CB-1.4.0 Canonical snapshot at repository HEAD

## 1. Objective

Establish a deterministic, fail-closed clean-database bootstrap kernel for DB schema target `1.6.0` without inventing persistence semantics outside the frozen Canonical authority. The first vertical slice bootstraps and verifies the SQLite Desktop profile from the exact `CORE_LOGICAL_MODEL.json` controlled by `BASELINE_LOCK.json`. PostgreSQL execution/conformance remains required before M0-STO-001 can be declared COMPLETE.

## 2. SDIB acceptance criteria

SDIB-1.0 requires:

- M0-STO-001: an empty DB can be initialized and pass schema/hash verification.
- DB schema target remains `1.6.0`; R3.3 does not create a synthetic migration.
- Desktop profile uses SQLite WAL; Service/CI uses PostgreSQL + Parquet/Alembic.
- Migration harness must eventually cover clean bootstrap, schema readiness, seed/hash parity, typed round-trip, recovery hooks, historical fixture hooks, and SQLite/PostgreSQL conformance.
- M0 Exit requires clean bootstrap on both SQLite and PostgreSQL.

This task does not claim the broader M0-STO-005 migration harness or M0 Exit.

## 3. Canonical / schema authority mapping

Machine authority discovered from the frozen baseline:

| Concern | Authority | Rule used by implementation |
| --- | --- | --- |
| DB target | `BASELINE_LOCK.json` | `baseline.db_schema == 1.6.0` |
| Logical persistence objects and fields | `canonical/CORE_LOGICAL_MODEL.json` | sole field-level persistence authority |
| Authority routing | `canonical/SCHEMA_AUTHORITY_REGISTRY.json` | logical persistence objects map to `CORE_LOGICAL_MODEL.json` |
| Storage/repository semantics | ED-2.0 `05E_Storage_Release_Replay` + SDIB-1.0 §10 | dialect split remains below Domain/Repository contract |
| Baseline byte trust | existing `CanonicalArtifactLoader` | exact lock + artifact byte/hash verification before use |

`CORE_LOGICAL_MODEL.json` declares 77 logical tables, each with ordered field SQL fragments and table-level `schema_version=1.6.0`.

### Authority gap recorded by v0.1

No controlled Canonical artifact found in R3.3 defines a complete independent index catalog or table-level DDL catalog. `CORE_LOGICAL_MODEL.json` contains field-level SQL fragments, including inline PK/FK/UNIQUE/CHECK/default semantics, but no explicit separate index list. Therefore this implementation MUST NOT invent performance or uniqueness indexes. M0-STO-001 cannot claim verification of unspecified indexes. If acceptance requires indexes beyond those implied by Canonical field SQL, that requires a Canonical/Baseline clarification or change before COMPLETE.

## 4. DB engine / compatibility assumptions

- SQLite is a required Desktop bootstrap target.
- PostgreSQL is a required Service/CI bootstrap target before task completion.
- v0.1 first slice uses Python standard-library `sqlite3`; this does **not** freeze the later Repository ORM/driver decision.
- `ADR-M0-004` is not present in the current repository and is still required by SDIB for Repository DB access implementation. Repository skeleton work must not silently choose that architecture in this task.
- SQLite physical DDL is a dialect projection of Canonical field SQL, not a second logical schema authority.

## 5. Clean bootstrap architecture

1. Load `CORE_LOGICAL_MODEL` through `CanonicalArtifactLoader` with expected schema `1.6.0`.
2. Validate the logical model envelope and every table/field entry before opening a write transaction.
3. Deterministically project Canonical field SQL to SQLite-compatible DDL while retaining logical table identity.
4. Create implementation metadata table `_tpaa_bootstrap_manifest` for bootstrap provenance only; it is not a business/domain object.
5. Create every Canonical table inside one explicit transaction.
6. Persist schema target, Core Baseline, Canonical artifact SHA-256, and baseline-lock SHA-256 in the bootstrap manifest.
7. Verify exact expected table inventory and generated DDL fingerprint before commit.
8. Roll back and fail closed on any mismatch.

## 6. Migration/bootstrap boundary

M0-STO-001 provides only clean bootstrap from an empty DB to `1.6.0`. It does not create a fictional pre-1.6.0 migration or a 1.6.0→new-version migration. Hop/rollback/forward-recovery infrastructure belongs to M0-STO-005 unless a real schema change is introduced.

## 7. Transaction semantics

- Bootstrap is all-or-nothing.
- SQLite foreign-key enforcement is enabled for verification/use.
- Any DDL, provenance, or post-create verification error triggers rollback.
- A non-empty/non-bootstrap database is rejected rather than silently adopted.
- Re-running bootstrap on an already initialized DB is not treated as success; callers must use verification for readiness.

## 8. Schema versioning

Authoritative target comes from frozen `BASELINE_LOCK.json` and must equal `CORE_LOGICAL_MODEL.db_schema_version`. Every table declaration must also report the same schema version. The implementation stores the resolved value in `_tpaa_bootstrap_manifest` and verifies it on readiness checks.

## 9. Baseline provenance

The bootstrap manifest records at minimum:

- schema version;
- Core Baseline;
- Canonical authority id (`CORE_LOGICAL_MODEL`);
- exact Canonical artifact SHA-256;
- exact trusted baseline-lock SHA-256;
- deterministic physical-schema DDL fingerprint;
- engine profile.

This creates a machine-verifiable trace from runtime DB bootstrap state back to the frozen Core/Canonical baseline without completing M0-CORE-006 runtime handshake.

## 10. Failure semantics

Fail closed for at least:

- baseline-lock or Canonical artifact drift;
- wrong DB schema version;
- malformed/missing logical table or field declarations;
- inconsistent per-table schema version;
- unsupported Canonical SQL fragment in the SQLite projection;
- non-empty target DB;
- missing/extra table after bootstrap;
- DDL fingerprint mismatch;
- bootstrap manifest mismatch;
- partial transaction/fault injection.

Errors are engineering/storage diagnostics and must not introduce business Metric/Stage reason semantics.

## 11. Idempotency policy

Clean bootstrap is intentionally strict rather than silently idempotent: it accepts an empty database only. Readiness is a separate `verify` operation. This prevents an existing partial or foreign database from being reported as successfully bootstrapped.

## 12. Test matrix

First slice:

- Canonical authority extraction/version checks;
- deterministic SQLite DDL generation;
- clean in-memory/file bootstrap;
- exact table inventory verification;
- manifest provenance verification;
- DDL fingerprint verification;
- WAL mode for file-backed Desktop DB;
- re-bootstrap rejection;
- missing table / altered manifest / schema drift failure injection;
- transaction rollback on injected DDL failure;
- architecture dependency gate regression.

Before COMPLETE:

- PostgreSQL clean bootstrap against a real PostgreSQL instance;
- SQLite/PostgreSQL logical schema parity/conformance evidence;
- any authority clarification required for separate indexes/table-level constraints;
- full repository regression and clean-clone evidence.

## 13. Explicit non-scope

- Repository interfaces/UoW/business persistence methods;
- SQLAlchemy/ORM selection;
- PostgreSQL driver selection;
- Application/FastAPI/PySide6 shells;
- M0-CORE-006 runtime handshake completion;
- Parquet/object storage;
- migration hop/down/recovery harness;
- business seed data, metrics, Stage inference, or training-evaluation logic.

## 14. Repository skeleton handoff criteria

Repository skeleton may begin only after:

1. schema authority and bootstrap contract are stable;
2. SQLite and PostgreSQL physical mappings are explicit and verified for the required subset/full schema;
3. `ADR-M0-004` is created/closed for Repository DB access implementation before concrete Repository adapter technology is frozen;
4. bootstrap/version/provenance access is exposed below Application without leaking DB-driver types upward.

## 15. Completion criteria

M0-STO-001 remains IN PROGRESS until all are true:

- SQLite clean bootstrap to `1.6.0` PASS;
- PostgreSQL clean bootstrap to `1.6.0` PASS on a real server;
- machine schema/hash verification PASS on both;
- required schema elements defined by authority are verified; unresolved authority gaps are closed at the correct baseline/governance layer;
- failure injection proves no silent partial success;
- historical gates/regression PASS;
- formal commit, clean HEAD revalidation, bundle, clean clone, machine-readable evidence, delivery ZIP and SHA-256 manifest are produced.

## 16. v0.1 implementation decision log

- 2026-09-21: use existing fail-closed Canonical loader as the only input path for `CORE_LOGICAL_MODEL`.
- 2026-09-21: do not add third-party DB/ORM dependencies for the SQLite kernel.
- 2026-09-21: preserve `ADR-M0-004` as a later explicit Repository technology decision; M0-STO-001 will not close it implicitly.
- 2026-09-21: record the missing explicit index catalog as an authority gap; do not invent indexes in code.

## 17. v0.2 revision from first vertical-slice execution

The first real SQLite execution initially failed while creating `metric.metric_definition`: Canonical field SQL contains PostgreSQL-specific `jsonb_typeof(required_world_products)='array'`. SQLite rejects that function name at DDL prepare time. The implementation was revised narrowly to project `jsonb_typeof(...)` to SQLite JSON1 `json_type(...)`, preserving the CHECK semantics rather than dropping the constraint.

Observed first-slice result on CPython 3.13.5 / Linux x86_64:

- 77/77 Canonical logical tables projected deterministically.
- SQLite file bootstrap + readiness verification PASS.
- WAL mode PASS for file-backed Desktop DB.
- duplicate clean-bootstrap rejection PASS.
- missing-table detection PASS.
- bootstrap-manifest tamper detection PASS.
- DDL tamper detection PASS.
- injected invalid DDL rollback leaves zero user tables PASS.
- focused suite: 9/9 PASS.

This feedback does not alter the authority model or introduce a new schema. It confirms that dialect adaptation is required below the logical authority boundary. PostgreSQL real-server execution and the separate-index authority gap remain open before task completion.
