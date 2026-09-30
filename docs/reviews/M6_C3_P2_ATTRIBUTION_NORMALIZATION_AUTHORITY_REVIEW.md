# M6 C3 P2 Attribution / Normalization Authority Review

## Identity

- Tracking issue: #151
- Program anchor: #149
- Change class: C3 - P2 implementation semantic contract
- Candidate authority: `P2_ATTRIBUTION_NORMALIZATION_AUTHORITY` v1.0.0
- Candidate authority SHA-256: `1bfc6c9eb8e2142249c327af5698bc6a8925f983fd8363b1d2bd835966eea5fa`
- Parent protected-main SHA: `8d23ef2e82e8d6dfe241e66fb4e630cc1f25f4f6`
- Parent protected-main Run: #480 / `36640903256` / 14 of 14 PASS
- Parent baseline lock SHA-256: `be54a16d2f33aca73f0686ffe09414045611fa4ad4c452e0e57ca96e460736d8`
- Candidate baseline lock SHA-256: `7eafadbb1d47297688595a8a0c48d4836dad13e040f76340ce2c0fa38a5547fa`
- DB schema: 1.6.0 unchanged
- Controlled artifacts: 24 -> 25

## Decisions frozen

1. P1 observations remain the immutable observed-fact layer and may never be overwritten by P2.
2. P2 consumes only exact published/immutable P1 observation projections; current/latest/default identity resolution is forbidden.
3. Factor feature specs are exact sealed `registry.context_artifact` identities using existing kind `ASSESSMENT_PROFILE`, exact logical-key prefix `P2_FACTOR_FEATURE_SPEC:` and schema `TPAA_P2_FACTOR_FEATURE_SPEC_V1`; id/version/hash enter the P2 input identity.
4. Reference conditions are exact sealed `registry.context_artifact` identities using existing kind `REFERENCE_SET`, exact logical-key prefix `P2_REFERENCE_CONDITION:` and schema `TPAA_P2_REFERENCE_CONDITION_V1`; `reference_condition_id` is the context-artifact identity.
5. Cohorts are frozen `registry.dataset_snapshot` products of type `P2_ATTRIBUTION_COHORT`; the target observation and target episode are excluded.
6. Cohort comparability includes capability, metric semantic/version, unit, aircraft model and comparison-key identity. Raw record, observation, independent-subject and effective-evidence counts remain distinct.
7. Attribution spec and model plugin id/version are exact values supplied by a sealed `registry.context_artifact` using existing kind `ASSESSMENT_PROFILE`, logical-key prefix `P2_ATTRIBUTION_SPEC:` and schema `TPAA_P2_ATTRIBUTION_SPEC_V1`; implementation defaults are forbidden.
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

## Pre-adoption schema-compatibility correction

The first exact-head candidate exposed a governance gap during post-merge static review: it named three P2-specific `registry.context_artifact.artifact_kind` values that are not allowed by the DB 1.6.0 CHECK constraint. The candidate was therefore **not** treated as complete even though Run #479 passed.

This corrective candidate preserves schema 1.6.0 by mapping P2 subtypes onto existing allowed kinds:
- factor feature spec -> `ASSESSMENT_PROFILE` + exact P2 logical-key prefix/schema;
- reference condition -> `REFERENCE_SET` + exact P2 logical-key prefix/schema;
- attribution spec -> `ASSESSMENT_PROFILE` + exact P2 logical-key prefix/schema.

Validator and contract tests now derive-check these artifact kinds against `CORE_LOGICAL_MODEL.json`, so a future authority/DB enum mismatch fails CI before adoption.
