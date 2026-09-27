# SDIB-1.2 Adoption / M3 Refinement Review

## Review identity

- **Change class:** C1 — SDIB implementation contract / post-M2 backlog refinement.
- **Candidate implementation baseline:** SDIB-1.2.
- **Parent implementation baseline:** SDIB-1.1.
- **Tracking issue:** #110.
- **Source design package:** TPAA V8.0 / ED-2.0 Rebaseline R3.3.
- **Core baseline:** CB-1.4.0.
- **DB schema:** 1.6.0.
- **SDIB-1.2 document SHA-256:** `97676e0c5d8eb6ce6ad3a0de4a347fd3023cf23069674c60bd11cea941fffd71`.
- **M3 task manifest SHA-256:** `ba4d810d06466aaf394c5260fca123eb117645789d107112be4e89620fa35934`.

## M2 Exit authority for refinement

M3 task-level refinement is admitted only because M2 Exit is GO on protected main:

- M2 Exit Issue: #99 — closed after protected-main verification;
- Batch 4 PR #109 exact candidate head: `c9dbd006868966414e899d16ca588e1ea5da032b`;
- merge/protected-main SHA: `9ed7754fdc5362cd3ea3896a65fc0f5a597c6381`;
- protected-main Run #338 / Actions run `36302102143`: PASS;
- `TPAA_M2_EXIT_REVIEW_V1`: `status=PASS`, `decision=GO`, `protected_main_exact=true`;
- 27/27 M2 Tasks PASS; `failed_acceptance=[]`; no unresolved authority/blocker risk.

This evidence admits M3 backlog refinement. It does not pre-complete any M3 Task.

## Authority boundary

SDIB-1.2 creates implementation Task IDs, dependencies, batch boundaries and minimum
acceptance for M3. It does **not** rewrite CB-1.4.0 machine-readable business authority.
Metric codes, semantics, formulas, Stage definitions, DTO contracts, Core schema,
publication routes, observation lanes, value kinds and family applicability remain
owned by frozen Canonical artifacts.

## Exact M3 Catalog derivation

The frozen Catalog contains exactly 84 entries with both:

- `delivery_milestone=M3`
- `delivery_batch=P1_REMAINDER_84`

Breakdown:

- AIR remainder: 36
- TRK: 7
- ID: 12
- PSV: 7
- ESM: 6
- DL: 8
- FUS: 8
- Total: 84

With the already-qualified `P1_FOUNDATION_32`, the executable P1 total is exactly 116.

## Stage and applicability boundary

M3 consumes exactly four frozen Stage profiles: BASIC_FLIGHT_V1, WVR_ENGAGEMENT_V1,
BVR_KILL_CHAIN_V1 and STRIKE_MISSION_V1. Family applicability is consumed directly from
the Catalog: AIR subject type; TRK/ID product capabilities; PSV IRST/EO; ESM RWR/ESM;
DL DATALINK; FUS FUSION.

## Task and batch refinement

SDIB-1.2 freezes 28 M3 implementation Tasks:

- WORLD: 5
- METRIC: 9
- OBSERVATION: 3
- API: 2
- GUI: 3
- TEST: 6

They are partitioned exactly once into four coarse batches:

1. Four-training World/Event + fixture foundations
2. General Metric expansion + P1_REMAINDER_84
3. Publication + API + GUI product closure
4. Golden / parity / cold-start / Exit

The machine-readable mirror is `docs/baseline/SDIB-1.2/M3_TASK_BASELINE.json` and is
contract-tested against Markdown, Catalog, Milestone and Stage authority.

## Adoption decision

Candidate decision: **GO_FOR_PR**.

SDIB-1.2 becomes the active implementation baseline only if:

1. the exact candidate PR head passes Hosted CI;
2. the exact candidate is merged without head drift;
3. the protected-main push run for the actual merge SHA passes;
4. post-merge evidence confirms the SDIB-1.2 contract tests on the exact merged SHA.

Until those conditions pass, #110 remains open and no M3 execution batch may write product code.

After protected-main adoption PASS, #110 may be completed and #85 may create the four
M3 execution-batch Issues from the frozen `M3_TASK_BASELINE.json`; M4 remains gated.
