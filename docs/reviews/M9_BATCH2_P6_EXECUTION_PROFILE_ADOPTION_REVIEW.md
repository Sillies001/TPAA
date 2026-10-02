# M9 Batch 2 - P6 execution-profile adoption review

## Decision

Candidate status: **READY FOR EXACT-HEAD HOSTED CI QUALIFICATION**.

This sub-gate adopts one explicit P6 execution profile before any P6 model training or forecast runtime is implemented. It exists because the frozen P6 authority requires an exact adopted model profile and forbids implementation-selected default model families.

## Adopted candidate

- Profile ID: `P6_TRAINING_SCORE_OLS_MAD_FORECAST`
- Version: `1.0.0`
- Canonical SHA256: `43bf6f3814d764de812c6ff478600959b3f7bd9c54e6b8bfec5297531271d038`
- Rebaseline: `R5.1_M9_P6_EXECUTION_PROFILE_ADOPTION`
- Candidate BASELINE_LOCK SHA256: `2852dc2904854fcd65e3207ddda4859795b003e839ff1d95e241b199879ddd1f`
- DB schema: unchanged at `1.6.0`
- Shadow schema: forbidden

## Scope

Profile v1 is restricted to training-evaluation projections. It forecasts only the next governed training session-order score from exact approved numeric P4/P5 assessment revisions:

- `P4_ASSESSMENT_SCORE`
- `P5_OVERALL_SCORE`

A P5 numeric target requires an exact aggregation-profile reference. Missing numeric scores are insufficient evidence and are never imputed.

Operational/tactical optimization, weapon/targeting recommendations, mission-command generation and real-time control are explicitly outside the profile.

## Determinism and leakage controls

The profile freezes:

- exact source revision and subject/composition semantics;
- exact assessment spec and P5 aggregation profile where applicable;
- distinct exact session-order assignments;
- deterministic OLS with intercept;
- temporal last-point holdout, never random split;
- no RNG, regularization, hidden weighting, clipping or imputation;
- future and same-outcome leakage rejection;
- exact training/validation snapshot identity.

## Validation and uncertainty

Minimum evidence is four distinct numeric sessions. The final historical point is the temporal holdout. Validation records the exact finite holdout residual and then refits on the final governed window.

Numeric projection uncertainty is explicit:

`half_width = max(abs(holdout_error), final_refit_residual_MAD)`

No confidence-to-uncertainty conversion, implementation-selected multiplier or threshold probability is allowed.

## Forecast and applicability

Profile v1 supports only:

- horizon type `NEXT_SESSION_ORDER`;
- exactly one step;
- no recursive multi-step forecast;
- numeric output only when applicability is `APPLICABLE`.

Identity or assessment-semantics drift is `OUT_OF_DOMAIN`; missing numeric evidence is `INSUFFICIENT_EVIDENCE`; ambiguous targets are `NOT_IDENTIFIABLE`. None of those states may be encoded as zero.

## Historical governance compatibility

The prior M9 C3 lock `ba4f152a...` is preserved as the first parent in lock lineage. The historical P6 authority and role/release profile remain byte-identical. Their validator now verifies historical lock lineage rather than incorrectly requiring the R5.0 lock to remain the current repository lock forever.

Generated baseline/package-init projections and the baseline verifier/loader trust root were updated coherently with R5.1.

## Admission boundary

Execution-profile adoption **does not admit P6** and does not complete M9-MODEL-001. After exact-head PR CI, guarded merge and protected-main CI, the implementation phase may execute this exact profile. Formal P6 admission still requires protected-main M9 Exit GO.
