# M1-DATA-004 — Aircraft entity resolution

## Scope

M1-DATA-004 resolves the single controlled M1 aircraft to the governed
`aircraft_id` carried by the frozen synthetic fixture. The source-local
`source_aircraft_key` remains lineage evidence only.

This implementation follows the existing M1 Data Spine order and does not
change Canonical authority.

## Authority and identity rule

The frozen logical model defines `master.aircraft.aircraft_id` as the aircraft
business identity. The M1 detailed design therefore requires:

- use the governed `aircraft_id` field as business identity;
- do not derive business identity from filename, row ordinal, source alias,
  callsign, adapter object identity, host state, or wall clock;
- preserve `source_aircraft_key` only as lineage;
- replaying the same frozen fixture/context resolves the same
  `aircraft_id`.

The controlled eight-fixture profile represents one aircraft. The acceptance
path fails closed if those fixtures resolve to more than one governed
`aircraft_id`.

## Implementation boundary

`src/tpaa_registry/aircraft_identity.py`:

1. loads the already-governed synthetic source bundle;
2. reuses immutable M1-DATA-002 Source Registry lineage;
3. validates `aircraft_id` as canonical non-nil UUID text;
4. records immutable source/context hashes as replay basis;
5. emits a deterministic logical hash for the resolution record;
6. enforces the single-aircraft profile across all eight governed fixtures.

The task does **not**:

- write `master.aircraft`;
- create `master.aircraft_instance`;
- project M1-DATA-005 Canonical flight channels;
- bind M1-DATA-006 Evaluation Context;
- execute Stage, World, Metric, Observation, or Release logic.

## Replay evidence

The governed command is:

`python tools/dev/tpaa_dev.py m1-aircraft-identity-check`

CI archives one platform-specific evidence file:

`evidence/m1-data-004/<platform>/aircraft-identity.json`

Acceptance requires:

- eight fixture resolutions;
- exactly one governed `aircraft_id`;
- exact replay equality across repeated resolution;
- eight immutable fixture-specific replay-basis hashes;
- source alias role exactly `LINEAGE_ONLY`;
- no downstream persistence/channel/context/Stage/Metric execution.
