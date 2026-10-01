# M8 Batch 1 P4/P5 Subject, World, Composition and Privacy Review

## Identity

- Program: #149
- Batch tracker: #182
- Authority tracker: #181 (COMPLETE)
- Parent protected-main SHA: \`0a704735a3e5ecb847d7ed4194aa6649280d351a\`
- Parent protected-main Run: #516 / \`36822713745\` / exactly 14/14 SUCCESS
- Authority: \`P4_P5_TRAINING_ASSESSMENT_AUTHORITY:1.0.0\`
- Role/privacy profile: \`P4_P5_ROLE_PRIVACY_PROFILE:1.0.0\`
- DB schema: 1.6.0 unchanged
- P4/P5 admission: false until protected-main M8 Exit GO
- P6: inactive

## M8-GOV-002 — C4 admission and claim guard

The implementation adds an exact M8 admission evidence contract. P4/P5 claims require:
- \`push\`;
- \`refs/heads/main\`;
- protected-main evidence;
- M8 Exit decision \`GO\`;
- successful run conclusion;
- exactly 14/14 required jobs;
- the respective P4/P5 admitted flag.

P6 always fails closed in M8. P1/P2/P3 remain distinct upstream capability layers. A dedicated P3 claim-envelope guard rejects any change to claim level, validity, as-of or uncertainty projection. P5-to-P4 result copying is explicitly rejected.

## M8-DATA-001 — exact immutable P4 subject/context

\`P4SubjectSource\` and \`P4SubjectContext\` bind:
- deterministic pseudonymous subject key;
- role/seat/function;
- session/episode/stage;
- aircraft;
- exact twin revision;
- optional exact P3 estimate;
- exact assessment spec/version;
- exact ROLE_MODEL context artifact;
- World/evidence refs;
- knowledge time and as-of cutoff.

\`subject_context_id\` is \`P4_SUBJECT_CONTEXT_SHA256:<digest>\` over the exact frozen identity fields. Current/latest/default resolution is rejected. Upstream P3 source episodes may not include the target episode, and knowledge time may not exceed as-of.

## M8-WORLD-001 — fact/evidence/assessment boundary

\`P4InteractionScopeSnapshot\` keeps three categories structurally distinct:
- World facts from Ground Truth / Perceived World / Action World;
- machine evidence;
- instructor evidence.

Each fact/evidence ref is exact and as-of bounded. Machine evidence cannot use the instructor annotation family, and instructor evidence cannot masquerade as machine evidence. World fact mutation is rejected. UNAVAILABLE / OUT_OF_DOMAIN / NOT_IDENTIFIABLE may never carry numeric zero as a substitute.

## M8-WORLD-002 — exact P5 composition

\`P5CompositionSnapshot\` deterministically binds:
- mission/session/episode/team;
- stable-ordered pseudonymous participants;
- mission role;
- aircraft and exact twin revision when applicable;
- exact P4 revision;
- exact World snapshot refs;
- exact scenario context;
- exact ROLE_MODEL context;
- assessment spec/version;
- as-of cutoff.

Any participant role, aircraft, twin, P4 revision, context or World snapshot change produces a new composition hash/identity. Reusing an old composition ID after content drift fails closed.

## M8-SEC-001 — role/privacy substrate

The existing versioned ROLE_MODEL profile is enforced without new RBAC tables.

- SUBJECT_SELF: direct identity only for self in scope.
- INSTRUCTOR_EVALUATOR: direct identity and annotation/approval writes only in assigned scope.
- TEAM_LEAD: pseudonymous participant projection.
- ANALYST: pseudonymous analytics projection.
- ADMIN_AUDITOR: direct identity only under explicit authorized audit scope; administrative privilege alone does not grant evaluator approval.

Annotation body projection requires both role authorization and visibility authorization. Default is deny.

## M8-TST-001 — negative/Golden coverage

The contract suite covers:
- missing authority;
- current/latest/default alias;
- future-information leakage;
- same-episode P3 leakage;
- unauthorized direct identity;
- unauthorized annotation/approval;
- premature P4/P5 admission;
- P6 activation;
- P3 claim upgrade/drift;
- P5-to-P4 scope copy;
- machine/instructor conflation;
- World fact mutation boundary;
- unavailable/OOD/not-identifiable numeric coercion;
- composition ordering determinism;
- composition drift under one identity.

## Non-goals

This batch does not:
- add or alter DB schema;
- add a P4/P5 scoring formula, weight or threshold;
- implement instructor revision persistence or approval mutation workflows from Batch 2;
- publish P5 team/mission scores from Batch 3;
- add API/GUI publication;
- admit P4/P5 externally;
- activate P6.

## Completion gate

The implementation remains candidate work until the exact PR head passes all 14 Hosted CI jobs, merges with expected-head protection, and the actual merge SHA passes protected-main push CI exactly 14/14. Only then may #182 and its Batch 1 tasks be marked COMPLETE.
