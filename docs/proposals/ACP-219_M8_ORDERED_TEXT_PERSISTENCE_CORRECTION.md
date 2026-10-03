# ACP-219 — DB 1.8.0 ordered-text persistence authority correction

Status: **PROPOSED / NOT ADOPTED**

ACP-219 is the minimal successor to adopted ACP-216 / DB 1.7.0. It resolves only the two residual PIQB B2 exact-persistence gaps recorded in Issue #219:

1. ordered text `P4AssessmentRevision.machine_evidence_ids`;
2. ordered text `P5AssessmentRevision.objective_result_refs`.

The candidate adds exactly two canonical relations: `assessment.actor_assessment_machine_evidence_ref` and `assessment.mission_assessment_objective_ref`. No historical M8/M9 semantic authority is rewritten, no shadow JSON/audit/object schema is permitted, and no P6 relation is added.

Formal adoption requires exact-head 14/14 candidate CI, guarded merge, exact merge-parent verification, then protected-main exact-merge-SHA 14/14 CI with reviewer GO.
