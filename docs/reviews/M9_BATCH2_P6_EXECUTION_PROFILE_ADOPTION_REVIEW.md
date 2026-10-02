# M9 Batch 2 - P6 execution-profile adoption review

## Decision

Candidate status: **READY FOR EXACT-HEAD HOSTED CI QUALIFICATION**.

This sub-gate adopts one explicit P6 execution profile before any P6 model execution code is implemented. The frozen P6 authority requires an exact adopted model profile and forbids an implementation-selected default model family.

An earlier Draft-only candidate attempted to forecast P4/P5 scores directly. That design was withdrawn before qualification because the current M8 authority intentionally has no adopted aggregation profile and current P4/P5 score fields remain evidence-only/null. The qualified candidate must be executable against already admitted products rather than depending on an unadopted scoring formula.

## Adopted candidate

- Profile ID: `P6_P3_CAPABILITY_OLS_MAD_FORECAST`
- Version: `1.0.0`
- Canonical SHA256: `6a064762b4edde3448b25e5b74384708745793acc863a8adfbfad40fc7651394`
- Rebaseline: `R5.1_M9_P6_P3_CAPABILITY_FORECAST_PROFILE_ADOPTION`
- Candidate BASELINE_LOCK SHA256: `9920b59601d8441f883879e813164f33ee5c02db81aa5e1b759e3a1772469e51`
- Parent qualified M9 C3 lock: `ba4f152a09206bcbaf06a1882d08763b332e95068ada0404a969073a7dc13a08`
- DB schema: unchanged at `1.6.0`
- Shadow schema: forbidden

## Executable target and context

Profile v1 forecasts the next-session value of an exact in-domain P3 reference-condition capability estimate:

- numeric target DTO: `IntrinsicCapabilityEstimateDTO`;
- numeric target: exact `value`;
- session axis: exact `condition_point.session_order`;
- reference condition: exact `condition_point.reference_condition_id`;
- uncertainty: exact P3 estimate interval.

Every training row also requires an exact APPROVED P4 assessment revision for the same governed training session, with an exact capability-projection reference to the P3 estimate. The P4 session's exact session-order assignment must equal the P3 estimate condition-point session order.

This satisfies the P6 requirement for exact P4/P5 factual context without inventing a P4/P5 score. Profile v1 uses P4 context only; P5 expansion requires a later explicitly adopted profile.

## Determinism and leakage controls

The profile freezes:

- one exact aircraft/capability/reference-condition/unit/configuration domain;
- distinct exact session-order assignments;
- deterministic OLS with intercept;
- temporal last-point holdout, never random split;
- no RNG, regularization, hidden weighting, clipping or imputation;
- exact P3 estimate + exact P4 context row identity;
- future and same-outcome leakage rejection;
- exact training/validation snapshot identity.

## Validation and uncertainty

Minimum evidence is four eligible sessions. The last historical point is the temporal holdout. Validation records the exact holdout residual and refits on the final governed window.

Forecast uncertainty is explicit:

`half_width = max(max_P3_input_half_width, abs(holdout_error), final_refit_residual_MAD)`

P4/P5 confidence is never converted into uncertainty. No implementation-selected accuracy multiplier or threshold-probability rule is permitted.

## Forecast and applicability

Profile v1 supports only:

- `NEXT_SESSION_ORDER`;
- exactly one step;
- no recursive multi-step forecast;
- numeric output only when applicability is `APPLICABLE`.

Configuration/reference-condition/semantic drift is `OUT_OF_DOMAIN`; too few eligible points is `INSUFFICIENT_EVIDENCE`; ambiguous targets are `NOT_IDENTIFIABLE`. None may be encoded as zero.

## Safety boundary

The profile is limited to training-evaluation forecast/debrief support. Operational/tactical optimization, weapon/targeting recommendation, mission-command generation, automatic training command and real-time control are explicitly forbidden.

## Historical governance compatibility

The prior qualified M9 C3 lock `ba4f152a09206bcbaf06a1882d08763b332e95068ada0404a969073a7dc13a08` remains the first historical lineage parent. The withdrawn Draft-only lock is not added to lineage because it was never protected-main qualified.

Historical P6 authority, P3 authority/profile and P4/P5 authority remain byte-identical. Generated baseline/package-init projections and the loader/baseline-verifier trust root are updated coherently.

## Admission boundary

Profile adoption does **not** admit P6 and does not complete M9-MODEL-001. Only after exact-head PR CI, guarded merge and protected-main exact merge-SHA CI may runtime implementation execute this exact profile. Formal P6 admission still requires protected-main M9 Exit GO.
