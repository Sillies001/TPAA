# M6 Batch 3 P2 Workspace / Diagnostics / Replay Review

## Identity

- Tracker: #164
- Program: #149
- Batch 2 protected-main prerequisite: #158 (closed)
- M7/P3 design runway: #155 (design only)
- Protected-main base: `551e620cee6b8f3a5b406790f08443c485bf234b`
- Protected-main qualification: Run #490 / `36674275763` / push / main / 14 of 14 SUCCESS
- DB schema: 1.6.0 unchanged
- P2 external admission: NOT ACTIVE until M6 Exit GO

## M6-GOV-003

#155 now contains task/interface/test-level M7/P3 design grounded in the actual P2 implementation:

- exact immutable P2 -> P3 input boundary;
- NOT_IDENTIFIABLE excluded from numeric training targets;
- lifecycle/configuration/as-of segmentation;
- capability-model/surface/twin/intrinsic-estimate existing DB carriers;
- independent-aircraft vs observation/episode evidence counts;
- model applicability/OOD and independent validation requirements;
- sealed managed-object URI prerequisite for model/surface artifacts;
- immutable Twin revision/replay identity;
- reference-condition estimate wording separated from independently supported intrinsic claims.

Batch 3 adds evidence that all P2 product layers remain explicitly release/run/reference/model bound through Application/API/GUI. No P3 implementation or claim is activated.

## M6-GUI-001 — Observed vs Adjusted

New M6 workspace read path:

`immutable P2/P1 products -> M6WorkspaceService -> FastAPI DTO -> GUI presentation adapter`.

The read path never calls the attribution engine.

The comparison projection preserves separate sections:

### Observed P1
- source observation id;
- source P1 Release id;
- metric semantic id/version;
- capability type;
- observed value/unit;
- coverage/confidence;
- P1 evidence-set id;
- P1 knowledge time.

### Adjusted P2
- estimate id;
- P2 Release id;
- attribution run id;
- reference condition id;
- status;
- adjusted value;
- uncertainty bounds/method/level;
- residual;
- factor effects;
- factor-effect semantics;
- claim level;
- governed reason codes;
- P2 evidence set;
- estimate time.

The GUI presents separate semantic states:
- P2_IDENTIFIABLE;
- P2_NOT_IDENTIFIABLE;
- P2_SYSTEM_ERROR.

NOT_IDENTIFIABLE is never rewritten as zero, N/A, generic error or a synthetic numeric value.

## M6-GUI-002 — Diagnostics

Diagnostics expose exact, already-computed evidence:

- factor feature-set id/spec/order/values/missing mask/World refs/coverage/confidence/input hash;
- feature-spec context-artifact id/version/hash;
- reference-condition and artifact identity;
- cohort dataset snapshot/data hash/spec/comparability/counts/knowledge cutoff;
- attribution spec/plugin versions;
- exact run request hash;
- model artifact hash/URI;
- run diagnostics;
- uncertainty method/level;
- factor effects labelled MODEL_CONDITIONED_ASSOCIATION;
- ASSOCIATION_ONLY claim level;
- residual/unexplained component;
- governed reason codes;
- source P1 Release/observation and knowledge time;
- P2 Release/estimate time;
- exact as-of time.

The Application layer verifies model-artifact SHA-256 before projection. The GUI verifies both transport logical-product hash and model-artifact hash.

## API routes

Read-only exact-identity routes:

- `GET /m6/p2/releases/{p2_release_id}/estimates/{estimate_id}/comparison`
- `GET /m6/p2/releases/{p2_release_id}/estimates/{estimate_id}/diagnostics`

Release/estimate mismatch fails closed. No current/latest/default route or fallback is introduced.

## M6-TST-004

The Batch 3 contract suite proves:

1. P1 observed and P2 adjusted are distinct products.
2. source P1 Release identity is preserved.
3. P2 Release/estimate/run/reference identities are preserved.
4. NOT_IDENTIFIABLE remains null + governed reasons.
5. exact factor-effect semantics stay MODEL_CONDITIONED_ASSOCIATION.
6. claim level stays ASSOCIATION_ONLY.
7. residual is separately projected.
8. uncertainty bounds/method/level are unchanged.
9. diagnostics preserve feature/reference/cohort/model provenance.
10. exact-release API mismatch fails closed.
11. repeated read/replay produces identical comparison logical hash.
12. repeated read/replay produces identical diagnostics logical hash.
13. model-artifact hash drift fails closed before read projection.
14. transport logical-hash drift fails closed in GUI.
15. GUI does not import Application/Assessment/Storage or recompute attribution.
16. API depends on Application only and does not import Assessment/Storage.
17. historical read source contains no /current or /latest fallback and no attribution execution/materialization call.
18. DB schema remains 1.6.0 and Batch 3 creates no shadow schema.

Because the same contract suite runs in the required Windows and Linux CI jobs and uses canonical sorted-key compact JSON hashes, the exact candidate provides cross-platform logical-equivalence evidence when both platform jobs pass.

## Non-goals

- no P2 external admission;
- no M6 Exit decision in Batch 3;
- no P3 implementation/admission;
- no DB migration;
- no factor taxonomy change;
- no attribution recomputation in Application/API/GUI;
- no causal wording upgrade.

## Completion gate

M6-GOV-003 / GUI-001 / GUI-002 / TST-004 remain NOT COMPLETE until:

1. this exact Batch 3 PR head passes 14/14 Hosted CI;
2. merge uses expected_head_sha;
3. actual merge parents are verified;
4. actual protected-main merge SHA passes 14/14 Hosted CI.

Only then may Batch 4 M6 Exit/admission implementation begin from that exact protected-main SHA.
