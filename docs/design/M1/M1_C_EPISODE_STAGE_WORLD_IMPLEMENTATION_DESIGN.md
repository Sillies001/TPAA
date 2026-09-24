# M1-C Episode / Stage / World Implementation Design

## Purpose

This is the rolling one-wave-ahead detailed design required while M1-B Data Spine
is being implemented. It prepares the M1-C construction wave without starting
M1-C feature code early.

Machine companion:

`docs/design/M1/M1_C_EPISODE_STAGE_WORLD_IMPLEMENTATION_DESIGN.json`

This document is implementation design, not semantic authority. CB-1.4.0
remains authoritative for Canonical fields, persistence objects, Stage semantics,
World capability semantics and DTO contracts.

## Entry conditions for M1-C implementation

Design work may proceed in parallel with M1-B. M1-C implementation itself waits
for the M1 Data Spine to close in order:

`M1-DATA-001 → 002 → 003 → 004 → 005 → 006 → 007`.

The M1-C implementation anchors are `M1-WORLD-001..007` and
`M1-TST-003`.

## Basic Flight Episode contract

The persistence authority is `episode.training_episode`.

The first slice uses:

- `episode_type = BASIC_FLIGHT`;
- `subject_scope = AIRCRAFT`;
- authoritative `primary_aircraft_id`;
- half-open `[start_session_time_us,end_session_time_us)`;
- immutable `context_id`;
- explicit detector version and quality state.

A replay identity must be a deterministic function of the frozen session,
context, aircraft identity, interval and detector version. Corrections create a
new row linked with `supersedes_episode_id`; published historical rows are
never updated in place.

## BASIC_FLIGHT_V1 Stage projection

The exact Stage order remains:

`SETUP_ENTRY → EXECUTION → STABILIZATION_RECOVERY → COMPLETION`.

The exact precedence remains the order frozen in `STAGE_REGISTRY 1.1.0`:

1. `CONTEXT_OFFICIAL_MARKER`
2. `NORMALIZED_AUTHORITY_EVENT`
3. `CONTEXT_RULE_WORLD_DERIVATION`
4. `MODEL_INFERENCE`
5. `MANUAL_REVIEW`

For the first controlled fixtures, official Stage markers are mapped through the
already-authoritative Session Time transform. The terminal `END` marker closes
the last interval and is **not** a Stage code.

Stage interval construction is:

`stage_i = [marker_i, marker_i+1)`.

The projector fails closed for a missing terminator, duplicate/out-of-order
governed Stage marker, unknown Stage code, a marker outside the Episode, or an
interval that crosses an Episode revision boundary.

The detector must carry `stage_status`, `coverage`, `confidence` and
`detector_version`. Corrections supersede rows through
`supersedes_stage_id`; historical published stages are not mutated.

## Stage Golden

`M1-TST-003` is a hard gate before the first Metric vertical slice.

The Golden basis uses `BF_M1_NOMINAL_V1` as the primary four-Stage case and
`BF_M1_STAGE_BOUNDARY_V1` for boundary behavior. Discrete identity, Stage,
order, time-boundary, detection-method and status outputs are exact. Coverage
and confidence follow governed numeric acceptance. Expected results remain
independently reviewable and may not be copied from the implementation under
test.

No Metric implementation may privately re-segment Episode or Stage boundaries.

## Minimal World contract

World persistence uses existing `world.world_product_manifest` authority and
the existing `WORLD_CAPABILITY_REGISTRY 1.0.0`.

For `BASIC_CORE`, capability letters C/W/A/M are required; P/J are optional.
M1-C may publish only world products actually supported by governed evidence and
only with an existing `world_kind` value:

`CONTEXT | TRUTH | PERCEPTION | ACTION | ADJUDICATION | MACHINE`.

This design does **not** invent an M1-only world kind. It also does not permit
synthetic perception or adjudication merely to satisfy a downstream consumer.
Truth cannot substitute for missing P, and missing J cannot become an inferred
official result.

Logical identity/hash inputs are platform-neutral. Windows/Linux path, PID and
native package bytes cannot participate in World business identity.

## Guardrails

This design does not:

- redefine Canonical or Stage semantics;
- start Metric business logic;
- add database migrations;
- add RADAR/IRST/ESM/DL/FUS to the M1 vertical slice;
- branch business behavior by OS;
- authorize M1-C implementation before M1-DATA-007 closes.

The design is advanced in parallel with M1-B exactly as required by the rolling
design runway.
