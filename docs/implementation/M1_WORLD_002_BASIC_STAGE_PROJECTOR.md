# M1-WORLD-002 BASIC_FLIGHT_V1 Stage projector

## Authority and scope

This implementation consumes the frozen `STAGE_REGISTRY 1.1.0`, the accepted
M1-C implementation design, authoritative Session Time markers, and the
M1-WORLD-001 Basic Episode. It does not redefine Stage semantics.

The projector publishes exactly four in-memory intervals in registry order:

`SETUP_ENTRY -> EXECUTION -> STABILIZATION_RECOVERY -> COMPLETION`.

Every interval is `[start_session_time_us,end_session_time_us)`. The official
`END` marker terminates `COMPLETION`; it is never emitted as a Stage code.
Official markers use the highest frozen precedence source,
`CONTEXT_OFFICIAL_MARKER`, which maps to detection method `CONTEXT`.

## Fail-closed behavior

Projection fails for a missing terminator, unknown Stage code, duplicate or
out-of-order marker, non-positive interval, incomplete Episode boundary
coverage, or any interval crossing its Episode boundary.

## Hard boundary

This task does not persist rows and does not implement M1-WORLD-003 quality or
status, M1-WORLD-005 revision/supersede behavior, M1-WORLD-006 logical hashes,
M1-WORLD-007 evidence refs, World products, Metrics, Observations, or Releases.
Those boundaries are surfaced explicitly in the acceptance evidence.
