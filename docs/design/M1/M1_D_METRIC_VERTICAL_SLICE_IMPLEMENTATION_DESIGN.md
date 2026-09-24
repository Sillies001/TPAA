# M1-D Metric Vertical Slice Implementation Design

## Role

This is the rolling one-wave-ahead implementation design while M1-C Episode /
Stage / World is under construction. It is implementation design only and does
not redefine Canonical, Metric, Stage, DTO, or persistence authority.

M1-D feature implementation remains blocked until the M1-C prerequisites close,
including Stage Golden M1-TST-003. This document does not advance M1-E
Observation/Release implementation design.

## Construction anchors

The M1-D construction anchors are M1-MET-001..008.

The first vertical slice consumes exact, already-published M1-C references:
Evaluation Context, Canonical input refs, Episode, Stage and World evidence.
Metric code may not re-segment Episode/Stage intervals or resolve "latest"
artifacts during historical replay.

## MetricContext

MetricContext is built only from frozen Catalog/Profile authority and explicit
input refs. UI state and ad-hoc database columns are not authority.

The builder carries:
- immutable metric catalog/profile refs and hashes;
- exact subject identity and scope;
- exact Evaluation Context ref;
- exact Episode/Stage/World/Canonical evidence refs;
- validity/coverage inputs and governed parameters.

## First five P1 AIR metrics

Implementation order remains M1-MET-002 through M1-MET-006:
P1-AIR-001, P1-AIR-002, P1-AIR-003, P1-AIR-004, P1-AIR-007.

Algorithms, value kinds, units, validity, coverage and evidence semantics come
from the frozen P1 Metric Catalog. The implementation may not replace missing
inputs with zero or change structured result shape.

P1-AIR-003 must use the governed unwrap + DERIVATIVE_LLS_V1 path and preserve
gap behavior. P1-AIR-004 must use the governed rolling-median/sustained-dwell
path. P1-AIR-007 must emit the authoritative typed STRUCT_P1_AIR_007_V1 result.

## Applicability and staging

M1-MET-007 enforces exact subject/applicability and result value-kind slots.
M1-MET-008 computes into staging only. Failed or incomplete compute must not
change a published/current result.

## Golden and replay gates

M1-TST-003 Stage Golden is a hard prerequisite before Metric implementation.
Metric Golden comparisons use independently reviewable expected values and
platform-neutral logical products. Historical replay uses release/context-bound
refs and never a latest fallback.

## Hard boundary

This design does not implement Observation, Release, publish CAS, API, GUI, or
M1-E feature code. It intentionally stays one construction wave ahead.
