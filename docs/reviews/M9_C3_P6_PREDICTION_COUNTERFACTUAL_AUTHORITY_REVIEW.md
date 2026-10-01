# M9 C3 P6 Prediction / Counterfactual Authority Review

## Identity

- Program: #149
- SDIB-1.8 baseline: #193
- C3 tracker: #194
- Entry protected-main SHA: `ffbd5e5f0561ce39d8736de765dd6be240edfae1`
- Entry Run: #529 / `36876431677` / exactly 14/14 SUCCESS
- Authority: `P6_PREDICTION_COUNTERFACTUAL_AUTHORITY:1.0.0`
- Role/privacy/release profile: `P6_ROLE_PRIVACY_RELEASE_PROFILE:1.0.0`
- DB schema: 1.6.0 unchanged; no shadow schema.

The C3 candidate freezes exact P4/P5 input identity, leakage-safe snapshots,
exact model/training/validation/artifact identity, applicability and
uncertainty, fact-versus-projection separation, forecast and counterfactual
identity, non-causal default counterfactual claims, advisory-only
recommendations, Joint/LVC profile/version/provenance, replay, and the M9 C4
admission guard.

It deliberately adopts no default prediction model family, numeric threshold,
causal estimator, or hidden recommendation formula. Existing 1.6.0 carriers
are reused.

The role profile separates model release (`MODEL_REVIEWER`) from recommendation
approval (`INSTRUCTOR_EVALUATOR`); `ADMIN_AUDITOR` inherits neither authority.
M8 pseudonymous identity semantics remain upstream privacy authority.

C3 adds 9 P6 DTOs and regenerates Python DTO/OpenAPI projections
from Canonical authority. Historical M8 validators preserve the exact M8 DTO
subset and BASELINE_LOCK lineage while allowing additive current-baseline
evolution.

C3 adoption does not admit P6. Only protected-main M9 Exit GO with exactly
14/14 required Hosted CI SUCCESS may set `p6_admitted=true`.
