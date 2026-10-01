# M8 Batch 4 Exit / C4 P4-P5 Admission Review

## Identity

- Tracker: #185
- Program: #149
- M9/P6 design-only runway: #186
- Task: M8-TST-005
- Protected-main prerequisite: eaa1a9a0f3374410cf59e82e97bef70ac18840b0
- Prerequisite Run: #525 / 36855927899 / push / main / exactly 14/14 SUCCESS
- DB schema: 1.6.0 unchanged
- Candidate transition: P4 and P5 only; P6 remains inactive

## Qualified upstream chain

C3 authority:
- #181 closed
- protected-main SHA 0a704735a3e5ecb847d7ed4194aa6649280d351a
- Run #516 / 36822713745 / exactly 14/14 SUCCESS

Batch 1:
- #182 closed
- protected-main SHA b212761dd57ab7abbd5c48b1fefb19a65fd5c71c
- Run #518 / 36829110420 / exactly 14/14 SUCCESS

Batch 2:
- #183 closed
- protected-main SHA 68881758cddca2f39b3d6f7801f2766755b8bc2f
- Run #520 / 36838469146 / exactly 14/14 SUCCESS

Batch 3:
- #184 closed
- protected-main SHA eaa1a9a0f3374410cf59e82e97bef70ac18840b0
- Run #525 / 36855927899 / exactly 14/14 SUCCESS

## Exact authority chain

- P4_P5_TRAINING_ASSESSMENT_AUTHORITY:1.0.0
- authority SHA-256 749360544e3e403e3a81b4992797d5186c93d1f06a92e96f1352c4ab4ed4cb77
- P4_P5_ROLE_PRIVACY_PROFILE:1.0.0
- role/privacy SHA-256 99a526cead816010373cdd81cd889d33fa359b5d0b74d87743e51d0f649f1113
- CROSS_LAYER_DTO_CONTRACTS SHA-256 2d5ff42aa3a8fee6ed7995be0e430dee18aa36bde6fc5144fd1484532d67ee47
- DB schema 1.6.0
- no shadow schema
- no numeric P5 aggregation profile; evidence-only aggregation remains score/grade null

## Exit validator

tools/testing/m8_exit_review.py performs one fail-closed M8-TST-005 review. It verifies the exact 23-task inventory, M7/P3 entry evidence, #181-#184 protected-main qualification, authority/role/DTO lock binding, DB 1.6.0, Batch 1-3 negative and replay gates, exact API/GUI/security boundaries, P1-P3 retained semantics, M9/P6 design-only runway, and exact 14/14 required CI.

## CI topology

The required Hosted CI topology remains exactly 14 jobs. No M8 side job is introduced. Existing m0-exit-review remains the final DAG sink. M8 issue evidence is fetched after the retained M7 Exit review, and the M8 Exit review is the final workflow step.

PR candidates can only produce PASS + PENDING_PROTECTED_MAIN with p4_admitted=false, p5_admitted=false and p6_inactive=true. Only exact push/main on the guarded merge SHA can produce GO.

## Admission representation

Batch 4 does not mutate CAPABILITY_PHASE_REGISTRY.json to manufacture a static runtime admission state. P4P5AdmissionStateDTO is sourced from exact M8 Exit evidence.

P4/P5 are admitted only when decision=GO. Formal qualification token: P4_P5_M8_QUALIFIED. P6 remains inactive and cannot be claimed before M9 Exit.

## Completion gate

Formal completion requires exact PR-head 14/14, head/ref/run equality, behind=0 and mergeable, expected-head guarded merge, verified merge parents, protected-main merge-SHA 14/14, and final output status=PASS, decision=GO, failed_acceptance=[], task_complete=true, p4_admitted=true, p5_admitted=true, p6_inactive=true, qualification=P4_P5_M8_QUALIFIED.
