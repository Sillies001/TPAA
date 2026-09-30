# M7 C3 P3 Capability/Twin Authority / Profile Review

## Identity
- Program: #149
- SDIB-1.6 baseline: #168 (adopted)
- P3 design runway: #155 (completed)
- C3 tracking: #169
- Batch 1 tracker: #172
- Change class: C3 semantic contract + execution profile + cross-layer DTO
- Parent protected-main SHA: `d590a3a9a05db1a8b566b2dafec05e93028436e5`
- Parent protected-main Run: #497 / `36709415054` / 14 of 14 PASS
- DB schema: 1.6.0 unchanged
- Parent BASELINE_LOCK SHA-256: `f95167aca59dc993ced607e55f21f01080c4e24cc0759bf97482d49654ea182b`
- Candidate P3 authority SHA-256: `76726fc533cde7b0a183a1575cb50276e166081cc37ebe4857ed3324ab913e3b`
- Candidate P3 execution profile SHA-256: `d66aa780d1c2e31ec664d173a0cdbc355f98c9ff3f751a6949e84f74cdf93876`
- Candidate cross-layer DTO SHA-256: `644370d40e42960144102e6f404b6ee31af9753686b67bb27e47690515898c41`
- Candidate BASELINE_LOCK SHA-256: `0d2f11dc5ee41038a1ef63b8b4157730bd1cd313c7a98faaa286132397b8de47`
- Controlled artifacts: 26 -> 28

## Semantic closure
The authority freezes exact P2 IDENTIFIABLE eligibility, immutable P1/P2 lineage, session-order identity, configuration/lifecycle segmentation, validation snapshot semantics, sealed managed-object binding, P3 claim tiers, replay identity and C4 admission evidence.

P2 NOT_IDENTIFIABLE remains valid P2 evidence but is never a numeric P3 training target.

Per-session configuration snapshot UUID remains exact provenance. Cross-session longitudinal segmentation uses the already-proven M4-style configuration key:
`AIRCRAFT_CONFIG_SHA256:<master.aircraft_configuration_snapshot.snapshot_hash>`.
This avoids falsely splitting every session merely because each session owns a distinct snapshot row.

Profile v1 is intentionally conservative: any lifecycle event occurring inside the selected session interval forces a new segment. No event taxonomy is silently invented by implementation.

## Execution profile v1
`P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL:1.0.0` supports AIRCRAFT subjects only.

It reuses exact M4 numerical semantics:
- SESSION_ORDER axis;
- EWMA alpha = 1/3;
- OLS slope, min 3 / max 5 points;
- unscaled MAD stability, min 3 / max 5 points.

P3-specific validation is temporal and fail-closed:
- minimum 4 eligible P2 points;
- final point is held out;
- prefix uses 3..5 points;
- heldout prediction must satisfy
  `abs(error) <= training MAD + heldout P2 uncertainty half-width`;
- no implementation-selected tolerance/multiplier;
- only after validation PASS may final refit include the heldout point.

The v1 model/surface validity domain never extrapolates beyond observed SESSION_ORDER.

## Claim boundary
Default output wording is `REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE`.
The stronger `INTRINSIC_CAPABILITY_ESTIMATE` label remains defined by authority as requiring independent evidence, but profile v1 does not authorize it. Aircraft-model-level inference likewise requires a later separately governed profile.

## Managed-object boundary
Model and surface URIs must equal an exact sealed ACTIVE, non-deleted `registry.object_reference.managed_uri`, and governed hashes must match `artifact_sha256`. `file://`, local paths, current/latest/default aliases and private URI fallback are forbidden.

## Non-goals
- no DB schema migration;
- no P3 model engine execution in Batch 1;
- no P3 external admission;
- no P4-P6 activation;
- no aircraft-model-level population inference;
- no stronger intrinsic wording in profile v1.

## Adoption gate
This candidate remains inactive until its exact branch head passes all 14 Hosted CI jobs, merges with expected-head protection, and the actual merge SHA passes protected-main push CI 14/14. Only then may #169 / M7-GOV-001 and the dependent Batch 1 tasks be completed.
