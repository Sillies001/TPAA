# M0 Migration Harness

The current frozen DB schema target is **1.6.0**. SDIB-1.0 explicitly forbids inventing a
new schema version merely because the engineering document changed.

M0-STO-005 therefore freezes the migration topology and executable recovery harness without
creating a fake 1.6.0→new revision:

- clean SQLite/PostgreSQL bootstrap remains authority-driven from `CORE_LOGICAL_MODEL`;
- readiness verifies schema/version/provenance exactly;
- transactional rollback is tested;
- committed drift is rejected fail-closed;
- forward recovery restores a previously verified 1.6.0 state;
- historical fixture/replay hooks are present;
- SQLite/PostgreSQL Repository conformance remains part of the migration test family.

The Service migration executor/history technology decision from ADR-M0-004 remains Alembic.
The first **real approved schema transition** must create the first governed Alembic revision;
M0-STO-005 does not fabricate an empty semantic revision only to populate history.
