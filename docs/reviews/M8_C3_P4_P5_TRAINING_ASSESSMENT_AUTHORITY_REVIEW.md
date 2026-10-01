# M8 C3 P4/P5 Training-Assessment Authority / Role-Privacy Review

## Identity

- Program: #149
- SDIB-1.7 baseline: #180 (adopted)
- C3 tracking: #181
- Batch 1 tracker: #182
- Change class: C3 semantic contract + ROLE_MODEL profile + cross-layer DTO
- Parent protected-main SHA: `4b5e0e6f47e6ca7291f941bc873d2b8054a15d62`
- Parent protected-main Run: #512 / `36813509518` / exactly 14/14 SUCCESS
- DB schema: 1.6.0 unchanged
- Parent BASELINE_LOCK SHA-256: `0d2f11dc5ee41038a1ef63b8b4157730bd1cd313c7a98faaa286132397b8de47`
- Candidate P4/P5 authority SHA-256: `749360544e3e403e3a81b4992797d5186c93d1f06a92e96f1352c4ab4ed4cb77`
- Candidate role/privacy profile SHA-256: `99a526cead816010373cdd81cd889d33fa359b5d0b74d87743e51d0f649f1113`
- Candidate cross-layer DTO SHA-256: `2d5ff42aa3a8fee6ed7995be0e430dee18aa36bde6fc5144fd1484532d67ee47`
- Candidate BASELINE_LOCK SHA-256: `d7073279fd5e8b1438fab3481f8654841b4e9445244d3b0369c5cad2cfe8111a`
- Controlled artifacts: 28 -> 30

## Semantic closure

The authority freezes exact P4 subject-context identity, exact P5 composition identity, machine-vs-instructor evidence separation, immutable assessment revision/approval semantics, explicit unavailable/OOD/not-identifiable states, least-privilege role/privacy projection, knowledge-time boundaries, exact replay and M8 C4 admission evidence.

P1, P2 and P3 remain immutable upstream evidence layers. P4/P5 remain candidates until M8 Exit GO. P6 remains inactive.

## Role model and privacy

The existing DB 1.6.0 carrier is reused:
- `registry.context_artifact` with `artifact_kind=ROLE_MODEL`;
- `context.context_artifact_binding` with `binding_role=ROLE_MODEL`;
- `audit.audit_log` for privileged workflow/audit evidence.

No RBAC shadow tables are introduced. The default transport identity is `SUBJECT_SHA256:<digest>`. Direct `actor_id` projection requires both an authorized role and an exact scope match. Frozen roles are SUBJECT_SELF, INSTRUCTOR_EVALUATOR, TEAM_LEAD, ANALYST and ADMIN_AUDITOR. Default is deny; ADMIN_AUDITOR does not imply evaluator permission.

## Instructor and approval boundary

Machine evidence never becomes instructor evidence. Annotation revisions create new identities and preserve prior content/evidence. Approval state is carried by immutable assessment revisions plus `audit.audit_log`; mutating requests require exact request_id.

## Aggregation boundary

No default P5 aggregation formula, threshold or weight is admitted. Numeric aggregate score/grade is allowed only when an exact adopted assessment/aggregation profile supplies them. Without such a profile, score/grade remain null. Team results never copy to individual P4 products.

## Historical compatibility

M8 extends `CROSS_LAYER_DTO_CONTRACTS.json` and `BASELINE_LOCK.json` additively. Historical P3 authority/profile bytes remain immutable. M7 validation advances to the M6-proven pattern: exact historical P3 DTO subset hash + current DTO lock binding + retained M7 lock lineage.

## Non-goals

- no DB schema migration or shadow schema;
- no P4/P5 runtime assessment engine in this C3 change;
- no numeric P4/P5 scoring formula;
- no P4/P5 external admission;
- no P6 activation;
- no current/latest/default aliasing.

## Adoption gate

The candidate remains inactive until exact-head Hosted CI 14/14, expected-head guarded merge, verified merge lineage and protected-main exact merge-SHA 14/14. Only then may #181 / M8-GOV-001 close.


## Run #513 remediation

Run #513 / `36818252564` failed at the three M0 root jobs while the new authority/lock verifier itself passed 30/30 controlled artifacts. The failure was historical-compatibility drift only:

- runtime-handshake unit test still pinned the prior current DTO SHA;
- loader contract still pinned 28 controlled artifacts;
- M6 DTO-profile contract test still pinned the prior current DTO SHA while its historical P2 subset/profile authority remained unchanged;
- M1 Entry activation expected the prior current BASELINE_LOCK/DTO identity although its build manifest correctly emitted the new governed identity;
- OpenAPI exact snapshot had not yet been regenerated after the additive M8 DTO authority extension.

The remediation updates only those current-baseline projections/assertions and regenerates the exact OpenAPI snapshot. Historical P2/P3 subset hashes, profiles, authority bytes, lock lineage and admission semantics are unchanged.
