# M1-DATA-003 — Session Time ingest path

## Scope

This task implements the SDIB-1.0.1 M1-DATA-003 minimum acceptance:

> 源时间→Session Time 显式；不依赖 OS timezone/locale

The implementation consumes the already-governed M1 source bundle and immutable
registry identity produced by M1-DATA-001/002. It adds only the explicit
source-clock → Session Time step.

## Authority

The governing Core Rule is `CR-003 Session Time`:

- computation uses authoritative Session Time;
- source clocks require an explicit TimeTransform;
- JS-visible int64 time transports as decimal string.

The persistent field authority remains
`baseline/CB-1.4.0/canonical/CORE_LOGICAL_MODEL.json`, especially:

- `registry.source_clock_segment`;
- `registry.time_transform`.

No schema, field, enum, DTO, Stage, Metric, or Canonical flight-channel semantic
is redefined by this task.

## Controlled M1 fixture transform

Every current governed M1 fixture carries:

```json
{
  "source_time_transform": {
    "kind": "OFFSET_US",
    "offset_us": "1000000"
  }
}
```

`OFFSET_US` is a controlled fixture-input shape, not a new Canonical
persistence model.

M1-DATA-003 translates it to the frozen Canonical-compatible model:

```text
model = ANCHORED_RATIONAL

segment_time_ns = source_time_us * 1000

session_time_us =
    anchor_session_time_us
    + (segment_time_ns - anchor_segment_time_ns)
      * rate_num / rate_den

rate_num = 1
rate_den = 1000
```

For the nominal fixture:

```text
source 0 us       -> Session 1,000,000 us
source 1,000,000  -> Session 2,000,000 us
...
source end 8,000,000 -> Session end 9,000,000 us
```

Only exact integral rational conversion is accepted. The implementation never
silently rounds.

## Source clock segmentation boundary

The M1 fixtures currently contain one monotonic source-clock segment each.

The implementation:

1. preserves physical row order from the Source Adapter;
2. parses source time only as canonical ASCII decimal integer text;
3. detects backward source-clock movement before any reordering;
4. creates a deterministic source-clock-segment identity;
5. creates a deterministic TimeTransform identity;
6. applies the transform to source rows and source markers.

If source clock rollback is observed without an explicit segment contract, the
task fails closed with
`M1_SESSION_TIME_CLOCK_ROLLBACK_UNSEGMENTED`.

This preserves the ED-2.0 ordering rule:

```text
physical artifact order
-> stream ordinal
-> clock reset / segment
-> validated TimeTransform
-> Session Time
```

## Deterministic identity and hash

The implementation uses UUIDv5 for:

- `source_clock_segment_id`;
- `time_transform_id`.

The transform hash covers the exact Canonical-compatible transform parameters.
The per-fixture logical hash covers:

- fixture/session/source identities;
- transform identity/hash;
- start/end Session Time;
- row source ordinal/source time/Session Time;
- marker source time/Session Time/value.

No random UUID, wall clock, host path, locale, or timezone participates.

## Fail-closed parsing

Accepted source time examples:

```text
0
1000000
8000000
```

Accepted offset examples:

```text
0
1000000
-1000000
```

Rejected forms include:

```text
+1000000
01
1,000,000
1 000 000
1000000.0
<leading/trailing whitespace>
```

This makes the parser independent of OS locale conventions.

## Task boundary

M1-DATA-003 intentionally leaves the following for later work:

```text
database_persistence_executed = false
canonical_flight_channel_projection_executed = false
stage_projection_executed = false
metric_logic_executed = false
```

M1-DATA-004 owns stable aircraft entity resolution.
M1-DATA-005 owns Canonical flight-channel projection.
M1-DATA-006 owns Evaluation Context artifact binding.

## Acceptance command

```text
python tools/dev/tpaa_dev.py m1-session-time-check
```

Windows/Linux CI archives exact evidence at:

```text
evidence/m1-data-003/<platform>/session-time.json
```

The evidence serializes all JS-visible/int64 time values as decimal strings.
