# M9 Batch 3 counterfactual / advisory / API / GUI / security review

## Decision

Candidate status: **READY FOR STATIC REVIEW, THEN ONE EXACT-HEAD HOSTED CI RUN**.

Entry authority:

- Batch 2 protected-main merge: `d37a994d6efbaeec2d10022ec083015771c40152`
- Run #542: exactly 14/14 SUCCESS
- DB schema remains `1.6.0`
- P6 remains NOT ADMITTED

## M9-CF-001

The candidate adds deterministic exact counterfactual revisions bound to:

- exact P6 input snapshot;
- exact P4/P5 factual baseline refs;
- explicit typed interventions;
- explicit held-fixed assumptions;
- exact model revisions and artifact hashes;
- exact applicability profile;
- explicit applicability and identifiability;
- explicit uncertainty trace and original as-of cutoff.

The only authorized causal claim is the frozen default
`SCENARIO_PROJECTION_NON_CAUSAL`. No numeric intervention effect is invented
because no separately adopted causal-effect authority exists. The projection is
therefore an immutable scenario/assumption trace with
`SCENARIO_ONLY_NON_CAUSAL` identifiability. Any stronger causal claim fails
with `FAIL_CLOSED_P6_CAUSAL_CLAIM_NOT_AUTHORIZED`.

## M9-ASSESS-001

Recommendations are immutable `ADVISORY` revisions. They require:

- exact forecast and/or counterfactual source revisions;
- explicit objective/constraint set;
- explicit allowed training action space;
- exact source applicability and uncertainty;
- immutable DRAFT -> IN_REVIEW -> APPROVED/REJECTED -> RELEASED provenance;
- RELEASED transition revalidates exact source projections are still published and applicable.

Operational, tactical, targeting, weapon, engagement and command semantics are
rejected by the advisory action-space guard. Approval/release never converts a
projection into fact.

Separation of duties is enforced from the frozen role profile:

- MODEL_REVIEWER can release qualified models but cannot approve recommendations;
- INSTRUCTOR_EVALUATOR can approve recommendations but cannot release models;
- ADMIN_AUDITOR gets neither permission from administrative privilege.

## M9-API-001

The candidate exposes exact-ID transport for model, forecast, counterfactual and
recommendation reads plus governed forecast/counterfactual execution,
recommendation create/approval, model release and export.

All business execution stays in the Application layer. API routes do not resolve
current/latest/default aliases, recompute products, substitute sources or touch
persistence directly. Mutation requests are request-id bound and idempotent.

## M9-GUI-001

The GUI projection model visibly separates:

1. `P1_P5_FACTUAL_HISTORY` -- immutable exact source refs;
2. `P6_FORECAST_PROJECTION`;
3. `P6_COUNTERFACTUAL_PROJECTION`;
4. `P6_TRAINING_ADVISORY`.

Exact revision/model refs, applicability, uncertainty and recommendation
approval state remain visible. Presentation asserts:

- `business_recompute=false`;
- `persistence_access=false`;
- `projection_to_fact_upgrade=false`.

## M9-SEC-001

Runtime security is projected from
`P6_ROLE_PRIVACY_RELEASE_PROFILE:1.0.0`, including:

- role/scope checked forecast and counterfactual execution;
- recommendation approval and model-release separation;
- M8 subject-key pseudonym reuse, no new pseudonym scheme;
- direct identity projection only under frozen role/scope authorization;
- explicit export authorization;
- request-id audit evidence;
- sensitive training/model/recommendation payloads excluded from unrestricted
  audit records.

Even a fully authorized ADMIN_AUDITOR export remains blocked before M9 Exit.
Candidate/internal validation never becomes an external P6 claim.

## M9-TST-002

The contract suite covers:

- deterministic exact forecast/counterfactual/recommendation identity;
- non-causal counterfactual boundary;
- command-upgrade rejection;
- model-release vs recommendation-approval separation;
- idempotent mutation;
- exact-ID API with alias rejection;
- GUI fact/projection separation;
- pre-Exit export fail closed;
- sensitive audit payload exclusion.

The existing Batch 1 interop negative suite remains part of full CI and continues
to cover unversioned external aliases, lossy mapping and fact/projection
conflation. Existing M5-M8 suites remain unchanged and therefore act as
non-regression qualification on the same exact candidate. TST-002 also pins
the protected P4/P5 authority/profile SHA256 values and DB schema `1.6.0`
from the unchanged BASELINE_LOCK.

No Canonical artifact, BASELINE_LOCK, migration, schema or CI workflow is
modified in this batch.
