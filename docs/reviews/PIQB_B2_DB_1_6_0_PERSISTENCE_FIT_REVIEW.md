# PIQB B2 — DB 1.6.0 Persistence Fit Review

## Decision

Full P2–P6 product persistence is **BLOCKED pending an Authority Change Proposal**.

This is not a failure of the existing M0–M9 capability qualifications. The qualified runtime DTOs contain more exact historical/revision semantics than DB schema 1.6.0 can losslessly represent for P2, P4/P5 and P6.

B2 may continue on the non-blocked substrate: repository ports, SQLite/PostgreSQL release/object/CAS registration, object/Parquet sealing, restart/recovery, existing P1/longitudinal wiring, and P3 persistence where all derivations are exact and pinned.

## Fail-closed rule

A field is persistable only when it is:
1. directly stored in an authorized DB 1.6.0 relation;
2. deterministically derivable from another exact authoritative relation or frozen execution profile; or
3. stored in an object/snapshot payload that the existing canonical schema explicitly authorizes for that semantic purpose.

Audit payloads, unrelated JSONB columns, and ad-hoc full-revision object blobs are not permitted to become shadow authority.

## Result by product family

- P1 session release — FIT_EXISTING.
- Longitudinal release — FIT_EXISTING_SUBSTRATE.
- P2 attribution — BLOCKED.
- P3 twin/capability — FIT_WITH_DERIVATIONS.
- P4/P5 assessment — BLOCKED.
- P6 model/projection/advisory — BLOCKED.

The machine-readable field-level findings are frozen in `B2_SCHEMA_PERSISTENCE_FIT.json`.

## Required governance action

Open a separate Authority Change Proposal to define the minimal additive canonical schema needed for exact P2/P4/P5/P6 historical reconstruction. Until that proposal is approved and independently qualified, B2 domain adapters for blocked families must fail closed and may not invent tables, columns, hidden JSON layouts, or object-file shadow records.
