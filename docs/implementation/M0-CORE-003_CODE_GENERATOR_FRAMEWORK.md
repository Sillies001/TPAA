# M0-CORE-003 — Code Generator Framework

Status: COMPLETE
Baseline: SDIB-1.0
Core Baseline: CB-1.4.0
Depends On: M0-CORE-001, M0-CORE-002

## 1. Objective

Implement a deterministic code-generation framework that transforms approved Canonical artifacts into generated Python source artifacts required by TPAA.

All Canonical inputs MUST be loaded through `CanonicalArtifactLoader`. Direct parsing of Canonical JSON by individual generators is prohibited. Generated source is a projection of Canonical authority and MUST NOT become a second authority.

## 2. Canonical Source Mapping

| Projection | Canonical machine authority |
| --- | --- |
| Capability Phase (P) registry | `CAPABILITY_PHASE_REGISTRY` |
| Development Milestone (M) registry | `DEVELOPMENT_MILESTONE_REGISTRY` |
| Engineering Workstream (WS) registry | `ENGINEERING_WORKSTREAM_REGISTRY` |
| Stage registry | `STAGE_REGISTRY` |
| P1 Metric registry | `P1_METRIC_CATALOG` |
| Cross-layer DTO/types | `CROSS_LAYER_DTO_CONTRACTS` |
| Baseline metadata projection | `BASELINE_LOCK` metadata exposed by `CanonicalArtifactLoader` |

`TERMINOLOGY_REGISTRY` may be used later for parity/cross-reference validation, but MUST NOT replace the entity-specific authorities above.

## 3. Scope

M0-CORE-003 SHALL provide generation support for controlled enums, P/M/WS registries, Stage registry, Metric registry, DTO/typed contracts, and baseline metadata projection. It SHALL also provide a normalized generator IR, deterministic rendering/writing, provenance, a generation manifest, a repeatable developer command, and unit/contract tests.

## 4. Explicit Non-Scope

M0-CORE-004 retains enforcement that generated source is read-only, CI regenerate-diff enforcement, rejection of manually edited generated source, and generated-source governance policy. M0-CORE-003 may provide deterministic output and provenance needed by M0-CORE-004, but SHALL NOT claim M0-CORE-004 completion.

## 5. Authority Boundary

`BASELINE_LOCK → CanonicalArtifactLoader → validated Canonical artifact → normalization/IR → renderer → generated source`.

Generators MUST NOT bypass `CanonicalArtifactLoader`. Markdown, source comments, or manually maintained Python constants MUST NOT be used as machine authority.

## 6. Architecture

- **Source layer** — receives validated artifacts exclusively from `CanonicalArtifactLoader`.
- **Normalization / IR layer** — converts Canonical structures to immutable generator models; rejects duplicates, unresolved references, unsupported constructs, and ambiguity rather than guessing.
- **Renderer layer** — converts IR to deterministic UTF-8/LF bytes; never reads Canonical files itself and never embeds timestamps, host paths, usernames, hostnames, locale-dependent output, or randomness.
- **Writer layer** — writes only repository-relative declared outputs; detects path collisions; normalizes UTF-8/LF/final newline for Python text.
- **Manifest layer** — records generator version, Core Baseline, source artifact identity/version/hash, output paths and output SHA-256.

## 7. Determinism Contract

For identical Canonical input and identical generator version, generation SHALL be byte-identical. A second generation run over an unchanged repository MUST produce identical bytes and identical generation manifest.

Generation MUST be independent from OS directory ordering, locale, wall-clock time, current user, absolute repository path, machine hostname, and random state.

## 8. Version Semantics

Generator code SHALL NOT invent missing Canonical artifact versions. `UNVERSIONED_BY_AUTHORITY` from `CanonicalArtifactLoader` is preserved as such. Consumer compatibility constraints are explicit implementation expectations, never hidden replacement authority.

## 9. Failure Semantics

Generation fails closed with deterministic reason codes including at minimum:

- `UNKNOWN_ARTIFACT`
- `UNSUPPORTED_ARTIFACT_SHAPE`
- `INVALID_IDENTIFIER`
- `DUPLICATE_IDENTIFIER`
- `DUPLICATE_VALUE`
- `UNRESOLVED_REFERENCE`
- `CONFLICTING_DEFINITION`
- `UNSUPPORTED_DTO_CONSTRUCT`
- `OUTPUT_PATH_COLLISION`
- `NON_DETERMINISTIC_OUTPUT`

Errors include generator ID, source artifact ID when applicable, offending identity/value when applicable, and detail.

## 10. Delivery Slices

### Slice 1 — Generator Kernel

Implement generator protocol, immutable result/source/file models, deterministic Python and JSON rendering, output collision detection, generation manifest, coordinator, baseline metadata projection, and the real `tpaa_dev.py generate` command.

Acceptance: identical inputs yield identical bytes; repeated generation is idempotent; no time/random/absolute-path fields exist; generated output and manifest hashes are deterministic.

### Slice 2 — Controlled P/M/WS Projections

Generate controlled capability-phase, milestone and workstream registries/enums from their entity-specific authorities. Detect Python-name collisions without synthesizing suffixes.

### Slice 3 — Stage Registry

Generate Stage profile/ordered-stage projection while preserving Canonical Stage identity and profile membership.

### Slice 4 — Metric Registry

Generate P1 Metric catalog projection without introducing new metric semantics; verify metric identity/reference parity.

### Slice 5 — DTO / Types

Generate supported cross-layer DTO types deterministically. Unsupported transport constructs fail closed rather than being approximated.

## 11. Test Strategy

1. IR/model unit tests
2. naming and renderer unit tests
3. negative normalization tests
4. generator-specific Canonical parity tests
5. generated-module import tests
6. full regeneration determinism test
7. existing repository regression tests

## 12. Implementation Feedback Rules

- Implementation-only detail → update this plan/task breakdown.
- Architectural choice → ADR as required by SDIB governance.
- Change to machine authority → stop implementation and use Baseline Change → Canonical → Lock → Validator before generator changes.

## 13. Completion Criteria

M0-CORE-003 may be marked COMPLETE only when all required generator families are implemented, all Canonical reads pass through `CanonicalArtifactLoader`, second generation is byte-identical, generated modules import, Canonical/generated parity tests pass, existing M0-CORE-001/002 tests do not regress, and this plan reflects the final implementation.

## 14. Current Implementation Record

- 2026-09-21 — v0.1 created; source-authority mapping frozen for implementation.
- 2026-09-21 — Slice 1 started with baseline metadata projection as the minimal vertical proof of the kernel.
- 2026-09-21 — Slice 2 P/M/WS projections passed exact Canonical identity parity.
- 2026-09-21 — Metric catalog inspection confirmed `structured_output_schema_id` is an authoritative nullable field (107 null / 9 string); generator validation was refined to preserve that domain rather than imposing a string-only implementation assumption.
- 2026-09-21 — DTO projection uses postponed annotations so Canonical cross-DTO references are preserved without imposing implementation-order authority.
- 2026-09-21 — DTO transport mapping was refined from actual authority: `number` projects to `int | float`; `object[]` projects explicitly to `list[dict[str, JSONValue]]`; only DTO-name arrays are treated as typed DTO lists. Unknown projection types remain fail-closed.
- 2026-09-21 — Slices 1–5 completed; repeat generation, importability, Canonical parity, loader-boundary and generated-byte drift tests pass. Task status advanced to COMPLETE; M0-CORE-004 remains separate.
