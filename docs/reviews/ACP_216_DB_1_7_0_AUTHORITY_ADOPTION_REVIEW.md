# ACP-216 DB 1.7.0 Authority Adoption Review

## Purpose

This gate is the independent authority transition required by ACP-216 after the
PIQB B2 readiness reviewer returned `READY_FOR_ADOPTION` on Run #567.

The authority PR may prove a candidate, but it may not declare itself adopted.
Formal adoption requires the actual guarded-merge SHA to pass protected-main
Hosted CI with exactly 14/14 required jobs.

## Candidate scope

- DB schema 1.6.0 -> 1.7.0.
- 15 additive companion relations exactly as proposed by ACP-216.
- No shadow schema.
- Existing 77 relation field semantics preserved byte-for-byte except their
  table-level schema-version metadata moving to 1.7.0.
- Exact 1.6.0 Core bytes retained as migration-source evidence.
- Composite PK/UNIQUE constraints projected identically to SQLite/PostgreSQL.
- First governed Alembic-compatible revision artifact.
- Real SQLite and PostgreSQL upgrade/downgrade qualification.
- Downgrade allowed only when every ACP-216 relation is empty.
- Historical M0-M9 semantic authorities remain unchanged.
- No B2 runtime implementation and no B3 data-plane work in this authority PR.

## Decisions

Pull-request exact-head PASS:
`PENDING_PROTECTED_MAIN / ACP216_DB_1_7_0_CANDIDATE`.

Actual guarded-merge SHA protected-main 14/14 PASS:
`GO / ACP216_DB_1_7_0_ADOPTED`.

Only the latter formally unblocks the authority prerequisite for PIQB B2.
