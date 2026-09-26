# M2 C3 QA/SNS Authority Review

Status: **APPROVED UNDER TEMPORARY OWNER DELEGATION**

Decision record: GitHub issue #106  
Change class: C3 Semantic contract  
Authority artifact: `baseline/CB-1.4.0/canonical/M2_QA_SNS_AUTHORITY.json`  
Authority version: `1.0.0`

## Governance disposition

The repository owner temporarily delegated the #106 human governance action to the assistant. For this closure only, the single-PR restriction is narrowed to permit one dedicated C3 Baseline Change PR from protected main. PR #105 remains the implementation PR and may not consume the new authority until the C3 PR is adopted.

The separate-person mathematical-review requirement is replaced, for #106 only, by an independent calculation-path review: the authority validator recomputes the Golden values directly from the frozen equations and does not call the Batch 2 consumer implementation.

## QA-001 review

The authority freezes WXYZ quaternions, active BODY_FRD -> ECEF attitude rotation, right-handed FRD axes, azimuth `atan2(y,x)` in `[-pi,pi)`, upward-positive elevation `atan2(-z,hypot(x,y))`, and SENSOR_FRD -> BODY_FRD boresight composition.

The discriminator uses both a non-identity +90 degree body yaw and a non-identity +45 degree sensor boresight. The independently recomputed expected own-body azimuth is 0 and sensor azimuth is `-pi/4`. A zero-norm quaternion is a fail-closed negative.

## QA-002 review

The six-dimensional covariance state is frozen as target ECEF XYZ followed by own ECEF XYZ, all in meters. The 3x6 Jacobian row semantics are relative ECEF XYZ and the canonical relative-position Jacobian is `[I3|-I3]`.

Position covariances populate the two 3x3 diagonal blocks. A shared time-alignment error is projected with `g=[v_target;v_own]` and `P_time=sigma_t^2 g g^T`, creating required target-own cross covariance. Source position cross covariance is zero only because this authority explicitly says absent means zero for QA-002 V1; other hidden cross terms are forbidden.

Own-attitude uncertainty contributes only to angular variance after relative-position covariance is rotated into OWN_BODY_FRD. Target-attitude sensitivity is exactly zero for QA-001 V1 relative position and own-body angles, but the reference remains required for provenance.

The non-degenerate Golden yields:
- `sigma_range_m = 5.000119998560034`
- `sigma_az_rad = 0.01063014581273465`
- `sigma_el_rad = 0.011874342087037918`
- `sigma_position_3d_m = 8.888261922333298`

## Reference-match-quality profile review

Profile `M2_REFERENCE_MATCH_QUALITY_V1` advances to version `1.1.0`. It explicitly freezes the five previously missing contract fields. `max_interpolation_age_us=50000` is intentionally equal to `max_gap_us=50000` for this version, but they remain distinct names and both participate in the profile hash. `min_coverage=0.8` remains a separate aggregate coverage gate.

All domain sigma caps are explicit null, meaning no numeric cap; this avoids inventing unsupported threshold magnitudes while still requiring all three uncertainty components. The canonical profile hash is `904100e467f10e89aca1f06b1e9eeff86923121063ec9a41a2d73f84cc2400f1`.

## Comparability

QA-001 and QA-002 retain their semantic IDs/versions because no formally completed M2 output exists before this authority. Their comparable history starts at the new authority hash and approved Baseline Lock. QA-006 keeps its formula identity and inherits the new upstream authority lineage. SNS accuracy metrics retain their metric semantic versions and segment comparisons by exact profile ID/version/hash.

## Adoption gate

Adoption requires the dedicated C3 PR to pass hosted Windows/Linux CI, baseline-lock verification, generated-diff verification, the independent calculation-path Golden validator, and normal repository checks. Only after adoption may PR #105 implement the authority.
