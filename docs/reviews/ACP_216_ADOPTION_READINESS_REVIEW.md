# ACP-216 Adoption Readiness Review

**Scope:** independent readiness gate only  
**Current authority:** CB-1.4.0 / DB schema 1.6.0  
**Candidate authority:** DB schema 1.7.0  
**Authority changed by this review:** no

## Purpose

This review adds a fail-closed machine gate before any authority adoption work may begin. It validates the frozen ACP-216 proposal against the current canonical model and baseline lock. Passing this gate means only that the proposal is internally ready for a separate authority-adoption change; it does not adopt DB 1.7.0, modify Canonical authority, create a migration, unblock PIQB B2, or authorize B3.

## Independent checks

The machine reviewer verifies:

- ACP identity/status remains `PROPOSED_NOT_ADOPTED`;
- current CORE_LOGICAL_MODEL and BASELINE_LOCK remain DB 1.6.0 and the lock hash/byte count matches the canonical file;
- candidate DB 1.7.0 remains explicitly not adopted;
- exactly 15 unique additive relation changes are proposed;
- proposed relation names do not already exist in the current canonical model;
- column names, primary keys, unique keys, foreign-key targets and non-null key semantics are structurally valid;
- all 13 current B2 persistence-fit blockers are covered exactly;
- every proposed relation has a non-empty duplicate-authority rationale;
- migration/rollback/parity discipline is present and consistent with `migrations/README.md`;
- Hosted CI inputs remain exact-head and exactly 14 required jobs.

## Gate semantics

A PASS emits:

- `decision=READY_FOR_ADOPTION`
- `qualification=ACP216_ADOPTION_READY`
- `authority_changed=false`
- `adoption_performed=false`
- `formal_b2_unblocked=false`
- `next_gate=SEPARATE_AUTHORITY_ADOPTION_CHANGE_REQUIRED`

Therefore a PASS cannot be interpreted as DB 1.7.0 authority or as PIQB B2 completion.

## After this gate

Only a separate governed authority-adoption change may update CORE_LOGICAL_MODEL, BASELINE_LOCK, deterministic SQLite/PostgreSQL projections and the first real migration. That later change must independently qualify exact historical reads, upgrade/rollback/recovery, parity, 14-job Hosted CI and protected-main authority before B2 can become eligible for GO.
