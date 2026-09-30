# 飞机机载数据评估系统软件开发实施基线 SDIB-1.6

**Software Development Implementation Baseline — SDIB-1.6**  
**Parent baseline:** SDIB-1.5  
**Core Baseline:** CB-1.4.0  
**DB schema authority:** 1.6.0  
**Current protected-main entry:** `892e4a64a321be9c7252b66207a7d1d90a6ce98d` / Run #494 (`36697493917`) / 14/14 PASS  
**Current admitted capability:** `P2_M6_QUALIFIED`  
**Program policy:** #149  
**M7 baseline tracking:** #168  
**P3 C3 authority closure:** #169  
**M8/P4-P5 design runway:** #170  
**Release date:** 2026-09-30

## 0. Revision purpose

SDIB-1.6 is the post-M6 C1 implementation refinement for **M7 — P3 Capability/Twin Activation**. It converts the completed #155 P3 design runway into an executable M7 task/batch baseline while preserving immutable P1 observed facts, immutable P2 attribution products and all M5/M6 qualification guarantees.

This revision does **not** itself admit P3. P3 remains a candidate until protected-main exact M7 Exit GO. P4-P6 remain dormant.

The machine task manifest is `M7_TASK_BASELINE.json`.

## 1. Entry evidence and authority hierarchy

M7 starts only from the exact protected-main M6 Exit qualification:

- source revision: `892e4a64a321be9c7252b66207a7d1d90a6ce98d`
- Cross-platform CI: Run #494 / `36697493917`
- required jobs: 14/14 PASS
- M6 Exit: `GO`
- admitted capability: `P2_M6_QUALIFIED`
- current machine authority: CB-1.4.0
- DB schema: 1.6.0

Authority precedence remains:

1. `BASELINE_LOCK.json` / CB-1.4.0;
2. machine-readable Canonical artifacts;
3. adopted C3 P3 authority/profile;
4. this SDIB implementation organization;
5. implementation code/tests.

Implementation may not invent missing P3 model, validation, applicability, claim or managed-object semantics.

## 2. M7 capability boundary

M7 corresponds to **P3 Intrinsic Capability / Aircraft Twin**, with the frozen extension interpretation **Reference-condition Longitudinal Capability / Aircraft Twin**.

Existing DB 1.6.0 products are reused:

- `capability.capability_model`
- `capability.capability_surface`
- `capability.aircraft_twin_revision`
- `capability.intrinsic_capability_estimate`

M7 inputs include validated exact P2 products, lifecycle/configuration history, as-of dataset snapshots and model-validation evidence.

Mandatory invariants:

- P1 observed, P2 adjusted and P3 capability/twin products remain separate immutable layers.
- P2 `NOT_IDENTIFIABLE` remains valid P2 evidence but is never silently converted into a numeric P3 training target.
- historical reads and replay never fall back to current/latest/default identities.
- future information and same-episode leakage are prohibited.
- independent-aircraft, episode, observation and effective-evidence counts remain distinct.
- lifecycle/config/software/maintenance changes are explicit segmentation inputs when governed evidence exists.
- twin is a published capability read model, not real-time World state.
- default interpretation remains reference-condition longitudinal estimate; stronger intrinsic wording requires independently governed evidence.
- DB schema remains 1.6.0 unless a separate explicit C3 schema change is adopted; shadow schema is forbidden.

## 3. C3 fail-closed authority blocker

Issue #169 is the M7 semantic blocker. Before dependent P3 tasks may claim completion, machine authority must freeze:

- exact P2-to-P3 eligible projection and NOT_IDENTIFIABLE exclusion semantics;
- lifecycle/configuration/as-of segment identity and leakage rules;
- training/validation snapshot identities and independent-aircraft accounting;
- exact model-spec/plugin/profile identity and deterministic execution semantics;
- validation metrics, applicability/OOD/validity-domain statuses and thresholds;
- `capability_model.model_artifact_uri` and `capability_surface.dataset_uri` binding to existing sealed ACTIVE `registry.object_reference.managed_uri` with matching hashes;
- exact model/surface/twin/estimate DTO/application projection;
- twin revision component ordering, evidence snapshot, supersession and replay identity;
- exact P3 claim tiers and independent-evidence requirement;
- immutable P3 publication/evidence binding and C4 admission state.

No algorithm/plugin/threshold is selected by SDIB-1.6 itself.

## 4. Rolling detailed-design policy

Program #149 requires one-milestone-ahead rolling design:

- while M7 implementation is active, M8/P4-P5 detailed design is refined in #170 from actual P3 evidence;
- P4/P5 task/interface/test contracts and authority gaps may be refined;
- P4/P5 implementation/admission remains forbidden before M7 protected-main Exit GO;
- P4 individual/human-machine and P5 team/mission scopes remain separated;
- distant M9/P6 algorithms are not pre-committed during M7.

## 5. M7 task inventory

| Task | WS | Deliverable |
| --- | --- | --- |
| M7-GOV-001 | WS-GOVERNANCE | P3 implementation authority closure |
| M7-GOV-002 | WS-GOVERNANCE | C4 P3 admission / claim guard |
| M7-DATA-001 | WS-DATA | Exact immutable P2 longitudinal eligibility projection for P3 |
| M7-DATA-002 | WS-LONGITUDINAL | Lifecycle/configuration/as-of segment snapshot |
| M7-DATA-003 | WS-LONGITUDINAL | Model-validation evidence snapshot and claim-tier eligibility |
| M7-CAP-001 | WS-CAPABILITY | Deterministic capability-model training-set materialization |
| M7-CAP-002 | WS-CAPABILITY | Governed capability-model execution and validation provenance |
| M7-CAP-003 | WS-CAPABILITY | Capability-surface generation and validity-domain product |
| M7-CAP-004 | WS-CAPABILITY | Immutable aircraft twin revision publication |
| M7-CAP-005 | WS-CAPABILITY | P3 reference-condition/intrinsic capability estimate |
| M7-API-001 | WS-API | Exact twin-revision-bound P3 read API |
| M7-GUI-001 | WS-GUI | P1 observed / P2 adjusted / P3 reference-condition product separation |
| M7-GOV-003 | WS-GOVERNANCE | M8/P4-P5 one-milestone-ahead detailed-design runway |
| M7-TST-001 | WS-TEST | P3 authority/admission/leakage/managed-object Golden-negative suite |
| M7-TST-002 | WS-TEST | Capability-model/surface synthetic fixture family |
| M7-TST-003 | WS-TEST | Deterministic model/surface Golden and replay qualification |
| M7-TST-004 | WS-TEST | Twin revision/API/GUI replay, cross-platform equivalence and P1/P2 non-regression |
| M7-TST-005 | WS-TEST | M7 Exit review and C4 P3 admission decision |

Exact dependencies and acceptance text are authoritative in `M7_TASK_BASELINE.json`.

The canonical M7 required workstreams remain CAPABILITY, LONGITUDINAL, TEST, GUI and GOVERNANCE. WS-DATA and WS-API are explicit supporting workstreams required by the concrete P3 implementation path; they do not alter the milestone meaning.

## 6. Coarse implementation batches

### M7 Batch 1 — P3 authority + exact P2/lifecycle/validation substrate
`M7-GOV-001`, `M7-GOV-002`, `M7-DATA-001`, `M7-DATA-002`, `M7-DATA-003`, `M7-TST-001`.

### M7 Batch 2 — Capability model + surface
`M7-CAP-001`, `M7-CAP-002`, `M7-CAP-003`, `M7-TST-002`, `M7-TST-003`.

### M7 Batch 3 — Aircraft twin + P3 estimate + API/GUI + M8 runway
`M7-CAP-004`, `M7-CAP-005`, `M7-API-001`, `M7-GUI-001`, `M7-GOV-003`, `M7-TST-004`.

### M7 Batch 4 — M7 Exit / P3 admission
`M7-TST-005`.

## 7. M7 Exit

M7 Exit may be `GO` only when all 18 tasks have exact accepted evidence, C3 #169 and the adopted P3 execution/profile authority are closed, managed-object/validation/applicability/claim gates pass, P1/P2 remain immutable, Windows/Linux parity and exact replay pass, retained M5/M6 guarantees remain regression-clean, M8 design-runway evidence exists without P4/P5 activation, `failed_acceptance=[]`, and the actual protected-main merge SHA passes all 14 required jobs.

Only after protected-main exact M7 Exit GO may P3 be claimed admitted.

## 8. Future roadmap

- **M8 / P4+P5:** detailed design during active M7 implementation.
- **M9 / P6:** detailed design during active M8 implementation.

No future capability is activated by this baseline.

## 9. Merge and evidence governance

Every M7 PR remains subject to exact-head Hosted CI 14/14, head/ref/base equality, mergeability, `expected_head_sha` guarded merge, exact merge-parent verification and actual protected-main merge-SHA 14/14 before issue/task completion.
