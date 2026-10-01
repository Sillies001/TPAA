# M9 / P6 Prediction and Counterfactual Detailed-Design Runway

## Status

- Tracking issue: #186
- Prepared during M8 as required by M8-GOV-003
- Source capability layers available to design against: P1 observed, P2 adjusted, P3 reference-condition longitudinal, P4 individual human-machine assessment candidate, P5 team/mission assessment candidate
- P6 implementation status: **DESIGN ONLY**
- P6 admission status: **NOT ADMITTED**
- DB schema assumption for runway: 1.6.0 unless a later explicit C3 decision proves a change necessary

## P6 product boundary

P6 is a projection layer, never a rewrite of P1-P5 facts. Every prediction/counterfactual product must preserve:

1. exact source revision IDs and composition/subject identities;
2. fact vs model projection separation;
3. model identity/version/hash;
4. assumptions and intervention/counterfactual definition;
5. applicability/domain status;
6. uncertainty representation;
7. knowledge-time/as-of cutoff;
8. approval/release state;
9. evidence/model/release provenance;
10. explicit non-identifiability and out-of-domain states.

No prediction may silently become an observed fact, adjusted fact, intrinsic capability estimate, individual assessment, or team/mission result.

## Candidate interfaces

### P6ForecastRequestDTO

- forecast_request_id
- target_scope: SUBJECT | COMPOSITION | MISSION
- exact P4/P5 source revision IDs
- exact P3 twin/estimate references where used
- forecast horizon and target variable
- model_revision_id
- assumption_profile_id/version
- as_of_utc
- requested uncertainty representation

### P6CounterfactualRequestDTO

- counterfactual_request_id
- exact factual baseline revision IDs
- intervention set with typed variable/value/unit/effective interval
- invariant assumptions
- model_revision_id
- applicability profile
- as_of_utc

### P6ProjectionDTO

- projection_id
- request_id
- model_revision_id
- factual_source_refs
- assumptions
- projected value/distribution or explicit unavailable state
- uncertainty
- validity/applicability
- sensitivity summary
- created_at_utc
- logical_content_hash

### P6AdmissionStateDTO

The admission contract must remain fail-closed until protected-main M9 Exit GO. Current/latest/default model or source resolution is forbidden.

## Model and applicability authority

Before any executable P6 forecast is admitted, M9 must freeze:

- permitted model families and exact implementation versions;
- training-window and leakage rules;
- validation/holdout requirements;
- minimum evidence and data sufficiency;
- domain/applicability representation;
- uncertainty semantics and calibration requirements;
- intervention/counterfactual identifiability rules;
- no-causal-claim boundary unless explicit causal authority exists;
- model retirement/supersession and exact historical replay.

A model may be mathematically executable yet product-invalid when its applicability gate fails.

## Approval and release

Candidate workflow:

DRAFT -> VALIDATED -> IN_REVIEW -> APPROVED -> RELEASED

Every state change is a new immutable revision with request-id idempotency and audit evidence. Approval of a model does not approve every future request; request applicability is evaluated independently.

## Interoperability

P6 must consume exact existing DTOs/revisions rather than copying their semantics into new local types. External interchange must retain:

- explicit capability/assessment phase;
- subject/composition/mission scope;
- units;
- timestamp/as-of;
- provenance;
- model version;
- uncertainty;
- availability/applicability;
- claim level.

## M9 candidate task decomposition

1. **M9-GOV-001** — freeze P6 model/projection/causal-claim authority and C4 admission guard.
2. **M9-DATA-001** — exact forecast/counterfactual request substrate and leakage-safe dataset snapshots.
3. **M9-MODEL-001** — deterministic model-revision training/validation artifact.
4. **M9-MODEL-002** — applicability/domain/uncertainty calibration product.
5. **M9-PROJ-001** — exact forecast projection and explicit unavailable/OOD output.
6. **M9-CF-001** — counterfactual request/intervention projection with assumption trace.
7. **M9-LONG-001** — model/projection longitudinal replay and supersession.
8. **M9-API-001** — exact model/request/projection APIs, no current/latest/default.
9. **M9-GUI-001** — fact-vs-projection visual separation, uncertainty/applicability visible.
10. **M9-SEC-001** — role/privacy/model-release authorization and audit/export enforcement.
11. **M9-TST-001** — leakage, replay, applicability, uncertainty and non-identifiability Golden/negative suite.
12. **M9-TST-002** — Win/Linux/API/GUI/release non-regression and P1-P5 immutable provenance.
13. **M9-EXIT-001** — protected-main M9 Exit and P6 admission evidence.

## Required negatives

M9 tests must reject:

- future-information leakage;
- same-outcome leakage;
- source revision aliasing;
- current/latest/default model resolution;
- unsupported causal language;
- OOD projection encoded as zero;
- missing uncertainty where authority requires it;
- hidden replacement of P4/P5 source revision;
- counterfactual intervention without explicit assumptions;
- model/profile mismatch;
- unauthorized direct identity/export;
- P6 claim before M9 Exit GO.

## M8 boundary

This runway is documentation and task/interface/test design only. M8 must not create an executable P6 model, P6 API product, or P6 admission evidence.
