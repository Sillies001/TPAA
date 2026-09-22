# M0-STO-001 — DB 1.6.0 Clean Bootstrap Implementation Plan

**Task:** M0-STO-001  
**Workstream:** WS-STORAGE  
**Status:** COMPLETE
**Plan version:** v0.6
**Implementation baseline:** SDIB-1.0 + frozen CB-1.4.0 Canonical snapshot at repository HEAD

## 1. Objective

Establish a deterministic, fail-closed clean-database bootstrap kernel for DB schema target `1.6.0` without inventing persistence semantics outside the frozen Canonical authority. The implemented slices bootstrap and verify the SQLite Desktop profile and deterministically project the same exact `CORE_LOGICAL_MODEL.json` authority to PostgreSQL DDL with FK dependency ordering. Repository-controlled PostgreSQL execution/readiness verification is implemented through an external `psql` acceptance harness that deliberately does not select a Python Repository driver. The corrected committed harness has now passed the real PostgreSQL 16.15 acceptance run, closing the M0-STO-001 engine-execution requirement.

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

### Index-authority clarification from PostgreSQL feasibility work

No controlled Canonical artifact found in R3.3 defines a complete independent index catalog or table-level DDL catalog. `CORE_LOGICAL_MODEL.json` contains field-level SQL fragments, including inline PK/FK/UNIQUE/CHECK/default semantics, but no explicit separate index list. SDIB-1.0 M0-STO-001 minimum acceptance is an empty DB initialized to `1.6.0` and passing schema/hash verification; repository-wide searches found no separate index-inventory acceptance clause. Therefore M0-STO-001 verifies the schema elements actually declared by Canonical authority and MUST NOT synthesize undeclared performance indexes. A later controlled artifact may add index authority, but the absence of an independent index catalog is no longer treated as a standalone blocker for this task.

## 4. DB engine / compatibility assumptions

- SQLite is a required Desktop bootstrap target.
- PostgreSQL is a required Service/CI bootstrap target before task completion.
- v0.1 first slice uses Python standard-library `sqlite3`; this does **not** freeze the later Repository ORM/driver decision.
- `ADR-M0-004` is not present in the current repository and is still required by SDIB for Repository DB access implementation. Repository skeleton work must not silently choose that architecture in this task.
- M0-STO-001 PostgreSQL execution uses the platform-required external PostgreSQL client (`psql`) only as an acceptance/bootstrap transport. This does not freeze `psycopg`, `asyncpg`, SQLAlchemy, an ORM, or any Repository adapter technology.
- SQLite physical DDL is a dialect projection of Canonical field SQL, not a second logical schema authority.

## 5. Clean bootstrap architecture

1. Load `CORE_LOGICAL_MODEL` through `CanonicalArtifactLoader` with expected schema `1.6.0`.
2. Validate the logical model envelope and every table/field entry before opening a write transaction.
3. Deterministically project Canonical field SQL to the target engine without changing the logical authority. SQLite performs the minimum documented dialect substitutions; PostgreSQL preserves native Canonical types/constraints and orders tables by the FK dependency graph.
4. Create implementation metadata table `_tpaa_bootstrap_manifest` for bootstrap provenance only; it is not a business/domain object.
5. Create every Canonical table inside one explicit transaction. PostgreSQL ordering is deterministic topological ordering with lexical tie-breaking; missing FK targets or dependency cycles fail closed before DDL execution.
6. Persist schema target, Core Baseline, Canonical artifact SHA-256, and baseline-lock SHA-256 in the bootstrap manifest.
7. PostgreSQL bootstrap additionally records a SHA-256 of a deterministic `pg_catalog` projection covering non-system schemas, relations, columns/defaults, constraints, indexes, triggers, views, and sequences.
8. Verify exact expected schema/table inventory, baseline provenance, deterministic DDL projection hash, and current PostgreSQL catalog hash before readiness success.
9. Roll back and fail closed on any mismatch.

## 6. Migration/bootstrap boundary

M0-STO-001 provides only clean bootstrap from an empty DB to `1.6.0`. It does not create a fictional pre-1.6.0 migration or a 1.6.0→new-version migration. Hop/rollback/forward-recovery infrastructure belongs to M0-STO-005 unless a real schema change is introduced.

## 7. Transaction semantics

- Bootstrap is all-or-nothing.
- SQLite foreign-key enforcement is enabled for verification/use.
- Any DDL, provenance, or post-create verification error triggers rollback.
- PostgreSQL bootstrap executes through one `psql` connection and one explicit transaction with `ON_ERROR_STOP`; injected mid-bootstrap failure must leave zero non-system user relations.
- PostgreSQL readiness verification executes inside `BEGIN READ ONLY` and finishes with `ROLLBACK`; it must not repair or mutate the target database.
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
- PostgreSQL catalog-schema SHA-256 for physical drift detection on the Service profile;
- engine profile.

This creates a machine-verifiable trace from runtime DB bootstrap state back to the frozen Core/Canonical baseline without completing M0-CORE-006 runtime handshake.

## 10. Failure semantics

Fail closed for at least:

- baseline-lock or Canonical artifact drift;
- wrong DB schema version;
- malformed/missing logical table or field declarations;
- inconsistent per-table schema version;
- unsupported Canonical SQL fragment/type in an engine projection;
- PostgreSQL FK target missing from the Canonical table catalog;
- PostgreSQL FK dependency cycle that prevents single-phase deterministic creation;
- non-empty target DB;
- missing/extra table after bootstrap;
- DDL fingerprint mismatch;
- bootstrap manifest mismatch;
- partial transaction/fault injection.

Errors are engineering/storage diagnostics and must not introduce business Metric/Stage reason semantics.

## 11. Idempotency policy

Clean bootstrap is intentionally strict rather than silently idempotent: it accepts an empty database only. Readiness is a separate `verify` operation. This prevents an existing partial or foreign database from being reported as successfully bootstrapped.

## 12. Test matrix

Implemented slices:

- Canonical authority extraction/version checks independent of a specific engine type map;
- deterministic SQLite DDL generation;
- deterministic PostgreSQL DDL projection from the same Canonical field SQL;
- PostgreSQL FK dependency extraction and lexical-tie-break topological ordering;
- fail-closed missing-reference and cycle tests;
- clean in-memory/file bootstrap;
- exact table inventory verification;
- manifest provenance verification;
- DDL fingerprint verification;
- WAL mode for file-backed Desktop DB;
- re-bootstrap rejection;
- missing table / altered manifest / schema drift failure injection;
- transaction rollback on injected DDL failure;
- architecture dependency gate regression.

Completion evidence now established:

- repository-controlled PostgreSQL real-server acceptance harness executed successfully on PostgreSQL 16.15;
- PostgreSQL schema/version/provenance verification matches the SQLite readiness contract at the governed authority boundary;
- SQLite/PostgreSQL projections are derived from the same 77-table Canonical authority and PostgreSQL FK ordering is deterministic;
- fail-closed corruption/rollback injections PASS;
- complete repository test inventory is 98/98 PASS when executed by file/partition;
- historical gates and clean-clone verification PASS, subject to the explicitly unclaimed Ruff/mypy/Windows-CI items outside this task completion claim.

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
2. SQLite and PostgreSQL physical mappings are explicit and verified for the full Canonical schema;
3. `ADR-M0-004` is created/closed for Repository DB access implementation before concrete Repository adapter technology is frozen;
4. bootstrap/version/provenance access is exposed below Application without leaking DB-driver types upward.

## 15. Completion criteria

M0-STO-001 is COMPLETE because all task completion criteria below are satisfied:

- SQLite clean bootstrap to `1.6.0` PASS;
- PostgreSQL clean bootstrap to `1.6.0` PASS on a real server;
- machine schema/hash verification PASS on both;
- required schema elements defined by authority are verified on both engines;
- failure injection proves no silent partial success;
- historical gates/regression PASS;
- formal commit, clean HEAD revalidation, bundle, clean clone, machine-readable evidence, delivery ZIP and SHA-256 manifest are produced.

## 16. v0.1 implementation decision log

- 2026-09-21: use existing fail-closed Canonical loader as the only input path for `CORE_LOGICAL_MODEL`.
- 2026-09-21: do not add third-party DB/ORM dependencies for the SQLite kernel.
- 2026-09-21: preserve `ADR-M0-004` as a later explicit Repository technology decision; M0-STO-001 will not close it implicitly.
- 2026-09-21: record the missing explicit index catalog; do not invent indexes in code. Subsequent SDIB/Canonical review narrowed this from a completion blocker to an explicit non-synthesis boundary because no independent index inventory is required by the M0-STO-001 acceptance text.

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

This feedback does not alter the authority model or introduce a new schema. It confirms that dialect adaptation is required below the logical authority boundary.

## 18. v0.3 revision from PostgreSQL real-server feasibility

Windows Docker Desktop with an isolated `postgres:16` container was used as a real PostgreSQL server without adding a Python PostgreSQL driver or changing the repository dependency baseline. Observed PostgreSQL version was 16.15. The feasibility sequence established:

- PostgreSQL server readiness and SQL execution PASS.
- transactional DDL rollback PASS; an intentionally created probe table left no residue after rollback.
- native `uuid`, `jsonb`, PK, UNIQUE, and `jsonb_typeof(...)` CHECK semantics PASS.
- valid JSON object input was rejected by the Canonical-style `jsonb_typeof(payload)='array'` CHECK, proving the constraint rather than JSON parsing was the failure boundary.
- raw Canonical JSON table order failed because a table referenced `registry.analysis_release` before that relation existed.
- the Canonical FK graph contains 77 tables and 125 inter-table dependency edges, with zero missing references and zero cycles.
- deterministic topological order therefore supports single-phase PostgreSQL table creation; lexical ordering is used only to break ties between simultaneously ready tables.
- all 77 Canonical tables created successfully inside one PostgreSQL transaction using the derived topological order, then `ROLLBACK` left zero user tables.

Implementation feedback from that real execution is now reflected in code:

1. Canonical authority validation is engine-neutral; SQLite type support is checked only in the SQLite projection.
2. PostgreSQL projection preserves native Canonical field SQL after the same authority-boundary cleanup of trailing human comments.
3. FK target absence and dependency cycles are deterministic fail-closed errors.
4. PostgreSQL DDL generation is now repository-controlled and deterministic, but PostgreSQL connection/Repository driver selection remains outside this slice and `ADR-M0-004` remains OPEN.
5. Repository-controlled real-server acceptance and PostgreSQL schema/provenance verification were subsequently implemented and passed on PostgreSQL 16.15; see v0.4-v0.6 revisions.

Repository regression after this slice on CPython 3.13.5 / Linux x86_64:

- focused SQLite + PostgreSQL projection migration suite: 15/15 PASS;
- unit suite: 33/33 PASS;
- contract suite: 40/40 PASS when run by file/partition;
- M0-CORE-001 baseline exact verification PASS;
- M0-CORE-002 Canonical loader verification PASS;
- codegen `generate --check` PASS;
- generated-source governance and `regenerate-diff` PASS;
- M0-CORE-005 architecture dependency gate PASS;
- `bootstrap --check-only` PASS;
- Ruff 0.16.8 and mypy 2.3.1 execution are NOT CLAIMED on this offline host because the frozen binaries are not installed/cached.


## 19. v0.4 revision — repository-controlled PostgreSQL execution/verification harness

The PostgreSQL execution boundary is implemented without changing the dependency baseline or closing `ADR-M0-004`. `tools/storage/postgres_db.py` invokes an external `psql` client directly or through an explicitly selected Docker container. `tools/dev/tpaa_dev.py` exposes the same repository-controlled entry points.

Implemented semantics:

- `db-postgres-bootstrap`: clean-target guard → deterministic 77-table DDL → manifest/provenance → exact inventory guard → commit → read-only verify.
- `db-postgres-verify`: read-only exact schema/table inventory, manifest/version/Core/Canonical/lock/projection verification, plus recomputed PostgreSQL catalog SHA-256.
- `db-postgres-acceptance`: destructive only inside a safely named disposable database (`tpaa_m0_sto_001_*`); runs mid-bootstrap rollback injection, clean bootstrap/verify, missing-table detection, manifest tamper detection, DDL tamper detection, and unexpected-index detection, then drops the disposable database.
- Direct client mode uses `psql`; Docker mode uses `docker exec -i <container> psql`. Neither mode introduces or implies a Python Repository driver.
- The catalog fingerprint includes non-system schemas/relations, column types/nullability/defaults, constraints, indexes, triggers, views, and sequences, so physical drift is not reduced to file/table existence.

Repository-local tests after this revision cover generated SQL transaction/read-only semantics, provenance fields, rollback-failure detection, dirty-target rejection, and acceptance database safety. The harness was subsequently executed on the user's PostgreSQL 16.15 Docker server; the first run exposed the catalog serialization issue corrected in v0.5, and the corrected run passed all acceptance checks recorded in v0.6.

Current repository-local verification after the final completion update: complete collected inventory 98/98 PASS by file/partition, including migration 25/25 and unit 33/33; Baseline/Canonical/codegen/generated-governance/regenerate-diff/architecture/bootstrap gates PASS. Ruff 0.16.8 and mypy 2.3.1 are not installed/cached on this offline host and remain NOT CLAIMED here.

## 20. v0.5 revision — PostgreSQL catalog serialization compatibility fix

The first execution of the committed repository-controlled PostgreSQL acceptance harness on the user's real PostgreSQL 16.15 Docker server reached the verifier but failed while serializing `pg_catalog` metadata for the physical-schema fingerprint. PostgreSQL reported `operator is not unique: text || "char"` because several catalog fields use PostgreSQL's internal one-byte `"char"` type rather than `text`.

This was an implementation defect in the verifier projection, not a Canonical schema, bootstrap, transaction, or Repository-technology decision. The catalog serializer now explicitly casts every internal `"char"` field used in concatenation to `text`: `pg_class.relkind`, `pg_attribute.attidentity`, `pg_attribute.attgenerated`, and `pg_constraint.contype`. A regression test asserts those casts so the failure cannot recur silently.

The corrected commit was re-run through the real PostgreSQL 16.15 acceptance command and all acceptance checks passed. The final completion cycle is recorded in v0.6.


## 21. v0.6 completion — real PostgreSQL acceptance and final closure

The corrected repository-controlled acceptance harness was executed from clean clone commit `af5aa512963fa7caf7ac1a0d8868914f57c8fe2e` against the user-managed `postgres:16` Docker container reporting PostgreSQL 16.15. The command `db-postgres-acceptance` returned PASS for every destructive/fail-closed scenario in its disposable acceptance database:

- `clean_bootstrap_verify`: PASS;
- `mid_bootstrap_rollback`: PASS;
- `missing_table_fail_closed`: PASS;
- `manifest_tamper_fail_closed`: PASS;
- `ddl_tamper_fail_closed`: PASS;
- `unexpected_index_fail_closed`: PASS.

The successful verification reported engine profile `postgresql-service`, schema version `1.6.0`, Core Baseline `CB-1.4.0`, Canonical SHA-256 `cfde6638e6899167267375c899bff2f04a490ce12f32e0005be4e15dda956245`, baseline-lock SHA-256 `9d96a7eb0ba2b1fb13b11d76943171f773fd42497df74bf79c01928cfa26e7fa`, 77 Canonical tables, physical-schema SHA-256 `b81611310f5519876e8331ef3a68c4993a4ae62ffa08d47dda9098eaf5e60411`, and PostgreSQL catalog-schema SHA-256 `c255519b726466d161492aa1b4a3e88c489b189cdde41b4f56bf315db1b5dcfd`.

Final repository regression on CPython 3.13.5 / Linux x86_64 collected 98 tests and passed all 98 when executed by complete file/partition to avoid the subprocess-heavy aggregate timeout. This includes migration 25/25 and unit 33/33. Historical exact-baseline, Canonical-loader, codegen `--check`, generated-source governance, regenerate-diff, architecture dependency, and `bootstrap --check-only` gates all PASS. A final formal completion commit and clean-clone revalidation are part of the delivery evidence.

Ruff 0.16.8, mypy 2.3.1, and Windows CI execution are not claimed by this Linux sandbox completion record; their absence does not alter the M0-STO-001 acceptance demonstrated above and they remain governed by the existing developer/platform workstreams. `ADR-M0-004` remains OPEN because this task deliberately did not select a Repository Python driver/ORM. M0 Exit and M0-CORE-006 are not claimed.
