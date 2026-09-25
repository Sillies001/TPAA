# M1 Batch 1 — World and Representative Metric Core Product

Tracking Issue: #86. Governance Issue: #85.

This batch completes `M1-WORLD-004..007`, `M1-MET-001..008`,
`M1-TST-002` and `M1-TST-003` as one reviewable domain increment.

## World product

`tpaa_world.minimal_p1` builds a release-bound, immutable
`M1_P1_AIRCRAFT_OBSERVED_WORLD_V1` product from the governed Evaluation
Context, Canonical aircraft rows, Basic Flight Episode and qualified Stages.
Its logical content uses canonical JSON and is independent of OS-local paths,
PIDs and native package bytes. Exact Context, Canonical, Episode and Stage refs
flow into downstream Metric Evidence.

The product declares only evidence-backed C/W/A/M inputs. P and J remain
explicitly absent; neither perception nor adjudication is fabricated.

Stage correction is append-only: `supersede_stage` creates a new deterministic
Stage identity linked through `supersedes_stage_id`; the historical Stage value
is never mutated.

## Metric product

`tpaa_metric` binds the frozen `P1_METRIC_CATALOG`, exact Evaluation Profile,
Aircraft subject and immutable input refs in `MetricContext`. It implements:

- P1-AIR-001 maximum absolute body roll rate with coverage and max-gap gates;
- P1-AIR-002 maximum Nz with diagnostic minimum retained only in Evidence;
- P1-AIR-003 heading unwrap plus `DERIVATIVE_LLS_V1`;
- P1-AIR-004 `ROLLING_MEDIAN_V1` sustained heading-rate evidence;
- P1-AIR-007 typed `STRUCT_P1_AIR_007_V1` TAS/Mach envelope using
  `QUANTILE_HF7_V1`.

Applicability and typed result slots fail closed. Missing prerequisites produce
`N_A` or `INSUFFICIENT_DATA` with reason codes and never fabricate zero.
Computation returns an immutable staging batch; the staging component exposes
no publish operation and failed staging cannot change current published state.

## Evidence

The consolidated command is:

```text
python tools/dev/tpaa_dev.py m1-batch-1-core-check --evidence <path>
```

It evaluates all eight governed fixtures, Stage Golden boundaries, nominal and
edge/failure Metric expectations, immutable Stage supersede behavior, replay
stability and exact evidence refs. Windows and Linux artifacts are compared by
`m1-batch-1-compare`; exact equality is required.

This batch does not implement Observation, Release, persistence, API or GUI.
Those remain in #87 and later batches.
