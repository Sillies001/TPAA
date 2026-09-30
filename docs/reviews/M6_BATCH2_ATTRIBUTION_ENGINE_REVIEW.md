# M6 Batch 2 Attribution Engine Review

## Identity

- Tracker: #158
- Program: #149
- Adopted execution-profile design: #159 (closed)
- Adopted central DTO/profile C3: #161 / PR #162 (closed)
- Protected-main prerequisite SHA: `047b4d03778243cf50b8825da52b4c6a85938710`
- Protected-main qualification: Run #487 / `36665607287` / push / main / 14 of 14 SUCCESS
- Development branch: `m6/batch-2-attribution-engine`
- DB schema: 1.6.0 unchanged
- Capability phase: P2 implementation only; P2 external admission remains blocked until M6 Exit GO

## Tasks implemented in this candidate

### M6-CAP-001 — Factor feature-set materialization

`materialize_factor_feature_set()` creates an immutable logical projection for
`assessment.factor_feature_set`:

- exact source P1 observation;
- exact sealed feature-spec id/version/hash;
- exact governed factor order;
- explicit nullable factor values and matching missing mask;
- canonical, unique World refs;
- computed structural coverage;
- governed confidence;
- exact canonical input hash;
- deterministic UUIDv5 identity from the adopted profile namespace;
- no mutation of the source P1 observation.

Missing features are materialized as evidence, not imputed. They may therefore produce a
valid feature-set product while later making an attribution result NOT_IDENTIFIABLE.

### M6-CAP-002 — Attribution execution and provenance

`execute_p2_attribution()` accepts only the protected-main
`P2_LINEAR_REFERENCE_ADJUSTMENT:1.0.0` runtime identity. The implementation reads
all numerical thresholds/namespaces from the controlled profile and fail-closes on
unsupported profile drift.

The execution path binds:

- exact P2 input-bundle hash;
- target feature-set input hash;
- exact frozen cohort snapshot/data hash and row identities;
- exact reference-condition identity/artifact hash and factor values;
- exact attribution spec/plugin/version;
- exact as-of time;
- model-conditioned association semantics.

The model artifact is canonical JSON with SHA-256 identity and contains every required
field in the adopted replay contract. `model_artifact_uri` remains null because this
batch does not invent a managed-object URI scheme.

### M6-CAP-003 — Identifiability

The engine returns a valid immutable NOT_IDENTIFIABLE product rather than raising a
numerical error when governed evidence/model conditions fail.

Implemented reasons:

- `INSUFFICIENT_EFFECTIVE_EVIDENCE`
- `REFERENCE_CONDITION_OUT_OF_SUPPORT`
- `COHORT_NOT_COMPARABLE`
- `FEATURE_COVERAGE_INSUFFICIENT`
- `MODEL_SPEC_DIAGNOSTIC_FAILURE`
- `UNCERTAINTY_NOT_ESTIMABLE`

Governed substrate errors still reject invalid identity, future-information leakage,
same-episode leakage and unsupported causal labeling.

A NOT_IDENTIFIABLE estimate has:

- `adjusted_value = null`;
- null residual;
- null uncertainty bounds;
- empty factor effects;
- non-empty governed reason codes;
- deterministic status-hash/run identity;
- no fabricated model artifact.

### M6-CAP-004 — Adjusted estimate

For identifiable executions the candidate produces a separate immutable logical
projection for `capability.adjusted_capability_estimate` with:

- source observation and source P1 Release identity;
- distinct P2 Release identity;
- exact attribution run/reference condition;
- context-adjusted value;
- per-factor model-conditioned contributions;
- target residual/unexplained component;
- 95% leave-one-independent-subject-out jackknife interval;
- ASSOCIATION_ONLY claim level;
- exact evidence-set binding;
- canonical logical hash and deterministic UUIDv5 estimate identity.

The source P1 observed value/Release remain unchanged.

## Numerical contract

The implementation follows the adopted machine profile:

- Python `Decimal`, precision 50, `ROUND_HALF_EVEN`;
- subject total weight exactly 1, split over its eligible rows;
- subject-balanced mean and RMS factor scaling;
- two-pass modified Gram-Schmidt QR in exact feature-spec order;
- no column pivoting;
- zero-scale tolerance `1E-24`;
- minimum QR diagonal ratio `1E-10`;
- no imputation, regularization, factor removal, alternate solver or RNG;
- inclusive zero-tolerance target/reference cohort support;
- `adjusted = observed + sum(beta_raw * (reference - target))`;
- residual = observed - model prediction at target;
- leave-one-independent-subject-out jackknife;
- fixed 95% z = `1.959963984540054`;
- output quantization `1E-12`.

## M6-TST-002 / M6-TST-003 qualification matrix

The committed synthetic qualification family covers all 14 frozen profile cases:

| Frozen case | Qualification |
| --- | --- |
| EXACT_LINEAR_NOMINAL | single-factor Golden: adjusted=15, residual=1, effect x=-2, CI=[15,15] |
| TWO_FACTOR_SUBJECT_BALANCED_NOMINAL | two-factor Golden: adjusted=14, residual=1 |
| ROW_ORDER_PERMUTATION_REPLAY_EQUAL | exact run/model/estimate identities equal after row reversal |
| REPEATED_ROWS_ONE_SUBJECT_WEIGHT_INVARIANT | duplicated row for one subject leaves estimate/effects unchanged |
| MISSING_REQUIRED_FACTOR_NOT_IDENTIFIABLE | FEATURE_COVERAGE_INSUFFICIENT |
| NON_COMPARABLE_COHORT_FAIL_CLOSED | COHORT_NOT_COMPARABLE |
| INSUFFICIENT_INDEPENDENT_SUBJECTS_NOT_IDENTIFIABLE | INSUFFICIENT_EFFECTIVE_EVIDENCE |
| RANK_DEFICIENT_FACTORS_NOT_IDENTIFIABLE | MODEL_SPEC_DIAGNOSTIC_FAILURE |
| REFERENCE_OUT_OF_SUPPORT_NOT_IDENTIFIABLE | REFERENCE_CONDITION_OUT_OF_SUPPORT |
| FUTURE_INFORMATION_REJECTED | FAIL_CLOSED_P2_FUTURE_INFORMATION |
| SAME_EPISODE_REJECTED | FAIL_CLOSED_P2_SAME_EPISODE_LEAKAGE |
| JACKKNIFE_FOLD_FAILURE_NOT_IDENTIFIABLE | UNCERTAINTY_NOT_ESTIMABLE |
| UNSUPPORTED_CAUSAL_LABEL_REJECTED | FAIL_CLOSED_P2_CAUSAL_EVIDENCE_REQUIRED |
| P1_RELEASE_AND_OBSERVED_VALUE_UNCHANGED | source observed value retained and P2 estimate stays separate |

The checked-in Golden JSON is the expected-result source used by tests; it is not merely
documentation.

## Persistence boundary

This batch deliberately does not introduce a second persistence schema. Each domain
product provides an `as_record()` projection whose field set exactly matches its
existing DB 1.6.0 carrier:

- `assessment.factor_feature_set`;
- `assessment.attribution_run`;
- `capability.adjusted_capability_estimate`.

Cross-layer-only fields such as source/P2 Release identities, reason codes and
uncertainty method/level remain derived according to the adopted DTO contract instead of
being added as new DB columns.

## Non-goals

- no P2 external admission;
- no P3 implementation or admission;
- no production factor taxonomy invention;
- no causal claim without independent causal evidence;
- no DB migration;
- no object-storage URI invention;
- no mutation of P1 historical products.

## Completion gate

This review is implementation evidence only. M6-CAP-001..004 and M6-TST-002/003 remain
NOT COMPLETE until this exact candidate head passes all 14 required Hosted CI jobs,
merges with expected-head protection, and the actual merge SHA passes protected-main
push CI 14/14.
