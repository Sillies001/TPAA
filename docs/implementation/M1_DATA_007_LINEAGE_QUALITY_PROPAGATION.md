# M1-DATA-007 — Lineage / quality propagation

## Scope

M1-DATA-007 completes the M1-B Data Spine by attaching field-level immutable
source lineage to the exact seven Canonical aircraft-state channels already
implemented by M1-DATA-005. It also proves that the existing source
`quality_mask` and missing-value state are propagated without reinterpretation.

This task does not redefine Canonical fields, quality bits, Metric inputs, Stage
semantics, DTOs, or persistence schema.

## Lineage contract

Every Canonical field records the immutable M1 source-artifact ref and SHA-256
from M1-DATA-002, deterministic source-stream ID, source row ordinal, exact
physical source field, frozen source mapping version, unchanged row
`quality_mask`, and only `PRESENT` or `MISSING` value state.
`session_time_us` additionally carries the authoritative M1-DATA-003
time-transform hash.

The field mapping remains exactly: `p -> body_p_rad_s`,
`nz -> nz_g`, `heading -> heading_true_rad`, `tas -> tas_mps`,
`mach -> mach`, `source_time_us -> session_time_us`, and
`quality -> quality_mask`.

## Missing and invalid values

Missing TAS/Mach samples remain null and are marked `MISSING`; they are never
replaced by zero. Invalid physical numeric values continue to fail closed at the
existing M1-DATA-005 Canonical boundary. M1-DATA-007 does not repair, coerce, or
zero-fill them.

## Hard boundary

This is in-memory evidence construction only. It does not persist source,
Canonical, lineage, or quality rows; segment Episodes or Stages; build World
products; or execute Metric, Observation, or Release logic.

## Parallel design runway

The one-wave-ahead M1-C Episode / Stage / World design completed by PR #76
remains the active runway. This task does not advance M1-D or M1-E detailed
design two waves ahead.

## Evidence

Governed command:

`python tools/dev/tpaa_dev.py m1-lineage-quality-check`

Windows/Linux CI archives:

`evidence/m1-data-007/<platform>/lineage-quality.json`

Acceptance requires eight fixtures, 62 rows, 434 field-lineage bindings, exact
immutable source refs, exact quality-mask propagation, eight governed missing
values preserved, invalid values fail-closed, replay-stable hashes, and no
downstream Episode/Stage/World/Metric or database execution.
