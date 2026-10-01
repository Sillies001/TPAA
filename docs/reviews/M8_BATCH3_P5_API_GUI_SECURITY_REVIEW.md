# M8 Batch 3 P5 / API / GUI / Security Qualification Review

## Identity

- Program: #149
- Batch tracker: #184
- Parent protected-main SHA: `68881758cddca2f39b3d6f7801f2766755b8bc2f`
- Parent protected-main Run: #520 / `36838469146` / exactly 14/14 SUCCESS
- P4/P5 authority: `P4_P5_TRAINING_ASSESSMENT_AUTHORITY:1.0.0`
- Role/privacy profile: `P4_P5_ROLE_PRIVACY_PROFILE:1.0.0`
- DB schema: 1.6.0 unchanged
- P4/P5 external admission: still false until M8 Exit GO
- P6: design only / not admitted

## M8-ASSESS-004

P5 evidence is materialized against an exact `P5CompositionSnapshot`. Each member row preserves pseudonymous subject, mission role, exact P4 revision, aircraft/twin identity, P3 claim/validity/as-of/uncertainty and an explicit availability state. Missing member evidence is represented as UNAVAILABLE with a reason code; it is never zero-filled.

Mission objective refs are retained separately from team-performance evidence.

## M8-ASSESS-005

The adopted M8 authority contains no numeric P5 aggregation profile. The only valid aggregation product is therefore `EVIDENCE_ONLY_SCORE_AND_GRADE_NULL`.

Any caller attempting to supply a convenience profile, normalization authority, score or grade fails closed with `FAIL_CLOSED_P4_P5_AGGREGATION_PROFILE_REQUIRED`. No incompatible P3/twin/configuration evidence can therefore be numerically pooled in M8 without a future explicit authority change.

## M8-ASSESS-006

P5 assessment revisions bind exact composition, evidence, objective refs, assessment spec/version, approval/claim/validity/as-of state and provenance. A changed composition cannot silently supersede a revision from the old composition series.

## M8-LONG-002

P5 replay groups exact historical revisions by composition identity while retaining a broader team/assessment comparison identity. Same-composition supersession is replayable; changed composition becomes a distinct series and is surfaced explicitly through `changed_composition`.

## M8-API-001

The Application/API boundary exposes exact IDs only:
- exact P4 revision read;
- exact P5 revision read;
- exact combined P1/P2/P3 vs P4 vs P5 workspace;
- authorized/idempotent P4 instructor annotation writes;
- authorized/idempotent P4/P5 approval writes;
- explicit privileged export.

The API does not accept role as a query/body business value. Principal resolution is injected by the transport authentication/authorization layer.

## M8-GUI-001

GUI presentation verifies a logical product hash and visibly separates:
- P1 OBSERVED;
- P2 ADJUSTED;
- P3 REFERENCE-CONDITION LONGITUDINAL;
- P4 INDIVIDUAL HUMAN-MACHINE;
- P5 TEAM/MISSION.

The presentation layer has no persistence or business recomputation and does not upgrade claims.

## M8-SEC-002

Role/privacy projection remains default-deny. Analyst/team views are pseudonymous; direct actor identity is returned only under the frozen role/scope rules. Explicit export additionally requires ADMIN_AUDITOR + scope match + privileged identity authorization + export authorization.

Security audit events store pseudonymous principal keys only; annotation body and direct actor identity are excluded from unrestricted audit event payloads.

## M8-GOV-003

`docs/reviews/M9_P6_DESIGN_RUNWAY_REVIEW.md` refines M9/P6 to task/interface/test detail using actual P4/P5 revision and composition semantics. P6 remains DESIGN ONLY with no executable model/API/admission product.

## M8-TST-003 / M8-TST-004

The contract suite verifies:
- exact P5 composition and member/P4/P3 lineage;
- explicit missing-member state;
- no numeric aggregation without adopted profile;
- changed-composition replay separation;
- role/privacy direct-identity projection;
- export fail-closed behavior;
- exact-ID API and alias rejection;
- idempotent authorized instructor writes;
- P5 pseudonymous team transport;
- GUI P1/P2/P3 vs P4 vs P5 separation;
- pre-M8-Exit API fail-closed behavior.

Existing Windows/Linux 14-job CI remains the authoritative cross-platform and P1-P3/M5-M7 non-regression gate.

## Completion gate

This candidate remains incomplete until its exact PR head passes all 14 Hosted CI jobs, merges with expected-head protection, and the actual merge SHA passes protected-main push CI exactly 14/14.
