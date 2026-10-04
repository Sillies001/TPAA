# ACP-221 — M8 standalone annotation subject-context persistence correction

Status: **PROPOSED / NOT ADOPTED**. Tracks #221 and blocks PIQB B2 #209 from claiming complete restart fidelity.

DB 1.8.0 can persist `InstructorAnnotationRevision` in `debrief.annotation`, but a standalone `annotate_p4()` write does not durably preserve `subject_context_id`. The minimal successor authority adds exactly one relation:

`assessment.annotation_subject_context(annotation_id uuid PRIMARY KEY REFERENCES debrief.annotation(annotation_id), subject_context_id text NOT NULL REFERENCES assessment.p4_subject_context(subject_context_id))`.

No audit/body/object/hash shadow authority is permitted. P4SubjectContext/P5CompositionSnapshot port completeness remains runtime implementation work, not schema scope.

Adoption requires candidate exact-head 14/14 Hosted CI, guarded merge, and protected-main exact-merge-SHA 14/14 with reviewer GO.
