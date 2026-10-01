# M8 Batch 2 P4 Evidence, Instructor Workflow, Assessment and Replay Review

## Identity

- Program: #149
- Batch tracker: #183
- Parent protected-main SHA: \`b212761dd57ab7abbd5c48b1fefb19a65fd5c71c\`
- Parent protected-main Run: #518 / \`36829110420\` / exactly 14/14 SUCCESS
- Authority: \`P4_P5_TRAINING_ASSESSMENT_AUTHORITY:1.0.0\`
- DB schema: 1.6.0 unchanged
- P4/P5 external admission remains false until M8 Exit GO
- P6 remains inactive

## M8-ASSESS-001 — deterministic human-machine evidence

The implementation materializes only authority-approved MACHINE evidence from the exact Batch 1 interaction scope. Products bind exact subject context, pseudonymous subject key, evidence set, World/source refs, exact P3 twin/estimate refs, availability state and as-of cutoff.

No P4 scoring formula, grade, threshold or weight is introduced. Unavailable/OOD/not-identifiable evidence keeps an explicit nonnumeric state and reason code.

## M8-ASSESS-002 — immutable instructor and approval workflow

Instructor annotation writes require the exact INSTRUCTOR_EVALUATOR authorization and assigned-scope match. Revisions create a new deterministic annotation UUID, increment revision number and retain an exact supersedes link; the prior revision object is never overwritten.

Mutating commands carry exact request_id. Same request_id + same payload replays the existing result; conflicting reuse fails closed. Every mutation creates an immutable audit projection.

Approval transitions are loaded from Canonical authority, not hard-coded as a second policy source. The normal chain is DRAFT -> IN_REVIEW -> APPROVED/REJECTED. Terminal correction may create a new DRAFT revision only because the adopted authority explicitly permits it.

## M8-ASSESS-003 — immutable P4 assessment revision

The P4 revision identity includes exact subject/configuration, machine evidence IDs, instructor annotation IDs, World refs, exact P3 claim/validity/as-of/uncertainty, approval state, confidence, evidence-set identity and supersession.

Score and grade are structurally fixed to null because M8 authority admits no default aggregation/scoring profile.

Approval changes create a new assessment UUID and preserve the previous revision through supersedes_id.

## M8-LONG-001 — longitudinal exact-revision replay

The longitudinal module intentionally depends only on a structural Protocol and \`tpaa_context\`, not \`tpaa_assessment\`, preserving the frozen architecture rule that forbids \`tpaa_longitudinal -> tpaa_assessment\`.

Replay:
- is exact as-of bounded;
- retains every historical revision visible at the cutoff;
- resolves active leaves from exact supersession refs;
- preserves direct exact-revision addressability;
- rejects duplicate/broken supersession;
- rejects pooling when subject/role/seat/function/aircraft/twin/assessment-profile/role-model comparison identity changes.

## M8-TST-002

Contract coverage includes:
- deterministic machine evidence;
- explicit OOD/unavailable semantics;
- immutable instructor revision and audit;
- request-id idempotency;
- unauthorized annotation/approval denial;
- exact P4 DRAFT -> IN_REVIEW -> APPROVED chain;
- invalid transition rejection;
- null score/grade;
- P3 claim/as-of/uncertainty preservation;
- historical replay before and after approval;
- comparison-boundary rejection under configuration/profile drift.

## Non-goals

This batch does not add persistence migrations, API/GUI publication, P5 aggregation, a human-performance scoring formula, or external P4/P5 admission.

## Completion gate

The candidate remains incomplete until its exact PR head passes all 14 Hosted CI jobs, merges with expected-head protection, and the actual merge SHA passes protected-main push CI exactly 14/14.
