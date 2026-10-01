# M8 / P4-P5 One-Milestone-Ahead Detailed-Design Runway

## Governance status

- Program: #149
- Design tracker: #170
- M7 governance task: M7-GOV-003
- Upstream authority: SDIB-1.6 / P3 authority 1.0.0
- Status: DESIGN ONLY
- M8 implementation: FORBIDDEN before protected-main M7 Exit GO
- P4/P5 admission: NOT ACTIVE

This document freezes the next-milestone engineering runway without implementing P4/P5.

## Capability intent

### P4 — Human-Machine

P4 evaluates pilot/operator + aircraft interaction after aircraft capability has already been separated into P1 observed, P2 adjusted and P3 exact twin/reference-condition products.

P4 does not redefine aircraft capability. It adds human-action, decision, workload, procedural and instructor-reviewed evidence around an exact aircraft/twin context.

### P5 — Team / Package / Mission

P5 evaluates multi-subject coordination and mission/package outcomes using exact composition identity.

P5 does not collapse individual P4 or aircraft P3 evidence into one untraceable score. Team/mission products must preserve contributing subject identities, roles, aircraft/twin revisions and evidence lineage.

## P3 -> P4/P5 interface contract

Every downstream product that consumes P3 must bind exact immutable identities:

- twin_revision_id;
- P3 estimate_id where used;
- capability_model_id / surface_id lineage;
- reference_condition_id;
- validity_domain_status;
- claim_level;
- as_of_time;
- uncertainty;
- evidence/configuration provenance.

Forbidden:

- current/latest/default twin resolution;
- implicit newest revision;
- hidden P3 recomputation;
- treating OUT_OF_DOMAIN/unavailable as zero;
- upgrading `REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE` to intrinsic wording;
- using a P3 AIRCRAFT-level profile as aircraft-model population evidence.

## P4 subject and evidence model

### Subject identity

Minimum P4 subject key:

- person/crew subject identity or governed pseudonymous subject key;
- role/seat/function;
- aircraft_id;
- exact twin_revision_id;
- session/episode/stage scope;
- as-of / knowledge-time cutoff.

Human identity exposure must follow role-based access and privacy rules; presentation layers should prefer governed pseudonymous identifiers where business use does not require direct identity.

### P4 evidence families

Candidate design families:

- action/timing evidence;
- tactical decision evidence;
- procedure/compliance evidence;
- workload/attention indicators where data authority permits;
- human-machine interaction sequence;
- instructor annotation/assessment;
- outcome/context evidence.

These are design families, not admitted metric codes. Any future metric must receive frozen semantic ID/input/formula/window/validity/N_A/evidence/Golden authority before implementation.

### Instructor / approval boundary

Instructor annotation must be distinct from machine-computed evidence.

Design requires:

- author/role identity;
- created/updated timestamp;
- exact target product/revision;
- approval/review state where applicable;
- immutable audit trail for published assessment;
- no silent overwrite of machine results or previous instructor decisions.

## P5 composition model

A P5 product must bind an exact composition snapshot.

Minimum composition identity:

- team/package/mission composition ID;
- participating subject IDs;
- roles;
- aircraft IDs;
- exact twin_revision_id per aircraft;
- relevant P4 revision IDs;
- scenario/mission scope;
- valid/as-of interval.

Composition change creates a new identity. Historical products do not silently follow roster changes.

## Individual vs team aggregation

Aggregation is not authorized by convenience.

Rules for M8 detailed design:

- individual P4 evidence stays individually addressable;
- team aggregation must identify contributing members and roles;
- missing/unavailable/OOD member evidence is explicit and never zero-filled;
- incompatible reference conditions or twin/configuration revisions cannot be pooled without an explicit governed normalization rule;
- weights, thresholds and aggregation formulas must be machine-authority fields, never GUI/application defaults;
- team performance and mission outcome remain distinct semantic layers.

## API design runway

P4/P5 APIs should follow the exact-revision pattern qualified in M7:

- exact subject/composition/product IDs;
- exact release/revision binding;
- historical replay;
- no current/latest/default alias;
- no transport-layer recomputation;
- role-aware evidence access;
- privacy-aware projection;
- explicit unavailable/OOD/not-identifiable states.

Write actions such as instructor annotation or approval require idempotency, authorization and immutable audit semantics.

## GUI design runway

GUI must separate at least:

- aircraft capability context (P1/P2/P3);
- individual human-machine assessment (P4);
- team/mission assessment (P5).

The GUI must display:

- subject/composition scope;
- exact revision IDs;
- evidence/claim level;
- validity/unavailable state;
- uncertainty where relevant;
- instructor vs machine origin;
- approval state;
- role-sensitive evidence visibility.

The GUI may not infer, recompute or upgrade claims.

## Privacy / security / roles

M8 detailed design must freeze a role matrix before implementation.

At minimum distinguish:

- subject/self view where applicable;
- instructor/evaluator;
- squadron/team lead;
- analyst;
- administrator/auditor.

Design requirements:

- least-privilege evidence access;
- direct identity minimization;
- pseudonymous analytical projections where possible;
- auditable privileged access;
- explicit separation of operational evidence from administrative identity data;
- no sensitive evidence in client-side logs or unrestricted exports.

## Proposed cross-layer DTO runway

Design candidates to be frozen by M8 C3 before code:

- P4SubjectContextDTO
- HumanMachineEvidenceDTO
- P4AssessmentRevisionDTO
- InstructorAnnotationDTO / ApprovalStateDTO
- P5CompositionSnapshotDTO
- TeamMissionEvidenceDTO
- P5AssessmentRevisionDTO
- P4P5AdmissionStateDTO

Names are design candidates only until M8 authority adoption.

## Test runway

M8 qualification should include:

### Golden

- exact subject/twin/context projection;
- exact composition identity;
- deterministic P4/P5 revision identity;
- immutable instructor annotation replay;
- exact aggregation inputs and governed formula identity.

### Negative

- current/latest/default resolution;
- P3 OOD -> zero coercion;
- stronger unsupported claim upgrade;
- missing role authorization;
- composition drift under same product ID;
- incompatible reference-condition aggregation;
- hidden GUI/API recomputation;
- P1/P2/P3 historical mutation.

### Replay

- exact historical revision;
- exact as-of/knowledge-time;
- exact composition/role context;
- same inputs -> same logical identity;
- changed composition/annotation/evidence -> new identity.

### Cross-platform

- Windows/Linux canonical serialization and logical identity equivalence;
- deterministic ordering;
- no filesystem/path-dependent identity.

## M8 admission runway

M8 should preserve the staged gate pattern:

1. C3 machine authority adopted on protected main;
2. data/input authority and privacy/role contracts;
3. P4 implementation + tests;
4. P5 implementation + tests;
5. API/GUI publication;
6. cross-platform replay/non-regression;
7. protected-main M8 Exit;
8. only then P4/P5 admission.

P6 remains inactive throughout M8.

## Blocking conditions before M8 implementation

M8 implementation must not start unless all are true:

- M7 protected-main Exit = GO;
- P3 admitted from exact qualified M7 merge SHA;
- P4/P5 C3 authority freezes subject/composition/privacy/aggregation semantics;
- DTO/API/GUI contracts are exact;
- no unresolved schema need;
- role/privacy approval is explicit;
- Golden/negative/replay plan is executable.

Until then this document is a design runway only.
