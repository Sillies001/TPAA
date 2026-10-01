# M7 Batch 4 Exit / C4 P3 Admission Review

## Identity

- Tracker: #177
- Program: #149
- M8/P4-P5 design-only runway: #170
- Task: M7-TST-005
- Protected-main prerequisite: a56acc6014daf68d5a0207fb78297777e575341b
- Prerequisite Run: #508 / 36801435432 / push / main / 14 of 14 SUCCESS
- DB schema: 1.6.0 unchanged
- Candidate transition: P3 only; P4-P6 remain inactive

## Qualified upstream chain

Batch 1:
- #172 closed
- protected-main SHA ebfb99afbb86cf1fc857d03d746afa6e774a4626
- Run #501 / 36726742843 / 14 of 14 SUCCESS
- M7-GOV-001/002, M7-DATA-001/002/003 and M7-TST-001 COMPLETE

Batch 2:
- #174 closed
- protected-main SHA df32b081747e3526e13d974f818cc58125c16fd3
- Run #504 / 36739428626 / 14 of 14 SUCCESS
- M7-CAP-001/002/003 and M7-TST-002/003 COMPLETE

Batch 3:
- #176 closed
- protected-main SHA a56acc6014daf68d5a0207fb78297777e575341b
- Run #508 / 36801435432 / exactly 14/14 SUCCESS
- M7-CAP-004/005, M7-API-001, M7-GUI-001, M7-GOV-003 and M7-TST-004 COMPLETE

## Exact authority chain

- P3_CAPABILITY_TWIN_AUTHORITY:1.0.0
- authority SHA-256 76726fc533cde7b0a183a1575cb50276e166081cc37ebe4857ed3324ab913e3b
- profile P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL:1.0.0
- profile SHA-256 d66aa780d1c2e31ec664d173a0cdbc355f98c9ff3f751a6949e84f74cdf93876
- current CROSS_LAYER_DTO_CONTRACTS SHA-256 644370d40e42960144102e6f404b6ee31af9753686b67bb27e47690515898c41
- current BASELINE_LOCK SHA-256 0d2f11dc5ee41038a1ef63b8b4157730bd1cd313c7a98faaa286132397b8de47
- DB schema 1.6.0
- no shadow schema

Profile v1 remains AIRCRAFT-only. It uses SESSION_ORDER, OLS, unscaled MAD,
EWMA alpha 1/3, temporal last-point holdout, at least four eligible P2 points,
and final refit over the last up-to-five points. The only authorized claim is
REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE. Stronger
INTRINSIC_CAPABILITY_ESTIMATE wording remains unauthorized.

## Exit validator

tools/testing/m7_exit_review.py performs one fail-closed M7-TST-005 review.

It verifies:
1. exact SDIB-1.6 18-task inventory and order;
2. deterministic evidence hashes for all 18 tasks;
3. exact retained M6/P2 qualification entry evidence;
4. C3 #169 closed;
5. Batch 1/2/3 exact protected-main SHA/Run evidence;
6. authority/profile/DTO/BASELINE_LOCK binding;
7. exact P3AdmissionStateDTO and C4 admission guard;
8. DB schema 1.6.0 and no shadow schema;
9. lifecycle/configuration/as-of and future-information gates;
10. sealed ACTIVE managed-object URI/hash binding;
11. validation/applicability/OOD gates;
12. substrate/model/surface/twin/estimate replay evidence;
13. P1/P2 immutable historical products;
14. profile-v1 claim boundary and stronger-claim fail-closed behavior;
15. exact-ID API with no current/latest/default or hidden recomputation;
16. GUI no persistence/recompute/claim upgrade;
17. M8 design runway #170 exists while P4/P5/P6 remain inactive;
18. exact required CI count is 14/14 SUCCESS.

## CI topology

The required Hosted CI topology remains exactly 14 jobs.

No M7 side job is introduced. Existing m0-exit-review remains the final DAG sink.
The retained M6 Exit review runs first inside that sink, then M7 issue evidence is
fetched, and the M7 Exit review is the final workflow step.

PR candidates can only produce PENDING_PROTECTED_MAIN with p3_admitted=false.
Only exact push/main on the merge SHA can produce GO.

No workflow step follows the M7 Exit review.

## Admission representation

Batch 4 does not mutate CAPABILITY_PHASE_REGISTRY.json to manufacture a static
runtime admission state. P3AdmissionStateDTO is sourced from exact M7 Exit evidence.

p3_admitted is true only when decision is GO.
The formal qualification token is P3_M7_QUALIFIED only on protected-main GO.

P4/P5/P6 remain inactive after M7 GO. M8 starts separately from the exact
P3-qualified protected-main SHA.

## Completion gate

Formal completion requires:
1. exact PR head Hosted CI 14/14 SUCCESS;
2. PR head == branch ref == qualified Run head;
3. PR base == current main, behind=0 and mergeable=true;
4. guarded merge using expected_head_sha;
5. verified actual merge parents;
6. protected-main merge SHA push/main CI exactly 14/14 SUCCESS;
7. final output status=PASS, decision=GO, failed_acceptance=[],
   task_complete=true, p3_admitted=true, qualification=P3_M7_QUALIFIED.

Only then may #177 close, M7 be declared complete, and P3 be externally admitted.
