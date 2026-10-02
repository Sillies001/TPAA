# M9 Batch 2 deterministic model / forecast implementation review

## Scope

Issue #196 implementation candidate covers:

- `M9-MODEL-001` deterministic model revision training/validation;
- `M9-MODEL-002` applicability/domain + explicit uncertainty calibration;
- `M9-PROJ-001` exact single-step forecast projection;
- `M9-LONG-001` exact-ID replay, supersession and later-outcome validation;
- `M9-TST-001` deterministic Golden + negative evidence.

The implementation executes only the protected-main adopted
`P6_P3_CAPABILITY_OLS_MAD_FORECAST:1.0.0` profile qualified by Run #540.
It does not introduce a model default, new DB schema, shadow registry, P4/P5
score formula, operational/tactical optimization or P6 admission claim.

## Model training and validation

Each eligible row binds:

1. exact in-domain `P3CapabilityEstimate`;
2. exact APPROVED `P4AssessmentRevision` referencing the same P3 estimate;
3. exact aircraft, configuration snapshot and session-order assignment;
4. exact capability, reference condition and unit;
5. exact P3 uncertainty interval and knowledge-time context.

Future context, P4/P3 identity drift and missing required uncertainty fail
closed. Out-of-domain P3 estimates are row-ineligible and are never converted
to numeric zero.

The last eligible point is the temporal holdout. The training prefix and
validation snapshot are frozen, deterministic and identity-disjoint. After
finite holdout validation, the final model is refit on the governed final
window exactly as frozen by the profile.

## Applicability and uncertainty

Applicability is an immutable evidence product with states:

- `APPLICABLE`
- `OUT_OF_DOMAIN`
- `INSUFFICIENT_EVIDENCE`
- `NOT_IDENTIFIABLE`

A mathematically executable function does not produce a numeric forecast unless
product applicability is `APPLICABLE`.

Calibration half-width is exactly:

`max(max P3 input half-width, holdout absolute error, final-refit residual MAD)`

Confidence is not substituted for uncertainty. Missing calibration fails
closed.

## Managed model artifact

The model revision is bound to:

- exact adopted model/profile/plugin identities;
- exact frozen training + validation snapshots;
- exact model artifact bytes and SHA-256;
- deterministic capability-model UUID;
- deterministic object-reference UUID;
- exact managed URI;
- sealed / ACTIVE / non-deleted managed-object state.

Artifact hash mismatch has its own fail-closed error.

## Forecast product

Forecast execution requires:

- exact Batch-1 P6 input snapshot;
- exact model revision and artifact hash;
- exact model profile/version;
- exact training and validation snapshot IDs;
- explicit target, horizon, assumptions, forecast origin and as-of cutoff;
- managed object available by the request as-of.

Profile v1 permits only one `NEXT_SESSION_ORDER` step. Wrong target/horizon or
unavailable input yields a non-numeric applicability product; it never emits
zero. Threshold probabilities remain empty because profile v1 does not
authorize them.

Projection is explicitly `P6_PROJECTION` and is never upgraded to P1-P5 fact.

## Longitudinal replay and validation lineage

The replay repository resolves model and forecast products only by exact IDs.
There is no current/latest/default lookup.

A model source change produces a new model revision and explicit supersession
link. Historical forecast replay preserves its original model, source refs,
knowledge cutoff and logical content hash.

A later P3 observed outcome may create a separate projection-validation record.
The observed outcome must match the forecast model domain and exact target
session. Validation never mutates or rewrites the historical forecast.

## Test evidence

`tests/contract/test_m9_batch_2_model_forecast.py` plus the static Golden
fixture prove:

- exact protected profile identity;
- static dataset/model/request/forecast identities and hashes;
- input-order replay determinism;
- training/validation identity disjointness;
- physical managed-object sealing and hash mismatch rejection;
- OOD row exclusion with no zero coercion;
- missing uncertainty rejection;
- future P4 context leakage rejection;
- unavailable/wrong-horizon non-numeric behavior;
- model supersession on source change;
- exact replay and later-outcome validation without historical rewrite.

The existing Batch-1 interop contract suite remains part of the same full CI
and continues to prove exact external profile/version binding, lossy mapping
rejection and fact/projection separation.

## Gate status

Implementation is a candidate only. `M9-MODEL-001/002`, `M9-PROJ-001`,
`M9-LONG-001` and `M9-TST-001` are not COMPLETE until this exact candidate
passes Hosted CI 14/14, guarded merge, and protected-main exact merge-SHA
Hosted CI 14/14.
