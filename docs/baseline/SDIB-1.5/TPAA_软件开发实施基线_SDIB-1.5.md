# 飞机机载数据评估系统软件开发实施基线 SDIB-1.5

**Software Development Implementation Baseline — SDIB-1.5**  
**Parent baseline:** SDIB-1.4  
**Core Baseline:** CB-1.4.0  
**DB schema authority:** 1.6.0  
**Current protected-main entry:** `aae1e692774f7c10114d66fd79acb254c2aabfef` / Run #472 (`36556569965`) / 14/14 PASS  
**Program policy:** #149  
**M6 baseline tracking:** #150  
**P2 C3 authority closure:** #151  
**Release date:** 2026-09-29

## 0. Revision purpose

SDIB-1.5 is the post-M5 C1 implementation refinement for **M6 — P2 Attribution Activation**. It converts the frozen M6 roadmap boundary into an executable task/batch baseline while preserving all admitted P1 semantics and M5 product guarantees.

This revision does **not** itself admit P2. P2 remains a candidate capability until protected-main exact M6 Exit GO. P3-P6 remain dormant.

The machine task manifest is `M6_TASK_BASELINE.json`; it is the exact task/batch inventory for this refinement.

## 1. Entry evidence and authority hierarchy

M6 refinement starts only from the latest protected-main PASS prerequisite:

- source revision: `aae1e692774f7c10114d66fd79acb254c2aabfef`
- Cross-platform CI: Run #472 / `36556569965`
- required jobs: 14/14 PASS
- current capability: `P1_M5_QUALIFIED`
- current machine authority: CB-1.4.0
- current DB schema: 1.6.0

Authority precedence remains:

1. `BASELINE_LOCK.json` / CB-1.4.0 Core rules;
2. machine-readable Canonical artifacts;
3. adopted C3 P2 authority;
4. this SDIB implementation organization;
5. implementation code/tests.

Implementation code may not invent missing P2 semantics.

## 2. M6 capability boundary

M6 corresponds to **P2 Context Attribution & Normalization**.

P2 consumes immutable published P1 observations plus frozen factor/context views, a reference condition, cohort/specification and quality/independence metadata. P2 products include:

- `assessment.factor_feature_set`
- `assessment.attribution_run`
- `capability.adjusted_capability_estimate`

Required P2 outputs include an adjusted value **or governed status**, reference condition, factor effects/candidate contributions, unexplained component/residual, uncertainty, identifiability state, evidence and version.

The following invariants are mandatory:

- `NOT_IDENTIFIABLE` is a valid result and must not be converted into a fabricated adjusted value.
- P2 never overwrites the P1 observed value.
- Attribution/contribution is association/model-conditioned unless independent causal evidence exists.
- Future information and same-episode leakage are prohibited.
- historical interpretation may not fall back to current/latest refs.
- DB schema remains 1.6.0 unless a separate explicit C3 schema change is adopted; shadow schema is forbidden.

## 3. C3 fail-closed authority blocker

Issue #151 is the M6 semantic blocker. Before dependent P2 tasks may claim completion, machine authority must freeze:

- factor feature-spec identity/version and allowed context/factor bindings;
- reference-condition identity/representation;
- cohort/specification identity, comparability and evidence-independence rules;
- attribution-spec/model-plugin identity/version;
- exact identifiability statuses and reason codes, including `NOT_IDENTIFIABLE`;
- uncertainty interval/object semantics;
- factor effect/candidate contribution representation and causal-claim boundary;
- knowledge-time/as-of rules and leakage rejection;
- exact cross-layer DTO/application projection;
- immutable P2 Release/evidence binding and replay interpretation.

M6 implementation remains fail-closed where these semantics are required.

## 4. Rolling detailed-design policy

Program policy #149 adopts **one-milestone-ahead rolling design**:

- while M6 implementation is active, M7/P3 detailed design is refined from real P2 implementation evidence;
- M7 design may define task/interface/test contracts and authority-gap registers;
- P3 code/claim remains forbidden until M6 protected-main Exit GO;
- while M7 implementation is active, refine M8; while M8 implementation is active, refine M9;
- distant model/algorithm choices are not frozen before evidence justifies them.

This policy implements the original M6-M9 roadmap rule that future details are refined from preceding capability evidence rather than pre-committed speculations.

## 5. M6 task inventory

| Task | WS | Deliverable |
| --- | --- | --- |
| M6-GOV-001 | WS-GOVERNANCE | P2 implementation authority closure |
| M6-GOV-002 | WS-GOVERNANCE | C4 P2 admission / feature-gate claim guard |
| M6-DATA-001 | WS-DATA | Immutable P1 observation eligibility projection for P2 |
| M6-DATA-002 | WS-DATA | Governed factor / reference-condition / cohort snapshot |
| M6-DATA-003 | WS-DATA | Knowledge-time, leakage and evidence-independence guard |
| M6-CAP-001 | WS-CAPABILITY | Factor feature-set materialization |
| M6-CAP-002 | WS-CAPABILITY | Attribution execution and provenance contract |
| M6-CAP-003 | WS-CAPABILITY | Identifiability and NOT_IDENTIFIABLE result semantics |
| M6-CAP-004 | WS-CAPABILITY | Context-adjusted estimate + uncertainty / residual / factor effects |
| M6-GUI-001 | WS-GUI | Observed-vs-adjusted product separation |
| M6-GUI-002 | WS-GUI | P2 attribution evidence / uncertainty / diagnostics drill-down |
| M6-GOV-003 | WS-GOVERNANCE | M7/P3 one-milestone-ahead detailed-design runway |
| M6-TST-001 | WS-TEST | P2 authority / admission / leakage Golden-negative suite |
| M6-TST-002 | WS-TEST | Factor / reference / cohort fixture family |
| M6-TST-003 | WS-TEST | P2 attribution Golden / identifiability qualification |
| M6-TST-004 | WS-TEST | P2 cross-platform logical equivalence / replay / P1 non-regression |
| M6-TST-005 | WS-TEST | M6 Exit review and C4 P2 admission decision |

Exact acceptance/dependency text is authoritative in `M6_TASK_BASELINE.json`.

## 6. Coarse implementation batches

### M6 Batch 1 — P2 authority + immutable input / factor-reference-cohort substrate

`M6-GOV-001`, `M6-GOV-002`, `M6-DATA-001`, `M6-DATA-002`, `M6-DATA-003`, `M6-TST-001`.

### M6 Batch 2 — Attribution engine + identifiability + adjusted estimate

`M6-CAP-001`, `M6-CAP-002`, `M6-CAP-003`, `M6-CAP-004`, `M6-TST-002`, `M6-TST-003`.

### M6 Batch 3 — Product presentation + parity + M7 rolling-design runway

`M6-GOV-003`, `M6-GUI-001`, `M6-GUI-002`, `M6-TST-004`.

### M6 Batch 4 — M6 Exit / P2 admission

`M6-TST-005`.

## 7. M6 Exit

M6 Exit may be `GO` only when all 17 tasks have accepted exact evidence, C3 #151 is adopted, leakage/identifiability/uncertainty gates pass, P1 remains immutable, Windows/Linux parity and replay pass, M5 product guarantees remain regression-clean, M7 design-runway evidence exists without P3 activation, `failed_acceptance=[]`, and the actual protected-main merge SHA passes the required 14-job CI.

Only after protected-main exact M6 Exit GO may the product claim P2 admission.

## 8. Future P roadmap

- **M7 / P3:** detailed design during active M6 implementation.
- **M8 / P4+P5:** detailed design during active M7 implementation.
- **M9 / P6:** detailed design during active M8 implementation.

No future P capability is activated by this baseline.

## 9. Merge and evidence governance

Every implementation PR remains subject to exact-head Hosted CI 14/14, head/ref/base equality, mergeability, expected-head guarded merge, exact merge-parent verification, and actual protected-main merge-SHA 14/14 before issue/task completion.
