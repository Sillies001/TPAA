# SDIB-1.1 Adoption / M2 Refinement Review

## Review identity

- **Change class:** C1 — SDIB implementation contract / post-M1 backlog refinement.
- **Candidate implementation baseline:** SDIB-1.1.
- **Parent implementation baseline:** SDIB-1.0.1.
- **Tracking issue:** #94.
- **Source design package:** TPAA V8.0 / ED-2.0 Rebaseline R3.3.
- **Core baseline:** CB-1.4.0.
- **DB schema:** 1.6.0.
- **SDIB-1.1 document SHA-256:** `ba6cfd3765c53fec7ea322b2ec964ee78f09392d1e6a1e32d9754584b71132fe`.
- **M2 task manifest SHA-256:** `733b4180ad6941ca1361e1a5857c802e698ad69351b07cf9c591c80045a63d4b`.

## M1 Exit authority for refinement

M2 task-level refinement is admitted only because M1 Exit is GO on protected main:

- M1 Exit Issue: #88 — closed after protected-main verification;
- PR #93 exact candidate: `21895335f2bdd0edfb6b21d7f54dc2e84360655f`;
- merge/protected-main SHA: `e96358c1060aa176d784bbaa291c999b7a859a7d`;
- protected-main Run #172 / Actions run `36097766180`: PASS;
- `TPAA_M1_EXIT_REVIEW_V1`: `status=PASS`, `decision=GO`, `protected_main_exact=true`;
- 56/56 M1 Tasks PASS; `failed_acceptance=[]`; `unresolved_risks=[]`.

This evidence admits M2 backlog refinement. It does not pre-complete any M2 Task.

## Authority boundary

SDIB-1.1 creates implementation Task IDs, dependencies, batch boundaries and minimum
acceptance for M2. It does **not** rewrite CB-1.4.0 machine-readable business authority.
Metric codes, semantics, formulas, Stage definitions, DTO contracts, Core schema,
publication routes, observation lanes, value kinds and family applicability remain
owned by the frozen Canonical artifacts.

Any conflict between this implementation baseline and machine-readable authority must
fail closed and be corrected through a governed change; runtime code must not guess.

## Exact M2 Catalog derivation

The frozen Catalog contains exactly 32 entries with both:

- `delivery_milestone=M2`
- `delivery_batch=P1_FOUNDATION_32`

Breakdown:

- QA foundation: 8
- AIR formal M2 delivery: 3
- SNS detection/accuracy: 21
- Total: 32

`P1-SNS-*` remains `SYSTEM_TYPE_EXACT` with `allowed_system_types=[RADAR]`.
IRST/EO remain outside SNS applicability.

## Task and batch refinement

SDIB-1.1 freezes 27 M2 implementation Tasks:

- DATA: 5
- WORLD: 3
- METRIC: 7
- OBSERVATION: 3
- GUI: 3
- TEST: 6

They are partitioned exactly once into four coarse batches:

1. Data + World foundations
2. General Metric Engine + P1_FOUNDATION_32
3. Publication + GUI product closure
4. Golden / parity / cold-start / Exit

The machine-readable mirror is `docs/baseline/SDIB-1.1/M2_TASK_BASELINE.json` and is
contract-tested against both the Markdown baseline and frozen Catalog/Milestone authority.

## Adoption decision

Candidate decision: **GO_FOR_PR**.

SDIB-1.1 becomes the active implementation baseline only if:

1. the exact candidate PR head passes Hosted CI;
2. the exact candidate is merged without head drift;
3. the protected-main push run for the actual merge SHA passes;
4. post-merge evidence confirms the SDIB-1.1 contract tests on the exact merged SHA.

Until those conditions pass, #94 remains open and no M2 execution batch may start.

After protected-main adoption PASS, #94 may be completed and #85 may create the four
M2 execution-batch Issues from the frozen `M2_TASK_BASELINE.json`; M3 remains gated.
