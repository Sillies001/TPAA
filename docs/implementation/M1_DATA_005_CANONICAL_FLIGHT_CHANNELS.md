# M1-DATA-005 — Canonical flight channels

## Scope

M1-DATA-005 projects the governed M1 synthetic aircraft samples onto the
existing `CANONICAL_AIRCRAFT_STATE_V1` view. It consumes the already-closed
M1-DATA-001..004 products and does not redefine Canonical field identity,
Metric inputs, Stage semantics, DTOs, or persistence schema.

The exact minimum channel set is:

- `body_p_rad_s`
- `nz_g`
- `heading_true_rad`
- `tas_mps`
- `mach`
- `session_time_us`
- `quality_mask`

The names are taken from the frozen Metric Input Authority Matrix and the
M1-A/B/C detailed design.

## Projection contract

The controlled fixture mapping remains exactly:

| Physical source | Canonical |
| --- | --- |
| `p` | `body_p_rad_s` |
| `nz` | `nz_g` |
| `heading` | `heading_true_rad` |
| `tas` | `tas_mps` |
| `mach` | `mach` |
| `source_time_us` | `session_time_us` through M1-DATA-003 |
| `quality` | `quality_mask` |

The projector accepts authoritative Session Time and governed aircraft identity
as explicit upstream inputs. It validates numeric values and quality masks,
preserves source row order, and emits a deterministic platform-neutral logical
hash.

Missing numeric values remain `null`. In particular,
`BF_M1_STRUCTURED_PARTIAL_V1` retains the four missing TAS samples and four
missing Mach samples. Normalization never converts missing or invalid values to
zero.

## Implementation boundary

`src/tpaa_ingest/canonical_flight_channels.py` owns the M1 physical-to-
Canonical normalization boundary. It deliberately does not:

- persist a Canonical dataset or write database rows;
- bind M1-DATA-006 Evaluation Context;
- implement M1-DATA-007 full lineage/quality propagation;
- segment Episodes or Stages;
- build World products;
- execute Metric, Observation, or Release logic.

The acceptance harness composes the frozen source adapter, authoritative Session
Time projection, and replay-stable aircraft identity before invoking the
Canonical projector. This makes upstream identity/time drift fail closed.

## Parallel design runway

The required one-wave-ahead M1-C Episode / Stage / World implementation design
was completed in parallel on PR #76 before this task. DATA-005 confirms its
upstream interface without changing that design: M1-C receives authoritative
aircraft identity and Session-Time-based Canonical aircraft state, while M1-C
feature code remains blocked until M1-DATA-001..007 are closed.

No M1-D/M1-E feature or two-waves-ahead detailed-design authority is introduced
by this task.

## Evidence

The governed command is:

`python tools/dev/tpaa_dev.py m1-canonical-flight-channels-check`

Windows/Linux CI archives:

`evidence/m1-data-005/<platform>/canonical-flight-channels.json`

Acceptance requires eight fixture projections, the exact seven-channel contract,
62 governed rows, replay-stable logical hashes, preservation of all eight
fixture-level missing values, and no downstream Context/Stage/World/Metric or
database execution.
