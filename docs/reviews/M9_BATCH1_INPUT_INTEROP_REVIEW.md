# M9 Batch 1 — P6 Input / Interoperability Review

## Qualification entry

- Tracker: #195
- C3 tracker: #194 — COMPLETE
- Qualified protected-main entry SHA:
  `7628e6caad30f76179d7fbfcf8e600ef80ccc314`
- Protected-main Run #531 / `36952909234`: exactly 14/14 SUCCESS
- DB schema: 1.6.0 unchanged
- P1-P5: immutable admitted upstream products
- P6: NOT ADMITTED

## Implemented task scope

This batch implements the dependency-closed substrate for:
- `M9-GOV-001` — consumed qualified C3 runtime authority;
- `M9-DATA-001` — exact leakage-safe input/request substrate;
- `M9-INTEROP-001` — exact Joint/LVC/external interoperability snapshots.

No model family, prediction formula, calibration threshold, forecast result,
counterfactual result, recommendation engine, or external P6 admission is
implemented here.

## Runtime governance

`tpaa_context.p6_governance` projects the protected-main C3 authority into
runtime guards:
- exact identity and UUID validation;
- CURRENT/LATEST/DEFAULT rejection;
- Canonical UTF-8 sorted-key/no-NaN logical hashing;
- explicit UTC knowledge-time handling;
- unavailable/OOD/not-identifiable numeric non-coercion;
- P1-P5 immutability;
- P6 claim/release denied until exact protected-main M9 Exit GO evidence.

## Leakage-safe input and request binding

`tpaa_capability.p6_input` provides:
- exact published P4/P5 factual source bindings;
- optional exact P3 model references;
- exact scenario/context references;
- explicit SUBJECT/COMPOSITION/MISSION scope;
- forecast-origin and as-of cutoff;
- rejection of future, target-outcome and post-horizon leakage;
- deterministic `P6_INPUT_SHA256:` snapshot identity;
- deterministic forecast request binding covering target/horizon,
  capability-model reference, model profile, training/validation snapshots and
  assumption profile;
- deterministic counterfactual request binding covering exact factual
  baseline, scenario, intervention, held-fixed assumptions, model references
  and applicability profile;
- train/validation identity overlap rejection.

These request bindings are structural only. They do not authorize or execute a
model or counterfactual computation.

## Joint/LVC interoperability

`tpaa_ingest.p6_interop` provides deterministic snapshots binding:
- LIVE/SIM/LVC session;
- source/source-stream/artifact identity;
- producer;
- exact external profile/version;
- exact adapter/version;
- explicit unit/time basis;
- FACT_SOURCE versus P6_PROJECTION classification;
- canonical entity/relation references and object hashes;
- applicability, uncertainty, release state and as-of;
- deterministic `P6_INTEROP_SHA256:` identity.

Unversioned aliases, future source availability, lossy phase mapping,
fact/projection conflation and pre-Exit external P6 release fail closed.

## Batch boundary

Batch 1 must still pass exact-head Hosted CI 14/14, guarded merge, verified
merge parents and protected-main exact merge-SHA 14/14 before #195 is COMPLETE.

P6 remains NOT ADMITTED after Batch 1. Admission is reserved exclusively for
M9 Exit / C4.
