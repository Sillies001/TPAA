# M8 / SDIB-1.7 Task Baseline Adoption Review

## Identity

- Program: #149
- M8 design runway: #170
- Baseline tracker: #180
- C3 authority tracker: #181
- Batch 1: #182
- Batch 2: #183
- Batch 3: #184
- Batch 4 / Exit: #185
- M9/P6 one-milestone-ahead design runway: #186
- Candidate file: `docs/baseline/SDIB-1.7/M8_TASK_BASELINE.json`
- Entry protected-main SHA: `c78604ade0aeffdbf7395fccfc0951751beae751`
- Entry qualification: Run #510 / `36807335564` / exactly 14/14 SUCCESS / `P3_M7_QUALIFIED`
- DB schema: 1.6.0 unchanged
- Canonical business authority: CB-1.4.0

## Adoption intent

This candidate turns the completed M8/P4-P5 design runway into an executable staged-governance task baseline without inventing P4/P5 metric formulas, thresholds, weights, role rules or assessment semantics that are not yet frozen by C3.

P1/P2/P3 remain exact immutable upstream evidence. P4 and P5 are candidate capability phases only. P6 remains inactive.

## Task structure

The candidate freezes 23 tasks in four coarse batches.

### Batch 1 — authority + subject/composition/privacy substrate

- M8-GOV-001
- M8-GOV-002
- M8-DATA-001
- M8-WORLD-001
- M8-WORLD-002
- M8-SEC-001
- M8-TST-001

The C3 authority in #181 is the fail-closed blocker. Dependent P4/P5 implementation cannot claim completion before exact authority adoption.

### Batch 2 — P4 individual/human-machine assessment

- M8-ASSESS-001
- M8-ASSESS-002
- M8-ASSESS-003
- M8-LONG-001
- M8-TST-002

The batch preserves machine evidence vs instructor annotation/approval separation and uses immutable revision/audit semantics.

### Batch 3 — P5 team/mission + publication/security

- M8-ASSESS-004
- M8-ASSESS-005
- M8-ASSESS-006
- M8-LONG-002
- M8-API-001
- M8-GUI-001
- M8-SEC-002
- M8-GOV-003
- M8-TST-003
- M8-TST-004

Team/mission products bind exact composition. Composition changes create new identity. Missing/unavailable/OOD evidence is explicit and never zero-filled. Aggregation may run only under an adopted exact profile/formula/weight/threshold authority.

M8-GOV-003 advances #186 so M9/P6 is refined one milestone ahead while P6 remains design-only.

### Batch 4 — M8 Exit

- M8-TST-005

Only protected-main exact M8 Exit GO may admit P4 and P5.

## Frozen boundaries

The candidate explicitly forbids:

- current/latest/default historical resolution;
- hidden P3 recomputation;
- OOD/unavailable/not-identifiable to zero coercion;
- P3 claim-level upgrade;
- direct identity exposure outside authorized projection;
- instructor overwrite of machine evidence or prior published decisions;
- composition drift under one identity;
- copying team results to individuals;
- pooling incompatible reference-condition/twin/configuration evidence without explicit authority;
- P6 activation during M8;
- implementation-local metric formula, threshold, weight or role-rule invention.

## Storage / schema

The candidate requires DB schema 1.6.0 and no shadow schema. If M8 C3 later proves that the existing logical/storage contract cannot represent an adopted requirement, that must be handled as an explicit separate schema authority decision; implementation must not create a private workaround.

## Baseline self-check

The candidate has been machine-checked before PR creation:

- declared task_count = 23;
- actual task count = 23;
- all task IDs unique;
- four batches cover every task exactly once;
- C3 blocker dependency list covers every task except the blocker itself;
- required M8 workstreams match DEVELOPMENT_MILESTONE_REGISTRY;
- entry evidence binds the exact P3-qualified protected-main SHA and Run #510.

## Adoption gate

This file remains a **candidate** until:

1. its exact branch/PR head passes Hosted CI exactly 14/14;
2. PR head == branch ref == qualified Run head;
3. PR base == current main, behind=0 and mergeable=true;
4. guarded merge uses exact expected_head_sha;
5. actual merge parents are verified;
6. the protected-main exact merge SHA passes Hosted CI exactly 14/14.

Only then may #180 close as adopted and #181 C3 implementation proceed from that exact qualified protected-main SHA.
