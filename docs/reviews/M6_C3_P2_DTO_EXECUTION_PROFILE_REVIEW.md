# M6 C3 P2 Cross-layer DTO / Execution Profile Review

## Identity

- Tracking issue: #161
- Program anchor: #149
- Batch 2 tracker: #158
- Profile design issue: #159
- Change class: C3 - cross-layer DTO and deterministic execution profile
- Parent protected-main SHA: `2a2b0907515761c3768bc952cf97894825e05109`
- Parent protected-main Run: #484 / `36650776582` / 14 of 14 PASS
- Parent BASELINE_LOCK SHA-256: `7eafadbb1d47297688595a8a0c48d4836dad13e040f76340ce2c0fa38a5547fa`
- Candidate BASELINE_LOCK SHA-256: `f95167aca59dc993ced607e55f21f01080c4e24cc0759bf97482d49654ea182b`
- Cross-layer DTO SHA-256: `9d94f75031afcbfe2391bed1245c3f8d95f124a6549a8f116aa1efb879ae45b4`
- Execution profile SHA-256: `202e255bd09349407e0e7cc4d77d8b848df99d84dc00e50e46871eb4f82f0d68`
- Controlled artifacts: 25 -> 26
- DB schema: 1.6.0 unchanged

## DTO closure

The central `CROSS_LAYER_DTO_CONTRACTS` now carries the exact five P2 DTO field sets
already frozen by `P2_ATTRIBUTION_NORMALIZATION_AUTHORITY`:

- `P2EligibleObservationDTO`
- `FactorFeatureSetDTO`
- `AttributionRunDTO`
- `AdjustedCapabilityEstimateDTO`
- `P2AdmissionStateDTO`

Each field now has an exact source, requiredness and transport type. P1 knowledge time
is the exact published Release time; metric semantic id/version come through the exact
immutable metric-instance/definition chain. The numerical execution profile accepts only
finite numeric P1 observations.

The Core semantic version is an integer. The Batch 1 substrate is aligned accordingly;
cohort comparability uses integer `metric_semantic_version`, not the string `"1"`.

## Execution profile

`P2_LINEAR_REFERENCE_ADJUSTMENT:1.0.0` freezes:

- runtime attribution spec logical key
  `P2_ATTRIBUTION_SPEC:P2_LINEAR_REFERENCE_ADJUSTMENT`;
- plugin `LINEAR_REFERENCE_ADJUSTMENT:1.0.0`;
- exact factor, row, subject and jackknife ordering;
- subject-balanced row weighting;
- Decimal precision 50 / ROUND_HALF_EVEN;
- output quantum `1E-12`;
- no imputation, random sampling, regularization, factor dropping or solver fallback;
- deterministic two-pass modified Gram-Schmidt QR;
- zero-scale tolerance `1E-24`;
- rank-ratio minimum `1E-10`;
- inclusive zero-tolerance target/reference support;
- model-conditioned association factor effects;
- leave-one-independent-subject-out 95% jackknife uncertainty;
- explicit NOT_IDENTIFIABLE fail-closed reason semantics;
- canonical model-artifact hashing and exact-release replay;
- deterministic UUIDv5 namespaces derived from RFC 4122 NAMESPACE_URL.

These values are engineering execution semantics, not capability pass/fail thresholds.

## Code generation

Because the central DTO registry is a codegen source, the candidate regenerates
`src/tpaa_generated/dto.py` and updates its manifest source/output hashes. The DTO
generator gains only one transport construct, `number?`, mapped to
`int | float | None` for nullable P2 numeric fields.

## Non-goals

- no attribution engine implementation in this C3;
- no production business factor taxonomy;
- no P2 admission;
- no P3 implementation/admission;
- no schema migration or shadow schema;
- no change to historical P1 Release/replay semantics.

## Adoption gate

The candidate remains inactive until its exact PR head passes all 14 required Hosted CI
jobs, merges with expected-head protection, and the actual merge SHA passes protected-main
push CI 14/14. Batch 2 implementation starts only from that qualified protected-main SHA.
