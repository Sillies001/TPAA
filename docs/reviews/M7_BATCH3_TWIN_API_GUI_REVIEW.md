# M7 Batch 3 — Aircraft Twin / P3 Estimate / Exact API / Three-Layer GUI Review

## Identity

- Program: #149
- Batch tracker: #176
- M8 design runway: #170
- Parent protected-main SHA: `df32b081747e3526e13d974f818cc58125c16fd3`
- Parent protected-main Run: #504 / `36739428626` / 14 of 14 PASS
- Adopted P3 authority/profile: 1.0.0
- DB schema: 1.6.0 unchanged

## Batch scope

This batch implements exactly:

- M7-CAP-004 — immutable aircraft twin revision publication;
- M7-CAP-005 — exact P3 reference-condition capability estimate;
- M7-API-001 — exact twin-revision-bound P3 read API;
- M7-GUI-001 — visible P1 observed / P2 adjusted / P3 reference-condition separation;
- M7-GOV-003 — M8/P4-P5 one-milestone-ahead detailed-design runway;
- M7-TST-004 — twin/API/GUI replay, cross-platform deterministic identity and P1/P2 non-regression.

M7 Exit / P3 external admission remains outside this batch.

## Immutable aircraft twin revision

The implementation reuses DB 1.6.0 `capability.aircraft_twin_revision` without a shadow schema.

Twin identity is UUIDv5 over deterministic canonical material binding:

- aircraft_id;
- revision_no;
- ordered component model bindings;
- exact model artifact hash and surface dataset hash;
- exact model/surface managed-object reference IDs;
- config_snapshot_id;
- evidence_snapshot_id;
- valid_from / valid_to;
- as_of_data_time;
- published_at;
- supersedes_twin_revision_id.

`component_model_refs` ordering is semantic and participates in identity. Reversing the same component list produces a different twin revision identity.

A successor revision:

- must reference the exact prior twin revision;
- increments revision_no;
- receives a new identity;
- never mutates the prior twin row.

The twin is a capability read model, not Ground Truth / Perceived World / Action World state and never represents same-episode reconstructed truth.

## P3 estimate

The implementation reuses `capability.intrinsic_capability_estimate` as the Core carrier while preserving the profile-v1 claim boundary.

The cross-layer estimate includes:

- exact twin_revision_id;
- exact capability_type;
- normalized condition_point;
- nullable value;
- unit;
- uncertainty bounds and exact source surface identity/hash;
- validity_domain_status;
- claim_level;
- as_of_time;
- created_at.

Profile v1 only authorizes `REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE`.

The Core table name must not be interpreted as permission to emit `INTRINSIC_CAPABILITY_ESTIMATE`; stronger wording continues to fail closed through the adopted claim authority.

Condition point v1 is exact:

- SESSION_ORDER;
- reference_condition_id.

IN_DOMAIN evaluates the exact governed component surface. OUT_OF_DOMAIN returns null value and null bounds. Zero substitution is forbidden.

The estimate as-of is bound to the exact twin `as_of_data_time`; publication time is not used as a substitute.

## Admission-gated API

The API exposes exact-ID routes only:

- exact twin revision;
- exact twin revision + estimate;
- exact twin revision + estimate + three-layer workspace.

No current/latest/default route or implicit newest revision exists.

Admission evidence is server-side construction state on `M7WorkspaceService`; it is not accepted from client URL/query/body data. Therefore pre-M7-Exit API access remains fail-closed even though the transport code exists.

Synthetic admitted evidence is used only by deterministic contract tests to qualify transport mechanics. It does not constitute program admission evidence.

API/Application reads return stored projections and never execute model, surface, twin or estimate computation.

## Three-layer GUI

The M7 workspace visibly separates:

1. `P1_OBSERVED`
2. `P2_ADJUSTED`
3. `P3_REFERENCE_CONDITION_LONGITUDINAL`

The P3 presentation carries:

- twin revision ID / revision number;
- estimate ID;
- exact component model refs;
- reference condition;
- session order;
- value/unit;
- uncertainty;
- validity-domain status;
- claim level;
- as-of time.

The GUI rejects:

- transport logical-hash drift;
- layer identity drift;
- twin/estimate mismatch;
- stronger claim wording;
- IN_DOMAIN with missing value/bounds;
- OUT_OF_DOMAIN with fabricated numeric value/bounds.

The GUI contains no storage access and no P3 business recomputation.

## P1/P2 non-regression

P1/P2 inputs enter the M7 workspace as exact immutable layer evidence:

- exact release ID;
- exact logical product hash;
- exact projection.

Registration validates the canonical hash. Reads copy projections and never mutate them.

Repository re-registration of the same P3 estimate identity with different P1/P2 evidence fails as an immutable conflict.

## Replay and deterministic qualification

TST-004 freezes deterministic synthetic identities:

- revision-1 twin: `70e19664-804d-5a98-871d-69d217d4ffef`
- in-domain estimate: `4d130ceb-8bb1-5fe2-96fc-45cfd76f4d21`

Coverage includes:

- same ordered component refs -> same twin identity;
- reversed ordered refs -> different twin identity;
- supersession/new-revision behavior;
- exact estimate replay;
- OOD null semantics;
- stronger claim rejection;
- pre-Exit API 423 fail-closed;
- admitted exact-ID API transport mechanics;
- GUI logical hash and claim drift;
- P1/P2 hash non-regression;
- no current/latest/recompute/storage leakage;
- DB schema 1.6.0 and later-phase inactivity.

Windows/Linux execute the same canonical JSON + UUIDv5 identity logic under required CI.

## Completion gate

Candidate evidence only until:

1. exact PR head Hosted CI 14/14 PASS;
2. guarded merge with expected head SHA;
3. merge parent1/parent2 exact verification;
4. protected-main exact merge-SHA push CI 14/14 PASS.

P3 remains NOT ADMITTED until M7 Batch 4 / M7 Exit GO.
