# M9 Batch 4 Exit / C4 P6 Admission Review

## Identity

- Tracker: #198
- Program: #149
- Task: M9-EXIT-001
- Protected-main prerequisite: `87e99b4ea3e55b60ef29a45adfc5e6ad7946bc0e`
- Prerequisite Run: #546 / `36993939363` / push / main / exactly 14/14 SUCCESS
- DB schema: 1.6.0 unchanged
- Canonical business authority: CB-1.4.0
- Candidate transition: P6 only; P1-P5 historical products remain immutable

## Qualified upstream chain

The Exit review requires exact closed governance evidence for:

- SDIB-1.8 baseline #193 — protected-main `ffbd5e5f0561ce39d8736de765dd6be240edfae1`, Run #529 / `36876431677`;
- C3 P6 authority #194 — protected-main `7628e6caad30f76179d7fbfcf8e600ef80ccc314`, Run #531 / `36952909234`;
- Batch 1 #195 — protected-main `47858360a8409fa9370a4e622f3dc3b308593fdc`, Run #535 / `36960346928`;
- Batch 2 #196 — protected-main `d37a994d6efbaeec2d10022ec083015771c40152`, Run #542 / `36981630238`;
- Batch 3 #197 — protected-main `87e99b4ea3e55b60ef29a45adfc5e6ad7946bc0e`, Run #546 / `36993939363`.

The adopted execution profile is separately pinned to
`P6_P3_CAPABILITY_OLS_MAD_FORECAST:1.0.0`, protected-main
`9d6c70133e1994c5823bbe6efb499001b5aa697c`, Run #540 /
`36968525803`.

## Exit acceptance

M9 Exit validates all 15 frozen M9 tasks and requires:

- exact checked-out revision identity;
- exact 15/15 task inventory and deterministic task-evidence hashes;
- exact M8-qualified M9 entry evidence;
- #193-#197 closed with their protected-main qualification evidence;
- frozen P6 authority, role/privacy/release profile, execution profile, DTO and
  BASELINE_LOCK hashes;
- DB schema 1.6.0 and no shadow schema;
- exact P6 admission DTO and protected-main-only admission guard;
- retained Batch 1 leakage-safe input and Joint/LVC interoperability gates;
- retained Batch 2 deterministic model/applicability/uncertainty/forecast/replay
  gates;
- retained Batch 3 non-causal counterfactual, advisory, exact API/GUI and
  security gates;
- exact-ID transport with no current/latest/default alias, hidden
  recomputation or direct persistence;
- P1-P5 immutable upstream semantics and fact/projection separation;
- exactly 14 required Hosted CI jobs.

Any failed acceptance produces NO_GO and P6 remains unadmitted.

## Admission rule

A pull-request candidate may return PASS only as
`PENDING_PROTECTED_MAIN`. It cannot admit P6.

P6 is admitted only when the same Exit implementation is running on:

- event = `push`;
- git ref = `refs/heads/main`;
- expected revision = checked-out revision;
- all acceptance checks pass;
- required jobs success = required jobs total = 14.

Only that condition returns:

- decision = `GO`;
- `failed_acceptance=[]`;
- `p6_admitted=true`;
- qualification = `P6_M9_QUALIFIED`.

No Canonical artifact, DB migration, historical P1-P5 product, model formula,
counterfactual causal authority, recommendation policy or API/GUI business
behavior is changed by this Exit batch.

## CI topology

M9 Exit is attached to the existing final review job in
`.github/workflows/cross-platform-ci.yml`. It does not create a fifteenth
Hosted CI job. The externally observed exact-head 14/14 result remains the only
merge and formal admission authority.
