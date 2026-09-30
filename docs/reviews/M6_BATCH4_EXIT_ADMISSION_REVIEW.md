# M6 Batch 4 Exit / C4 P2 Admission Review

## Identity

- Tracker: #166
- Program: #149
- M7/P3 design-only runway: #155
- Task: M6-TST-005
- Protected-main prerequisite: adab5b6c6c03dd7ddfa096fcf7ff5d41cb0adb1c
- Prerequisite Run: #492 / 36686582998 / push / main / 14 of 14 SUCCESS
- DB schema: 1.6.0 unchanged
- Candidate transition: P2 only; P3-P6 remain inactive

## Qualified upstream chain

Batch 1:
- #156 closed
- protected-main SHA 2a2b0907515761c3768bc952cf97894825e05109
- Run #484 / 36650776582 / 14 of 14 SUCCESS
- C3 #151 closed
- authority P2_ATTRIBUTION_NORMALIZATION_AUTHORITY:1.0.0
- authority SHA-256 1bfc6c9eb8e2142249c327af5698bc6a8925f983fd8363b1d2bd835966eea5fa

P2 DTO/execution profile:
- #159 and #161 closed
- protected-main SHA 047b4d03778243cf50b8825da52b4c6a85938710
- Run #487 / 36665607287 / 14 of 14 SUCCESS
- cross-layer DTO SHA-256 9d94f75031afcbfe2391bed1245c3f8d95f124a6549a8f116aa1efb879ae45b4
- profile P2_LINEAR_REFERENCE_ADJUSTMENT:1.0.0
- profile SHA-256 202e255bd09349407e0e7cc4d77d8b848df99d84dc00e50e46871eb4f82f0d68

Batch 2:
- #158 closed
- protected-main SHA 551e620cee6b8f3a5b406790f08443c485bf234b
- Run #490 / 36674275763 / 14 of 14 SUCCESS

Batch 3:
- #164 closed
- protected-main SHA adab5b6c6c03dd7ddfa096fcf7ff5d41cb0adb1c
- Run #492 / 36686582998 / 14 of 14 SUCCESS

## Exit validator

tools/testing/m6_exit_review.py performs one fail-closed M6-TST-005 review.

It verifies:
1. exact SDIB-1.5 17-task inventory and order;
2. deterministic evidence hashes for all 17 tasks;
3. C3 #151/#159/#161 closed;
4. Batch 1/2/3 exact protected-main SHA/Run identities;
5. authority / DTO / execution-profile hashes against BASELINE_LOCK;
6. exact P2AdmissionStateDTO field contract;
7. exact C4 admission guard: push, refs/heads/main, GO, success, 14 jobs;
8. DB schema 1.6.0 and no shadow schema;
9. leakage/admission negatives;
10. identifiability/uncertainty/Golden coverage;
11. observed-vs-adjusted, replay and P1 non-regression evidence;
12. no current/latest/recompute historical fallback;
13. retained M5 qualification gates;
14. P1 immutable baseline;
15. no silent CAPABILITY_PHASE_REGISTRY mutation for runtime admission;
16. P3-P6 inactive;
17. M7/P3 #155 remains design-only at task/interface/test detail.

## CI topology

The required Hosted CI topology remains 14 jobs.

No M6 side job is added. Existing m0-exit-review becomes the final DAG sink and depends
on every other required job id. Since m0-cross-platform expands to Windows and Linux,
13 actual required jobs have succeeded before the final M6 Exit step runs.

The M6 Exit step is the final workflow step. Therefore:
- PR candidate: decision PENDING_PROTECTED_MAIN, p2_admitted=false;
- push/main exact merge SHA: GO is possible only if the final step succeeds, which
  completes the current final required job and therefore the 14/14 run.

The final JSON is printed in the required-job log and written to
evidence/m6-exit/review.json. There is no later step that can fail after a GO decision.

## Admission representation

Batch 4 does not mutate CAPABILITY_PHASE_REGISTRY.json to manufacture a static runtime
admission state.

The adopted P2 authority already defines P2AdmissionStateDTO as an
Application/governance DTO sourced from exact protected-main M6 Exit evidence.

p2_admitted is true only when decision is GO.
The formal token is P2_M6_QUALIFIED and exists only in the protected-main GO result.

## Completion gate

This candidate does not by itself complete M6.

Formal completion requires:
1. exact PR head 14/14 SUCCESS;
2. Ready only after exact-head qualification;
3. merge using expected_head_sha;
4. actual merge-parent verification;
5. actual protected-main merge SHA 14/14 SUCCESS;
6. final M6 Exit log on that exact merge SHA:
   status=PASS,
   decision=GO,
   failed_acceptance=[],
   p2_admitted=true,
   qualification=P2_M6_QUALIFIED.

Only then may #166 close and M7/P3 implementation begin from that exact qualified SHA.
