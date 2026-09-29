# M6 C3 P2 Attribution / Normalization Authority Review

## Identity

- Tracking issue: #151
- Program anchor: #149
- Change class: C3 - P2 implementation semantic contract
- Candidate authority: `P2_ATTRIBUTION_NORMALIZATION_AUTHORITY` v1.0.0
- Candidate authority SHA-256: `a2bc9d4e68366214002a3b391e1b9764db520bfff123c095967043a8d9990f01`
- Parent protected-main SHA: `b6afa0a21388dea38c58ff1ac8f091d3be5c60a7`
- Parent protected-main Run: #478 / `36588646293` / 14 of 14 PASS
- Parent baseline lock SHA-256: `e4f6c2bb97c169cc8db9eecfa09c67201510b5fad85e6e59fc2b96532b011db9`
- Candidate baseline lock SHA-256: `be54a16d2f33aca73f0686ffe09414045611fa4ad4c452e0e57ca96e460736d8`
- DB schema: 1.6.0 unchanged
- Controlled artifacts: 24 -> 25

## Decisions frozen

1. P1 observations remain the immutable observed-fact layer and may never be overwritten by P2.
2. P2 consumes only exact published/immutable P1 observation projections; current/latest/default identity resolution is forbidden.
3. Factor feature specs are exact sealed `registry.context_artifact` identities of kind `P2_FACTOR_FEATURE_SPEC`; id/version/hash enter the P2 input identity.
4. Reference conditions are exact sealed `registry.context_artifact` identities of kind `P2_REFERENCE_CONDITION_SPEC`; `reference_condition_id` is the context-artifact identity.
5. Cohorts are frozen `registry.dataset_snapshot` products of type `P2_ATTRIBUTION_COHORT`; the target observation and target episode are excluded.
6. Cohort comparability includes capability, metric semantic/version, unit, aircraft model and comparison-key identity. Raw record, observation, independent-subject and effective-evidence counts remain distinct.
7. Attribution spec and model plugin id/version are exact values supplied by a sealed `P2_ATTRIBUTION_SPEC`; implementation defaults are forbidden.
8. `NOT_IDENTIFIABLE` is a valid governed product. It requires null adjusted value and an exact governed reason code; no synthetic value may be emitted merely to produce a number.
9. Uncertainty method/level come only from the exact attribution spec; no implementation default is permitted.
10. Factor contributions are `MODEL_CONDITIONED_ASSOCIATION` unless independent causal evidence is explicitly bound. Unsupported causal labels fail closed.
11. Every input is checked against an explicit as-of time; future information and same-episode leakage fail closed.
12. P2 published/history queries bind exact immutable Release/evidence identities and never fall back to current/latest. Retrospective recomputation creates new identities.
13. Authority adoption alone does not admit P2. External P2 claims remain blocked until protected-main M6 Exit GO with all 14 required jobs. P3-P6 remain inactive.

## Existing-schema realization

No table is added or changed. The authority maps to existing schema 1.6.0 carriers:

- `metric.capability_observation`
- `assessment.factor_feature_set`
- `assessment.attribution_run`
- `capability.adjusted_capability_estimate`
- `registry.context_artifact` + `registry.object_reference`
- `registry.dataset_snapshot`
- `metric.evidence_set` + `registry.analysis_release`

## Batch 1 implementation surface

The candidate also adds transport-neutral `tpaa_assessment` substrate that:

- projects immutable P1 eligibility;
- validates factor/reference/attribution-spec exact bindings;
- validates frozen comparable cohorts and evidence-count independence;
- rejects future-information and same-episode leakage;
- computes deterministic P2 input identity;
- enforces P1 no-overwrite, causal-evidence and capability-admission guards;
- validates `NOT_IDENTIFIABLE` without running an attribution algorithm.

No attribution model, adjusted-value computation or P2 admission is implemented by this batch.

## Adoption gate

The authority and Batch 1 substrate remain candidates until the exact branch head passes Hosted CI, merges with expected-head protection, and the actual merge SHA passes protected-main CI. #151 closes only after that evidence.
