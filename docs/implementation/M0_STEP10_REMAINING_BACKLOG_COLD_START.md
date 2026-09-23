# SDIB §39 Step 10 — Remaining M0 Backlog + Cold Start

- **Status:** COMPLETE
- **Accepted main revision:** `5768d53e6e2eb4cda59080ff4958d06e3984f499`
- **Authority:** SDIB-1.0 §17, §18, §30–§34, §39 step 10; Appendix E/F/H/I/P/Q/T.
- **Hosted acceptance:** GitHub Actions Run #26 (`35836960857`) on merged `main`.
- **Scope:** remaining M0 backlog only. M0 Exit Review is §39 step 11.

## Accepted backlog

Step 10 closes the remaining M0 implementation backlog:

- **M0-STO-004..007:** logical object/Parquet abstraction, migration harness, distinct request/logical/artifact hashes, development backup/restore.
- **M0-API-003..005:** Canonical-driven OpenAPI snapshot, idempotent job-control skeleton, controlled business/system status mapping.
- **M0-PLAT-001..003:** filesystem/path, spawn-worker and temp/lock/atomic-replace adapters.
- **M0-SEC-001..004:** Desktop/path security minimum, structured audit, development data guard, secret/config separation.
- **M0-DEV-003..006:** build manifest, SBOM/license/native inventory, four-profile development packages, clean-clone cold-start.
- **M0-GOV-001..004:** ADR-M0-001..010 CLOSED, Issue/PR templates, Baseline Change workflow, Definition of Done.

## Merged-main acceptance — Run #26

Run #26 completed SUCCESS for:

- `M0 windows`;
- `M0 linux`;
- `M0 logical equivalence`.

Both platform CI evidence files report:

- `status = PASS`;
- `failed_gate_names = []`;
- `source_revision = 5768d53e6e2eb4cda59080ff4958d06e3984f499`.

Both cold-start files report:

- `status = PASS`;
- `clean_clone = true`;
- `uv_sync_locked = true`;
- `m0_gates = PASS`;
- `worktree_clean = true`.

Windows/Linux also share the exact dependency-lock SHA-256:

`302ab51a013c713af6ece61113526eb411f6edf302b70c7a924224701387257e`.

The logical-equivalence evidence reports `status=PASS`, `mismatches=[]`, with identical frozen Core,
Baseline Lock, DB schema, Catalog, Stage, DTO and dependency-lock identities.

All four governed development package profiles are present and remain explicitly
`DEVELOPMENT_NOT_M5_QUALIFIED`.

## Step 11 handoff

Step 10 is COMPLETE. M0 is not yet COMPLETE: SDIB §18 requires the separate M0 Exit Review.

The first Exit Review pass identified one evidence-strengthening requirement before a GO decision:
ordinary Step 10 cold-start reruns the governed M0 CI set, while live PostgreSQL server acceptance was
retained as earlier M0-STO-001/003 evidence. Because §18.14 requires cold-start to reproduce all Exit
results, Step 11 adds a live PostgreSQL Exit job and a clean-clone cold-start that re-executes both
PostgreSQL clean-bootstrap and Repository acceptance. No GO decision is recorded until that job passes.
