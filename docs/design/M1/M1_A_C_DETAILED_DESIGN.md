# M1-A / M1-B / M1-C Detailed Design Baseline

## 1. Scope and authority

This document prepares the first three M1 construction waves without starting M1 feature implementation before admission.

It is an implementation-design artifact, not a semantic authority. Canonical field identity, DTO shape, Stage semantics, Metric semantics, persistence schema and authority hashes remain owned by CB-1.4.0 machine-readable artifacts.

Machine companion:

`docs/design/M1/M1_A_C_DETAILED_DESIGN.json`

Primary authorities:

- SDIB-1.0.1 §19.2–§19.4;
- SDIB-1.0.1 §21–§23;
- `CORE_RULES.json`;
- `CORE_LOGICAL_MODEL.json`;
- `CROSS_LAYER_DTO_CONTRACTS.json`;
- `STAGE_REGISTRY.json`;
- `METRIC_INPUT_AUTHORITY_MATRIX.json`.

At design freeze, the Entry review is an `M1_ADMISSION_CANDIDATE`. Feature implementation remains unauthorized until the merged-main activation artifact states `M1_ADMITTED`.

---

## 2. M1-A — Fixture Contract

Parent task:

`M1-TST-001`

### 2.1 First implementation target

The first fixture to become executable after admission is:

`BF_M1_NOMINAL_V1`

All eight governed bundle identities remain:

1. `BF_M1_NOMINAL_V1`
2. `BF_M1_GAP_V1`
3. `BF_M1_ANGLE_WRAP_V1`
4. `BF_M1_STRUCTURED_PARTIAL_V1`
5. `BF_M1_STAGE_BOUNDARY_V1`
6. `BF_M1_REPLAY_V1`
7. `BF_M1_CROSS_PLATFORM_V1`
8. `BF_M1_FAILURE_V1`

### 2.2 Bundle layout

The planned implementation layout is:

```text
tests/fixtures/m1/<fixture_id>/
├─ manifest.json
├─ source/
├─ context/
└─ expected/
```

This layout is test-harness organization only; it does not create persistence or Canonical schema authority.

Each manifest must carry at least:

- `fixture_id`
- `fixture_version`
- `input_sha256`
- `expected_sha256`
- `authority_refs`
- `tolerance_profile`
- `data_classification`
- `review_state`

Lifecycle:

```text
DRAFT → REVIEWED → APPROVED_GOLDEN → RETIRED
```

### 2.3 BF_M1_NOMINAL_V1 expected skeleton

Before implementation begins, the nominal fixture must have reviewable placeholders for:

- stable training-session identity inputs;
- one stable aircraft identity;
- explicit source-time → Session Time basis;
- the representative AIR Canonical channels;
- a Basic Flight Episode boundary basis;
- official-marker basis for the four `BASIC_FLIGHT_V1` stages;
- expected-result calculations that can be independently reproduced.

The expected output may not be created by simply copying the first output of the implementation under test.

---

## 3. M1-B — Data Spine

Parent tasks:

`M1-DATA-001..007`

The Data Spine is:

```text
controlled synthetic fixture
→ Synthetic Source Adapter
→ Source Registry / Source Artifact
→ explicit Session Time
→ stable Aircraft identity
→ Canonical aircraft state
→ immutable Evaluation Context
→ lineage / quality
```

### 3.1 Package ownership

Planned implementation ownership:

| Package | Responsibility |
| --- | --- |
| `tpaa_ingest` | fixture-only source adapter and physical→Canonical normalization boundary |
| `tpaa_registry` | source/source-stream/source-artifact registration orchestration |
| `tpaa_context` | immutable Evaluation Context resolution and binding consumption |
| `tpaa_storage` | persistence ports/repositories only; no M1 business semantics |

The packages may depend on generated/Canonical contracts but may not redefine them.

### 3.2 Source Adapter — M1-DATA-001

The adapter accepts only controlled M1 fixture bundles.

Required behavior:

- verify the bundle identity/version;
- verify input bytes against the manifest hash;
- use only versioned source-column mappings;
- produce stable source identity/provenance;
- reject uncontrolled operational/sensitive input in the M1 baseline path.

A physical source column may map to a Canonical field only through explicit versioned mapping metadata. Matching by “similar-looking” field names is forbidden.

### 3.3 Registry / Artifact registration — M1-DATA-002

Persistence uses the existing authority objects, including:

- `registry.training_session`
- `registry.data_source`
- `registry.source_stream`
- `registry.source_artifact`
- `registry.dataset_manifest`

A source artifact is addressable by immutable identity/hash. Managed Canonical datasets must also carry governed logical-content identity through the existing dataset-manifest contract.

No new M1-only persistence table is introduced by this design.

### 3.4 Session Time — M1-DATA-003

`CR-003 Session Time` is mandatory.

The implementation must make this transformation explicit:

```text
source time
+ frozen TimeTransform / mapping basis
→ authoritative session_time_us
```

Forbidden dependencies:

- host timezone;
- Windows/Linux local timezone defaults;
- locale-specific parsing;
- current wall-clock time as a business input.

At API/DTO boundaries where int64 is JS-visible, Session Time remains a decimal string as required by the existing contract.

### 3.5 Aircraft identity — M1-DATA-004

The business identity is the governed `aircraft_id`, not a source-local filename, row index, callsign or temporary adapter object.

Replay with the same frozen fixture/context must resolve the same governed aircraft identity.

Source-local aliases remain lineage evidence only.

### 3.6 Canonical flight channels — M1-DATA-005

For the five representative M1 AIR metrics, the minimum Canonical channel set is:

- `body_p_rad_s`
- `nz_g`
- `heading_true_rad`
- `tas_mps`
- `mach`
- `session_time_us`
- `quality_mask`

These names come from the Metric Catalog/Input Authority Matrix. The source adapter does not invent aliases above the normalization boundary.

Missing/invalid values do not become zero.

### 3.7 Evaluation Context — M1-DATA-006

The implementation consumes the existing:

- `EvaluationContextDTO`
- `ContextArtifactRefDTO`
- `context.evaluation_context`
- `context.context_artifact_binding`

At minimum, the M1 path must bind/resolve governed Rule Set and Metric Profile artifacts required by the Basic Flight evaluation path.

The Stage profile is the existing generated profile:

`StageProfileId.BASIC_FLIGHT_V1`

from `STAGE_REGISTRY 1.1.0`.

Important constraint: the current Canonical persistence binding vocabulary does not define a `STAGE_PROFILE` binding role. M1 must therefore **not invent one** in SQL/DTOs. The authoritative Stage-profile selection is carried by governed M1 context/provenance and the existing Stage Registry until Canonical authority explicitly adds another field or binding role.

### 3.8 Lineage and quality — M1-DATA-007

Every Canonical value that enters the M1 evaluation path must remain traceable to source artifact identity/hash.

Rules:

- missing remains missing;
- invalid remains invalid;
- quality never upgrades merely because normalization succeeded;
- gaps/validity/source boundaries remain visible to later Stage/Metric processing;
- managed Canonical products use existing dataset identity/hash/provenance contracts.

---

## 4. M1-C — Episode / Stage / World design-ahead

Parent tasks:

`M1-WORLD-001..007`, `M1-TST-003`

This is the detailed-design runway immediately following the Data Spine. It is prepared now so M1-B implementation does not lock the system into incompatible downstream interfaces.

### 4.1 Basic Flight Episode

The persistence authority is:

`episode.training_episode`

M1 uses:

`episode_type = BASIC_FLIGHT`

Requirements:

- deterministic/replayable episode identity inputs;
- half-open `[start_session_time_us,end_session_time_us)`;
- correction by new revision/supersession, not mutation of a published historical episode;
- explicit context reference;
- coverage/confidence/data-sufficiency carried as governed product state.

### 4.2 BASIC_FLIGHT_V1 Stage projector

The persistence authority is:

`episode.episode_stage`

The exact Stage order is:

```text
SETUP_ENTRY
→ EXECUTION
→ STABILIZATION_RECOVERY
→ COMPLETION
```

Stage intervals remain half-open.

The exact precedence order is:

1. `CONTEXT_OFFICIAL_MARKER`
2. `NORMALIZED_AUTHORITY_EVENT`
3. `CONTEXT_RULE_WORLD_DERIVATION`
4. `MODEL_INFERENCE`
5. `MANUAL_REVIEW`

Each Stage carries:

- `stage_status`
- `coverage`
- `confidence`
- `detector_version`

Corrections create a new Stage row using `supersedes_stage_id`; historical published Stage rows are not rewritten.

### 4.3 Stage Golden before Metric integration

`M1-TST-003` must freeze a deterministic Basic Flight Stage Golden before the project claims the first Metric vertical slice.

Metric code may not recreate Stage segmentation privately.

The first AIR-001 integration must consume the official Stage/World product produced by this layer.

### 4.4 Minimal P1 World

The M1 World contains only the observed-aircraft information needed by the representative AIR metrics.

It must not fabricate:

- perception not supported by current World capability;
- adjudication;
- official outcome;
- M2 sensor-system products.

`CR-018 World Capability Gate` remains governing.

The same frozen logical World input must produce cross-platform-stable logical identity/hash.

World/Stage/Canonical references needed by Metric Evidence must be addressable and immutable.

---

## 5. Critical implementation order after admission

After the merged-main Entry activation artifact authorizes implementation:

```text
M1-TST-001
→ M1-DATA-001
→ M1-DATA-002
→ M1-DATA-003
→ M1-DATA-004
→ M1-DATA-005
→ M1-DATA-006
→ M1-DATA-007
→ M1-WORLD-001
→ M1-WORLD-002
→ M1-WORLD-003
→ M1-WORLD-004
→ M1-WORLD-006
→ M1-WORLD-007
→ M1-TST-003 Stage Golden
→ M1-MET-001 / M1-MET-002 (AIR-001)
```

This is deliberately narrower than spreading implementation across all 56 M1 tasks.

---

## 6. M2 boundary

The M1 vertical slice continues to exclude:

- RADAR
- IRST
- ESM
- DL
- FUS

Before M1 Exit GO, M2 work remains design-seed only: interfaces, risks, ADR questions, evidence needs and compatibility constraints. It does not become implementation authority.

---

## 7. Design acceptance

This design is implementation-ready when machine verification confirms:

- all eight fixture identities match the frozen fixture policy;
- representative AIR inputs map to Canonical authority fields;
- required source/context/episode/stage persistence authority objects exist;
- `BASIC_FLIGHT_V1` Stage order and precedence match `STAGE_REGISTRY`;
- Session Time/Missing/Context/World/platform rules remain bound to the frozen Core Rules;
- no M2 sensor family is introduced into the M1 vertical slice;
- no pre-admission feature implementation is authorized by this document.
