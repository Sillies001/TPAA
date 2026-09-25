# M1-F Desktop Vertical Slice Implementation Design

## Role and authority

This document is implementation design for coarse Batch 3 / Issue #89. It is not
semantic authority. SDIB-1.0.1 and frozen CB-1.4.0 artifacts remain authoritative
for Canonical, Metric, Stage, DTO, Release, and persistence semantics.

Batch 3 consumes the protected-main Batch 2 products at
`f1f09441a9e23428dfc844ee67d712b8b927332a`. The GUI is only a projection and
interaction adapter. It must not calculate Metric formulas, infer Stage
boundaries, invent publication identities, or substitute current state for an
explicit historical Release.

## Desktop transport boundary

ADR-M0-005 remains in force:

- one GUI process owns one isolated local FastAPI child;
- the GUI talks to the child only through authenticated loopback HTTP;
- the bearer token remains memory-only inside `LocalBackendController`;
- Desktop HTTP keeps docs/CORS disabled and rejects unexpected Origin headers;
- M1 routes are admitted only under the existing Desktop bearer dependency and
  an explicit `/m1/` path prefix;
- normal shutdown remains private stdio `SHUTDOWN`, never an HTTP route.

The local child wires the same `M1PublicationService`,
`InMemorySessionPublicationRepository`, and `ApplicationService` used by the
Batch 2 service evidence. No business logic moves into PySide6.

## M1-GUI-001 / Session Browser

The first governed synthetic journey uses `BF_M1_NOMINAL_V1`. The browser
selects a fixture and, after publication, the explicit immutable Release id.

Publication identity fields are explicit user/test inputs. The GUI does not
derive aircraft model, aircraft instance, subject entity, capability dimension,
or capability type from filenames, aliases, row order, or UI state.

## M1-GUI-002 / Context header

The header renders only release-bound API projections:

- runtime baseline/readiness from existing diagnostics;
- Release id/status/provenance;
- Context id/version/rule-set;
- Session id.

## M1-GUI-003 / Master timeline

One session-time cursor drives all Batch 3 timeline projections. Moving it:

- updates the visible cursor time;
- marks the release-bound Stage interval containing the cursor;
- publishes the same cursor value beside Metric Detail and Evidence panes.

No Stage boundary is calculated in the UI; intervals come from the release-bound
`/topology` projection.

## M1-GUI-004 / Stage lane

All four `BASIC_FLIGHT_V1` Stage projections are rendered in Stage order with
their API-provided start/end times, status, coverage, and confidence.

## M1-GUI-005 / Metric list

The five release-bound representative Metrics are rendered from `/metrics`.
Quality columns are joined only from release-bound Capability Observation
coverage/confidence values; the GUI does not derive quality thresholds.

## M1-GUI-006 / Metric Detail and Evidence

Selecting a Metric reads the immutable release-bound Detail and Evidence
endpoints. The UI displays Definition identity/hash and Evidence refs/details.
It never contains formula implementations.

## M1-GUI-007 / failure-state distinction

The Desktop includes stable, visually distinct state badges for
`N_A`, `INSUFFICIENT`, `INVALID`, and `SYSTEM_ERROR`. Actual Metric status
is rendered verbatim from the backend; transport/system failures map only to the
`SYSTEM_ERROR` presentation state.

## M1-TST-008 / Desktop E2E

The real PySide6 automation path must exercise:

`import -> compute -> publish -> release/context/topology -> timeline cursor ->
metric detail/evidence -> replay -> close/cleanup`.

The automation supplies explicit synthetic publication identities; this is test
input, not production authority.

## M1-PLAT-001 / M1-PLAT-002

Windows and Linux Hosted CI run the same headless Desktop journey on the same
`BF_M1_NOMINAL_V1` fixture and emit exact-source-revision evidence. A final
cross-platform Batch 3 review fails closed unless all ten #89 rows PASS.

## Completion boundary

PR green is insufficient. Batch 3 completes only after exact candidate-head
Hosted CI, exact-head merge, and protected-main push CI on the exact merged SHA.
