# M9 / SDIB-1.8 Task Baseline Adoption Review

## Identity

- Program: #149
- M9/P6 design runway: #186
- Baseline tracker: #193
- C3 authority tracker: #194
- Batch 1: #195
- Batch 2: #196
- Batch 3: #197
- Batch 4 / Exit: #198
- Candidate file: `docs/baseline/SDIB-1.8/M9_TASK_BASELINE.json`
- Entry protected-main SHA: `06b9f0c55dda803765fc265b8d5ca0353620476f`
- Entry qualification: Run #527 / `36869057230` / exactly 14/14 SUCCESS / `P4_P5_M8_QUALIFIED`
- DB schema: 1.6.0 unchanged
- Canonical business authority: CB-1.4.0

## Adoption intent

This candidate turns the completed M9/P6 design runway into an executable staged-governance task baseline. It does not adopt a prediction formula, model family, counterfactual causal rule, recommendation policy, interoperability mapping or role rule; those remain fail-closed until C3 #194 freezes exact authority.

P1-P5 remain immutable admitted upstream products. P6 is only a candidate capability phase until protected-main M9 Exit GO.

## Runway-to-baseline reconciliation

The M8-era #186 runway proposed 13 candidate tasks. During formal baseline adoption the canonical `DEVELOPMENT_MILESTONE_REGISTRY.json` was rechecked. M9 requires both `WS-INTEROP` and `WS-ASSESS`, but the 13-task candidate list had no explicit carrier for either workstream.

SDIB-1.8 therefore adds:
- `M9-INTEROP-001` — exact Joint/LVC/external interoperability snapshot contract;
- `M9-ASSESS-001` — governed recommendation/advisory revision and approval boundary.

The formal candidate contains 15 tasks. This closes a workstream-coverage gap without widening P6 beyond the already-frozen Canonical M9 objective.

## Task structure

### Batch 1 — authority + leakage-safe input + interoperability
- M9-GOV-001
- M9-DATA-001
- M9-INTEROP-001

C3 #194 is the fail-closed authority blocker. No dependent P6 implementation may claim completion until it is protected-main qualified.

### Batch 2 — model + applicability + forecast + replay
- M9-MODEL-001
- M9-MODEL-002
- M9-PROJ-001
- M9-LONG-001
- M9-TST-001

Forecast remains a projection. Model executability does not imply product validity when applicability/calibration gates fail.

### Batch 3 — counterfactual + recommendation + publication/security
- M9-CF-001
- M9-ASSESS-001
- M9-API-001
- M9-GUI-001
- M9-SEC-001
- M9-TST-002

Counterfactuals require explicit assumptions/interventions and adopted identifiability authority. Recommendations remain advisory products, never facts or commands. Exact IDs, role/privacy and P1-P5 provenance remain mandatory.

### Batch 4 — M9 Exit
- M9-EXIT-001

Only protected-main exact M9 Exit GO may admit P6.

## Frozen boundaries

The candidate explicitly forbids:
- current/latest/default source or model resolution;
- hidden source recomputation/substitution;
- future, same-episode or outcome leakage;
- fact/projection conflation;
- unsupported causal upgrades;
- unavailable/OOD/not-identifiable to zero coercion;
- recommendation-to-fact or recommendation-to-command upgrade;
- unversioned/lossy Joint/LVC external aliases;
- mutation of published P1-P5 products;
- direct identity exposure outside authorized projection;
- implementation-local model formula, threshold, causal rule or role rule invention.

## Storage / schema

DB schema remains 1.6.0 and shadow schemas are forbidden. A future schema change is allowed only through an explicit authority decision proving the existing frozen schema cannot represent an adopted requirement; implementation cannot create a private workaround.

## Baseline self-check

- declared task_count = 15;
- actual task count = 15;
- all task IDs unique;
- four batches cover every task exactly once;
- C3 blocker list covers all 14 dependent tasks;
- canonical M9 required workstreams all have explicit task carriers;
- entry evidence binds exact M8-qualified protected-main SHA and Run #527;
- no M10/P7 roadmap is invented because the current canonical roadmap ends at M9/P6.

## Adoption gate

This file remains a candidate until:
1. exact branch/PR head passes Hosted CI exactly 14/14;
2. PR head == branch ref == qualified Run head;
3. PR base == current main, behind=0 and mergeable=true;
4. guarded merge uses exact `expected_head_sha`;
5. actual merge parents are verified;
6. protected-main exact merge SHA passes Hosted CI exactly 14/14.

Only then may #193 close as adopted, #186 close as consumed design runway, and #194 C3 implementation proceed from the exact qualified protected-main SHA.
