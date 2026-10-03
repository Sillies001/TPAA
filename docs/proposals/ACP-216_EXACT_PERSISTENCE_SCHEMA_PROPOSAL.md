# ACP-216 — Exact persistence completeness beyond DB 1.6.0

**Status:** PROPOSED / NOT ADOPTED  
**Candidate schema version:** 1.7.0  
**Current authority remains:** CB-1.4.0 / DB 1.6.0

This document is an implementation-ready proposal only. It does **not** modify Canonical authority, BASELINE_LOCK, migration history, or runtime admission.

## Design choice

Use additive, semantically named companion relations instead of hiding missing fields inside unrelated JSONB, audit payloads, or arbitrary object blobs. Existing 1.6.0 tables remain the authority for the fields they already own; new relations own only the qualified revision/request/link semantics that 1.6.0 cannot represent.

The proposal adds:
- P2 release/reason/request bindings;
- a reusable restart-durable mutation idempotency relation;
- first-class P4 subject context plus assessment revision/annotation membership;
- first-class P5 composition plus participant and mission-revision metadata;
- P6 forecast/counterfactual request authority and revision metadata;
- P6 model profile bindings and recommendation lineage/constraints.

The exact field list, types, references and blocker coverage are machine-readable in `ACP-216_EXACT_PERSISTENCE_SCHEMA_PROPOSAL.json`.

## Migration discipline

This would be the first real governed schema transition in the repository. Adoption must create the first real migration revision, update Canonical authority and BASELINE_LOCK, generate deterministic SQLite/PostgreSQL bootstrap projections, and prove upgrade/restart/recovery/parity.

The transition is additive. Existing 1.6.0 data is not backfilled with fabricated P2/P4/P5/P6 values. New 1.7.0 writes remain disabled until the migrated database verifies exact schema/provenance. Downgrade is allowed only while all new authority relations are empty; once 1.7.0 data exists, rollback must use governed backup/restore or forward recovery.

## Non-negotiable invariants

No current/latest fallback for historical reads. No shadow schema. No weakening of P1-P6 admission, claim levels, privacy, separation of duties, or P6 training-only/non-causal restrictions. No B3 source/data-plane work is pulled into this authority proposal.
