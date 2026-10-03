# M0 Migration Harness

The current governed DB schema target is **1.7.0**.

ACP-216 is the first real approved schema transition in the repository:

- source authority: CB-1.4.0 / DB 1.6.0;
- target authority: CB-1.4.0 / DB 1.7.0;
- transition class: additive companion relations only;
- new relations: 15;
- shadow schema: forbidden;
- historical 1.6.0 Core bytes are retained under
  `migrations/authority/CORE_LOGICAL_MODEL_DB_1_6_0.json` strictly as migration-source evidence.

The governed revision artifact is
`migrations/versions/0001_acp216_db_1_7_0.py`. ADR-M0-004 continues to designate
Alembic as the Service migration executor/history technology. The current locked
toolchain does not yet contain Alembic or SQLAlchemy, so CI executes the exact same
transition semantics through the repository-controlled migration harness rather than
hand-editing `uv.lock` or introducing an unqualified dependency change.

Qualification requires:

- clean SQLite/PostgreSQL 1.7.0 bootstrap from current Canonical authority;
- verified 1.6.0 source before upgrade;
- 1.6.0 -> 1.7.0 upgrade on both engines;
- preservation of historical 1.6.0 business rows;
- deterministic current schema/provenance verification after upgrade;
- downgrade only when every ACP-216 relation is empty;
- fail-closed downgrade when any new relation contains data;
- forward re-upgrade;
- SQLite/PostgreSQL logical transition parity;
- exact-head 14-job Hosted CI and protected-main authority qualification.

A later toolchain change may install/pin Alembic and SQLAlchemy and execute the
revision through the Alembic CLI. That dependency change is separate from the schema
authority adoption and must update `pyproject.toml` and `uv.lock` together.
