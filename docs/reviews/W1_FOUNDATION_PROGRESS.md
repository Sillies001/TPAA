# W1 migration, configuration, and product-management closure review

Date: 2026-10-19

W1 state: `CLOSED_LOCAL / PASS`

Program state: `LOCAL_ONLY / NOT_PRODUCTION_READY`

W1 is closed as a development stage. This does not close W2-W9, authorize a push,
or qualify a production deployment.

## Closure result

| Work package | Result | Closure evidence |
|---|---|---|
| W1-A migration | PASS | One Desktop/Service `plan|verify|apply|resume|rollback|status` surface; governed 1.6→1.9 graph; verified backup; exclusive lock/write drain; atomic journal; non-empty rollback block; no silent bootstrap |
| W1-B configuration | PASS | Shared strict `TPAA_RUNTIME_CONFIG_V1`, absolute roots, version/Core/DB/authority handshake, `env://` secret references, explicit Service migration state root |
| W1-C registries | PASS | Engine-neutral Context/configuration/lifecycle service, immutable replay, approval before snapshot, object hash binding, persistent audit |
| W1-D Release lifecycle | PASS | Engine-neutral list/withdraw/supersede, lineage/current-pointer rules, optimistic CAS, persistent audit |
| W1-E READY | PASS | Migration head/journal, authority, object store, identity, worker, and active Service write-drain detection are fail-closed |

The legacy environment-only Service startup path is frozen as deprecated compatibility
for W2/W3 development and must be removed before W3 exits. It is not acceptable as
formal release evidence.

## Real PostgreSQL evidence

An isolated disposable `postgres:16` container was used; no external or production
database was contacted.

- clean DB 1.9 bootstrap: PASS, 95 tables;
- bootstrap mid-fault rollback and missing/extra/tampered schema rejection: PASS;
- DB 1.6 plan contained ACP-216, ACP-219, ACP-221;
- injected failure persisted a FAILED journal and `resume` reached DB 1.9: PASS;
- DB 1.9→1.8 rollback and 1.8→1.9 reapply: PASS;
- three real custom-format `pg_dump` backups were produced and hash-verified;
- READY around managed drain: `true → false → true`;
- PostgreSQL Context/configuration/lifecycle/Release qualification: PASS, nine audit
  records, Context retired, approved configuration snapshotted, lifecycle event
  recorded, releases ended `SUPERSEDED` and `WITHDRAWN`.

Reusable qualification commands are implemented in:

- `tools/testing/w1_postgres_migration_qualification.py`
- `tools/testing/w1_registry_postgres_qualification.py`

The disposable container was stopped and removed after qualification. Its database
data was intentionally ephemeral; local backup/evidence files remain under
`evidence/local/w1/`.

## Automated verification

- W1 focused tests: `33 passed`;
- complete unit suite: `728 passed`;
- complete contract suite: `814 passed, 1 failed`;
- targeted Ruff, mypy, and `compileall`: PASS.

The sole contract failure is the intentional clean-worktree package gate in
`test_m0_dev_toolchain.py`: the repository contains the authorized local W0/W1 and
earlier remediation edits. The packaging tool correctly refuses that dirty tree.
No commit, staging, bypass, push, or deployment was performed to suppress the gate.
It is not a W1 functional regression and must be rerun only when an authorized clean
release candidate exists.

That deferred check was completed on 2026-10-20 after explicit authorization.
Local checkpoint `8401751` passed the Windows Desktop development-package gate,
including build/package manifests and SBOM, and the complete contract suite
reported `815 passed, 0 failed`. No gate was relaxed, and no push or deployment
was performed. The generated package remains `DEVELOPMENT_NOT_M5_QUALIFIED`.

Pytest also emits the existing Windows cache/temp cleanup `WinError 5` after test
assertions. Test processes otherwise returned the stated results.

## Source evidence

- `src/tpaa_storage/migration_service.py`
- `src/tpaa_admin/__main__.py`
- `src/tpaa_runtime/entry_config.py`
- `src/tpaa_runtime/production.py`
- `src/tpaa_runtime/readiness.py`
- `src/tpaa_runtime/recovery.py`
- `src/tpaa_application/governance_registry.py`
- `src/tpaa_application/release_management.py`
- `tests/unit/storage/test_w1_migration_service.py`
- `tests/unit/application/test_w1_governance_registry.py`
- `tests/unit/application/test_w1_release_management.py`

No source was pushed and no production deployment was attempted.
