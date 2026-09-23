# M1 Rolling Detailed-Design Runway

## Purpose

This plan defines how TPAA should combine implementation with forward detailed design after M1 admission.

It is intentionally **not** a full M2 detailed design. SDIB-1.0.1 §19.2 step 23 states that M2 backlog refinement is allowed only after the M1 Exit Review is GO. Before that gate, M2 work is limited to design seeds: interfaces, risks, ADR questions, evidence needs, and dependency pressure that should be captured early without freezing speculative semantics.

Machine plan: `docs/planning/M1_DESIGN_RUNWAY.json`.

## Design cadence

Use a rolling runway:

```text
current implementation wave
        +
next wave detailed design
        +
M2 design seeds only
```

The target is approximately **one M1 construction wave of detailed-design lead**.

A wave should not begin implementation until its own detailed design is implementation-ready. While that wave is being built and tested, the next wave's detailed design should advance in parallel.

This avoids both failure modes:

- coding without enough downstream design, which creates rework at interfaces;
- fully designing M2/M3 too early, which freezes assumptions before M1 evidence exists.

## Before M1 admission

Planning and design are allowed; M1 feature implementation is not.

The immediate pre-admission design focus is:

1. `BF_M1_NOMINAL_V1` contract, manifest lifecycle and human-recalculable expected skeleton;
2. Data Spine boundaries from Synthetic Source through Evaluation Context;
3. Basic Flight Episode and `BASIC_FLIGHT_V1` Stage-boundary design;
4. minimal World product identity/hash/evidence model;
5. MetricContext and staging contract;
6. Release/API/GUI first-E2E interfaces;
7. replay/failure/platform evidence matrix.

No feature code may be counted as M1 progress before the Entry activation artifact states `M1_ADMITTED`.

## M1-A → M1-B

### Implement

M1-A Transition & Fixture Contract:

- `M1-TST-001`;
- fixture schema/lifecycle;
- minimum `BF_M1_NOMINAL_V1` source payload;
- independently reviewable expected skeleton.

### Design in parallel

Prepare M1-B Data Spine:

- Synthetic Source Adapter contract;
- Source Registry identity/version behavior;
- Session Time normalization;
- Aircraft Entity identity;
- Canonical channel projection;
- Evaluation Context lineage and quality.

Do not design Metrics as though they may bypass these upstream products.

## M1-B → M1-C

### Implement

`M1-DATA-001..007`.

### Design in parallel

Prepare Episode / Stage / World:

- Basic Flight Episode start/end and invalidation rules;
- official marker handling;
- four `BASIC_FLIGHT_V1` Stage boundaries;
- precedence/revision/boundary/quality behavior;
- Stage Golden review basis;
- minimal P1 World product;
- logical hash and Evidence refs.

Stage Golden must be stable before downstream Metric integration can claim vertical-slice progress.

## M1-C → M1-D / M1-E

### Implement

Episode / Stage / World and Stage Golden.

### Design in parallel

Prepare:

- MetricContext builder;
- Metric staging lifecycle;
- AIR-001 reference calculation and eligibility;
- Observation identity;
- immutable SESSION Release;
- publish CAS/idempotency;
- minimum query API;
- GUI read flow from Session Browser through Evidence.

The objective is the first narrow published E2E:

```text
BF_M1_NOMINAL_V1
→ AIR-001
→ Observation
→ SESSION Release
→ API
→ GUI / Evidence
```

## M1-D / M1-E → M1-F

Once AIR-001 is stable and the first published E2E closes, design the remaining representative Metric paths before implementing all of them:

- AIR-002 ordinary numeric path;
- AIR-003 heading unwrap + `DERIVATIVE_LLS_V1`;
- AIR-004 upstream series + rolling median + sustained dwell;
- AIR-007 structured value + partial-channel status;
- GAP / ANGLE_WRAP / STRUCTURED_PARTIAL / STAGE_BOUNDARY expected results.

AIR-004 and AIR-007 remain formally assigned to later Catalog delivery milestones; M1 integration must not rewrite that authority.

## M1-F → M1-G

While the five representative Metric paths are being completed, design:

- historical read with frozen refs;
- replay under changed current profiles/registries;
- Release immutability;
- idempotency race behavior;
- corrupt/missing/version-mismatch failure closure;
- DB write-denial behavior;
- SQLite/PostgreSQL parity;
- Windows/Linux logical-equivalence evidence.

## M1-G → M1-H

While replay/failure/platform work is executing, prepare:

- M1 clean-workspace reconstruction;
- full M1 cold-start evidence;
- Exit aggregation;
- §24 review checklist;
- unresolved risk register.

At this stage M2 **design seeds** may become richer, but they remain non-authoritative until M1 Exit GO.

## What may be designed for M2 before M1 Exit GO

Allowed:

- interfaces that future RADAR/IRST/ESM/DL/FUS products will need to consume;
- architectural pressure discovered in M1;
- candidate ADR questions;
- expected evidence and testing needs;
- dependency/schema risks that should be investigated early;
- compatibility constraints that M1 must not accidentally make impossible.

Not allowed:

- starting M2 feature implementation;
- claiming M2 Task completion;
- freezing detailed M2 backlog as implementation authority;
- adding RADAR/IRST/ESM/DL/FUS to the M1 vertical slice;
- changing Canonical/Metric/Stage authority merely to satisfy speculative M2 needs.

## Formal handoff to M2 design

The formal transition is:

```text
M1-H complete
→ §24 M1 Exit Review
→ GO
→ M2 backlog refinement / detailed-design expansion
```

Therefore the operating rule is:

**M1 implementation and one-wave-ahead M1 detailed design run in parallel; M2 receives only bounded design seeds until M1 Exit GO.**
